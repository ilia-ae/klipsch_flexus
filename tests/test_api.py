"""Tests for Klipsch Flexus API client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.klipsch_flexus.api import KlipschAPI


@pytest.fixture
def api():
    """Create an API client with mocked session."""
    return KlipschAPI("192.168.1.100")


async def test_get_data_success(api: KlipschAPI) -> None:
    """Test successful getData call."""
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=[{"i32_": 25}])
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False

    result = await api.get_data("player:volume")
    assert result == [{"i32_": 25}]
    assert api.total_requests == 1
    assert api.failed_requests == 0
    assert api.last_response_time is not None


async def test_get_data_retry_on_timeout(api: KlipschAPI) -> None:
    """Test retry logic on timeout."""
    call_count = 0

    def mock_get(*args, **kwargs):
        # aiohttp's session.get is sync and returns an async context manager,
        # so this mock must be a plain function (not async def).
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TimeoutError()
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=[{"i32_": 10}])
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        return mock_resp

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.get = mock_get
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False

    result = await api.get_data("player:volume")
    assert result == [{"i32_": 10}]
    assert call_count == 3  # 2 retries + 1 success


async def test_get_data_all_retries_fail(api: KlipschAPI) -> None:
    """Test that exception is raised after all retries fail."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.get = MagicMock(side_effect=TimeoutError())
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False

    with pytest.raises(TimeoutError):
        await api.get_data("player:volume")


async def test_get_status_graceful_degradation(api: KlipschAPI) -> None:
    """Test graceful degradation when some params fail."""
    call_count = 0

    async def mock_get_data(path, timeout=8, **_):
        nonlocal call_count
        call_count += 1
        if "volume" in path:
            return [{"i32_": 50}]
        if "mute" in path:
            return [{"bool_": False}]
        if "powerTarget" in path or "powermanager" in path:
            return [{"powerTarget": {"target": "on"}}]
        # Fail for everything else — with a device answer (bad payload), not a
        # transport error (consecutive ones abort the poll; tested below)
        raise ValueError("unexpected payload")

    api.get_data = mock_get_data
    result = await api.get_status()

    # Should still be online since not ALL params failed
    assert result["online"] is True
    assert result["volume"] == 50


async def test_get_status_aborts_when_device_drops_mid_poll(api: KlipschAPI) -> None:
    """The device answering power, then timing out twice in a row → offline at
    once (not ~25 s of retries for every remaining key)."""
    calls: list[tuple[str, dict]] = []

    async def mock_get_data(path, timeout=8, **kwargs):
        calls.append((path, kwargs))
        if "powermanager" in path:
            return [{"powerTarget": {"target": "online"}}]
        raise TimeoutError()

    api.get_data = mock_get_data
    result = await api.get_status()

    assert result == {"online": False}
    assert len(calls) == 3  # power + 2 parameters, then the poll stops
    assert calls[0][1].get("retries") is None  # the power probe keeps its retries
    assert calls[1][1]["retries"] == 0  # per-parameter reads are not retried


async def test_get_status_isolated_timeouts_stay_online(api: KlipschAPI) -> None:
    """Single (non-consecutive) timeouts fall back to cached values and keep going."""
    seen = 0

    async def mock_get_data(path, timeout=8, **_):
        nonlocal seen
        if "powermanager" in path:
            return [{"powerTarget": {"target": "online"}}]
        seen += 1
        if seen % 2:
            raise TimeoutError()
        return [{"i32_": 1, "bool_": True}]

    api.get_data = mock_get_data
    api._last_status = {"volume": 30}
    result = await api.get_status()

    assert result["online"] is True
    assert result["volume"] == 30  # first read timed out → cached value kept
    assert result["failed_params"] == 10


async def test_get_status_all_fail(api: KlipschAPI) -> None:
    """Test offline status when all params fail."""
    api.get_data = AsyncMock(side_effect=TimeoutError())
    result = await api.get_status()
    assert result == {"online": False}


async def test_get_status_standby_lightweight_poll(api: KlipschAPI) -> None:
    """Test that standby mode only polls power and returns cached data."""
    call_count = 0
    call_paths: list[str] = []

    # Pre-populate cache with some values (as if device was ON before)
    api._last_status = {
        "volume": 30,
        "muted": False,
        "input": "hdmiarc",
        "mode": "movie",
    }
    api._cache_seeded = True

    async def mock_get_data(path, timeout=8, **_):
        nonlocal call_count
        call_count += 1
        call_paths.append(path)
        if "powermanager" in path:
            return [{"powerTarget": {"target": "networkStandby"}}]
        # If we get here, the test should fail — standby should NOT poll other params
        raise AssertionError(f"Unexpected poll in standby mode: {path}")

    api.get_data = mock_get_data
    result = await api.get_status()

    # Only power was polled
    assert call_count == 1
    assert "powermanager" in call_paths[0]

    # Device is online in standby
    assert result["online"] is True
    assert result["power"] == "networkStandby"
    assert result["failed_params"] == 0

    # Cached values preserved
    assert result["volume"] == 30
    assert result["input"] == "hdmiarc"
    assert result["mode"] == "movie"

    # Response time should be fast (< 1 second)
    assert result["poll_time_ms"] < 1000


async def test_get_status_standby_first_poll_seeds_cache(api: KlipschAPI) -> None:
    """First poll after setup in standby (empty cache): one full read seeds the
    cache, then polling goes back to the lightweight power-only probe."""
    paths: list[str] = []

    async def mock_get_data(path, timeout=8, **_):
        paths.append(path)
        if "powermanager" in path:
            return [{"powerTarget": {"target": "networkStandby"}}]
        if path == "cinema:/external/physicalAudioInput":
            raise ValueError("no answer for this key")
        return [{"i32_": 21, "bool_": True, "cinemaLEDMode": "bright"}]

    api.get_data = mock_get_data
    result = await api.get_status()

    assert result["online"] is True
    assert result["power"] == "networkStandby"
    assert result["volume"] == 21
    assert result["eq_bypass"] is True  # settings group seeded too
    assert result["led_mode"] == "bright"
    assert "input" not in result  # never read → stays absent (unknown), no default

    paths.clear()
    second = await api.get_status()
    assert paths == ["powermanager:target"]  # back to the lightweight poll
    assert second["volume"] == 21  # seeded value carried by the cache


async def test_get_status_standby_seed_failure_is_not_offline(api: KlipschAPI) -> None:
    """A standby seed read that times out still reports online/standby (the bar
    answered the power probe) and is not retried on every standby poll."""
    paths: list[str] = []

    async def mock_get_data(path, timeout=8, **_):
        paths.append(path)
        if "powermanager" in path:
            return [{"powerTarget": {"target": "networkStandby"}}]
        raise TimeoutError()

    api.get_data = mock_get_data
    result = await api.get_status()

    assert result["online"] is True
    assert result["power"] == "networkStandby"
    assert "volume" not in result

    paths.clear()
    await api.get_status()
    assert paths == ["powermanager:target"]


async def test_get_status_power_fail_means_offline(api: KlipschAPI) -> None:
    """Test that power query failure immediately returns offline."""
    call_count = 0

    async def mock_get_data(path, timeout=8, **_):
        nonlocal call_count
        call_count += 1
        raise TimeoutError()

    api.get_data = mock_get_data
    result = await api.get_status()

    assert result == {"online": False}
    # Only power was attempted (no further params polled)
    assert call_count == 1


def _mock_response(status: int = 200, text: str = "OK") -> AsyncMock:
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


async def test_set_data_uses_post_json(api: KlipschAPI) -> None:
    """Test that setData sends POST with JSON body (2026+ firmware)."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(return_value=_mock_response())
    mock_session.get = MagicMock(return_value=_mock_response())
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False

    result = await api.set_data("player:volume", {"type": "i32_", "i32_": 25})

    assert result == "OK"
    mock_session.post.assert_called_once()
    args, kwargs = mock_session.post.call_args
    assert args[0] == "http://192.168.1.100:80/api/setData"
    assert kwargs["json"] == {
        "path": "player:volume",
        "roles": "value",
        "value": {"type": "i32_", "i32_": 25},
    }
    mock_session.get.assert_not_called()


async def test_set_data_falls_back_to_get(api: KlipschAPI) -> None:
    """Test fallback to legacy GET when POST is rejected (old firmware)."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(return_value=_mock_response(status=405))
    mock_session.get = MagicMock(return_value=_mock_response(text="LEGACY"))
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False

    result = await api.set_data("player:volume", {"type": "i32_", "i32_": 25})

    assert result == "LEGACY"
    mock_session.post.assert_called_once()
    mock_session.get.assert_called_once()
    url = mock_session.get.call_args[0][0]
    assert url.startswith("http://192.168.1.100:80/api/setData?path=player:volume")

    # Subsequent calls go straight to GET — POST is remembered as unsupported
    await api.set_data("player:volume", {"type": "i32_", "i32_": 30})
    mock_session.post.assert_called_once()
    assert mock_session.get.call_count == 2


def _mock_session(post, get) -> AsyncMock:
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(side_effect=post) if isinstance(post, list) else MagicMock(return_value=post)
    session.get = MagicMock(side_effect=get) if isinstance(get, list) else MagicMock(return_value=get)
    session.closed = False
    return session


async def test_set_data_5xx_with_strict_get_keeps_post(api: KlipschAPI) -> None:
    """2026 firmware: a stray POST 500 must not latch the legacy GET form.

    The GET answers 405 "Strict HTTP required!", so POST stays the method and
    the caller gets an error instead of a silent success.
    """
    from homeassistant.exceptions import HomeAssistantError

    api._session = _mock_session(
        [_mock_response(status=500, text="busy"), _mock_response(text="OK")],
        _mock_response(status=405, text="Strict HTTP required!"),
    )
    api._own_session = False

    with pytest.raises(HomeAssistantError, match=r"HTTP 500.*busy"):
        await api.set_data("player:volume", {"type": "i32_", "i32_": 25})
    assert api._set_post_unsupported is False

    # The next write uses POST again and succeeds.
    assert await api.set_data("player:volume", {"type": "i32_", "i32_": 26}) == "OK"
    assert api._session.post.call_count == 2
    assert api._session.get.call_count == 1


async def test_set_data_legacy_get_error_raises(api: KlipschAPI) -> None:
    """A failing legacy GET is an error, not a success (its status is checked)."""
    from homeassistant.exceptions import HomeAssistantError

    api._set_post_unsupported = True  # GET-only firmware already detected
    api._session = _mock_session(_mock_response(), _mock_response(status=500, text="invalidPath"))
    api._own_session = False

    with pytest.raises(HomeAssistantError, match=r"HTTP 500.*invalidPath"):
        await api.set_data("settings:/cinema/ledMode", {"type": "cinemaLEDMode", "cinemaLEDMode": "dim"})
    api._session.post.assert_not_called()
    assert api._set_post_unsupported is True  # a 500 is a command error, not a method change

    # A 405 "Strict HTTP required!" means the firmware now wants POST → switch back.
    api._session.get = MagicMock(return_value=_mock_response(status=405, text="Strict HTTP required!"))
    with pytest.raises(HomeAssistantError, match="HTTP 405"):
        await api.set_volume(20)
    assert api._set_post_unsupported is False


async def test_set_data_signed_5xx_raises_but_keeps_credential(api: KlipschAPI) -> None:
    """A cached-credential write answered with 500 raises to the caller; the
    credential stays cached (only 401/403 mean a wrong MAC)."""
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.klipsch_flexus.auth import KlipschAuth

    api._auth = KlipschAuth("AA:BB:CC:DD:EE:FF", "192.168.1.100")
    api._auth_required_paths.add("dirac:/activeFilter")
    api._session = _mock_session(_mock_response(status=500, text="bad filter"), _mock_response())
    api._own_session = False

    with pytest.raises(HomeAssistantError, match=r"dirac:/activeFilter rejected \(HTTP 500\)"):
        await api.set_dirac(99)
    assert api.signing_mac == "AA:BB:CC:DD:EE:FF"
    assert api._session.post.call_count == 1  # HTTP errors are not retried


async def test_media_control_is_not_retried(api: KlipschAPI) -> None:
    """'next' is not idempotent: a timeout must not resend it (double skip)."""
    api._session = _mock_session([TimeoutError(), _mock_response()], _mock_response())
    api._own_session = False

    with pytest.raises(TimeoutError):
        await api.media_control("next")
    assert api._session.post.call_count == 1


async def test_value_write_still_retried(api: KlipschAPI) -> None:
    """Idempotent value writes keep the transient-error retry."""
    api._session = _mock_session([TimeoutError(), _mock_response(text="OK")], _mock_response())
    api._own_session = False

    await api.set_volume(20)
    assert api._session.post.call_count == 2


async def test_set_data_signs_on_401(api: KlipschAPI) -> None:
    """2026 firmware: a gated write (401) is retried HMAC-signed over HTTPS."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(side_effect=[_mock_response(status=401, text="Forbidden"), _mock_response(text="OK")])
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    # MAC for credential derivation comes from eureka_info (port 8008).
    api.get_device_info = AsyncMock(return_value={"mac_address": "AA:BB:CC:DD:EE:FF"})

    result = await api.set_data(
        "settings:/cinema/dialogMode",
        {"type": "cinemaDialogMode", "cinemaDialogMode": "dialog_2"},
    )

    assert result == "OK"
    assert mock_session.post.call_count == 2
    # 1st: unsigned POST on http:80
    assert mock_session.post.call_args_list[0].args[0] == "http://192.168.1.100:80/api/setData"
    # 2nd: signed POST on https:443, TLS verification off, Authorization present
    second = mock_session.post.call_args_list[1]
    assert second.args[0] == "https://192.168.1.100/api/setData"
    assert second.kwargs["ssl"] is False
    assert second.kwargs["headers"]["Authorization"].startswith("HMAC_SHA256_AES256 ")

    # Path is now remembered as gated → next write signs directly (single POST).
    mock_session.post.reset_mock()
    mock_session.post.side_effect = [_mock_response(text="OK2")]
    result2 = await api.set_data(
        "settings:/cinema/dialogMode",
        {"type": "cinemaDialogMode", "cinemaDialogMode": "off"},
    )
    assert result2 == "OK2"
    assert mock_session.post.call_count == 1
    assert mock_session.post.call_args.args[0] == "https://192.168.1.100/api/setData"


async def test_set_data_oracle_resolves_sibling_mac(api: KlipschAPI) -> None:
    """Auto-detect: the discovered MAC 401s, its sibling authenticates → cached."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    # unsigned 401 → signed with first candidate (…3E) 401 → sibling (…3D) 200
    mock_session.post = MagicMock(
        side_effect=[
            _mock_response(status=401, text="Forbidden"),
            _mock_response(status=401, text="Forbidden"),
            _mock_response(text="OK"),
        ]
    )
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    api.get_device_info = AsyncMock(return_value=None)
    api.set_mac_seeds(["AA:BB:CC:DD:EE:FE"])  # only the wireless MAC is known

    result = await api.set_data(
        "settings:/cinema/dialogMode",
        {"type": "cinemaDialogMode", "cinemaDialogMode": "dialog_2"},
    )
    assert result == "OK"
    assert mock_session.post.call_count == 3  # unsigned + 2 signed candidates
    assert api._auth is not None  # working MAC cached

    # Cached → next gated write is a single signed POST, no re-probing.
    mock_session.post.reset_mock()
    mock_session.post.side_effect = [_mock_response(text="OK2")]
    result2 = await api.set_data(
        "settings:/cinema/dialogMode",
        {"type": "cinemaDialogMode", "cinemaDialogMode": "off"},
    )
    assert result2 == "OK2"
    assert mock_session.post.call_count == 1


async def test_set_data_activate_role_and_500_resolves_mac(api: KlipschAPI) -> None:
    """Power write: role is threaded as 'activate', and a 500 (valid signature,
    wrong body) still resolves the MAC — only 401/403 means a wrong credential."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(
        side_effect=[
            _mock_response(status=401, text="Forbidden"),  # unsigned :80
            _mock_response(status=401, text="Forbidden"),  # signed …3E (wrong MAC)
            _mock_response(status=500, text="node error"),  # signed …3D (right MAC, body 500)
        ]
    )
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    api.get_device_info = AsyncMock(return_value=None)
    api.set_mac_seeds(["AA:BB:CC:DD:EE:FE"])

    from homeassistant.exceptions import HomeAssistantError

    with pytest.raises(HomeAssistantError, match=r"HTTP 500.*node error"):
        await api.set_data("powermanager:targetRequest", {"target": "on", "reason": "userActivity"}, roles="activate")
    assert api._auth is not None  # but the MAC was resolved (500 ≠ 401)
    # the signed body carried role="activate" (3rd POST = winning candidate)
    signed = mock_session.post.call_args_list[2]
    assert json.loads(signed.kwargs["data"])["role"] == "activate"


async def test_set_data_raises_clear_error_when_no_mac_authenticates(api: KlipschAPI) -> None:
    """No candidate MAC works → a clear HomeAssistantError (not 'unknown error')."""
    from homeassistant.exceptions import HomeAssistantError

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(return_value=_mock_response(status=401, text="Forbidden"))
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    api.get_device_info = AsyncMock(return_value=None)  # no MAC anywhere

    with pytest.raises(HomeAssistantError, match="HMAC signature"):
        await api.set_data(
            "settings:/cinema/dialogMode",
            {"type": "cinemaDialogMode", "cinemaDialogMode": "dialog_2"},
        )
    assert api._auth_failed is True


async def test_set_data_timeouts_do_not_latch_auth_failed(api: KlipschAPI) -> None:
    """All candidate probes timing out (device slow) is transient, not 'wrong MAC'.

    The signer must NOT permanently latch _auth_failed on transport timeouts —
    only on definitive 401/403 — so a later command retries once the bar responds.
    """
    from homeassistant.exceptions import HomeAssistantError

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    # unsigned :80 → 401; every signed candidate then times out (transport error)
    mock_session.post = MagicMock(side_effect=[_mock_response(status=401, text="Forbidden"), *([TimeoutError()] * 8)])
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    api.get_device_info = AsyncMock(return_value=None)
    api.set_mac_seeds(["AA:BB:CC:DD:EE:FE"])

    with pytest.raises(HomeAssistantError):
        await api.set_data("settings:/cinema/dialogMode", {"type": "cinemaDialogMode", "cinemaDialogMode": "off"})
    # transient — stays un-latched so the next command can resolve
    assert api._auth_failed is False
    assert api._auth is None


async def test_probe_command_health(api: KlipschAPI) -> None:
    """Test deep diagnostic: alive vs auth-blocked commands (2026 firmware)."""

    async def mock_get_data(path, timeout=8, **_):
        if "authMode" in path:
            return [{"type": "webserverAuthMode", "webserverAuthMode": "setData"}]
        if "powermanager" in path:
            return [{"powerTarget": {"target": "online"}}]
        return [{"type": "i32_", "i32_": 0}]

    async def mock_probe_set_status(path, value, roles):
        # Firmware keeps volume/mute open, blocks everything else with 401.
        if path in ("player:volume", "settings:/mediaPlayer/mute"):
            return 200
        return 401

    api.get_data = mock_get_data
    api._probe_set_status = mock_probe_set_status

    report = await api.probe_command_health()

    assert report["auth_mode"] == "setData"
    assert report["commands"]["volume"]["alive"] is True
    assert report["commands"]["mute"]["alive"] is True
    assert report["commands"]["bass"]["alive"] is False
    assert report["commands"]["bass"]["needs_auth"] is True
    assert report["commands"]["dirac"]["http_status"] == 401
    # Power is probed read-only (no safe no-op write)
    assert report["commands"]["power"]["readable"] is True
    assert report["commands"]["power"]["current_target"] == "online"


async def test_close_session(api: KlipschAPI) -> None:
    """Test session cleanup."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.closed = False
    api._session = mock_session
    api._own_session = True

    await api.close()
    mock_session.close.assert_called_once()


async def test_new_setters_payload_shapes(api: KlipschAPI) -> None:
    """Switch / LED / delay setters build the correct setData payloads."""
    calls: list[tuple] = []

    async def fake_set_data(path, value, role="value"):
        calls.append((path, value))
        return "OK"

    api.set_data = fake_set_data  # type: ignore[assignment]

    await api.set_switch("eq_bypass", True)
    await api.set_switch("ota_updates", False)
    await api.set_led_mode("bright")
    await api.set_delay("lipsync_delay", 40, "i32_")

    assert calls == [
        ("settings:/cinema/eqBypass", {"type": "bool_", "bool_": True}),
        ("settings:/cinema/otaUpdateEnabled", {"type": "bool_", "bool_": False}),
        ("settings:/cinema/ledMode", {"type": "cinemaLEDMode", "cinemaLEDMode": "bright"}),
        ("settings:/cinema/dsp/manualLipSyncDelay", {"type": "i32_", "i32_": 40}),
    ]


async def test_get_status_includes_settings_group(api: KlipschAPI) -> None:
    """When the device is on, the settings group (switches/LED/info) is polled."""

    def value_for(path: str, **_):
        if path.endswith("powermanager:target") or "powermanager" in path:
            return [{"powerTarget": {"target": "online"}}]
        if path.endswith("ledMode"):
            return [{"type": "cinemaLEDMode", "cinemaLEDMode": "dim"}]
        if path.endswith("eqBypass"):
            return [{"type": "bool_", "bool_": True}]
        if path.endswith("manualLipSyncDelay"):
            return [{"type": "i32_", "i32_": 0}]
        if path.endswith("wiredSubwooferDelay"):
            return [{"type": "i64_", "i64_": 8300}]
        if path.endswith("operatingMode"):
            return [{"type": "cinemaOperatingMode", "cinemaOperatingMode": "consumer"}]
        return [{"i32_": 0, "bool_": False}]

    api.get_data = AsyncMock(side_effect=value_for)
    status = await api.get_status()

    assert status["online"] is True
    assert status["led_mode"] == "dim"
    assert status["eq_bypass"] is True
    assert status["sub_wired_delay"] == 8300
    assert status["operating_mode"] == "consumer"


async def test_note_cached_survives_standby_poll(api: KlipschAPI) -> None:
    """A value applied while the bar is in standby must not be reverted by the
    cache-only standby poll (regression: optimistic write getting clobbered)."""
    api._last_status = {"mode": "movie", "led_mode": "dim"}
    api._cache_seeded = True  # seen ON before → no seeding read
    # Device reports standby → get_status takes the cache-only branch
    api.get_data = AsyncMock(return_value=[{"powerTarget": {"target": "networkStandby"}}])

    st = await api.get_status()
    assert st["power"] == "networkStandby"
    assert st["mode"] == "movie"  # served from cache

    # A successful write records the new value in the status cache...
    api.note_cached({"mode": "music"})
    st2 = await api.get_status()
    assert st2["mode"] == "music"  # ...and it sticks across the standby poll


def _on_value_for(volume: int = 40):
    """get_data stub for an ON device: power 'on', a given volume, neutral rest."""

    def value_for(path: str, timeout: float = 8, **_):
        if "powermanager" in path:
            return [{"powerTarget": {"target": "online"}}]
        if path.endswith("player:volume"):
            return [{"i32_": volume}]
        # Neutral payload — numeric parsers read i32_/bool_/double_/i64_, enum
        # parsers fall back to their own defaults for the missing keys.
        return [{"i32_": 0, "bool_": False, "double_": 0, "i64_": 0}]

    return value_for


async def test_optimistic_value_survives_racing_full_poll(api: KlipschAPI) -> None:
    """A just-applied value must not be reverted by an ON-path poll that races the
    device actually applying the write (the poll still reads the pre-write value)."""
    api.get_data = AsyncMock(side_effect=_on_value_for(volume=40))  # device still reports 40

    api.note_cached({"volume": 50})  # optimistic write succeeded → recorded
    status = await api.get_status()

    assert status["power"] == "online"
    assert status["volume"] == 50  # optimistic value wins over the stale poll


async def test_optimistic_value_expires(api: KlipschAPI) -> None:
    """Once the optimistic window lapses, the polled device value takes over again
    (so an external change is not masked indefinitely)."""
    api.get_data = AsyncMock(side_effect=_on_value_for(volume=40))

    api.note_cached({"volume": 50})
    api._optimistic["volume"] -= 60  # written a minute ago (settled and expired)
    status = await api.get_status()

    assert status["volume"] == 40  # device value, optimistic override dropped
    assert "volume" not in api._optimistic


class _Clock:
    """Controllable stand-in for ``time.monotonic`` in the api module."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


async def test_optimistic_value_survives_slow_poll_started_before_write(api: KlipschAPI, monkeypatch) -> None:
    """A full poll that read the key *before* the write, and finishes long after
    the TTL (real polls take 20-40 s), must not publish the stale value."""
    from custom_components.klipsch_flexus import api as api_mod

    clock = _Clock()
    monkeypatch.setattr(api_mod, "time", clock)
    base = _on_value_for(volume=40)

    def slow_device(path: str, **kwargs):
        if path == "player:volume" and kwargs.get("roles", "value") == "value":
            out = base(path)  # the poll reads volume=40 ...
            clock.now += 1
            api.note_cached({"volume": 50})  # ... then the user's write lands
            return out
        clock.now += 1  # every further read takes a second
        return base(path)

    api.get_data = AsyncMock(side_effect=slow_device)
    status = await api.get_status()

    assert clock.now - api._optimistic["volume"] > 30  # far past the 5 s TTL
    assert status["volume"] == 50  # still the written value, not the stale read

    # A poll that starts after the write settled has the last word (device = 40,
    # e.g. changed on the remote), and the entry expires.
    api.get_data = AsyncMock(side_effect=lambda path, **kw: base(path))
    assert (await api.get_status())["volume"] == 40
    assert "volume" not in api._optimistic


async def test_optimistic_value_kept_for_poll_started_just_after_write(api: KlipschAPI, monkeypatch) -> None:
    """The confirming refresh ~1 s after a write may still read the old value."""
    from custom_components.klipsch_flexus import api as api_mod

    clock = _Clock()
    monkeypatch.setattr(api_mod, "time", clock)
    api.note_cached({"volume": 50})
    clock.now += 1.0  # COMMAND_REFRESH_DELAY

    def slow(path: str, **kwargs):
        clock.now += 1  # the poll then runs ~40 s
        return _on_value_for(volume=40)(path)

    api.get_data = AsyncMock(side_effect=slow)
    assert (await api.get_status())["volume"] == 50


async def test_cached_credential_re_resolves_on_401(api: KlipschAPI) -> None:
    """A cached signing MAC that the device later rejects (401) is re-resolved
    against the candidates instead of failing the command outright."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    api.get_device_info = AsyncMock(return_value=None)
    api.set_mac_seeds(["AA:BB:CC:DD:EE:FE"])  # candidates: FE, FD, FF, FC, …

    # First gated write resolves + caches the …FE credential.
    mock_session.post = MagicMock(side_effect=[_mock_response(status=401), _mock_response(text="OK")])
    await api.set_data("settings:/cinema/dialogMode", {"type": "cinemaDialogMode", "cinemaDialogMode": "dialog_2"})
    assert api.signing_mac == "AA:BB:CC:DD:EE:FE"

    # Next write: the cached …FE is now rejected (401) → re-probe → …FD authenticates.
    mock_session.post.reset_mock()
    mock_session.post.side_effect = [
        _mock_response(status=401),  # cached …FE rejected
        _mock_response(status=401),  # candidate …FE rejected again
        _mock_response(text="OK2"),  # candidate …FD accepted
    ]
    result = await api.set_data("settings:/cinema/dialogMode", {"type": "cinemaDialogMode", "cinemaDialogMode": "off"})
    assert result == "OK2"
    assert api.signing_mac == "AA:BB:CC:DD:EE:FD"  # credential re-resolved


async def test_transient_timeout_reports_retryable_message(api: KlipschAPI) -> None:
    """All signed probes timing out yields a 'device slow, will retry' message —
    not the 'set your MAC' credential error — and does not latch auth-failed."""
    from homeassistant.exceptions import HomeAssistantError

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = MagicMock(side_effect=[_mock_response(status=401), *([TimeoutError()] * 8)])
    mock_session.closed = False
    api._session = mock_session
    api._own_session = False
    api.get_device_info = AsyncMock(return_value=None)
    api.set_mac_seeds(["AA:BB:CC:DD:EE:FE"])

    with pytest.raises(HomeAssistantError, match="did not respond"):
        await api.set_data("settings:/cinema/dialogMode", {"type": "cinemaDialogMode", "cinemaDialogMode": "off"})
    assert api._auth_failed is False  # transient → next command retries


async def test_night_mode_conversion_roundtrips() -> None:
    """UI ↔ API night-mode mapping is consistent and defaults safely."""
    from custom_components.klipsch_flexus.const import NIGHT_MODE_FROM_API, NIGHT_MODE_TO_API

    assert NIGHT_MODE_TO_API["night_mode_1"] == "nightMode_1"
    assert NIGHT_MODE_FROM_API["nightMode_1"] == "night_mode_1"
    for ui in ("off", "night_mode_1"):
        assert NIGHT_MODE_FROM_API[NIGHT_MODE_TO_API[ui]] == ui
    # An unknown device value falls back to "off" (the get_status parser default).
    assert NIGHT_MODE_FROM_API.get("somethingElse", "off") == "off"


# --- Volume range probe (issue #22) -------------------------------------------


def _on_with_edit(edit):
    """get_data stub: ON device whose player:volume ``edit`` role returns ``edit``."""
    base = _on_value_for(volume=20)
    calls = []

    def value_for(path: str, timeout: float = 8, roles: str = "value", **_):
        if roles == "edit":
            calls.append(path)
            if isinstance(edit, Exception):
                raise edit
            return edit
        return base(path, timeout)

    return value_for, calls


async def test_volume_max_read_from_device(api: KlipschAPI) -> None:
    stub, calls = _on_with_edit([{"type": "slider", "min": "0", "max": "50", "step": "1"}])
    api.get_data = AsyncMock(side_effect=stub)
    status = await api.get_status()
    assert status["volume_max"] == 50
    await api.get_status()
    assert calls == ["player:volume"]  # probed once, then cached


async def test_volume_max_custom_value(api: KlipschAPI) -> None:
    stub, _ = _on_with_edit([{"type": "slider", "min": "0", "max": "80", "step": "1"}])
    api.get_data = AsyncMock(side_effect=stub)
    assert (await api.get_status())["volume_max"] == 80


async def test_volume_max_falls_back_and_gives_up(api: KlipschAPI) -> None:
    stub, calls = _on_with_edit(TimeoutError())
    api.get_data = AsyncMock(side_effect=stub)
    for _ in range(5):
        status = await api.get_status()
        assert status["online"] is True
        assert status["volume_max"] == 50  # default kept
    assert len(calls) == 3  # bounded number of probes


async def test_volume_max_rejects_garbage(api: KlipschAPI) -> None:
    stub, _ = _on_with_edit([{"type": "slider", "max": "0"}])
    api.get_data = AsyncMock(side_effect=stub)
    assert (await api.get_status())["volume_max"] == 50


async def test_volume_max_carried_through_standby(api: KlipschAPI) -> None:
    api.volume_max = 60
    api.get_data = AsyncMock(return_value=[{"powerTarget": {"target": "networkStandby"}}])
    assert (await api.get_status())["volume_max"] == 60
