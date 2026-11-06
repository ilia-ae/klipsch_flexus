"""Number entities for Klipsch Flexus channel levels and settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHANNEL_LEVEL_RANGE, CHANNEL_LEVEL_RANGES, CHANNEL_LEVELS, CONFIG_NUMBERS, DOMAIN
from .coordinator import KlipschCoordinator
from .entity import KlipschControllableEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Idle timeout moved to a select (the device field is an enum) — drop the
    # orphaned number entity older versions registered for it.
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id(Platform.NUMBER, DOMAIN, f"{entry.entry_id}_idle_timeout"):
        registry.async_remove(old)
    entities: list[NumberEntity] = [KlipschChannelLevel(coordinator, entry, key, icon) for key, icon in CHANNEL_LEVELS]
    entities += [KlipschSettingNumber(coordinator, entry, *cfg) for cfg in CONFIG_NUMBERS]
    async_add_entities(entities)


class KlipschChannelLevel(KlipschControllableEntity, NumberEntity):
    """Channel level slider (bass/mid/treble/surround/subwoofer)."""

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
        self._attr_native_min_value, self._attr_native_max_value = CHANNEL_LEVEL_RANGES.get(key, CHANNEL_LEVEL_RANGE)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get(self._key)  # None until the level has been read

    async def async_set_native_value(self, value: float) -> None:
        int_val = int(value)
        await self.coordinator.api.set_channel_level(self._key, int_val)
        self._optimistic_update(**{self._key: int_val})


class KlipschSettingNumber(KlipschControllableEntity, NumberEntity):
    """Typed setting number — lip-sync delay (ms), balance (double, dB)."""

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
        return data.get(self._key)  # None until the setting has been read

    async def async_set_native_value(self, value: float) -> None:
        # double settings (balance) keep fractional precision; integer types are rounded
        val: float = float(value) if self._vtype == "double_" else int(value)
        await self.coordinator.api.set_number(self._key, val, self._vtype)
        self._optimistic_update(**{self._key: val})
