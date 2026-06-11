"""Tests for Klipsch Flexus API client."""

from __future__ import annotations

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

    async def mock_get(*args, **kwargs):
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
