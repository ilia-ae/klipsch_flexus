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
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .auth import ZERO_MAC, mac_to_colon
from .const import (
    DIRAC_OFF,
    DOMAIN,
    SELECTABLE_SOURCES,
    SOUND_MODES,
    SOURCES,
    SOURCES_REVERSE,
    VOLUME_MAX_DEFAULT,
)
from .coordinator import KlipschCoordinator
from .entity import KlipschEntity

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


class KlipschMediaPlayer(KlipschEntity, MediaPlayerEntity):
    """Klipsch Flexus media player."""

    _attr_name = None
    _attr_icon = "mdi:speaker"

    def __init__(self, coordinator: KlipschCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "media_player")
        self._entry = entry
        host = entry.data.get("host", "")
        device_info: dict = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "manufacturer": "Klipsch",
            # Model from discovery (Cast TXT 'md'), if the entry was discovered
            "model": entry.data.get(CONF_MODEL) or "Flexus CORE 300",
            "configuration_url": f"http://{host}",
        }
        # Enrich from eureka_info (Google Cast API, port 8008)
        eureka = coordinator.device_info
        if eureka and eureka.get("name"):
            device_info["name"] = eureka["name"]
        elif getattr(coordinator.registered_device(), "name", None) is None:
            # Generic name for a new / unnamed device only: no eureka_info (setup
            # in standby) must not overwrite the name the registry already has.
            device_info["name"] = "Klipsch Flexus CORE 300"
        if eureka:
            if eureka.get("cast_build_revision"):
                device_info["sw_version"] = eureka["cast_build_revision"]
            # 2026 firmware reports the all-zero MAC here; registering it as a
            # connection would make every Flexus share ('mac','00:…:00') and risk
            # HA merging two physical units into one device. Only add a real MAC.
            colon = mac_to_colon(eureka.get("mac_address") or "")
            if colon and colon != ZERO_MAC:
                device_info["connections"] = {("mac", colon.lower())}
        self._attr_device_info = device_info
        self._attr_source_list = [SOURCES[key] for key in SELECTABLE_SOURCES]
        self._attr_sound_mode_list = SOUND_MODES
        # Media position tracking (API has no position, only duration)
        self._position: int = 0  # seconds
        self._position_updated_at: datetime | None = None
        self._prev_player_state: str | None = None
        self._prev_track_title: str | None = None

    def _player_data(self) -> dict:
        """Current player/media payload from the coordinator (empty dict if absent)."""
        data = self.coordinator.data or {}
        return data.get("player", {})

    def _dirac_filter_name(self) -> str:
        """Resolve Dirac filter ID to human name."""
        data = self.coordinator.data or {}
        dirac_id = data.get("dirac", DIRAC_OFF)
        for f in self.coordinator.dirac_filters:
            if f["id"] == dirac_id:
                return f["name"]
        return "off" if dirac_id == DIRAC_OFF else str(dirac_id)

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
            if title != self._prev_track_title:
                # New track → restart from zero.
                self._position = 0
                self._position_updated_at = now
            elif self._prev_player_state != "playing":
                # Resumed from pause/idle → keep the frozen position but re-stamp,
                # so the frontend extrapolates forward from now instead of jumping
                # back to zero (the device API exposes no position of its own).
                self._position_updated_at = now
            # else: still playing the same track → leave position + timestamp
            # untouched so the frontend keeps extrapolating elapsed time.
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
            return MediaPlayerState.OFF
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
        volume = data.get("volume")
        if volume is None:
            return None  # not read yet (e.g. HA started while the bar was in standby)
        return min(volume / self._volume_max(), 1.0)

    @property
    def is_volume_muted(self) -> bool | None:
        data = self.coordinator.data or {}
        if not data.get("online"):
            return None
        return data.get("muted")

    @property
    def source(self) -> str | None:
        data = self.coordinator.data or {}
        raw = data.get("input")
        if raw is None:
            return None
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
        # Values not read yet (e.g. HA started while the bar was in standby) are None
        attrs = {
            # Audio processing
            "decoder": data.get("decoder"),
            "eq_preset": data.get("eq_preset"),
            "night_mode": data.get("night_mode"),
            "dialog_mode": data.get("dialog_mode"),
            # Surround channels
            "back_height": data.get("back_height"),
            "back_left": data.get("back_left"),
            "back_right": data.get("back_right"),
            "front_height": data.get("front_height"),
            "side_left": data.get("side_left"),
            "side_right": data.get("side_right"),
            # Subwoofers. The CORE 300's two subs are both wireless, so the
            # firmware's "wired"/"wireless" volume nodes are surfaced as Wireless
            # 1/2 (matching the number-entity translations) — intentional mapping,
            # not a copy/paste slip.
            "sub_wireless_1": data.get("sub_wired"),
            "sub_wireless_2": data.get("sub_wireless"),
            # Tone
            "bass": data.get("bass"),
            "mid": data.get("mid"),
            "treble": data.get("treble"),
            # Dirac
            "dirac_filter": self._dirac_filter_name(),
        }
        # Source app (only when available)
        source_app = self._source_app_name()
        if source_app:
            attrs["source_app"] = source_app
        return attrs

    # --- Commands with optimistic updates ---

    def _volume_max(self) -> int:
        """Device volume scale (0..max); 50 on Flexus soundbars, not 100."""
        value = (self.coordinator.data or {}).get("volume_max")
        return value if isinstance(value, int) and value > 0 else VOLUME_MAX_DEFAULT

    def _volume_step(self) -> int:
        """Volume up/down step: ~5% of the scale, at least 1 (2 of 50)."""
        return max(1, self._volume_max() // 20)

    async def async_set_volume_level(self, volume: float) -> None:
        level = max(0, min(round(volume * self._volume_max()), self._volume_max()))
        await self.coordinator.api.set_volume(level)
        self._optimistic_update(volume=level)
        self.coordinator.async_request_delayed_refresh()

    def _current_volume(self) -> int:
        """Last read device volume — refuse to step from a made-up level."""
        current = (self.coordinator.data or {}).get("volume")
        if current is None:
            raise HomeAssistantError("Klipsch Flexus volume is not known yet; set a level instead of stepping")
        return current

    async def async_volume_up(self) -> None:
        new_level = min(self._current_volume() + self._volume_step(), self._volume_max())
        await self.coordinator.api.set_volume(new_level)
        self._optimistic_update(volume=new_level)
        self.coordinator.async_request_delayed_refresh()

    async def async_volume_down(self) -> None:
        new_level = max(self._current_volume() - self._volume_step(), 0)
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
