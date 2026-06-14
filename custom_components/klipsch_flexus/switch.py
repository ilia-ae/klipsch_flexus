"""Switch entities for Klipsch Flexus toggle settings."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SWITCHES
from .coordinator import KlipschCoordinator
from .entity import KlipschControllableEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KlipschSwitch(coordinator, entry, key, icon) for key, icon in SWITCHES])


class KlipschSwitch(KlipschControllableEntity, SwitchEntity):
    """A boolean device setting (auto lip-sync, EQ bypass, auto power, …)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry, key: str, icon: str) -> None:
        super().__init__(coordinator, entry, key)
        self._key = key
        self._attr_translation_key = key
        self._attr_icon = icon

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return bool(data.get(self._key, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, on: bool) -> None:
        await self.coordinator.api.set_switch(self._key, on)
        self._optimistic_update(**{self._key: on})
