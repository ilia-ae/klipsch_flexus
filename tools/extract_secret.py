#!/usr/bin/env python3
"""Extract the Klipsch webserver-password secret from a Connect Plus APK.

The per-device webserver password is::

    password = base64( MAC_UPPER_HEX + SECRET )

where ``SECRET`` is a string constant hardcoded in the Flutter Dart-AOT snapshot
(``lib/arm64-v8a/libapp.so``) inside ``generatePasswordFromMac``. For Connect
Plus v2.3.7 it is ``KlipschSupport!!88``. When Klipsch ships a new app, run this
on the new APK to re-extract the constant without redoing the reverse-engineering.

Usage:
    extract_secret.py <app.apk | app.xapk | libapp.so | PACKAGE_ID>
        [--mac AA:BB:CC:DD:EE:FF] [--expect <known base64 password>] [--keep]

If the target is a package id (e.g. ``com.klipsch.connectxp``, the default when
nothing is given) it is downloaded with ``apkeep`` (APKPure source) into a temp
dir, the secret is extracted, and the download is deleted afterwards unless
``--keep`` is passed. ``.xapk`` bundles (split APKs) are handled transparently.

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
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ANCHOR = b"[^A-F0-9]"            # regex immediately preceding the secret
STR_RE = re.compile(rb"[\x20-\x7e]{3,80}")
DEFAULT_PACKAGE = "com.klipsch.connectxp"
PKG_RE = re.compile(r"^[A-Za-z][\w]*(\.[A-Za-z][\w]*)+$")


def _libapp_from_zip(zf: zipfile.ZipFile) -> bytes | None:
    """Find libapp.so in an APK zip (prefer arm64-v8a)."""
    names = [n for n in zf.namelist() if n.endswith("libapp.so")]
    if not names:
        return None
    names.sort(key=lambda n: ("arm64" not in n, n))
    return zf.read(names[0])


def load_libapp(path: str) -> bytes:
    """Return libapp.so bytes from a .so, an .apk, or a split .xapk/.apks bundle."""
    if path.endswith(".so"):
        with open(path, "rb") as fh:
            return fh.read()
    with zipfile.ZipFile(path) as z:
        direct = _libapp_from_zip(z)
        if direct is not None:
            return direct
        # .xapk / .apks: a zip of split APKs — recurse into each inner APK.
        for inner in z.namelist():
            if inner.endswith(".apk"):
                with zipfile.ZipFile(io.BytesIO(z.read(inner))) as iz:
                    found = _libapp_from_zip(iz)
                    if found is not None:
                        return found
    sys.exit("libapp.so not found in APK/XAPK")


def download_apk(package: str, dest_dir: str) -> str:
    """Download ``package`` from APKPure with apkeep into ``dest_dir``.

    Returns the path of the downloaded .xapk/.apk. Requires the ``apkeep`` CLI
    (``brew install apkeep`` / ``cargo install apkeep``).
    """
    if shutil.which("apkeep") is None:
        sys.exit("apkeep not found — install it (brew install apkeep)")
    print(f"downloading {package} via apkeep (APKPure)…", flush=True)
    subprocess.run(
        ["apkeep", "-a", package, "-d", "apk-pure", dest_dir],
        check=True,
    )
    files = (glob.glob(os.path.join(dest_dir, "*.xapk"))
             + glob.glob(os.path.join(dest_dir, "*.apk"))
             + glob.glob(os.path.join(dest_dir, "*.apks")))
    if not files:
        sys.exit("apkeep produced no apk/xapk")
    return max(files, key=os.path.getsize)


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
    ap.add_argument("target", nargs="?", default=DEFAULT_PACKAGE,
                    help="APK/XAPK/libapp.so path, or a package id to download "
                         f"(default: {DEFAULT_PACKAGE})")
    ap.add_argument("--mac", help="device MAC, e.g. 34:3D:7F:00:2F:3D")
    ap.add_argument("--expect", help="known base64 password to verify against")
    ap.add_argument("--keep", action="store_true",
                    help="keep the downloaded APK instead of deleting it")
    args = ap.parse_args()

    # A package id (or a missing/non-file target) is downloaded, then cleaned up.
    tmpdir = None
    target = args.target
    if not os.path.exists(target) and PKG_RE.match(target):
        tmpdir = tempfile.mkdtemp(prefix="apkextract_")
        try:
            target = download_apk(target, tmpdir)
            print(f"downloaded: {os.path.basename(target)} "
                  f"({os.path.getsize(target) // (1024 * 1024)} MB)")
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise

    try:
        blob = load_libapp(target)
        _run(blob, args)
    finally:
        if tmpdir is not None and not args.keep:
            shutil.rmtree(tmpdir, ignore_errors=True)
            print("(downloaded APK deleted)")
        elif tmpdir is not None:
            print(f"(kept download in {tmpdir})")


def _run(blob: bytes, args: argparse.Namespace) -> None:

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
