"""Number entities for Klipsch Flexus channel levels and settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHANNEL_LEVELS, CONFIG_NUMBERS, DOMAIN
from .coordinator import KlipschCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [KlipschChannelLevel(coordinator, entry, key, icon) for key, icon in CHANNEL_LEVELS]
    entities += [KlipschSettingNumber(coordinator, entry, *cfg) for cfg in CONFIG_NUMBERS]
    async_add_entities(entities)


class KlipschChannelLevel(CoordinatorEntity[KlipschCoordinator], NumberEntity):
    """Channel level slider (bass/mid/treble/surround/subwoofer)."""

    _attr_has_entity_name = True
    _attr_native_min_value = -6
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: KlipschCoordinator,
        entry: ConfigEntry,
        param: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._param = param
        self._attr_translation_key = param
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{param}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def available(self) -> bool:
        """Available whenever the device is reachable (shows last value in standby)."""
        return bool((self.coordinator.data or {}).get("online")) and super().available

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get(self._param, 0)

    async def async_set_native_value(self, value: float) -> None:
        int_val = int(value)
        await self.coordinator.api.set_channel_level(self._param, int_val)
        # Optimistic update (also cached so the standby poll won't revert it)
        self.coordinator.api.note_cached({self._param: int_val})
        if self.coordinator.data:
            self.coordinator.data[self._param] = int_val
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()


class KlipschSettingNumber(CoordinatorEntity[KlipschCoordinator], NumberEntity):
    """Typed setting number — lip-sync delay (ms), balance (double), idle timeout (s)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: KlipschCoordinator,
        entry: ConfigEntry,
        key: str,
        icon: str,
        unit: str | None,
        minimum: float,
        maximum: float,
        step: float,
        vtype: str,
        mode: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._vtype = vtype
        self._attr_translation_key = key
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_mode = NumberMode.SLIDER if mode == "slider" else NumberMode.BOX
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def available(self) -> bool:
        """Available whenever the device is reachable (shows last value in standby)."""
        return bool((self.coordinator.data or {}).get("online")) and super().available

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get(self._key, 0)

    async def async_set_native_value(self, value: float) -> None:
        # double settings (balance) keep fractional precision; integer types are rounded
        val: float = float(value) if self._vtype == "double_" else int(value)
        await self.coordinator.api.set_number(self._key, val, self._vtype)
        self.coordinator.api.note_cached({self._key: val})
        if self.coordinator.data:
            self.coordinator.data[self._key] = val
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()
