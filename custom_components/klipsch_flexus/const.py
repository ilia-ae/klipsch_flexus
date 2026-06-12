"""Constants for Klipsch Flexus integration."""

DOMAIN = "klipsch_flexus"
DEFAULT_PORT = 80
SCAN_INTERVAL_SECONDS = 15
SCAN_INTERVAL_STANDBY = 60  # slower polling when soundbar is in standby
CONF_SCAN_INTERVAL = "scan_interval"
# Optional manual override for the device MAC used to derive the write-auth
# credential (2026 firmware). Normally auto-detected; only needed if detection
# fails (e.g. eureka_info reports 00:00:00:00:00:00 and the MAC isn't otherwise
# discoverable on the network).
CONF_DEVICE_MAC = "device_mac"

# API timeouts (seconds) — soundbar is single-threaded and slow
API_TIMEOUT_READ = 8
API_TIMEOUT_WRITE = 10
API_TIMEOUT_POWER = 15  # device needs time to wake up

# Retry settings
API_RETRIES = 2
API_RETRY_DELAY = 0.5  # seconds between retries

# Delay before refresh after command (let device process)
COMMAND_REFRESH_DELAY = 1.0

# API paths
API_PATHS = {
    "volume": "player:volume",
    "mute": "settings:/mediaPlayer/mute",
    "input": "cinema:/external/physicalAudioInput",
    "mode": "settings:/cinema/postProcessorMode",
    "night": "cinema:/nightMode",
    "dialog": "settings:/cinema/dialogMode",
    "bass": "cinema:cinemaBass",
    "mid": "cinema:cinemaMid",
    "treble": "cinema:cinemaTreble",
    "power": "powermanager:target",
    "power_req": "powermanager:targetRequest",
    "decoder": "cinema:/audioDecoder",
    "eq_preset": "settings:/cinema/dsp/cinemaEqPreset",
    "dirac": "dirac:/activeFilter",
    "sub_wired": "settings:/cinema/dsp/wiredSubwooferVolume",
    "sub_wireless": "settings:/cinema/dsp/wirelessSubwoofersVolume",
    # Surround channel levels (Dolby Atmos)
    "back_height": "settings:/cinema/dsp/backHeightVolume",
    "back_left": "settings:/cinema/dsp/backLeftVolume",
    "back_right": "settings:/cinema/dsp/backRightVolume",
    "front_height": "settings:/cinema/dsp/frontHeightVolume",
    "side_left": "settings:/cinema/dsp/sideLeftVolume",
    "side_right": "settings:/cinema/dsp/sideRightVolume",
    "player": "player:player/data",
    "player_control": "player:player/control",
}

# Channel levels — surround speakers, subwoofers, then tone controls
# Display names are handled by translations (entity.number.<key>.name)
CHANNEL_LEVELS = [
    # Surround channels (Dolby Atmos)
    ("back_height", "mdi:speaker"),
    ("back_left", "mdi:speaker"),
    ("back_right", "mdi:speaker"),
    ("front_height", "mdi:speaker"),
    ("side_left", "mdi:speaker"),
    ("side_right", "mdi:speaker"),
    # Subwoofers
    ("sub_wired", "mdi:speaker-wireless"),
    ("sub_wireless", "mdi:speaker-wireless"),
    # Tone
    ("bass", "mdi:sine-wave"),
    ("mid", "mdi:tune"),
    ("treble", "mdi:music-clef-treble"),
]

# Source list (input names → display names)
SOURCES = {
    "hdmiarc": "TV ARC",
    "hdmi1": "HDMI",
    "spdif": "SPDIF",
    "bluetooth": "Bluetooth",
    "googlecast": "Google Cast",
    "airplay": "AirPlay",
}
SOURCES_REVERSE = {v: k for k, v in SOURCES.items()}

# Sound modes
SOUND_MODES = ["movie", "music", "game", "sport", "night", "direct", "surround", "stereo"]

# Night mode (translation keys; display names via translations)
NIGHT_MODES = ["off", "night_mode_1"]
# Mapping: translation key → API value
NIGHT_MODE_TO_API = {"night_mode_1": "nightMode_1", "off": "off"}
NIGHT_MODE_FROM_API = {v: k for k, v in NIGHT_MODE_TO_API.items()}

# Dialog mode (raw API keys; display names via translations)
DIALOG_MODES = ["off", "dialog_1", "dialog_2", "dialog_3"]

# EQ Presets
EQ_PRESETS = ["flat", "bass", "rock", "vocal"]

# Dirac filters (discovered dynamically, but defaults)
DIRAC_OFF = -1
