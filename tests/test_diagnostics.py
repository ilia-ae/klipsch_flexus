"""Tests for Klipsch Flexus diagnostics."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from custom_components.klipsch_flexus.api import KlipschAPI
from custom_components.klipsch_flexus.auth import KlipschAuth
from custom_components.klipsch_flexus.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import MOCK_HOST, MOCK_STATUS

# Placeholder identifiers — NOT a real device.
PRIMARY_MAC = "AA:BB:CC:DD:EE:FF"
WIFI_MAC = "AA:BB:CC:DD:EE:FE"
BSSID = "11:22:33:44:55:66"


async def test_diagnostics(hass) -> None:
    """Test diagnostics output."""
    mock_api = MagicMock()
    mock_api.last_response_time = 42.5
    mock_api.total_requests = 100
    mock_api.failed_requests = 2
    mock_api.signing_info = MagicMock(return_value={"resolved": False})
    mock_api.probe_command_health = AsyncMock(return_value={"commands": {}})

    mock_coordinator = MagicMock()
    mock_coordinator.data = MOCK_STATUS.copy()
    mock_coordinator.dirac_filters = [{"id": 1, "name": "Filter 1"}]
    mock_coordinator.api = mock_api
    mock_coordinator.device_info = None
    mock_coordinator._seed_sources = {}

    mock_entry = MagicMock()
    mock_entry.data = {"host": MOCK_HOST}
    mock_entry.options = {"scan_interval": 15}
    mock_entry.entry_id = "test_entry_id"

    hass.data = {"klipsch_flexus": {"test_entry_id": mock_coordinator}}

    result = await async_get_config_entry_diagnostics(hass, mock_entry)

    assert "entry" in result
    assert "device_status" in result
    assert "api_stats" in result
    # Host should be redacted
    assert result["entry"]["data"]["host"] == "**REDACTED**"
    assert result["api_stats"]["total_requests"] == 100


async def test_diagnostics_redacts_macs_and_credentials(hass) -> None:
    """No device MAC, BSSID or replayable Authorization header leaks anywhere in
    the file, and the command-health probe writes nothing."""
    api = KlipschAPI(MOCK_HOST)
    api.set_mac_seeds([PRIMARY_MAC, WIFI_MAC])
    api._auth = KlipschAuth(PRIMARY_MAC, MOCK_HOST)
    api._auth_required_paths.add("cinema:/external/physicalAudioInput")

    async def get_data(path, timeout=8, **_):
        if "authMode" in path:
            return [{"type": "webserverAuthMode", "webserverAuthMode": "setData"}]
        if "wiredInterface" in path:
            return [{"type": "string_", "string_": "eth0"}]
        if "wirelessInterface" in path:
            return [{"type": "string_", "string_": "wlan0"}]
        if "powermanager" in path:
            return [{"powerTarget": {"target": "online"}}]
        return [{"type": "i32_", "i32_": 0}]

    api.get_data = get_data
    api.set_data = AsyncMock()
    api._ensure_session = AsyncMock(side_effect=AssertionError("diagnostics must not hit the network"))

    coordinator = MagicMock()
    coordinator.api = api
    coordinator.data = MOCK_STATUS.copy()
    coordinator.dirac_filters = []
    coordinator.device_info = {"mac_address": WIFI_MAC, "hotspot_bssid": BSSID, "ethernet_connected": False}
    coordinator._seed_sources = {"device_primary_mac": PRIMARY_MAC, "arp_table": WIFI_MAC}

    entry = MagicMock()
    entry.data = {"host": MOCK_HOST}
    entry.options = {"scan_interval": 15, "device_mac": PRIMARY_MAC}
    entry.entry_id = "test_entry_id"
    hass.data = {"klipsch_flexus": {"test_entry_id": coordinator}}

    result = await async_get_config_entry_diagnostics(hass, entry)
    dumped = json.dumps(result)

    for secret in (MOCK_HOST, PRIMARY_MAC, WIFI_MAC, BSSID, "HMAC_SHA256_AES256 "):
        assert secret not in dumped
    assert "sample_authorization" not in result["write_auth"]
    assert result["write_auth"]["resolved"] is True
    assert result["write_auth"]["signing_mac_matches_primary_mac"] is True
    assert result["entry"]["options"]["device_mac"] == "**REDACTED**"
    assert result["entry"]["options"]["scan_interval"] == 15
    assert result["network"]["wired_interface"] == "eth0"  # names stay visible
    assert result["mac_sources"]["arp_table"] == "**REDACTED**"
    # Read-only probe: gated input is reported via the real (signed) write path
    assert result["command_health"]["probe"] == "read-only"
    assert result["command_health"]["commands"]["input"]["needs_auth"] is True
    api.set_data.assert_not_called()
