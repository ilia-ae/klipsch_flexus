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

    async def mock_get_data(path, timeout=8):
        nonlocal call_count
        call_count += 1
        if "volume" in path:
            return [{"i32_": 50}]
        if "mute" in path:
            return [{"bool_": False}]
        if "powerTarget" in path or "powermanager" in path:
            return [{"powerTarget": {"target": "on"}}]
        # Fail for everything else
        raise TimeoutError()

    api.get_data = mock_get_data
    result = await api.get_status()

    # Should still be online since not ALL params failed
    assert result["online"] is True
    assert result["volume"] == 50


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

    async def mock_get_data(path, timeout=8):
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


async def test_get_status_standby_no_cache(api: KlipschAPI) -> None:
    """Test standby with empty cache (first boot in standby)."""
    api._last_status = {}

    async def mock_get_data(path, timeout=8):
        if "powermanager" in path:
            return [{"powerTarget": {"target": "networkStandby"}}]
        raise AssertionError(f"Unexpected poll: {path}")

    api.get_data = mock_get_data
    result = await api.get_status()

    assert result["online"] is True
    assert result["power"] == "networkStandby"
    # No cached values — keys should be absent
    assert "volume" not in result
    assert "input" not in result


async def test_get_status_power_fail_means_offline(api: KlipschAPI) -> None:
    """Test that power query failure immediately returns offline."""
    call_count = 0

    async def mock_get_data(path, timeout=8):
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

    result = await api.set_data(
        "powermanager:targetRequest", {"target": "on", "reason": "userActivity"}, roles="activate"
    )
    assert result == "node error"  # 500 returned to caller
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

    async def mock_get_data(path, timeout=8):
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

    def value_for(path: str):
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
