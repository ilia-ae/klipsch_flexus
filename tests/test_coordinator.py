"""Tests for the Klipsch Flexus data update coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.klipsch_flexus.const import (
    DOMAIN,
    EAGER_AUTH_MAX_ATTEMPTS,
    SCAN_INTERVAL_SECONDS,
    SCAN_INTERVAL_STANDBY,
)
from custom_components.klipsch_flexus.coordinator import KlipschCoordinator

from .conftest import MOCK_HOST


def _make_api(power: str) -> MagicMock:
    api = MagicMock()
    api.host = MOCK_HOST
    api.signing_mac = None
    api.get_status = AsyncMock(return_value={"online": True, "power": power})
    api.get_data = AsyncMock(return_value=[{"string_": "AA:BB:CC:DD:EE:FF"}])
    api.set_mac_seeds = MagicMock()
    api.get_device_info = AsyncMock(return_value={})
    api.get_auth_mode = AsyncMock(return_value="setData")
    api.resolve_write_auth = AsyncMock(return_value=True)
    api.get_dirac_filters = AsyncMock(return_value=[])
    api.get_player_data = AsyncMock(return_value=None)
    return api


def _make_coordinator(hass, api) -> KlipschCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data={"host": MOCK_HOST})
    entry.add_to_hass(hass)
    return KlipschCoordinator(hass, api, MOCK_HOST, SCAN_INTERVAL_SECONDS, entry=entry)


async def test_adaptive_interval_slows_in_standby(hass) -> None:
    """In standby the poll interval slows down and heavy fetches are skipped."""
    api = _make_api("networkStandby")
    coordinator = _make_coordinator(hass, api)

    status = await coordinator._async_update_data()

    assert status["power"] == "networkStandby"
    api.get_status.assert_awaited_once_with(seed_standby=True)  # first poll may seed the cache
    assert coordinator.update_interval == timedelta(seconds=SCAN_INTERVAL_STANDBY)
    api.set_mac_seeds.assert_called_once()  # seeds still refreshed so turn_on works
    api.get_device_info.assert_not_called()  # heavy fetch skipped in standby
    api.resolve_write_auth.assert_not_called()


async def test_active_poll_resolves_write_auth_and_normal_interval(hass) -> None:
    """When the device is on, the interval is normal and write-auth resolves eagerly."""
    api = _make_api("online")
    coordinator = _make_coordinator(hass, api)

    await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(seconds=SCAN_INTERVAL_SECONDS)
    api.resolve_write_auth.assert_awaited_once()
    assert coordinator._write_auth_ready is True


async def test_eager_write_auth_skipped_when_firmware_does_not_sign(hass) -> None:
    """authMode 'none' (pre-2026 firmware): no signing probe; the mode is read once."""
    api = _make_api("online")
    api.get_auth_mode = AsyncMock(return_value="none")
    coordinator = _make_coordinator(hass, api)

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    api.get_auth_mode.assert_awaited_once()
    api.resolve_write_auth.assert_not_called()


async def test_eager_write_auth_gives_up_after_fruitless_attempts(hass) -> None:
    """Probes that never resolve (e.g. no HTTPS endpoint) stop after a few polls."""
    api = _make_api("online")
    api.resolve_write_auth = AsyncMock(return_value=False)
    coordinator = _make_coordinator(hass, api)

    for _ in range(EAGER_AUTH_MAX_ATTEMPTS + 3):
        await coordinator._async_update_data()

    assert api.resolve_write_auth.await_count == EAGER_AUTH_MAX_ATTEMPTS
    assert coordinator._write_auth_ready is False


async def test_mac_seeds_not_refreshed_once_credential_resolved(hass) -> None:
    """A credential resolved lazily (a command in standby) stops seed refreshing,
    so a flapping seed source can't throw it away."""
    api = _make_api("networkStandby")
    api.signing_mac = "AA:BB:CC:DD:EE:FF"
    coordinator = _make_coordinator(hass, api)

    await coordinator._async_update_data()

    api.set_mac_seeds.assert_not_called()
    assert coordinator._write_auth_ready is True


async def test_gather_mac_seeds_prefers_device_primary_mac(hass) -> None:
    """The device-reported wired MAC is the deterministic credential → first seed."""
    api = _make_api("online")
    coordinator = _make_coordinator(hass, api)

    seeds = await coordinator._gather_mac_seeds()

    assert seeds[0] == "AA:BB:CC:DD:EE:FF"
    assert coordinator._seed_sources["device_primary_mac"] == "AA:BB:CC:DD:EE:FF"


async def test_offline_status_short_circuits(hass) -> None:
    """An offline poll returns the offline marker without touching the device further."""
    api = _make_api("online")
    api.get_status = AsyncMock(return_value={"online": False})
    coordinator = _make_coordinator(hass, api)

    status = await coordinator._async_update_data()

    assert status == {"online": False}
    api.set_mac_seeds.assert_not_called()


async def test_refresh_mid_poll_joins_and_polls_once_more(hass) -> None:
    """Refreshes requested while a poll runs don't start interleaved polls: they
    join it, and exactly one follow-up poll runs afterwards."""
    api = _make_api("networkStandby")
    release = asyncio.Event()
    running = 0
    max_running = 0
    polls = 0

    async def slow_status(**_):
        nonlocal running, max_running, polls
        polls += 1
        running += 1
        max_running = max(max_running, running)
        if polls == 1:
            await release.wait()
        running -= 1
        return {"online": True, "power": "networkStandby", "poll": polls}

    api.get_status = slow_status
    coordinator = _make_coordinator(hass, api)

    first = asyncio.ensure_future(coordinator._async_update_data())
    await asyncio.sleep(0)
    joiners = [asyncio.ensure_future(coordinator._async_update_data()) for _ in range(3)]
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(first, *joiners)

    assert polls == 2  # the running poll + one follow-up for all three requests
    assert max_running == 1  # never two get_status at once
    assert all(r["poll"] == 2 for r in results)  # everyone gets the fresh data

    # Without a mid-poll request, a refresh is a single poll.
    await coordinator._async_update_data()
    assert polls == 3


async def test_poll_error_propagates_to_joiners(hass) -> None:
    """A failing poll raises UpdateFailed for the caller and for joined refreshes."""
    api = _make_api("online")
    release = asyncio.Event()

    async def failing_status(**_):
        await release.wait()
        raise TimeoutError

    api.get_status = failing_status
    coordinator = _make_coordinator(hass, api)

    first = asyncio.ensure_future(coordinator._async_update_data())
    await asyncio.sleep(0)
    joiner = asyncio.ensure_future(coordinator._async_update_data())
    await asyncio.sleep(0)
    release.set()
    for fut in (first, joiner):
        with pytest.raises(UpdateFailed):
            await fut
    assert coordinator._poll_task is None


async def test_device_registry_follows_eureka_info(hass) -> None:
    """A device registered before eureka_info was known (setup in standby) gets
    the real name and firmware once it arrives, and sw_version follows a
    firmware update after the next standby → on transition."""
    api = _make_api("networkStandby")
    coordinator = _make_coordinator(hass, api)
    entry = coordinator.entry
    reg = dr.async_get(hass)
    device = reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Klipsch Flexus CORE 300",
    )

    await coordinator._async_update_data()  # standby: no eureka yet
    api.get_device_info.assert_not_called()

    api.get_status = AsyncMock(return_value={"online": True, "power": "online"})
    api.get_device_info = AsyncMock(return_value={"name": "Living Room", "cast_build_revision": "1.0"})
    await coordinator._async_update_data()
    await coordinator._async_update_data()  # still on → not fetched again
    api.get_device_info.assert_awaited_once()
    device = reg.async_get(device.id)
    assert device.name == "Living Room"
    assert device.sw_version == "1.0"

    # Firmware updated while in standby → re-read once when back on.
    api.get_status = AsyncMock(return_value={"online": True, "power": "networkStandby"})
    await coordinator._async_update_data()
    api.get_status = AsyncMock(return_value={"online": True, "power": "online"})
    api.get_device_info = AsyncMock(return_value={"name": "Living Room", "cast_build_revision": "2.0"})
    await coordinator._async_update_data()
    await coordinator._async_update_data()
    api.get_device_info.assert_awaited_once()
    assert reg.async_get(device.id).sw_version == "2.0"


async def test_cancel_pending_refreshes(hass) -> None:
    """Scheduled delayed refreshes are cancelled (e.g. on unload)."""
    api = _make_api("online")
    coordinator = _make_coordinator(hass, api)

    coordinator.async_request_delayed_refresh(delay=30)
    assert len(coordinator._refresh_handles) == 1

    coordinator.cancel_pending_refreshes()
    assert len(coordinator._refresh_handles) == 0


async def test_delayed_refresh_runs_as_entry_background_task(hass, monkeypatch) -> None:
    """The delayed refresh is tied to the entry, so unload cancels it."""
    api = _make_api("online")
    coordinator = _make_coordinator(hass, api)
    started: list[str] = []

    def fake_background_task(hass_, target, name, eager_start=True):
        started.append(name)
        target.close()  # don't actually run the refresh coroutine

    monkeypatch.setattr(coordinator.entry, "async_create_background_task", fake_background_task)
    coordinator.async_request_delayed_refresh(delay=0)
    await asyncio.sleep(0.01)

    assert len(started) == 1
    assert not coordinator._refresh_handles


@pytest.fixture(autouse=True)
def _no_socket_arp(monkeypatch):
    """ARP lookup reads /proc/net/arp (absent off-Linux); force the no-op path."""
    monkeypatch.setattr(
        "custom_components.klipsch_flexus.coordinator._arp_lookup",
        lambda ip: None,
    )
