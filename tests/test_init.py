"""Setup / unload of a real config entry through Home Assistant.

Only the device I/O of ``KlipschAPI`` is replaced; the coordinator, every
platform's ``async_setup_entry`` and the entities run for real, so an HA
platform-API break fails here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.klipsch_flexus import PLATFORMS
from custom_components.klipsch_flexus.api import KlipschAPI
from custom_components.klipsch_flexus.const import DOMAIN

from .conftest import MOCK_HOST, MOCK_STATUS


def _mock_api(power: str = "on") -> KlipschAPI:
    api = KlipschAPI(MOCK_HOST)
    api.get_status = AsyncMock(return_value={**MOCK_STATUS, "power": power, "volume_max": 50})
    api.get_data = AsyncMock(return_value=[{"type": "string_", "string_": "eth0"}])
    api.get_device_info = AsyncMock(return_value={"name": "Living Room", "cast_build_revision": "1.0"})
    api.get_auth_mode = AsyncMock(return_value="setData")
    api.resolve_write_auth = AsyncMock(return_value=True)
    api.get_dirac_filters = AsyncMock(return_value=[{"id": 1, "name": "Filter 1"}])
    api.get_player_data = AsyncMock(return_value=None)
    return api


@pytest.fixture(autouse=True)
def _no_arp(monkeypatch):
    """ARP lookup reads /proc/net/arp (absent off-Linux); force the no-op path."""
    monkeypatch.setattr("custom_components.klipsch_flexus.coordinator._arp_lookup", lambda ip: None)


async def _setup(hass, api: KlipschAPI, unique_id: str = "aabbccddeeff") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data={CONF_HOST: MOCK_HOST})
    entry.add_to_hass(hass)
    with patch("custom_components.klipsch_flexus.KlipschAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _device(hass, entry: MockConfigEntry) -> dr.DeviceEntry | None:
    """The entry's soundbar device (identifiers {(DOMAIN, entry_id)})."""
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    return next((d for d in devices if (DOMAIN, entry.entry_id) in d.identifiers), None)


async def test_setup_and_unload_entry(hass) -> None:
    """Every platform creates entities; unload closes the client for good."""
    api = _mock_api()
    close = AsyncMock(wraps=api.close)
    api.close = close

    entry = await _setup(hass, api)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    domains = {e.domain for e in entities}
    assert domains == {str(p) for p in PLATFORMS}
    media_player = next(e.entity_id for e in entities if e.domain == "media_player")
    assert hass.states.get(media_player) is not None

    device = _device(hass, entry)
    assert device is not None
    assert device.name == "Living Room"  # from eureka_info
    assert device.sw_version == "1.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
    close.assert_awaited_once()
    with pytest.raises(RuntimeError):
        await api._ensure_session()  # a late poll can't open a new session


async def test_setup_in_standby_then_device_registry_catches_up(hass) -> None:
    """HA starting with the bar in standby: no eureka_info yet, so the device is
    registered generically; the first poll with the bar on fills in the real
    name and firmware without a reload."""
    api = _mock_api(power="networkStandby")
    entry = await _setup(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    reg = dr.async_get(hass)
    device = _device(hass, entry)
    assert device.name == "Klipsch Flexus CORE 300"  # generic until eureka is read
    assert device.sw_version is None
    api.get_device_info.assert_not_called()

    api.get_status.return_value = {**MOCK_STATUS, "power": "on", "volume_max": 50}
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = reg.async_get(device.id)
    assert device.name == "Living Room"
    assert device.sw_version == "1.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_in_standby_keeps_registered_device_name(hass) -> None:
    """A restart / reload in standby (no eureka_info) keeps the real device name
    instead of writing the generic one back over it."""
    entry = await _setup(hass, _mock_api())
    assert _device(hass, entry).name == "Living Room"

    with patch("custom_components.klipsch_flexus.KlipschAPI", return_value=_mock_api(power="networkStandby")):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert _device(hass, entry).name == "Living Room"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def _api_with_primary_mac() -> KlipschAPI:
    api = _mock_api()

    async def get_data(path, *args, **kwargs):
        if path == "settings:/system/primaryMacAddress":
            return [{"type": "string_", "string_": "34:3D:7F:00:2F:3D"}]
        return [{"type": "string_", "string_": "eth0"}]

    api.get_data = get_data
    return api


async def test_setup_rekeys_older_entry_by_primary_mac(hass) -> None:
    """An entry keyed by the Cast UUID (older zeroconf flow) moves to the primary
    MAC the config flows use now, without a reload."""
    entry = await _setup(hass, _api_with_primary_mac(), unique_id="3fb1d5cda039be9c934c877174add9bf")
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await hass.async_block_till_done()

    assert entry.unique_id == "343d7f002f3d"
    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id] is coordinator  # not reloaded

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_keeps_unique_id_held_by_another_entry(hass) -> None:
    """No re-keying onto an id another entry (e.g. an ignored discovery) holds."""
    MockConfigEntry(domain=DOMAIN, unique_id="343d7f002f3d", source="ignore", data={}).add_to_hass(hass)
    entry = await _setup(hass, _api_with_primary_mac(), unique_id="3fb1d5cda039be9c934c877174add9bf")

    assert entry.unique_id == "3fb1d5cda039be9c934c877174add9bf"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
