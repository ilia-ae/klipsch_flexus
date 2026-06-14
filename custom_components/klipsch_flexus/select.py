"""Select entities for Klipsch Flexus."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DIALOG_MODES,
    DIRAC_OFF,
    DOMAIN,
    EQ_PRESETS,
    LED_MODES,
    NIGHT_MODES,
)
from .coordinator import KlipschCoordinator
from .entity import KlipschControllableEntity


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


class KlipschNightModeSelect(KlipschControllableEntity, SelectEntity):
    """Night mode selector."""

    _attr_translation_key = "night_mode"
    _attr_icon = "mdi:weather-night"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "night_mode")
        self._attr_options = NIGHT_MODES

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("night_mode", "off")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_night_mode(option)
        self._optimistic_update(night_mode=option)


class KlipschDialogModeSelect(KlipschControllableEntity, SelectEntity):
    """Dialog mode selector."""

    _attr_translation_key = "dialog_mode"
    _attr_icon = "mdi:account-voice"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "dialog_mode")
        self._attr_options = DIALOG_MODES

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("dialog_mode", "off")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_dialog_mode(option)
        self._optimistic_update(dialog_mode=option)


class KlipschEqPresetSelect(KlipschControllableEntity, SelectEntity):
    """EQ preset selector."""

    _attr_translation_key = "eq_preset"
    _attr_icon = "mdi:tune-variant"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "eq_preset")
        self._attr_options = EQ_PRESETS

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("eq_preset", "flat")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_eq_preset(option)
        self._optimistic_update(eq_preset=option)


class KlipschDiracSelect(KlipschControllableEntity, SelectEntity):
    """Dirac room correction filter selector."""

    _attr_translation_key = "dirac"
    _attr_icon = "mdi:tune"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "dirac")
        self._dirac_map: dict[str, int] = {}
        self._dirac_reverse: dict[int, str] = {}
        self._update_filter_options()

    def _update_filter_options(self) -> None:
        """Sync the name<->id Dirac maps + option list from the coordinator's filters."""
        filters = self.coordinator.dirac_filters
        if filters:
            self._dirac_map = {f["name"]: f["id"] for f in filters}
            self._dirac_reverse = {f["id"]: f["name"] for f in filters}
            self._attr_options = [f["name"] for f in filters]
        else:
            self._attr_options = ["off"]
            self._dirac_map = {"off": DIRAC_OFF}
            self._dirac_reverse = {DIRAC_OFF: "off"}

    @property
    def current_option(self) -> str | None:
        self._update_filter_options()
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        dirac_id = data.get("dirac", DIRAC_OFF)
        return self._dirac_reverse.get(dirac_id, "off")

    async def async_select_option(self, option: str) -> None:
        filter_id = self._dirac_map.get(option, DIRAC_OFF)
        await self.coordinator.api.set_dirac(filter_id)
        self._optimistic_update(dirac=filter_id)


class KlipschLedModeSelect(KlipschControllableEntity, SelectEntity):
    """Front LED brightness selector."""

    _attr_translation_key = "led_mode"
    _attr_icon = "mdi:led-on"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "led_mode")
        self._attr_options = LED_MODES

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
        self._optimistic_update(led_mode=option)
