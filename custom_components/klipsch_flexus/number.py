"""Number entities for Klipsch Flexus channel levels and settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHANNEL_LEVELS, CONFIG_NUMBERS, DOMAIN
from .coordinator import KlipschCoordinator
from .entity import KlipschControllableEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [KlipschChannelLevel(coordinator, entry, key, icon) for key, icon in CHANNEL_LEVELS]
    entities += [KlipschSettingNumber(coordinator, entry, *cfg) for cfg in CONFIG_NUMBERS]
    async_add_entities(entities)


class KlipschChannelLevel(KlipschControllableEntity, NumberEntity):
    """Channel level slider (bass/mid/treble/surround/subwoofer)."""

    _attr_native_min_value = -6
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: KlipschCoordinator,
        entry: ConfigEntry,
        key: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._key = key
        self._attr_translation_key = key
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get(self._key, 0)

    async def async_set_native_value(self, value: float) -> None:
        int_val = int(value)
        await self.coordinator.api.set_channel_level(self._key, int_val)
        self._optimistic_update(**{self._key: int_val})


class KlipschSettingNumber(KlipschControllableEntity, NumberEntity):
    """Typed setting number — lip-sync delay (ms), balance (double), idle timeout (s)."""

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
        super().__init__(coordinator, entry, key)
        self._key = key
        self._vtype = vtype
        self._attr_translation_key = key
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_mode = NumberMode.SLIDER if mode == "slider" else NumberMode.BOX

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
        self._optimistic_update(**{self._key: val})
