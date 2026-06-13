# Klipsch Flexus CORE 300 — Home Assistant Dashboard

> Full-featured soundbar control dashboard for Home Assistant.
> Designed for [Klipsch Flexus](https://github.com/ilia-ae/klipsch_flexus) HACS integration by [@ilia-ae](https://github.com/ilia-ae).

## Requirements

### HACS Integration
- [Klipsch Flexus](https://github.com/ilia-ae/klipsch_flexus) — native API integration (v2.3.2+)

### HACS Frontend (Lovelace cards)
- [Mushroom](https://github.com/piitaya/lovelace-mushroom) — media player card
- [button-card](https://github.com/custom-cards/button-card) — interactive buttons with dynamic styling
- [card-mod](https://github.com/thomasloven/lovelace-card-mod) — CSS customization for active state highlighting

## Layout

### Left Column — Controls
| Section | Description |
|---------|-------------|
| **Player** | Mushroom media player — power, play/pause, mute, volume slider, +/- buttons |
| **Volume Presets** | 7 quick buttons: 5% / 10% / 15% / 20% / 35% / 50% / 75% (half-height, active = blue) |
| **Input Source** | TV ARC / HDMI / SPDIF / BT / Cast / AirPlay — each with unique color |
| **Sound Mode** | Movie / Music / Game / Sport / Night / Direct / 5.1 / Stereo — each with unique color |
| **Night Mode** | Off (yellow) / Night On (indigo) — with icons |
| **Dialog Enhance** | Off (gray) / Low / Mid / High (teal gradient) — with voice icons |

### Right Column — Tuning
| Section | Description |
|---------|-------------|
| **EQ Preset** | Flat (gray) / Bass (red) / Rock (orange) / Vocal (purple) — with icons |
| **Dirac Filter** | Dropdown selector for room correction filters |
| **Tone** | Bass (red) / Mid (orange) / Treble (blue) — gradient fill bars, tap for slider |
| **Surround** | Front/Back Height (green), Side L/R (purple), Back L/R (teal) — directional icons |
| **Subwoofer** | Sub 1 & 2 (deep orange) — gradient fill bars |

## Color Scheme
```
Sources:   TV ARC=#4CAF50  HDMI=#2196F3  SPDIF=#FF9800  BT=#1E88E5  Cast=#4285F4  AirPlay=#646464
Modes:     Movie=#B71C1C   Music=#9C27B0  Game=#4CAF50   Sport=#FF9800
           Night=#3F51B5   Direct=#795548  5.1=#009688    Stereo=#2196F3
Night:     Off=#FFC107     On=#3F51B5
Dialog:    Off=#9E9E9E     Low=#009688    Mid=#00796B    High=#004D40
EQ:        Flat=#9E9E9E    Bass=#F44336   Rock=#FF9800   Vocal=#9C27B0
Tone:      Bass=#F44336    Mid=#FF9800    Treble=#2196F3
Surround:  Front=#4CAF50   Side=#9C27B0   Back=#009688
Sub:       #FF5722
```

## Sizing
- All buttons: `height: 40px`
- Volume presets: `height: 20px` (half)
- Channel/tone bars: `height: 40px` (same as buttons)

## Dashboard YAML

```yaml
title: Soundbar
path: soundbar
icon: mdi:soundbar
type: sections
max_columns: 2
sections:
- type: grid
  cards:
  - type: heading
    heading: KLIPSCH CORE 300
    icon: mdi:soundbar
  - type: custom:mushroom-media-player-card
    entity: media_player.klipsch_flexus_core_300
    name: Klipsch CORE 300
    icon: mdi:soundbar
    use_media_info: true
    show_volume_level: true
    media_controls:
    - on_off
    - play_pause_stop
    volume_controls:
    - volume_mute
    - volume_set
    - volume_buttons
    fill_container: true
    collapsible_controls: false
    layout: horizontal
    grid_options:
      columns: full
      rows: 2
  - type: grid
    columns: 7
    cards:
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 5%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.05
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.05 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 10%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.1
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.1 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 15%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.15
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.15 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 20%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.2
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.2 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 35%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.35
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.35 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 50%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.5
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.5 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    - type: custom:button-card
      entity: media_player.klipsch_flexus_core_300
      name: 75%
      show_icon: false
      show_state: false
      tap_action:
        action: call-service
        service: media_player.volume_set
        service_data:
          entity_id: media_player.klipsch_flexus_core_300
          volume_level: 0.75
      styles:
        card:
        - padding: 2px
        - border-radius: 8px
        - height: 20px
        name:
        - font-size: 11px
        - font-weight: bold
      card_mod:
        style: 'ha-card { background: {% if (state_attr(''media_player.klipsch_flexus_core_300'', ''volume_level'') or 0)
          | round(2) == 0.75 %}rgba(33,150,243,0.2){% else %}rgba(var(--rgb-primary-text-color), 0.04){% endif %}; }'
    grid_options:
      columns: full
  - type: heading
    heading: Input
    heading_style: subtitle
    icon: mdi:audio-input-stereo-minijack
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: TV ARC
    icon: mdi:hdmi-port
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_source
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        source: TV ARC
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''TV ARC'' %}rgba(76,
        175, 80, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''source'') == ''TV ARC'' %}1px solid rgba(76, 175, 80, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''TV ARC'' %}rgb(76, 175,
        80){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 2
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: HDMI
    icon: mdi:video-input-hdmi
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_source
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        source: HDMI
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''HDMI'' %}rgba(33,
        150, 243, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''source'') == ''HDMI'' %}1px solid rgba(33, 150, 243, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon
        { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''HDMI'' %}rgb(33, 150, 243){%
        else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 2
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: SPDIF
    icon: mdi:toslink
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_source
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        source: SPDIF
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''SPDIF'' %}rgba(255,
        152, 0, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''source'') == ''SPDIF'' %}1px solid rgba(255, 152, 0, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon
        { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''SPDIF'' %}rgb(255, 152, 0){%
        else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 2
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: BT
    icon: mdi:bluetooth-audio
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_source
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        source: Bluetooth
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''Bluetooth''
        %}rgba(33, 150, 243, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''source'') == ''Bluetooth'' %}1px solid rgba(33, 150, 243, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''Bluetooth'' %}rgb(33,
        150, 243){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 2
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Cast
    icon: mdi:cast-audio
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_source
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        source: Google Cast
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''Google Cast''
        %}rgba(33, 150, 243, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''source'') == ''Google Cast'' %}1px solid rgba(33, 150, 243, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''Google Cast'' %}rgb(33,
        150, 243){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 2
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: AirPlay
    icon: mdi:apple
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_source
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        source: AirPlay
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''AirPlay''
        %}rgba(100, 100, 100, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''source'') == ''AirPlay'' %}1px solid rgba(100, 100, 100, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''source'') == ''AirPlay'' %}rgb(100,
        100, 100){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 2
  - type: heading
    heading: Mode
    heading_style: subtitle
    icon: mdi:surround-sound-2-0
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Movie
    icon: mdi:movie-open
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: movie
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''movie''
        %}rgba(183, 28, 28, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''movie'' %}1px solid rgba(183, 28, 28, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''movie'' %}rgb(183,
        28, 28){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Music
    icon: mdi:music-note
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: music
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''music''
        %}rgba(156, 39, 176, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''music'' %}1px solid rgba(156, 39, 176, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''music'' %}rgb(156,
        39, 176){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Game
    icon: mdi:controller
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: game
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''game''
        %}rgba(76, 175, 80, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''game'' %}1px solid rgba(76, 175, 80, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''game'' %}rgb(76,
        175, 80){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Sport
    icon: mdi:stadium
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: sport
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''sport''
        %}rgba(255, 152, 0, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''sport'' %}1px solid rgba(255, 152, 0, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''sport'' %}rgb(255,
        152, 0){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Night
    icon: mdi:moon-waning-crescent
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: night
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''night''
        %}rgba(63, 81, 181, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''night'' %}1px solid rgba(63, 81, 181, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''night'' %}rgb(63,
        81, 181){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Direct
    icon: mdi:audio-input-xlr
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: direct
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''direct''
        %}rgba(121, 85, 72, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''direct'' %}1px solid rgba(121, 85, 72, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''direct'' %}rgb(121,
        85, 72){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: '5.1'
    icon: mdi:surround-sound-5-1
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: surround
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''surround''
        %}rgba(0, 150, 136, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''surround'' %}1px solid rgba(0, 150, 136, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''surround'' %}rgb(0,
        150, 136){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: custom:button-card
    entity: media_player.klipsch_flexus_core_300
    name: Stereo
    icon: mdi:speaker-multiple
    show_state: false
    tap_action:
      action: call-service
      service: media_player.select_sound_mode
      service_data:
        entity_id: media_player.klipsch_flexus_core_300
        sound_mode: stereo
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 20px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''stereo''
        %}rgba(33, 150, 243, 0.15){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if state_attr(''media_player.klipsch_flexus_core_300'',
        ''sound_mode'') == ''stereo'' %}1px solid rgba(33, 150, 243, 0.4){% else %}1px solid transparent{% endif %}; } ha-card
        ha-icon { color: {% if state_attr(''media_player.klipsch_flexus_core_300'', ''sound_mode'') == ''stereo'' %}rgb(33,
        150, 243){% else %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
  - type: heading
    heading: Night Mode
    heading_style: subtitle
    icon: mdi:moon-waning-crescent
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_1_night_mode
    name: Night Off
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_1_night_mode
        option: 'off'
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_1_night_mode'') == ''off'' %}rgba(255, 193,
        7, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_1_night_mode'')
        == ''off'' %}1px solid rgba(255, 193, 7, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_1_night_mode'') == ''off'' %}rgb(255, 193, 7){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:brightness-7
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_1_night_mode
    name: Night On
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_1_night_mode
        option: night_mode_1
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_1_night_mode'') == ''night_mode_1'' %}rgba(63,
        81, 181, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_1_night_mode'')
        == ''night_mode_1'' %}1px solid rgba(63, 81, 181, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon
        { color: {% if states(''select.klipsch_flexus_core_300_1_night_mode'') == ''night_mode_1'' %}rgb(63, 81, 181){% else
        %}var(--secondary-text-color){% endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:moon-waning-crescent
    layout: vertical
  - type: heading
    heading: Dialog Enhance
    heading_style: subtitle
    icon: mdi:account-voice
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_2_dialog_mode
    name: Dlg Off
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_2_dialog_mode
        option: 'off'
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''off'' %}rgba(158,
        158, 158, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'')
        == ''off'' %}1px solid rgba(158, 158, 158, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''off'' %}rgb(158, 158, 158){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:account-voice-off
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_2_dialog_mode
    name: Low
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_2_dialog_mode
        option: dialog_1
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''dialog_1'' %}rgba(0,
        150, 136, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'')
        == ''dialog_1'' %}1px solid rgba(0, 150, 136, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon {
        color: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''dialog_1'' %}rgb(0, 150, 136){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:account-voice
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_2_dialog_mode
    name: Mid
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_2_dialog_mode
        option: dialog_2
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''dialog_2'' %}rgba(0,
        121, 107, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'')
        == ''dialog_2'' %}1px solid rgba(0, 121, 107, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon {
        color: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''dialog_2'' %}rgb(0, 121, 107){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:account-voice
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_2_dialog_mode
    name: High
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_2_dialog_mode
        option: dialog_3
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''dialog_3'' %}rgba(0,
        77, 64, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'')
        == ''dialog_3'' %}1px solid rgba(0, 77, 64, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_2_dialog_mode'') == ''dialog_3'' %}rgb(0, 77, 64){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:account-voice
    layout: vertical
- type: grid
  cards:
  - type: heading
    heading: EQ & CHANNELS
    icon: mdi:knob
  - type: heading
    heading: EQ Preset
    heading_style: subtitle
    icon: mdi:chart-bar
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_3_eq_preset
    name: Flat
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_3_eq_preset
        option: flat
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''flat'' %}rgba(158, 158,
        158, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'')
        == ''flat'' %}1px solid rgba(158, 158, 158, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''flat'' %}rgb(158, 158, 158){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:equalizer
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_3_eq_preset
    name: Bass
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_3_eq_preset
        option: bass
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''bass'' %}rgba(244, 67,
        54, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'')
        == ''bass'' %}1px solid rgba(244, 67, 54, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''bass'' %}rgb(244, 67, 54){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:waveform
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_3_eq_preset
    name: Rock
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_3_eq_preset
        option: rock
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''rock'' %}rgba(255, 152,
        0, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'')
        == ''rock'' %}1px solid rgba(255, 152, 0, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''rock'' %}rgb(255, 152, 0){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:guitar-electric
    layout: vertical
  - type: custom:button-card
    entity: select.klipsch_flexus_core_300_3_eq_preset
    name: Vocal
    show_state: false
    show_icon: true
    tap_action:
      action: call-service
      service: select.select_option
      service_data:
        entity_id: select.klipsch_flexus_core_300_3_eq_preset
        option: vocal
    styles:
      card:
      - padding: 4px 2px
      - border-radius: 10px
      - height: 40px
      icon:
      - width: 18px
      name:
      - font-size: 10px
      - margin-top: 1px
      - font-weight: '500'
    card_mod:
      style: 'ha-card { background: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''vocal'' %}rgba(156,
        39, 176, 0.2){% else %}rgba(var(--rgb-primary-text-color), 0.03){% endif %}; border: {% if states(''select.klipsch_flexus_core_300_3_eq_preset'')
        == ''vocal'' %}1px solid rgba(156, 39, 176, 0.4){% else %}1px solid transparent{% endif %}; } ha-card ha-icon { color:
        {% if states(''select.klipsch_flexus_core_300_3_eq_preset'') == ''vocal'' %}rgb(156, 39, 176){% else %}var(--secondary-text-color){%
        endif %}; }'
    grid_options:
      columns: 3
    icon: mdi:microphone
    layout: vertical
  - type: heading
    heading: Dirac
    heading_style: subtitle
    icon: mdi:waveform
  - type: tile
    entity: select.klipsch_flexus_core_300_4_dirac_filter
    name: Dirac Filter
    icon: mdi:waveform
    grid_options:
      columns: full
  - type: heading
    heading: Tone
    heading_style: subtitle
    icon: mdi:tune-vertical
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_tone_bass
    name: Bass
    icon: mdi:waveform
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(244,\
        \ 67, 54, 0.15) {% set v = (states('number.klipsch_flexus_core_300_tone_bass') | float(0) + 6) / 12 * 100 %}{{ v }}%,\n\
        \                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n                border-left:\
        \ 3px solid rgb(244, 67, 54);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_tone_mid
    name: Mid
    icon: mdi:sine-wave
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(255,\
        \ 152, 0, 0.15) {% set v = (states('number.klipsch_flexus_core_300_tone_mid') | float(0) + 6) / 12 * 100 %}{{ v }}%,\n\
        \                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n                border-left:\
        \ 3px solid rgb(255, 152, 0);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_tone_treble
    name: Treble
    icon: mdi:sawtooth-wave
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(33,\
        \ 150, 243, 0.15) {% set v = (states('number.klipsch_flexus_core_300_tone_treble') | float(0) + 6) / 12 * 100 %}{{\
        \ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n           \
        \     border-left: 3px solid rgb(33, 150, 243);\n            }"
    grid_options:
      columns: full
  - type: heading
    heading: Surround
    heading_style: subtitle
    icon: mdi:dolby
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_front_height
    name: Front Height
    icon: mdi:arrow-up-bold
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(76,\
        \ 175, 80, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_front_height') | float(0) + 6) / 12 *\
        \ 100 %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n  \
        \              border-left: 3px solid rgb(76, 175, 80);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_back_height
    name: Back Height
    icon: mdi:arrow-up-bold-outline
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(76,\
        \ 175, 80, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_back_height') | float(0) + 6) / 12 * 100\
        \ %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n      \
        \          border-left: 3px solid rgb(76, 175, 80);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_side_left
    name: Side Left
    icon: mdi:arrow-left-bold
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(156,\
        \ 39, 176, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_side_left') | float(0) + 6) / 12 * 100\
        \ %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n      \
        \          border-left: 3px solid rgb(156, 39, 176);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_side_right
    name: Side Right
    icon: mdi:arrow-right-bold
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(156,\
        \ 39, 176, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_side_right') | float(0) + 6) / 12 * 100\
        \ %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n      \
        \          border-left: 3px solid rgb(156, 39, 176);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_back_left
    name: Back Left
    icon: mdi:arrow-bottom-left
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(0,\
        \ 150, 136, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_back_left') | float(0) + 6) / 12 * 100\
        \ %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n      \
        \          border-left: 3px solid rgb(0, 150, 136);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_back_right
    name: Back Right
    icon: mdi:arrow-bottom-right
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(0,\
        \ 150, 136, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_back_right') | float(0) + 6) / 12 * 100\
        \ %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n                );\n      \
        \          border-left: 3px solid rgb(0, 150, 136);\n            }"
    grid_options:
      columns: full
  - type: heading
    heading: Subwoofer
    heading_style: subtitle
    icon: mdi:speaker-wireless
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_subwoofer_wireless_1
    name: Sub Wireless 1
    icon: mdi:speaker
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(255,\
        \ 87, 34, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_subwoofer_wireless_1') | float(0) + 6)\
        \ / 12 * 100 %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n               \
        \ );\n                border-left: 3px solid rgb(255, 87, 34);\n            }"
    grid_options:
      columns: full
  - type: custom:button-card
    entity: number.klipsch_flexus_core_300_channel_subwoofer_wireless_2
    name: Sub Wireless 2
    icon: mdi:speaker
    show_state: true
    show_name: true
    tap_action:
      action: more-info
    styles:
      card:
      - padding: 2px 8px
      - border-radius: 8px
      - flex-direction: row
      - justify-content: flex-start
      - align-items: center
      - height: 40px
      grid:
      - grid-template-areas: '"i n s"'
      - grid-template-columns: 20px 1fr auto
      - gap: 4px
      icon:
      - width: 14px
      name:
      - font-size: 10px
      - font-weight: '500'
      - justify-self: start
      state:
      - font-size: 10px
      - font-weight: bold
    card_mod:
      style: "ha-card {\n                background: linear-gradient(\n                    90deg,\n                    rgba(255,\
        \ 87, 34, 0.15) {% set v = (states('number.klipsch_flexus_core_300_channel_subwoofer_wireless_2') | float(0) + 6)\
        \ / 12 * 100 %}{{ v }}%,\n                    rgba(var(--rgb-primary-text-color), 0.03) {{ v }}%\n               \
        \ );\n                border-left: 3px solid rgb(255, 87, 34);\n            }"
    grid_options:
      columns: full

```

## License

MIT — feel free to use and modify.
