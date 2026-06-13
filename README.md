# Klipsch Flexus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://img.shields.io/github/license/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#auto-discovery)

[![Validate](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/hassfest.yaml)
[![CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 **English** | [Русский](docs/README_ru.md) | [Deutsch](docs/README_de.md) | [Español](docs/README_es.md) | [Português](docs/README_pt.md)  
🔒 **Security**: [Policy](SECURITY.md) | [Assessment Report](docs/SECURITY_ASSESSMENT_CORE_300.md)

---

Home Assistant custom integration for **Klipsch Flexus** soundbars — control via **native local HTTP API**, no cloud, no delays.

> ✅ **Up to date as of v2.5.10 (2026-06-13)** — **41 entities**, all write commands verified live against 2026 firmware (HMAC-signed), controllable in standby. The badges above reflect the live release and last push.

## 📸 Dashboard

A custom Lovelace dashboard driven entirely by the integration's entities — input, sound mode, night / dialog enhance, EQ presets, Dirac filter, tone (bass / mid / treble), surround channel levels and subwoofers — all controlled live over the local API.

![Klipsch Flexus dashboard](docs/images/dashboard.png)

**Required HACS components** (all installable via [HACS](https://github.com/hacs/integration)):

| Component | Repo | Used for |
|-----------|------|----------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | this integration — the entities |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | media-player card |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | source / mode / EQ tiles with dynamic styling |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | active-state highlighting (CSS) |

📋 **Full dashboard YAML + colour scheme:** [docs/DASHBOARD.md](docs/DASHBOARD.md)

### Supported Models

| Model | Channels | Features |
|-------|----------|----------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 drivers |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

> The soundbar must be pre-configured via the official Klipsch Connect Plus app (Wi-Fi, firmware, speaker pairing, Dirac calibration). This integration handles ongoing control only.

## ⚠️ Firmware Compatibility (2026 update)

A 2026 soundbar firmware update (**Device Version `1.1.3.x`**, e.g. `1.1.3.0x7cd294e`, Cast build `20250512_0201_RC25`) changed the local HTTP API in two ways:

1. **`setData` now requires `POST` with a JSON body.** The old `GET /api/setData?...` returns `405 Strict HTTP required!`. **Fixed in v2.4.1** — update the integration.
2. **Most `setData` writes are now authenticated** (`settings:/webserver/authMode = setData`). Protected writes return `401 Forbidden` with `WWW-Authenticate: HMAC_SHA256_AES256`. **Fixed in v2.5.0** — the integration now signs these writes automatically.

### What works on the new firmware

| Capability | Status |
|------------|--------|
| All sensors / status reads (`getData`) | ✅ Works |
| Volume, Mute | ✅ Works |
| Input, Sound mode, Night / Dialog, Bass / Mid / Treble, EQ Preset, Dirac, Subwoofer & Surround levels, Power | ✅ Works (HMAC-signed, v2.5.0+) |
| LED, Lip-sync, Balance, Loudness, DND, Auto-standby + 4 more toggles | ✅ Works (signed; added v2.5.8–2.5.9) — also in standby |

You can see the live per-command status on your own device via **Download diagnostics** (the `command_health` section, added in v2.4.2).

### Status of the fix

✅ **Solved in v2.5.0 — full control restored, no user action required.** The `HMAC_SHA256_AES256` request signing is now implemented. The per-device credential is derived automatically from the soundbar's MAC address, so there is **nothing to configure** — just update the integration. Since **v2.5.9** the MAC is read deterministically from the device itself (`settings:/system/primaryMacAddress`), so resolution works on the first try for every unit (with the previous registry/ARP discovery kept as a fallback). Signed writes go to the device's HTTPS endpoint; volume/mute continue to work unsigned.

> Requires the `cryptography` package (declared in the manifest; bundled with Home Assistant, so it is already present).

📖 **How we reverse-engineered it** — the full investigation story (blutter, Frida, WireGuard-MITM, the security-theatre teardown): [the field report](docs/REPORT_en.md) (also in [Russian](docs/REPORT.md)).

Older firmware (pre-`1.1.3`) is unaffected and keeps full control via the legacy `GET` fallback.

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
- **LED Brightness** — front LED: Off / Dim / Bright

### Settings Numbers
- **Lip-sync Delay** — manual A/V sync (0–300 ms)
- **Balance** — left/right balance (−10…+10)
- **Idle Timeout** — auto-standby idle time (0–3600 s)

### Toggles (Switches)
- **Auto Lip-sync** — automatic A/V delay
- **EQ Bypass** — bypass the equaliser
- **Auto Power** — auto on/standby behaviour
- **Loudness** — low-volume loudness compensation
- **Do Not Disturb** — suppress notifications/sounds
- **Auto Standby** — drop to standby when idle
- **UI Sounds**, **Extra Sound Modes**, **BLE Remote Auto-pair**, **Firmware Auto-update**

> All settings above are also writable while the soundbar is in **standby** (the device applies and persists them); the integration keeps the entities available and remembers the value you set rather than reverting it.

### Diagnostics
- **Response Time** — API poll duration in ms, request/failure counters
- **Device Status** — On / Standby / Offline with decoder, input, sound mode info
- **Signing MAC** — the MAC used to sign 2026-firmware writes (scheme, candidates, resolved state)
- **Network Link** — active wired/wireless interface, interface names, MAC sources
- **Operating Mode** / **Speaker Test** — read-only device state (surfaced, deliberately not controllable)
- **Speaker Delays** (wired/wireless sub, wireless surround) — read-only, auto-calibrated by the device
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
| Optimistic updates | UI updates instantly, then verified via delayed poll; values applied in standby are cached so the standby poll never reverts them |
| **Standby-aware polling** | Power state probed first; in standby only 1 request instead of 20+, cached values preserved, poll interval slows to 60 s. Settings stay **available and controllable** in standby — the device applies writes and the integration remembers them |

## Entities

![Klipsch Flexus device page in Home Assistant](docs/images/device-page.png)

*The integration's Home Assistant device page — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + toggles) and the Activity log.*

| Entity | Type | Category |
|--------|------|----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Night Mode / Dialog Mode / EQ Preset / Dirac Filter / LED Brightness | Select (x5) | Config |
| Back Height / Left / Right, Front Height, Side Left / Right | Number (x6) | Config |
| Subwoofer Wireless 1 / 2 | Number (x2) | Config |
| Bass / Mid / Treble | Number (x3) | Config |
| Lip-sync Delay, Balance, Idle Timeout | Number (x3) | Config |
| Auto Lip-sync, EQ Bypass, Auto Power, UI Sounds, Extra Sound Modes, BLE Remote Auto-pair, Firmware Auto-update | Switch (x7) | Config |
| Loudness, Do Not Disturb, Auto Standby | Switch (x3) | Config |
| Response Time, Device Status, Active Input, Active Sound Mode | Sensor (x4) | Diagnostic |
| Signing MAC, Network Link | Sensor (x2) | Diagnostic |
| Operating Mode, Speaker Test, Sub Wired/Wireless Delay, Surround Delay | Sensor (x5, read-only) | Diagnostic |

**Total: 41 entities** (1 media player + 5 selects + 14 numbers + 10 switches + 11 sensors)

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

**Network Security Notice**: The soundbar communicates over HTTP. Older firmware required no authentication at all; the 2026 firmware (`1.1.3.x`) authenticates most write commands but reads stay open (see [Firmware Compatibility](#️-firmware-compatibility-2026-update)). Keep it on a trusted network segment. Read the [Security Assessment Report](docs/SECURITY_ASSESSMENT_CORE_300.md) for detailed security analysis.

## License

MIT — see [LICENSE](LICENSE).
