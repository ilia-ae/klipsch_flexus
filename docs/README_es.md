# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#descubrimiento-automático)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | **Español** | [Português](README_pt.md) | [Français](README_fr.md) | [Italiano](README_it.md) | [Nederlands](README_nl.md) | [中文](README_zh.md)  
🔒 **Seguridad**: [Política](../SECURITY.md) | [Informe de evaluación](SECURITY_ASSESSMENT_CORE_300.md)

---

Integración personalizada de Home Assistant para barras de sonido **Klipsch Flexus** — control mediante **API HTTP local nativa**, sin nube, sin retrasos.

> ✅ **42 entidades**. Todos los comandos de escritura están verificados en vivo con el firmware de 2026 (firmados con HMAC) y funcionan en standby. Cada commit en `main` se prueba primero en local: consulte [Resultados de las pruebas](#resultados-de-las-pruebas).

## 📸 Panel (Dashboard)

Un panel Lovelace personalizado basado íntegramente en las entidades de la integración — entrada, modo de sonido, noche/diálogo, presets de EQ, filtro Dirac, tono (graves/medios/agudos), niveles de canales surround y subwoofers — todo en vivo por la API local.

![Panel de Klipsch Flexus](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**Componentes HACS necesarios** (todos instalables vía [HACS](https://github.com/hacs/integration)):

| Componente | Repositorio | Para qué |
|------------|-------------|----------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | esta integración — las entidades |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | tarjeta del reproductor |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | botones de entrada/modo/EQ con estilo dinámico |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | resaltado del estado activo (CSS) |

📋 **YAML completo del panel + esquema de colores:** [docs/DASHBOARD.md](DASHBOARD.md)

### Modelos compatibles

| Modelo | Canales | Características |
|--------|---------|----------------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 drivers |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

La integración no comprueba el modelo. Añade cualquier barra de sonido Flexus que se anuncie por Google Cast y usa la misma API local y las mismas 42 entidades para todos los modelos. El mantenedor prueba con una CORE 300. Un control para hardware que su modelo no tiene (por ejemplo, los canales de altura de una CORE 100) puede fallar con un error.

> La barra de sonido debe **configurarse primero por completo en la aplicación oficial Klipsch Connect Plus** — complete todo el proceso de configuración al menos una vez (Wi-Fi, actualización de firmware, emparejamiento de altavoces, calibración Dirac). En el firmware de 2026 esto también genera la credencial de firma de comandos, por lo que una configuración a medias deja la mayoría de los comandos sin autorización. Esta integración solo se encarga del control diario.

## ⚠️ Compatibilidad de firmware (actualización 2026)

Una actualización de firmware de 2026 (**Device Version `1.1.3.x`**, p. ej. `1.1.3.0x7cd294e`, build de Cast `20250512_0201_RC25`) cambió la API HTTP local de dos formas:

1. **`setData` ahora requiere `POST` con cuerpo JSON.** El antiguo `GET /api/setData?...` devuelve `405 Strict HTTP required!`. **Corregido en v2.4.1** — actualiza la integración.
2. **La mayoría de las escrituras `setData` ahora requieren autenticación** (`settings:/webserver/authMode = setData`). Los comandos protegidos responden `401 Forbidden` con `WWW-Authenticate: HMAC_SHA256_AES256`. **Corregido en v2.5.0** — la integración ahora firma estas escrituras automáticamente.

### Qué funciona con el nuevo firmware

| Función | Estado |
|---------|--------|
| Todos los sensores / lecturas de estado (`getData`) | ✅ Funciona |
| Volumen, silencio (Mute) | ✅ Funciona |
| Entrada, modo de sonido, noche/diálogo, graves/medios/agudos, preajuste EQ, Dirac, niveles de subwoofer y surround, encendido | ✅ Funciona (firmado con HMAC, v2.5.0+) |
| LED, Lip-sync, Balance, Loudness, No molestar, Espera automática + 4 conmutadores más | ✅ Funciona (firmado; añadido en v2.5.8–2.5.9) — también en standby |

El estado en vivo por comando se ve en **Download diagnostics** (sección `command_health`, añadida en v2.4.2). Es de solo lectura: por comando indica si el ajuste se puede leer y cómo respondió el dispositivo a las escrituras hechas desde la última carga de la integración (`http_status`, `needs_auth` si el dispositivo pidió firma).

### Estado de la solución

✅ **Resuelto en v2.5.0 — control completo restaurado, no se requiere ninguna acción del usuario.** La firma de solicitudes `HMAC_SHA256_AES256` ya está implementada. La credencial del dispositivo se deriva automáticamente de la dirección MAC de la barra de sonido (que la integración ya detecta), por lo que **no hay nada que configurar** — solo actualiza la integración. Desde **v2.5.9** la MAC se lee de forma determinista del propio dispositivo (`settings:/system/primaryMacAddress`), por lo que la resolución funciona al primer intento en cada unidad (manteniendo el descubrimiento previo por registro/ARP como respaldo). Las escrituras firmadas van al endpoint HTTPS del dispositivo; volumen/silencio siguen funcionando sin firma.

> Requiere el paquete `cryptography` (incluido con Home Assistant, por lo que ya está presente; no figura como requisito en el manifiesto).

📖 **Cómo lo aplicamos ingeniería inversa** — la historia completa de la investigación (blutter, Frida, WireGuard-MITM, el análisis del «teatro de seguridad»): [informe](REPORT_en.md) (en inglés; ruso: [REPORT.md](REPORT.md)).

El firmware anterior (anterior a `1.1.3`) no se ve afectado y conserva el control completo mediante el respaldo `GET`.

## Características

### Reproductor multimedia
- **Volumen** — nivel, subir/bajar, silenciar
- **Encendido** — encender / apagar (espera de red)
- **Fuente de entrada** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast. Mientras una app de streaming (Spotify Connect, TIDAL Connect, QPlay), USB o la calibración Dirac está activa, la fuente lo muestra
- **Modo de sonido** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Reproducción** — play/pausa, pista siguiente/anterior
- **Info multimedia** — título, artista, álbum, carátula, app de origen

### Niveles de canal (11 controles: 9 de -6 a +6 dB, 2 subwoofers de -12 a +6 dB)

| Canal | Descripción |
|-------|-------------|
| Front Height | Altavoz de altura frontal Dolby Atmos |
| Back Height | Altavoz de altura trasero Dolby Atmos |
| Side Left / Right | Altavoces surround laterales |
| Back Left / Right | Altavoces surround traseros |
| Wired Subwoofer / Wireless Subwoofers | Salida de subwoofer con cable (RCA) y subwoofers inalámbricos (uno o dos, se ajustan juntos), -12 a +6 dB |
| Bass / Mid / Treble | Controles de ecualización |

### Ajustes de audio (Selects)
- **Preajuste EQ** — Flat, Bass, Rock, Vocal (+ Custom, que aparece al cambiar Bass / Mid / Treble — desde HA o la app Klipsch — o al ajustar una curva propia en la app; no se puede seleccionar desde HA)
- **Modo nocturno** — reduce el rango dinámico para escucha silenciosa
- **Modo diálogo** — mejora la claridad del habla (3 niveles)
- **Dirac Live** — filtro de corrección de sala (detectado automáticamente del dispositivo)
- **Brillo del LED** — LED frontal: Apagado / Tenue / Brillante
- **Tiempo de inactividad** — tiempo de inactividad antes del modo espera automático: Apagado / 5 / 10 / 15 / 30 min

### Ajustes numéricos
- **Retardo de labios (Lip-sync)** — sincronización A/V manual (0–500 ms)
- **Balance** — balance izquierda/derecha (−10…+10 dB)

### Conmutadores (Switches)
- **Auto Lip-sync** — retardo A/V automático
- **Bypass de EQ** — omite el ecualizador
- **Encendido automático** — comportamiento de encendido/espera automático
- **Loudness** — compensación de sonoridad a bajo volumen
- **No molestar** — suprime notificaciones/sonidos
- **Espera automática** — pasa a modo espera al estar inactivo
- **Sonidos de la interfaz**, **Modos de sonido adicionales**, **Auto-emparejamiento del mando BLE**, **Actualización automática del firmware**

> Todos los ajustes anteriores también se pueden escribir mientras la barra de sonido está en **standby** (el dispositivo los aplica y los conserva); la integración mantiene las entidades disponibles y recuerda el valor que estableciste en lugar de revertirlo.

### Diagnósticos
- **Tiempo de respuesta** — duración de la consulta API en ms, contadores de peticiones/errores
- **Estado del dispositivo** — Encendido / Espera / Sin conexión con info del decodificador, entrada y modo de sonido
- **MAC de firma** — la MAC usada para firmar las escrituras del firmware de 2026 (esquema, candidatos, estado resuelto)
- **Enlace de red** — interfaz activa cableada/inalámbrica, nombres de interfaz, orígenes de la MAC
- **Modo de operación** / **Prueba de altavoces** — estado del dispositivo de solo lectura (expuesto, deliberadamente no controlable)
- **Retardos de altavoces** (sub cableado/inalámbrico, surround inalámbrico) — solo lectura, calibrados automáticamente por el dispositivo
- **Descargar diagnósticos** — exportación completa del estado (Ajustes > Dispositivos > Klipsch Flexus > Descargar diagnósticos). Se ocultan la dirección IP, todas las direcciones MAC, el BSSID de la Wi-Fi, el ID del dispositivo y las URL de streaming

### Altavoces inalámbricos
- **Un dispositivo por altavoz emparejado** — los altavoces Flexus SUB / SURR (Subwoofer inalámbrico 1 / 2, Surround izquierdo / derecho) aparecen como dispositivos propios bajo la barra de sonido, con las versiones que muestra la app Klipsch Connect Plus (Product Information): el firmware de MCU, RX y EQ como *Firmware*, la versión de hardware y el número de modelo
- **Conectado** — un sensor por altavoz: activado si el enlace inalámbrico del altavoz funcionaba en la última lectura, desactivado si estaba caído
- **Cuándo se leen** — una vez tras la configuración y cuando pulse **Leer altavoces inalámbricos** (un botón de la barra de sonido), de modo que la consulta habitual sigue siendo tan ligera como antes. Para seguir las desconexiones en vivo, active **Supervisar altavoces inalámbricos** en Opciones: el enlace se lee entonces en cada consulta (una petición más), y un subwoofer que se desconecta queda reflejado en el historial del sensor Conectado. Los sensores supervisados no están disponibles en standby
- Un altavoz obtiene su dispositivo en cuanto se ha visto enlazado, y lo conserva mientras esté desemparejado o sin conexión. El dispositivo de un altavoz desemparejado se puede eliminar desde su página de dispositivo

### Traducciones
Traducción completa de la interfaz en **9 idiomas**: inglés, ruso, alemán, español, francés, italiano, portugués, neerlandés, chino simplificado (`zh-Hans`). Todos los nombres de entidades, estados y pantallas de configuración están traducidos.

## Instalación

### HACS (recomendado)

Klipsch Flexus está en la tienda predeterminada de HACS, así que no necesita añadir un repositorio personalizado.

[![Abra su instancia de Home Assistant y este repositorio en HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. Use el botón de arriba para abrir Klipsch Flexus en su HACS (enlace de My Home Assistant), o abra **HACS** y busque **Klipsch Flexus**
2. Seleccione **Descargar** y reinicie Home Assistant
3. La barra de sonido debería **descubrirse automáticamente** — revise las notificaciones
4. O vaya a **Ajustes** > Dispositivos y servicios > **Agregar integración** > Klipsch Flexus

### Manual

1. Copie `custom_components/klipsch_flexus/` al directorio `config/custom_components/` de su HA
2. Reinicie Home Assistant
3. Agregue la integración desde Ajustes > Dispositivos y servicios

### Actualización

Tras actualizar la integración (HACS o manual), **reinicie Home Assistant**: HA carga el código Python de la integración al arrancar, así que la nueva versión solo se ejecuta tras un reinicio. Cambiar las **Opciones** o **Reconfigurar** el host se aplica de inmediato, sin reinicio (la entrada se recarga).

### Versiones beta

Las nuevas funciones y correcciones salen primero como **beta**: una pre-release de GitHub con la etiqueta `vX.Y.Z-beta.N`. La versión estable `vX.Y.Z` llega después. HACS solo ofrece una beta a quien la activa. Si no hace nada, se queda en las versiones estables y no recibe avisos de las betas.

Para recibir betas (HACS 2.x; aquí se usan los nombres en inglés, su HACS puede mostrarlos traducidos):

1. Vaya a **Ajustes** > Dispositivos y servicios > **HACS** y abra la entrada de servicio **Klipsch Flexus** (HACS crea una por cada repositorio descargado)
2. Busque el interruptor **Pre-release** (una entidad de diagnóstico). Está deshabilitado por defecto: ábralo, seleccione el icono del engranaje, habilite la entidad y guarde el cambio
3. Active **Pre-release**. HACS ofrecerá entonces la beta más reciente como actualización. Para comprobarlo en el momento, abra Klipsch Flexus en HACS y seleccione **Update information** en el menú ⋮
4. Instale la actualización y reinicie Home Assistant

Para volver a la versión estable, desactive **Pre-release**. HACS volverá a ofrecer solo versiones estables, y usted conservará la beta hasta que la próxima versión estable la sustituya. Para volver de inmediato, abra Klipsch Flexus en HACS, seleccione ⋮ > **Redownload** > **Need a different version?**, elija la versión más reciente sin la marca *pre-release*, descárguela y reinicie Home Assistant.

## Descubrimiento automático

La barra de sonido se descubre automáticamente en su red mediante **mDNS / Zeroconf** (protocolo Google Cast).

Con la barra de sonido encendida, Home Assistant mostrará una notificación:
> Se encontró **Klipsch Flexus CORE 300** en `192.168.1.100`. ¿Desea agregar esta barra de sonido?

**Cómo funciona:**
- La barra se anuncia como `Flexus-Core-*` a través del servicio mDNS `_googlecast._tcp`
- La integración identifica el dispositivo por los registros TXT `md` (modelo) y `fn` (nombre)
- Los dispositivos proxy AirCast se filtran automáticamente

Si el descubrimiento automático no funciona (p.ej. aislamiento de red), siempre puede agregar la integración manualmente ingresando la dirección IP.

## Configuración

| Parámetro | Predeterminado | Descripción |
|-----------|---------------|-------------|
| Host | — | Dirección IP de la barra de sonido (obligatorio) |
| Intervalo de consulta | 15 s | Configurable en Opciones (5–120 s). En standby la integración consulta siempre cada 60 s |
| Supervisar altavoces inalámbricos | desactivado | Solo en Opciones. Comprueba en cada consulta si cada subwoofer / surround inalámbrico está enlazado (una petición más), para que las desconexiones se vean en su sensor **Conectado**. Desactivado: se lee tras la configuración y con el botón **Leer altavoces inalámbricos** |
| MAC del dispositivo | detectada automáticamente | Solo en Opciones (opcional). Sustituye la MAC usada para firmar las escrituras del firmware de 2026; solo hace falta si fallan los comandos distintos de volumen/silencio (vea el sensor de diagnóstico **MAC de firma**) |

**Consejo:** Asigne una IP estática / reserva DHCP a la barra de sonido.

Puede cambiar la IP más tarde mediante **Reconfigurar** (Ajustes > Dispositivos > Klipsch Flexus > Reconfigurar).

## Cómo funciona

La barra de sonido expone una API HTTP local en el puerto 80:
- `GET /api/getData` — leer parámetros
- `POST /api/setData` — escribir parámetros (cuerpo JSON; fallback a GET para firmware antiguo)
- `GET /api/getRows` — listar datos estructurados (filtros Dirac)

En el firmware de 2026, las escrituras firmadas con HMAC van en su lugar a `POST https://<IP>/api/setData`.

### Diseño resiliente para un dispositivo lento

El Klipsch Flexus tiene un **servidor HTTP de un solo hilo** que procesa una petición a la vez. La integración está diseñada en torno a esta limitación:

| Mecanismo | Descripción |
|-----------|-------------|
| Serialización de peticiones | Todas las llamadas API pasan por `asyncio.Lock` — sin concurrencia |
| Reintento con espera | Escrituras (salvo controles multimedia) y la consulta de energía reintentadas 2x con 0,5 s de espera; las lecturas del sondeo no se reintentan (valor en caché), y dos timeouts seguidos terminan el sondeo como offline |
| Timeouts adaptativos | 8 s lectura, 10 s escritura, 15 s comandos de encendido |
| Degradación elegante | Lecturas fallidas usan los últimos valores conocidos |
| Actualizaciones optimistas | UI se actualiza al instante y mantiene el valor escrito hasta el siguiente sondeo regular, que lo vuelve a leer (el sondeo ~1 s tras un comando recoge sus efectos secundarios, p. ej. el decodificador tras cambiar de entrada); los valores aplicados en standby se almacenan en caché para que el sondeo en standby nunca los revierta |
| **Polling con detección de standby** | Primero se consulta el estado de energía; el primer sondeo tras la configuración lee todo una vez, incluso en standby — después, en standby solo 1 petición en vez de ~40, valores en caché preservados, intervalo reducido a 60 s. Los ajustes siguen **disponibles y controlables** en standby — el dispositivo aplica las escrituras y la integración las recuerda |

## Entidades

![Página del dispositivo Klipsch Flexus en Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*La página del dispositivo en Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + interruptores) y el registro de actividad.*

| Entidad | Tipo | Categoría |
|---------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Modo nocturno / Modo diálogo / Preajuste EQ / Filtro Dirac / Brillo del LED / Tiempo de inactividad | Select (x6) | Configuración |
| Back Height / Left / Right, Front Height, Side Left / Right | Number (x6) | Configuración |
| Wired Subwoofer / Wireless Subwoofers | Number (x2) | Configuración |
| Bass / Mid / Treble | Number (x3) | Configuración |
| Retardo de labios, Balance | Number (x2) | Configuración |
| Auto Lip-sync, Bypass de EQ, Encendido automático, Sonidos de la interfaz, Modos de sonido adicionales, Auto-emparejamiento del mando BLE, Actualización automática del firmware | Switch (x7) | Configuración |
| Loudness, No molestar, Espera automática | Switch (x3) | Configuración |
| Tiempo de respuesta, Estado del dispositivo, Entrada activa, Modo de sonido activo | Sensor (x4) | Diagnóstico |
| MAC de firma, Enlace de red | Sensor (x2) | Diagnóstico |
| Modo de operación, Prueba de altavoces, Retardo de sub cableado/inalámbrico, Retardo de surround | Sensor (x5, solo lectura) | Diagnóstico |
| Leer altavoces inalámbricos | Button | Diagnóstico |
| Conectado (en el dispositivo de cada altavoz inalámbrico) | Binary Sensor (uno por altavoz emparejado, hasta 4) | Diagnóstico |

**Total: 42 entidades** (1 reproductor + 6 selects + 13 numbers + 10 switches + 11 sensors + 1 button), más un sensor Conectado por cada altavoz inalámbrico emparejado

## Solución de problemas

| Problema | Solución |
|----------|----------|
| No se puede conectar | Verifique que la barra de sonido esté en la misma red. Pruebe: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entidades no disponibles | La app Klipsch puede estar consultando simultáneamente — ciérrela |
| Actualizaciones lentas | Aumente el intervalo de consulta en Opciones |
| Fallan los comandos distintos de volumen/silencio | Revise el sensor de diagnóstico **MAC de firma**. Si no muestra una MAC resuelta (o muestra una incorrecta), introduzca la MAC de la barra de sonido como **MAC del dispositivo** en Opciones |
| La integración no carga | Revise los logs de HA por errores de importación. Se requiere HA 2024.11+ |
| El subwoofer o el surround inalámbrico se desconecta | Active **Supervisar altavoces inalámbricos** en Opciones y luego abra el dispositivo del altavoz bajo la barra de sonido: su sensor **Conectado** está desactivado mientras el enlace está caído, y su historial muestra cuándo se cayó. La barra de sonido indica entonces la ranura como vacía, así que esto es lo que la barra de sonido ve del enlace inalámbrico. Un altavoz cuya placa se bloquea mientras la radio sigue enlazada (sin sonido) sigue apareciendo como conectado; su atributo `mcu_responding` indica si la placa respondió en la última lectura (pulse **Leer altavoces inalámbricos** para comprobarlo). |
| Logo invisible en el tema oscuro | Actualice a v2.5.19+ y reinicie HA. El icono para el tema oscuro viene con la integración y requiere HA 2026.3+; las versiones anteriores muestran el icono negro del sitio de marcas de HA |

## Limitaciones conocidas

- Una barra de sonido por entrada de integración (agregue varias por separado)
- Sin gestión de multiroom / grupos de altavoces inalámbricos (use Klipsch Connect Plus)
- El control usa solo la API HTTP nativa, no los protocolos Cast ni AirPlay. Google Cast es una entrada seleccionable (inicie la reproducción desde una app con Cast); AirPlay no está en la lista de entradas del dispositivo, así que no se ofrece como fuente (transmitir a la barra desde un dispositivo Apple no se ve afectado)
- La configuración inicial debe completarse **por completo** en la app oficial Klipsch Connect Plus — todo el proceso al menos una vez (esto genera la credencial de escritura del firmware de 2026)

## Seguridad

Política de seguridad y buenas prácticas en [SECURITY.md](../SECURITY.md).

**Aviso de seguridad de red:** la barra de sonido se comunica por HTTP plano y su API local está prácticamente sin autenticación en la LAN. El firmware antiguo no requería autenticación alguna; el firmware de 2026 (`1.1.3.x`) firma la mayoría de las escrituras (`HMAC_SHA256_AES256`), pero **no es una barrera de seguridad real** — la credencial se deriva de la propia MAC del dispositivo (que divulga sin autenticación) más una constante fija en toda la gama, así que cualquier host de la red puede falsificarla. Las lecturas siempre están abiertas. **Mantén la barra de sonido en un segmento de red de confianza / aislado.** Análisis completo en el [informe de evaluación de seguridad](SECURITY_ASSESSMENT_CORE_300.md) (sección 12).

## Resultados de las pruebas

[![pytest, Home Assistant actual](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest, Home Assistant más antiguo compatible](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![CI local firmada](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

Todas las pruebas se ejecutan en el equipo del mantenedor, no en GitHub. Las cinco primeras insignias muestran los resultados de esa ejecución local firmada para el último commit verificado en `main` (la insignia *Signed local CI* muestra su SHA corto y su fecha). GitHub solo las escribe después de verificar la evidencia firmada. *Verify signed local CI* es esa verificación en GitHub. *HACS validation* es la comprobación del repositorio por HACS, que se ejecuta en GitHub.

Puede comprobar la evidencia usted mismo (Python 3.11 o posterior, git, OpenSSH):

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` contiene la clave pública de firma del mantenedor. Compárela con las claves SSH de firma que GitHub muestra para el mantenedor: `curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`. Más detalles en [TESTING.md](TESTING.md#test-result-badges) (en inglés).

## Colaboradores

Gracias a todos los que informan de problemas y envían correcciones:

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — descubrió que el volumen de la barra va de 0 a 50, no de 0 a 100, y corrigió la conversión ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — sustituyó el estado `STANDBY` eliminado del reproductor para que la integración siga funcionando en Home Assistant 2026.12+ ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Consulte la [lista completa de colaboradores](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Contribuir y soporte

- **Preguntas e ideas**: [GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions). Qué incluir: [SUPPORT.md](../SUPPORT.md).
- **Errores**: abra un [issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose) con el formulario de errores y adjunte los diagnósticos.
- **Problemas de seguridad**: infórmelos en privado, vea [SECURITY.md](../SECURITY.md).
- Los **pull requests** son bienvenidos. [CONTRIBUTING.md](../CONTRIBUTING.md) explica cómo probar su cambio y cómo lo verifica el mantenedor. [TESTING.md](TESTING.md) describe las pruebas y la CI local firmada.
- Todos los participantes siguen el [Código de conducta](../CODE_OF_CONDUCT.md).

## Licencia

MIT — ver [LICENSE](../LICENSE).
