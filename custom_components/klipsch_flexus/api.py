"""Klipsch Flexus HTTP API client."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from urllib.parse import quote

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .auth import KlipschAuth, expand_mac_candidates
from .const import (
    API_RETRIES,
    API_RETRY_DELAY,
    API_TIMEOUT_POWER,
    API_TIMEOUT_READ,
    API_TIMEOUT_WRITE,
    NIGHT_MODE_FROM_API,
    NIGHT_MODE_TO_API,
)

_LOGGER = logging.getLogger(__name__)


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
        self._lock = asyncio.Lock()
        self._last_status: dict = {}
        self._set_post_unsupported = False  # pre-2026 firmware: setData via GET only
        # 2026 firmware: writes (except volume/mute) need an HMAC signature.
        # Built lazily from the device MAC on the first gated (401) write.
        self._auth: KlipschAuth | None = None
        self._auth_failed = False  # no candidate MAC authenticated → stop retrying
        self._auth_required_paths: set[str] = set()  # paths known to need signing
        self._mac_seeds: list[str] = []  # candidate MAC sources (registry/ARP/option)
        self.last_response_time: float | None = None  # ms
        self.total_requests: int = 0
        self.failed_requests: int = 0

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request_with_retry(
        self,
        request_func,
        retries: int = API_RETRIES,
        delay: float = API_RETRY_DELAY,
    ):
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

    async def get_data(self, path: str, timeout: float = API_TIMEOUT_READ) -> list:
        """GET /api/getData — serialized via lock."""
        async with self._lock:
            return await self._request_with_retry(lambda: self._do_get_data(path, timeout))

    async def _do_get_data(self, path: str, timeout: float) -> list:
        session = await self._ensure_session()
        url = f"{self._base}/api/getData?path={quote(path, safe=':/')}&roles=value"
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
    ) -> str:
        """POST /api/setData — serialized via lock.

        Firmware released in 2026 requires POST with a JSON body; older
        firmware only understands GET with query params, so a rejected POST
        falls back to GET and the working method is remembered.
        """
        async with self._lock:
            return await self._request_with_retry(lambda: self._do_set_data(path, value, roles, timeout))

    async def _do_set_data(self, path: str, value: dict, roles: str, timeout: float) -> str:
        session = await self._ensure_session()
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        # 2026 firmware: this path was already seen to require signing → sign
        # directly, skipping the doomed unsigned POST (the device is slow).
        if path in self._auth_required_paths:
            signed = await self._do_signed_set_data(session, path, value, roles, timeout)
            if signed is not None:
                return signed
            raise self._auth_error()

        if not self._set_post_unsupported:
            payload = {"path": path, "roles": roles, "value": value}
            async with session.post(f"{self._base}/api/setData", json=payload, timeout=client_timeout) as resp:
                status = resp.status
                text = await resp.text()
            if status < 400:
                return text
            if status in (401, 403):
                # Write is gated behind an HMAC signature (authMode=setData).
                self._auth_required_paths.add(path)
                signed = await self._do_signed_set_data(session, path, value, roles, timeout)
                if signed is not None:
                    return signed
                raise self._auth_error()
            # Any other 4xx/5xx → assume pre-2026 (GET-only) firmware.
            self._set_post_unsupported = True
            _LOGGER.info(
                "setData POST rejected with HTTP %d — falling back to legacy GET",
                status,
            )

        val_str = json.dumps(value, separators=(",", ":"))
        url = f"{self._base}/api/setData?path={quote(path, safe=':/')}&roles={roles}&value={quote(val_str)}"
        async with session.get(url, timeout=client_timeout) as resp:
            return await resp.text()

    @property
    def host(self) -> str:
        return self._host

    def set_mac_seeds(self, seeds: list[str]) -> None:
        """Provide candidate MAC sources for write-auth (registry / ARP / option).

        The coordinator passes whatever MACs Home Assistant knows for the device.
        New seeds reset any cached/failed auth so resolution re-runs against them.
        """
        cleaned = [s for s in seeds if s]
        if set(cleaned) != set(self._mac_seeds):
            self._mac_seeds = cleaned
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
    ) -> str | None:
        """Sign and send a gated setData, resolving the device MAC by oracle.

        Tries each candidate MAC; the first whose signature the device accepts
        (anything but 401/403) is cached for all future writes. Returns the device
        response text, or ``None`` if no candidate authenticates (the caller raises
        a clear error). A cached credential is only re-resolved on a real auth
        rejection (401/403), not on other command errors.
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
                return text
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

        for mac in candidates:
            auth = KlipschAuth(mac, self._host)
            text, status = await self._send_signed(session, auth, path, value, roles, timeout)
            if self._sig_accepted(status):
                self._auth = auth
                _LOGGER.info("Klipsch write-auth resolved: MAC %s accepted (HTTP %s)", mac, status)
                if status >= 400:
                    _LOGGER.warning("Signed setData %s → HTTP %d: %s", path, status, text[:200])
                return text

        self._auth_failed = True
        _LOGGER.error(
            "Klipsch: none of %d candidate MAC(s) authenticated writes %s. "
            "Set the soundbar's MAC in the integration options.",
            len(candidates),
            candidates,
        )
        return None

    async def resolve_write_auth(self) -> bool:
        """Eagerly resolve the signing MAC via an idempotent oracle probe.

        Reads a benign value-role parameter (bass) and writes the same value back
        signed, trying candidates until the device accepts one — so the first real
        command succeeds immediately instead of probing then. No-op: the value
        written equals the value just read. Returns ``True`` if resolved.
        """
        from .const import API_PATHS

        if self._auth is not None:
            return True
        if self._auth_failed:
            return False
        path = API_PATHS["bass"]
        try:
            current = await self.get_data(path)
        except Exception:  # noqa: BLE001
            return False
        value = current[0] if current else None
        if value is None:
            return False
        async with self._lock:
            session = await self._ensure_session()
            try:
                await self._do_signed_set_data(session, path, value, "value", API_TIMEOUT_WRITE)
            except (TimeoutError, aiohttp.ClientError, OSError):
                return False
        return self._auth is not None

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
        """Deep diagnostic: report which write commands the firmware accepts.

        For every command path it reads the current value and writes the same
        value straight back — an idempotent no-op — recording the HTTP status.
        ``200`` means the command is alive; ``401`` means the firmware now
        blocks it (auth required). Power is probed read-only since it has no
        safe no-op. Nothing is changed on the device.
        """
        from .const import API_PATHS

        # (key, roles) — only value-roles paths have a safe idempotent write-back.
        probes = [
            ("volume", "value"),
            ("mute", "value"),
            ("input", "value"),
            ("mode", "value"),
            ("night", "value"),
            ("dialog", "value"),
            ("bass", "value"),
            ("mid", "value"),
            ("treble", "value"),
            ("eq_preset", "value"),
            ("dirac", "value"),
            ("sub_wired", "value"),
            ("sub_wireless", "value"),
        ]

        report: dict = {"auth_mode": await self.get_auth_mode(), "commands": {}}

        for key, roles in probes:
            path = API_PATHS[key]
            try:
                current = await self.get_data(path)
                value = current[0] if current else None
            except Exception as err:
                report["commands"][key] = {"alive": False, "detail": f"read failed: {type(err).__name__}"}
                continue
            if value is None:
                report["commands"][key] = {"alive": False, "detail": "no value returned"}
                continue
            status = await self._probe_set_status(path, value, roles)
            report["commands"][key] = {
                "alive": status is not None and status < 400,
                "http_status": status,
                "needs_auth": status in (401, 403),
            }

        # Power: read-only probe (no safe idempotent write).
        try:
            power = await self.get_data(API_PATHS["power"])
            target = power[0].get("powerTarget", {}).get("target", "unknown")
            report["commands"]["power"] = {"alive": None, "readable": True, "current_target": target}
        except Exception as err:
            report["commands"]["power"] = {"alive": None, "readable": False, "detail": type(err).__name__}

        return report

    async def _probe_set_status(self, path: str, value: dict, roles: str) -> int | None:
        """Write a value back and return the HTTP status (no retry, no raise)."""
        async with self._lock:
            try:
                session = await self._ensure_session()
                payload = {"path": path, "roles": roles, "value": value}
                async with session.post(
                    f"{self._base}/api/setData",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_WRITE),
                ) as resp:
                    return resp.status
            except (TimeoutError, aiohttp.ClientError, OSError):
                return None

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

    async def get_status(self) -> dict:
        """Poll device status. Individual failures fall back to last-known values.

        When the soundbar is in standby (networkStandby), only the power state
        is polled — the device is very slow to respond in this mode, so we skip
        all other parameters and keep cached values. This prevents response-time
        spikes (up to 40 s) and sensor unavailability during standby.
        """
        from .const import API_PATHS

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
            "dirac": (API_PATHS["dirac"], lambda d: d[0].get("i32_", -1)),
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

        poll_start = time.monotonic()

        # ── Step 1: probe power state first ──
        try:
            power_data = await self.get_data(API_PATHS["power"])
            power = power_data[0].get("powerTarget", {}).get("target", "unknown")
        except Exception:
            # Cannot reach device at all → offline
            return {"online": False}

        # ── Step 2: standby → return cached data, skip heavy polling ──
        if power == "networkStandby":
            result: dict = {"online": True, "power": power}
            # Preserve all previously known values so sensors stay available
            for key in ALL_PARAMS:
                cached = self._last_status.get(key)
                if cached is not None:
                    result[key] = cached
            result["poll_time_ms"] = round((time.monotonic() - poll_start) * 1000)
            result["failed_params"] = 0
            self._last_status = result
            _LOGGER.debug("Device in standby — lightweight poll (%d ms)", result["poll_time_ms"])
            return result

        # ── Step 3: device is ON → full poll ──
        result = {"online": True, "power": power}
        fail_count = 0

        for key, (path, parser) in ALL_PARAMS.items():
            try:
                data = await self.get_data(path)
                result[key] = parser(data)
            except Exception:
                fail_count += 1
                # Fall back to last-known value
                cached = self._last_status.get(key)
                if cached is not None:
                    result[key] = cached
                    _LOGGER.debug("Using cached value for %s", key)
                else:
                    _LOGGER.debug("No cached value for %s, skipping", key)

        # If ALL parameters failed (besides power), device is truly offline
        if fail_count == len(ALL_PARAMS):
            return {"online": False}

        result["poll_time_ms"] = round((time.monotonic() - poll_start) * 1000)
        result["failed_params"] = fail_count
        self._last_status = result
        return result

    # --- Setters ---

    async def set_volume(self, level: int) -> None:
        from .const import API_PATHS

        await self.set_data(API_PATHS["volume"], {"type": "i32_", "i32_": level})

    async def set_mute(self, muted: bool) -> None:
        from .const import API_PATHS

        await self.set_data(API_PATHS["mute"], {"type": "bool_", "bool_": muted})

    async def set_input(self, source: str) -> None:
        from .const import API_PATHS

        await self.set_data(
            API_PATHS["input"],
            {"type": "cinemaPhysicalAudioInput", "cinemaPhysicalAudioInput": source},
        )

    async def set_sound_mode(self, mode: str) -> None:
        from .const import API_PATHS

        await self.set_data(
            API_PATHS["mode"],
            {"type": "cinemaPostProcessorMode", "cinemaPostProcessorMode": mode},
        )

    async def set_night_mode(self, mode: str) -> None:
        from .const import API_PATHS

        api_val = NIGHT_MODE_TO_API.get(mode, mode)
        await self.set_data(
            API_PATHS["night"],
            {"type": "cinemaNightMode", "cinemaNightMode": api_val},
        )

    async def set_dialog_mode(self, mode: str) -> None:
        from .const import API_PATHS

        await self.set_data(
            API_PATHS["dialog"],
            {"type": "cinemaDialogMode", "cinemaDialogMode": mode},
        )

    async def set_channel_level(self, param: str, value: int) -> None:
        """Set any channel level (bass/mid/treble/surround/sub) by key."""
        from .const import API_PATHS

        await self.set_data(API_PATHS[param], {"type": "i32_", "i32_": value})

    # Legacy aliases
    set_eq = set_channel_level
    set_sub = set_channel_level

    async def set_eq_preset(self, preset: str) -> None:
        from .const import API_PATHS

        await self.set_data(
            API_PATHS["eq_preset"],
            {"type": "cinemaEqPreset", "cinemaEqPreset": preset},
        )

    async def set_dirac(self, filter_id: int) -> None:
        from .const import API_PATHS

        await self.set_data(API_PATHS["dirac"], {"type": "i32_", "i32_": filter_id})

    async def set_power(self, target: str) -> None:
        from .const import API_PATHS

        await self.set_data(
            API_PATHS["power_req"],
            {"target": target, "reason": "userActivity"},
            roles="activate",
            timeout=API_TIMEOUT_POWER,
        )

    async def get_dirac_filters(self) -> list[dict]:
        data = await self.get_rows("dirac:filters")
        return [{"id": r["value"]["i32_"], "name": r["title"]} for r in data.get("rows", [])]

    async def get_player_data(self) -> dict | None:
        """Fetch current player/media data."""
        from .const import API_PATHS

        try:
            data = await self.get_data(API_PATHS["player"])
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
        except Exception:
            _LOGGER.debug("Failed to get player data")
        return None

    async def media_control(self, control: str) -> None:
        """Send media control command (pause/next/previous)."""
        from .const import API_PATHS

        await self.set_data(
            API_PATHS["player_control"],
            {"control": control},
            roles="activate",
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
