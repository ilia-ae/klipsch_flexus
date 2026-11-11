"""Button for Klipsch Flexus: read the wireless speakers on demand."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KlipschCoordinator
from .entity import KlipschEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KlipschReadSpeakersButton(coordinator, entry)])


class KlipschReadSpeakersButton(KlipschEntity, ButtonEntity):
    """Read which wireless speakers are linked and their versions, once.

    Without the "Monitor wireless speakers" option this is the only read after
    setup, so the regular poll stays as light as before.
    """

    _attr_translation_key = "read_speakers"
    _attr_icon = "mdi:speaker-wireless"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "read_speakers")

    async def async_press(self) -> None:
        await self.coordinator.async_read_speakers_now()
