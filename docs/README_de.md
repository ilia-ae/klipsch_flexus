# Klipsch Flexus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/razqqm/klipsch_flexus.svg?style=for-the-badge)](https://github.com/razqqm/klipsch_flexus/releases)
[![License](https://img.shields.io/github/license/razqqm/klipsch_flexus.svg?style=for-the-badge)](LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#automatische-erkennung)

[![Validate](https://github.com/razqqm/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/razqqm/klipsch_flexus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/hassfest.yaml)
[![CI](https://github.com/razqqm/klipsch_flexus/actions/workflows/ci.yaml/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/razqqm/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/razqqm/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | **Deutsch** | [Español](README_es.md) | [Português](README_pt.md)

---

Benutzerdefinierte Home Assistant Integration für **Klipsch Flexus** Soundbars — Steuerung über **native lokale HTTP-API**, ohne Cloud, ohne Verzögerungen.

### Unterstützte Modelle

| Modell | Kanäle | Funktionen |
|--------|--------|------------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 Treiber |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

> Die Soundbar muss vorab über die offizielle Klipsch Connect Plus App eingerichtet werden (WLAN, Firmware, Lautsprecher-Kopplung, Dirac-Kalibrierung). Diese Integration übernimmt nur die laufende Steuerung.

## ⚠️ Firmware-Kompatibilität (Update 2026)

Ein Firmware-Update von 2026 (**Device Version `1.1.3.x`**, z. B. `1.1.3.0x7cd294e`, Cast-Build `20250512_0201_RC25`) hat die lokale HTTP-API auf zwei Arten geändert:

1. **`setData` erfordert jetzt `POST` mit JSON-Body.** Das alte `GET /api/setData?...` liefert `405 Strict HTTP required!`. **Behoben in v2.4.1** — Integration aktualisieren.
2. **Die meisten `setData`-Schreibvorgänge sind jetzt authentifiziert** (`settings:/webserver/authMode = setData`). Geschützte Befehle antworten mit `401 Forbidden` und `WWW-Authenticate: HMAC_SHA256_AES256`.

### Was mit der neuen Firmware funktioniert

| Funktion | Status |
|----------|--------|
| Alle Sensoren / Status-Lesevorgänge (`getData`) | ✅ Funktioniert |
| Lautstärke, Stummschaltung | ✅ Funktioniert (weiterhin ohne Auth) |
| Eingang, Sound-Modus, Nacht/Dialog, Bass/Mitten/Höhen, EQ-Preset, Dirac, Subwoofer- & Surround-Pegel, Power | ❌ `401` — durch Firmware-Auth blockiert |

Den Live-Status pro Befehl zeigt **Download diagnostics** (Abschnitt `command_health`, hinzugefügt in v2.4.2).

### Status der Lösung

🚧 **Noch keine fertige Lösung — in Arbeit.** Volle Steuerung erfordert die Implementierung der `HMAC_SHA256_AES256`-Signierung. Das Signaturgeheimnis wird von der offiziellen App bereitgestellt und ist noch nicht identifiziert (kein Benutzerpasswort gesetzt, Geräte-Weboberfläche deaktiviert, daher funktioniert der Fall mit leerem Passwort nicht). Bis dahin bleiben Lesevorgänge und Lautstärke/Stummschaltung funktionsfähig.

Ältere Firmware (vor `1.1.3`) ist nicht betroffen und behält die volle Steuerung über den `GET`-Fallback.

## Funktionen

### Media Player
- **Lautstärke** — Pegel einstellen, schrittweise erhöhen/verringern, Stummschaltung
- **Ein/Aus** — Einschalten / Standby
- **Eingangsquelle** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast
- **Klangmodus** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Wiedergabe** — Play/Pause, nächster/vorheriger Titel
- **Medien-Info** — Titel, Künstler, Album, Cover, Quell-App

### Kanalpegel (11 Regler, -6 bis +6 dB)

| Kanal | Beschreibung |
|-------|-------------|
| Front Height | Dolby Atmos vorderer Höhenlautsprecher |
| Back Height | Dolby Atmos hinterer Höhenlautsprecher |
| Side Left / Right | Surround-Seitenlautsprecher |
| Back Left / Right | Surround-Rücklautsprecher |
| Subwoofer Wireless 1 / 2 | Drahtlose Subwoofer-Pegel |
| Bass / Mid / Treble | Klangregelung |

### Audio-Einstellungen (Selects)
- **EQ-Voreinstellung** — Flat, Bass, Rock, Vocal
- **Nachtmodus** — reduziert den Dynamikbereich für leises Hören
- **Dialogmodus** — verbessert die Sprachklarheit (3 Stufen)
- **Dirac Live** — Raumkorrekturfilter (automatisch vom Gerät erkannt)

### Diagnose
- **Antwortzeit** — API-Abfragedauer in ms, Anfrage-/Fehlerzähler
- **Gerätestatus** — Ein / Standby / Offline mit Decoder-, Eingangs- und Klangmodus-Info
- **Diagnose herunterladen** — vollständiger Gerätestatusdump (Einstellungen > Geräte > Klipsch Flexus > Diagnose herunterladen)

### Übersetzungen
Vollständige UI-Übersetzung in **7 Sprachen**: Englisch, Russisch, Deutsch, Spanisch, Französisch, Italienisch, Portugiesisch. Alle Entitätsnamen, Zustände und Konfigurationsbildschirme sind übersetzt.

## Installation

### HACS (empfohlen)

1. Öffnen Sie **HACS** > Integrationen > suchen Sie **Klipsch Flexus**
2. Installieren und Home Assistant neu starten
3. Die Soundbar sollte **automatisch erkannt** werden — prüfen Sie die Benachrichtigungen
4. Oder gehen Sie zu **Einstellungen** > Geräte & Dienste > **Integration hinzufügen** > Klipsch Flexus

### Manuell

1. Kopieren Sie `custom_components/klipsch_flexus/` in das `config/custom_components/`-Verzeichnis Ihres HA
2. Starten Sie Home Assistant neu
3. Fügen Sie die Integration über Einstellungen > Geräte & Dienste hinzu

## Automatische Erkennung

Die Soundbar wird automatisch in Ihrem Netzwerk über **mDNS / Zeroconf** (Google Cast Protokoll) erkannt.

Bei eingeschalteter Soundbar zeigt Home Assistant eine Benachrichtigung an:
> **Klipsch Flexus CORE 300** unter `192.168.1.100` gefunden. Möchten Sie diese Soundbar hinzufügen?

**So funktioniert es:**
- Die Soundbar meldet sich als `Flexus-Core-*` über den `_googlecast._tcp` mDNS-Dienst an
- Die Integration identifiziert das Gerät anhand der TXT-Einträge `md` (Modell) und `fn` (Name)
- AirCast-Proxy-Geräte werden automatisch herausgefiltert

Falls die automatische Erkennung nicht funktioniert (z.B. Netzwerkisolation), können Sie die Integration jederzeit manuell durch Eingabe der IP-Adresse hinzufügen.

## Konfiguration

| Parameter | Standard | Beschreibung |
|-----------|----------|-------------|
| Host | — | IP-Adresse der Soundbar (erforderlich) |
| Abfrageintervall | 15 s (60 s im Standby) | Konfigurierbar über Optionen (5–120 s); wird im Standby automatisch reduziert |

**Tipp:** Weisen Sie der Soundbar eine statische IP / DHCP-Reservierung zu.

Die IP-Adresse kann später über **Neu konfigurieren** geändert werden (Einstellungen > Geräte > Klipsch Flexus > Neu konfigurieren).

## So funktioniert es

Die Soundbar stellt eine lokale HTTP-API auf Port 80 bereit:
- `GET /api/getData` — Parameter lesen
- `POST /api/setData` — Parameter schreiben (JSON-Body; GET-Fallback für ältere Firmware)
- `GET /api/getRows` — Strukturierte Daten auflisten (Dirac-Filter)

### Robustes Design für ein langsames Gerät

Die Klipsch Flexus hat einen **Single-Thread HTTP-Server**, der jeweils eine Anfrage verarbeitet. Die Integration ist um diese Einschränkung herum gebaut:

| Mechanismus | Beschreibung |
|------------|-------------|
| Anfrage-Serialisierung | Alle API-Aufrufe laufen über `asyncio.Lock` — keine parallelen Anfragen |
| Wiederholung mit Verzögerung | Vorübergehende Fehler werden 2x mit 0,5 s Verzögerung wiederholt |
| Adaptive Timeouts | 8 s Lesen, 10 s Schreiben, 15 s Ein/Aus-Befehle |
| Graceful Degradation | Fehlgeschlagene Lesevorgänge verwenden zuletzt bekannte Werte |
| Optimistische Updates | UI aktualisiert sofort, dann durch verzögertes Polling bestätigt |
| **Standby-bewusstes Polling** | Energiezustand wird zuerst abgefragt; im Standby nur 1 Anfrage statt 20+, zwischengespeicherte Werte bleiben erhalten, Abfrageintervall auf 60 s reduziert |

## Entitäten

| Entität | Typ | Kategorie |
|---------|-----|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Nachtmodus | Select | Konfiguration |
| Dialogmodus | Select | Konfiguration |
| EQ-Voreinstellung | Select | Konfiguration |
| Dirac-Filter | Select | Konfiguration |
| Back Height / Left / Right | Number (x3) | Konfiguration |
| Front Height | Number | Konfiguration |
| Side Left / Right | Number (x2) | Konfiguration |
| Subwoofer Wireless 1 / 2 | Number (x2) | Konfiguration |
| Bass / Mid / Treble | Number (x3) | Konfiguration |
| Antwortzeit | Sensor | Diagnose |
| Gerätestatus | Sensor | Diagnose |
| Aktiver Eingang | Sensor | Diagnose |
| Aktiver Klangmodus | Sensor | Diagnose |

**Gesamt: 20 Entitäten** (1 Media Player + 4 Selects + 11 Numbers + 4 Sensors)

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Verbindung nicht möglich | Prüfen Sie, ob die Soundbar im selben Netzwerk ist. Testen Sie: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entitäten nicht verfügbar | Die Klipsch-App pollt möglicherweise gleichzeitig — schließen Sie sie |
| Langsame Updates | Erhöhen Sie das Abfrageintervall in den Optionen |
| Integration lädt nicht | Prüfen Sie die HA-Logs auf Importfehler. HA 2024.4.0+ erforderlich |

## Legacy-Version (ohne Custom Integration)

Wenn Sie keine Custom Integration installieren möchten, finden Sie im Ordner [`legacy/`](../legacy/) eine eigenständige Variante mit integrierten HA-Komponenten (`command_line` Sensor + `rest_command` + Skripte).

Dies war die ursprüngliche Implementierung vor der Erstellung der Integration. Sie bietet grundlegende Lautstärke-/Eingangs-/Modus-Steuerung über Dashboard-Buttons, jedoch ohne Media-Player-Entity, Wiedergabesteuerung, automatische Erkennung und Übersetzungen. Siehe [`legacy/README.md`](../legacy/README.md).

## Bekannte Einschränkungen

- Eine Soundbar pro Integrationseintrag (für mehrere separat hinzufügen)
- Kein Multi-Room / drahtlose Surround-Gruppenverwaltung (verwenden Sie Klipsch Connect Plus)
- AirPlay und Cast werden nicht verwendet — nur die native HTTP-API
- Ersteinrichtung erfordert die offizielle Klipsch Connect Plus App

## Lizenz

MIT — siehe [LICENSE](../LICENSE).
