# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#automatische-erkennung)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | **Deutsch** | [Español](README_es.md) | [Português](README_pt.md) | [Français](README_fr.md) | [Italiano](README_it.md) | [Nederlands](README_nl.md) | [中文](README_zh.md)  
🔒 **Sicherheit**: [Richtlinie](../SECURITY.md) | [Bewertungsbericht](SECURITY_ASSESSMENT_CORE_300.md)

---

Benutzerdefinierte Home Assistant Integration für **Klipsch Flexus** Soundbars — Steuerung über **native lokale HTTP-API**, ohne Cloud, ohne Verzögerungen.

> ✅ **42 Entitäten**. Alle Schreibbefehle sind live auf der Firmware von 2026 verifiziert (HMAC-signiert) und funktionieren auch im Standby. Jeder Commit auf `main` wird zuerst lokal getestet: siehe [Testergebnisse](#testergebnisse).

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

Die Integration prüft das Modell nicht. Sie fügt jede Flexus-Soundbar hinzu, die sich über Google Cast meldet, und nutzt für jedes Modell dieselbe lokale API und dieselben 42 Entitäten. Der Maintainer testet auf einer CORE 300. Ein Regler für Hardware, die Ihr Modell nicht hat (zum Beispiel die Höhenkanäle einer CORE 100), kann mit einer Fehlermeldung fehlschlagen.

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
| Wired Subwoofer / Wireless Subwoofers | Kabel-Sub-Ausgang (RCA) und Funk-Subwoofer (einer oder zwei, gemeinsam geregelt), -12 bis +6 dB |
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
- **Diagnose herunterladen** — vollständiger Gerätestatusdump (Einstellungen > Geräte > Klipsch Flexus > Diagnose herunterladen). IP-Adresse, alle MAC-Adressen, die WLAN-BSSID, die Geräte-ID und Stream-URLs werden unkenntlich gemacht

### Drahtlose Lautsprecher
- **Ein Gerät pro gekoppeltem Lautsprecher** — die Lautsprecher Flexus SUB / SURR (Funk-Subwoofer 1 / 2, Surround links / rechts) erscheinen als eigene Geräte unter der Soundbar, mit den Versionen, die die Klipsch Connect Plus App anzeigt (Product Information): MCU-, RX- und EQ-Firmware als *Firmware*, die Hardwareversion und die Modellnummer
- **Verbunden** — ein Sensor pro Lautsprecher: an, wenn die Funkverbindung des Lautsprechers beim letzten Lesen bestand, aus, wenn sie unterbrochen war
- **Wann sie gelesen werden** — einmal nach der Einrichtung und wenn Sie **Drahtlose Lautsprecher lesen** drücken (ein Button an der Soundbar), sodass die reguläre Abfrage so schlank bleibt wie bisher. Um Aussetzer live zu verfolgen, schalten Sie in den Optionen **Drahtlose Lautsprecher überwachen** ein: Die Verbindung wird dann bei jeder Abfrage gelesen (eine zusätzliche Anfrage), und ein Subwoofer, der aussetzt, ist im Verlauf des Verbunden-Sensors zu sehen. Überwachte Sensoren sind im Standby nicht verfügbar
- Ein Lautsprecher erhält sein Gerät, sobald er einmal verbunden gesehen wurde, und behält es, solange er entkoppelt oder offline ist. Das Gerät eines entkoppelten Lautsprechers kann auf seiner Geräteseite gelöscht werden

### Übersetzungen
Vollständige UI-Übersetzung in **9 Sprachen**: Englisch, Russisch, Deutsch, Spanisch, Französisch, Italienisch, Portugiesisch, Niederländisch, vereinfachtes Chinesisch (`zh-Hans`). Alle Entitätsnamen, Zustände und Konfigurationsbildschirme sind übersetzt.

## Installation

### HACS (empfohlen)

Klipsch Flexus ist im HACS-Standard-Store. Sie müssen also kein benutzerdefiniertes Repository hinzufügen.

[![Öffnen Sie Ihre Home-Assistant-Instanz und dieses Repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. Öffnen Sie Klipsch Flexus mit der Schaltfläche oben in Ihrem HACS (Link über My Home Assistant), oder öffnen Sie **HACS** und suchen Sie **Klipsch Flexus**
2. Wählen Sie **Herunterladen** und starten Sie Home Assistant neu
3. Die Soundbar sollte **automatisch erkannt** werden — prüfen Sie die Benachrichtigungen
4. Oder gehen Sie zu **Einstellungen** > Geräte & Dienste > **Integration hinzufügen** > Klipsch Flexus

### Manuell

1. Kopieren Sie `custom_components/klipsch_flexus/` in das `config/custom_components/`-Verzeichnis Ihres HA
2. Starten Sie Home Assistant neu
3. Fügen Sie die Integration über Einstellungen > Geräte & Dienste hinzu

### Aktualisieren

Nach einem Update der Integration (HACS oder manuell) **Home Assistant neu starten**: HA lädt den Python-Code der Integration beim Start, die neue Version läuft also erst nach einem Neustart. Änderungen in den **Optionen** oder eine **Neukonfiguration** des Hosts wirken sofort, ohne Neustart (der Eintrag wird neu geladen).

### Beta-Versionen

Neue Funktionen und Fehlerbehebungen erscheinen zuerst als **Beta**: ein GitHub-Pre-Release mit dem Tag `vX.Y.Z-beta.N`. Das stabile Release `vX.Y.Z` folgt später. HACS bietet eine Beta nur an, wenn Sie sich dafür entscheiden. Wenn Sie nichts tun, bleiben Sie bei den stabilen Releases und werden über Betas nicht benachrichtigt.

So erhalten Sie Betas (HACS 2.x; hier stehen die englischen Namen, Ihr HACS zeigt sie eventuell übersetzt):

1. Gehen Sie zu **Einstellungen** > Geräte & Dienste > **HACS** und öffnen Sie den Dienst-Eintrag **Klipsch Flexus** (HACS legt einen für jedes heruntergeladene Repository an)
2. Suchen Sie den Schalter **Pre-release** (eine Diagnose-Entität). Er ist standardmäßig deaktiviert: Öffnen Sie ihn, wählen Sie das Zahnrad, aktivieren Sie die Entität und speichern Sie
3. Schalten Sie **Pre-release** ein. HACS bietet jetzt die neueste Beta als Update an. Um sofort zu prüfen, öffnen Sie Klipsch Flexus in HACS und wählen Sie im ⋮-Menü **Update information**
4. Installieren Sie das Update und starten Sie Home Assistant neu

Zurück zu den stabilen Versionen: Schalten Sie **Pre-release** aus. HACS bietet dann wieder nur stabile Releases an, und Sie behalten die Beta, bis das nächste stabile Release sie ersetzt. Um sofort zurückzuwechseln, öffnen Sie Klipsch Flexus in HACS, wählen Sie ⋮ > **Redownload** > **Need a different version?**, wählen Sie das neueste Release ohne die Markierung *pre-release*, laden Sie es herunter und starten Sie Home Assistant neu.

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
| Abfrageintervall | 15 s | Konfigurierbar über Optionen (5–120 s). Im Standby fragt die Integration immer alle 60 s ab |
| Drahtlose Lautsprecher überwachen | aus | Nur in den Optionen. Liest bei jeder Abfrage, ob jeder drahtlose Subwoofer / Surround verbunden ist (eine zusätzliche Anfrage), damit Aussetzer an seinem Sensor **Verbunden** sichtbar werden. Aus: gelesen nach der Einrichtung und mit dem Button **Drahtlose Lautsprecher lesen** |
| Geräte-MAC | automatisch erkannt | Nur in den Optionen (optional). Überschreibt die MAC zum Signieren der Schreibbefehle der 2026-Firmware; nur nötig, wenn Befehle außer Lautstärke/Stummschaltung fehlschlagen (siehe Diagnosesensor **Signing MAC**) |

**Tipp:** Weisen Sie der Soundbar eine statische IP / DHCP-Reservierung zu.

Die IP-Adresse kann später über **Neu konfigurieren** geändert werden (Einstellungen > Geräte > Klipsch Flexus > Neu konfigurieren).

## So funktioniert es

Die Soundbar stellt eine lokale HTTP-API auf Port 80 bereit:
- `GET /api/getData` — Parameter lesen
- `POST /api/setData` — Parameter schreiben (JSON-Body; GET-Fallback für ältere Firmware)
- `GET /api/getRows` — Strukturierte Daten auflisten (Dirac-Filter)

Auf der Firmware von 2026 gehen die HMAC-signierten Schreibbefehle stattdessen an `POST https://<IP>/api/setData`.

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
| Wired Subwoofer / Wireless Subwoofers | Number (x2) | Konfiguration |
| Bass / Mid / Treble | Number (x3) | Konfiguration |
| Lippensynchronisations-Verzögerung, Balance | Number (x2) | Konfiguration |
| Auto-Lippensynchronisation, EQ-Bypass, Auto-Power, UI-Töne, Zusätzliche Klangmodi, BLE-Fernbedienung Auto-Kopplung, Firmware Auto-Update | Switch (x7) | Konfiguration |
| Loudness, Nicht stören, Auto-Standby | Switch (x3) | Konfiguration |
| Antwortzeit, Gerätestatus, Aktiver Eingang, Aktiver Klangmodus | Sensor (x4) | Diagnose |
| Signing MAC, Netzwerkverbindung | Sensor (x2) | Diagnose |
| Betriebsmodus, Lautsprechertest, Sub Wired/Wireless Delay, Surround Delay | Sensor (x5, schreibgeschützt) | Diagnose |
| Drahtlose Lautsprecher lesen | Button | Diagnose |
| Verbunden (auf dem Gerät jedes drahtlosen Lautsprechers) | Binary Sensor (einer pro gekoppeltem Lautsprecher, bis zu 4) | Diagnose |

**Gesamt: 42 Entitäten** (1 Media Player + 6 Selects + 13 Numbers + 10 Switches + 11 Sensors + 1 Button), plus ein Verbunden-Sensor pro gekoppeltem drahtlosem Lautsprecher

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Verbindung nicht möglich | Prüfen Sie, ob die Soundbar im selben Netzwerk ist. Testen Sie: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entitäten nicht verfügbar | Die Klipsch-App pollt möglicherweise gleichzeitig — schließen Sie sie |
| Langsame Updates | Erhöhen Sie das Abfrageintervall in den Optionen |
| Befehle außer Lautstärke/Stummschaltung schlagen fehl | Prüfen Sie den Diagnosesensor **Signing MAC**. Zeigt er keine (oder eine falsche) aufgelöste MAC, tragen Sie die MAC der Soundbar als **Geräte-MAC** in den Optionen ein |
| Integration lädt nicht | Prüfen Sie die HA-Logs auf Importfehler. HA 2024.11+ erforderlich |
| Drahtloser Subwoofer oder Surround setzt aus | Schalten Sie in den Optionen **Drahtlose Lautsprecher überwachen** ein und öffnen Sie dann das Gerät des Lautsprechers unter der Soundbar: Sein Sensor **Verbunden** ist aus, solange die Verbindung unterbrochen ist, und sein Verlauf zeigt, wann sie abgerissen ist. Die Soundbar meldet den Platz dann als leer; das ist also die Sicht der Soundbar auf die Funkverbindung. Ein Lautsprecher, dessen eigene Platine hängt, während die Funkverbindung steht (kein Ton), wird weiter als verbunden angezeigt; das Attribut `mcu_responding` zeigt, ob die Platine beim letzten Lesen geantwortet hat (zum Prüfen **Drahtlose Lautsprecher lesen** drücken). |
| Logo im dunklen Design unsichtbar | Auf v2.5.19+ aktualisieren und HA neu starten. Das Symbol für das dunkle Design ist in der Integration enthalten und braucht HA 2026.3+; ältere HA-Versionen zeigen das schwarze Symbol der HA-Brands-Seite |

## Bekannte Einschränkungen

- Eine Soundbar pro Integrationseintrag (für mehrere separat hinzufügen)
- Kein Multi-Room / drahtlose Surround-Gruppenverwaltung (verwenden Sie Klipsch Connect Plus)
- Gesteuert wird nur über die native HTTP-API, nicht über die Cast- oder AirPlay-Protokolle. Google Cast ist als Eingang wählbar (Wiedergabe aus einer Cast-App starten); AirPlay steht nicht in der Eingangsliste des Geräts und wird daher nicht als Quelle angeboten (Streamen von einem Apple-Gerät zur Soundbar ist davon nicht betroffen)
- Ersteinrichtung muss **vollständig** in der offiziellen Klipsch Connect Plus App erfolgen — die gesamte Ersteinrichtung mindestens einmal durchlaufen (dabei werden die Zugangsdaten für die 2026er-Firmware bereitgestellt)

## Sicherheit

Sicherheitsrichtlinie und Best Practices in [SECURITY.md](../SECURITY.md).

**Hinweis zur Netzwerksicherheit:** Die Soundbar kommuniziert über einfaches HTTP, und ihre lokale API ist im LAN praktisch nicht authentifiziert. Ältere Firmware verlangte überhaupt keine Authentifizierung; die 2026-Firmware (`1.1.3.x`) signiert die meisten Schreibvorgänge (`HMAC_SHA256_AES256`), aber das ist **keine echte Sicherheitsgrenze** — die Anmeldedaten werden aus der MAC des Geräts selbst (die es unauthentifiziert preisgibt) plus einer geräteübergreifend fest einprogrammierten Konstante abgeleitet, sodass jeder Host im Netzwerk sie fälschen kann. Lesezugriffe bleiben offen. **Betreiben Sie die Soundbar in einem vertrauenswürdigen / isolierten Netzwerksegment.** Vollständige Analyse im [Sicherheitsbewertungsbericht](SECURITY_ASSESSMENT_CORE_300.md) (Abschnitt 12).

## Testergebnisse

[![pytest, aktuelles Home Assistant](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest, ältestes unterstütztes Home Assistant](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![Signierte lokale CI](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

Alle Tests laufen auf dem Rechner des Maintainers, nicht auf GitHub. Die ersten fünf Badges zeigen die Ergebnisse dieses signierten lokalen Laufs für den neuesten geprüften Commit auf `main` (das Badge *Signed local CI* zeigt seinen kurzen SHA und sein Datum). GitHub schreibt sie erst, nachdem es die signierten Nachweise geprüft hat. *Verify signed local CI* ist diese Prüfung auf GitHub. *HACS validation* ist die HACS-Prüfung des Repositorys, die auf GitHub läuft.

Sie können die Nachweise selbst prüfen (Python 3.11 oder neuer, git, OpenSSH):

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` enthält den öffentlichen Signaturschlüssel des Maintainers. Vergleichen Sie ihn mit den SSH-Signaturschlüsseln, die GitHub für den Maintainer auflistet: `curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`. Details in [TESTING.md](TESTING.md#test-result-badges) (auf Englisch).

## Mitwirkende

Danke an alle, die Probleme melden und Korrekturen beisteuern:

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — hat entdeckt, dass die Lautstärke der Soundbar von 0 bis 50 statt bis 100 reicht, und die Umrechnung korrigiert ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — hat den entfernten Media-Player-Zustand `STANDBY` ersetzt, damit die Integration ab Home Assistant 2026.12 weiter funktioniert ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Siehe die [vollständige Liste der Mitwirkenden](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Mitmachen und Hilfe

- **Fragen und Ideen**: [GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions). Was Sie angeben sollten, steht in [SUPPORT.md](../SUPPORT.md).
- **Fehler**: Eröffnen Sie ein [Issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose) mit dem Fehlerformular und hängen Sie die Diagnose an.
- **Sicherheitsprobleme**: Melden Sie sie vertraulich, siehe [SECURITY.md](../SECURITY.md).
- **Pull Requests** sind willkommen. [CONTRIBUTING.md](../CONTRIBUTING.md) erklärt, wie Sie Ihre Änderung testen und wie der Maintainer sie prüft. [TESTING.md](TESTING.md) beschreibt die Tests und die signierte lokale CI.
- Alle Beteiligten halten sich an den [Verhaltenskodex](../CODE_OF_CONDUCT.md).

## Lizenz

MIT — siehe [LICENSE](../LICENSE).
