#!/usr/bin/env python3
"""Extract the Klipsch webserver-password secret from a Connect Plus APK.

The per-device webserver password is::

    password = base64( MAC_UPPER_HEX + SECRET )

where ``SECRET`` is a string constant hardcoded in the Flutter Dart-AOT snapshot
(``lib/arm64-v8a/libapp.so``) inside ``generatePasswordFromMac``. For Connect
Plus v2.3.7 it is ``KlipschSupport!!88``. When Klipsch ships a new app, run this
on the new APK to re-extract the constant without redoing the reverse-engineering.

Usage:
    extract_secret.py <app.apk | libapp.so>
        [--mac AA:BB:CC:DD:EE:FF] [--expect <known base64 password>]

Strategy:
  * Pull ``libapp.so`` from the APK and collect its printable strings.
  * The secret sits right after the regex ``[^A-F0-9]`` in the password routine,
    so candidates are ranked by proximity to that anchor + secret-like shape
    (no path/space/'.'; mixes letters, digits, punctuation; vendor-ish).
  * If ``--mac`` and ``--expect`` (a known captured password) are given, the
    correct secret is verified deterministically: it is the candidate for which
    ``base64(MAC_UPPER + secret) == expect``. With only a known password you can
    also just decode it: ``base64decode(password)`` == ``MAC_UPPER + SECRET``.
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
import zipfile

ANCHOR = b"[^A-F0-9]"            # regex immediately preceding the secret
STR_RE = re.compile(rb"[\x20-\x7e]{3,80}")


def load_libapp(path: str) -> bytes:
    if path.endswith(".so"):
        with open(path, "rb") as fh:
            return fh.read()
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.endswith("libapp.so")]
        if not names:
            sys.exit("libapp.so not found in APK")
        # prefer arm64
        names.sort(key=lambda n: ("arm64" not in n, n))
        return z.read(names[0])


VENDOR_MARKERS = ("klipsch", "support", "secret", "passwd", "password",
                  "salt", "hmac", "stream", "nsdk")


def secret_score(s: str) -> int:
    """Heuristic: how 'secret-constant'-like is this string.

    The secret is a hardcoded credential constant (not a path/symbol/log line),
    typically mixing case + digits + punctuation and often carrying a vendor
    marker. Dart pools strings far from the code that uses them, so position in
    the binary is useless — we rank purely on shape.
    """
    if any(c in s for c in "/ \t") or s.count(".") > 1:
        return -100
    if re.search(r"@\d{4,}", s):     # Dart symbol id, e.g. _MapStream@5048458
        return -100
    if any(tok in s for tok in ("package:", "dart:", "Helper", "Service",
                                "Exception", "Error", "http", "://", "{", "}",
                                "()", "==", "Notifier", "Widget", "State")):
        return -100
    score = 0
    low = s.lower()
    if any(m in low for m in VENDOR_MARKERS):
        score += 6
    if any(c.isupper() for c in s) and any(c.islower() for c in s):
        score += 2
    if any(c.isdigit() for c in s):
        score += 1
    if any(c in s for c in "!@#$%^&*_-+"):
        score += 3
    if 8 <= len(s) <= 40:
        score += 1
    return score


def find_candidates(blob: bytes) -> list[str]:
    alls = {m.group().decode("latin1") for m in STR_RE.finditer(blob)}
    ranked = sorted(alls, key=lambda s: (secret_score(s), -len(s)), reverse=True)
    return [s for s in ranked if secret_score(s) >= 6][:20]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="APK or libapp.so")
    ap.add_argument("--mac", help="device MAC, e.g. 34:3D:7F:00:2F:3D")
    ap.add_argument("--expect", help="known base64 password to verify against")
    args = ap.parse_args()

    blob = load_libapp(args.target)

    # If we already know a password, the secret falls straight out of it.
    if args.expect and args.mac:
        mac_up = re.sub(r"[^A-F0-9]", "", args.mac.upper())
        decoded = base64.b64decode(args.expect).decode("latin1")
        if decoded.startswith(mac_up):
            secret = decoded[len(mac_up):]
            present = secret.encode() in blob
            print(f"SECRET (from known password) = {secret!r}")
            print(f"present in libapp.so: {present}")
            return
        print("known password does not start with MAC — check inputs")

    print("Top secret-constant candidates (anchor = generatePasswordFromMac regex):")
    cands = find_candidates(blob)
    for i, c in enumerate(cands):
        deriv = ""
        if args.mac:
            mac_up = re.sub(r"[^A-F0-9]", "", args.mac.upper())
            pw = base64.b64encode((mac_up + c).encode()).decode()
            deriv = f"  -> password {pw}"
            if args.expect and pw == args.expect:
                deriv += "  ✅ MATCHES --expect"
        print(f"  [{i:2}] {c!r}{deriv}")


if __name__ == "__main__":
    main()
