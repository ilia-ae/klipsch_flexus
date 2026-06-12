"""Fixtures for Klipsch Flexus tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.klipsch_flexus.const import DOMAIN

MOCK_HOST = "192.168.1.100"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    """Enable the custom integration (and mock zeroconf) for hass-based tests.

    Only engaged when a test actually uses the ``hass`` fixture:
    - ``enable_custom_integrations`` makes ``klipsch_flexus`` loadable, otherwise
      ``flow.async_init`` raises ``IntegrationNotFound``.
    - ``mock_async_zeroconf`` stops HA from setting up the real ``zeroconf``
      dependency, which would open a socket (blocked by pytest-socket).

    Pure unit tests (api/auth) don't request ``hass``, so they skip all of this
    and stay fast and decoupled from the HA test harness.
    """
    if "hass" in request.fixturenames:
        request.getfixturevalue("enable_custom_integrations")
        request.getfixturevalue("mock_async_zeroconf")
    yield


MOCK_STATUS = {
    "online": True,
    "volume": 25,
    "muted": False,
    "input": "hdmiarc",
    "mode": "movie",
    "night_mode": "off",
    "dialog_mode": "off",
    "bass": 0,
    "mid": 0,
    "treble": 0,
    "power": "on",
    "decoder": "dolbyDigitalPlus",
    "eq_preset": "flat",
    "dirac": 1,
    "sub_wired": 0,
    "sub_wireless": 0,
    "back_height": 0,
    "back_left": 0,
    "back_right": 0,
    "front_height": 0,
    "side_left": 0,
    "side_right": 0,
    "poll_time_ms": 850,
    "failed_params": 0,
}


@pytest.fixture
def mock_api():
    """Create a mocked KlipschAPI."""
    with patch("custom_components.klipsch_flexus.api.KlipschAPI", autospec=True) as mock_cls:
        api = mock_cls.return_value
        api.get_status = AsyncMock(return_value=MOCK_STATUS.copy())
        api.get_dirac_filters = AsyncMock(return_value=[{"id": 1, "name": "Filter 1"}, {"id": 2, "name": "Filter 2"}])
        api.get_player_data = AsyncMock(return_value=None)
        api.set_volume = AsyncMock()
        api.set_mute = AsyncMock()
        api.set_input = AsyncMock()
        api.set_sound_mode = AsyncMock()
        api.set_night_mode = AsyncMock()
        api.set_dialog_mode = AsyncMock()
        api.set_channel_level = AsyncMock()
        api.set_eq_preset = AsyncMock()
        api.set_dirac = AsyncMock()
        api.set_power = AsyncMock()
        api.media_control = AsyncMock()
        api.close = AsyncMock()
        api.last_response_time = 42.5
        api.total_requests = 100
        api.failed_requests = 2
        yield api


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    from homeassistant.config_entries import ConfigEntry

    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=f"Klipsch Flexus ({MOCK_HOST})",
        data={"host": MOCK_HOST},
        source="user",
        unique_id=MOCK_HOST,
        entry_id="test_entry_id",
    )
