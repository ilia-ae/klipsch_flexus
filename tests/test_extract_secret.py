"""Tests for tools/extract_secret.py (secret recovery from a Connect Plus APK).

The tool lives in tools/ (not an importable package), so it is loaded by path.
These cover the pure logic — secret derivation/decoding and the string-ranking
heuristic — without touching the network (apkeep) or any real APK.
"""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import pytest

_ES_PATH = Path(__file__).resolve().parent.parent / "tools" / "extract_secret.py"
_spec = importlib.util.spec_from_file_location("extract_secret", _ES_PATH)
es = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es)

# base64("AABBCCDDEEFF" + "KlipschSupport!!88") — placeholder MAC, no real device.
KNOWN_PASSWORD = base64.b64encode(b"AABBCCDDEEFFKlipschSupport!!88").decode()


def test_secret_from_password_decode_only():
    """A known password decodes to (MAC, secret) without needing --mac."""
    mac, secret = es.secret_from_password(KNOWN_PASSWORD, None)
    assert mac == "AABBCCDDEEFF"
    assert secret == "KlipschSupport!!88"


def test_secret_from_password_with_matching_mac():
    mac, secret = es.secret_from_password(KNOWN_PASSWORD, "AABBCCDDEEFF")
    assert (mac, secret) == ("AABBCCDDEEFF", "KlipschSupport!!88")


def test_secret_from_password_mac_mismatch_raises():
    # a different MAC than the password encodes → prefix check fails
    with pytest.raises(ValueError, match="does not start with"):
        es.secret_from_password(KNOWN_PASSWORD, "001122334455")


def test_secret_from_password_bad_base64_raises():
    with pytest.raises(ValueError, match="not valid base64"):
        es.secret_from_password("not!!base64!!", None)


def test_secret_score_ranks_secret_above_junk():
    assert es.secret_score("KlipschSupport!!88") >= 6
    # paths, Dart symbol ids and framework tokens are rejected outright
    assert es.secret_score("package:foo/Bar") == -100
    assert es.secret_score("_MapStream@5048458") == -100
    assert es.secret_score("dart:core") == -100


def test_find_candidates_surfaces_secret():
    blob = b"\x00random\x00KlipschSupport!!88\x00dart:core\x00/data/app/x\x00"
    cands = es.find_candidates(blob)
    assert "KlipschSupport!!88" in cands
    # junk strings must not appear
    assert "/data/app/x" not in cands
    assert "dart:core" not in cands
