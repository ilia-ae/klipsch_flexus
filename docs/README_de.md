# Klipsch Flexus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#automatische-erkennung)

[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | **Deutsch** | [Español](README_es.md) | [Português](README_pt.md)

---

Benutzerdefinierte Home Assistant Integration für **Klipsch Flexus** Soundbars — Steuerung über **native lokale HTTP-API**, ohne Cloud, ohne Verzögerungen.

> ✅ **41 Entitäten**, alle Schreibbefehle live gegen die Firmware von 2026 verifiziert (HMAC-signiert), auch im Standby steuerbar. Die Badges oben spiegeln das aktuelle Release und den letzten Push wider.

## 📸 Dashboard

Ein eigenes Lovelace-Dashboard, komplett auf den Entitäten der Integration — Eingang, Sound-Modus, Nacht/Dialog, EQ-Presets, Dirac-Filter, Klang (Bass/Mitten/Höhen), Surround-Kanalpegel und Subwoofer — alles live über die lokale API.

![Klipsch Flexus Dashboard](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**Benötigte HACS-Komponenten** (alle über [HACS](https://github.com/hacs/integration) installierbar):

| Komponente | Repo | Wofür |
|------------|------|-------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | diese Integration — die Entitäten |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | Media-Player-Karte |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | Eingang-/Modus-/EQ-Kacheln mit dynamischem Styling |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | Hervorhebung des aktiven Zustands (CSS) |

📋 **Vollständiges Dashboard-YAML + Farbschema:** [docs/DASHBOARD.md](DASHBOARD.md)

### Unterstützte Modelle

| Modell | Kanäle | Funktionen |
|--------|--------|------------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 Treiber |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

> Die Soundbar muss zuerst **vollständig in der offiziellen Klipsch Connect Plus App eingerichtet werden** — durchlaufen Sie die gesamte Ersteinrichtung mindestens einmal (WLAN, Firmware-Update, Lautsprecher-Kopplung, Dirac-Kalibrierung). Auf der 2026er-Firmware werden dabei auch die Zugangsdaten zum Signieren der Befehle bereitgestellt, sodass eine unvollständige Einrichtung die meisten Befehle ohne Autorisierung lässt. Diese Integration übernimmt nur die laufende Steuerung.

## ⚠️ Firmware-Kompatibilität (Update 2026)

Ein Firmware-Update von 2026 (**Device Version `1.1.3.x`**, z. B. `1.1.3.0x7cd294e`, Cast-Build `20250512_0201_RC25`) hat die lokale HTTP-API auf zwei Arten geändert:

1. **`setData` erfordert jetzt `POST` mit JSON-Body.** Das alte `GET /api/setData?...` liefert `405 Strict HTTP required!`. **Behoben in v2.4.1** — Integration aktualisieren.
2. **Die meisten `setData`-Schreibvorgänge sind jetzt authentifiziert** (`settings:/webserver/authMode = setData`). Geschützte Befehle antworten mit `401 Forbidden` und `WWW-Authenticate: HMAC_SHA256_AES256`. **Behoben in v2.5.0** — die Integration signiert diese Schreibvorgänge jetzt automatisch.

### Was mit der neuen Firmware funktioniert

| Funktion | Status |
|----------|--------|
| Alle Sensoren / Status-Lesevorgänge (`getData`) | ✅ Funktioniert |
| Lautstärke, Stummschaltung | ✅ Funktioniert |
| Eingang, Sound-Modus, Nacht/Dialog, Bass/Mitten/Höhen, EQ-Preset, Dirac, Subwoofer- & Surround-Pegel, Power | ✅ Funktioniert (HMAC-signiert, ab v2.5.0) |
| LED, Lippensynchronisation, Balance, Loudness, Nicht stören, Auto-Standby + 4 weitere Schalter | ✅ Funktioniert (signiert; hinzugefügt in v2.5.8–2.5.9) — auch im Standby |

Den Live-Status pro Befehl zeigt **Download diagnostics** (Abschnitt `command_health`, hinzugefügt in v2.4.2). Er liest nur: pro Befehl zeigt er, ob die Einstellung lesbar ist und wie das Gerät auf die Schreibvorgänge seit dem letzten Laden der Integration geantwortet hat (`http_status`, `needs_auth`, wenn das Gerät eine Signatur verlangt hat).

### Status der Lösung

✅ **Gelöst in v2.5.0 — volle Steuerung wiederhergestellt, keine Benutzeraktion erforderlich.** Die `HMAC_SHA256_AES256`-Signierung ist jetzt implementiert. Die gerätespezifischen Anmeldedaten werden automatisch aus der MAC-Adresse der Soundbar abgeleitet (die die Integration ohnehin ermittelt), daher ist **nichts zu konfigurieren** — einfach die Integration aktualisieren. Seit **v2.5.9** wird die MAC-Adresse deterministisch direkt vom Gerät gelesen (`settings:/system/primaryMacAddress`), sodass die Auflösung bei jedem Gerät bereits im ersten Versuch gelingt (die bisherige Registry-/ARP-Erkennung bleibt als Fallback erhalten). Signierte Schreibvorgänge gehen an den HTTPS-Endpunkt des Geräts; Lautstärke/Stummschaltung funktionieren weiterhin ohne Signatur.

> Erfordert das Paket `cryptography` (mit Home Assistant gebündelt, also bereits vorhanden; nicht als Anforderung im Manifest aufgeführt).

📖 **Wie wir es reverse-engineered haben** — die ganze Story der Untersuchung (blutter, Frida, WireGuard-MITM, die „Security-Theater"-Analyse): [Field Report](REPORT_en.md) (auf Englisch; russisch: [REPORT.md](REPORT.md)).

Ältere Firmware (vor `1.1.3`) ist nicht betroffen und behält die volle Steuerung über den `GET`-Fallback.

## Funktionen

### Media Player
- **Lautstärke** — Pegel einstellen, schrittweise erhöhen/verringern, Stummschaltung
- **Ein/Aus** — Einschalten / Ausschalten (Netzwerk-Standby)
- **Eingangsquelle** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast. Ist eine Streaming-App (Spotify Connect, TIDAL Connect, QPlay), USB oder die Dirac-Kalibrierung aktiv, zeigt die Quelle dies an
- **Klangmodus** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Wiedergabe** — Play/Pause, nächster/vorheriger Titel
- **Medien-Info** — Titel, Künstler, Album, Cover, Quell-App

### Kanalpegel (11 Regler: 9 von -6 bis +6 dB, 2 Subwoofer von -12 bis +6 dB)

| Kanal | Beschreibung |
|-------|-------------|
| Front Height | Dolby Atmos vorderer Höhenlautsprecher |
| Back Height | Dolby Atmos hinterer Höhenlautsprecher |
| Side Left / Right | Surround-Seitenlautsprecher |
| Back Left / Right | Surround-Rücklautsprecher |
| Subwoofer Wireless 1 / 2 | Subwoofer-Pegel (-12 bis +6 dB) |
| Bass / Mid / Treble | Klangregelung |

### Audio-Einstellungen (Selects)
- **EQ-Voreinstellung** — Flat, Bass, Rock, Vocal (+ Custom, gemeldet, sobald Bass / Mid / Treble geändert werden — in HA oder in der Klipsch-App — oder in der App eine eigene Kurve eingestellt ist; in HA nicht auswählbar)
- **Nachtmodus** — reduziert den Dynamikbereich für leises Hören
- **Dialogmodus** — verbessert die Sprachklarheit (3 Stufen)
- **Dirac Live** — Raumkorrekturfilter (automatisch vom Gerät erkannt)
- **LED-Helligkeit** — Front-LED: Aus / Gedimmt / Hell
- **Leerlauf-Timeout** — Leerlaufzeit bis zum automatischen Standby: Aus / 5 / 10 / 15 / 30 min

### Einstellungen (Numbers)
- **Lippensynchronisations-Verzögerung** — manuelle A/V-Synchronisation (0–500 ms)
- **Balance** — Links/Rechts-Balance (−10…+10 dB)

### Schalter (Switches)
- **Auto-Lippensynchronisation** — automatische A/V-Verzögerung
- **EQ-Bypass** — Equalizer umgehen
- **Auto-Power** — automatisches Ein-/Standby-Verhalten
- **Loudness** — Loudness-Kompensation bei geringer Lautstärke
- **Nicht stören** — Benachrichtigungen/Töne unterdrücken
- **Auto-Standby** — bei Leerlauf in den Standby wechseln
- **UI-Töne**, **Zusätzliche Klangmodi**, **BLE-Fernbedienung Auto-Kopplung**, **Firmware Auto-Update**

> Alle oben genannten Einstellungen lassen sich auch schreiben, während sich die Soundbar im **Standby** befindet (das Gerät übernimmt und speichert sie dauerhaft); die Integration hält die Entitäten verfügbar und merkt sich den von Ihnen gesetzten Wert, anstatt ihn zurückzusetzen.

### Diagnose
- **Antwortzeit** — API-Abfragedauer in ms, Anfrage-/Fehlerzähler
- **Gerätestatus** — Ein / Standby / Offline mit Decoder-, Eingangs- und Klangmodus-Info
- **Signing MAC** — die MAC-Adresse zum Signieren der Schreibvorgänge der 2026-Firmware (Schema, Kandidaten, aufgelöster Zustand)
- **Netzwerkverbindung** — aktive kabelgebundene/drahtlose Schnittstelle, Schnittstellennamen, MAC-Quellen
- **Betriebsmodus** / **Lautsprechertest** — schreibgeschützter Gerätezustand (sichtbar gemacht, bewusst nicht steuerbar)
- **Lautsprecher-Verzögerungen** (kabelgebundener/drahtloser Subwoofer, drahtloser Surround) — schreibgeschützt, vom Gerät automatisch kalibriert
- **Diagnose herunterladen** — vollständiger Gerätestatusdump (Einstellungen > Geräte > Klipsch Flexus > Diagnose herunterladen)

### Übersetzungen
Vollständige UI-Übersetzung in **7 Sprachen**: Englisch, Russisch, Deutsch, Spanisch, Französisch, Italienisch, Portugiesisch. Alle Entitätsnamen, Zustände und Konfigurationsbildschirme sind übersetzt.

## Installation

### HACS (empfohlen)

1. Öffnen Sie **HACS** > Integrationen > suchen Sie **Klipsch Flexus**
2. Herunterladen und Home Assistant neu starten
3. Die Soundbar sollte **automatisch erkannt** werden — prüfen Sie die Benachrichtigungen
4. Oder gehen Sie zu **Einstellungen** > Geräte & Dienste > **Integration hinzufügen** > Klipsch Flexus

### Manuell

1. Kopieren Sie `custom_components/klipsch_flexus/` in das `config/custom_components/`-Verzeichnis Ihres HA
2. Starten Sie Home Assistant neu
3. Fügen Sie die Integration über Einstellungen > Geräte & Dienste hinzu

### Aktualisieren

Nach einem Update der Integration (HACS oder manuell) **Home Assistant neu starten**: HA lädt den Python-Code der Integration beim Start, die neue Version läuft also erst nach einem Neustart. Änderungen in den **Optionen** oder eine **Neukonfiguration** des Hosts wirken sofort, ohne Neustart (der Eintrag wird neu geladen).

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
| Geräte-MAC | automatisch erkannt | Nur in den Optionen (optional). Überschreibt die MAC zum Signieren der Schreibbefehle der 2026-Firmware; nur nötig, wenn Befehle außer Lautstärke/Stummschaltung fehlschlagen (siehe Diagnosesensor **Signing MAC**) |

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
| Wiederholung mit Verzögerung | Schreibvorgänge (außer Mediensteuerung) und die Energiezustandsabfrage werden 2x mit 0,5 s Verzögerung wiederholt; Lesevorgänge des Pollings nicht (zuletzt bekannter Wert), und zwei Timeouts in Folge beenden das Polling als offline |
| Adaptive Timeouts | 8 s Lesen, 10 s Schreiben, 15 s Ein/Aus-Befehle |
| Graceful Degradation | Fehlgeschlagene Lesevorgänge verwenden zuletzt bekannte Werte |
| Optimistische Updates | UI aktualisiert sofort und behält den geschriebenen Wert bis zum nächsten regulären Polling, das ihn zurückliest (das Polling ~1 s nach einem Befehl holt dessen Nebenwirkungen, z. B. den Decoder nach einem Eingangswechsel); im Standby angewendete Werte werden zwischengespeichert, sodass das Standby-Polling sie nie zurücksetzt |
| **Standby-bewusstes Polling** | Energiezustand wird zuerst abgefragt; das erste Polling nach dem Setup liest einmal alles, auch im Standby — danach im Standby nur 1 Anfrage statt ~40, zwischengespeicherte Werte bleiben erhalten, Abfrageintervall auf 60 s reduziert. Einstellungen bleiben im Standby **verfügbar und steuerbar** — das Gerät übernimmt die Schreibvorgänge und die Integration merkt sie sich |

## Entitäten

![Klipsch Flexus Geräteseite in Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*Die Geräteseite in Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + Schalter) und das Aktivitätsprotokoll.*

| Entität | Typ | Kategorie |
|---------|-----|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Nachtmodus / Dialogmodus / EQ-Voreinstellung / Dirac-Filter / LED-Helligkeit / Leerlauf-Timeout | Select (x6) | Konfiguration |
| Back Height / Left / Right, Front Height, Side Left / Right | Number (x6) | Konfiguration |
| Subwoofer Wireless 1 / 2 | Number (x2) | Konfiguration |
| Bass / Mid / Treble | Number (x3) | Konfiguration |
| Lippensynchronisations-Verzögerung, Balance | Number (x2) | Konfiguration |
| Auto-Lippensynchronisation, EQ-Bypass, Auto-Power, UI-Töne, Zusätzliche Klangmodi, BLE-Fernbedienung Auto-Kopplung, Firmware Auto-Update | Switch (x7) | Konfiguration |
| Loudness, Nicht stören, Auto-Standby | Switch (x3) | Konfiguration |
| Antwortzeit, Gerätestatus, Aktiver Eingang, Aktiver Klangmodus | Sensor (x4) | Diagnose |
| Signing MAC, Netzwerkverbindung | Sensor (x2) | Diagnose |
| Betriebsmodus, Lautsprechertest, Sub Wired/Wireless Delay, Surround Delay | Sensor (x5, schreibgeschützt) | Diagnose |

**Gesamt: 41 Entitäten** (1 Media Player + 6 Selects + 13 Numbers + 10 Switches + 11 Sensors)

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Verbindung nicht möglich | Prüfen Sie, ob die Soundbar im selben Netzwerk ist. Testen Sie: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entitäten nicht verfügbar | Die Klipsch-App pollt möglicherweise gleichzeitig — schließen Sie sie |
| Langsame Updates | Erhöhen Sie das Abfrageintervall in den Optionen |
| Befehle außer Lautstärke/Stummschaltung schlagen fehl | Prüfen Sie den Diagnosesensor **Signing MAC**. Zeigt er keine (oder eine falsche) aufgelöste MAC, tragen Sie die MAC der Soundbar als **Geräte-MAC** in den Optionen ein |
| Integration lädt nicht | Prüfen Sie die HA-Logs auf Importfehler. HA 2024.11+ erforderlich |
| Logo im dunklen Design unsichtbar | Auf v2.5.19+ aktualisieren und HA neu starten. Das Symbol für das dunkle Design ist in der Integration enthalten und braucht HA 2026.3+; ältere HA-Versionen zeigen das schwarze Symbol der HA-Brands-Seite |

## Bekannte Einschränkungen

- Eine Soundbar pro Integrationseintrag (für mehrere separat hinzufügen)
- Kein Multi-Room / drahtlose Surround-Gruppenverwaltung (verwenden Sie Klipsch Connect Plus)
- Gesteuert wird nur über die native HTTP-API, nicht über die Cast- oder AirPlay-Protokolle. Google Cast ist als Eingang wählbar (Wiedergabe aus einer Cast-App starten); AirPlay steht nicht in der Eingangsliste des Geräts und wird daher nicht als Quelle angeboten (Streamen von einem Apple-Gerät zur Soundbar ist davon nicht betroffen)
- Ersteinrichtung muss **vollständig** in der offiziellen Klipsch Connect Plus App erfolgen — die gesamte Ersteinrichtung mindestens einmal durchlaufen (dabei werden die Zugangsdaten für die 2026er-Firmware bereitgestellt)

## Sicherheit

Sicherheitsrichtlinie und Best Practices in [SECURITY.md](../SECURITY.md).

**Hinweis zur Netzwerksicherheit:** Die Soundbar kommuniziert über einfaches HTTP, und ihre lokale API ist im LAN praktisch nicht authentifiziert. Ältere Firmware verlangte überhaupt keine Authentifizierung; die 2026-Firmware (`1.1.3.x`) signiert die meisten Schreibvorgänge (`HMAC_SHA256_AES256`), aber das ist **keine echte Sicherheitsgrenze** — die Anmeldedaten werden aus der MAC des Geräts selbst (die es unauthentifiziert preisgibt) plus einer geräteübergreifend fest einprogrammierten Konstante abgeleitet, sodass jeder Host im Netzwerk sie fälschen kann. Lesezugriffe bleiben offen. **Betreiben Sie die Soundbar in einem vertrauenswürdigen / isolierten Netzwerksegment.** Vollständige Analyse im [Sicherheitsbewertungsbericht](SECURITY_ASSESSMENT_CORE_300.md) (Abschnitt 12).

## Mitwirkende

Danke an alle, die Probleme melden und Korrekturen beisteuern:

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — hat entdeckt, dass die Lautstärke der Soundbar von 0 bis 50 statt bis 100 reicht, und die Umrechnung korrigiert ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — hat den entfernten Media-Player-Zustand `STANDBY` ersetzt, damit die Integration ab Home Assistant 2026.12 weiter funktioniert ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Issues und Pull Requests sind willkommen — siehe die [vollständige Liste der Mitwirkenden](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Lizenz

MIT — siehe [LICENSE](../LICENSE).
