"""Select entities for Klipsch Flexus."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DIALOG_MODES,
    DIRAC_OFF,
    DOMAIN,
    EQ_PRESET_CUSTOM,
    EQ_PRESETS,
    IDLE_TIMEOUTS,
    LED_MODES,
    NIGHT_MODES,
)
from .coordinator import KlipschCoordinator
from .entity import KlipschControllableEntity

_IDLE_TIMEOUT_OPTIONS = {seconds: option for option, seconds in IDLE_TIMEOUTS.items()}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        KlipschNightModeSelect(coordinator, entry),
        KlipschDialogModeSelect(coordinator, entry),
        KlipschEqPresetSelect(coordinator, entry),
        KlipschDiracSelect(coordinator, entry),
        KlipschLedModeSelect(coordinator, entry),
        KlipschIdleTimeoutSelect(coordinator, entry),
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
        return data.get("night_mode")

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
        return data.get("dialog_mode")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_dialog_mode(option)
        self._optimistic_update(dialog_mode=option)


class KlipschEqPresetSelect(KlipschControllableEntity, SelectEntity):
    """EQ preset selector.

    The device reports ``custom`` once bass/mid/treble are changed (or a curve is
    set in the Klipsch app). That is a derived state, not a preset that can be
    written, so it is offered as an option only while the device reports it —
    enough for the select to show the real state instead of Unknown, without
    advertising a choice that would always fail.
    """

    _attr_translation_key = "eq_preset"
    _attr_icon = "mdi:tune-variant"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "eq_preset")

    @property
    def options(self) -> list[str]:
        if (self.coordinator.data or {}).get("eq_preset") == EQ_PRESET_CUSTOM:
            return [*EQ_PRESETS, EQ_PRESET_CUSTOM]
        return EQ_PRESETS

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("eq_preset")

    async def async_select_option(self, option: str) -> None:
        if option == EQ_PRESET_CUSTOM:
            raise ServiceValidationError(
                "The custom EQ is set by changing bass/mid/treble or in the Klipsch app; it cannot be selected"
            )
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
        dirac_id = data.get("dirac")
        if dirac_id is None:
            return None  # not read yet
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
        val = data.get("led_mode")
        # Field accepts free strings; a value outside the standard set (or one not
        # read yet) shows as unknown rather than being passed off as another mode
        return val if val in LED_MODES else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api.set_led_mode(option)
        self._optimistic_update(led_mode=option)


class KlipschIdleTimeoutSelect(KlipschControllableEntity, SelectEntity):
    """Idle timeout — an enum of fixed durations on the device (maxIdleTimeValues)."""

    _attr_translation_key = "idle_timeout"
    _attr_icon = "mdi:timer-sand"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(IDLE_TIMEOUTS)

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "idle_timeout")

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        # A value outside the device's list (or not read yet) shows as unknown
        return _IDLE_TIMEOUT_OPTIONS.get(data.get("idle_timeout"))

    async def async_select_option(self, option: str) -> None:
        seconds = IDLE_TIMEOUTS[option]
        await self.coordinator.api.set_number("idle_timeout", seconds, "i32_")
        self._optimistic_update(idle_timeout=seconds)
