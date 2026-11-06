"""Data update coordinator for Klipsch Flexus."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KlipschAPI
from .const import (
    API_PATHS,
    COMMAND_REFRESH_DELAY,
    CONF_DEVICE_MAC,
    DOMAIN,
    EAGER_AUTH_MAX_ATTEMPTS,
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


class KlipschCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        self._refresh_handles: set = set()  # pending delayed-refresh timers
        self._auth_mode: str | None = None  # settings:/webserver/authMode, read once
        self._eager_auth_attempts = 0  # fruitless eager write-auth probes
        self._device_info_stale = False  # re-read eureka_info after standby → on
        self._poll_task: asyncio.Future[dict[str, Any]] | None = None  # running poll
        self._poll_again = False  # a refresh was requested while polling

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
        # Best source: the device reports its own wired MAC — the exact credential
        # for write-signing — via an auth-free read. Deterministic for every client,
        # so it goes first (the ARP/registry/neighbour guesswork below is a fallback).
        try:
            pm = await self.api.get_data(API_PATHS["primary_mac"])
            mac = pm[0].get("string_")
            if mac and mac != "00:00:00:00:00:00":
                seeds.append(mac)
                sources["device_primary_mac"] = mac
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Klipsch: primaryMacAddress read failed", exc_info=True)
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
        the power command. Once the credential is resolved — eagerly, or lazily
        by a command — there is nothing left to seed.
        """
        if self._write_auth_ready:
            return
        if self.api.signing_mac is not None:
            self._write_auth_ready = True
            return
        self.api.set_mac_seeds(await self._gather_mac_seeds())

    async def _eager_resolve_write_auth(self) -> None:
        """Resolve the credential up front via an idempotent probe (device on).

        Skipped when the firmware doesn't gate writes (authMode ``none``, read
        once), and given up after ``EAGER_AUTH_MAX_ATTEMPTS`` fruitless tries —
        e.g. firmware without the HTTPS endpoint — so polls don't keep probing.
        A gated (401) command still resolves the credential lazily.
        """
        if self._write_auth_ready or self._eager_auth_attempts >= EAGER_AUTH_MAX_ATTEMPTS:
            return
        if self._auth_mode is None:
            try:
                self._auth_mode = await self.api.get_auth_mode()
            except Exception:  # noqa: BLE001
                self._auth_mode = "unknown"
        if self._auth_mode == "none":
            return  # writes are open; nothing to sign
        try:
            if await self.api.resolve_write_auth():
                self._write_auth_ready = True
                _LOGGER.info("Klipsch write commands enabled (signing credential resolved)")
                return
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Klipsch: write-auth resolution attempt failed", exc_info=True)
        self._eager_auth_attempts += 1
        if self._eager_auth_attempts >= EAGER_AUTH_MAX_ATTEMPTS:
            _LOGGER.debug("Klipsch: eager write-auth resolution stopped; the first gated command resolves it")

    @callback
    def _async_update_device_registry(self) -> None:
        """Push the eureka name / firmware version to the device entry.

        The media player reads eureka_info only when it is created, so a setup
        in standby (no eureka yet) or a later firmware update would otherwise
        leave the device with the generic name and a missing or stale
        sw_version until a reload. A name the user set (``name_by_user``) still
        wins in the UI.
        """
        if self.entry is None or not self.device_info:
            return
        reg = dr.async_get(self.hass)
        # Looked up via the entry (works on every supported HA; async_get_device
        # by identifiers is deprecated in newer releases).
        identifier = (DOMAIN, self.entry.entry_id)
        device = next(
            (d for d in dr.async_entries_for_config_entry(reg, self.entry.entry_id) if identifier in d.identifiers),
            None,
        )
        if device is None:
            return  # not registered yet — the media player will use device_info
        changes: dict[str, str] = {}
        name = self.device_info.get("name")
        if name and name != device.name:
            changes["name"] = name
        sw_version = self.device_info.get("cast_build_revision")
        if sw_version and sw_version != device.sw_version:
            changes["sw_version"] = sw_version
        if changes:
            reg.async_update_device(device.id, **changes)

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll the device — one poll at a time.

        A full poll (~40 sequential reads) outlasts the scan interval, and a
        command's refresh (or a re-armed timer) can start another refresh
        mid-poll. Two interleaved polls would double the load on the
        single-threaded device, and the older one could publish pre-command
        values. So a refresh arriving mid-poll joins the running poll, which
        then runs once more to pick up the command's effect (and again if
        another refresh arrives during that follow-up).
        """
        if self._poll_task is not None and not self._poll_task.done():
            self._poll_again = True
            return await asyncio.shield(self._poll_task)
        self._poll_again = False
        task = asyncio.ensure_future(self._async_poll_with_follow_up())
        self._poll_task = task
        try:
            return await task
        finally:
            if self._poll_task is task:
                self._poll_task = None

    async def _async_poll_with_follow_up(self) -> dict[str, Any]:
        """Run one poll, then another as long as a refresh was requested meanwhile."""
        status = await self._async_poll()
        while self._poll_again:
            self._poll_again = False
            status = await self._async_poll()
        return status

    async def _async_poll(self) -> dict[str, Any]:
        try:
            # seed_standby: a first poll in standby reads everything once
            status = await self.api.get_status(seed_standby=True)
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
            # Re-read eureka_info once the bar is back on, so sw_version follows
            # firmware updates (installed while in standby).
            self._device_info_stale = self.device_info is not None
            return status

        # Fetch device info (eureka_info from Google Cast API) once, and again
        # after each standby → on transition
        if self.device_info is None or self._device_info_stale:
            self._device_info_stale = False
            try:
                info = await self.api.get_device_info()
            except Exception:
                info = None
                _LOGGER.debug("Failed to fetch device info from port 8008")
            if info is not None:
                self.device_info = info
                self._async_update_device_registry()

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
        The timer handle is tracked so it can be cancelled on unload (otherwise a
        command issued just before unload would fire a refresh on a dead entry).
        """

        def _fire() -> None:
            self._refresh_handles.discard(handle)
            if self.entry is not None:
                # Tied to the entry, so unload cancels a refresh still running.
                self.entry.async_create_background_task(
                    self.hass, self.async_request_refresh(), name=f"{self.name} delayed refresh"
                )
            else:
                self.hass.async_create_task(self.async_request_refresh())

        handle = self.hass.loop.call_later(delay, _fire)
        self._refresh_handles.add(handle)

    @callback
    def cancel_pending_refreshes(self) -> None:
        """Cancel any scheduled delayed refreshes (called on unload)."""
        for handle in self._refresh_handles:
            handle.cancel()
        self._refresh_handles.clear()
