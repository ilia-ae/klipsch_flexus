"""Diagnostics for Klipsch Flexus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_DEVICE_MAC, DOMAIN
from .coordinator import KlipschCoordinator

# Applied to the WHOLE output (diagnostics files get pasted into public issues).
# The write credential is base64(MAC + a public constant), so every device MAC is
# effectively the password; the hotspot BSSID geolocates the user's access point.
# Interface *names* (wired_interface / wireless_interface = "eth0" / "wlan0")
# are not identifiers and stay visible.
TO_REDACT = {
    CONF_HOST,
    CONF_DEVICE_MAC,
    # write_auth (api.signing_info)
    "signing_mac",
    "candidate_seeds",
    # network
    "eureka_mac",
    "mac_address",
    "hotspot_bssid",
    "registry_macs",
    # MAC sources (coordinator._seed_sources)
    "device_primary_mac",
    "manual_option",
    "device_registry",
    "arp_table",
    # player:player/data — unique device id ("ksb5000-<uuid>") and the stream
    # URL of Cast / Spotify / radio sources
    "systemMemberId",
    "uri",
}


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

    # Command health: read-only (no write-backs, so it can't revert a user
    # change or mislabel signed-OK commands) — readability plus the outcome of
    # the real writes this session. On 2026+ firmware with authMode=setData,
    # gated commands report needs_auth=True.
    try:
        command_health = await api.probe_command_health()
    except Exception as err:  # diagnostics must never raise
        command_health = {"error": type(err).__name__}

    try:
        network = await _network_info(hass, entry, coordinator)
    except Exception as err:  # noqa: BLE001
        network = {"error": type(err).__name__}

    write_auth = api.signing_info()
    # MACs are redacted below; keep the one fact write-auth debugging needs.
    signing_mac = write_auth.get("signing_mac")
    primary_mac = coordinator._seed_sources.get("device_primary_mac")
    write_auth["signing_mac_matches_primary_mac"] = signing_mac is not None and signing_mac == primary_mac

    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "device_status": coordinator.data or {},
            "dirac_filters": coordinator.dirac_filters,
            # 2026 write-auth: resolved?, candidates tried, gated paths (MACs redacted)
            "write_auth": write_auth,
            "network": network,
            "mac_sources": coordinator._seed_sources,
            # Wireless speakers: cinema:peripherals as reported (incl. the
            # unidentified group 3) and the versions read per speaker
            "speakers": {
                "peripherals": coordinator.peripherals_raw,
                "versions": coordinator.speaker_versions,
                "soundbar_versions": coordinator.bar_versions,
            },
            "command_health": command_health,
            "api_stats": {
                "last_response_time_ms": api.last_response_time,
                "total_requests": api.total_requests,
                "failed_requests": api.failed_requests,
            },
        },
        TO_REDACT,
    )
