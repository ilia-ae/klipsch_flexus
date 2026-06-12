"""Tests for the 2026 firmware write-authentication (auth.py).

Known-answer tests for the MAC-derived credential and the full
``HMAC_SHA256_AES256`` request signing. The signing vector below is a real
ground-truth request captured from the official Connect Plus app (Frida hook on
``generateAuthHeader`` / ``Encrypter.encrypt``); feeding the same nonce/IV/ts
back in must reproduce it byte-for-byte.
"""

from __future__ import annotations

import base64
import json

from custom_components.klipsch_flexus.auth import (
    KlipschAuth,
    generate_password_from_mac,
    generate_username_from_mac,
    normalize_mac,
)

# Lab unit MAC (from eureka_info). Derivation must be reproducible from this.
TEST_MAC = "34:3D:7F:00:2F:3D"
TEST_HOST = "10.0.1.51"


def test_normalize_mac_strips_separators_and_lowercases():
    assert normalize_mac("34:3D:7F:00:2F:3D") == "343d7f002f3d"
    assert normalize_mac("34-3D-7F-00-2F-3D") == "343d7f002f3d"
    assert normalize_mac("343d7f002f3d") == "343d7f002f3d"


def test_username_default_is_user():
    assert generate_username_from_mac(normalize_mac(TEST_MAC)) == "user"


def test_password_derivation_known_answer():
    # base64(utf8("343D7F002F3D" + "KlipschSupport!!88")) — exact app derivation.
    expected = "MzQzRDdGMDAyRjNES2xpcHNjaFN1cHBvcnQhITg4"
    assert generate_password_from_mac(TEST_MAC) == expected
    # Casing-independent: lowercased/normalized MAC yields the same credential.
    assert generate_password_from_mac(normalize_mac(TEST_MAC)) == expected


def test_password_secret_is_reversible_theatre():
    # The "secret" is just a hardcoded string + the public MAC: base64 is
    # trivially reversible, demonstrating the credential adds no real secrecy.
    decoded = base64.b64decode(generate_password_from_mac(TEST_MAC)).decode()
    assert decoded == "343D7F002F3DKlipschSupport!!88"


def test_build_set_data_known_answer(monkeypatch):
    """Reproduce a real captured signed setData byte-for-byte.

    Ground truth (Frida dump from Connect Plus v2.3.7 against the lab unit):
    nonce ``+QjQ8fsG``, ts ``1781254222108``, the IV below, setting
    ``settings:/cinema/postProcessorMode`` -> ``music`` produced exactly the
    value ciphertext and Authorization header asserted here.
    """
    from custom_components.klipsch_flexus import auth as auth_mod

    nonce = "+QjQ8fsG"
    ts = "1781254222108"
    iv = bytes([41, 28, 165, 84, 134, 164, 136, 76,
                127, 113, 185, 83, 128, 233, 197, 26])
    nonce_raw = base64.b64decode(nonce)

    # Inject the captured randomness/clock so the output is deterministic.
    randoms = iter([nonce_raw, iv])
    monkeypatch.setattr(auth_mod.os, "urandom", lambda n: next(randoms))
    monkeypatch.setattr(auth_mod.time, "time", lambda: int(ts) / 1000.0)

    auth = KlipschAuth(TEST_MAC, TEST_HOST)
    body, headers = auth.build_set_data(
        "settings:/cinema/postProcessorMode",
        {"type": "cinemaPostProcessorMode", "cinemaPostProcessorMode": "music"},
    )

    expected_value = (
        "KRylVIakiEx/cblTgOnFGpo3+AwXpSXzJZbC3PSPAwo/+YpqdHZD3GpMnFoiCBH1"
        "TDxFY+zjHRBCZP9phtgOClnIpMOKMVoMUkAOq994i3Puu7vIPkHgoNGmW27YtEHT"
    )
    expected_auth = (
        "HMAC_SHA256_AES256 dXNlcg==.+QjQ8fsG.1781254222108."
        "HKQvtPM3bntMfnnBSqgIwA94lUI1mW/hpFKDnncENSY="
    )

    assert json.loads(body)["value"] == expected_value
    assert headers["Authorization"] == expected_auth
    # Body is pretty-printed (the bytes that get signed) with path/role/value order.
    assert body.startswith('{\n    "path": "settings:/cinema/postProcessorMode"')
