# РАПОРТ: расследование «они поменяли обмен» (Flexus Core 300, прошивка май-2026)

Хроника реверс-инжиниринга нового протокола Klipsch Flexus. Пишется по ходу работ.
Технические детали — в [`PROTOCOL_2026_CHANGES.md`](PROTOCOL_2026_CHANGES.md);
здесь — репортаж: что делали, что находили, на чём спотыкались.

---

## День 1 — 2026-06-11

### Завязка
Интеграция перестала управлять баром. Гипотеза пользователя: «они поменяли обмен».
На руках — два захвата PCAPdroid (переключения режимов) и живой бар на `10.0.1.51`.

### Что показал трафик
- В pcap почти весь обмен с устройством ушёл на **TLS:443**, на :80 остался только
  long-poll событий `GET /api/event/pollQueue?queueId={UUID}&timeout=5`.
- Event-ответы (открытый :80) выдали реальные изменения, которые крутил пользователь:
  `dialogMode`, `nightMode`, `audioDecoder`, `player:volume` — **модель данных та же**.

### Живое прощупывание устройства (read-only / идемпотентно)
- `getData` на :80 и :443 — **работает**, формат прежний → читать ничего не сломано.
- TLS-серт :443 — self-signed **Klipsch-CA** (выдан 28 мая 2026). Это и есть «пол-оборота»
  безопасности, на который жаловался пользователь.
- `getData settings:/webserver/authMode` → **`setData`**.
- Неподписанный `POST /api/setData` (gated путь) → **401 Forbidden**.
- `GET /api/setData` (старый fallback интеграции) → **405 «Strict HTTP required!»**.
- 401 отдаёт `WWW-Authenticate: HMAC_SHA256, HMAC_SHA256_AES256` — **без соли/nonce**.

**Вывод:** сломалась не модель данных, а **запись** — её теперь надо подписывать.

### Разбор приложения
- APK `com.klipsch.connectxp` v2.3.7 — **Flutter**. Логика в `libapp.so` (Dart AOT),
  не в Java (jadx бесполезен). `libdc/libduff` — это Dirac Live, не наш канал.
- Декомпиляция Dart AOT через **blutter** (собрал совпадающий Dart 3.10.0-232 SDK).
- Имена функций сразу выдали схему: `generateUsernameFromMac` / `generatePasswordFromMac`
  + `HmacAuthHelper` (`generateAuthHeader`, `setCredentials`).

### 🔓 Взлом деривации пароля
Тело `generatePasswordFromMac` (asm):
```
cleaned  = MAC.replaceAll(RegExp("[^A-F0-9]"), "")     // UPPER hex, 12 символов
password = base64( utf8( cleaned + "KlipschSupport!!88" ) )
```
«Секрет» — **захардкоженная строка `KlipschSupport!!88`** + публичный MAC. То есть
любой в LAN воспроизводит пароль → защита от реального атакующего нулевая, трения —
только легитимным клиентам. Подтверждение от пользователя: «никакого запроса на пароль
нет» (приложение выводит его само из MAC).

Для бара (wired MAC `34:3D:7F:00:2F:3D`):
`password = MzQzRDdGMDAyRjNES2xpcHNjaFN1cHBvcnQhITg4`. Вписано в `auth.py`.

### Форма подписи (из asm `generateAuthHeader`)
```
nonce  = base64(SecureRandom)                 // клиентский
ts     = DateTime.now().toUtc() micros / N
aesKey = sha256(password)                      // 32 байта
iv     = random 16 байт
cipher = base64( AES(aesKey, iv).encrypt(body) )   // тело ШИФРУЕТСЯ
sig    = base64( HMAC_SHA256(key, utf8(<dot-joined canonical>)) )
header = "HMAC_SHA256_AES256 " + F1.F2.F3.F4
```
Схема `HMAC_SHA256_AES256` шифрует тело (AES-CBC, случайный IV) и подписывает. Слепой
перебор отпал — слишком много неизвестных. Решение: снять истину **динамически**.

### Поворот на эмулятор + Frida
Frida/root на реальном телефоне нет, но есть Android-эмулятор. Подняли
`Pixel_8_API_35` (arm64-v8a — нативно тянет либы приложения), `adb root` доступен,
залит **frida-server 17.11.0**, установлен APK Klipsch. Цель: хукнуть
`generateAuthHeader` (оффсет `0x6d7ce0` в libapp.so) и снять готовый `Authorization`
+ AES-ключ/IV/каноническую строку вживую.

**Статус (промежуточный):** эмулятор `Pixel_8_API_35` поднят (arm64, `adb root`),
frida-server 17.11 залит, приложение установлено и запущено, эмулятор **пингует бар**.

### Тупик эмулятора — три блокера
Поймать живую подпись на эмуляторе мешают сразу три вещи:
1. **Нет BLE** — приложению нужен Bluetooth, чтобы достать MAC и увидеть бар; у эмулятора
   BLE нет.
2. **Нет mDNS через NAT** — пинг до `10.0.1.51` проходит, но Cast/eureka-discovery
   (multicast) через эмуляторный NAT — нет.
3. **TLS без символов** — Dart-HTTP идёт через собственный BoringSSL внутри
   `libflutter.so`, символы `SSL_write`/`SSL_read` вырезаны (0 export, 0 symbol) →
   нужен byte-pattern хук (friTap-стиль).

Каждый блокер решаем, но это три отдельных под-реверса с неясным исходом.

### Решение: детерминированная реконструкция из asm + бар как оракул
Эмулятор для съёма подписи отложен. У нас уже есть: взломанный пароль, полная **форма**
подписи из asm, и **оракул — сам бар** (`200` vs `401` на идемпотентный setData).
Осталось дочитать 4 байтовые детали (порядок 4 полей заголовка, порядок канонической
строки, режим AES, ключ HMAC) и валидировать гипотезы прямо против `10.0.1.51`.

(Эмулятор + frida оставлены поднятыми — пригодятся, если решим всё же снять истину
динамически через friTap + Frida-подмену MAC.)

### Реконструкция `generateAuthHeader` из asm (детально)

Декомпиляторы (`r2 pdc`, r2ghidra) для Dart AOT не помогают — не резолвят строковый
пул/символы; лучшее представление — аннотированный asm blutter. Трассировка стек-слотов
(`[fp, x17]`, x17 = отрицательный офсет) дала:

| Слот | Что лежит | Как получено |
|---|---|---|
| `-360` (`-0x168`) | **nonce** | `base64(SecureRandom bytes)` |
| `-368` (`-0x170`) | DateTime / **timestamp** | `micros`, `sub`(эпоха), `sdiv /1000` → **миллисекунды** |
| `-384` (`-0x180`).field_f | **cipher** | `base64(AES.encrypt(body))` → кладётся в map → `JsonStringStringifier.stringify` = тело запроса |
| `-304` (`-0x130`) | **arg2** функции | параметр generateAuthHeader |
| `-312` (`-0x138`) | **arg3** | параметр |
| `-328` (`-0x148`) | **arg6** | параметр |
| `-336` (`-0x150`) | (вход в Hmac — вероятно ключ/пароль) | загружается в x2 прямо перед `Hmac::Hmac` |

**Конвейер:**
```
nonce  = base64(SecureRandom)                         // slot -360
ts     = (DateTime.now().toUtc().micros - epoch)/1000 // мс, slot -368
aesKey = sha256(password)   // _Sha256 @0x6d8240, 32 байта
iv     = SecureRandom 16 байт
cipher = base64(AES(aesKey, iv).encrypt(jsonBody))    // тело шифруется → JSON
canonical = A.B.C.D.E         // 5 значений через "." (interpolate @0x6d8be4):
            slot-328 . nonce(-360) . slot-336 . slot-312 . slot-416
msg    = utf8(canonical)
sig    = base64( Hmac(sha256, key).convert(msg) )     // key грузится из -336
header = "HMAC_SHA256_AES256 " + F1.F2.F3.F4           // 4 поля через "."  (@0x6d8cd4)
```

**Что ещё НЕ зафиксировано байт-точно (остаток):**
1. Соответствие arg-слотов (-304/-312/-328) ↔ {method, path, body} — порядок параметров
   `generateAuthHeader(...)` (смотреть в `stream_unlimited_api_service.dart` на call-site).
2. Ключ HMAC: `utf8(password)` или `aesKey` (slot -336 — что именно).
3. Режим AES (`encrypt` пакет: `AESMode.sic`/`cbc`) + куда кладётся IV (в одно из 4 полей
   заголовка или в начало cipher).
4. Идентичность 4 полей заголовка `F1.F2.F3.F4` (вероятно username/nonce/ts/sig или
   nonce/ts/iv/sig).

**ПОДТВЕРЖДЕНО (интерполяция заголовка @0x6d8cd4, слоты разрешены):**
```
Authorization: HMAC_SHA256_AES256 {ts_ms}.{nonce}.{username}.{base64_sig}
                                   -368    -360    -336        -432
```
- `ts_ms` = `DateTime.now().toUtc().micros/1000` (миллисекунды), НЕ входит в подпись.
- `nonce` = `base64(SecureRandom)`.
- `username` = `user` (slot -336 — он же в канонической строке, значит это НЕ секрет).
- `sig` = `base64(HMAC_SHA256(key, utf8(canonical)))`.

Каноническая строка (подписывается) = dot-join набора
`{arg6(-328), nonce(-360), username(-336), arg3(-312), cipher(-416)}` — порядок и точная
идентичность arg-слотов (method/path/body) ещё не закреплены на 100%.

**Оценка:** бинарный оракул (401 без подсказки) + AES-над-телом + остаточная
неопределённость порядка канонической строки делают последние проценты непропорционально
дорогими по статике. Заголовок и пароль — закрыты; для байт-точной `build_signature`
эффективнее всего **динамический съём**.

### 🎯 Перехват подписи — УДАЛСЯ (iPhone + WireGuard-MITM)
HTTP-прокси не ловил bar-трафик (Flutter шлёт local-IP мимо прокси; и iOS Flutter не
уважает системный прокси). Решение: **mitmproxy в режиме WireGuard**, `AllowedIPs =
10.0.1.51/32` (только бар через туннель, discovery остаётся на прямом Wi-Fi),
`--ssl-insecure` (принять Klipsch-CA серт бара). Приложение **не пиннится** к бару —
mitmproxy расшифровал. Поймано 17 живых подписанных setData:

```
POST https://10.0.1.51/api/setData
Authorization: HMAC_SHA256_AES256 dXNlcg==.UpnlFt5z.1781204748147.gncG+ZgSG5WsjzMtVoWOsRpZNw3c4VAo5AS2NLwXtyQ=
Body: {"path":"settings:/cinema/dialogMode","role":"value","value":"<base64 AES, 80B>"}
```
Заголовок (точно): `HMAC_SHA256_AES256 {base64(username)}.{nonce}.{ts_ms}.{base64(sig)}`
где `dXNlcg==`=base64("user"), nonce=6 байт, ts=мс, sig=32 байта.

### Стена офлайн-крека
Имея реальную `sig` как ТОЧНЫЙ оракул, перебрал офлайн:
- HMAC: ~10 дериваций ключа × все порядки 2–5 полей (method/path/role/ts/user/nonce/
  cipher в виде строк и сырых байт), оба MAC → **0 совпадений**.
- AES-тело: ~7 ключей × 6 форм MAC × {CBC,CTR,CFB,OFB} × {IV=ct[:16]/ct[-16:]/zero/
  sha256(nonce)/sha256(ts)} × {full/skip16/trim16} → **0 читаемых**.

Вывод: **деривация ключа НЕ простая** функция от выведённого пароля (возможно PBKDF/
доп.соль/иной MAC), либо пароль приложение берёт иначе. Нужен **ground-truth**: Frida-хук
на эмуляторе с приложением, подключённым к бару. Блокер эмулятора (нет BLE/mDNS) обходится,
если приложение покажет бар из **облачного аккаунта Klipsch** (коннект по IP, не mDNS) —
тогда хук `generateAuthHeader`/`_getPassword`/`Hmac.convert` выдаст точные key+canonical.

Артефакты захвата: `/tmp/klip_flows.log` (17 подписей).
