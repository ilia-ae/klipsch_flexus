"""Media player platform for Klipsch Flexus."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SOUND_MODES, SOURCES, SOURCES_REVERSE
from .coordinator import KlipschCoordinator

_BASE_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)


def _http_image_url(icon: object) -> str | None:
    """Return ``icon`` only if it is a real http(s) artwork URL.

    Physical inputs report a device-internal skin reference instead of a URL
    (e.g. ``"skin:iconHdmi"`` for HDMI-eARC), which Home Assistant would try to
    fetch and render as a broken image. Returning ``None`` for those falls back
    to the default media-player icon.
    """
    if isinstance(icon, str) and icon.startswith(("http://", "https://")):
        return icon
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KlipschCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KlipschMediaPlayer(coordinator, entry)])


class KlipschMediaPlayer(CoordinatorEntity[KlipschCoordinator], MediaPlayerEntity):
    """Klipsch Flexus media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:speaker"

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        host = entry.data.get("host", "")
        device_info: dict = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Klipsch Flexus CORE 300",
            "manufacturer": "Klipsch",
            "model": "Flexus CORE 300",
            "configuration_url": f"http://{host}",
        }
        # Enrich from eureka_info (Google Cast API, port 8008)
        eureka = coordinator.device_info
        if eureka:
            if eureka.get("name"):
                device_info["name"] = eureka["name"]
            if eureka.get("cast_build_revision"):
                device_info["sw_version"] = eureka["cast_build_revision"]
            if eureka.get("mac_address"):
                device_info["connections"] = {("mac", eureka["mac_address"].lower())}
        self._attr_device_info = device_info
        self._attr_source_list = list(SOURCES.values())
        self._attr_sound_mode_list = SOUND_MODES
        # Media position tracking (API has no position, only duration)
        self._position: int = 0  # seconds
        self._position_updated_at: datetime | None = None
        self._prev_player_state: str | None = None
        self._prev_track_title: str | None = None

    def _player_data(self) -> dict:
        data = self.coordinator.data or {}
        return data.get("player", {})

    def _dirac_filter_name(self) -> str:
        """Resolve Dirac filter ID to human name."""
        data = self.coordinator.data or {}
        dirac_id = data.get("dirac", -1)
        for f in self.coordinator.dirac_filters:
            if f["id"] == dirac_id:
                return f["name"]
        return "off" if dirac_id == -1 else str(dirac_id)

    def _source_app_name(self) -> str | None:
        """Get source app name from player metadata."""
        player = self._player_data()
        meta = player.get("trackRoles", {}).get("mediaData", {}).get("metaData", {})
        return meta.get("externalAppName")

    # --- Media position tracking ---

    @callback
    def _handle_coordinator_update(self) -> None:
        """Track media position based on playback state transitions."""
        player = self._player_data()
        state = player.get("state")
        title = player.get("trackRoles", {}).get("title")
        now = datetime.now(UTC)

        if state == "playing":
            # New track or transition from non-playing → reset position
            if title != self._prev_track_title or self._prev_player_state != "playing":
                self._position = 0
                self._position_updated_at = now
        elif state == "paused" and self._prev_player_state == "playing":
            # Freeze: calculate elapsed time since last update
            if self._position_updated_at is not None:
                elapsed = (now - self._position_updated_at).total_seconds()
                self._position = int(self._position + elapsed)
                self._position_updated_at = now
        elif state not in ("playing", "paused"):
            self._position = 0
            self._position_updated_at = None

        self._prev_player_state = state
        self._prev_track_title = title
        super()._handle_coordinator_update()

    # --- Optimistic update helper ---

    def _optimistic_update(self, **kwargs) -> None:
        """Update coordinator data in-memory and push state to all entities."""
        # Persist into the status cache too, so the cache-only standby poll
        # doesn't revert a just-applied value.
        self.coordinator.api.note_cached(kwargs)
        if self.coordinator.data:
            self.coordinator.data.update(kwargs)
            self.coordinator.async_set_updated_data(self.coordinator.data)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = _BASE_FEATURES
        player = self._player_data()
        controls = player.get("controls", {})
        if controls.get("pause"):
            features |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        if controls.get("next_"):
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if controls.get("previous"):
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        return features

    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return MediaPlayerState.OFF
        power = data.get("power", "unknown")
        if power == "networkStandby":
            return MediaPlayerState.STANDBY
        player = self._player_data()
        player_state = player.get("state")
        if player_state == "playing":
            return MediaPlayerState.PLAYING
        if player_state == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("volume", 0) / 100.0

    @property
    def is_volume_muted(self) -> bool | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("muted", False)

    @property
    def source(self) -> str | None:
        data = self.coordinator.data or {}
        raw = data.get("input", "unknown")
        return SOURCES.get(raw, raw)

    @property
    def sound_mode(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("mode")

    @property
    def media_content_type(self) -> MediaType | None:
        player = self._player_data()
        if player.get("state") in ("playing", "paused"):
            return MediaType.MUSIC
        return None

    @property
    def media_title(self) -> str | None:
        player = self._player_data()
        track = player.get("trackRoles", {})
        return track.get("title")

    @property
    def media_artist(self) -> str | None:
        player = self._player_data()
        meta = player.get("trackRoles", {}).get("mediaData", {}).get("metaData", {})
        return meta.get("artist")

    @property
    def media_album_name(self) -> str | None:
        player = self._player_data()
        meta = player.get("trackRoles", {}).get("mediaData", {}).get("metaData", {})
        return meta.get("album")

    @property
    def media_image_url(self) -> str | None:
        player = self._player_data()
        return _http_image_url(player.get("trackRoles", {}).get("icon"))

    @property
    def media_duration(self) -> int | None:
        player = self._player_data()
        status = player.get("status", {})
        duration_ms = status.get("duration")
        if duration_ms is not None:
            return duration_ms // 1000
        return None

    @property
    def media_position(self) -> int | None:
        player = self._player_data()
        if player.get("state") in ("playing", "paused"):
            return self._position
        return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        player = self._player_data()
        if player.get("state") in ("playing", "paused"):
            return self._position_updated_at
        return None

    @property
    def app_name(self) -> str | None:
        player = self._player_data()
        media_roles = player.get("mediaRoles", {})
        return media_roles.get("title")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return {}
        attrs = {
            # Audio processing
            "decoder": data.get("decoder", "unknown"),
            "eq_preset": data.get("eq_preset", "unknown"),
            "night_mode": data.get("night_mode", "off"),
            "dialog_mode": data.get("dialog_mode", "off"),
            # Surround channels
            "back_height": data.get("back_height", 0),
            "back_left": data.get("back_left", 0),
            "back_right": data.get("back_right", 0),
            "front_height": data.get("front_height", 0),
            "side_left": data.get("side_left", 0),
            "side_right": data.get("side_right", 0),
            # Subwoofers
            "sub_wireless_1": data.get("sub_wired", 0),
            "sub_wireless_2": data.get("sub_wireless", 0),
            # Tone
            "bass": data.get("bass", 0),
            "mid": data.get("mid", 0),
            "treble": data.get("treble", 0),
            # Dirac
            "dirac_filter": self._dirac_filter_name(),
        }
        # Source app (only when available)
        source_app = self._source_app_name()
        if source_app:
            attrs["source_app"] = source_app
        return attrs

    # --- Commands with optimistic updates ---

    async def async_set_volume_level(self, volume: float) -> None:
        level = round(volume * 100)
        await self.coordinator.api.set_volume(level)
        self._optimistic_update(volume=level)
        self.coordinator.async_request_delayed_refresh()

    async def async_volume_up(self) -> None:
        data = self.coordinator.data or {}
        current = data.get("volume", 0)
        new_level = min(current + 5, 100)
        await self.coordinator.api.set_volume(new_level)
        self._optimistic_update(volume=new_level)
        self.coordinator.async_request_delayed_refresh()

    async def async_volume_down(self) -> None:
        data = self.coordinator.data or {}
        current = data.get("volume", 0)
        new_level = max(current - 5, 0)
        await self.coordinator.api.set_volume(new_level)
        self._optimistic_update(volume=new_level)
        self.coordinator.async_request_delayed_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.api.set_mute(mute)
        self._optimistic_update(muted=mute)
        self.coordinator.async_request_delayed_refresh()

    async def async_select_source(self, source: str) -> None:
        raw = SOURCES_REVERSE.get(source, source)
        await self.coordinator.api.set_input(raw)
        self._optimistic_update(input=raw)
        self.coordinator.async_request_delayed_refresh()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        await self.coordinator.api.set_sound_mode(sound_mode)
        self._optimistic_update(mode=sound_mode)
        self.coordinator.async_request_delayed_refresh()

    async def async_media_play(self) -> None:
        await self.coordinator.api.media_control("play")
        self.coordinator.async_request_delayed_refresh()

    async def async_media_pause(self) -> None:
        await self.coordinator.api.media_control("pause")
        self.coordinator.async_request_delayed_refresh()

    async def async_media_next_track(self) -> None:
        await self.coordinator.api.media_control("next")
        self.coordinator.async_request_delayed_refresh()

    async def async_media_previous_track(self) -> None:
        await self.coordinator.api.media_control("previous")
        self.coordinator.async_request_delayed_refresh()

    async def async_turn_on(self) -> None:
        await self.coordinator.api.set_power("online")
        self._optimistic_update(power="online")
        self.coordinator.async_request_delayed_refresh(delay=3.0)

    async def async_turn_off(self) -> None:
        await self.coordinator.api.set_power("networkStandby")
        self._optimistic_update(power="networkStandby")
        self.coordinator.async_request_delayed_refresh(delay=3.0)
