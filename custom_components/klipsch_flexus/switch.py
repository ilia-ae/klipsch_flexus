"""Switch entities for Klipsch Flexus toggle settings."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCHES
from .coordinator import KlipschCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KlipschSwitch(coordinator, entry, key, icon) for key, icon in SWITCHES])


class KlipschSwitch(CoordinatorEntity[KlipschCoordinator], SwitchEntity):
    """A boolean device setting (auto lip-sync, EQ bypass, auto power, …)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry, key: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_icon = icon
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
        if self.coordinator.data:
            self.coordinator.data[self._key] = on
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()
