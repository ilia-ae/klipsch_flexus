"""Data update coordinator for Klipsch Flexus."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KlipschAPI
from .const import (
    COMMAND_REFRESH_DELAY,
    CONF_DEVICE_MAC,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
    SCAN_INTERVAL_STANDBY,
)

_LOGGER = logging.getLogger(__name__)


def _arp_lookup(ip: str) -> str | None:
    """Best-effort MAC for ``ip`` from the kernel ARP table (Linux / HA OS)."""
    try:
        with open("/proc/net/arp") as fh:
            for line in fh.readlines()[1:]:
                cols = line.split()
                if len(cols) >= 4 and cols[0] == ip and cols[3] != "00:00:00:00:00:00":
                    return cols[3]
    except OSError:
        pass
    return None


class KlipschCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to poll Klipsch device status."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: KlipschAPI,
        name: str,
        scan_interval: int = SCAN_INTERVAL_SECONDS,
        entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.entry = entry
        self.dirac_filters: list[dict] = []
        self.device_info: dict | None = None  # eureka_info from port 8008
        self._normal_interval = timedelta(seconds=scan_interval)
        self._standby_interval = timedelta(seconds=SCAN_INTERVAL_STANDBY)
        self._write_auth_ready = False  # signing credential resolved
        self.network_info: dict = {}  # link / interfaces / MAC sources (diagnostics)
        self._net_interfaces: dict | None = None  # cached interface names
        self._seed_sources: dict = {}  # where each candidate MAC came from

    async def _gather_mac_seeds(self) -> list[str]:
        """Collect candidate MACs for the 2026 write-auth credential.

        eureka_info reports ``00:00:00:00:00:00`` on this firmware, so the MAC is
        taken from what HA already knows — a manual option, the device registry
        (populated by discovery / a router integration), and the ARP table.
        ``api`` expands each with last-byte neighbours and picks the one the
        device accepts.
        """
        seeds: list[str] = []
        sources: dict = {}
        if self.entry:
            manual = self.entry.options.get(CONF_DEVICE_MAC)
            if manual:
                seeds.append(manual)
                sources["manual_option"] = manual
            registry: list[str] = []
            try:
                reg = dr.async_get(self.hass)
                for device in dr.async_entries_for_config_entry(reg, self.entry.entry_id):
                    registry.extend(val for ctype, val in device.connections if ctype == dr.CONNECTION_NETWORK_MAC)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Klipsch: device-registry MAC lookup failed", exc_info=True)
            seeds.extend(registry)
            if registry:
                sources["device_registry"] = registry
        arp = await self.hass.async_add_executor_job(_arp_lookup, self.api.host)
        if arp:
            seeds.append(arp)
            sources["arp_table"] = arp
        self._seed_sources = sources
        return seeds

    async def _refresh_network_info(self) -> None:
        """Build the network/interface diagnostic snapshot (for sensors + diag)."""
        if self._net_interfaces is None:
            self._net_interfaces = {}
            try:
                wired = await self.api.get_data("settings:/network/wiredInterface")
                wireless = await self.api.get_data("settings:/network/wirelessInterface")
                self._net_interfaces = {
                    "wired_interface": wired[0].get("string_"),
                    "wireless_interface": wireless[0].get("string_"),
                }
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Klipsch: network interface read failed", exc_info=True)
        eu = self.device_info or {}
        self.network_info = {
            "active_link": "wired" if eu.get("ethernet_connected") else "wireless",
            "ethernet_connected": eu.get("ethernet_connected"),
            "eureka_mac": eu.get("mac_address"),
            "hotspot_bssid": eu.get("hotspot_bssid"),
            **self._net_interfaces,
            "mac_sources": self._seed_sources,
        }

    async def _refresh_mac_seeds(self) -> None:
        """Keep the signer's candidate MACs fresh (cheap; no device writes).

        Runs every poll until resolved — **including in standby** — so a turn_on
        from standby still has candidates and resolves the credential lazily on
        the power command.
        """
        if not self._write_auth_ready:
            self.api.set_mac_seeds(await self._gather_mac_seeds())

    async def _eager_resolve_write_auth(self) -> None:
        """Resolve the credential up front via an idempotent probe (device on)."""
        if self._write_auth_ready:
            return
        try:
            if await self.api.resolve_write_auth():
                self._write_auth_ready = True
                _LOGGER.info("Klipsch write commands enabled (signing credential resolved)")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Klipsch: write-auth resolution attempt failed", exc_info=True)

    async def _async_update_data(self) -> dict:
        try:
            status = await self.api.get_status()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Klipsch: {err}") from err

        if not status.get("online"):
            return {"online": False}

        # Adaptive polling interval: slow down in standby, speed up when on
        is_standby = status.get("power") == "networkStandby"
        desired = self._standby_interval if is_standby else self._normal_interval
        if self.update_interval != desired:
            self.update_interval = desired
            _LOGGER.debug(
                "Polling interval changed to %s s (%s)",
                desired.total_seconds(),
                "standby" if is_standby else "active",
            )

        # Always keep candidate MACs fresh — even in standby — so turn_on works.
        await self._refresh_mac_seeds()

        # In standby skip heavy fetches (player data, eureka_info, dirac)
        if is_standby:
            return status

        # Fetch device info once (eureka_info from Google Cast API)
        if self.device_info is None:
            try:
                self.device_info = await self.api.get_device_info()
            except Exception:
                _LOGGER.debug("Failed to fetch device info from port 8008")

        # Resolve the 2026 write-auth credential up front (idempotent probe, device on)
        await self._eager_resolve_write_auth()

        # Refresh the network/interface diagnostic snapshot (visible via sensors)
        await self._refresh_network_info()

        # Fetch Dirac filters once
        if not self.dirac_filters:
            try:
                self.dirac_filters = await self.api.get_dirac_filters()
            except Exception:
                self.dirac_filters = []

        # Fetch player/media data
        try:
            player = await self.api.get_player_data()
            if player:
                status["player"] = player
        except Exception:
            _LOGGER.debug("Failed to fetch player data")

        return status

    @callback
    def async_request_delayed_refresh(self, delay: float = COMMAND_REFRESH_DELAY) -> None:
        """Schedule a refresh after delay (non-blocking).

        Gives the soundbar time to process a command before we poll its state.
        """
        self.hass.loop.call_later(
            delay,
            lambda: self.hass.async_create_task(self.async_request_refresh()),
        )
