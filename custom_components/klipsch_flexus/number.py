"""Number entities for Klipsch Flexus channel levels."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHANNEL_LEVELS, DELAY_NUMBERS, DOMAIN
from .coordinator import KlipschCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [KlipschChannelLevel(coordinator, entry, key, icon) for key, icon in CHANNEL_LEVELS]
    entities += [KlipschDelayNumber(coordinator, entry, *cfg) for cfg in DELAY_NUMBERS]
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
        """Unavailable when device is offline or in standby (can't control)."""
        data = self.coordinator.data or {}
        if not data.get("online"):
            return False
        if data.get("power") == "networkStandby":
            return False
        return super().available

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get(self._param, 0)

    async def async_set_native_value(self, value: float) -> None:
        int_val = int(value)
        await self.coordinator.api.set_channel_level(self._param, int_val)
        # Optimistic update
        if self.coordinator.data:
            self.coordinator.data[self._param] = int_val
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()


class KlipschDelayNumber(CoordinatorEntity[KlipschCoordinator], NumberEntity):
    """Lip-sync / speaker-delay number (advanced A/V sync & calibration)."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: KlipschCoordinator,
        entry: ConfigEntry,
        key: str,
        icon: str,
        unit: str,
        minimum: int,
        maximum: int,
        step: int,
        vtype: str,
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
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def available(self) -> bool:
        """Unavailable when device is offline or in standby (can't control)."""
        data = self.coordinator.data or {}
        if not data.get("online"):
            return False
        if data.get("power") == "networkStandby":
            return False
        return super().available

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get(self._key, 0)

    async def async_set_native_value(self, value: float) -> None:
        int_val = int(value)
        await self.coordinator.api.set_delay(self._key, int_val, self._vtype)
        if self.coordinator.data:
            self.coordinator.data[self._key] = int_val
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()
