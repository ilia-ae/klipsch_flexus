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

**Статус:** эмулятор готов, frida работает, приложение установлено. Дальше — подключить
приложение к бару, поймать подпись, дописать `build_signature`, проверить против бара
до `200`.
