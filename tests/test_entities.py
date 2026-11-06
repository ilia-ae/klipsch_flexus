"""Tests for the switch / number / select optimistic-update setters.

These platforms share a pattern: call the API setter, record the value with
``note_cached`` (so the standby/full poll won't revert it), update the in-memory
coordinator data, push state, and request a delayed refresh. The tests assert
that whole contract end-to-end.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import STATE_UNKNOWN, Platform, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockEntityPlatform

from custom_components.klipsch_flexus import number as number_platform
from custom_components.klipsch_flexus.const import CONFIG_NUMBERS, DOMAIN, INFO_SENSORS
from custom_components.klipsch_flexus.number import KlipschChannelLevel, KlipschSettingNumber
from custom_components.klipsch_flexus.select import (
    KlipschDiracSelect,
    KlipschEqPresetSelect,
    KlipschIdleTimeoutSelect,
    KlipschLedModeSelect,
    KlipschNightModeSelect,
)
from custom_components.klipsch_flexus.sensor import (
    KlipschInfoSensor,
    KlipschInputSensor,
    KlipschSoundModeSensor,
    KlipschStatusSensor,
)
from custom_components.klipsch_flexus.switch import KlipschSwitch


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.data = {"online": True}
    coord.dirac_filters = []
    coord.async_request_delayed_refresh = MagicMock()
    api = MagicMock()
    api.set_switch = AsyncMock()
    api.set_channel_level = AsyncMock()
    api.set_eq_preset = AsyncMock()
    api.set_number = AsyncMock()
    api.note_cached = MagicMock()
    coord.api = api
    return coord


@pytest.fixture
def entry():
    e = MagicMock()
    e.entry_id = "e1"
    return e


def _bind(entity):
    """Detach the entity from HA's state machine for a pure unit test."""
    entity.async_write_ha_state = MagicMock()
    return entity


async def test_switch_optimistic_update(coordinator, entry) -> None:
    switch = _bind(KlipschSwitch(coordinator, entry, "loudness", "mdi:volume-vibrate"))

    await switch.async_turn_on()

    coordinator.api.set_switch.assert_awaited_once_with("loudness", True)
    coordinator.api.note_cached.assert_called_once_with({"loudness": True})
    assert coordinator.data["loudness"] is True
    switch.async_write_ha_state.assert_called_once()
    coordinator.async_request_delayed_refresh.assert_called_once()


async def test_number_channel_level_optimistic_update(coordinator, entry) -> None:
    number = _bind(KlipschChannelLevel(coordinator, entry, "bass", "mdi:sine-wave"))

    await number.async_set_native_value(3.0)

    coordinator.api.set_channel_level.assert_awaited_once_with("bass", 3)  # rounded to int
    coordinator.api.note_cached.assert_called_once_with({"bass": 3})
    assert coordinator.data["bass"] == 3
    coordinator.async_request_delayed_refresh.assert_called_once()


async def test_select_optimistic_update(coordinator, entry) -> None:
    select = _bind(KlipschEqPresetSelect(coordinator, entry))

    await select.async_select_option("rock")

    coordinator.api.set_eq_preset.assert_awaited_once_with("rock")
    coordinator.api.note_cached.assert_called_once_with({"eq_preset": "rock"})
    assert coordinator.data["eq_preset"] == "rock"
    coordinator.async_request_delayed_refresh.assert_called_once()


# --- Shared base-entity behavior (KlipschEntity / KlipschControllableEntity) ---


def test_control_available_is_gated_on_online(coordinator, entry) -> None:
    """A control is available only while the device reports online."""
    coordinator.last_update_success = True
    switch = KlipschSwitch(coordinator, entry, "loudness", "mdi:volume-vibrate")
    coordinator.data = {"online": True}
    assert switch.available is True
    coordinator.data = {"online": False}
    assert switch.available is False


def test_diagnostic_sensor_stays_available_when_offline(coordinator, entry) -> None:
    """The status sensor must NOT be online-gated — it has to report 'offline'."""
    coordinator.last_update_success = True
    sensor = KlipschStatusSensor(coordinator, entry)
    coordinator.data = {"online": False}
    assert sensor.available is True
    assert sensor.native_value == "offline"


def test_base_sets_unique_id_and_device(coordinator, entry) -> None:
    """The base entity derives unique_id + device link consistently."""
    switch = KlipschSwitch(coordinator, entry, "loudness", "mdi:volume-vibrate")
    assert switch.unique_id == "e1_loudness"
    assert switch.device_info == {"identifiers": {(DOMAIN, "e1")}}


# --- Never invent values for keys that were never read ------------------------


def test_controls_report_none_for_unread_keys(coordinator, entry) -> None:
    """Right after a restart in standby only online/power are known: controls
    must show unknown, not a made-up off / 0 / 'off'."""
    coordinator.data = {"online": True, "power": "networkStandby"}
    assert KlipschSwitch(coordinator, entry, "loudness", "mdi:x").is_on is None
    assert KlipschChannelLevel(coordinator, entry, "bass", "mdi:x").native_value is None
    assert KlipschSettingNumber(coordinator, entry, *CONFIG_NUMBERS[0]).native_value is None
    assert KlipschNightModeSelect(coordinator, entry).current_option is None
    assert KlipschEqPresetSelect(coordinator, entry).current_option is None
    assert KlipschDiracSelect(coordinator, entry).current_option is None
    assert KlipschLedModeSelect(coordinator, entry).current_option is None
    assert KlipschIdleTimeoutSelect(coordinator, entry).current_option is None


def test_controls_report_read_values(coordinator, entry) -> None:
    coordinator.data = {"online": True, "loudness": False, "bass": -2, "night_mode": "night_mode_1"}
    assert KlipschSwitch(coordinator, entry, "loudness", "mdi:x").is_on is False
    assert KlipschChannelLevel(coordinator, entry, "bass", "mdi:x").native_value == -2
    assert KlipschNightModeSelect(coordinator, entry).current_option == "night_mode_1"


# --- Select details -------------------------------------------------------------


def test_led_mode_unknown_value_is_none(coordinator, entry) -> None:
    """A non-standard LED value shows as unknown, not as 'dim'."""
    select = KlipschLedModeSelect(coordinator, entry)
    coordinator.data = {"online": True, "led_mode": "bright"}
    assert select.current_option == "bright"
    coordinator.data = {"online": True, "led_mode": "pulse"}
    assert select.current_option is None


def test_eq_preset_custom_shown_only_while_reported(coordinator, entry) -> None:
    select = KlipschEqPresetSelect(coordinator, entry)
    coordinator.data = {"online": True, "eq_preset": "rock"}
    assert "custom" not in select.options
    coordinator.data = {"online": True, "eq_preset": "custom"}
    assert select.options == ["flat", "bass", "rock", "vocal", "custom"]
    assert select.current_option == "custom"
    assert select.state == "custom"  # not Unknown


async def test_eq_preset_custom_cannot_be_selected(coordinator, entry) -> None:
    select = _bind(KlipschEqPresetSelect(coordinator, entry))
    coordinator.data = {"online": True, "eq_preset": "custom"}
    with pytest.raises(ServiceValidationError):
        await select.async_select_option("custom")
    coordinator.api.set_eq_preset.assert_not_awaited()
    assert coordinator.data["eq_preset"] == "custom"


@pytest.mark.parametrize(
    ("seconds", "option"),
    [(0, "off"), (300, "5_min"), (600, "10_min"), (900, "15_min"), (1800, "30_min"), (1234, None)],
)
def test_idle_timeout_select_maps_device_values(coordinator, entry, seconds, option) -> None:
    coordinator.data = {"online": True, "idle_timeout": seconds}
    select = KlipschIdleTimeoutSelect(coordinator, entry)
    assert select.options == ["off", "5_min", "10_min", "15_min", "30_min"]
    assert select.current_option == option


async def test_idle_timeout_select_writes_seconds_as_i32(coordinator, entry) -> None:
    select = _bind(KlipschIdleTimeoutSelect(coordinator, entry))

    await select.async_select_option("30_min")

    coordinator.api.set_number.assert_awaited_once_with("idle_timeout", 1800, "i32_")
    coordinator.api.note_cached.assert_called_once_with({"idle_timeout": 1800})
    assert select.current_option == "30_min"


async def test_number_setup_removes_orphaned_idle_timeout_number(hass: HomeAssistant, coordinator) -> None:
    """The idle timeout used to be a number; its registry entry is dropped on setup."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(Platform.NUMBER, DOMAIN, f"{entry.entry_id}_idle_timeout", config_entry=entry)
    keep = registry.async_get_or_create(Platform.NUMBER, DOMAIN, f"{entry.entry_id}_bass", config_entry=entry)
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    add_entities = MagicMock()

    await number_platform.async_setup_entry(hass, entry, add_entities)

    assert registry.async_get(old.entity_id) is None
    assert registry.async_get(keep.entity_id) is not None
    added = {e.unique_id for e in add_entities.call_args[0][0]}
    assert f"{entry.entry_id}_idle_timeout" not in added


# --- Number ranges follow the device's edit metadata ----------------------------


def test_channel_level_ranges(coordinator, entry) -> None:
    for key in ("sub_wired", "sub_wireless"):
        sub = KlipschChannelLevel(coordinator, entry, key, "mdi:x")
        assert (sub.native_min_value, sub.native_max_value, sub.native_step) == (-12, 6, 1)
    for key in ("bass", "back_left"):
        level = KlipschChannelLevel(coordinator, entry, key, "mdi:x")
        assert (level.native_min_value, level.native_max_value, level.native_step) == (-6, 6, 1)


def test_setting_number_ranges_and_units(coordinator, entry) -> None:
    numbers = {cfg[0]: KlipschSettingNumber(coordinator, entry, *cfg) for cfg in CONFIG_NUMBERS}
    assert set(numbers) == {"lipsync_delay", "balance"}  # idle timeout is a select now
    lipsync = numbers["lipsync_delay"]
    assert (lipsync.native_min_value, lipsync.native_max_value, lipsync.native_step) == (0, 500, 1)
    assert lipsync.native_unit_of_measurement == UnitOfTime.MILLISECONDS
    assert numbers["balance"].native_unit_of_measurement == "dB"


# --- Sensors --------------------------------------------------------------------


async def _sensor_state(hass: HomeAssistant, sensor) -> str:
    """Add ``sensor`` to a real entity platform and return its written state
    (HA validates ENUM states against the options when writing)."""
    platform = MockEntityPlatform(hass, domain=Platform.SENSOR, platform_name=DOMAIN)
    await platform.async_add_entities([sensor])
    return hass.states.get(sensor.entity_id).state


@pytest.mark.parametrize(
    "value", ["hdmi1", "hdmiarc", "spdif", "bluetooth", "usbdevice", "googlecast", "spotify", "tidal", "qplay", "dirac"]
)
async def test_input_sensor_accepts_every_device_input(hass: HomeAssistant, coordinator, entry, value) -> None:
    """Every value of the device's input enum is a valid ENUM state (no ValueError)."""
    coordinator.data = {"online": True, "input": value}
    coordinator.last_update_success = True
    assert await _sensor_state(hass, KlipschInputSensor(coordinator, entry)) == value


@pytest.mark.parametrize("value", ["unknown", "airplay", None])
async def test_input_sensor_unlisted_value_is_unknown(hass: HomeAssistant, coordinator, entry, value) -> None:
    coordinator.data = {"online": True, "input": value}
    coordinator.last_update_success = True
    sensor = KlipschInputSensor(coordinator, entry)
    assert sensor.native_value is None
    assert await _sensor_state(hass, sensor) == STATE_UNKNOWN  # written, HA did not raise


async def test_sound_mode_sensor_unlisted_value_is_unknown(hass: HomeAssistant, coordinator, entry) -> None:
    coordinator.data = {"online": True, "mode": "unknown"}
    coordinator.last_update_success = True
    assert await _sensor_state(hass, KlipschSoundModeSensor(coordinator, entry)) == STATE_UNKNOWN


def test_status_sensor_media_attributes(coordinator, entry) -> None:
    coordinator.data = {
        "online": True,
        "power": "online",
        "player": {"trackRoles": {"title": "Song A", "mediaData": {"metaData": {"artist": "Band"}}}},
    }
    attrs = KlipschStatusSensor(coordinator, entry).extra_state_attributes
    assert attrs["media_title"] == "Song A"
    assert attrs["media_artist"] == "Band"


def test_delay_sensors_use_ha_microseconds(coordinator, entry) -> None:
    units = {key: KlipschInfoSensor(coordinator, entry, key, icon, unit) for key, icon, unit in INFO_SENSORS}
    for key in ("sub_wired_delay", "sub_wireless_delay", "surround_delay"):
        assert units[key].native_unit_of_measurement == UnitOfTime.MICROSECONDS
