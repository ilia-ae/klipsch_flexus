"""Config flow for Klipsch Flexus."""

from __future__ import annotations

from ipaddress import IPv4Address

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # HA < 2026.2
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .api import KlipschAPI
from .auth import mac_to_colon
from .const import CONF_DEVICE_MAC, CONF_SCAN_INTERVAL, DOMAIN, SCAN_INTERVAL_SECONDS


class KlipschFlexusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Klipsch Flexus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KlipschOptionsFlow(config_entry)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> config_entries.ConfigFlowResult:
        """Handle Zeroconf/mDNS discovery (Google Cast or AirPlay)."""
        # Prefer IPv4 — the soundbar HTTP API only listens on IPv4
        host = None
        for addr in discovery_info.ip_addresses:
            if isinstance(addr, IPv4Address):
                host = str(addr)
                break
        if host is None:
            host = str(discovery_info.ip_address)
        properties = discovery_info.properties

        # Google Cast TXT records use 'md' for model, 'fn' for friendly name
        model = properties.get("md", "")
        friendly_name = properties.get("fn", "")
        # AirPlay uses 'model' and the service name directly
        if not model:
            model = properties.get("model", "")

        # Filter: only Klipsch devices, skip AirCast proxy
        name_lower = discovery_info.name.lower()
        model_lower = model.lower()
        is_klipsch = (
            "klipsch" in name_lower or "flexus" in name_lower or "klipsch" in model_lower or "flexus" in model_lower
        )
        is_aircast_proxy = properties.get("am") == "aircast"

        if not is_klipsch or is_aircast_proxy:
            return self.async_abort(reason="not_klipsch_device")

        # Unique ID from Cast UUID or fallback to host
        device_id = properties.get("id", host)
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._discovered_host = host
        self._discovered_name = friendly_name or model or "Klipsch Flexus"
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Confirm Zeroconf discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Klipsch Flexus ({self._discovered_host})",
                data={CONF_HOST: self._discovered_host},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovered_name,
                "host": self._discovered_host,
            },
        )

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            api = KlipschAPI(host)
            try:
                status = await api.get_status()
                if status.get("online"):
                    # Try eureka_info for stable unique ID (MAC) and model check
                    device_info = await api.get_device_info()
                    unique_id = host
                    title = f"Klipsch Flexus ({host})"
                    if device_info:
                        mac = device_info.get("mac_address")
                        if mac:
                            unique_id = mac.replace(":", "").lower()
                        name = device_info.get("name", "")
                        if name:
                            title = name
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=title,
                        data={CONF_HOST: host},
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration (change IP address)."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            api = KlipschAPI(host)
            try:
                status = await api.get_status()
                if status.get("online"):
                    return self.async_update_reload_and_abort(
                        entry,
                        data={CONF_HOST: host},
                        title=f"Klipsch Flexus ({host})",
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await api.close()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                }
            ),
            errors=errors,
        )


class KlipschOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Klipsch Flexus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            mac = str(user_input.get(CONF_DEVICE_MAC, "")).strip()
            if mac and mac_to_colon(mac) is None:
                errors[CONF_DEVICE_MAC] = "invalid_mac"
            else:
                data = {CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]}
                if mac:
                    data[CONF_DEVICE_MAC] = mac_to_colon(mac)
                return self.async_create_entry(data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self._entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_SECONDS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                    vol.Optional(
                        CONF_DEVICE_MAC,
                        default=self._entry.options.get(CONF_DEVICE_MAC, ""),
                    ): str,
                }
            ),
            errors=errors,
        )
