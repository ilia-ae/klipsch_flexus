"""Klipsch Flexus HTTP API client."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from urllib.parse import quote

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .auth import AUTH_SCHEME, KlipschAuth, expand_mac_candidates
from .const import (
    API_PATHS,
    API_RETRIES,
    API_RETRY_DELAY,
    API_TIMEOUT_POWER,
    API_TIMEOUT_READ,
    API_TIMEOUT_WRITE,
    BAR_VERSION_PATHS,
    DIRAC_OFF,
    NIGHT_MODE_FROM_API,
    NIGHT_MODE_TO_API,
    OPTIMISTIC_SETTLE,
    OPTIMISTIC_TTL,
    PERIPHERALS_PATH,
    POLL_MAX_TRANSPORT_ERRORS,
    SPEAKER_SLOTS,
    SPEAKER_VERSION_NODES,
    VOLUME_MAX_DEFAULT,
    VOLUME_MAX_PROBE_TRIES,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

# The device did not answer at all (vs. answering with an error / bad payload).
_TRANSPORT_ERRORS = (TimeoutError, aiohttp.ClientConnectionError, OSError)


class KlipschAPI:
    """Client for Klipsch Flexus native HTTP API.

    The soundbar is single-threaded — all requests are serialized via asyncio.Lock
    to prevent collisions between polling and commands.
    """

    def __init__(self, host: str, port: int = 80, session: aiohttp.ClientSession | None = None) -> None:
        self._host = host
        self._port = port
        self._base = f"http://{host}:{port}"
        self._session = session
        self._own_session = session is None
        self._closed = False  # set by close(); no new session afterwards
        self._lock = asyncio.Lock()
        self._last_status: dict = {}
        self._cache_seeded = False  # a full read has run (standby polls are cache-only)
        self._set_post_unsupported = False  # pre-2026 firmware: setData via GET only
        # 2026 firmware: writes (except volume/mute) need an HMAC signature.
        # Built lazily from the device MAC on the first gated (401) write.
        self._auth: KlipschAuth | None = None
        self._auth_failed = False  # no candidate MAC authenticated → stop retrying
        self._auth_required_paths: set[str] = set()  # paths known to need signing
        self._mac_seeds: list[str] = []  # candidate MAC sources (registry/ARP/option)
        self._resolve_warned = False  # "could not resolve write-auth" logged at WARNING once
        # path -> HTTP status of the last real write (None = no answer); diagnostics
        self._last_write_status: dict[str, int | None] = {}
        self.last_response_time: float | None = None  # ms
        self.total_requests: int = 0
        self.failed_requests: int = 0
        # key -> monotonic expiry; values applied optimistically are shielded from
        # a racing full poll until they expire (see note_cached / _apply_optimistic).
        self._optimistic: dict[str, float] = {}
        # Upper bound of player:volume, from the node's ``edit`` metadata.
        self.volume_max: int = VOLUME_MAX_DEFAULT
        self._volume_max_tries = 0  # probes made; capped by VOLUME_MAX_PROBE_TRIES

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._closed:
            # Unloaded: a poll still running must not open a new session that
            # nothing would ever close.
            raise RuntimeError("Klipsch API client is closed")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        self._closed = True
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request_with_retry(
        self,
        request_func: Callable[[], Awaitable[T]],
        retries: int = API_RETRIES,
        delay: float = API_RETRY_DELAY,
    ) -> T:
        """Execute HTTP request with retry on transient errors."""
        for attempt in range(retries + 1):
            try:
                return await request_func()
            except (TimeoutError, aiohttp.ClientError, OSError) as err:
                if attempt == retries:
                    raise
                _LOGGER.debug(
                    "Retry %d/%d after %s: %s",
                    attempt + 1,
                    retries,
                    type(err).__name__,
                    err,
                )
                await asyncio.sleep(delay)

    async def get_data(
        self, path: str, timeout: float = API_TIMEOUT_READ, roles: str = "value", retries: int = API_RETRIES
    ) -> list[dict[str, Any]]:
        """GET /api/getData — serialized via lock."""
        async with self._lock:
            return await self._request_with_retry(lambda: self._do_get_data(path, timeout, roles), retries)

    async def _do_get_data(self, path: str, timeout: float, roles: str = "value") -> list[dict[str, Any]]:
        session = await self._ensure_session()
        url = f"{self._base}/api/getData?path={quote(path, safe=':/')}&roles={roles}"
        t0 = time.monotonic()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                result = await resp.json(content_type=None)
            self.last_response_time = round((time.monotonic() - t0) * 1000, 1)
            self.total_requests += 1
            return result
        except Exception:
            self.failed_requests += 1
            self.total_requests += 1
            raise

    async def set_data(
        self,
        path: str,
        value: dict,
        roles: str = "value",
        timeout: float = API_TIMEOUT_WRITE,
        retries: int = API_RETRIES,
    ) -> str:
        """POST /api/setData — serialized via lock.

        Firmware released in 2026 requires POST with a JSON body; older
        firmware only understands GET with query params, so a rejected POST
        falls back to GET and the working method is remembered.

        ``retries=0`` is for non-idempotent commands (``activate`` media
        controls): a write the device executed but answered too late must not
        be sent again (one tap on "next" would skip twice).
        """
        async with self._lock:
            return await self._request_with_retry(lambda: self._do_set_data(path, value, roles, timeout), retries)

    @staticmethod
    def _rejected_error(path: str, status: int, text: str) -> HomeAssistantError:
        """Error for a write the device answered with HTTP >= 400."""
        return HomeAssistantError(f"Klipsch Flexus: {path} rejected (HTTP {status}): {text[:200]}")

    async def _signed_write(
        self, session: aiohttp.ClientSession, path: str, value: dict, roles: str, timeout: float
    ) -> str:
        """Signed write on behalf of a caller: raise unless the device accepted it."""
        signed = await self._do_signed_set_data(session, path, value, roles, timeout)
        if signed is None:
            self._last_write_status[path] = None
            raise self._write_unavailable_error()
        text, status = signed
        self._last_write_status[path] = status
        if status >= 400:
            # Valid signature (the credential stays cached) but the command itself
            # failed, e.g. a node this model lacks — don't report it as applied.
            raise self._rejected_error(path, status, text)
        return text

    async def _do_set_data(self, path: str, value: dict, roles: str, timeout: float) -> str:
        session = await self._ensure_session()
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        # 2026 firmware: this path was already seen to require signing → sign
        # directly, skipping the doomed unsigned POST (the device is slow).
        if path in self._auth_required_paths:
            return await self._signed_write(session, path, value, roles, timeout)

        post_error: tuple[int, str] | None = None
        if not self._set_post_unsupported:
            payload = {"path": path, "roles": roles, "value": value}
            async with session.post(f"{self._base}/api/setData", json=payload, timeout=client_timeout) as resp:
                status = resp.status
                text = await resp.text()
            if status < 400:
                self._last_write_status[path] = status
                return text
            if status in (401, 403):
                # Write is gated behind an HMAC signature (authMode=setData).
                self._auth_required_paths.add(path)
                return await self._signed_write(session, path, value, roles, timeout)
            # Any other 4xx/5xx may mean pre-2026 (GET-only) firmware — or just a
            # failed command. Try the legacy GET once, but only remember the switch
            # if GET works: 2026 firmware answers GET setData with 405 "Strict HTTP
            # required!", so latching on a stray 5xx would break every later write.
            post_error = (status, text)

        val_str = json.dumps(value, separators=(",", ":"))
        url = f"{self._base}/api/setData?path={quote(path, safe=':/')}&roles={roles}&value={quote(val_str)}"
        async with session.get(url, timeout=client_timeout) as resp:
            get_status = resp.status
            get_text = await resp.text()
        if get_status >= 400:
            if post_error is not None:
                # GET doesn't work either → POST stays the method; report its error.
                self._last_write_status[path] = post_error[0]
                raise self._rejected_error(path, *post_error)
            self._last_write_status[path] = get_status
            if get_status == 405:
                # The firmware now insists on POST ("Strict HTTP required!").
                self._set_post_unsupported = False
            raise self._rejected_error(path, get_status, get_text)
        self._last_write_status[path] = get_status
        if post_error is not None:
            self._set_post_unsupported = True
            _LOGGER.info("setData POST rejected with HTTP %d — falling back to legacy GET", post_error[0])
        return get_text

    @property
    def host(self) -> str:
        return self._host

    def set_mac_seeds(self, seeds: list[str]) -> None:
        """Provide candidate MAC sources for write-auth (registry / ARP / option).

        The coordinator passes whatever MACs Home Assistant knows for the device.
        New seeds reset a failed resolution so it re-runs against them; a resolved
        credential is only dropped if its MAC is no longer among the candidates
        (a flapping seed source must not force a fresh round of signed probes).
        """
        cleaned = [s for s in seeds if s]
        if set(cleaned) != set(self._mac_seeds):
            self._mac_seeds = cleaned
            if self._auth is not None and self._auth.mac not in expand_mac_candidates(cleaned):
                self._auth = None
            self._auth_failed = False

    def _auth_error(self) -> HomeAssistantError:
        """Clear, user-facing error when a gated write cannot be signed."""
        return HomeAssistantError(
            "Klipsch Flexus: this command needs an HMAC signature (2026 firmware), but "
            "the device credential could not be established — no candidate MAC authenticated. "
            "Set the soundbar's MAC in the integration options "
            "(Settings → Devices & Services → Klipsch Flexus → Configure)."
        )

    def _write_unavailable_error(self) -> HomeAssistantError:
        """Error for a gated write that couldn't be signed on this attempt.

        Distinguishes a *permanent* credential failure (no candidate MAC ever
        authenticated → the user must set the MAC) from a *transient* one (the
        device didn't answer the signed write in time). The transient case keeps
        ``_auth_failed`` unset, so the next command re-tries the resolution — and
        the message says so instead of wrongly blaming the credential.
        """
        if self._auth_failed:
            return self._auth_error()
        return HomeAssistantError(
            "Klipsch Flexus: the device did not respond to the signed write in time "
            "(it can be slow, especially when waking from standby). The command was "
            "not confirmed and will be retried on the next attempt."
        )

    async def _resolve_mac_candidates(self) -> list[str]:
        """Ordered MAC candidates to try for the signing credential.

        Seeds come from the coordinator (HA device registry / ARP / manual option)
        plus ``eureka_info`` as a last resort; each is expanded with its last-byte
        neighbours, since a unit's wired and wireless MACs differ by one.
        """
        seeds = list(self._mac_seeds)
        try:
            info = await self.get_device_info()
            if info and info.get("mac_address"):
                seeds.append(info["mac_address"])
        except Exception:  # noqa: BLE001
            pass
        return expand_mac_candidates(seeds)

    @staticmethod
    def _sig_accepted(status: int | None) -> bool:
        """True if the device accepted the signature.

        Only ``401``/``403`` mean a *wrong* credential. Anything else — ``200`` or
        even a ``500`` (valid signature but a wrong body/role) — means the MAC is
        correct, so it resolves the credential.
        """
        return status is not None and status not in (401, 403)

    async def _send_signed(
        self, session: aiohttp.ClientSession, auth: KlipschAuth, path: str, value: dict, roles: str, timeout: float
    ) -> tuple[str | None, int | None]:
        """POST one signed setData; return ``(text, status)`` or ``(None, None)`` on transport error.

        The device serves a self-signed Klipsch-CA certificate, so TLS
        verification is disabled (``ssl=False``) — a LAN device with no public CA,
        exactly like the official app, which trusts Klipsch-CA.
        """
        try:
            body, headers = auth.build_set_data(path, value, role=roles)
            async with session.post(
                auth.set_data_url,
                data=body,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                return await resp.text(), resp.status
        except (TimeoutError, aiohttp.ClientError, OSError) as err:
            _LOGGER.debug("Signed setData transport error: %s", err)
            return None, None

    async def _do_signed_set_data(
        self, session: aiohttp.ClientSession, path: str, value: dict, roles: str, timeout: float
    ) -> tuple[str, int] | None:
        """Sign and send a gated setData, resolving the device MAC by oracle.

        Tries each candidate MAC; the first whose signature the device accepts
        (anything but 401/403) is cached for all future writes. Returns the device
        response ``(text, status)`` — the status may still be >= 400 (valid
        signature, failed command), which callers check — or ``None`` if no
        candidate authenticates (the caller raises a clear error). A cached
        credential is only re-resolved on a real auth rejection (401/403), not on
        other command errors.
        """
        if self._auth is not None:
            # Use the cached credential; transport errors propagate to the retry wrapper.
            body, headers = self._auth.build_set_data(path, value, role=roles)
            async with session.post(
                self._auth.set_data_url,
                data=body,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                text = await resp.text()
                status = resp.status
            if self._sig_accepted(status):
                if status >= 400:
                    _LOGGER.warning("Signed setData %s → HTTP %d: %s", path, status, text[:200])
                return text, status
            _LOGGER.info("Cached Klipsch credential rejected (HTTP %s) — re-resolving MAC", status)
            self._auth = None

        if self._auth_failed:
            return None

        candidates = await self._resolve_mac_candidates()
        if not candidates:
            self._auth_failed = True
            _LOGGER.error(
                "Klipsch: cannot sign writes — no candidate MAC available (eureka_info "
                "reports 00:00:00:00:00:00). Set the device MAC in the integration options."
            )
            return None

        statuses: list[int | None] = []
        for mac in candidates:
            auth = KlipschAuth(mac, self._host)
            text, status = await self._send_signed(session, auth, path, value, roles, timeout)
            if self._sig_accepted(status):
                self._auth = auth
                _LOGGER.info("Klipsch write-auth resolved: MAC %s accepted (HTTP %s)", mac, status)
                self._resolve_warned = False
                if status >= 400:
                    _LOGGER.warning("Signed setData %s → HTTP %d: %s", path, status, text[:200])
                return text, status
            statuses.append(status)

        # Give up permanently only if EVERY candidate was definitively rejected
        # (401/403 = wrong credential). All-timeouts (status None) means the device
        # was slow/unreachable — not that the MAC is wrong — so stay un-failed and
        # let the next command retry.
        if statuses and all(s in (401, 403) for s in statuses):
            self._auth_failed = True
            _LOGGER.error(
                "Klipsch: none of %d candidate MAC(s) authenticated writes %s. "
                "Set the soundbar's MAC in the integration options.",
                len(candidates),
                candidates,
            )
        else:
            # Warn once; repeats (e.g. firmware without the HTTPS endpoint) go to debug.
            _LOGGER.log(
                logging.DEBUG if self._resolve_warned else logging.WARNING,
                "Klipsch: could not resolve write-auth this attempt (device slow/unreachable; "
                "statuses=%s) — will retry on the next command.",
                statuses,
            )
            self._resolve_warned = True
        return None

    async def resolve_write_auth(self) -> bool:
        """Eagerly resolve the signing MAC via an idempotent oracle probe.

        Reads a benign value-role parameter (bass) and writes the same value back
        signed, trying candidates until the device accepts one — so the first real
        command succeeds immediately instead of probing then. No-op: the value
        written equals the value just read. Returns ``True`` if resolved.

        The read and the write-back happen under one lock acquisition, so a
        user's bass change can't land in between and be overwritten with the
        old value.
        """
        if self._auth is not None:
            return True
        if self._auth_failed:
            return False
        path = API_PATHS["bass"]
        async with self._lock:
            try:
                current = await self._do_get_data(path, API_TIMEOUT_READ)
            except Exception:  # noqa: BLE001
                return False
            value = current[0] if current else None
            if value is None:
                return False
            try:
                session = await self._ensure_session()
                await self._do_signed_set_data(session, path, value, "value", API_TIMEOUT_WRITE)
            except (TimeoutError, aiohttp.ClientError, OSError):
                return False
        return self._auth is not None

    @property
    def signing_mac(self) -> str | None:
        """The resolved write-auth MAC (``AA:BB:CC:DD:EE:FF``), or ``None``."""
        return self._auth.mac if self._auth is not None else None

    def signing_info(self) -> dict:
        """Snapshot of the 2026 write-auth state for diagnostics.

        Exposes the resolved signing MAC and the candidate seeds tried. It never
        includes an ``Authorization`` header: a signed header is replayable.
        """
        info: dict = {
            "scheme": AUTH_SCHEME,
            "resolved": self._auth is not None,
            "auth_failed": self._auth_failed,
            "candidate_seeds": list(self._mac_seeds),
            "gated_paths_seen": sorted(self._auth_required_paths),
        }
        if self._auth is not None:
            info["username"] = self._auth.username
            info["signing_mac"] = self._auth.mac
        return info

    async def get_auth_mode(self) -> str:
        """Read settings:/webserver/authMode.

        Firmware from 2026 gates setData behind authentication. Returns one of
        ``none`` (all writes open), ``setData`` (most writes require an
        HMAC-signed request; only volume/mute stay open) or ``all``.
        """
        try:
            data = await self.get_data("settings:/webserver/authMode")
            return data[0].get("webserverAuthMode", "none")
        except Exception:
            return "unknown"

    async def probe_command_health(self) -> dict:
        """Deep diagnostic: report the state of every write command.

        **Read-only.** It used to write each value straight back unsigned, which
        on 2026 firmware labelled every signed-OK command as blocked (401) and
        could revert a change the user made during the slow probe. Now, per
        command, it checks the node is readable and reports what the *real*
        writes this session saw (through the signed path where needed):
        ``http_status`` / ``alive`` of the last write (``None`` = not written
        yet, or no answer) and ``needs_auth`` (the device asked for a signature).
        Nothing is written to the device.
        """
        probes = [
            "volume",
            "mute",
            "input",
            "mode",
            "night",
            "dialog",
            "bass",
            "mid",
            "treble",
            "eq_preset",
            "dirac",
            "sub_wired",
            "sub_wireless",
        ]

        report: dict = {"auth_mode": await self.get_auth_mode(), "probe": "read-only", "commands": {}}

        for key in probes:
            path = API_PATHS[key]
            status = self._last_write_status.get(path)
            entry: dict = {
                "alive": None if status is None else status < 400,
                "http_status": status,
                "needs_auth": path in self._auth_required_paths,
            }
            try:
                current = await self.get_data(path)
                entry["readable"] = bool(current)
                if not current:
                    entry["detail"] = "no value returned"
            except Exception as err:
                entry["readable"] = False
                entry["detail"] = f"read failed: {type(err).__name__}"
            report["commands"][key] = entry

        # Power: read-only probe (no safe idempotent write).
        try:
            power = await self.get_data(API_PATHS["power"])
            target = power[0].get("powerTarget", {}).get("target", "unknown")
            report["commands"]["power"] = {"alive": None, "readable": True, "current_target": target}
        except Exception as err:
            report["commands"]["power"] = {"alive": None, "readable": False, "detail": type(err).__name__}

        return report

    async def get_rows(self, path: str) -> dict:
        """GET /api/getRows — serialized via lock."""
        async with self._lock:
            return await self._request_with_retry(lambda: self._do_get_rows(path))

    async def _do_get_rows(self, path: str) -> dict:
        session = await self._ensure_session()
        url = f"{self._base}/api/getRows?path={quote(path, safe=':/')}&roles=@all&from=0&to=65535&type=structure"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_READ)) as resp:
            return await resp.json(content_type=None)

    # --- Status polling with graceful degradation ---

    async def get_status(self, seed_standby: bool = False) -> dict:
        """Poll device status. Individual failures fall back to last-known values.

        When the soundbar is in standby (networkStandby), only the power state
        is polled — the device is very slow to respond in this mode, so we skip
        all other parameters and keep cached values. This prevents response-time
        spikes (up to 40 s) and sensor unavailability during standby. The one
        exception, with ``seed_standby`` (the coordinator), is the first poll
        after setup, which seeds the empty cache. A one-shot caller such as the
        config flow leaves it off and gets the quick power-only answer.

        If the device stops answering mid-poll (``POLL_MAX_TRANSPORT_ERRORS``
        transport errors in a row), the poll is cut short and reports offline.
        """
        ALL_PARAMS = {
            "volume": (API_PATHS["volume"], lambda d: d[0].get("i32_", 0)),
            "muted": (API_PATHS["mute"], lambda d: d[0].get("bool_", False)),
            "input": (API_PATHS["input"], lambda d: d[0].get("cinemaPhysicalAudioInput", "unknown")),
            "mode": (API_PATHS["mode"], lambda d: d[0].get("cinemaPostProcessorMode", "unknown")),
            "night_mode": (
                API_PATHS["night"],
                lambda d: NIGHT_MODE_FROM_API.get(d[0].get("cinemaNightMode", "off"), "off"),
            ),
            "dialog_mode": (API_PATHS["dialog"], lambda d: d[0].get("cinemaDialogMode", "off")),
            "bass": (API_PATHS["bass"], lambda d: d[0].get("i32_", 0)),
            "mid": (API_PATHS["mid"], lambda d: d[0].get("i32_", 0)),
            "treble": (API_PATHS["treble"], lambda d: d[0].get("i32_", 0)),
            "decoder": (API_PATHS["decoder"], lambda d: d[0].get("cinemaAudioDecoder", "unknown")),
            "eq_preset": (API_PATHS["eq_preset"], lambda d: d[0].get("cinemaEqPreset", "unknown")),
            "dirac": (API_PATHS["dirac"], lambda d: d[0].get("i32_", DIRAC_OFF)),
            "sub_wired": (API_PATHS["sub_wired"], lambda d: d[0].get("i32_", 0)),
            "sub_wireless": (API_PATHS["sub_wireless"], lambda d: d[0].get("i32_", 0)),
            # Surround channel levels
            "back_height": (API_PATHS["back_height"], lambda d: d[0].get("i32_", 0)),
            "back_left": (API_PATHS["back_left"], lambda d: d[0].get("i32_", 0)),
            "back_right": (API_PATHS["back_right"], lambda d: d[0].get("i32_", 0)),
            "front_height": (API_PATHS["front_height"], lambda d: d[0].get("i32_", 0)),
            "side_left": (API_PATHS["side_left"], lambda d: d[0].get("i32_", 0)),
            "side_right": (API_PATHS["side_right"], lambda d: d[0].get("i32_", 0)),
        }

        # Additional settings (toggles / LED / delays / read-only info). Polled
        # only when the device is on; failures here never mark the device offline.
        SETTINGS_PARAMS = {
            "auto_lipsync": (API_PATHS["auto_lipsync"], lambda d: d[0].get("bool_", False)),
            "eq_bypass": (API_PATHS["eq_bypass"], lambda d: d[0].get("bool_", False)),
            "auto_power": (API_PATHS["auto_power"], lambda d: d[0].get("bool_", False)),
            "ui_sounds": (API_PATHS["ui_sounds"], lambda d: d[0].get("bool_", False)),
            "extra_modes": (API_PATHS["extra_modes"], lambda d: d[0].get("bool_", False)),
            "ble_pair": (API_PATHS["ble_pair"], lambda d: d[0].get("bool_", False)),
            "ota_updates": (API_PATHS["ota_updates"], lambda d: d[0].get("bool_", False)),
            "lipsync_delay": (API_PATHS["lipsync_delay"], lambda d: d[0].get("i32_", 0)),
            "sub_wired_delay": (API_PATHS["sub_wired_delay"], lambda d: d[0].get("i64_", 0)),
            "sub_wireless_delay": (API_PATHS["sub_wireless_delay"], lambda d: d[0].get("i64_", 0)),
            "surround_delay": (API_PATHS["surround_delay"], lambda d: d[0].get("i64_", 0)),
            "led_mode": (API_PATHS["led_mode"], lambda d: d[0].get("cinemaLEDMode", "dim")),
            "operating_mode": (API_PATHS["operating_mode"], lambda d: d[0].get("cinemaOperatingMode", "unknown")),
            "speaker_test": (API_PATHS["speaker_test"], lambda d: d[0].get("cinemaSpeakerTestMode", "unknown")),
            # other namespaces (mediaPlayer / system) — writable even in standby
            "balance": (API_PATHS["balance"], lambda d: d[0].get("double_", 0)),
            "loudness": (API_PATHS["loudness"], lambda d: d[0].get("bool_", False)),
            "do_not_disturb": (API_PATHS["do_not_disturb"], lambda d: d[0].get("bool_", False)),
            "auto_standby": (API_PATHS["auto_standby"], lambda d: d[0].get("bool_", False)),
            "idle_timeout": (API_PATHS["idle_timeout"], lambda d: d[0].get("i32_", 0)),
        }

        poll_start = time.monotonic()

        # ── Step 1: probe power state first ──
        try:
            power_data = await self.get_data(API_PATHS["power"])
            power = power_data[0].get("powerTarget", {}).get("target", "unknown")
        except Exception:
            # Cannot reach device at all → offline
            return {"online": False}

        # ── Step 2: standby → return cached data, skip heavy polling ──
        # Except on the first poll after setup: with nothing cached yet every
        # entity would show a made-up default until the bar is turned on, so
        # the cache is seeded once with a full read, then standby stays light.
        keys = (*ALL_PARAMS, *SETTINGS_PARAMS)
        standby = power == "networkStandby"
        if standby and (self._cache_seeded or not seed_standby):
            return self._standby_status(power, poll_start, keys)

        # ── Step 3: device is ON (or the one-off standby seed) → full poll ──
        self._cache_seeded = True
        result = {"online": True, "power": power}
        fail_count = 0
        transport_errors = 0  # consecutive; the device may have dropped mid-poll

        async def read(key: str, path: str, parser: Callable[[Any], Any]) -> bool:
            """Read one parameter into ``result`` (last-known value on failure).

            No retries per parameter: a device that stopped answering is caught
            by the transport-error count instead of ~25 s of retries per key.
            """
            nonlocal transport_errors
            try:
                result[key] = parser(await self.get_data(path, retries=0))
            except Exception as err:
                transport_errors = transport_errors + 1 if isinstance(err, _TRANSPORT_ERRORS) else 0
                cached = self._last_status.get(key)
                if cached is not None:
                    result[key] = cached
                    _LOGGER.debug("Using cached value for %s", key)
                else:
                    _LOGGER.debug("No cached value for %s, skipping", key)
                return False
            transport_errors = 0
            return True

        def offline() -> dict:
            # A standby seed that fails is not "offline": the bar answered the
            # power probe, it is just slow in standby → plain standby result.
            if standby:
                return self._standby_status(power, poll_start, keys)
            return {"online": False}

        for key, (path, parser) in ALL_PARAMS.items():
            if not await read(key, path, parser):
                fail_count += 1
            if transport_errors >= POLL_MAX_TRANSPORT_ERRORS:
                _LOGGER.debug("Device stopped answering mid-poll (at %s) — reporting offline", key)
                return offline()

        # If ALL parameters failed (besides power), device is truly offline
        if fail_count == len(ALL_PARAMS):
            return offline()

        # Settings group — tolerated failures, cached fallback, not offline-counted
        for key, (path, parser) in SETTINGS_PARAMS.items():
            await read(key, path, parser)
            if transport_errors >= POLL_MAX_TRANSPORT_ERRORS:
                _LOGGER.debug("Device stopped answering mid-poll (at %s) — reporting offline", key)
                return offline()

        await self._probe_volume_max()
        result["volume_max"] = self.volume_max

        result["poll_time_ms"] = round((time.monotonic() - poll_start) * 1000)
        result["failed_params"] = fail_count
        # Don't let a poll that races the device applying a just-issued write
        # revert the optimistic value (the standby path already preserves cached
        # values; this does the same for the full poll — see _apply_optimistic).
        self._apply_optimistic(result, poll_start)
        self._last_status = result
        return result

    def _standby_status(self, power: str, poll_start: float, keys: tuple[str, ...]) -> dict:
        """Lightweight standby result: power + every previously known value."""
        result: dict = {"online": True, "power": power, "volume_max": self.volume_max}
        # Preserve all previously known values so sensors stay available
        for key in keys:
            cached = self._last_status.get(key)
            if cached is not None:
                result[key] = cached
        result["poll_time_ms"] = round((time.monotonic() - poll_start) * 1000)
        result["failed_params"] = 0
        self._last_status = result
        _LOGGER.debug("Device in standby — lightweight poll (%d ms)", result["poll_time_ms"])
        return result

    async def _probe_volume_max(self) -> None:
        """Read the volume slider's maximum from the node's ``edit`` metadata.

        ``player:volume`` reports e.g. ``[{"type": "slider", "min": "0",
        "max": "50", "step": "1"}]`` for ``roles=edit``. Done once (a few tries at
        most) on a full poll; anything unexpected keeps :data:`VOLUME_MAX_DEFAULT`.
        """
        if self._volume_max_tries >= VOLUME_MAX_PROBE_TRIES:
            return
        self._volume_max_tries += 1
        try:
            edit = (await self.get_data(API_PATHS["volume"], roles="edit", retries=0))[0]
            value = int(edit["max"])
        except Exception as err:  # noqa: BLE001 — metadata is best-effort
            _LOGGER.debug("Volume range not available (%s), using max %d", err, self.volume_max)
            return
        if 0 < value <= 1000:
            self.volume_max = value
            self._volume_max_tries = VOLUME_MAX_PROBE_TRIES  # done
            _LOGGER.debug("Volume range: 0..%d", value)

    def _apply_optimistic(self, result: dict, poll_start: float) -> None:
        """Override freshly-polled values with still-valid optimistic ones.

        ``note_cached`` records each optimistically-applied value in
        ``_last_status`` and its write time in ``_optimistic``. The optimistic
        value (which the device *will* report, since the write already
        succeeded) wins over a poll that may have read the pre-write value: one
        that started before the write settled (``OPTIMISTIC_SETTLE``), however
        long that poll took — a full poll is ~40 sequential reads, far longer
        than the TTL — and any poll finishing within ``OPTIMISTIC_TTL`` of the
        write. A poll started later reads the applied value, so for it the
        entry expires (external changes aren't masked for long).
        """
        if not self._optimistic:
            return
        now = time.monotonic()
        for key, written in list(self._optimistic.items()):
            if poll_start < written + OPTIMISTIC_SETTLE or now < written + OPTIMISTIC_TTL:
                if key in self._last_status:
                    result[key] = self._last_status[key]
            else:
                del self._optimistic[key]

    def note_cached(self, values: dict) -> None:
        """Record just-applied values in the status cache.

        The standby poll is cache-only (it doesn't re-read settings), so without
        this an optimistic UI update would be reverted to the stale cached value
        on the next poll even though the write succeeded on the device. The write
        time also shields the value from a racing *full* poll (see
        :meth:`_apply_optimistic`).
        """
        if isinstance(self._last_status, dict):
            self._last_status.update(values)
        written = time.monotonic()
        for key in values:
            self._optimistic[key] = written

    # --- Setters ---

    async def set_volume(self, level: int) -> None:
        await self.set_data(API_PATHS["volume"], {"type": "i32_", "i32_": level})

    async def set_mute(self, muted: bool) -> None:
        await self.set_data(API_PATHS["mute"], {"type": "bool_", "bool_": muted})

    async def set_input(self, source: str) -> None:
        await self.set_data(
            API_PATHS["input"],
            {"type": "cinemaPhysicalAudioInput", "cinemaPhysicalAudioInput": source},
        )

    async def set_sound_mode(self, mode: str) -> None:
        await self.set_data(
            API_PATHS["mode"],
            {"type": "cinemaPostProcessorMode", "cinemaPostProcessorMode": mode},
        )

    async def set_night_mode(self, mode: str) -> None:
        api_val = NIGHT_MODE_TO_API.get(mode, mode)
        await self.set_data(
            API_PATHS["night"],
            {"type": "cinemaNightMode", "cinemaNightMode": api_val},
        )

    async def set_dialog_mode(self, mode: str) -> None:
        await self.set_data(
            API_PATHS["dialog"],
            {"type": "cinemaDialogMode", "cinemaDialogMode": mode},
        )

    async def set_channel_level(self, param: str, value: int) -> None:
        """Set any channel level (bass/mid/treble/surround/sub) by key."""
        await self.set_data(API_PATHS[param], {"type": "i32_", "i32_": value})

    # Legacy aliases
    set_eq = set_channel_level
    set_sub = set_channel_level

    async def set_eq_preset(self, preset: str) -> None:
        await self.set_data(
            API_PATHS["eq_preset"],
            {"type": "cinemaEqPreset", "cinemaEqPreset": preset},
        )

    async def set_dirac(self, filter_id: int) -> None:
        await self.set_data(API_PATHS["dirac"], {"type": "i32_", "i32_": filter_id})

    async def set_switch(self, key: str, on: bool) -> None:
        """Toggle a boolean setting (auto-lipsync, EQ bypass, auto-power, …)."""
        await self.set_data(API_PATHS[key], {"type": "bool_", "bool_": on})

    async def set_led_mode(self, mode: str) -> None:
        await self.set_data(API_PATHS["led_mode"], {"type": "cinemaLEDMode", "cinemaLEDMode": mode})

    async def set_number(self, key: str, value: float, vtype: str = "i32_") -> None:
        """Set a typed numeric setting (i32 ms, i64 µs, or double like balance)."""
        await self.set_data(API_PATHS[key], {"type": vtype, vtype: value})

    # Backwards-compatible alias (lip-sync delay was the first such number)
    set_delay = set_number

    async def set_power(self, target: str) -> None:
        await self.set_data(
            API_PATHS["power_req"],
            {"target": target, "reason": "userActivity"},
            roles="activate",
            timeout=API_TIMEOUT_POWER,
        )

    async def get_dirac_filters(self) -> list[dict]:
        data = await self.get_rows("dirac:filters")
        return [{"id": r["value"]["i32_"], "name": r["title"]} for r in data.get("rows", [])]

    async def get_peripherals(self) -> dict[str, Any]:
        """Read ``cinema:peripherals``: which wireless speakers are linked.

        Returns ``{"speakers": {slot: {"connected", "rx", "model"}}, "raw": [...]}``
        for the slots of :data:`SPEAKER_SLOTS` the device lists (an empty slot is
        ``connected=False`` with no model). ``raw`` keeps every group as reported,
        including the unidentified group 3, for diagnostics.
        """
        data = await self.get_data(PERIPHERALS_PATH, retries=0)
        groups = data[0].get("cinemaPeripherals") or []
        by_id = {g.get("id"): g for g in groups if isinstance(g, dict)}
        speakers: dict[str, dict[str, Any]] = {}
        for slot, (group_id, index, _prefix, _model) in SPEAKER_SLOTS.items():
            group = by_id.get(group_id)
            if group is None:
                continue

            def field(name: str, group: dict = group, index: int = index) -> str:
                values = str(group.get(name, "")).split(",")
                return values[index].strip() if index < len(values) else ""

            model = field("m")
            rx = field("ver")
            speakers[slot] = {
                "connected": field("con") == "1",
                "rx": rx if rx not in ("", "0.0") else None,
                "model": model if model not in ("", "0") else None,
            }
        return {"speakers": speakers, "raw": groups}

    async def get_speaker_versions(self, slot: str) -> dict[str, str | None]:
        """Read one speaker's RX / EQ / MCU / HW versions (``hostlink:*``, read-only).

        Unknown or not-yet-reported parts are None.
        """
        prefix = SPEAKER_SLOTS[slot][2]
        versions: dict[str, str | None] = {}
        for key, suffix in SPEAKER_VERSION_NODES.items():
            value = (await self.get_data(f"hostlink:{prefix}{suffix}", retries=0))[0].get("string_")
            # "0.0.0": the radio link is up but the speaker's MCU has not answered
            # yet (seen right after a sub reconnects) — not a real version
            versions[key] = value if value and value != "0.0.0" else None
        return versions

    async def get_bar_versions(self) -> dict[str, str | None]:
        """Read the soundbar's own component versions; unreadable ones are skipped."""
        versions: dict[str, str | None] = {}
        for key, path in BAR_VERSION_PATHS.items():
            try:
                versions[key] = (await self.get_data(path, retries=0))[0].get("string_") or None
            except _TRANSPORT_ERRORS:
                raise  # the device stopped answering: don't wait out every node
            except Exception:  # noqa: BLE001 — best-effort, firmware-dependent nodes
                _LOGGER.debug("Klipsch: %s not readable", path)
        return versions

    async def get_player_data(self) -> dict | None:
        """Fetch current player/media data."""
        try:
            data = await self.get_data(API_PATHS["player"])
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
        except Exception:
            _LOGGER.debug("Failed to get player data")
        return None

    async def media_control(self, control: str) -> None:
        """Send media control command (pause/next/previous)."""
        # Not idempotent (a resent "next" skips twice) → never retried.
        await self.set_data(
            API_PATHS["player_control"],
            {"control": control},
            roles="activate",
            retries=0,
        )

    async def get_device_info(self) -> dict | None:
        """Fetch device info from Google Cast API (port 8008).

        Returns eureka_info with name, mac_address, build_version, uptime, etc.
        Useful for device identification and firmware version display.
        """
        session = await self._ensure_session()
        url = f"http://{self._host}:8008/setup/eureka_info"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
        except Exception:
            _LOGGER.debug("Failed to get eureka_info from port 8008")
        return None
