"""Wireless speakers (Flexus SUB / SURR): parsing, version reads, devices, link sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.klipsch_flexus.api import KlipschAPI
from custom_components.klipsch_flexus.const import DOMAIN
from custom_components.klipsch_flexus.coordinator import speaker_sw_version

from .conftest import MOCK_HOST, MOCK_STATUS
from .test_init import SUB_VERSIONS, _device, _mock_api, _no_arp, _peripherals, _setup  # noqa: F401

# cinema:peripherals as a CORE 300 with one wireless sub and two surrounds reports it
LIVE_PERIPHERALS = [
    {"con": "0", "ver": "", "m": "", "id": 3},
    {"con": "1,0", "ver": "4.6,0.0", "m": "1072557,0", "id": 2},
    {"con": "1,1", "ver": "4.6,4.6", "m": "1072559,1072559", "id": 1},
]


def _api_reading(nodes: dict[str, list]) -> KlipschAPI:
    api = KlipschAPI(MOCK_HOST)

    async def get_data(path, timeout=8, roles="value", retries=2):
        if path not in nodes:
            raise ValueError(f"unexpected read {path}")
        return nodes[path]

    api.get_data = AsyncMock(side_effect=get_data)
    return api


# --- api ---


async def test_get_peripherals_parses_slots_by_group_id() -> None:
    api = _api_reading({"cinema:peripherals": [{"type": "cinemaPeripherals", "cinemaPeripherals": LIVE_PERIPHERALS}]})
    result = await api.get_peripherals()
    assert result["speakers"] == {
        "surround_left": {"connected": True, "rx": "4.6", "model": "1072559"},
        "surround_right": {"connected": True, "rx": "4.6", "model": "1072559"},
        "sub_1": {"connected": True, "rx": "4.6", "model": "1072557"},
        "sub_2": {"connected": False, "rx": None, "model": None},  # "0.0" / "0" = empty slot
    }
    assert result["raw"] == LIVE_PERIPHERALS  # group 3 kept for diagnostics only


async def test_get_peripherals_tolerates_missing_groups_and_short_lists() -> None:
    groups = [{"id": 2, "con": "1", "ver": "4.6", "m": "1072557"}]  # no surrounds, one slot listed
    api = _api_reading({"cinema:peripherals": [{"cinemaPeripherals": groups}]})
    speakers = (await api.get_peripherals())["speakers"]
    assert set(speakers) == {"sub_1", "sub_2"}
    assert speakers["sub_1"]["connected"] is True
    assert speakers["sub_2"] == {"connected": False, "rx": None, "model": None}


async def test_get_speaker_versions_reads_the_hostlink_nodes() -> None:
    api = _api_reading(
        {
            "hostlink:sub2RxFirmwareVersion": [{"string_": "4.6"}],
            "hostlink:sub2EqFirmwareVersion": [{"string_": "0.3.0"}],
            "hostlink:sub2McuFirmwareVersion": [{"string_": "1.0.4"}],
            "hostlink:sub2HwVersion": [{"string_": ""}],
        }
    )
    assert await api.get_speaker_versions("sub_2") == {"rx": "4.6", "eq": "0.3.0", "mcu": "1.0.4", "hw": None}
    assert all(call.kwargs["retries"] == 0 for call in api.get_data.await_args_list)


async def test_get_bar_versions_skips_unreadable_nodes() -> None:
    api = _api_reading(
        {
            "hostlink:hardwareRevision": [{"string_": "3.0.1"}],
            "hostlink:hostFirmwareVersion": [{"string_": "1.0.25"}],
            "settings:/releasetext": [{"string_": "1.1.4"}],
        }
    )
    assert await api.get_bar_versions() == {"hardware_revision": "3.0.1", "host_mcu": "1.0.25", "release": "1.1.4"}


def test_speaker_sw_version() -> None:
    assert speaker_sw_version(SUB_VERSIONS) == "MCU 1.0.4 · RX 4.6 · EQ 0.3.0"
    assert speaker_sw_version({"rx": "4.6"}) == "RX 4.6"
    assert speaker_sw_version({}) is None


# --- full setup ---


async def _setup_monitored(hass, api: KlipschAPI):
    """Set up with the "Monitor wireless speakers" option on (read every poll)."""
    from unittest.mock import patch

    from homeassistant.const import CONF_HOST
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.klipsch_flexus.const import CONF_MONITOR_SPEAKERS

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="aabbccddeeff", data={CONF_HOST: MOCK_HOST}, options={CONF_MONITOR_SPEAKERS: True}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.klipsch_flexus.KlipschAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _speaker_device(hass, entry, slot: str) -> dr.DeviceEntry | None:
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    return next((d for d in devices if (DOMAIN, f"{entry.entry_id}_{slot}") in d.identifiers), None)


def _link_entity(hass, entry, slot: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_{slot}_connected")


async def test_linked_speaker_gets_a_device_under_the_soundbar(hass) -> None:
    api = _mock_api()
    entry = await _setup(hass, api)

    soundbar = _device(hass, entry)
    assert soundbar.hw_version == "3.0.1"  # hostlink:hardwareRevision
    sub = _speaker_device(hass, entry, "sub_1")
    assert sub is not None
    assert sub.via_device_id == soundbar.id
    assert sub.name == "Wireless Subwoofer 1"  # translated device name
    assert sub.manufacturer == "Klipsch"
    assert sub.model == "Flexus Subwoofer"
    assert sub.model_id == "1072557"
    assert sub.sw_version == "MCU 1.0.4 · RX 4.6 · EQ 0.3.0"
    assert sub.hw_version == "3.0.0"
    # Slots that never had a speaker get nothing
    for slot in ("sub_2", "surround_left", "surround_right"):
        assert _speaker_device(hass, entry, slot) is None
        assert _link_entity(hass, entry, slot) is None

    assert _link_entity(hass, entry, "sub_1") == "binary_sensor.wireless_subwoofer_1_connected"
    state = hass.states.get(_link_entity(hass, entry, "sub_1"))
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == "connectivity"
    assert state.attributes["mcu_firmware_version"] == "1.0.4"
    assert state.attributes["model_number"] == "1072557"
    api.get_speaker_versions.assert_awaited_once_with("sub_1")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_link_drop_standby_and_a_newly_paired_speaker(hass) -> None:
    """With monitoring on: a drop, standby, then a newly paired speaker."""
    api = _mock_api()
    entry = await _setup_monitored(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sub_1 = _link_entity(hass, entry, "sub_1")

    # The sub drops its wireless link: the bar then reports the slot like an
    # empty one (con 0, ver 0.0, m 0), as seen on a live CORE 300
    api.get_peripherals.return_value = _peripherals()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(sub_1).state == STATE_OFF
    api.get_speaker_versions.assert_awaited_once()  # versions not re-read for a drop
    # The device keeps the last versions read while it was linked
    assert _speaker_device(hass, entry, "sub_1").sw_version == "MCU 1.0.4 · RX 4.6 · EQ 0.3.0"

    # Standby: speakers are not polled → unavailable, not "disconnected"
    api.get_status.return_value = {**MOCK_STATUS, "power": "networkStandby", "volume_max": 50}
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(sub_1).state == STATE_UNAVAILABLE

    # Back on with a second sub paired: new device + sensor without a reload,
    # and versions re-read after standby (speakers may have updated)
    api.get_status.return_value = {**MOCK_STATUS, "power": "on", "volume_max": 50}
    api.get_peripherals.return_value = _peripherals(sub_1=True, sub_2=True)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(sub_1).state == STATE_ON
    sub_2 = _link_entity(hass, entry, "sub_2")
    assert sub_2 is not None
    assert hass.states.get(sub_2).state == STATE_ON
    assert _speaker_device(hass, entry, "sub_2").via_device_id == _device(hass, entry).id
    assert {c.args[0] for c in api.get_speaker_versions.await_args_list} == {"sub_1", "sub_2"}
    assert api.get_speaker_versions.await_count == 3

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_known_speaker_comes_back_after_restart_in_standby(hass) -> None:
    """A speaker registered before keeps its sensor (unavailable) when HA starts
    with the bar in standby, instead of vanishing until the bar is turned on."""
    entry = await _setup(hass, _mock_api())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    api = _mock_api(power="networkStandby")
    from unittest.mock import patch

    with patch("custom_components.klipsch_flexus.KlipschAPI", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    api.get_peripherals.assert_not_called()  # standby: not polled
    assert hass.states.get(_link_entity(hass, entry, "sub_1")).state == STATE_UNAVAILABLE
    # The versions read before the restart stay on the device
    sub = _speaker_device(hass, entry, "sub_1")
    assert sub.sw_version == "MCU 1.0.4 · RX 4.6 · EQ 0.3.0"
    assert sub.hw_version == "3.0.0"
    assert sub.model_id == "1072557"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_peripherals_read_failure_never_fails_the_poll(hass) -> None:
    api = _mock_api()
    api.get_peripherals = AsyncMock(side_effect=ValueError("node missing on this firmware"))
    api.get_bar_versions = AsyncMock(side_effect=ValueError("no hostlink"))
    entry = await _setup(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.last_update_success
    assert "speakers" not in coordinator.data
    assert _link_entity(hass, entry, "sub_1") is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unlinked_speaker_device_can_be_deleted_and_comes_back(hass) -> None:
    from custom_components.klipsch_flexus import async_remove_config_entry_device

    api = _mock_api()
    entry = await _setup_monitored(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sub = _speaker_device(hass, entry, "sub_1")

    assert await async_remove_config_entry_device(hass, entry, _device(hass, entry)) is False  # never the soundbar
    assert await async_remove_config_entry_device(hass, entry, sub) is False  # linked right now

    api.get_peripherals.return_value = _peripherals()  # unpaired
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert await async_remove_config_entry_device(hass, entry, sub) is True
    dr.async_get(hass).async_remove_device(sub.id)
    await hass.async_block_till_done()
    assert _speaker_device(hass, entry, "sub_1") is None
    assert _link_entity(hass, entry, "sub_1") is None

    await coordinator.async_refresh()  # still unpaired: not re-created
    await hass.async_block_till_done()
    assert _link_entity(hass, entry, "sub_1") is None

    api.get_peripherals.return_value = _peripherals(sub_1=True)  # paired again
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(_link_entity(hass, entry, "sub_1")).state == STATE_ON
    assert _speaker_device(hass, entry, "sub_1") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_bar_versions_stop_at_a_timeout_and_are_retried(hass) -> None:
    # The API stops at the first timeout instead of waiting out every node
    api_reader = _api_reading({})
    api_reader.get_data = AsyncMock(side_effect=TimeoutError)
    import pytest

    with pytest.raises(TimeoutError):
        await api_reader.get_bar_versions()
    assert api_reader.get_data.await_count == 1

    api = _mock_api()
    api.get_bar_versions = AsyncMock(side_effect=TimeoutError)
    entry = await _setup(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.bar_versions == {}
    api.get_bar_versions = AsyncMock(return_value={"hardware_revision": "3.0.1"})
    await coordinator.async_refresh()  # retried on the next poll
    await hass.async_block_till_done()
    assert coordinator.bar_versions == {"hardware_revision": "3.0.1"}
    assert _device(hass, entry).hw_version == "3.0.1"
    await coordinator.async_refresh()  # read once per power-on
    await hass.async_block_till_done()
    api.get_bar_versions.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_speakers_timeout_skips_the_remaining_reads(hass) -> None:
    api = _mock_api()
    api.get_peripherals = AsyncMock(side_effect=TimeoutError)
    entry = await _setup(hass, api)
    api.get_speaker_versions.assert_not_called()
    api.get_bar_versions.assert_not_called()  # the device stopped answering

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_versions_reported_as_zero_are_read_again(hass) -> None:
    """Right after a sub links, the bar reports its MCU / EQ as 0.0.0 (the radio
    is up, the speaker's MCU not yet): read again on the next polls, a few times."""
    zero = _api_reading(
        {
            "hostlink:sub1RxFirmwareVersion": [{"string_": "4.6"}],
            "hostlink:sub1EqFirmwareVersion": [{"string_": "0.0.0"}],
            "hostlink:sub1McuFirmwareVersion": [{"string_": "0.0.0"}],
            "hostlink:sub1HwVersion": [{"string_": "3.0.0"}],
        }
    )
    partial = await zero.get_speaker_versions("sub_1")
    assert partial == {"rx": "4.6", "eq": None, "mcu": None, "hw": "3.0.0"}

    api = _mock_api()
    api.get_speaker_versions = AsyncMock(return_value=dict(partial))
    entry = await _setup_monitored(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert _speaker_device(hass, entry, "sub_1").sw_version == "RX 4.6"

    api.get_speaker_versions.return_value = dict(SUB_VERSIONS)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _speaker_device(hass, entry, "sub_1").sw_version == "MCU 1.0.4 · RX 4.6 · EQ 0.3.0"
    await coordinator.async_refresh()  # complete now: not read again
    await hass.async_block_till_done()
    assert api.get_speaker_versions.await_count == 2

    # A speaker that keeps reporting 0.0.0 is read SPEAKER_VERSION_READS times, then left alone
    api.get_speaker_versions = AsyncMock(return_value=dict(partial))
    api.get_peripherals.return_value = _peripherals(sub_1=True, sub_2=True)
    for _ in range(5):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert [c.args[0] for c in api.get_speaker_versions.await_args_list] == ["sub_2"] * 3

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_without_monitoring_speakers_are_read_once_and_on_the_button(hass) -> None:
    """Default: one full read after setup, then only the button reads them."""
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    api = _mock_api()
    entry = await _setup(hass, api)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert api.get_peripherals.await_count == 1
    api.get_bar_versions.assert_awaited_once()
    sub_1 = _link_entity(hass, entry, "sub_1")
    assert hass.states.get(sub_1).state == STATE_ON
    assert hass.states.get(sub_1).attributes["last_checked"] is not None

    for _ in range(3):  # regular polls: no speaker reads
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert api.get_peripherals.await_count == 1
    assert hass.states.get(sub_1).state == STATE_ON  # last read stays shown

    # Standby: the last read is still shown (it is not a live value)
    api.get_status.return_value = {**MOCK_STATUS, "power": "networkStandby", "volume_max": 50}
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(sub_1).state == STATE_ON

    # The button: a full read (versions re-read even when unchanged), shown at once
    api.get_peripherals.return_value = _peripherals()
    button = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_read_speakers")
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(sub_1).state == STATE_OFF
    assert api.get_bar_versions.await_count == 2
    api.get_peripherals.return_value = _peripherals(sub_1=True)
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    assert api.get_speaker_versions.await_count == 2

    api.get_peripherals = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
