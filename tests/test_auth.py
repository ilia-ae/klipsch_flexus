"""Tests for the 2026 firmware write-authentication (auth.py).

Known-answer tests for the MAC-derived credential and the full
``HMAC_SHA256_AES256`` request signing. The vectors are **synthetic and
deterministic** — a placeholder MAC/host plus fixed nonce/IV/ts inputs — so they
contain no real device identifiers. They lock the signer against regressions;
the live byte-for-byte match against the official Connect Plus app (captured via
a Frida hook) is documented in ``docs/REPORT.md``.
"""

from __future__ import annotations

import base64
import json

from custom_components.klipsch_flexus.auth import (
    KlipschAuth,
    expand_mac_candidates,
    generate_password_from_mac,
    generate_username_from_mac,
    mac_to_colon,
    normalize_mac,
)

# Placeholder identifiers — NOT a real device (no personal addresses in tests).
TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_HOST = "192.168.1.100"


def test_normalize_mac_strips_separators_and_lowercases():
    assert normalize_mac("AA:BB:CC:DD:EE:FF") == "aabbccddeeff"
    assert normalize_mac("AA-BB-CC-DD-EE-FF") == "aabbccddeeff"
    assert normalize_mac("aabbccddeeff") == "aabbccddeeff"


def test_username_default_is_user():
    assert generate_username_from_mac(normalize_mac(TEST_MAC)) == "user"


def test_mac_to_colon():
    assert mac_to_colon("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"
    assert mac_to_colon("AABBCCDDEEFF") == "AA:BB:CC:DD:EE:FF"
    assert mac_to_colon("not-a-mac") is None
    assert mac_to_colon("") is None


def test_expand_mac_candidates_finds_sibling():
    # eureka often gives the all-zero MAC; the LAN shows the wireless interface,
    # but the credential is the wired sibling (last byte ±1) → must be a candidate.
    cands = expand_mac_candidates(["00:00:00:00:00:00", "AA:BB:CC:DD:EE:FE"])
    assert cands[0] == "AA:BB:CC:DD:EE:FE"
    assert cands[1] == "AA:BB:CC:DD:EE:FD"  # wired sibling, nearest neighbour
    # the all-zero sentinel and its neighbours never appear
    assert not any(c.startswith("00:00:00:00:00") for c in cands)


def test_expand_mac_candidates_manual_first_and_dedup():
    cands = expand_mac_candidates(["AA:BB:CC:DD:EE:FD", "aa:bb:cc:dd:ee:fd"])
    assert cands[0] == "AA:BB:CC:DD:EE:FD"
    assert cands.count("AA:BB:CC:DD:EE:FD") == 1  # deduped across case/format


def test_password_derivation_known_answer():
    # base64(utf8("AABBCCDDEEFF" + "KlipschSupport!!88")) — exact app derivation.
    expected = "QUFCQkNDRERFRUZGS2xpcHNjaFN1cHBvcnQhITg4"
    assert generate_password_from_mac(TEST_MAC) == expected
    # Casing-independent: lowercased/normalized MAC yields the same credential.
    assert generate_password_from_mac(normalize_mac(TEST_MAC)) == expected


def test_build_set_data_threads_role():
    auth = KlipschAuth(TEST_MAC, TEST_HOST)
    body, _ = auth.build_set_data("powermanager:targetRequest", {"target": "on"}, role="activate")
    assert json.loads(body)["role"] == "activate"
    body2, _ = auth.build_set_data("cinema:cinemaBass", {"type": "i32_", "i32_": 0})
    assert json.loads(body2)["role"] == "value"  # default


def test_password_secret_is_reversible_theatre():
    # The "secret" is just a hardcoded string + the public MAC: base64 is
    # trivially reversible, demonstrating the credential adds no real secrecy.
    decoded = base64.b64decode(generate_password_from_mac(TEST_MAC)).decode()
    assert decoded == "AABBCCDDEEFFKlipschSupport!!88"


def test_build_set_data_known_answer(monkeypatch):
    """Deterministic signing vector — reproducible from fixed inputs.

    Fixed nonce ``+QjQ8fsG``, ts ``1781254222108`` and the IV below, signing
    ``settings:/cinema/postProcessorMode`` -> ``music`` for the placeholder
    MAC/host, must yield exactly the value ciphertext and Authorization header
    asserted here. This is a regression lock on our signer; the byte-for-byte
    match against the real app is recorded in ``docs/REPORT.md``.
    """
    from custom_components.klipsch_flexus import auth as auth_mod

    nonce = "+QjQ8fsG"
    ts = "1781254222108"
    iv = bytes([41, 28, 165, 84, 134, 164, 136, 76, 127, 113, 185, 83, 128, 233, 197, 26])
    nonce_raw = base64.b64decode(nonce)

    # Inject the fixed randomness/clock so the output is deterministic.
    randoms = iter([nonce_raw, iv])
    monkeypatch.setattr(auth_mod.os, "urandom", lambda n: next(randoms))
    monkeypatch.setattr(auth_mod.time, "time", lambda: int(ts) / 1000.0)

    auth = KlipschAuth(TEST_MAC, TEST_HOST)
    body, headers = auth.build_set_data(
        "settings:/cinema/postProcessorMode",
        {"type": "cinemaPostProcessorMode", "cinemaPostProcessorMode": "music"},
    )

    expected_value = (
        "KRylVIakiEx/cblTgOnFGpPjZ94JW9ZeXnHsvUnyEeB3Z64mTn8MLxTEZrpPqhXshn4"
        "q7iam3207DWeUWeyt03blviHNfuJO9vHfyC0lqHh9iZOmxL/mantrS9dztZfv"
    )
    expected_auth = "HMAC_SHA256_AES256 dXNlcg==.+QjQ8fsG.1781254222108.MOuz+q4AXE5bzUYnD6wLPBJbpZBlom/namk1asT4DpQ="

    assert json.loads(body)["value"] == expected_value
    assert headers["Authorization"] == expected_auth
    # Body is pretty-printed (the bytes that get signed) with path/role/value order.
    assert body.startswith('{\n    "path": "settings:/cinema/postProcessorMode"')
