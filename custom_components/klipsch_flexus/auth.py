"""HMAC-SHA256 write-authentication for 2026 Klipsch firmware.

The May-2026 firmware sets ``settings:/webserver/authMode = setData``: every
write except volume/mute must carry an HMAC-SHA256 signature, otherwise the
device answers ``401 Forbidden`` with header
``WWW-Authenticate: HMAC_SHA256_AES256``. See
``docs/PROTOCOL_2026_CHANGES.md`` for the full reverse-engineering writeup.

The credential is **per-device, derived from the MAC** (which the integration
already discovers from ``eureka_info`` on port 8008). The official Klipsch
Connect Plus app provisions this same MAC-derived password onto the device
during onboarding, so the unit already rejects unsigned writes out of the box.

Scheme — fully recovered from ``libapp.so`` of Connect Plus v2.3.7 (blutter +
Frida ground-truth) and **confirmed live against the device (HTTP 200)**:

    username  = "user"                                   # generateUsernameFromMac
    password  = base64(MAC_UPPER_HEX + "KlipschSupport!!88")   # generatePasswordFromMac
    nonce     = base64(6 random bytes)        # fresh per request (client-generated)
    ts        = current time in ms (string)
    key       = sha256(base64decode(nonce) + password)   # per-request; AES *and* HMAC
    value_b64 = base64(iv + AES_256_CBC(key, iv).encrypt(PKCS7(value_json)))
    body      = json(indent=4) {"path", "role": "value", "value": value_b64}
    canonical = f"{username}.{nonce}.{ts}.{url}.{body}"
    sig       = base64(HMAC_SHA256(key, canonical))
    header    = f"HMAC_SHA256_AES256 {base64(username)}.{nonce}.{ts}.{sig}"

There is **no server salt/challenge** — nonce, IV and timestamp are all
client-generated, so the request is fully reproducible offline from the (public)
MAC plus the hardcoded ``KlipschSupport!!88`` constant. That constant is the same
in every install, so this works for *any* Flexus device (only the MAC varies).
The ``HMAC_SHA256_AES256`` 401 challenge is only the *pre-provisioning* fallback.

``tools/extract_secret.py`` re-extracts the constant from a future APK if Klipsch
ever changes it. The public entry point is :meth:`KlipschAuth.build_set_data`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time

from cryptography.hazmat.primitives import padding as _sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)

# StreamUnlimited webserver default account. The app logs
# "Pushing webserver password to device (username: user)".
DEFAULT_USERNAME = "user"

# Value of settings:/webserver/authMode that gates writes behind a signature.
AUTH_MODE_SETDATA = "setData"

# Scheme advertised by the device in the WWW-Authenticate header on 401.
AUTH_SCHEME = "HMAC_SHA256_AES256"

# Hardcoded "secret" interpolated into the MAC for the webserver password.
# Recovered verbatim from generatePasswordFromMac in Connect Plus v2.3.7. It is
# the same constant in every app install — combined only with the (public) MAC,
# so the resulting password is fully reproducible by any LAN client. Kept here
# as-is purely to reproduce the device's provisioned credential.
_PASSWORD_SECRET = "KlipschSupport!!88"


def normalize_mac(mac: str) -> str:
    """Reduce a MAC to its canonical form for credential derivation.

    eureka_info reports the MAC as e.g. ``34:3D:7F:00:2F:3D``; the app may key
    derivation off a specific casing/separator. This returns lowercase hex with
    no separators (``343d7f002f3d``) as the working assumption — adjust here if
    the decompiled ``generate*FromMac`` expects colons or uppercase.
    """
    return mac.replace(":", "").replace("-", "").lower()


def generate_username_from_mac(mac: str) -> str:
    """Webserver username derived from the device MAC.

    Mirrors ``generateUsernameFromMac`` in the app. The default observed on the
    wire is the literal ``"user"``; if the app actually derives a per-device
    username, replace the body below with the exact derivation.
    """
    # ── FILL IN (1/3): exact username derivation from decompiled app ──
    return DEFAULT_USERNAME


def generate_password_from_mac(mac: str) -> str:
    """Webserver password derived from the device MAC.

    Exact reproduction of ``generatePasswordFromMac`` from Connect Plus v2.3.7:

        cleaned  = mac.replaceAll(RegExp("[^A-F0-9]"), "")   # UPPER hex, 12 chars
        password = base64( utf8( cleaned + "KlipschSupport!!88" ) )

    The app's regex keeps only **uppercase** hex, so we uppercase first — this
    makes the derivation independent of the incoming MAC casing while producing
    exactly what the app (fed an uppercase eureka MAC) provisioned onto the
    device. This is the plaintext password that feeds the per-request key
    derivation ``sha256(nonce + password)`` (see :func:`_request_key`).
    """
    cleaned = re.sub(r"[^A-F0-9]", "", mac.upper())
    return base64.b64encode((cleaned + _PASSWORD_SECRET).encode("utf-8")).decode("ascii")


def _request_key(nonce_raw: bytes, password: str) -> bytes:
    """Per-request key = ``SHA256(nonce_raw || password)``.

    Recovered and confirmed live from Connect Plus v2.3.7: the **same** 32-byte
    key both AES-256-CBC-encrypts the body value and keys the HMAC-SHA256
    signature. ``nonce_raw`` is the raw (Base64-decoded) client nonce;
    ``password`` is the Base64 string from :func:`generate_password_from_mac`,
    hashed as its ASCII bytes. There is no server salt/challenge — nonce, IV and
    timestamp are all client-generated, so the whole request is reproducible
    offline from the (public) MAC plus the hardcoded password secret.
    """
    return hashlib.sha256(nonce_raw + password.encode("ascii")).digest()


def _encrypt_value(key: bytes, plaintext: bytes) -> str:
    """AES-256-CBC encrypt ``plaintext`` (PKCS7) → ``base64(iv + ciphertext)``.

    The random IV is prepended to the ciphertext before Base64 — the device has
    no separate IV field; it splits the first 16 bytes back off on decrypt.
    """
    iv = os.urandom(16)
    padder = _sym_padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode("ascii")


class KlipschAuth:
    """Holds MAC-derived credentials and signs setData requests.

    Created once per device from the discovered MAC + host; reused for every
    write. ``host`` is the device IP/hostname that appears in the canonical URL
    (it is part of the signed string, so it must match the request target).
    """

    def __init__(self, mac: str, host: str) -> None:
        self._mac = normalize_mac(mac)
        self._host = host
        self.username = generate_username_from_mac(self._mac)
        # generate_password_from_mac re-uppercases internally, so the lowercase
        # normalized MAC is fine here. Computed lazily on first write.
        self._password: str | None = None

    @property
    def password(self) -> str:
        if self._password is None:
            self._password = generate_password_from_mac(self._mac)
        return self._password

    @property
    def set_data_url(self) -> str:
        return f"https://{self._host}/api/setData"

    def build_set_data(self, path: str, value: dict) -> tuple[str, dict[str, str]]:
        """Build a signed ``POST /api/setData`` request.

        ``value`` is the plaintext value object, e.g.
        ``{"type": "cinemaDialogMode", "cinemaDialogMode": "dialog_2"}``.

        Returns ``(body, headers)`` — the request **body string** (with the
        value AES-encrypted) and the headers (incl. the ``Authorization``
        signature). Send them verbatim over HTTPS (the device serves a
        self-signed Klipsch-CA cert, so the client must skip verification).

        Exact reproduction of ``HmacAuthHelper.generateAuthHeader`` from Connect
        Plus v2.3.7, verified live against the device (HTTP 200):

            nonce_raw = 6 random bytes;  nonce = base64(nonce_raw)
            ts        = current time in ms (decimal string)
            key       = SHA256(nonce_raw + password)
            value_b64 = base64(iv + AES_256_CBC(key, iv).encrypt(PKCS7(value_json)))
            body      = json(indent=4) {"path", "role": "value", "value": value_b64}
            canonical = f"{user}.{nonce}.{ts}.{url}.{body}"
            sig       = base64(HMAC_SHA256(key, canonical))
            header    = f"HMAC_SHA256_AES256 {base64(user)}.{nonce}.{ts}.{sig}"
        """
        nonce_raw = os.urandom(6)
        nonce = base64.b64encode(nonce_raw).decode("ascii")
        ts = str(int(time.time() * 1000))
        key = _request_key(nonce_raw, self.password)

        # The value is encrypted as its COMPACT JSON encoding (no whitespace).
        value_json = json.dumps(value, separators=(",", ":")).encode("utf-8")
        value_b64 = _encrypt_value(key, value_json)

        # The body is PRETTY-printed (4-space indent); the signature is computed
        # over this exact serialization, so it must match the bytes that are
        # sent byte-for-byte (key order: path, role, value).
        body = json.dumps({"path": path, "role": "value", "value": value_b64}, indent=4)

        canonical = f"{self.username}.{nonce}.{ts}.{self.set_data_url}.{body}"
        sig = base64.b64encode(hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).digest()).decode("ascii")

        user_b64 = base64.b64encode(self.username.encode("ascii")).decode("ascii")
        authorization = f"{AUTH_SCHEME} {user_b64}.{nonce}.{ts}.{sig}"
        return body, {
            "Content-Type": "application/json",
            "Authorization": authorization,
        }
