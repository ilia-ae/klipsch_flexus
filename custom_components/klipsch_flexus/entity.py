"""Shared base entities for Klipsch Flexus."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KlipschCoordinator


class KlipschEntity(CoordinatorEntity[KlipschCoordinator]):
    """Base entity: links every entity to the one soundbar device.

    All entities share the same device (keyed by the config entry) and derive
    their unique id as ``<entry_id>_<key>``. The media player overrides
    ``_attr_device_info`` afterwards to enrich it from eureka_info; the rest keep
    the bare identifier set here.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}


class KlipschControllableEntity(KlipschEntity):
    """Base for writable controls (select / number / switch).

    Adds the online-gated availability shared by every control and the optimistic
    write helper: cache the just-applied value, mirror it into the coordinator
    data, push this entity's state, then schedule a confirming refresh.
    """

    @property
    def available(self) -> bool:
        """Available whenever the device is reachable (shows last value in standby)."""
        return bool((self.coordinator.data or {}).get("online")) and super().available

    def _optimistic_update(self, **values: Any) -> None:
        """Apply ``values`` optimistically after a successful write."""
        self.coordinator.api.note_cached(values)
        if self.coordinator.data:
            self.coordinator.data.update(values)
            self.async_write_ha_state()
        self.coordinator.async_request_delayed_refresh()
