"""Tests for the Klipsch Flexus media player."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError

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


# --- Volume scale (issue #22: device volume is 0..50, not a percentage) --------


def _volume_player(monkeypatch, volume: int, volume_max: int | None = 50):
    player, coordinator, _clock = _make_player(monkeypatch)
    coordinator.data = {"online": True, "power": "on", "volume": volume}
    if volume_max is not None:
        coordinator.data["volume_max"] = volume_max
    coordinator.api.set_volume = AsyncMock()
    return player, coordinator


def test_volume_level_uses_device_scale(monkeypatch):
    player, _ = _volume_player(monkeypatch, volume=25)
    assert player.volume_level == 0.5
    player, _ = _volume_player(monkeypatch, volume=50)
    assert player.volume_level == 1.0


def test_volume_level_falls_back_to_50_without_range(monkeypatch):
    player, _ = _volume_player(monkeypatch, volume=10, volume_max=None)
    assert player.volume_level == 0.2


def test_volume_level_follows_reported_max(monkeypatch):
    player, _ = _volume_player(monkeypatch, volume=30, volume_max=60)
    assert player.volume_level == 0.5


def test_volume_level_clamped_to_one(monkeypatch):
    player, _ = _volume_player(monkeypatch, volume=70)
    assert player.volume_level == 1.0


async def test_set_volume_level_maps_to_device_scale(monkeypatch):
    player, coordinator = _volume_player(monkeypatch, volume=0)
    await player.async_set_volume_level(0.5)
    coordinator.api.set_volume.assert_awaited_once_with(25)
    coordinator.api.set_volume.reset_mock()
    await player.async_set_volume_level(1.0)
    coordinator.api.set_volume.assert_awaited_once_with(50)


async def test_volume_up_down_step_and_clamp(monkeypatch):
    player, coordinator = _volume_player(monkeypatch, volume=49)
    await player.async_volume_up()
    coordinator.api.set_volume.assert_awaited_once_with(50)  # step 2, clamped at max

    player, coordinator = _volume_player(monkeypatch, volume=20)
    await player.async_volume_down()
    coordinator.api.set_volume.assert_awaited_once_with(18)

    player, coordinator = _volume_player(monkeypatch, volume=1)
    await player.async_volume_down()
    coordinator.api.set_volume.assert_awaited_once_with(0)


def test_unread_values_are_none(monkeypatch):
    """Right after a restart in standby nothing but power is known: no invented
    volume 0 / unmuted / 'unknown' source."""
    player, coordinator, _clock = _make_player(monkeypatch)
    coordinator.data = {"online": True, "power": "networkStandby", "volume_max": 50}
    assert player.volume_level is None
    assert player.is_volume_muted is None
    assert player.source is None
    assert player.extra_state_attributes["bass"] is None


def test_subwoofer_attributes_name_wired_and_wireless(monkeypatch):
    """The wired RCA sub output and the shared wireless-subs trim keep their own
    names; the old 'wireless 1/2' attribute names stay as deprecated aliases so
    existing templates do not silently turn into None."""
    player, coordinator, _clock = _make_player(monkeypatch)
    coordinator.data = {"online": True, "sub_wired": -3, "sub_wireless": 4}
    attrs = player.extra_state_attributes
    assert attrs["sub_wired"] == -3
    assert attrs["sub_wireless"] == 4
    assert attrs["sub_wireless_1"] == -3
    assert attrs["sub_wireless_2"] == 4


@pytest.mark.parametrize("step", ["async_volume_up", "async_volume_down"])
async def test_volume_step_refuses_unknown_volume(monkeypatch, step):
    """Stepping needs the real current level; never step from a made-up 0."""
    player, coordinator, _clock = _make_player(monkeypatch)
    coordinator.data = {"online": True, "power": "networkStandby"}
    coordinator.api.set_volume = AsyncMock()
    with pytest.raises(HomeAssistantError):
        await getattr(player, step)()
    coordinator.api.set_volume.assert_not_awaited()


def test_source_list_and_names(monkeypatch):
    player, coordinator, _clock = _make_player(monkeypatch)
    # Only inputs a user can pick; no AirPlay (not a device input).
    assert player.source_list == ["TV ARC", "HDMI", "SPDIF", "Bluetooth", "Google Cast"]
    # Every device input still gets a display name when it is active.
    coordinator.data = {"online": True, "input": "spotify"}
    assert player.source == "Spotify Connect"
    coordinator.data = {"online": True, "input": "usbdevice"}
    assert player.source == "USB"


async def test_select_source_writes_device_value(monkeypatch):
    player, coordinator, _clock = _make_player(monkeypatch)
    coordinator.data = {"online": True}
    coordinator.api.set_input = AsyncMock()
    await player.async_select_source("TV ARC")
    coordinator.api.set_input.assert_awaited_once_with("hdmiarc")


def test_device_info_model_from_discovery():
    coordinator = MagicMock()
    coordinator.device_info = None
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.data = {"host": "1.2.3.4", "model": "Flexus Core 200"}
    assert KlipschMediaPlayer(coordinator, entry)._attr_device_info["model"] == "Flexus Core 200"
    entry.data = {"host": "1.2.3.4"}
    assert KlipschMediaPlayer(coordinator, entry)._attr_device_info["model"] == "Flexus CORE 300"


def test_network_standby_reports_off(monkeypatch):
    """STANDBY is removed from HA core; network standby must read as OFF (#25)."""
    player, coordinator, _clock = _make_player(monkeypatch)
    coordinator.data = {"online": True, "power": "networkStandby"}
    assert player.state == MediaPlayerState.OFF
