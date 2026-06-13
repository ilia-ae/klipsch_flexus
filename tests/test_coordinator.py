"""Tests for the Klipsch Flexus data update coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.klipsch_flexus.const import (
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
    SCAN_INTERVAL_STANDBY,
)
from custom_components.klipsch_flexus.coordinator import KlipschCoordinator

from .conftest import MOCK_HOST


def _make_api(power: str) -> MagicMock:
    api = MagicMock()
    api.host = MOCK_HOST
    api.get_status = AsyncMock(return_value={"online": True, "power": power})
    api.get_data = AsyncMock(return_value=[{"string_": "AA:BB:CC:DD:EE:FF"}])
    api.set_mac_seeds = MagicMock()
    api.get_device_info = AsyncMock(return_value={})
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


async def test_cancel_pending_refreshes(hass) -> None:
    """Scheduled delayed refreshes are cancelled (e.g. on unload)."""
    api = _make_api("online")
    coordinator = _make_coordinator(hass, api)

    coordinator.async_request_delayed_refresh(delay=30)
    assert len(coordinator._refresh_handles) == 1

    coordinator.cancel_pending_refreshes()
    assert len(coordinator._refresh_handles) == 0


@pytest.fixture(autouse=True)
def _no_socket_arp(monkeypatch):
    """ARP lookup reads /proc/net/arp (absent off-Linux); force the no-op path."""
    monkeypatch.setattr(
        "custom_components.klipsch_flexus.coordinator._arp_lookup",
        lambda ip: None,
    )
