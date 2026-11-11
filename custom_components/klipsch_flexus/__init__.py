"""Klipsch Flexus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import KlipschAPI
from .const import CONF_SCAN_INTERVAL, DOMAIN, SCAN_INTERVAL_SECONDS, SPEAKER_SLOTS
from .coordinator import KlipschCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Klipsch Flexus from a config entry."""
    host = entry.data[CONF_HOST]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_SECONDS)
    api = KlipschAPI(host)
    coordinator = KlipschCoordinator(hass, api, host, scan_interval, entry=entry)

    await coordinator.async_config_entry_first_refresh()
    # Before the update listener is added: re-keying must not trigger a reload.
    coordinator.async_migrate_unique_id()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register the soundbar before the platforms, so the wireless speakers'
    # devices (binary_sensor) can link to it whichever platform runs first. The
    # media player fills in its name, model and firmware.
    dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: KlipschCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.cancel_pending_refreshes()
        # Stop scheduled / debounced refreshes before the session goes away
        # (HA does this itself only after async_unload_entry returns).
        shutdown = getattr(coordinator, "async_shutdown", None)
        if shutdown is not None:
            await shutdown()
        await coordinator.api.close()
    return unload_ok


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry) -> bool:
    """Allow deleting a wireless speaker's device (unpaired / sold / moved slot).

    Never the soundbar, and not a speaker that is linked right now (it would be
    re-created on the next poll anyway).
    """
    coordinator: KlipschCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    speakers = ((coordinator.data or {}).get("speakers") or {}) if coordinator else {}
    for slot in SPEAKER_SLOTS:
        if (DOMAIN, f"{entry.entry_id}_{slot}") in device.identifiers:
            return not (speakers.get(slot) or {}).get("connected")
    return False
