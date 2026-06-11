# Klipsch Flexus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/razqqm/klipsch_flexus.svg?style=for-the-badge)](https://github.com/razqqm/klipsch_flexus/releases)
[![License](https://img.shields.io/github/license/razqqm/klipsch_flexus.svg?style=for-the-badge)](LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#auto-discovery)

[![Validate](https://github.com/razqqm/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/razqqm/klipsch_flexus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/hassfest.yaml)
[![CI](https://github.com/razqqm/klipsch_flexus/actions/workflows/ci.yaml/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/razqqm/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 **English** | [Русский](docs/README_ru.md) | [Deutsch](docs/README_de.md) | [Español](docs/README_es.md) | [Português](docs/README_pt.md)  
🔒 **Security**: [Policy](SECURITY.md) | [Assessment Report](docs/SECURITY_ASSESSMENT_CORE_300.md)

---

Home Assistant custom integration for **Klipsch Flexus** soundbars — control via **native local HTTP API**, no cloud, no delays.

### Supported Models

| Model | Channels | Features |
|-------|----------|----------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 drivers |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

> The soundbar must be pre-configured via the official Klipsch Connect Plus app (Wi-Fi, firmware, speaker pairing, Dirac calibration). This integration handles ongoing control only.

## Features

### Media Player
- **Volume** — set level, step up/down, mute/unmute
- **Power** — turn on / standby
- **Input source** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast
- **Sound mode** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Playback** — play/pause, next/previous track
- **Media info** — title, artist, album, artwork, source app

### Channel Levels (11 sliders, -6 to +6 dB)

| Channel | Description |
|---------|-------------|
| Front Height | Dolby Atmos front height speaker |
| Back Height | Dolby Atmos rear height speaker |
| Side Left / Right | Surround side speakers |
| Back Left / Right | Surround rear speakers |
| Subwoofer Wireless 1 / 2 | Wireless subwoofer levels |
| Bass / Mid / Treble | Tone EQ controls |

### Audio Settings (Selects)
- **EQ Preset** — Flat, Bass, Rock, Vocal
- **Night Mode** — reduces dynamic range for quiet listening
- **Dialog Mode** — boosts dialog clarity (3 levels)
- **Dirac Live** — room correction filter (auto-discovered from device)

### Diagnostics
- **Response Time** — API poll duration in ms, request/failure counters
- **Device Status** — On / Standby / Offline with decoder, input, sound mode info
- **Download diagnostics** — full device state export (Settings > Devices > Klipsch Flexus > Download diagnostics)

### Translations
Full UI translation in **7 languages**: English, Russian, German, Spanish, French, Italian, Portuguese. All entity names, states, and configuration screens are translated.

## Installation

### HACS (recommended)

1. Open **HACS** > Integrations > search **Klipsch Flexus**
2. Install and restart Home Assistant
3. The soundbar should be **automatically discovered** — check notifications
4. Or go to **Settings** > Devices & Services > **Add Integration** > Klipsch Flexus

### Manual

1. Copy `custom_components/klipsch_flexus/` to your HA `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via Settings > Devices & Services

## Auto-Discovery

The soundbar is automatically discovered on your network via **mDNS / Zeroconf** (Google Cast protocol).

When powered on, Home Assistant will detect the soundbar and display a notification:
> **Klipsch Flexus CORE 300** found at `192.168.1.100`. Do you want to add this soundbar?

**How it works:**
- Soundbar announces itself as `Flexus-Core-*` via `_googlecast._tcp` mDNS service
- Integration identifies the device by `md` (model) and `fn` (friendly name) TXT records
- AirCast proxy devices are automatically filtered out

If auto-discovery doesn't work (e.g. network isolation), you can always add the integration manually by entering the IP address.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| Host | — | IP address of the soundbar (required) |
| Poll interval | 15 s (60 s in standby) | Configurable via Options (5–120 s); automatically reduced in standby |

**Tip:** Assign a static IP / DHCP reservation to the soundbar for reliable operation.

You can change the IP address later via **Reconfigure** (Settings > Devices > Klipsch Flexus > Reconfigure).

## How It Works

The soundbar exposes a local HTTP API on port 80:
- `GET /api/getData` — read parameters
- `POST /api/setData` — write parameters (JSON body; legacy GET fallback for older firmware)
- `GET /api/getRows` — list structured data (Dirac filters)

### Resilient Design for a Slow Device

The Klipsch Flexus has a **single-threaded HTTP server** that processes one request at a time. The integration is built around this constraint:

| Mechanism | Description |
|-----------|-------------|
| Request serialization | All API calls go through `asyncio.Lock` — no concurrent requests |
| Retry with backoff | Transient errors retried 2x with 0.5 s delay |
| Adaptive timeouts | 8 s reads, 10 s writes, 15 s power commands |
| Graceful degradation | Failed reads fall back to last-known cached values |
| Optimistic updates | UI updates instantly, then verified via delayed poll |
| **Standby-aware polling** | Power state probed first; in standby only 1 request instead of 20+, cached values preserved, poll interval slows to 60 s |

## Entities

| Entity | Type | Category |
|--------|------|----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Night Mode | Select | Config |
| Dialog Mode | Select | Config |
| EQ Preset | Select | Config |
| Dirac Filter | Select | Config |
| Back Height / Left / Right | Number (x3) | Config |
| Front Height | Number | Config |
| Side Left / Right | Number (x2) | Config |
| Subwoofer Wireless 1 / 2 | Number (x2) | Config |
| Bass / Mid / Treble | Number (x3) | Config |
| Response Time | Sensor | Diagnostic |
| Device Status | Sensor | Diagnostic |
| Active Input | Sensor | Diagnostic |
| Active Sound Mode | Sensor | Diagnostic |

**Total: 20 entities** (1 media player + 4 selects + 11 numbers + 4 sensors)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Cannot connect | Check that the soundbar is on the same network. Try: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entities unavailable | The Klipsch app may be polling simultaneously — close it and retry |
| Slow updates | Increase poll interval in Options (Settings > Devices > Klipsch Flexus > Configure) |
| Integration not loading | Check Home Assistant logs for import errors. Ensure you're on HA 2024.4.0+ |

## Legacy Alternative (no custom integration)

If you prefer not to install a custom integration, see the [`legacy/`](legacy/) folder for a standalone approach using only built-in HA components (`command_line` sensor + `rest_command` + scripts).

This was the original implementation before the custom integration was created. It provides basic volume/input/mode control via dashboard buttons but lacks media player entity, playback controls, auto-discovery, and translations. See [`legacy/README.md`](legacy/README.md) for setup instructions and a feature comparison.

## Known Limitations

- One soundbar per integration entry (add multiple as separate entries)
- No multi-room / wireless surround group management (use Klipsch Connect Plus app)
- AirPlay and Cast protocols are not used — only the native HTTP API
- Initial device setup requires the official Klipsch Connect Plus app

## Security

See [SECURITY.md](SECURITY.md) for security policy and best practices.

**Network Security Notice**: The soundbar communicates over HTTP without authentication. Keep it on a trusted network segment. Read the [Security Assessment Report](docs/SECURITY_ASSESSMENT_CORE_300.md) for detailed security analysis.

## License

MIT — see [LICENSE](LICENSE).
