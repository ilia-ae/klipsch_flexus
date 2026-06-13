"""Select entities for Klipsch Flexus."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DIALOG_MODES,
    DOMAIN,
    EQ_PRESETS,
    LED_MODES,
    NIGHT_MODES,
)
from .coordinator import KlipschCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        KlipschNightModeSelect(coordinator, entry),
        KlipschDialogModeSelect(coordinator, entry),
        KlipschEqPresetSelect(coordinator, entry),
        KlipschDiracSelect(coordinator, entry),
        KlipschLedModeSelect(coordinator, entry),
    ]
    async_add_entities(entities)


class KlipschNightModeSelect(CoordinatorEntity[KlipschCoordinator], SelectEntity):
    """Night mode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "night_mode"
    _attr_icon = "mdi:weather-night"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_night_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}
        self._attr_options = NIGHT_MODES

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
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("night_mode", "off")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_night_mode(option)
        if self.coordinator.data:
            self.coordinator.data["night_mode"] = option
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()


class KlipschDialogModeSelect(CoordinatorEntity[KlipschCoordinator], SelectEntity):
    """Dialog mode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "dialog_mode"
    _attr_icon = "mdi:account-voice"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_dialog_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}
        self._attr_options = DIALOG_MODES

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
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("dialog_mode", "off")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_dialog_mode(option)
        if self.coordinator.data:
            self.coordinator.data["dialog_mode"] = option
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()


class KlipschEqPresetSelect(CoordinatorEntity[KlipschCoordinator], SelectEntity):
    """EQ preset selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "eq_preset"
    _attr_icon = "mdi:tune-variant"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_eq_preset"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}
        self._attr_options = EQ_PRESETS

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
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("eq_preset", "flat")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_eq_preset(option)
        if self.coordinator.data:
            self.coordinator.data["eq_preset"] = option
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()


class KlipschDiracSelect(CoordinatorEntity[KlipschCoordinator], SelectEntity):
    """Dirac room correction filter selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "dirac"
    _attr_icon = "mdi:tune"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_dirac"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}
        self._dirac_map: dict[str, int] = {}
        self._dirac_reverse: dict[int, str] = {}
        self._update_filter_options()

    def _update_filter_options(self) -> None:
        filters = self.coordinator.dirac_filters
        if filters:
            self._dirac_map = {f["name"]: f["id"] for f in filters}
            self._dirac_reverse = {f["id"]: f["name"] for f in filters}
            self._attr_options = [f["name"] for f in filters]
        else:
            self._attr_options = ["off"]
            self._dirac_map = {"off": -1}
            self._dirac_reverse = {-1: "off"}

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
    def current_option(self) -> str | None:
        self._update_filter_options()
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        dirac_id = data.get("dirac", -1)
        return self._dirac_reverse.get(dirac_id, "off")

    async def async_select_option(self, option: str) -> None:
        filter_id = self._dirac_map.get(option, -1)
        await self.coordinator.api.set_dirac(filter_id)
        # Optimistic update
        if self.coordinator.data:
            self.coordinator.data["dirac"] = filter_id
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()


class KlipschLedModeSelect(CoordinatorEntity[KlipschCoordinator], SelectEntity):
    """Front LED brightness selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "led_mode"
    _attr_icon = "mdi:led-on"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_led_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}
        self._attr_options = LED_MODES

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
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        val = data.get("led_mode", "dim")
        # Field accepts free strings; show unknown values rather than dropping them
        return val if val in LED_MODES else "dim"

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_led_mode(option)
        if self.coordinator.data:
            self.coordinator.data["led_mode"] = option
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()
