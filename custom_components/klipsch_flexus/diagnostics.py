"""Diagnostics for Klipsch Flexus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import KlipschCoordinator

TO_REDACT = {CONF_HOST}


async def _network_info(hass: HomeAssistant, entry: ConfigEntry, coordinator: KlipschCoordinator) -> dict[str, Any]:
    """Network interfaces + the MACs HA knows for the device.

    Helps debug write-auth: the credential MAC must match the device, and on
    2026 firmware eureka_info reports 00:00:00:00:00:00, so the integration falls
    back to the registry/ARP MAC and its neighbours.
    """
    api = coordinator.api
    eureka = coordinator.device_info or {}
    net: dict[str, Any] = {
        "eureka_mac": eureka.get("mac_address"),
        "ethernet_connected": eureka.get("ethernet_connected"),
        "hotspot_bssid": eureka.get("hotspot_bssid"),
        "active_link": "wired" if eureka.get("ethernet_connected") else "wireless",
    }
    try:
        wired = await api.get_data("settings:/network/wiredInterface")
        wireless = await api.get_data("settings:/network/wirelessInterface")
        net["wired_interface"] = wired[0].get("string_")
        net["wireless_interface"] = wireless[0].get("string_")
    except Exception:  # noqa: BLE001 — diagnostics must never raise
        pass
    try:
        reg = dr.async_get(hass)
        macs: list[str] = []
        for device in dr.async_entries_for_config_entry(reg, entry.entry_id):
            macs.extend(val for ctype, val in device.connections if ctype == dr.CONNECTION_NETWORK_MAC)
        net["registry_macs"] = macs
    except Exception:  # noqa: BLE001
        pass
    return net


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    api = coordinator.api

    # Deep probe: which write commands the firmware still accepts. Idempotent —
    # reads each value and writes it straight back. On 2026+ firmware with
    # authMode=setData, most commands report needs_auth=True.
    try:
        command_health = await api.probe_command_health()
    except Exception as err:  # diagnostics must never raise
        command_health = {"error": type(err).__name__}

    try:
        network = await _network_info(hass, entry, coordinator)
    except Exception as err:  # noqa: BLE001
        network = {"error": type(err).__name__}

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device_status": coordinator.data or {},
        "dirac_filters": coordinator.dirac_filters,
        # 2026 write-auth: resolved signing MAC, candidates tried, sample signature
        "write_auth": api.signing_info(),
        "network": network,
        "command_health": command_health,
        "api_stats": {
            "last_response_time_ms": api.last_response_time,
            "total_requests": api.total_requests,
            "failed_requests": api.failed_requests,
        },
    }
