# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#découverte-automatique)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | [Español](README_es.md) | [Português](README_pt.md) | **Français** | [Italiano](README_it.md) | [Nederlands](README_nl.md) | [中文](README_zh.md)  
🔒 **Sécurité** : [Politique](../SECURITY.md) | [Rapport d'évaluation](SECURITY_ASSESSMENT_CORE_300.md)

---

Intégration personnalisée Home Assistant pour les barres de son **Klipsch Flexus** — pilotage via l'**API HTTP locale native**, sans cloud, sans délai.

> ✅ **41 entités**. Toutes les commandes d'écriture sont vérifiées en conditions réelles sur le firmware 2026 (signées HMAC) et fonctionnent en veille. Chaque commit sur `main` est d'abord testé en local : voir [Résultats des tests](#résultats-des-tests).

## 📸 Tableau de bord (Dashboard)

Un tableau de bord Lovelace personnalisé, entièrement construit sur les entités de l'intégration — entrée, mode son, nuit / dialogue, préréglages EQ, filtre Dirac, tonalité (graves / médiums / aigus), niveaux des canaux surround et caissons de basses — le tout piloté en direct via l'API locale.

![Tableau de bord Klipsch Flexus](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**Composants HACS nécessaires** (tous installables via [HACS](https://github.com/hacs/integration)) :

| Composant | Dépôt | Utilisé pour |
|-----------|-------|--------------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | cette intégration — les entités |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | carte lecteur multimédia |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | tuiles source / mode / EQ avec style dynamique |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | mise en évidence de l'état actif (CSS) |

📋 **YAML complet du tableau de bord + palette de couleurs :** [docs/DASHBOARD.md](DASHBOARD.md)

### Modèles pris en charge

| Modèle | Canaux | Caractéristiques |
|--------|--------|------------------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 haut-parleurs |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

L'intégration ne vérifie pas le modèle. Elle ajoute toute barre de son Flexus qui s'annonce via Google Cast et utilise la même API locale et les mêmes 41 entités pour tous les modèles. Le mainteneur teste sur une CORE 300. Une commande pour un matériel absent de votre modèle (par exemple les canaux de hauteur d'une CORE 100) peut échouer avec une erreur.

> La barre de son doit d'abord être **entièrement configurée dans l'application officielle Klipsch Connect Plus** — effectuez toute la configuration initiale au moins une fois (Wi-Fi, mise à jour du firmware, appairage des enceintes, calibrage Dirac). Sur le firmware 2026, c'est aussi cette étape qui provisionne l'identifiant d'authentification des écritures dont l'intégration a besoin : une configuration inachevée dans l'application laisse la plupart des commandes non autorisées. Cette intégration ne gère que le pilotage au quotidien.

## ⚠️ Compatibilité firmware (mise à jour 2026)

Une mise à jour du firmware de 2026 (**Device Version `1.1.3.x`**, p. ex. `1.1.3.0x7cd294e`, build Cast `20250512_0201_RC25`) a modifié l'API HTTP locale de deux façons :

1. **`setData` exige désormais `POST` avec un corps JSON.** L'ancien `GET /api/setData?...` renvoie `405 Strict HTTP required!`. **Corrigé dans la v2.4.1** — mettez à jour l'intégration.
2. **La plupart des écritures `setData` sont désormais authentifiées** (`settings:/webserver/authMode = setData`). Les écritures protégées renvoient `401 Forbidden` avec `WWW-Authenticate: HMAC_SHA256_AES256`. **Corrigé dans la v2.5.0** — l'intégration signe désormais ces écritures automatiquement.

### Ce qui fonctionne avec le nouveau firmware

| Fonction | État |
|----------|------|
| Tous les capteurs / lectures d'état (`getData`) | ✅ Fonctionne |
| Volume, Sourdine | ✅ Fonctionne |
| Entrée, Mode son, Nuit / Dialogue, Graves / Médiums / Aigus, Préréglage EQ, Dirac, Niveaux caissons et surround, Alimentation | ✅ Fonctionne (signé HMAC, v2.5.0+) |
| LED, Synchronisation labiale, Balance, Loudness, Ne pas déranger, Veille auto + 4 autres interrupteurs | ✅ Fonctionne (signé ; ajouté en v2.5.8–2.5.9) — aussi en veille |

Vous pouvez voir l'état en direct de chaque commande sur votre propre appareil via **Télécharger les diagnostics** (section `command_health`, ajoutée en v2.4.2). Elle est en lecture seule : pour chaque commande, elle indique si le réglage est lisible et comment l'appareil a répondu aux écritures effectuées depuis le dernier chargement de l'intégration (`http_status`, `needs_auth` quand l'appareil a exigé une signature).

### État du correctif

✅ **Résolu dans la v2.5.0 — contrôle complet rétabli, aucune action requise.** La signature des requêtes `HMAC_SHA256_AES256` est désormais implémentée. L'identifiant propre à chaque appareil est dérivé automatiquement de l'adresse MAC de la barre de son : il n'y a **rien à configurer**, il suffit de mettre à jour l'intégration. Depuis la **v2.5.9**, la MAC est lue de façon déterministe sur l'appareil lui-même (`settings:/system/primaryMacAddress`) : la résolution réussit donc du premier coup sur chaque appareil (l'ancienne découverte via le registre / ARP reste en solution de repli). Les écritures signées partent vers le point de terminaison HTTPS de l'appareil ; volume et sourdine continuent de fonctionner sans signature.

> Nécessite le paquet `cryptography` (fourni avec Home Assistant, donc déjà présent ; non déclaré comme dépendance dans le manifeste).

📖 **Comment nous l'avons rétro-conçu** — toute l'histoire de l'enquête (blutter, Frida, WireGuard-MITM, le démontage du « théâtre de sécurité ») : [le rapport de terrain](REPORT_en.md) (en anglais ; aussi en [russe](REPORT.md)).

Les firmwares plus anciens (avant `1.1.3`) ne sont pas concernés et gardent le contrôle complet grâce au repli `GET` historique.

## Fonctionnalités

### Lecteur multimédia
- **Volume** — réglage du niveau, pas à pas plus / moins, sourdine / rétablir le son
- **Alimentation** — allumer / éteindre (veille réseau)
- **Source d'entrée** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast. Quand une application de streaming (Spotify Connect, TIDAL Connect, QPlay), l'USB ou le calibrage Dirac est actif, la source l'affiche
- **Mode son** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Lecture** — lecture / pause, piste suivante / précédente
- **Infos média** — titre, artiste, album, pochette, application source

### Niveaux des canaux (11 curseurs : 9 de -6 à +6 dB, 2 caissons de basses de -12 à +6 dB)

| Canal | Description |
|-------|-------------|
| Avant haut | Enceinte de hauteur avant Dolby Atmos |
| Arrière haut | Enceinte de hauteur arrière Dolby Atmos |
| Latéral gauche / droit | Enceintes surround latérales |
| Arrière gauche / droit | Enceintes surround arrière |
| Caisson filaire / Caissons sans fil | Sortie caisson filaire (RCA) et caissons sans fil (un ou deux, réglés ensemble), -12 à +6 dB |
| Graves / Médiums / Aigus | Réglages de tonalité |

### Réglages audio (Selects)
- **Préréglage EQ** — Plat, Basses, Rock, Voix (+ Personnalisé, signalé dès que Graves / Médiums / Aigus sont modifiés — depuis HA ou l'application Klipsch — ou qu'une courbe personnalisée est définie dans l'application ; non sélectionnable depuis HA)
- **Mode nuit** — réduit la plage dynamique pour une écoute à faible volume
- **Mode dialogue** — améliore l'intelligibilité des dialogues (3 niveaux)
- **Filtre Dirac** — filtre de correction acoustique Dirac Live (découvert automatiquement sur l'appareil)
- **Luminosité de la LED** — LED en façade : Éteint / Faible / Vif
- **Délai d'inactivité** — durée d'inactivité avant la mise en veille automatique : Éteint / 5 / 10 / 15 / 30 min

### Réglages numériques (Numbers)
- **Délai de synchronisation labiale** — synchronisation A/V manuelle (0–500 ms)
- **Balance** — balance gauche / droite (−10…+10 dB)

### Interrupteurs (Switches)
- **Synchronisation labiale auto** — délai A/V automatique
- **Contournement de l'égaliseur** — désactive l'égaliseur
- **Allumage automatique** — comportement automatique de mise en marche / veille
- **Loudness** — compensation physiologique à faible volume
- **Ne pas déranger** — supprime les notifications / sons
- **Veille auto** — passe en veille en cas d'inactivité
- **Sons de l'interface**, **Modes sonores supplémentaires**, **Appairage auto de la télécommande BLE**, **Mise à jour auto du firmware**

> Tous les réglages ci-dessus sont aussi modifiables pendant que la barre de son est en **veille** (l'appareil les applique et les conserve) ; l'intégration garde les entités disponibles et mémorise la valeur que vous avez définie au lieu de la rétablir.

### Diagnostic
- **Temps de réponse** — durée d'interrogation de l'API en ms, compteurs de requêtes / d'échecs
- **Statut : Appareil** — Allumé / Veille / Hors ligne, avec infos sur le décodeur, l'entrée et le mode son
- **MAC de signature** — la MAC utilisée pour signer les écritures du firmware 2026 (schéma, candidates, état de résolution)
- **Liaison réseau** — interface filaire / sans fil active, noms des interfaces, sources de la MAC
- **Mode de fonctionnement** / **Test des haut-parleurs** — état de l'appareil en lecture seule (exposé, volontairement non pilotable)
- **Délais des enceintes** (caisson filaire / sans fil, surround sans fil) — en lecture seule, calibrés automatiquement par l'appareil
- **Télécharger les diagnostics** — export complet de l'état de l'appareil (Paramètres > Appareils > Klipsch Flexus > Télécharger les diagnostics). L'adresse IP, toutes les adresses MAC, le BSSID Wi-Fi, l'identifiant de l'appareil et les URL de flux sont masqués

### Traductions
Interface entièrement traduite en **9 langues** : anglais, russe, allemand, espagnol, français, italien, portugais, néerlandais, chinois simplifié (`zh-Hans`). Tous les noms d'entités, les états et les écrans de configuration sont traduits.

## Installation

### HACS (recommandé)

Klipsch Flexus fait partie du store par défaut de HACS : inutile d'ajouter un dépôt personnalisé.

[![Ouvrez votre instance Home Assistant et ce dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. Sélectionnez le bouton ci-dessus pour ouvrir Klipsch Flexus dans votre HACS (lien My Home Assistant), ou ouvrez **HACS** et recherchez **Klipsch Flexus**
2. Sélectionnez **Télécharger**, puis redémarrez Home Assistant
3. La barre de son devrait être **découverte automatiquement** — consultez les notifications
4. Sinon, allez dans **Paramètres** > Appareils et services > **Ajouter une intégration** > Klipsch Flexus

### Manuelle

1. Copiez `custom_components/klipsch_flexus/` dans le répertoire `config/custom_components/` de votre HA
2. Redémarrez Home Assistant
3. Ajoutez l'intégration via Paramètres > Appareils et services

### Mise à jour

Après une mise à jour de l'intégration (HACS ou manuelle), **redémarrez Home Assistant** : HA charge le code Python de l'intégration au démarrage, la nouvelle version ne tourne donc qu'après un redémarrage. Modifier les **Options** ou **Reconfigurer** l'hôte s'applique immédiatement, sans redémarrage (l'entrée est rechargée).

### Versions bêta

Les nouvelles fonctionnalités et corrections sortent d'abord en **bêta** : une pré-version GitHub avec le tag `vX.Y.Z-beta.N`. La version stable `vX.Y.Z` suit plus tard. HACS ne propose une bêta qu'aux utilisateurs qui l'ont activée. Si vous ne faites rien, vous restez sur les versions stables et n'êtes pas averti des bêtas.

Pour recevoir les bêtas (HACS 2.x ; les libellés HACS ci-dessous sont ceux de l'interface anglaise, votre HACS peut les afficher traduits) :

1. Allez dans **Paramètres** > Appareils et services > **HACS** et ouvrez l'entrée de service **Klipsch Flexus** (HACS en crée une pour chaque dépôt téléchargé)
2. Trouvez l'interrupteur **Pre-release** (une entité de diagnostic). Il est désactivé par défaut : ouvrez-le, sélectionnez l'icône d'engrenage, activez l'option **Activée** (Enabled) et sélectionnez **Mettre à jour** (Update)
3. Activez **Pre-release**. HACS propose alors la bêta la plus récente comme mise à jour. Pour vérifier tout de suite, ouvrez Klipsch Flexus dans HACS et sélectionnez **Update information** (Actualiser les informations) dans le menu ⋮
4. Installez la mise à jour et redémarrez Home Assistant

Pour revenir aux versions stables, désactivez **Pre-release**. HACS ne propose alors plus que des versions stables, et vous gardez la bêta jusqu'à ce que la prochaine version stable la remplace. Pour revenir immédiatement, ouvrez Klipsch Flexus dans HACS, sélectionnez ⋮ > **Redownload** (Retélécharger) > **Need a different version?** (Besoin d'une version différente ?), choisissez la version la plus récente sans la mention *pre-release*, téléchargez-la et redémarrez Home Assistant.

## Découverte automatique

La barre de son est découverte automatiquement sur votre réseau via **mDNS / Zeroconf** (protocole Google Cast).

Une fois la barre de son allumée, Home Assistant la détecte et affiche une notification :
> **Klipsch Flexus CORE 300** trouvé à `192.168.1.100`. Voulez-vous ajouter cette barre de son ?

**Fonctionnement :**
- La barre de son s'annonce sous le nom `Flexus-Core-*` via le service mDNS `_googlecast._tcp`
- L'intégration identifie l'appareil grâce aux enregistrements TXT `md` (modèle) et `fn` (nom convivial)
- Les appareils proxy AirCast sont automatiquement filtrés

Si la découverte automatique ne fonctionne pas (p. ex. isolation réseau), vous pouvez toujours ajouter l'intégration manuellement en saisissant l'adresse IP.

## Configuration

| Paramètre | Par défaut | Description |
|-----------|------------|-------------|
| Adresse IP | — | Adresse IP de la barre de son (obligatoire) |
| Intervalle d'interrogation | 15 s | Réglable dans les Options (5–120 s). En veille, l'intégration interroge toujours toutes les 60 s |
| MAC de l'appareil | détectée automatiquement | Uniquement dans les Options (facultatif). Remplace la MAC utilisée pour signer les écritures du firmware 2026 ; nécessaire seulement si des commandes autres que volume / sourdine échouent (voir le capteur de diagnostic **MAC de signature**) |

**Conseil :** attribuez une IP statique / une réservation DHCP à la barre de son pour un fonctionnement fiable.

Vous pouvez changer l'adresse IP plus tard via **Reconfigurer** (Paramètres > Appareils > Klipsch Flexus > Reconfigurer).

## Fonctionnement

La barre de son expose une API HTTP locale sur le port 80 :
- `GET /api/getData` — lecture des paramètres
- `POST /api/setData` — écriture des paramètres (corps JSON ; repli GET historique pour les anciens firmwares)
- `GET /api/getRows` — liste de données structurées (filtres Dirac)

Sur le firmware 2026, les écritures signées HMAC partent à la place vers `POST https://<IP>/api/setData`.

### Conception robuste pour un appareil lent

La Klipsch Flexus dispose d'un **serveur HTTP mono-thread** qui traite une seule requête à la fois. L'intégration est construite autour de cette contrainte :

| Mécanisme | Description |
|-----------|-------------|
| Sérialisation des requêtes | Tous les appels API passent par `asyncio.Lock` — aucune requête simultanée |
| Nouvel essai avec temporisation | Les écritures (sauf les commandes multimédia) et la sonde d'alimentation sont réessayées 2 fois avec 0,5 s de délai ; les lectures de l'interrogation ne sont pas réessayées (repli sur le cache), et deux délais d'attente consécutifs terminent l'interrogation avec l'état hors ligne |
| Délais d'attente adaptatifs | 8 s en lecture, 10 s en écriture, 15 s pour les commandes d'alimentation |
| Dégradation progressive | Les lectures échouées se rabattent sur les dernières valeurs connues en cache |
| Mises à jour optimistes | L'interface se met à jour instantanément et garde la valeur écrite jusqu'à ce que la prochaine interrogation régulière la relise (l'interrogation ~1 s après une commande récupère ses effets de bord, p. ex. le décodeur après un changement d'entrée) ; les valeurs appliquées en veille sont mises en cache pour que l'interrogation en veille ne les annule jamais |
| **Interrogation adaptée à la veille** | L'état d'alimentation est sondé en premier ; la première interrogation après la configuration lit tout une fois, même en veille — ensuite, en veille, l'interrogation fait 1 requête au lieu d'environ 40, les valeurs en cache sont conservées et l'intervalle passe à 60 s. Les réglages restent **disponibles et pilotables** en veille — l'appareil applique les écritures et l'intégration les mémorise |

## Entités

![Page de l'appareil Klipsch Flexus dans Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*La page de l'appareil de l'intégration dans Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + interrupteurs) et le journal d'activité.*

| Entité | Type | Catégorie |
|--------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Mode nuit / Mode dialogue / Préréglage EQ / Filtre Dirac / Luminosité de la LED / Délai d'inactivité | Select (x6) | Configuration |
| Arrière haut / gauche / droit, Avant haut, Latéral gauche / droit | Number (x6) | Configuration |
| Caisson filaire / Caissons sans fil | Number (x2) | Configuration |
| Graves / Médiums / Aigus | Number (x3) | Configuration |
| Délai de synchronisation labiale, Balance | Number (x2) | Configuration |
| Synchronisation labiale auto, Contournement de l'égaliseur, Allumage automatique, Sons de l'interface, Modes sonores supplémentaires, Appairage auto de la télécommande BLE, Mise à jour auto du firmware | Switch (x7) | Configuration |
| Loudness, Ne pas déranger, Veille auto | Switch (x3) | Configuration |
| Temps de réponse, Statut : Appareil, Entrée active, Mode son | Sensor (x4) | Diagnostic |
| MAC de signature, Liaison réseau | Sensor (x2) | Diagnostic |
| Mode de fonctionnement, Test des haut-parleurs, Délai : caisson filaire / sans fil, Délai : surround sans fil | Sensor (x5, lecture seule) | Diagnostic |

**Total : 41 entités** (1 media player + 6 selects + 13 numbers + 10 switches + 11 sensors)

## Dépannage

| Problème | Solution |
|----------|----------|
| Connexion impossible | Vérifiez que la barre de son est sur le même réseau. Essayez : `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entités indisponibles | L'application Klipsch interroge peut-être l'appareil en même temps — fermez-la et réessayez |
| Mises à jour lentes | Augmentez l'intervalle d'interrogation dans les Options (Paramètres > Appareils > Klipsch Flexus > Configurer) |
| Les commandes autres que volume / sourdine échouent | Consultez le capteur de diagnostic **MAC de signature**. S'il n'affiche aucune MAC résolue (ou une mauvaise), saisissez la MAC de la barre de son dans **MAC de l'appareil** dans les Options |
| L'intégration ne se charge pas | Cherchez des erreurs d'import dans les journaux de Home Assistant. Vérifiez que vous utilisez HA 2024.11+ |
| Logo invisible avec le thème sombre | Passez à la v2.5.19+ et redémarrez. L'icône pour le thème sombre est fournie avec l'intégration et nécessite HA 2026.3+ ; les versions plus anciennes de HA affichent l'icône noire du site HA brands |

## Limitations connues

- Une barre de son par entrée d'intégration (ajoutez-en plusieurs comme entrées séparées)
- Pas de gestion multiroom / des groupes surround sans fil (utilisez l'application Klipsch Connect Plus)
- Le pilotage passe uniquement par l'API HTTP native, pas par les protocoles Cast ou AirPlay. Google Cast est une entrée sélectionnable (lancez la lecture depuis une application Cast) ; AirPlay ne figure pas dans la liste des entrées de l'appareil et n'est donc pas proposé comme source (le streaming vers la barre depuis un appareil Apple n'est pas affecté)
- La configuration initiale doit être faite **entièrement** dans l'application officielle Klipsch Connect Plus — effectuez toute la configuration au moins une fois (c'est ce qui provisionne l'identifiant d'authentification des écritures du firmware 2026)

## Sécurité

Consultez [SECURITY.md](../SECURITY.md) pour la politique de sécurité et les bonnes pratiques.

**Avertissement sur la sécurité réseau :** la barre de son communique en HTTP non chiffré, et son API locale est de fait non authentifiée sur le réseau local. Les anciens firmwares n'exigeaient aucune authentification ; le firmware 2026 (`1.1.3.x`) signe la plupart des écritures (`HMAC_SHA256_AES256`), mais ce n'est **pas une vraie barrière de sécurité** — l'identifiant est dérivé de la MAC de l'appareil (qu'il divulgue sans authentification) et d'une constante codée en dur, commune à toute la gamme : n'importe quel hôte du réseau peut donc le forger. Les lectures restent ouvertes (voir [Compatibilité firmware](#️-compatibilité-firmware-mise-à-jour-2026)). **Gardez la barre de son sur un segment réseau de confiance / isolé.** Analyse complète dans le [rapport d'évaluation de sécurité](SECURITY_ASSESSMENT_CORE_300.md) (section 12).

## Résultats des tests

[![pytest, Home Assistant actuel](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest, plus ancien Home Assistant pris en charge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![CI locale signée](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

Tous les tests tournent sur la machine du mainteneur, pas sur GitHub. Les cinq premiers badges affichent les résultats de cette exécution locale signée pour le dernier commit vérifié sur `main` (le badge *Signed local CI* indique son SHA court et sa date). GitHub ne les écrit qu'après avoir vérifié les preuves signées. *Verify signed local CI* est cette vérification sur GitHub. *HACS validation* est le contrôle du dépôt par HACS, exécuté sur GitHub.

Vous pouvez vérifier les preuves vous-même (Python 3.11 ou plus récent, git, OpenSSH) :

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` contient la clé publique de signature du mainteneur. Comparez-la avec les clés de signature SSH que GitHub liste pour le mainteneur : `curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`. Détails dans [TESTING.md](TESTING.md#test-result-badges) (en anglais).

## Contributeurs

Merci à toutes les personnes qui ont signalé des problèmes et envoyé des correctifs :

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — a découvert que le volume de la barre de son va de 0 à 50, et non de 0 à 100, et a corrigé la conversion ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — a remplacé l'état de lecteur multimédia `STANDBY`, supprimé de Home Assistant, pour que l'intégration continue de fonctionner sur Home Assistant 2026.12+ ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Voir la [liste complète des contributeurs](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Contribuer et obtenir de l'aide

- **Questions et idées** : [GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions). Voir [SUPPORT.md](../SUPPORT.md) pour savoir quoi inclure.
- **Bugs** : ouvrez une [issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose) avec le formulaire de bug et joignez les diagnostics.
- **Problèmes de sécurité** : signalez-les en privé, voir [SECURITY.md](../SECURITY.md).
- Les **pull requests** sont les bienvenues. [CONTRIBUTING.md](../CONTRIBUTING.md) explique comment tester votre modification et comment le mainteneur la vérifie. [TESTING.md](TESTING.md) décrit les tests et la CI locale signée.
- Toutes les personnes qui participent suivent le [Code de conduite](../CODE_OF_CONDUCT.md).

## Licence

MIT — voir [LICENSE](../LICENSE).
