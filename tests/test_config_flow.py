"""Tests for Klipsch Flexus config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # HA < 2026.2
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from custom_components.klipsch_flexus.const import DOMAIN

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
