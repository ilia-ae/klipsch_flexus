"""Diagnostics for Klipsch Flexus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import KlipschCoordinator

TO_REDACT = {CONF_HOST}


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

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device_status": coordinator.data or {},
        "dirac_filters": coordinator.dirac_filters,
        "command_health": command_health,
        "api_stats": {
            "last_response_time_ms": api.last_response_time,
            "total_requests": api.total_requests,
            "failed_requests": api.failed_requests,
        },
    }
