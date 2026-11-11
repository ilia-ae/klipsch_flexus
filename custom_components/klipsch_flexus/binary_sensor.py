"""Wireless speaker link sensors for Klipsch Flexus.

Each Flexus SUB / SURR speaker paired with the soundbar gets its own device
(linked to the soundbar) with a connectivity sensor. The link is read once after
setup and on the "Read wireless speakers" button; with the "Monitor wireless
speakers" option on every poll, so a speaker that drops its link shows up in HA.
Slots that never had a speaker get no device.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SPEAKER_SLOTS
from .coordinator import KlipschCoordinator
from .entity import KlipschEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    ent_reg = er.async_get(hass)
    added: set[str] = set()

    def wanted(slot: str) -> bool:
        """A speaker seen now (linked, or a model in the slot) or registered before."""
        speaker = ((coordinator.data or {}).get("speakers") or {}).get(slot)
        if speaker and (speaker["connected"] or speaker["model"]):
            return True
        unique_id = f"{entry.entry_id}_{slot}_connected"
        return ent_reg.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, unique_id) is not None

    @callback
    def add_new_speakers() -> None:
        new = [slot for slot in SPEAKER_SLOTS if slot not in added and wanted(slot)]
        if new:
            added.update(new)
            async_add_entities(KlipschSpeakerConnectedSensor(coordinator, entry, slot, added.discard) for slot in new)

    add_new_speakers()
    # A speaker paired later (or first seen once the bar is on) appears without a reload.
    entry.async_on_unload(coordinator.async_add_listener(add_new_speakers))


class KlipschSpeakerConnectedSensor(KlipschEntity, BinarySensorEntity):
    """Whether a wireless speaker was linked to the soundbar at the last read.

    Monitored: read every poll while the bar is on, unavailable in standby
    (speakers are not linked then). Otherwise it shows the last on-demand read
    (``last_checked``). Unavailable while the bar is offline.
    """

    _attr_translation_key = "speaker_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: KlipschCoordinator,
        entry: ConfigEntry,
        slot: str,
        forget_slot: Callable[[str], None],
    ) -> None:
        super().__init__(coordinator, entry, f"{slot}_connected")
        self._slot = slot
        self._forget_slot = forget_slot
        self._attr_device_info = coordinator.speaker_device_info(slot)

    async def async_will_remove_from_hass(self) -> None:
        """Forget the slot (device deleted by the user), so a re-paired speaker comes back."""
        self._forget_slot(self._slot)
        await super().async_will_remove_from_hass()

    def _speaker(self) -> dict[str, Any] | None:
        return ((self.coordinator.data or {}).get("speakers") or {}).get(self._slot)

    @property
    def available(self) -> bool:
        return super().available and self._speaker() is not None

    @property
    def is_on(self) -> bool | None:
        speaker = self._speaker()
        return None if speaker is None else speaker["connected"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Versions as the Klipsch Connect app shows them (Product Information)."""
        versions = self.coordinator.speaker_versions.get(self._slot, {})
        checked = self.coordinator.speakers_checked_at
        return {
            "last_checked": checked.isoformat() if checked else None,
            # The speaker's board answered (MCU / EQ versions, not 0.0.0) at the
            # last read; None before the first read of this speaker
            "mcu_responding": self.coordinator.speaker_responding.get(self._slot),
            "model_number": versions.get("model"),
            "rx_version": versions.get("rx"),
            "eq_firmware_version": versions.get("eq"),
            "mcu_firmware_version": versions.get("mcu"),
            "hw_version": versions.get("hw"),
        }
