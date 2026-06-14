# Klipsch Flexus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](../LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#descubrimiento-automático)

[![Validate](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/hassfest.yaml)
[![CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | **Español** | [Português](README_pt.md)

---

Integración personalizada de Home Assistant para barras de sonido **Klipsch Flexus** — control mediante **API HTTP local nativa**, sin nube, sin retrasos.

> ✅ **Actualizado a v2.5.12 (2026-06-13)** — **41 entidades**, todos los comandos de escritura verificados en vivo contra el firmware de 2026 (firmados con HMAC), controlables en standby. Las insignias de arriba reflejan la versión publicada y el último push.

## 📸 Panel (Dashboard)

Un panel Lovelace personalizado basado íntegramente en las entidades de la integración — entrada, modo de sonido, noche/diálogo, presets de EQ, filtro Dirac, tono (graves/medios/agudos), niveles de canales surround y subwoofers — todo en vivo por la API local.

![Panel de Klipsch Flexus](images/dashboard.png)

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

El estado en vivo por comando se ve en **Download diagnostics** (sección `command_health`, añadida en v2.4.2).

### Estado de la solución

✅ **Resuelto en v2.5.0 — control completo restaurado, no se requiere ninguna acción del usuario.** La firma de solicitudes `HMAC_SHA256_AES256` ya está implementada. La credencial del dispositivo se deriva automáticamente de la dirección MAC de la barra de sonido (que la integración ya detecta), por lo que **no hay nada que configurar** — solo actualiza la integración. Desde **v2.5.9** la MAC se lee de forma determinista del propio dispositivo (`settings:/system/primaryMacAddress`), por lo que la resolución funciona al primer intento en cada unidad (manteniendo el descubrimiento previo por registro/ARP como respaldo). Las escrituras firmadas van al endpoint HTTPS del dispositivo; volumen/silencio siguen funcionando sin firma.

> Requiere el paquete `cryptography` (declarado en el manifiesto; incluido con Home Assistant, por lo que ya está presente).

📖 **Cómo lo aplicamos ingeniería inversa** — la historia completa de la investigación (blutter, Frida, WireGuard-MITM, el análisis del «teatro de seguridad»): [informe](REPORT_en.md) (en inglés; ruso: [REPORT.md](REPORT.md)).

El firmware anterior (anterior a `1.1.3`) no se ve afectado y conserva el control completo mediante el respaldo `GET`.

## Características

### Reproductor multimedia
- **Volumen** — nivel, subir/bajar, silenciar
- **Encendido** — encender / modo espera
- **Fuente de entrada** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast
- **Modo de sonido** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Reproducción** — play/pausa, pista siguiente/anterior
- **Info multimedia** — título, artista, álbum, carátula, app de origen

### Niveles de canal (11 controles, -6 a +6 dB)

| Canal | Descripción |
|-------|-------------|
| Front Height | Altavoz de altura frontal Dolby Atmos |
| Back Height | Altavoz de altura trasero Dolby Atmos |
| Side Left / Right | Altavoces surround laterales |
| Back Left / Right | Altavoces surround traseros |
| Subwoofer Wireless 1 / 2 | Niveles de subwoofer inalámbrico |
| Bass / Mid / Treble | Controles de ecualización |

### Ajustes de audio (Selects)
- **Preajuste EQ** — Flat, Bass, Rock, Vocal
- **Modo nocturno** — reduce el rango dinámico para escucha silenciosa
- **Modo diálogo** — mejora la claridad del habla (3 niveles)
- **Dirac Live** — filtro de corrección de sala (detectado automáticamente del dispositivo)
- **Brillo del LED** — LED frontal: Apagado / Tenue / Brillante

### Ajustes numéricos
- **Retardo de labios (Lip-sync)** — sincronización A/V manual (0–300 ms)
- **Balance** — balance izquierda/derecha (−10…+10)
- **Tiempo de inactividad** — tiempo de inactividad para el modo espera automático (0–3600 s)

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
- **Descargar diagnósticos** — exportación completa del estado (Ajustes > Dispositivos > Klipsch Flexus > Descargar diagnósticos)

### Traducciones
Traducción completa de la interfaz en **7 idiomas**: inglés, ruso, alemán, español, francés, italiano, portugués. Todos los nombres de entidades, estados y pantallas de configuración están traducidos.

## Instalación

### HACS (recomendado)

1. Abra **HACS** > Integraciones > busque **Klipsch Flexus**
2. Instale y reinicie Home Assistant
3. La barra de sonido debería **descubrirse automáticamente** — revise las notificaciones
4. O vaya a **Ajustes** > Dispositivos y servicios > **Agregar integración** > Klipsch Flexus

### Manual

1. Copie `custom_components/klipsch_flexus/` al directorio `config/custom_components/` de su HA
2. Reinicie Home Assistant
3. Agregue la integración desde Ajustes > Dispositivos y servicios

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
| Intervalo de consulta | 15 s (60 s en standby) | Configurable en Opciones (5–120 s); se reduce automáticamente en modo de espera |

**Consejo:** Asigne una IP estática / reserva DHCP a la barra de sonido.

Puede cambiar la IP más tarde mediante **Reconfigurar** (Ajustes > Dispositivos > Klipsch Flexus > Reconfigurar).

## Cómo funciona

La barra de sonido expone una API HTTP local en el puerto 80:
- `GET /api/getData` — leer parámetros
- `POST /api/setData` — escribir parámetros (cuerpo JSON; fallback a GET para firmware antiguo)
- `GET /api/getRows` — listar datos estructurados (filtros Dirac)

### Diseño resiliente para un dispositivo lento

El Klipsch Flexus tiene un **servidor HTTP de un solo hilo** que procesa una petición a la vez. La integración está diseñada en torno a esta limitación:

| Mecanismo | Descripción |
|-----------|-------------|
| Serialización de peticiones | Todas las llamadas API pasan por `asyncio.Lock` — sin concurrencia |
| Reintento con espera | Errores temporales reintentados 2x con 0,5 s de espera |
| Timeouts adaptativos | 8 s lectura, 10 s escritura, 15 s comandos de encendido |
| Degradación elegante | Lecturas fallidas usan los últimos valores conocidos |
| Actualizaciones optimistas | UI se actualiza al instante, luego se verifica por polling; los valores aplicados en standby se almacenan en caché para que el sondeo en standby nunca los revierta |
| **Polling con detección de standby** | Primero se consulta el estado de energía; en standby solo 1 petición en vez de 20+, valores en caché preservados, intervalo reducido a 60 s. Los ajustes siguen **disponibles y controlables** en standby — el dispositivo aplica las escrituras y la integración las recuerda |

## Entidades

![Página del dispositivo Klipsch Flexus en Home Assistant](images/device-page.png)

*La página del dispositivo en Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + interruptores) y el registro de actividad.*

| Entidad | Tipo | Categoría |
|---------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Modo nocturno / Modo diálogo / Preajuste EQ / Filtro Dirac / Brillo del LED | Select (x5) | Configuración |
| Back Height / Left / Right, Front Height, Side Left / Right | Number (x6) | Configuración |
| Subwoofer Wireless 1 / 2 | Number (x2) | Configuración |
| Bass / Mid / Treble | Number (x3) | Configuración |
| Retardo de labios, Balance, Tiempo de inactividad | Number (x3) | Configuración |
| Auto Lip-sync, Bypass de EQ, Encendido automático, Sonidos de la interfaz, Modos de sonido adicionales, Auto-emparejamiento del mando BLE, Actualización automática del firmware | Switch (x7) | Configuración |
| Loudness, No molestar, Espera automática | Switch (x3) | Configuración |
| Tiempo de respuesta, Estado del dispositivo, Entrada activa, Modo de sonido activo | Sensor (x4) | Diagnóstico |
| MAC de firma, Enlace de red | Sensor (x2) | Diagnóstico |
| Modo de operación, Prueba de altavoces, Retardo de sub cableado/inalámbrico, Retardo de surround | Sensor (x5, solo lectura) | Diagnóstico |

**Total: 41 entidades** (1 reproductor + 5 selects + 14 numbers + 10 switches + 11 sensors)

## Solución de problemas

| Problema | Solución |
|----------|----------|
| No se puede conectar | Verifique que la barra de sonido esté en la misma red. Pruebe: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entidades no disponibles | La app Klipsch puede estar consultando simultáneamente — ciérrela |
| Actualizaciones lentas | Aumente el intervalo de consulta en Opciones |
| La integración no carga | Revise los logs de HA por errores de importación. Se requiere HA 2024.11+ |

## Limitaciones conocidas

- Una barra de sonido por entrada de integración (agregue varias por separado)
- Sin gestión de multiroom / grupos de altavoces inalámbricos (use Klipsch Connect Plus)
- AirPlay y Cast no se utilizan — solo la API HTTP nativa
- La configuración inicial debe completarse **por completo** en la app oficial Klipsch Connect Plus — todo el proceso al menos una vez (esto genera la credencial de escritura del firmware de 2026)

## Licencia

MIT — ver [LICENSE](../LICENSE).
