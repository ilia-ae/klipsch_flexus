"""Tests for Klipsch Flexus config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # HA < 2026.2
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from custom_components.klipsch_flexus.const import CONF_DEVICE_MAC, CONF_SCAN_INTERVAL, DOMAIN

from .conftest import MOCK_HOST, MOCK_STATUS

MOCK_ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(MOCK_HOST),
    ip_addresses=[ip_address(MOCK_HOST)],
    hostname="3fb1d5cd-a039-be9c-934c-877174add9bf.local.",
    name="Flexus-Core-300-3fb1d5cda039be9c934c877174add9bf._googlecast._tcp.local.",
    port=8009,
    type="_googlecast._tcp.local.",
    properties={
        "id": "3fb1d5cda039be9c934c877174add9bf",
        "md": "Flexus Core 300",
        "fn": "Klipsch Flexus CORE 300",
        "ca": "199172",
        "st": "0",
    },
)

MOCK_AIRCAST_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.100"),
    ip_addresses=[ip_address("192.168.1.100")],
    hostname="aircast-proxy.local.",
    name="Klipsch-Flexus-CORE-300._googlecast._tcp.local.",
    port=8009,
    type="_googlecast._tcp.local.",
    properties={
        "id": "aircast-proxy-id",
        "md": "Klipsch Flexus CORE 300",
        "fn": "Klipsch Flexus CORE 300",
        "am": "aircast",
    },
)


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    with (
        patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls,
        patch("custom_components.klipsch_flexus.async_setup_entry", return_value=True),
    ):
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value=MOCK_STATUS)
        # No eureka_info → flow falls back to host-based unique_id and title.
        api.get_device_info = AsyncMock(return_value=None)
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: MOCK_HOST})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Klipsch Flexus ({MOCK_HOST})"
        assert result["data"] == {CONF_HOST: MOCK_HOST}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow when device is offline."""
    with patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls:
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value={"online": False})
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: MOCK_HOST})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_exception(hass: HomeAssistant) -> None:
    """Test config flow when API raises exception."""
    with patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls:
        api = mock_cls.return_value
        api.get_status = AsyncMock(side_effect=ConnectionError)
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: MOCK_HOST})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test Zeroconf discovery shows confirmation form."""
    with patch("custom_components.klipsch_flexus.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DISCOVERY,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zeroconf_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Klipsch Flexus ({MOCK_HOST})"
        assert result["data"] == {CONF_HOST: MOCK_HOST}


async def test_zeroconf_rejects_aircast_proxy(hass: HomeAssistant) -> None:
    """Test Zeroconf rejects AirCast proxy devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_AIRCAST_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_klipsch_device"


async def test_zeroconf_rejects_non_klipsch(hass: HomeAssistant) -> None:
    """Test Zeroconf rejects non-Klipsch Cast devices."""
    non_klipsch = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.200"),
        ip_addresses=[ip_address("192.168.1.200")],
        hostname="chromecast.local.",
        name="Chromecast-Ultra._googlecast._tcp.local.",
        port=8009,
        type="_googlecast._tcp.local.",
        properties={"md": "Chromecast Ultra", "fn": "Living Room TV"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=non_klipsch,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_klipsch_device"


async def test_user_flow_already_configured_aborts(hass: HomeAssistant) -> None:
    """A duplicate device aborts cleanly with 'already_configured' — the abort must
    not be swallowed by the broad connection-error handler and shown as cannot_connect."""
    MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data={CONF_HOST: "192.168.1.50"}).add_to_hass(hass)

    with patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls:
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value=MOCK_STATUS)
        api.get_device_info = AsyncMock(return_value={"mac_address": "AA:BB:CC:DD:EE:FF"})
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: MOCK_HOST})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_ignores_zero_mac(hass: HomeAssistant) -> None:
    """The all-zero MAC 2026 firmware reports must not become the unique_id (else
    every device would collide on '000000000000'); fall back to the host instead."""
    with (
        patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls,
        patch("custom_components.klipsch_flexus.async_setup_entry", return_value=True),
    ):
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value=MOCK_STATUS)
        api.get_device_info = AsyncMock(return_value={"mac_address": "00:00:00:00:00:00", "name": "My Bar"})
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: MOCK_HOST})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_HOST  # host fallback, not 000000000000
    assert result["title"] == "My Bar"


async def test_reconfigure_updates_host(hass: HomeAssistant) -> None:
    """Reconfigure to a reachable IP updates the entry's host."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data={CONF_HOST: "192.168.1.50"})
    entry.add_to_hass(hass)

    with (
        patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls,
        patch("custom_components.klipsch_flexus.async_setup_entry", return_value=True),
        patch("custom_components.klipsch_flexus.async_unload_entry", return_value=True),
    ):
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value=MOCK_STATUS)
        api.get_device_info = AsyncMock(return_value={"mac_address": "AA:BB:CC:DD:EE:FF"})
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.77"})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.77"


async def test_reconfigure_rejects_different_device(hass: HomeAssistant) -> None:
    """Pointing reconfigure at a different unit (different MAC) is refused."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data={CONF_HOST: "192.168.1.50"})
    entry.add_to_hass(hass)

    with patch("custom_components.klipsch_flexus.config_flow.KlipschAPI") as mock_cls:
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value=MOCK_STATUS)
        api.get_device_info = AsyncMock(return_value={"mac_address": "11:22:33:44:55:66"})  # other unit
        api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.168.1.77"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data[CONF_HOST] == "192.168.1.50"  # unchanged


async def test_options_flow_validates_mac(hass: HomeAssistant) -> None:
    """The options flow rejects a malformed MAC and normalizes a valid one."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data={CONF_HOST: MOCK_HOST})
    entry.add_to_hass(hass)

    # Invalid MAC → form re-shown with an error.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 15, CONF_DEVICE_MAC: "nope"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_MAC: "invalid_mac"}

    # Valid MAC (any separator/case) → normalized to AA:BB:CC:DD:EE:FF.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 20, CONF_DEVICE_MAC: "aa-bb-cc-dd-ee-ff"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 20, CONF_DEVICE_MAC: "AA:BB:CC:DD:EE:FF"}
