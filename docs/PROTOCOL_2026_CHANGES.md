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
| Set mode / dialog / night / EQ / Dirac / channel levels / tone | ❌ **401** — needs HMAC signing (not yet implemented) |
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

### What's still needed (the exact byte-level algorithm)

The **bodies** of `generatePasswordFromMac` and `buildSignature` (salt/format, what
string is signed, which header carries the signature) are inside the Dart AOT and need
a Flutter-AOT decompiler. Options, in order of preference:

1. **`blutter`** on `libapp.so` — recovers pseudo-Dart for those two functions →
   gives the exact password derivation + signature construction. Heavy/version-specific
   build, but deterministic once it runs.
2. **Frida** on the running app — hook the two functions and dump the live
   username/password + the signed request for one `setData`. Needs a rooted/hookable
   device but is the fastest way to ground-truth.
3. Confirm against a **TLS-decrypted PCAPNG** if mitm can be made to work.

Once the derivation + signing are known, the integration computes
`user = generateUsernameFromMac(mac)`, `pass = generatePasswordFromMac(mac)` from the
device MAC it already discovers, then signs `POST /api/setData` per `buildSignature` —
restoring mode/dialog/night/EQ/channel writes. Volume/mute may also just need the
credential (they stay otherwise open but require POST, not the banned GET).

Artifacts: APK + extracted libs under `.reverse/` (gitignored).

See [`SECURITY_ASSESSMENT_CORE_300.md`](SECURITY_ASSESSMENT_CORE_300.md) — it already
notes a "signed data blob (Base64)" and TLS client-auth cert on a sibling Klipsch
device; consistent with this StreamUnlimited signing scheme.

## Notes
- PCAPdroid mitm with the **standard (user) CA did NOT decrypt** the soundbar traffic
  (the saved `.pcap` carries only plain-:80 events + opaque :443 TLS).
- Device API is **StreamUnlimited SDK** (`/api/getData|setData|getRows|event`).
