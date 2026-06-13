"""Diagnostic sensors for Klipsch Flexus."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SOUND_MODES, SOURCES
from .coordinator import KlipschCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            KlipschResponseTimeSensor(coordinator, entry),
            KlipschStatusSensor(coordinator, entry),
            KlipschInputSensor(coordinator, entry),
            KlipschSoundModeSensor(coordinator, entry),
            KlipschSigningMacSensor(coordinator, entry),
            KlipschNetworkLinkSensor(coordinator, entry),
        ]
    )


class KlipschResponseTimeSensor(CoordinatorEntity[KlipschCoordinator], SensorEntity):
    """API response time (last request)."""

    _attr_has_entity_name = True
    _attr_translation_key = "response_time"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_response_time"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("poll_time_ms")

    @property
    def extra_state_attributes(self) -> dict:
        api = self.coordinator.api
        return {
            "last_request_ms": api.last_response_time,
            "total_requests": api.total_requests,
            "failed_requests": api.failed_requests,
        }


class KlipschStatusSensor(CoordinatorEntity[KlipschCoordinator], SensorEntity):
    """Device online/offline status with decoder info."""

    _attr_has_entity_name = True
    _attr_translation_key = "device_status"
    _attr_icon = "mdi:soundbar"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["offline", "on", "standby"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return "offline"
        power = data.get("power", "unknown")
        if power == "networkStandby":
            return "standby"
        return "on"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return {}
        attrs = {
            "decoder": data.get("decoder", "unknown"),
            "failed_params": data.get("failed_params", 0),
            "poll_time_ms": data.get("poll_time_ms"),
        }
        # Player info if available
        player = data.get("player")
        if player and isinstance(player, dict):
            attrs["media_title"] = player.get("title", "")
            attrs["media_artist"] = player.get("artist", "")
        return attrs


class KlipschInputSensor(CoordinatorEntity[KlipschCoordinator], SensorEntity):
    """Active audio input source."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_input"
    _attr_icon = "mdi:audio-input-stereo-minijack"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(SOURCES.keys())
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_input"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def available(self) -> bool:
        """Unavailable when device is offline (coordinator returned online=False)."""
        data = self.coordinator.data or {}
        if not data.get("online"):
            return False
        return super().available

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("input")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        raw = data.get("input", "")
        return {"display_name": SOURCES.get(raw, raw)}


class KlipschSoundModeSensor(CoordinatorEntity[KlipschCoordinator], SensorEntity):
    """Active sound mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_sound_mode"
    _attr_icon = "mdi:surround-sound"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = SOUND_MODES
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_sound_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def available(self) -> bool:
        """Unavailable when device is offline (coordinator returned online=False)."""
        data = self.coordinator.data or {}
        if not data.get("online"):
            return False
        return super().available

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("mode")


class KlipschSigningMacSensor(CoordinatorEntity[KlipschCoordinator], SensorEntity):
    """The MAC the integration uses to sign 2026-firmware write commands."""

    _attr_has_entity_name = True
    _attr_translation_key = "signing_mac"
    _attr_icon = "mdi:key-chain-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_signing_mac"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def native_value(self) -> str:
        info = self.coordinator.api.signing_info()
        if info.get("signing_mac"):
            return info["signing_mac"]
        return "auth failed" if info.get("auth_failed") else "not resolved"

    @property
    def extra_state_attributes(self) -> dict:
        # scheme / username / resolved / auth_failed / candidate_seeds / gated_paths_seen
        return self.coordinator.api.signing_info()


class KlipschNetworkLinkSensor(CoordinatorEntity[KlipschCoordinator], SensorEntity):
    """Which network interface the soundbar is connected through (wired/wireless)."""

    _attr_has_entity_name = True
    _attr_translation_key = "network_link"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_network_link"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def icon(self) -> str:
        return "mdi:ethernet-cable" if self.coordinator.network_info.get("active_link") == "wired" else "mdi:wifi"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.network_info.get("active_link")

    @property
    def extra_state_attributes(self) -> dict:
        # ethernet_connected / eureka_mac / hotspot_bssid / wired+wireless interface / mac_sources
        return {k: v for k, v in self.coordinator.network_info.items() if k != "active_link"}
