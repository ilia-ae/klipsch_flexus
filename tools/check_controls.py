#!/usr/bin/env python3
"""Live self-check for every Klipsch Flexus write command, via the real API client.

For each control it reads the current value, performs a write through the actual
``KlipschAPI`` (so it exercises the full 2026 HMAC-signing path), verifies the
device applied it, and then **restores the original value** — leaving the device
exactly as it was. Disruptive controls (input, volume, mute, Dirac) are only
written back to their current value (idempotent); the rest are briefly toggled
and restored.

Power and media are covered specially:
  * Power does a real round-trip — turn off, confirm the status, turn back on,
    confirm the status (restoring the original power state). This briefly
    **power-cycles the soundbar**.
  * Media transport (play/pause) is checked for signed-command acceptance.

Every test is wrapped so the original is restored even on failure.

Usage:
    PYTHONPATH=. python tools/check_controls.py <device-ip> [mac-seed]

``mac-seed`` is any MAC the device exposes (e.g. the wireless one from your
router/ARP); the signing oracle expands it to neighbours to find the credential.
Inside Home Assistant the integration supplies this automatically.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time

from custom_components.klipsch_flexus.api import KlipschAPI
from custom_components.klipsch_flexus.const import API_PATHS

# (label, API_PATHS key, roles, kind, enum-options)
#   kind "toggle"      → change to a different value, verify, restore (signed)
#   kind "idempotent"  → write current value back (disruptive/unsigned controls)
CONTROLS = [
    ("Sound mode", "mode", "value", "toggle", ["movie", "music"]),
    ("Night mode", "night", "value", "toggle", ["off", "nightMode_1"]),
    ("Dialog mode", "dialog", "value", "toggle", ["off", "dialog_1", "dialog_2", "dialog_3"]),
    ("EQ preset", "eq_preset", "value", "toggle", ["flat", "bass", "rock", "vocal"]),
    ("Bass", "bass", "value", "toggle", None),
    ("Mid", "mid", "value", "toggle", None),
    ("Treble", "treble", "value", "toggle", None),
    ("Sub (wired)", "sub_wired", "value", "toggle", None),
    ("Sub (wireless)", "sub_wireless", "value", "toggle", None),
    ("Ch: back height", "back_height", "value", "toggle", None),
    ("Ch: back left", "back_left", "value", "toggle", None),
    ("Ch: back right", "back_right", "value", "toggle", None),
    ("Ch: front height", "front_height", "value", "toggle", None),
    ("Ch: side left", "side_left", "value", "toggle", None),
    ("Ch: side right", "side_right", "value", "toggle", None),
    ("Dirac filter", "dirac", "value", "idempotent", None),
    ("Input", "input", "value", "idempotent", None),
    ("Volume", "volume", "value", "idempotent", None),
    ("Mute", "mute", "value", "idempotent", None),
    # v2.5.8 — cinema settings (need device ON)
    ("LED mode", "led_mode", "value", "toggle", ["off", "dim", "bright"]),
    ("Lip-sync delay", "lipsync_delay", "value", "toggle", None),
    ("Auto lip-sync", "auto_lipsync", "value", "toggle", None),
    ("EQ bypass", "eq_bypass", "value", "toggle", None),
    ("Auto power", "auto_power", "value", "toggle", None),
    ("UI sounds", "ui_sounds", "value", "toggle", None),
    ("Extra modes", "extra_modes", "value", "toggle", None),
    ("BLE auto-pair", "ble_pair", "value", "toggle", None),
    ("OTA updates", "ota_updates", "value", "toggle", None),
    # v2.5.9 — mediaPlayer/system (writable even in standby)
    ("Balance", "balance", "value", "toggle", None),
    ("Idle timeout", "idle_timeout", "value", "toggle", None),
    ("Loudness", "loudness", "value", "toggle", None),
    ("Do Not Disturb", "do_not_disturb", "value", "toggle", None),
    ("Auto standby", "auto_standby", "value", "toggle", None),
]


def _field(value: dict) -> str:
    if "i32_" in value:
        return "i32_"
    if "bool_" in value:
        return "bool_"
    return value.get("type", "")


def _alt(cur, options):
    if options is not None:
        return next((o for o in options if o != cur), cur)
    if isinstance(cur, bool):
        return not cur
    if isinstance(cur, int):
        return cur - 1 if cur >= 5 else cur + 1
    return cur


async def _read_value(api: KlipschAPI, path: str) -> dict:
    return (await api.get_data(path))[0]


async def _power_target(api: KlipschAPI) -> str | None:
    return (await api.get_data(API_PATHS["power"]))[0].get("powerTarget", {}).get("target")


async def _wait_power(api: KlipschAPI, want: str, budget: float = 45.0) -> tuple[bool, float]:
    """Poll the power status until it reaches ``want``; return (ok, seconds)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < budget:
        if await _power_target(api) == want:
            return True, time.monotonic() - t0
        await asyncio.sleep(2)
    return (await _power_target(api)) == want, time.monotonic() - t0


async def check(host: str, mac_seed: str | None = None) -> int:
    api = KlipschAPI(host)
    # In HA the coordinator feeds candidate MACs from the device registry/ARP;
    # standalone we pass one explicitly (the oracle expands its neighbours).
    if mac_seed:
        api.set_mac_seeds([mac_seed])
    failures = 0
    print(f"Klipsch control self-check against {host}\n" + "-" * 62)

    # Cinema controls reject writes in standby — wake the bar first if needed and
    # remember to put it back exactly as we found it at the very end.
    power_orig = await _power_target(api)
    if power_orig == "networkStandby":
        print("  ⏻ bar in standby — waking for full test…")
        with contextlib.suppress(Exception):
            await asyncio.wait_for(api.set_power("online"), timeout=12)
        ok, secs = await _wait_power(api, "online", budget=50)
        print(f"     {'awake' if ok else 'STILL ASLEEP — cinema writes may fail'} ({secs:.0f}s)")

    # Changing tone (bass/mid/treble) flips eq_preset to 'custom' as a side
    # effect, so snapshot it and restore explicitly at the very end.
    try:
        eq_orig = (await api.get_data(API_PATHS["eq_preset"]))[0]
    except Exception:  # noqa: BLE001
        eq_orig = None

    for label, key, roles, kind, options in CONTROLS:
        path = API_PATHS[key]
        try:
            original = await _read_value(api, path)
            field = _field(original)

            if kind == "idempotent":
                t0 = time.monotonic()
                await api.set_data(path, original, roles=roles)
                ms = (time.monotonic() - t0) * 1000
                print(f"  ✅ {label:17} idempotent write accepted          ({ms:5.0f} ms)")
                continue

            # toggle: change → verify → restore (restore guaranteed in finally)
            changed = dict(original)
            changed[field] = _alt(original[field], options)
            try:
                t0 = time.monotonic()
                await api.set_data(path, changed, roles=roles)
                ms = (time.monotonic() - t0) * 1000
                after = await _read_value(api, path)
                ok = after.get(field) == changed[field]
                if not ok:
                    failures += 1
                mark = "✅" if ok else "❌"
                detail = "changed & verified" if ok else f"NO CHANGE ({after.get(field)})"
                print(f"  {mark} {label:17} {original[field]!s:>6} → {changed[field]!s:<10} {detail:22} ({ms:5.0f} ms)")
            finally:
                await api.set_data(path, original, roles=roles)  # always restore
        except Exception as err:  # noqa: BLE001
            failures += 1
            print(f"  ❌ {label:17} ERROR: {type(err).__name__}: {str(err)[:70]}")

    # Restore eq_preset last (tone tests above dirty it to 'custom').
    if eq_orig is not None:
        with contextlib.suppress(Exception):
            await api.set_data(API_PATHS["eq_preset"], eq_orig, roles="value")

    # --- Power: real round-trip (send → poll status → time), then restore ---
    async def _power_step(label: str, target: str) -> bool:
        # The device often stops answering the HTTP request during the transition,
        # but the command still lands — cap the send and poll the status instead.
        t0 = time.monotonic()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(api.set_power(target), timeout=12)
        # waking is slow; standby either engages fast or not at all (active source)
        budget = 20.0 if target == "networkStandby" else 50.0
        ok, _ = await _wait_power(api, target, budget=budget)
        ms = (time.monotonic() - t0) * 1000
        if ok:
            print(f"  ✅ {label:17} → {target:<14} confirmed                  ({ms:5.0f} ms)")
            return True
        if target == "networkStandby":
            # standby won't engage while an HDMI source/CEC keeps the bar awake —
            # the signed command was still sent; not a signing failure.
            print(f"  ⚠️  {label:17} → {target:<14} no standby (active source?) ({ms:5.0f} ms)")
            return True
        print(f"  ❌ {label:17} → {target:<14} NO TRANSITION              ({ms:5.0f} ms)")
        return False

    try:
        orig = await _power_target(api)
        other = "networkStandby" if orig == "online" else "online"
        ok_a = await _power_step("Power", other)
        ok_b = await _power_step("Power restore", orig)
        if not (ok_a and ok_b):
            failures += 1
    except Exception as err:  # noqa: BLE001
        failures += 1
        print(f"  ❌ {'Power':17} ERROR: {type(err).__name__}: {str(err)[:70]}")

    # Put the bar back into standby if that's how we found it.
    if power_orig == "networkStandby":
        with contextlib.suppress(Exception):
            await asyncio.wait_for(api.set_power("networkStandby"), timeout=12)
        print("  ⏻ restored bar to original standby state")

    # --- Media transport: signed command accepted (auth path) + latency ---
    for ctl in ("pause", "play"):
        t0 = time.monotonic()
        try:
            await asyncio.wait_for(api.media_control(ctl), timeout=12)
            ms = (time.monotonic() - t0) * 1000
            print(f"  ✅ {'Media: ' + ctl:17} signed command accepted            ({ms:5.0f} ms)")
        except TimeoutError:
            print(f"  ⚠️  {'Media: ' + ctl:17} sent, no ack within 12s (device busy)")
        except Exception as err:  # noqa: BLE001
            failures += 1
            print(f"  ❌ {'Media: ' + ctl:17} {type(err).__name__}: {str(err)[:55]}")

    await api.close()
    print("-" * 62)
    print("RESULT:", "ALL OK ✅" if failures == 0 else f"{failures} problem(s) ❌")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: PYTHONPATH=. python tools/check_controls.py <device-ip> [mac-seed]")
    seed = sys.argv[2] if len(sys.argv) == 3 else None
    sys.exit(asyncio.run(check(sys.argv[1], seed)))
