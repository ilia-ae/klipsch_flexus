# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#rilevamento-automatico)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | [Español](README_es.md) | [Português](README_pt.md) | [Français](README_fr.md) | **Italiano** | [Nederlands](README_nl.md) | [中文](README_zh.md)  
🔒 **Sicurezza**: [Policy](../SECURITY.md) | [Rapporto di valutazione](SECURITY_ASSESSMENT_CORE_300.md)

---

Integrazione personalizzata per Home Assistant dedicata alle soundbar **Klipsch Flexus** — controllo tramite **API HTTP locale nativa**, senza cloud e senza ritardi.

> ✅ **42 entità**. Tutti i comandi di scrittura sono verificati dal vivo sul firmware 2026 (firmati con HMAC) e funzionano anche in standby. Ogni commit su `main` viene prima testato in locale: vedi [Risultati dei test](#risultati-dei-test).

## 📸 Dashboard

Una dashboard Lovelace personalizzata basata interamente sulle entità dell'integrazione — ingresso, modalità audio, notte / dialogo, preset EQ, filtro Dirac, tono (bassi / medi / alti), livelli dei canali surround e subwoofer — tutto controllato dal vivo tramite l'API locale.

![Dashboard Klipsch Flexus](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**Componenti HACS necessari** (tutti installabili tramite [HACS](https://github.com/hacs/integration)):

| Componente | Repo | Uso |
|------------|------|-----|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | questa integrazione — le entità |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | scheda del media player |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | riquadri di ingresso / modalità / EQ con stile dinamico |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | evidenziazione dello stato attivo (CSS) |

📋 **YAML completo della dashboard + schema dei colori:** [docs/DASHBOARD.md](DASHBOARD.md)

### Modelli supportati

| Modello | Canali | Caratteristiche |
|---------|--------|-----------------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 driver |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

L'integrazione non controlla il modello. Aggiunge qualsiasi soundbar Flexus che si annuncia tramite Google Cast e usa la stessa API locale e le stesse 42 entità per ogni modello. Il maintainer esegue i test su una CORE 300. Un controllo per hardware che il tuo modello non ha (per esempio i canali di altezza su una CORE 100) può fallire con un errore.

> La soundbar deve essere prima **configurata completamente nell'app ufficiale Klipsch Connect Plus** — completa l'intera procedura di configurazione iniziale almeno una volta (Wi-Fi, aggiornamento del firmware, abbinamento degli altoparlanti, calibrazione Dirac). Sul firmware 2026 è questa procedura a fornire anche la credenziale di autenticazione per la scrittura su cui si basa l'integrazione, quindi una configurazione lasciata a metà nell'app lascia la maggior parte dei comandi non autorizzata. Questa integrazione si occupa solo del controllo quotidiano.

## ⚠️ Compatibilità firmware (aggiornamento 2026)

Un aggiornamento firmware della soundbar del 2026 (**Device Version `1.1.3.x`**, es. `1.1.3.0x7cd294e`, build Cast `20250512_0201_RC25`) ha cambiato l'API HTTP locale in due modi:

1. **`setData` ora richiede `POST` con un corpo JSON.** Il vecchio `GET /api/setData?...` restituisce `405 Strict HTTP required!`. **Risolto nella v2.4.1** — aggiorna l'integrazione.
2. **La maggior parte delle scritture `setData` ora è autenticata** (`settings:/webserver/authMode = setData`). Le scritture protette restituiscono `401 Forbidden` con `WWW-Authenticate: HMAC_SHA256_AES256`. **Risolto nella v2.5.0** — l'integrazione ora firma automaticamente queste scritture.

### Cosa funziona con il nuovo firmware

| Funzione | Stato |
|----------|-------|
| Tutti i sensori / letture di stato (`getData`) | ✅ Funziona |
| Volume, Muto | ✅ Funziona |
| Ingresso, Modalità audio, Notte / Dialogo, Bassi / Medi / Alti, Preset EQ, Dirac, livelli Subwoofer e Surround, Accensione | ✅ Funziona (firma HMAC, v2.5.0+) |
| LED, Sincronizzazione labiale, Bilanciamento, Loudness, Non disturbare, Standby automatico + altri 4 interruttori | ✅ Funziona (firmato; aggiunto nelle v2.5.8–2.5.9) — anche in standby |

Puoi vedere lo stato dal vivo di ogni comando sul tuo dispositivo tramite **Scarica la diagnostica** (la sezione `command_health`, aggiunta nella v2.4.2). È di sola lettura: per ogni comando mostra se l'impostazione è leggibile e come il dispositivo ha risposto alle scritture effettuate dall'ultimo caricamento dell'integrazione (`http_status`, `needs_auth` quando il dispositivo ha richiesto una firma).

### Stato della correzione

✅ **Risolto nella v2.5.0 — controllo completo ripristinato, nessuna azione richiesta.** La firma delle richieste `HMAC_SHA256_AES256` è ora implementata. La credenziale specifica del dispositivo viene ricavata automaticamente dall'indirizzo MAC della soundbar, quindi **non c'è nulla da configurare** — basta aggiornare l'integrazione. Dalla **v2.5.9** il MAC viene letto in modo deterministico dal dispositivo stesso (`settings:/system/primaryMacAddress`), così la risoluzione riesce al primo tentativo su ogni unità (il precedente rilevamento tramite registro/ARP resta come fallback). Le scritture firmate vanno all'endpoint HTTPS del dispositivo; volume/muto continuano a funzionare senza firma.

> Richiede il pacchetto `cryptography` (incluso in Home Assistant, quindi già presente; non elencato come requisito nel manifest).

📖 **Come lo abbiamo ricostruito con il reverse engineering** — la storia completa dell'indagine (blutter, Frida, WireGuard-MITM, lo smontaggio del "teatro della sicurezza"): [il report sul campo](REPORT_en.md) (in inglese; in russo: [REPORT.md](REPORT.md)).

Il firmware più vecchio (precedente alla `1.1.3`) non è interessato e mantiene il controllo completo tramite il fallback `GET` legacy.

## Funzionalità

### Media player
- **Volume** — imposta il livello, alza/abbassa a passi, attiva/disattiva il muto
- **Accensione** — accendi / spegni (standby di rete)
- **Sorgente di ingresso** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast. Quando è attiva un'app di streaming (Spotify Connect, TIDAL Connect, QPlay), l'USB o la calibrazione Dirac, la sorgente lo mostra
- **Modalità audio** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Riproduzione** — play/pausa, brano successivo/precedente
- **Informazioni multimediali** — titolo, artista, album, copertina, app di origine

### Livelli dei canali (11 cursori: 9 da -6 a +6 dB, 2 subwoofer da -12 a +6 dB)

| Canale | Descrizione |
|--------|-------------|
| Anteriore alto | Altoparlante di altezza anteriore Dolby Atmos |
| Posteriore alto | Altoparlante di altezza posteriore Dolby Atmos |
| Laterale sinistro / destro | Altoparlanti surround laterali |
| Posteriore sinistro / destro | Altoparlanti surround posteriori |
| Subwoofer cablato / Subwoofer wireless | Uscita subwoofer cablata (RCA) e subwoofer wireless (uno o due, regolati insieme), da -12 a +6 dB |
| Bassi / Medi / Alti | Controlli di tono dell'EQ |

### Impostazioni audio (Select)
- **Preset EQ** — Piatto, Bassi, Rock, Voce (+ Personalizzato, segnalato quando Bassi / Medi / Alti vengono modificati — da HA o dall'app Klipsch — o quando nell'app è impostata una curva personalizzata; non è selezionabile da HA)
- **Modalità notturna** — riduce la gamma dinamica per l'ascolto a basso volume
- **Modalità dialogo** — migliora la chiarezza dei dialoghi (3 livelli)
- **Filtro Dirac** — filtro di correzione ambientale Dirac Live (rilevato automaticamente dal dispositivo)
- **Luminosità LED** — LED frontale: Spento / Soffuso / Luminoso
- **Timeout di inattività** — tempo di inattività prima dello standby automatico: Spento / 5 / 10 / 15 / 30 min

### Impostazioni numeriche (Number)
- **Ritardo sincronizzazione labiale** — sincronizzazione A/V manuale (0–500 ms)
- **Bilanciamento** — bilanciamento sinistra/destra (−10…+10 dB)

### Interruttori (Switch)
- **Sincronizzazione labiale automatica** — ritardo A/V automatico
- **Bypass equalizzatore** — esclude l'equalizzatore
- **Accensione automatica** — comportamento automatico di accensione/standby
- **Loudness** — compensazione loudness a basso volume
- **Non disturbare** — sopprime notifiche/suoni
- **Standby automatico** — passa in standby quando inattiva
- **Suoni dell'interfaccia**, **Modalità audio extra**, **Accoppiamento automatico telecomando BLE**, **Aggiornamento automatico firmware**

> Tutte le impostazioni sopra sono scrivibili anche mentre la soundbar è in **standby** (il dispositivo le applica e le memorizza); l'integrazione mantiene le entità disponibili e ricorda il valore che hai impostato invece di ripristinarlo.

### Diagnostica
- **Stato: Tempo di risposta** — durata del polling dell'API in ms, contatori di richieste/errori
- **Stato: Dispositivo** — Acceso / Standby / Offline con informazioni su decoder, ingresso e modalità audio
- **MAC di firma** — il MAC usato per firmare le scritture del firmware 2026 (schema, candidati, stato di risoluzione)
- **Collegamento di rete** — interfaccia cablata/wireless attiva, nomi delle interfacce, origini del MAC
- **Stato: modalità operativa** / **Stato: test altoparlanti** — stato del dispositivo in sola lettura (esposto, volutamente non controllabile)
- **Ritardi degli altoparlanti** (subwoofer cablato/wireless, surround wireless) — in sola lettura, calibrati automaticamente dal dispositivo
- **Scarica la diagnostica** — esportazione completa dello stato del dispositivo (Impostazioni > Dispositivi > Klipsch Flexus > Scarica la diagnostica). L'indirizzo IP, tutti gli indirizzi MAC, il BSSID Wi-Fi, l'ID del dispositivo e gli URL degli stream vengono oscurati

### Altoparlanti wireless
- **Un dispositivo per ogni altoparlante abbinato** — gli altoparlanti Flexus SUB / SURR (Subwoofer wireless 1 / 2, Surround sinistro / destro) compaiono come dispositivi a sé sotto la soundbar, con le versioni mostrate dall'app Klipsch Connect Plus (Product Information): firmware MCU, RX ed EQ come *Firmware*, la versione hardware e il numero di modello
- **Connesso** — un sensore per altoparlante: acceso se il collegamento wireless dell'altoparlante era attivo all'ultima lettura, spento se era interrotto
- **Quando vengono letti** — una volta dopo la configurazione e quando premi **Leggi altoparlanti wireless** (un pulsante della soundbar), così il polling regolare resta leggero come prima. Per seguire le disconnessioni dal vivo, attiva **Monitora altoparlanti wireless** nelle Opzioni: il collegamento viene allora letto a ogni polling (una richiesta in più), e un subwoofer che si disconnette risulta nella cronologia del sensore Connesso. I sensori monitorati non sono disponibili in standby
- Un altoparlante ottiene il suo dispositivo non appena è stato visto collegato, e lo mantiene anche quando non è più abbinato o è offline. Il dispositivo di un altoparlante non più abbinato può essere eliminato dalla sua pagina del dispositivo

### Traduzioni
Interfaccia completamente tradotta in **9 lingue**: inglese, russo, tedesco, spagnolo, francese, italiano, portoghese, olandese, cinese semplificato (`zh-Hans`). Tutti i nomi delle entità, gli stati e le schermate di configurazione sono tradotti.

## Installazione

### HACS (consigliato)

Klipsch Flexus è nello store predefinito di HACS, quindi non devi aggiungere un repository personalizzato.

[![Apri la tua istanza di Home Assistant e apri questo repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. Usa il pulsante qui sopra per aprire Klipsch Flexus nel tuo HACS (link My Home Assistant), oppure apri **HACS** e cerca **Klipsch Flexus**
2. Seleziona **Scarica**, poi riavvia Home Assistant
3. La soundbar dovrebbe essere **rilevata automaticamente** — controlla le notifiche
4. In alternativa vai su **Impostazioni** > Dispositivi e servizi > **Aggiungi integrazione** > Klipsch Flexus

### Manuale

1. Copia `custom_components/klipsch_flexus/` nella directory `config/custom_components/` del tuo HA
2. Riavvia Home Assistant
3. Aggiungi l'integrazione da Impostazioni > Dispositivi e servizi

### Aggiornamento

Dopo aver aggiornato l'integrazione (con HACS o manualmente), **riavvia Home Assistant**: HA carica il codice Python dell'integrazione all'avvio, quindi la nuova versione entra in funzione solo dopo un riavvio. Le modifiche alle **Opzioni** o la **Riconfigurazione** dell'host si applicano subito, senza riavvio (la voce viene ricaricata).

### Versioni beta

Le nuove funzionalità e correzioni escono prima come **beta**: una pre-release di GitHub con il tag `vX.Y.Z-beta.N`. La versione stabile `vX.Y.Z` arriva più tardi. HACS offre una beta solo a chi la attiva esplicitamente. Se non fai nulla, resti sulle versioni stabili e non ricevi notifiche sulle beta.

Per ricevere le beta (HACS 2.x; qui sono indicati i nomi inglesi, il tuo HACS potrebbe mostrarli tradotti):

1. Vai su **Impostazioni** > Dispositivi e servizi > **HACS** e apri la voce di servizio **Klipsch Flexus** (HACS ne crea una per ogni repository scaricato)
2. Trova l'interruttore **Pre-release** (un'entità diagnostica). È disabilitato per impostazione predefinita: aprilo, seleziona l'icona dell'ingranaggio, attiva **Abilitata** (Enabled) e seleziona **Aggiorna** (Update)
3. Attiva **Pre-release**. HACS ora offre la beta più recente come aggiornamento. Per verificare subito, apri Klipsch Flexus in HACS e seleziona **Update information** nel menu ⋮
4. Installa l'aggiornamento e riavvia Home Assistant

Per tornare alle versioni stabili, disattiva **Pre-release**. HACS offrirà di nuovo solo versioni stabili e manterrai la beta finché la prossima versione stabile non la sostituisce. Per tornare indietro subito, apri Klipsch Flexus in HACS, seleziona ⋮ > **Redownload** > **Need a different version?**, scegli la versione più recente senza il contrassegno *pre-release*, scaricala e riavvia Home Assistant.

## Rilevamento automatico

La soundbar viene rilevata automaticamente nella tua rete tramite **mDNS / Zeroconf** (protocollo Google Cast).

Quando la soundbar è accesa, Home Assistant la rileva e mostra una notifica:
> Trovato **Klipsch Flexus CORE 300** all'indirizzo `192.168.1.100`. Vuoi aggiungere questa soundbar?

**Come funziona:**
- La soundbar si annuncia come `Flexus-Core-*` tramite il servizio mDNS `_googlecast._tcp`
- L'integrazione identifica il dispositivo dai record TXT `md` (modello) e `fn` (nome descrittivo)
- I dispositivi proxy AirCast vengono esclusi automaticamente

Se il rilevamento automatico non funziona (es. per isolamento della rete), puoi sempre aggiungere l'integrazione manualmente inserendo l'indirizzo IP.

## Configurazione

| Parametro | Predefinito | Descrizione |
|-----------|-------------|-------------|
| Indirizzo IP | — | Indirizzo IP della soundbar (obbligatorio) |
| Intervallo di polling | 15 s | Configurabile nelle Opzioni (5–120 s). In standby l'integrazione esegue sempre il polling ogni 60 s |
| Monitora altoparlanti wireless | disattivato | Solo nelle Opzioni. Controlla a ogni polling se ogni subwoofer / surround wireless è collegato (una richiesta in più), così le disconnessioni si vedono sul suo sensore **Connesso**. Disattivato: lettura dopo la configurazione e con il pulsante **Leggi altoparlanti wireless** |
| MAC del dispositivo | rilevato automaticamente | Solo nelle Opzioni (facoltativo). Sostituisce il MAC usato per firmare le scritture del firmware 2026; serve solo se falliscono comandi diversi da volume/muto (vedi il sensore diagnostico **MAC di firma**) |

**Suggerimento:** assegna alla soundbar un IP statico / una prenotazione DHCP per un funzionamento affidabile.

Puoi cambiare l'indirizzo IP in seguito con **Riconfigura** (Impostazioni > Dispositivi > Klipsch Flexus > Riconfigura).

## Come funziona

La soundbar espone un'API HTTP locale sulla porta 80:
- `GET /api/getData` — lettura dei parametri
- `POST /api/setData` — scrittura dei parametri (corpo JSON; fallback GET legacy per il firmware più vecchio)
- `GET /api/getRows` — elenco di dati strutturati (filtri Dirac)

Sul firmware 2026 le scritture firmate con HMAC vanno invece a `POST https://<IP>/api/setData`.

### Progettazione robusta per un dispositivo lento

La Klipsch Flexus ha un **server HTTP single-thread** che elabora una richiesta alla volta. L'integrazione è costruita attorno a questo vincolo:

| Meccanismo | Descrizione |
|------------|-------------|
| Serializzazione delle richieste | Tutte le chiamate API passano per `asyncio.Lock` — nessuna richiesta concorrente |
| Nuovi tentativi con backoff | Le scritture (tranne i controlli multimediali) e il controllo dello stato di alimentazione vengono ritentati 2 volte con 0,5 s di attesa; le letture del polling non vengono ritentate (fallback sui valori in cache) e due timeout consecutivi chiudono il polling come offline |
| Timeout adattivi | 8 s per le letture, 10 s per le scritture, 15 s per i comandi di accensione |
| Degrado controllato | Le letture fallite ripiegano sugli ultimi valori noti in cache |
| Aggiornamenti ottimistici | L'interfaccia si aggiorna subito e mantiene il valore scritto finché il successivo polling regolare non lo rilegge (il polling ~1 s dopo un comando ne raccoglie gli effetti collaterali, es. il decoder dopo un cambio di ingresso); i valori applicati in standby vengono memorizzati in cache, così il polling in standby non li ripristina mai |
| **Polling consapevole dello standby** | Lo stato di alimentazione viene verificato per primo; il primo polling dopo la configurazione legge tutto una volta, anche in standby — dopo di che i polling in standby fanno 1 richiesta invece di ~40, i valori in cache vengono conservati e l'intervallo di polling rallenta a 60 s. Le impostazioni restano **disponibili e controllabili** in standby — il dispositivo applica le scritture e l'integrazione le ricorda |

## Entità

![Pagina del dispositivo Klipsch Flexus in Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*La pagina del dispositivo in Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + interruttori) e il registro attività.*

| Entità | Tipo | Categoria |
|--------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Modalità notturna / Modalità dialogo / Preset EQ / Filtro Dirac / Luminosità LED / Timeout di inattività | Select (x6) | Configurazione |
| Posteriore alto / sinistro / destro, Anteriore alto, Laterale sinistro / destro | Number (x6) | Configurazione |
| Subwoofer cablato / Subwoofer wireless | Number (x2) | Configurazione |
| Bassi / Medi / Alti | Number (x3) | Configurazione |
| Ritardo sincronizzazione labiale, Bilanciamento | Number (x2) | Configurazione |
| Sincronizzazione labiale automatica, Bypass equalizzatore, Accensione automatica, Suoni dell'interfaccia, Modalità audio extra, Accoppiamento automatico telecomando BLE, Aggiornamento automatico firmware | Switch (x7) | Configurazione |
| Loudness, Non disturbare, Standby automatico | Switch (x3) | Configurazione |
| Stato: Tempo di risposta, Stato: Dispositivo, Stato: Ingresso attivo, Stato: Modalità audio | Sensor (x4) | Diagnostica |
| MAC di firma, Collegamento di rete | Sensor (x2) | Diagnostica |
| Stato: modalità operativa, Stato: test altoparlanti, Ritardo: subwoofer cablato/wireless, Ritardo: surround wireless | Sensor (x5, sola lettura) | Diagnostica |
| Leggi altoparlanti wireless | Button | Diagnostica |
| Connesso (sul dispositivo di ogni altoparlante wireless) | Binary Sensor (uno per altoparlante abbinato, fino a 4) | Diagnostica |

**Totale: 42 entità** (1 media player + 6 select + 13 number + 10 switch + 11 sensor + 1 button), più un sensore Connesso per ogni altoparlante wireless abbinato

## Risoluzione dei problemi

| Problema | Soluzione |
|----------|-----------|
| Impossibile connettersi | Verifica che la soundbar sia sulla stessa rete. Prova: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entità non disponibili | L'app Klipsch potrebbe eseguire il polling contemporaneamente — chiudila e riprova |
| Aggiornamenti lenti | Aumenta l'intervallo di polling nelle Opzioni (Impostazioni > Dispositivi > Klipsch Flexus > Configura) |
| Falliscono i comandi diversi da volume/muto | Controlla il sensore diagnostico **MAC di firma**. Se non mostra un MAC risolto (o ne mostra uno sbagliato), inserisci il MAC della soundbar come **MAC del dispositivo** nelle Opzioni |
| L'integrazione non si carica | Controlla nei log di Home Assistant se ci sono errori di importazione. Assicurati di usare HA 2024.11+ |
| Il subwoofer o il surround wireless si disconnette | Attiva **Monitora altoparlanti wireless** nelle Opzioni, poi apri il dispositivo dell'altoparlante sotto la soundbar: il suo sensore **Connesso** è spento finché il collegamento è interrotto, e la sua cronologia mostra quando è caduto. A quel punto la soundbar segnala lo slot come vuoto, quindi questa è la visione che la soundbar ha del collegamento wireless. Un altoparlante la cui scheda si blocca mentre la radio resta collegata (nessun suono) risulta ancora connesso; il suo attributo `mcu_responding` indica se la scheda ha risposto all'ultima lettura (premi **Leggi altoparlanti wireless** per verificarlo). Spegnerlo e riaccenderlo con una presa smart di solito lo ripristina |
| Logo invisibile con il tema scuro | Aggiorna alla v2.5.19+ e riavvia. L'icona per il tema scuro è inclusa nell'integrazione e richiede HA 2026.3+; le versioni di HA più vecchie mostrano l'icona nera dal sito dei brand di HA |

## Limitazioni note

- Una soundbar per voce dell'integrazione (aggiungine più di una come voci separate)
- Nessuna gestione multi-room / dei gruppi surround wireless (usa l'app Klipsch Connect Plus)
- Il controllo usa solo l'API HTTP nativa, non i protocolli Cast o AirPlay. Google Cast è un ingresso selezionabile (avvia la riproduzione da un'app Cast); AirPlay non è nell'elenco degli ingressi del dispositivo, quindi non viene offerto come sorgente (lo streaming verso la soundbar da un dispositivo Apple non ne è influenzato)
- La configurazione iniziale va completata **per intero** nell'app ufficiale Klipsch Connect Plus — completa l'intera procedura almeno una volta (è questa a fornire la credenziale di scrittura del firmware 2026)

## Sicurezza

Consulta [SECURITY.md](../SECURITY.md) per la policy di sicurezza e le buone pratiche.

**Avviso sulla sicurezza di rete:** la soundbar comunica in HTTP in chiaro e la sua API locale è di fatto non autenticata nella LAN. Il firmware più vecchio non richiedeva alcuna autenticazione; il firmware 2026 (`1.1.3.x`) firma la maggior parte delle scritture (`HMAC_SHA256_AES256`), ma questo **non è un vero confine di sicurezza** — la credenziale è ricavata dal MAC del dispositivo stesso (che il dispositivo rivela senza autenticazione) più una costante fissa nel codice, uguale per l'intera linea di prodotti, quindi qualsiasi host della rete può falsificarla. Le letture restano aperte (vedi [Compatibilità firmware](#️-compatibilità-firmware-aggiornamento-2026)). **Tieni la soundbar su un segmento di rete fidato / isolato.** Consulta il [Rapporto di valutazione della sicurezza](SECURITY_ASSESSMENT_CORE_300.md) (Sezione 12) per l'analisi completa.

## Risultati dei test

[![pytest, Home Assistant attuale](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest, Home Assistant più vecchio supportato](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![CI locale firmata](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

Tutti i test girano sulla macchina del maintainer, non su GitHub. I primi cinque badge mostrano i risultati di quell'esecuzione locale firmata per l'ultimo commit verificato su `main` (il badge *Signed local CI* ne mostra lo SHA breve e la data). GitHub li scrive solo dopo aver verificato le prove firmate. *Verify signed local CI* è quella verifica su GitHub. *HACS validation* è il controllo HACS del repository, che gira su GitHub.

Puoi verificare le prove da solo (Python 3.11 o successivo, git, OpenSSH):

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` contiene la chiave pubblica di firma del maintainer. Confrontala con le chiavi SSH di firma che GitHub elenca per il maintainer: `curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`. Dettagli in [TESTING.md](TESTING.md#test-result-badges) (in inglese).

## Collaboratori

Grazie a tutti coloro che hanno segnalato problemi e inviato correzioni:

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — ha scoperto che il volume della soundbar va da 0 a 50, non da 0 a 100, e ha corretto la conversione ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — ha sostituito lo stato `STANDBY` del media player, rimosso da Home Assistant, così l'integrazione continua a funzionare su Home Assistant 2026.12+ ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Vedi l'[elenco completo dei collaboratori](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Contribuire e supporto

- **Domande e idee**: [GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions). Cosa includere è spiegato in [SUPPORT.md](../SUPPORT.md).
- **Bug**: apri una [issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose) con il modulo per i bug e allega la diagnostica.
- **Problemi di sicurezza**: segnalali in privato, vedi [SECURITY.md](../SECURITY.md).
- Le **pull request** sono benvenute. [CONTRIBUTING.md](../CONTRIBUTING.md) spiega come testare la tua modifica e come il maintainer la verifica. [TESTING.md](TESTING.md) descrive i test e la CI locale firmata.
- Chiunque partecipi segue il [Codice di condotta](../CODE_OF_CONDUCT.md).

## Licenza

MIT — vedi [LICENSE](../LICENSE).
