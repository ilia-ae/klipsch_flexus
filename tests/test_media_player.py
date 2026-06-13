"""Tests for the Klipsch Flexus media player."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from custom_components.klipsch_flexus import media_player as mp_mod
from custom_components.klipsch_flexus.media_player import KlipschMediaPlayer, _http_image_url


def test_http_image_url_filters_non_urls():
    # physical inputs report a device skin ref, not a URL → no broken image
    assert _http_image_url("skin:iconHdmi") is None
    assert _http_image_url("") is None
    assert _http_image_url(None) is None
    assert _http_image_url("iconHdmi") is None
    # real artwork URLs pass through
    assert _http_image_url("http://10.0.0.5/art.png") == "http://10.0.0.5/art.png"
    assert _http_image_url("https://art.example/cover.jpg") == "https://art.example/cover.jpg"


# --- Media position state machine ---------------------------------------------


class _Clock:
    """Controllable stand-in for ``datetime`` (only ``now`` is used)."""

    def __init__(self) -> None:
        self.now_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    def now(self, _tz=None) -> datetime:
        return self.now_dt

    def advance(self, seconds: float) -> None:
        self.now_dt = self.now_dt + timedelta(seconds=seconds)


def _make_player(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(mp_mod, "datetime", clock)
    coordinator = MagicMock()
    coordinator.device_info = None
    coordinator.data = {}
    coordinator.dirac_filters = []
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.data = {"host": "1.2.3.4"}
    player = KlipschMediaPlayer(coordinator, entry)
    player.async_write_ha_state = lambda: None  # no HA registration in a unit test
    return player, coordinator, clock


def _feed(coordinator, state: str, title: str | None = "Song A") -> None:
    coordinator.data = {"player": {"state": state, "trackRoles": {"title": title}}}


def test_media_position_resets_on_new_track(monkeypatch):
    player, coordinator, clock = _make_player(monkeypatch)
    _feed(coordinator, "playing", "Song A")
    player._handle_coordinator_update()
    assert player._position == 0
    clock.advance(30)
    _feed(coordinator, "playing", "Song B")  # different track
    player._handle_coordinator_update()
    assert player._position == 0  # restart for the new track


def test_media_position_preserved_on_resume(monkeypatch):
    """Resuming from pause must continue, not jump back to zero (the bug fixed)."""
    player, coordinator, clock = _make_player(monkeypatch)
    _feed(coordinator, "playing", "Song A")
    player._handle_coordinator_update()  # t0, position 0
    clock.advance(30)
    _feed(coordinator, "paused", "Song A")
    player._handle_coordinator_update()  # freeze at 30s
    assert player._position == 30
    clock.advance(10)  # paused for 10s
    _feed(coordinator, "playing", "Song A")
    player._handle_coordinator_update()  # resume
    assert player._position == 30  # preserved, not reset to 0


def test_media_position_accumulates_across_pauses(monkeypatch):
    player, coordinator, clock = _make_player(monkeypatch)
    _feed(coordinator, "playing", "Song A")
    player._handle_coordinator_update()
    clock.advance(30)
    _feed(coordinator, "paused", "Song A")
    player._handle_coordinator_update()  # 30s
    _feed(coordinator, "playing", "Song A")
    player._handle_coordinator_update()  # resume (re-stamp)
    clock.advance(20)
    _feed(coordinator, "paused", "Song A")
    player._handle_coordinator_update()  # 30 + 20 = 50s
    assert player._position == 50


def test_media_position_cleared_on_stop(monkeypatch):
    player, coordinator, clock = _make_player(monkeypatch)
    _feed(coordinator, "playing", "Song A")
    player._handle_coordinator_update()
    clock.advance(30)
    _feed(coordinator, "paused", "Song A")
    player._handle_coordinator_update()
    assert player._position == 30
    _feed(coordinator, "stopped", None)
    player._handle_coordinator_update()
    assert player._position == 0
    assert player._position_updated_at is None


# --- Device registry connections ----------------------------------------------


def _make_player_with_eureka(eureka):
    coordinator = MagicMock()
    coordinator.device_info = eureka
    coordinator.dirac_filters = []
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.data = {"host": "1.2.3.4"}
    return KlipschMediaPlayer(coordinator, entry)


def test_device_info_skips_zero_mac():
    """The all-zero eureka MAC must not be registered as a connection (else two
    units would share it and HA could merge them into one device)."""
    player = _make_player_with_eureka({"mac_address": "00:00:00:00:00:00", "name": "Klipsch"})
    assert "connections" not in player._attr_device_info


def test_device_info_registers_real_mac():
    player = _make_player_with_eureka({"mac_address": "34:3D:7F:00:2F:3E", "name": "Klipsch"})
    assert player._attr_device_info["connections"] == {("mac", "34:3d:7f:00:2f:3e")}
