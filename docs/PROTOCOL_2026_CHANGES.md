# Klipsch Flexus — 2026 firmware protocol changes

What the May-2026 firmware changed in the device "exchange", reverse-engineered from
two PCAPdroid captures + live probing of the unit (`10.0.1.51`) on 2026-06-11.

> **TL;DR** — The data model is **unchanged** (same `settings:/…` / `cinema:/…` paths
> and value shapes). What changed is **transport + write authentication**:
> the firmware added an HTTPS:443 endpoint, moved event subscription behind TLS, and
> now **rejects unsigned writes** (`authMode=setData`). Reads still work over plain
> HTTP:80; **writes to DSP/mode/dialog/night/EQ are blocked (401) until HMAC-signed**.

## Evidence (live probes, read-only / idempotent)

| Request | Result |
|---|---|
| `GET http://10.0.1.51/api/getData?path=player:volume` | `[{"type":"i32_","i32_":21}]` — **200 OK** |
| `GET http://…/api/getData?path=settings:/cinema/dialogMode` | `[{"cinemaDialogMode":"dialog_2",…}]` — **200 OK** |
| `GET https://10.0.1.51/api/getData?…` (`-k`) | same JSON — **200 OK** (parallel TLS endpoint) |
| TLS cert on :443 | self-signed **O=Klipsch Group Inc, CN=Klipsch-device**, issuer **CN=Klipsch-CA**, valid **2026-05-28 → 2027-05-28** |
| `GET http://…/api/getData?path=settings:/webserver/authMode` | `[{"type":"webserverAuthMode","webserverAuthMode":"setData"}]` |
| `POST http://…/api/setData` dialogMode (unsigned, idempotent) | `{"error":…"Forbidden"}` — **401** |
| `GET http://…/api/setData?…` (any path, incl. volume) | `{"error":…"Strict HTTP required!"}` — **405** |
| `GET http://…/api/event/create` | `Not implemented!` — **501** |
| `GET http://…/api/event/subscribe?…` | `Not implemented!` — **501** |
| `GET http://…/api/event/pollQueue?queueId={unknown}` | `Unknown queue id!` — **400** |
| `GET http://…/api/event/pollQueue?queueId={app-registered}` | **200** — array of update events |

## The three changes

### 1. Parallel HTTPS:443 endpoint (new)
The device now serves the **same `/api/*` API over TLS** (TLSv1.3) in addition to
plain HTTP:80. Cert is self-signed by an on-device **Klipsch-CA** (not a public CA),
so any client must skip verification or trust Klipsch-CA. The official app talks 443.

### 2. Event subscription moved behind TLS (push model)
The app no longer just polls. It registers an **event queue** and long-polls it:

```
GET /api/event/pollQueue?queueId={UUID}&timeout=5      → [{path,itemValue,itemType:"update",rowsEvents}]
```

Queue **create + subscribe return 501 on plain :80** — they now happen only over
TLS:443. `pollQueue` itself works on :80 but only with a queueId registered via 443.
Event payloads are the same value shapes as `getData` (so once subscribed, parsing is
identical). Observed live events while switching modes:
`settings:/cinema/postProcessorMode` (movie/music), `settings:/cinema/dialogMode`
(dialog_1/2/3/off), `cinema:/nightMode` (nightMode_1/off), `cinema:/audioDecoder`,
`player:volume` (`i32_`), `player:player/data` (source/codec).

### 3. Write authentication hardened — **this is what breaks the integration**
`authMode=setData` means (per the device's own semantics):
- **volume / mute** — writes stay **open** (but must be **POST**; GET now 405).
- **everything else** (mode, dialog, night, EQ preset, Dirac, channel levels, bass/mid/
  treble, input, decoder) — **POST must be HMAC-signed**, else **401 Forbidden**.
- The legacy **GET `setData` form is banned outright** → `405 "Strict HTTP required!"`.

The official app writes these successfully over TLS:443 (the event stream shows the
changes landing), so the signature is valid and lives inside the encrypted channel.

## Impact on this integration

| Capability | State |
|---|---|
| Read all state (`getData`, `getRows`) on :80 | ✅ works |
| Set **volume / mute** | ✅ works **if** sent as POST (drop the GET fallback) |
| Set mode / dialog / night / EQ / Dirac / channel levels / tone | ✅ **solved** — `auth.py` `build_set_data` signs the write (HMAC_SHA256_AES256), confirmed live (HTTP 200) |
| Event-driven (instant) updates | ❌ not implemented (queue register is TLS-only) |

`probe_command_health()` already surfaces this: gated commands report
`needs_auth: true` / `http_status: 401`.

## The write-auth scheme (reverse-engineered from the app)

Source: official **Klipsch Connect Plus** app `com.klipsch.connectxp` **v2.3.7**
(2026-05-15). It is a **Flutter** app — the device-control logic is in the Dart AOT
snapshot `lib/arm64-v8a/libapp.so`, **not** in the Java/DEX layer (jadx finds only the
Flutter shell). `libdc.so`/`libduff.so` are the Dirac Live filter-design SDK (gRPC +
protobuf + boringssl), unrelated to the `/api/*` control channel.

Strings recovered from `libapp.so` reveal the full mechanism:

- API endpoints used by the app:
  `/api/getData`, `/api/getRows`, `/api/setData`,
  `/api/event/modifyQueue` (subscribe/unsubscribe — the queue register that returns
  501 on plain :80), `/api/event/pollQueue?queueId=`.
- Auth is a **per-device HTTP credential derived from the device MAC**, plus a
  **challenge-response signature**:
  - `generateUsernameFromMac(mac)`  → the webserver **username** (default seen: `user`)
  - `generatePasswordFromMac(mac)`  → the webserver **password**
  - `buildSignature(...)` + `authChallenge` + `HMac.withDigest`/`impl.digest.sha256`
    → request is signed with **HMAC-SHA256** in a challenge-response (`authChallenge`).
  - Crypto via **PointyCastle** (bundled in the Dart snapshot).
- Onboarding flow (log strings): the app **provisions** this password onto the device
  (`setWebserverPassword`, "Pushing webserver password to device (username: user)"),
  derived from / synced to the MAC ("Could not resolve MAC / sync credentials,
  skipping device password push"), and stores it locally
  (`hasWebserverPasswordCredentials`). That's why the unit already 401s unsigned
  writes — a MAC-derived password is set.

### Where each piece is computed (source map)

Recovered from `libapp.so` (Flutter AOT, Connect Plus v2.3.7). Symbol → role:

| App symbol | Computes | Integration slot (`auth.py`) |
|---|---|---|
| `generateUsernameFromMac(mac)` | webserver username (default `user`) | `generate_username_from_mac` |
| `generatePasswordFromMac(mac)` | webserver password from MAC ✅ **solved** | `generate_password_from_mac` |
| `authChallenge` / `WWW-Authenticate` parse | salt/nonce from the 401 | `parse_challenge` |
| `HMac.withDigest(impl.digest.sha256)` (PointyCastle) | `key = sha256(salt+password)`, `HMAC_SHA256` | `_derive_key` + `build_signature` |
| `buildSignature(...)` | canonical string + signature + header | `build_signature` |
| `setWebserverPassword` (onboarding) | pushes the MAC-derived password to the device | n/a (device already provisioned) |

The MAC itself is **not secret** — it is read from `eureka_info` (port 8008) and is also
visible in ARP/mDNS and the device's BLE advertisement (the app's `DeviceMacUtils` scans
BLE to obtain it). So `generatePasswordFromMac` is a reversible derivation, not a shared
secret: any LAN client can reproduce it. The 2026 "auth" therefore adds friction for
legitimate local clients (this integration) without changing the threat model — an
attacker on the same LAN derives the same credential. That reversibility is exactly what
lets us restore writes.

### Password derivation — **solved** (exact)

The body of `generatePasswordFromMac` is recovered verbatim from Connect Plus v2.3.7:

```
cleaned  = mac.replaceAll(RegExp("[^A-F0-9]"), "")    // keep UPPERCASE hex → 12 chars
password = base64( utf8( cleaned + "KlipschSupport!!88" ) )
```

The entire "secret" is the **hardcoded string `KlipschSupport!!88`** interpolated with the
**public MAC**, then Base64-ed. Base64 is an *encoding, not encryption* — the password is
trivially reversible (`base64 -d` → `343D7F002F3DKlipschSupport!!88`). There is no salt,
no KDF, no per-install secret. Worked example for MAC `34:3D:7F:00:2F:3D`:

```
cleaned  = 343D7F002F3D
password = base64("343D7F002F3DKlipschSupport!!88")
         = MzQzRDdGMDAyRjNES2xpcHNjaFN1cHBvcnQhITg4
```

> ⚠️ Note the regex keeps **uppercase** hex only — a lowercase MAC would lose its
> `a–f` digits. `eureka_info` reports the MAC uppercased; `auth.py` re-uppercases
> defensively so the derivation is casing-independent.

This is implemented in
[`generate_password_from_mac`](../custom_components/klipsch_flexus/auth.py) with a
known-answer test in [`tests/test_auth.py`](../tests/test_auth.py).

### Signature construction (`generateAuthHeader`) — **SOLVED** (confirmed live, HTTP 200)

Recovered from `libapp.so` (blutter) and pinned byte-exact with a **Frida** hook on the
running app (`HmacAuthHelper.generateAuthHeader`, `Hmac.convert`, `Encrypter.encrypt`),
then reproduced in pure Python and **accepted live by the device (HTTP 200, state changed)**.

Per signed `POST /api/setData`:

```
nonce      = base64(6 random bytes)                  # fresh per request, client-side
ts         = current time in milliseconds (string)
key        = SHA256( base64decode(nonce) + password )   # 32 bytes; the SAME key for AES and HMAC
iv         = 16 random bytes
cipher     = AES-256-CBC(key, iv).encrypt( PKCS7( compact_json(value) ) )
value_b64  = base64( iv + cipher )                   # IV prepended; no separate IV field
body       = json_pretty_4space({ "path": path, "role": "value", "value": value_b64 })
canonical  = "user" + "." + nonce + "." + ts + "." + "https://<host>/api/setData" + "." + body
sig        = base64( HMAC_SHA256(key, canonical) )
Authorization: HMAC_SHA256_AES256 {base64("user")}.{nonce}.{ts}.{sig}
```

Key facts that matter for re-implementation:
- **One 32-byte per-request key** (`SHA256(nonce_raw + password)`) does *both* the body
  AES-256-CBC encryption and the HMAC-SHA256 signature.
- The signed `body` is **pretty-printed** (4-space indent, key order `path, role, value`) —
  it must be serialized exactly so, because the signature covers those bytes.
- The encrypted `value` is the **compact** JSON of the value object; the IV is prepended to
  the ciphertext inside the Base64 (`base64(iv || cipher)`).
- **No server challenge/salt** — `nonce`, `iv`, `ts` are all client-generated. Everything is
  reproducible offline from the public MAC + the hardcoded `KlipschSupport!!88`. The
  `HMAC_SHA256_AES256` 401 challenge is only the *pre-provisioning* fallback path; once the
  device has a provisioned webserver password it accepts this scheme directly.

Implemented in [`auth.py`](../custom_components/klipsch_flexus/auth.py) as
`KlipschAuth.build_set_data(path, value) -> (body, headers)`; the integration sends those
verbatim over HTTPS (skip cert verification — self-signed Klipsch-CA). The constant can be
re-extracted from a future APK with [`tools/extract_secret.py`](../tools/extract_secret.py).

Artifacts: APK + extracted libs under `.reverse/` (gitignored).

See [`SECURITY_ASSESSMENT_CORE_300.md`](SECURITY_ASSESSMENT_CORE_300.md) — it already
notes a "signed data blob (Base64)" and TLS client-auth cert on a sibling Klipsch
device; consistent with this StreamUnlimited signing scheme.

## Security assessment — this is theatre, not security

Putting the pieces together, the 2026 write-"auth" provides **no meaningful protection**:

- The credential is `base64(UPPER_HEX_MAC + "KlipschSupport!!88")` — a hardcoded constant
  plus a value (the MAC) that is broadcast in ARP, mDNS, and BLE advertisements. Any device
  on the LAN computes the exact same password.
- Base64 is reversible encoding, not encryption; there is no salt, KDF, or per-unit secret.
- Net effect: a real attacker on the network is **unaffected** (they derive the credential
  in one line), while legitimate local clients — Home Assistant, this integration — are the
  only parties actually locked out until they reimplement the scheme. The change raised the
  cost of *interoperability*, not the cost of *attack*. It is a compliance-shaped checkbox,
  not a threat-model change.

### Context / timeline (author's note)

This integration and its reverse-engineering were documented publicly in
["Klipsch Flexus × Home Assistant"](https://ilia.ae/en/blog/digital/klipsch-flexus-home-assistant-integration/).
The May-2026 firmware (and Connect Plus v2.3.7, build 2026051321, identical on Android/iOS)
introduced the write-lock described above shortly afterward. Whether causally related or not,
the chosen mechanism does not withstand the same analysis the original article applied — a
follow-up writeup is in progress.

## Notes
- PCAPdroid mitm with the **standard (user) CA did NOT decrypt** the soundbar traffic
  (the saved `.pcap` carries only plain-:80 events + opaque :443 TLS).
- Device API is **StreamUnlimited SDK** (`/api/getData|setData|getRows|event`).
