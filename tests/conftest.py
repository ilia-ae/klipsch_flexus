"""Fixtures for Klipsch Flexus tests."""

from __future__ import annotations

import pytest

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
