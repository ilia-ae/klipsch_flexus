"""Tests for the switch / number / select optimistic-update setters.

These platforms share a pattern: call the API setter, record the value with
``note_cached`` (so the standby/full poll won't revert it), update the in-memory
coordinator data, push state, and request a delayed refresh. The tests assert
that whole contract end-to-end.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.klipsch_flexus.const import DOMAIN
from custom_components.klipsch_flexus.number import KlipschChannelLevel
from custom_components.klipsch_flexus.select import KlipschEqPresetSelect
from custom_components.klipsch_flexus.sensor import KlipschStatusSensor
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
