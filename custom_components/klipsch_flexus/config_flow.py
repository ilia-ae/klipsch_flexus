"""Config flow for Klipsch Flexus."""

from __future__ import annotations

import re
from ipaddress import IPv4Address

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import callback

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # HA < 2026.2
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .api import KlipschAPI
from .auth import ZERO_MAC, mac_to_colon
from .const import API_PATHS, CONF_DEVICE_MAC, CONF_SCAN_INTERVAL, DOMAIN, SCAN_INTERVAL_SECONDS


def _is_mac_unique_id(unique_id: str | None) -> bool:
    """True if the entry's unique_id is a bare 12-hex-char MAC (vs a host fallback)."""
    return bool(unique_id) and re.fullmatch(r"[0-9a-f]{12}", unique_id) is not None


def _mac_id(mac: str | None) -> str | None:
    """``mac`` as a unique_id (12 lowercase hex chars), or None if invalid / all-zero."""
    colon = mac_to_colon(mac or "")
    if not colon or colon == ZERO_MAC:
        return None
    return colon.replace(":", "").lower()


async def _read_primary_mac_id(api: KlipschAPI) -> str | None:
    """The canonical unique_id: the device-reported wired MAC, normalised.

    ``settings:/system/primaryMacAddress`` is an auth-free read that works the
    same for every client and in standby (it's also the write-signing seed, see
    the coordinator), so the user and zeroconf flows agree on it. None if it
    can't be read — callers then fall back to their previous identifiers.
    """
    try:
        data = await api.get_data(API_PATHS["primary_mac"])
        return _mac_id(data[0].get("string_"))
    except Exception:  # noqa: BLE001 — any failure → caller's fallback id
        return None


class KlipschFlexusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Klipsch Flexus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._discovered_model: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KlipschOptionsFlow(config_entry)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> config_entries.ConfigFlowResult:
        """Handle Google Cast (``_googlecast._tcp``) mDNS discovery.

        The soundbar always advertises over Google Cast (the manifest's only
        matcher); the extra ``model``/``am`` lookups below just keep the
        Klipsch/AirCast filtering robust against TXT-record variations.
        """
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
        # Some records expose 'model' instead of 'md' — fall back to it.
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

        # An entry for this IP exists already (whatever its unique_id: older
        # entries are keyed by host or Cast UUID) → same soundbar, nothing to add.
        self._async_abort_entries_match({CONF_HOST: host})

        # Entries discovered before the MAC unique_id (and ignored discoveries)
        # are keyed by the Cast UUID: still follow their IP changes. Setup moves
        # them to the MAC (KlipschCoordinator.async_migrate_unique_id).
        cast_id = properties.get("id")
        if cast_id:
            await self.async_set_unique_id(cast_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Unique ID: the device MAC, as in the user flow; Cast UUID / host fallback
        api = KlipschAPI(host)
        try:
            device_id = await _read_primary_mac_id(api)
        finally:
            await api.close()
        await self.async_set_unique_id(device_id or cast_id or host)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._discovered_host = host
        self._discovered_name = friendly_name or model or "Klipsch Flexus"
        self._discovered_model = model or None
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Confirm Zeroconf discovery."""
        if user_input is not None:
            data = {CONF_HOST: self._discovered_host}
            if self._discovered_model:
                data[CONF_MODEL] = self._discovered_model  # device registry model
            return self.async_create_entry(title=f"Klipsch Flexus ({self._discovered_host})", data=data)

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
            self._async_abort_entries_match({CONF_HOST: host})
            api = KlipschAPI(host)
            try:
                status = await api.get_status()
                online = status.get("online")
                # eureka_info gives a friendly title (and a MAC on older firmware)
                device_info = await api.get_device_info() if online else None
                mac_id = await _read_primary_mac_id(api) if online else None
            except Exception:  # noqa: BLE001 — any connect/parse failure → cannot_connect
                status, device_info, mac_id = None, None, None
            finally:
                await api.close()

            if status and status.get("online"):
                # Prefer the device-reported MAC (the same id zeroconf uses), then
                # the eureka MAC, then the host. _mac_id ignores the all-zero MAC
                # 2026 firmware reports in eureka_info — it would make every
                # device collide on unique_id "000000000000".
                unique_id = mac_id or _mac_id((device_info or {}).get("mac_address")) or host
                title = f"Klipsch Flexus ({host})"
                if device_info and device_info.get("name"):
                    title = device_info["name"]
                # Outside the try: _abort_if_unique_id_configured raises AbortFlow,
                # which must propagate rather than be turned into "cannot_connect".
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data={CONF_HOST: host})
            errors["base"] = "cannot_connect"

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
                online = status.get("online")
                device_info = await api.get_device_info() if online else None
                mac_id = await _read_primary_mac_id(api) if online else None
            except Exception:  # noqa: BLE001 — any connect/parse failure → cannot_connect
                status, device_info, mac_id = None, None, None
            finally:
                await api.close()

            if status and status.get("online"):
                # If this entry is keyed by MAC and the device reports a real MAC,
                # make sure it's still the *same* unit — guards against typing a
                # different device's IP into the reconfigure form. Older entries
                # may be keyed by the eureka MAC rather than the primary one.
                reported = {i for i in (mac_id, _mac_id((device_info or {}).get("mac_address"))) if i}
                if reported and _is_mac_unique_id(entry.unique_id) and entry.unique_id not in reported:
                    return self.async_abort(reason="wrong_device")
                # Keep a friendly / user-set title; only the auto-generated
                # "Klipsch Flexus (<ip>)" one follows the new address.
                updates = {}
                if entry.title == f"Klipsch Flexus ({entry.data.get(CONF_HOST)})":
                    updates["title"] = f"Klipsch Flexus ({host})"
                return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: host}, **updates)
            errors["base"] = "cannot_connect"

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
            # A missing key means the field was cleared (the frontend drops empty
            # optional strings) → the manual MAC is removed from the options.
            mac = str(user_input.get(CONF_DEVICE_MAC, "")).strip()
            if mac and mac_to_colon(mac) is None:
                errors[CONF_DEVICE_MAC] = "invalid_mac"
            else:
                data = {CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]}
                if mac:
                    data[CONF_DEVICE_MAC] = mac_to_colon(mac)
                return self.async_create_entry(data=data)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self._entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_SECONDS),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                # Pre-filled as a suggestion, not a default: voluptuous would put a
                # default back when the field is cleared, so the MAC could never go.
                vol.Optional(CONF_DEVICE_MAC): str,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or self._entry.options),
            errors=errors,
        )
