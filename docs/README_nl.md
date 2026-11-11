# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#automatische-detectie)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | [Español](README_es.md) | [Português](README_pt.md) | [Français](README_fr.md) | [Italiano](README_it.md) | **Nederlands** | [中文](README_zh.md)  
🔒 **Beveiliging**: [Beleid](../SECURITY.md) | [Beoordelingsrapport](SECURITY_ASSESSMENT_CORE_300.md)

---

Aangepaste Home Assistant-integratie voor **Klipsch Flexus**-soundbars — bediening via de **eigen lokale HTTP-API**, zonder cloud, zonder vertraging.

> ✅ **42 entiteiten**. Alle schrijfopdrachten zijn live geverifieerd op de firmware van 2026 (HMAC-ondertekend) en werken ook in stand-by. Elke commit op `main` wordt eerst lokaal getest: zie [Testresultaten](#testresultaten).

## 📸 Dashboard

Een eigen Lovelace-dashboard dat volledig draait op de entiteiten van de integratie — ingang, geluidsmodus, nacht- / dialoogverbetering, EQ-voorinstellingen, Dirac-filter, toon (lage tonen / middentonen / hoge tonen), surroundkanaalniveaus en subwoofers — alles live bediend via de lokale API.

![Klipsch Flexus-dashboard](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**Benodigde HACS-componenten** (allemaal te installeren via [HACS](https://github.com/hacs/integration)):

| Component | Repo | Gebruikt voor |
|-----------|------|---------------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | deze integratie — de entiteiten |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | mediaspelerkaart |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | tegels voor bron / modus / EQ met dynamische opmaak |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | markering van de actieve status (CSS) |

📋 **Volledige dashboard-YAML + kleurenschema:** [docs/DASHBOARD.md](DASHBOARD.md)

### Ondersteunde modellen

| Model | Kanalen | Functies |
|-------|---------|----------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 drivers |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

De integratie controleert het model niet. Ze voegt elke Flexus-soundbar toe die zich via Google Cast aanmeldt, en gebruikt voor elk model dezelfde lokale API en dezelfde 42 entiteiten. De maintainer test op een CORE 300. Een bedieningselement voor hardware die jouw model niet heeft (bijvoorbeeld de hoogtekanalen op een CORE 100) kan met een foutmelding mislukken.

> De soundbar moet **eerst volledig zijn ingesteld in de officiële Klipsch Connect Plus-app** — doorloop de volledige onboarding minstens één keer (wifi, firmware-update, luidsprekers koppelen, Dirac-kalibratie). Op de firmware van 2026 worden daarbij ook de toegangsgegevens voor het ondertekenen van schrijfopdrachten ingericht waar de integratie op vertrouwt; een half afgeronde installatie in de app laat de meeste opdrachten dus zonder autorisatie. Deze integratie verzorgt alleen de doorlopende bediening.

## ⚠️ Firmwarecompatibiliteit (update 2026)

Een firmware-update voor de soundbar uit 2026 (**Device Version `1.1.3.x`**, bijv. `1.1.3.0x7cd294e`, Cast-build `20250512_0201_RC25`) heeft de lokale HTTP-API op twee punten veranderd:

1. **`setData` vereist nu `POST` met een JSON-body.** De oude `GET /api/setData?...` geeft `405 Strict HTTP required!` terug. **Opgelost in v2.4.1** — werk de integratie bij.
2. **De meeste `setData`-schrijfacties zijn nu geauthenticeerd** (`settings:/webserver/authMode = setData`). Beschermde schrijfacties geven `401 Forbidden` terug met `WWW-Authenticate: HMAC_SHA256_AES256`. **Opgelost in v2.5.0** — de integratie ondertekent deze schrijfacties nu automatisch.

### Wat werkt op de nieuwe firmware

| Functie | Status |
|---------|--------|
| Alle sensoren / statusuitlezingen (`getData`) | ✅ Werkt |
| Volume, dempen | ✅ Werkt |
| Ingang, geluidsmodus, nacht / dialoog, lage / midden- / hoge tonen, EQ-voorinstelling, Dirac, subwoofer- & surroundniveaus, aan/uit | ✅ Werkt (HMAC-ondertekend, v2.5.0+) |
| LED, lipsync, balans, loudness, niet storen, automatische stand-by + nog 4 schakelaars | ✅ Werkt (ondertekend; toegevoegd in v2.5.8–2.5.9) — ook in stand-by |

De live status per opdracht op je eigen apparaat zie je via **Diagnostiek downloaden** (de sectie `command_health`, toegevoegd in v2.4.2). Die is alleen-lezen: per opdracht toont ze of de instelling leesbaar is en hoe het apparaat heeft gereageerd op de schrijfacties sinds de integratie voor het laatst is geladen (`http_status`, `needs_auth` als het apparaat om een handtekening vroeg).

### Status van de oplossing

✅ **Opgelost in v2.5.0 — volledige bediening hersteld, geen actie van de gebruiker nodig.** Het ondertekenen van verzoeken met `HMAC_SHA256_AES256` is nu geïmplementeerd. De toegangsgegevens per apparaat worden automatisch afgeleid van het MAC-adres van de soundbar, dus er valt **niets te configureren** — werk de integratie gewoon bij. Sinds **v2.5.9** wordt het MAC-adres deterministisch van het apparaat zelf gelezen (`settings:/system/primaryMacAddress`), zodat het bij elk exemplaar meteen bij de eerste poging wordt gevonden (de eerdere detectie via register/ARP blijft als fallback behouden). Ondertekende schrijfacties gaan naar het HTTPS-endpoint van het apparaat; volume/dempen blijven zonder handtekening werken.

> Vereist het pakket `cryptography` (meegeleverd met Home Assistant, dus al aanwezig; niet als vereiste in het manifest opgenomen).

📖 **Hoe we het hebben gereverse-engineerd** — het volledige verhaal van het onderzoek (blutter, Frida, WireGuard-MITM, de ontmanteling van het "security theatre"): [het veldrapport](REPORT_en.md) (in het Engels; Russisch: [REPORT.md](REPORT.md)).

Oudere firmware (vóór `1.1.3`) is niet getroffen en houdt volledige bediening via de oude `GET`-fallback.

## Functies

### Mediaspeler
- **Volume** — niveau instellen, stapsgewijs harder/zachter, dempen/dempen opheffen
- **Aan/uit** — in- / uitschakelen (netwerk-stand-by)
- **Invoerbron** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast. Is een streaming-app (Spotify Connect, TIDAL Connect, QPlay), USB of de Dirac-kalibratie actief, dan toont de bron dat
- **Geluidsmodus** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Afspelen** — afspelen/pauzeren, volgend/vorig nummer
- **Media-informatie** — titel, artiest, album, albumhoes, bron-app

### Kanaalniveaus (11 schuifregelaars: 9 van -6 tot +6 dB, 2 subwoofers van -12 tot +6 dB)

| Kanaal | Beschrijving |
|--------|--------------|
| Voor hoog | Dolby Atmos-hoogteluidspreker voor |
| Achter hoog | Dolby Atmos-hoogteluidspreker achter |
| Zijkant links / rechts | Surround-zijluidsprekers |
| Achter links / rechts | Surround-achterluidsprekers |
| Bekabelde subwoofer / Draadloze subwoofers | Bekabelde subwooferuitgang (RCA) en draadloze subwoofers (één of twee, samen geregeld), -12 tot +6 dB |
| Lage tonen / Middentonen / Hoge tonen | Toonregeling (EQ) |

### Audio-instellingen (Selects)
- **EQ-voorinstelling** — Vlak, Bas, Rock, Zang (+ Aangepast, gemeld zodra lage / midden- / hoge tonen zijn gewijzigd — vanuit HA of de Klipsch-app — of in de app een eigen curve is ingesteld; vanuit HA niet te kiezen)
- **Nachtmodus** — verkleint het dynamisch bereik om zacht te luisteren
- **Dialoogmodus** — verbetert de verstaanbaarheid van dialogen (3 niveaus)
- **Dirac Live** — filter voor ruimtecorrectie (automatisch van het apparaat opgehaald)
- **Led-helderheid** — led aan de voorkant: Uit / Gedimd / Helder
- **Inactiviteitstime-out** — inactieve tijd vóór automatische stand-by: Uit / 5 / 10 / 15 / 30 min

### Instellingen (Numbers)
- **Lipsync-vertraging** — handmatige A/V-synchronisatie (0–500 ms)
- **Balans** — balans links/rechts (−10…+10 dB)

### Schakelaars (Switches)
- **Automatische lipsync** — automatische A/V-vertraging
- **EQ-bypass** — de equalizer omzeilen
- **Automatisch inschakelen** — automatisch aan / stand-by
- **Loudness** — loudnesscompensatie bij laag volume
- **Niet storen** — meldingen/geluiden onderdrukken
- **Automatische stand-by** — bij inactiviteit naar stand-by
- **Interfacegeluiden**, **Extra geluidsmodi**, **BLE-afstandsbediening automatisch koppelen**, **Automatische firmware-update**

> Alle bovenstaande instellingen zijn ook te wijzigen terwijl de soundbar in **stand-by** staat (het apparaat past ze toe en slaat ze op); de integratie houdt de entiteiten beschikbaar en onthoudt de waarde die je hebt ingesteld in plaats van die terug te zetten.

### Diagnostiek
- **Reactietijd** — duur van de API-polling in ms, tellers voor verzoeken/mislukkingen
- **Apparaatstatus** — Aan / Stand-by / Offline met informatie over decoder, ingang en geluidsmodus
- **Ondertekenings-MAC** — het MAC-adres waarmee schrijfacties op de firmware van 2026 worden ondertekend (schema, kandidaten, of het adres is gevonden)
- **Netwerkverbinding** — actieve bekabelde/draadloze interface, interfacenamen, MAC-bronnen
- **Bedrijfsmodus** / **Luidsprekertest** — alleen-lezen apparaatstatus (zichtbaar gemaakt, bewust niet bedienbaar)
- **Luidsprekervertragingen** (bekabelde/draadloze sub, draadloze surround) — alleen-lezen, automatisch gekalibreerd door het apparaat
- **Diagnostiek downloaden** — volledige export van de apparaatstatus (Instellingen > Apparaten > Klipsch Flexus > Diagnostiek downloaden). Het IP-adres, elk MAC-adres, de wifi-BSSID, de apparaat-ID en stream-URL's worden onleesbaar gemaakt

### Draadloze luidsprekers
- **Een apparaat per gekoppelde luidspreker** — Flexus SUB / SURR-luidsprekers (Draadloze subwoofer 1 / 2, Surround links / rechts) verschijnen als eigen apparaten onder de soundbar, met de versies die de Klipsch Connect Plus-app toont (Product Information): MCU-, RX- en EQ-firmware als *Firmware*, de hardwareversie en het modelnummer
- **Verbonden** — een sensor per luidspreker: aan als de draadloze verbinding van de luidspreker bij de laatste uitlezing actief was, uit als die weg was
- **Wanneer ze worden uitgelezen** — één keer na de installatie en wanneer je op **Draadloze luidsprekers uitlezen** drukt (een knop op de soundbar), zodat de gewone poll even licht blijft als voorheen. Om uitval live te volgen, zet je **Draadloze luidsprekers bewaken** aan in Opties: de verbinding wordt dan bij elke poll uitgelezen (één extra verzoek), en een subwoofer die wegvalt, is terug te zien in de geschiedenis van de Verbonden-sensor. Bewaakte sensoren zijn niet beschikbaar in stand-by
- Een luidspreker krijgt zijn apparaat zodra hij eenmaal verbonden is gezien, en houdt het zolang hij ontkoppeld of offline is. Het apparaat van een ontkoppelde luidspreker kan op de apparaatpagina worden verwijderd

### Vertalingen
Volledige vertaling van de interface in **9 talen**: Engels, Russisch, Duits, Spaans, Frans, Italiaans, Portugees, Nederlands, vereenvoudigd Chinees (`zh-Hans`). Alle entiteitsnamen, statussen en configuratieschermen zijn vertaald.

## Installatie

### HACS (aanbevolen)

Klipsch Flexus staat in de standaardstore van HACS, dus je hoeft geen aangepaste repository toe te voegen.

[![Open je Home Assistant-instantie en open deze repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. Kies de knop hierboven om Klipsch Flexus in je HACS te openen (My Home Assistant-link), of open **HACS** en zoek naar **Klipsch Flexus**
2. Kies **Downloaden** en herstart daarna Home Assistant
3. De soundbar zou **automatisch ontdekt** moeten worden — kijk bij de meldingen
4. Of ga naar **Instellingen** > Apparaten en diensten > **Voeg integratie toe** > Klipsch Flexus

### Handmatig

1. Kopieer `custom_components/klipsch_flexus/` naar de map `config/custom_components/` van je HA
2. Herstart Home Assistant
3. Voeg de integratie toe via Instellingen > Apparaten en diensten

### Bijwerken

Herstart na het bijwerken van de integratie (via HACS of handmatig) **Home Assistant**: HA laadt de Python-code van de integratie bij het opstarten, dus de nieuwe versie draait pas na een herstart. Wijzigingen in de **Opties** of het wijzigen van de host via **Herconfigureer** worden direct toegepast, zonder herstart (het integratie-item wordt opnieuw geladen).

### Bètaversies

Nieuwe functies en oplossingen verschijnen eerst als **bèta**: een GitHub-pre-release met de tag `vX.Y.Z-beta.N`. De stabiele release `vX.Y.Z` volgt later. HACS biedt een bèta alleen aan gebruikers aan die zich daarvoor aanmelden. Doe je niets, dan blijf je op stabiele releases en krijg je geen meldingen over bèta's.

Zo krijg je bèta's (HACS 2.x; hieronder staan de Engelse namen, je HACS toont ze mogelijk vertaald):

1. Ga naar **Instellingen** > Apparaten en diensten > **HACS** en open de dienst **Klipsch Flexus** (HACS maakt er een aan voor elke repository die je hebt gedownload)
2. Zoek de schakelaar **Pre-release** (een diagnostische entiteit). Die is standaard uitgeschakeld: open hem, kies het tandwielpictogram, zet **Ingeschakeld** (Enabled) aan en kies **Bijwerken** (Update)
3. Zet **Pre-release** aan. HACS biedt nu de nieuwste bèta aan als update. Wil je meteen controleren, open dan Klipsch Flexus in HACS en kies **Update information** in het ⋮-menu
4. Installeer de update en herstart Home Assistant

Terug naar stabiel: zet **Pre-release** uit. HACS biedt dan weer alleen stabiele releases aan, en je houdt de bèta tot de volgende stabiele release hem vervangt. Wil je meteen terug, open dan Klipsch Flexus in HACS, kies ⋮ > **Redownload** > **Need a different version?**, kies de nieuwste release zonder de markering *pre-release*, download die en herstart Home Assistant.

## Automatische detectie

De soundbar wordt automatisch in je netwerk gevonden via **mDNS / Zeroconf** (Google Cast-protocol).

Als de soundbar aan staat, detecteert Home Assistant hem en toont een melding:
> **Klipsch Flexus CORE 300** gevonden op `192.168.1.100`. Wil je deze soundbar toevoegen?

**Zo werkt het:**
- De soundbar meldt zich aan als `Flexus-Core-*` via de mDNS-dienst `_googlecast._tcp`
- De integratie herkent het apparaat aan de TXT-records `md` (model) en `fn` (weergavenaam)
- AirCast-proxyapparaten worden automatisch uitgefilterd

Werkt automatische detectie niet (bijv. door netwerkisolatie), dan kun je de integratie altijd handmatig toevoegen door het IP-adres in te voeren.

## Configuratie

| Parameter | Standaard | Beschrijving |
|-----------|-----------|--------------|
| Host | — | IP-adres van de soundbar (verplicht) |
| Pollinginterval | 15 s | In te stellen via Opties (5–120 s). In stand-by pollt de integratie altijd elke 60 s |
| Draadloze luidsprekers bewaken | uit | Alleen in Opties. Controleert bij elke poll of elke draadloze subwoofer / surround verbonden is (één extra verzoek), zodat uitval zichtbaar wordt op de sensor **Verbonden**. Uit: uitgelezen na de installatie en met de knop **Draadloze luidsprekers uitlezen** |
| MAC-adres van het apparaat | automatisch gedetecteerd | Alleen in Opties (optioneel). Overschrijft het MAC-adres waarmee schrijfacties op de firmware van 2026 worden ondertekend; alleen nodig als andere opdrachten dan volume/dempen mislukken (zie de diagnostische sensor **Ondertekenings-MAC**) |

**Tip:** Geef de soundbar een vast IP-adres / DHCP-reservering voor een betrouwbare werking.

Je kunt het IP-adres later wijzigen via **Herconfigureer** (Instellingen > Apparaten > Klipsch Flexus > Herconfigureer).

## Hoe het werkt

De soundbar biedt een lokale HTTP-API aan op poort 80:
- `GET /api/getData` — parameters lezen
- `POST /api/setData` — parameters schrijven (JSON-body; oude GET-fallback voor oudere firmware)
- `GET /api/getRows` — gestructureerde gegevens opvragen (Dirac-filters)

Op de firmware van 2026 gaan de HMAC-ondertekende schrijfacties in plaats daarvan naar `POST https://<IP>/api/setData`.

### Robuust ontwerp voor een traag apparaat

De Klipsch Flexus heeft een **single-threaded HTTP-server** die één verzoek tegelijk verwerkt. De integratie is rond deze beperking gebouwd:

| Mechanisme | Beschrijving |
|------------|--------------|
| Serialisatie van verzoeken | Alle API-aanroepen lopen via `asyncio.Lock` — geen gelijktijdige verzoeken |
| Opnieuw proberen met backoff | Schrijfacties (behalve mediabediening) en de aan/uit-controle worden 2x opnieuw geprobeerd met 0,5 s vertraging; leesacties van de polling niet (terugval op cache), en twee time-outs op rij beëindigen de polling als offline |
| Adaptieve time-outs | 8 s lezen, 10 s schrijven, 15 s aan/uit-opdrachten |
| Geleidelijke degradatie | Mislukte leesacties vallen terug op de laatst bekende waarden uit de cache |
| Optimistische updates | De interface werkt direct bij en houdt de geschreven waarde vast tot de volgende reguliere polling die waarde terugleest (de polling ~1 s na een opdracht pikt de bijwerkingen op, bijv. de decoder na een ingangswissel); waarden die in stand-by zijn toegepast worden gecachet, zodat de stand-by-polling ze nooit terugzet |
| **Stand-by-bewuste polling** | Eerst wordt de aan/uit-status gecontroleerd; de eerste polling na de installatie leest alles één keer, ook in stand-by — daarna doet een polling in stand-by 1 verzoek in plaats van ~40, blijven gecachete waarden behouden en vertraagt het pollinginterval naar 60 s. Instellingen blijven in stand-by **beschikbaar en bedienbaar** — het apparaat past schrijfacties toe en de integratie onthoudt ze |

## Entiteiten

![Apparaatpagina van Klipsch Flexus in Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*De apparaatpagina van de integratie in Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + schakelaars) en het activiteitenlogboek.*

| Entiteit | Type | Categorie |
|----------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Nachtmodus / Dialoogmodus / EQ-voorinstelling / Dirac-filter / Led-helderheid / Inactiviteitstime-out | Select (x6) | Configuratie |
| Achter hoog / links / rechts, Voor hoog, Zijkant links / rechts | Number (x6) | Configuratie |
| Bekabelde subwoofer / Draadloze subwoofers | Number (x2) | Configuratie |
| Lage tonen / Middentonen / Hoge tonen | Number (x3) | Configuratie |
| Lipsync-vertraging, Balans | Number (x2) | Configuratie |
| Automatische lipsync, EQ-bypass, Automatisch inschakelen, Interfacegeluiden, Extra geluidsmodi, BLE-afstandsbediening automatisch koppelen, Automatische firmware-update | Switch (x7) | Configuratie |
| Loudness, Niet storen, Automatische stand-by | Switch (x3) | Configuratie |
| Reactietijd, Apparaatstatus, Actieve ingang, Actieve geluidsmodus | Sensor (x4) | Diagnose |
| Ondertekenings-MAC, Netwerkverbinding | Sensor (x2) | Diagnose |
| Bedrijfsmodus, Luidsprekertest, Vertraging bekabelde/draadloze subwoofer, Vertraging draadloze surround | Sensor (x5, alleen-lezen) | Diagnose |
| Draadloze luidsprekers uitlezen | Button | Diagnose |
| Verbonden (op het apparaat van elke draadloze luidspreker) | Binary Sensor (één per gekoppelde luidspreker, maximaal 4) | Diagnose |

**Totaal: 42 entiteiten** (1 mediaspeler + 6 selects + 13 numbers + 10 switches + 11 sensoren + 1 button), plus één Verbonden-sensor per gekoppelde draadloze luidspreker

## Probleemoplossing

| Probleem | Oplossing |
|----------|-----------|
| Kan geen verbinding maken | Controleer of de soundbar in hetzelfde netwerk zit. Probeer: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entiteiten niet beschikbaar | Misschien pollt de Klipsch-app tegelijkertijd — sluit de app en probeer het opnieuw |
| Trage updates | Verhoog het pollinginterval in Opties (Instellingen > Apparaten > Klipsch Flexus > Configureer) |
| Andere opdrachten dan volume/dempen mislukken | Controleer de diagnostische sensor **Ondertekenings-MAC**. Toont die geen gevonden MAC-adres (of het verkeerde), voer dan het MAC-adres van de soundbar in als **MAC-adres van het apparaat** in Opties |
| Integratie laadt niet | Zoek in de logboeken van Home Assistant naar importfouten. Zorg dat je HA 2024.11+ gebruikt |
| Draadloze subwoofer of surround valt weg | Zet **Draadloze luidsprekers bewaken** aan in Opties en open daarna het apparaat van de luidspreker onder de soundbar: de sensor **Verbonden** staat uit zolang de verbinding weg is, en de geschiedenis toont wanneer die wegviel. De soundbar meldt de plek dan als leeg; dit is dus hoe de soundbar de draadloze verbinding ziet. Een luidspreker waarvan de eigen printplaat vastloopt terwijl de radioverbinding blijft (geen geluid), staat nog steeds als verbonden; het attribuut `mcu_responding` laat zien of de printplaat bij de laatste uitlezing antwoordde (druk op **Draadloze luidsprekers uitlezen** om te controleren). De luidspreker met een slimme stekker uit- en weer aanzetten helpt meestal |
| Logo onzichtbaar in het donkere thema | Werk bij naar v2.5.19+ en herstart. Het pictogram voor het donkere thema wordt met de integratie meegeleverd en vereist HA 2026.3+; oudere HA-versies tonen het zwarte pictogram van de HA-brands-site |

## Bekende beperkingen

- Eén soundbar per integratie-item (voeg meerdere toe als aparte items)
- Geen beheer van multiroom / draadloze surroundgroepen (gebruik de Klipsch Connect Plus-app)
- Bediening gebruikt alleen de eigen HTTP-API, niet de Cast- of AirPlay-protocollen. Google Cast is een selecteerbare ingang (start het afspelen vanuit een Cast-app); AirPlay staat niet in de ingangenlijst van het apparaat en wordt daarom niet als bron aangeboden (streamen naar de soundbar vanaf een Apple-apparaat werkt gewoon)
- De eerste installatie moet **volledig** worden afgerond in de officiële Klipsch Connect Plus-app — doorloop de hele onboarding minstens één keer (daarmee worden de toegangsgegevens voor schrijfacties op de firmware van 2026 ingericht)

## Beveiliging

Zie [SECURITY.md](../SECURITY.md) voor het beveiligingsbeleid en best practices.

**Melding over netwerkbeveiliging**: De soundbar gebruikt onversleuteld HTTP, en de lokale API is op het LAN in feite niet geauthenticeerd. Oudere firmware vereiste helemaal geen authenticatie; de firmware van 2026 (`1.1.3.x`) ondertekent de meeste schrijfacties (`HMAC_SHA256_AES256`), maar dat is **geen echte beveiligingsgrens** — de toegangsgegevens worden afgeleid van het eigen MAC-adres van het apparaat (dat het zonder authenticatie prijsgeeft) plus een hardgecodeerde constante die voor de hele productlijn gelijk is, zodat elke host in het netwerk ze kan vervalsen. Leesacties blijven open (zie [Firmwarecompatibiliteit](#️-firmwarecompatibiliteit-update-2026)). **Houd de soundbar in een vertrouwd / geïsoleerd netwerksegment.** Zie het [beveiligingsbeoordelingsrapport](SECURITY_ASSESSMENT_CORE_300.md) (sectie 12) voor de volledige analyse.

## Testresultaten

[![pytest, huidige Home Assistant](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest, oudste ondersteunde Home Assistant](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![Ondertekende lokale CI](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

Alle tests draaien op de computer van de maintainer, niet op GitHub. De eerste vijf badges tonen de resultaten van die ondertekende lokale run voor de nieuwste geverifieerde commit op `main` (de badge *Signed local CI* toont de korte SHA en de datum). GitHub schrijft ze pas nadat het ondertekende bewijsmateriaal is geverifieerd. *Verify signed local CI* is die controle op GitHub. *HACS validation* is de HACS-controle van de repository, die op GitHub draait.

Je kunt het bewijsmateriaal zelf controleren (Python 3.11 of nieuwer, git, OpenSSH):

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` bevat de publieke ondertekeningssleutel van de eigenaar. Vergelijk die met de SSH-ondertekeningssleutels die GitHub voor de eigenaar vermeldt: `curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`. Details in [TESTING.md](TESTING.md#test-result-badges) (in het Engels).

## Bijdragers

Dank aan iedereen die problemen heeft gemeld en oplossingen heeft ingestuurd:

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — ontdekte dat het volume van de soundbar van 0 tot 50 loopt in plaats van 0 tot 100, en corrigeerde de omrekening ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — verving de verwijderde mediaspelerstatus `STANDBY`, zodat de integratie blijft werken op Home Assistant 2026.12+ ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Zie de [volledige lijst van bijdragers](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Bijdragen en ondersteuning

- **Vragen en ideeën**: [GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions). In [SUPPORT.md](../SUPPORT.md) staat wat je moet meesturen.
- **Bugs**: open een [issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose) met het bugformulier en voeg de diagnostische gegevens toe.
- **Beveiligingsproblemen**: meld ze vertrouwelijk, zie [SECURITY.md](../SECURITY.md).
- **Pull requests** zijn welkom. [CONTRIBUTING.md](../CONTRIBUTING.md) legt uit hoe je je wijziging test en hoe de maintainer die controleert. [TESTING.md](TESTING.md) beschrijft de tests en de ondertekende lokale CI.
- Iedereen die meedoet, volgt de [gedragscode](../CODE_OF_CONDUCT.md).

## Licentie

MIT — zie [LICENSE](../LICENSE).
