"""Data update coordinator for Klipsch Flexus."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import _TRANSPORT_ERRORS, KlipschAPI
from .config_flow import _mac_id
from .const import (
    API_PATHS,
    COMMAND_REFRESH_DELAY,
    CONF_DEVICE_MAC,
    CONF_MONITOR_SPEAKERS,
    DOMAIN,
    EAGER_AUTH_MAX_ATTEMPTS,
    SCAN_INTERVAL_SECONDS,
    SCAN_INTERVAL_STANDBY,
    SPEAKER_SLOTS,
    SPEAKER_VERSION_READS,
)

_LOGGER = logging.getLogger(__name__)

# Newer HA links a child device by the parent's registry id (``via_device`` is
# deprecated there, removal planned for 2027.8); older releases only know the
# ``via_device`` identifier.
_HAS_VIA_DEVICE_ID = "via_device_id" in dr.DeviceInfo.__annotations__


def speaker_sw_version(versions: dict[str, str | None]) -> str | None:
    """``MCU 1.0.4 · RX 4.6 · EQ 0.3.0`` from a speaker's versions (None if none)."""
    parts = [
        f"{label} {versions[key]}" for key, label in (("mcu", "MCU"), ("rx", "RX"), ("eq", "EQ")) if versions.get(key)
    ]
    return " · ".join(parts) or None


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
        # Wireless speakers. Read once after setup (first poll with the bar on)
        # and on the "Read wireless speakers" button; every poll only with the
        # "Monitor wireless speakers" option. Versions per slot (hostlink:*).
        self.monitor_speakers = bool(entry.options.get(CONF_MONITOR_SPEAKERS, False)) if entry else False
        self.speakers: dict[str, dict[str, Any]] | None = None  # last cinema:peripherals read
        self.speakers_checked_at: datetime | None = None
        self._speaker_read_pending = True  # the one read after setup
        self.speaker_versions: dict[str, dict[str, str | None]] = {}
        self._speaker_versions_key: dict[str, tuple] = {}
        self._speaker_version_attempts: dict[str, int] = {}  # incomplete reads so far
        self.peripherals_raw: list = []  # cinema:peripherals as reported (diagnostics)
        self.bar_versions: dict[str, str | None] = {}  # soundbar MCU / TX / HDMI / HW
        # Device name from before this setup (the platforms register concurrently,
        # so the media player can't tell a new device from an existing one later).
        self.registered_name: str | None = getattr(self.registered_device(), "name", None)

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

    @callback
    def async_migrate_unique_id(self) -> None:
        """Re-key an older entry (Cast UUID, host or eureka MAC) by the primary MAC.

        The config flows now key the soundbar by its primary MAC; without this,
        discovery of an older entry at a new IP would match nothing and offer
        a duplicate. Uses the MAC the first poll read (nothing to do if it
        couldn't); left alone if another entry already holds that id.
        """
        new_id = _mac_id(self._seed_sources.get("device_primary_mac"))
        if self.entry is None or new_id is None or self.entry.unique_id == new_id:
            return
        entries = self.hass.config_entries.async_entries(DOMAIN, include_ignore=True)
        if any(e.unique_id == new_id for e in entries):
            return
        _LOGGER.debug("Klipsch: unique_id %s → %s (primary MAC)", self.entry.unique_id, new_id)
        self.hass.config_entries.async_update_entry(self.entry, unique_id=new_id)

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
    def registered_device(self, slot: str | None = None) -> dr.DeviceEntry | None:
        """The soundbar's (or a speaker ``slot``'s) registry entry, or None."""
        if self.entry is None:
            return None
        reg = dr.async_get(self.hass)
        # Looked up via the entry (works on every supported HA; async_get_device
        # by identifiers is deprecated in newer releases).
        identifier = (DOMAIN, self.entry.entry_id if slot is None else f"{self.entry.entry_id}_{slot}")
        return next(
            (d for d in dr.async_entries_for_config_entry(reg, self.entry.entry_id) if identifier in d.identifiers),
            None,
        )

    def speaker_device_info(self, slot: str) -> dict[str, Any]:
        """Device info of a wireless speaker, linked to the soundbar.

        ``sw_version`` lists the speaker's firmware parts (MCU / RX / EQ) and
        ``model_id`` its model number, as the Klipsch Connect app shows them.
        """
        entry_id = self.entry.entry_id if self.entry else ""
        versions = self.speaker_versions.get(slot, {})
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, f"{entry_id}_{slot}")},
            "translation_key": slot,
            "manufacturer": "Klipsch",
            "model": SPEAKER_SLOTS[slot][3],
        }
        # Only known values: an explicit None would wipe what the registry holds
        # (e.g. after a restart in standby, before the speaker is read again).
        for key, value in (
            ("sw_version", speaker_sw_version(versions)),
            ("hw_version", versions.get("hw")),
            ("model_id", versions.get("model")),
        ):
            if value:
                info[key] = value
        if _HAS_VIA_DEVICE_ID:
            parent = self.registered_device()
            if parent is not None:
                info["via_device_id"] = parent.id
        else:
            info["via_device"] = (DOMAIN, entry_id)
        return info

    @callback
    def _async_update_speaker_device(self, slot: str) -> None:
        """Push a speaker's new versions to its (already registered) device."""
        device = self.registered_device(slot)
        if device is None:
            return  # the entity registers it with speaker_device_info()
        info = self.speaker_device_info(slot)
        changes = {
            key: info.get(key)
            for key in ("sw_version", "hw_version", "model_id")
            if info.get(key) is not None and info.get(key) != getattr(device, key, None)
        }
        if changes:
            dr.async_get(self.hass).async_update_device(device.id, **changes)

    async def async_read_speakers(self, full: bool = False) -> bool:
        """Read which wireless speakers are linked, and their versions.

        ``full`` (after setup, the button): re-read every linked speaker's
        versions and the soundbar's. Otherwise (monitoring, every poll) one
        request, plus a speaker's four version reads only when it links with
        another RX version / model or still reported "0.0.0" (a few polls).
        Returns False if the device stopped answering (nothing more is read).
        """
        try:
            peripherals = await self.api.get_peripherals()
        except _TRANSPORT_ERRORS:
            _LOGGER.debug("Klipsch: device stopped answering (cinema:peripherals)")
            return False
        except Exception:  # noqa: BLE001 — optional; older firmware may lack the node
            _LOGGER.debug("Klipsch: cinema:peripherals read failed", exc_info=True)
            return True
        self.speakers = peripherals["speakers"]
        self.speakers_checked_at = dt_util.utcnow()
        self.peripherals_raw = peripherals["raw"]
        if full:
            self._speaker_versions_key.clear()
            self._speaker_version_attempts.clear()
        for slot, speaker in peripherals["speakers"].items():
            key = (speaker["rx"], speaker["model"])
            if not speaker["connected"] or self._speaker_versions_key.get(slot) == key:
                continue
            try:
                versions = await self.api.get_speaker_versions(slot)
            except _TRANSPORT_ERRORS:
                _LOGGER.debug("Klipsch: device stopped answering during %s versions", slot)
                return False  # don't wait out the other speakers' timeouts
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Klipsch: %s versions read failed", slot, exc_info=True)
                continue
            versions["model"] = speaker["model"]
            known = self.speaker_versions.get(slot, {})
            # Keep parts read before when this read has none (e.g. "0.0.0")
            self.speaker_versions[slot] = {k: v or known.get(k) for k, v in versions.items()}
            attempts = self._speaker_version_attempts.get(slot, 0) + 1
            self._speaker_version_attempts[slot] = attempts
            # A speaker that just linked may not report its MCU / EQ yet: with
            # monitoring, read again on the next polls (a few times).
            complete = all(versions.get(k) for k in ("mcu", "eq", "hw"))
            if complete or not self.monitor_speakers or attempts >= SPEAKER_VERSION_READS:
                self._speaker_versions_key[slot] = key
                self._speaker_version_attempts.pop(slot, None)
            self._async_update_speaker_device(slot)
        if full:
            return await self._read_bar_versions()
        return True

    async def _read_bar_versions(self) -> bool:
        """Soundbar component versions; HW revision → the device's hw_version."""
        try:
            versions = await self.api.get_bar_versions()
        except _TRANSPORT_ERRORS:
            _LOGGER.debug("Klipsch: device stopped answering (soundbar versions)")
            return False
        except Exception:  # noqa: BLE001 — informational; never fails a poll
            _LOGGER.debug("Klipsch: soundbar versions read failed", exc_info=True)
            return True
        if versions:
            self.bar_versions = versions
        hw = self.bar_versions.get("hardware_revision")
        device = self.registered_device()
        if hw and device is not None and device.hw_version != hw:
            dr.async_get(self.hass).async_update_device(device.id, hw_version=hw)
        return True

    async def async_read_speakers_now(self) -> None:
        """The "Read wireless speakers" button: a full read, published at once."""
        if not await self.async_read_speakers(full=True):
            raise HomeAssistantError("The soundbar did not answer")
        self._speaker_read_pending = False
        if self.data is not None:
            self.data["speakers"] = self.speakers
        self.async_update_listeners()

    @callback
    def _async_update_device_registry(self) -> None:
        """Push the eureka name / firmware version to the device entry.

        The media player reads eureka_info only when it is created, so a setup
        in standby (no eureka yet) or a later firmware update would otherwise
        leave the device with the generic name and a missing or stale
        sw_version until a reload. A name the user set (``name_by_user``) still
        wins in the UI.
        """
        if not self.device_info:
            return
        device = self.registered_device()
        if device is None:
            return  # not registered yet — the media player will use device_info
        reg = dr.async_get(self.hass)
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
            self._speaker_versions_key.clear()  # speakers may update in standby
            self._speaker_version_attempts.clear()
            if not self.monitor_speakers and self.speakers is not None:
                status["speakers"] = self.speakers  # last read (on demand)
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

        # Wireless speakers: once after setup, then every poll only if monitored
        if self.monitor_speakers or self._speaker_read_pending:
            full = self._speaker_read_pending
            self._speaker_read_pending = False
            if not await self.async_read_speakers(full=full):
                self._speaker_read_pending = full  # retry the setup read next poll
            elif self.monitor_speakers:
                status["speakers"] = self.speakers
        if not self.monitor_speakers and self.speakers is not None:
            status["speakers"] = self.speakers  # last read (on demand)

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
