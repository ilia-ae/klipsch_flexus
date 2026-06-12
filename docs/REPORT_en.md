# FIELD REPORT: investigating "they changed the exchange" (Flexus Core 300, May-2026 firmware)

A chronicle of reverse-engineering the new Klipsch Flexus protocol, written as the
work happened. The technical reference lives in
[`PROTOCOL_2026_CHANGES.md`](PROTOCOL_2026_CHANGES.md); this is the *story* — what we
did, what we found, where we tripped. 🇷🇺 Russian original: [`REPORT.md`](REPORT.md).

---

## Day 1 — 2026-06-11

### The setup
The integration stopped controlling the bar. The user's hypothesis: "they changed the
exchange." In hand — two PCAPdroid captures (mode switches) and a live bar at `10.0.1.51`.

### What the traffic showed
- In the pcap almost all device traffic moved to **TLS:443**; on :80 only the event
  long-poll remained: `GET /api/event/pollQueue?queueId={UUID}&timeout=5`.
- The event responses (cleartext :80) revealed the real changes the user was making:
  `dialogMode`, `nightMode`, `audioDecoder`, `player:volume` — **the data model is the same**.

### Live probing of the device (read-only / idempotent)
- `getData` on :80 and :443 — **works**, same format → reads are not broken.
- TLS cert on :443 — self-signed **Klipsch-CA** (issued May 28, 2026). This is the
  "half-turn" of security the user complained about.
- `getData settings:/webserver/authMode` → **`setData`**.
- An unsigned `POST /api/setData` (gated path) → **401 Forbidden**.
- `GET /api/setData` (the integration's old fallback) → **405 "Strict HTTP required!"**.
- The 401 returns `WWW-Authenticate: HMAC_SHA256, HMAC_SHA256_AES256` — **no salt/nonce**.

**Conclusion:** it isn't the data model that broke, it's **writes** — they now must be signed.

### Tearing apart the app
- APK `com.klipsch.connectxp` v2.3.7 — **Flutter**. Logic is in `libapp.so` (Dart AOT),
  not in Java (jadx is useless). `libdc/libduff` are Dirac Live, not our channel.
- Dart-AOT decompilation via **blutter** (built a matching Dart 3.10.0-232 SDK).
- The function names gave away the scheme immediately: `generateUsernameFromMac` /
  `generatePasswordFromMac` + `HmacAuthHelper` (`generateAuthHeader`, `setCredentials`).

### 🔓 Cracking the password derivation
The body of `generatePasswordFromMac` (asm):
```
cleaned  = MAC.replaceAll(RegExp("[^A-F0-9]"), "")     // UPPER hex, 12 chars
password = base64( utf8( cleaned + "KlipschSupport!!88" ) )
```
The "secret" is a **hardcoded string `KlipschSupport!!88`** + the public MAC. So anyone
on the LAN reproduces the password → zero protection against a real attacker, friction
only for legitimate clients. Confirmed by the user: "there is no password prompt"
(the app derives it itself from the MAC).

For the bar (wired MAC `34:3D:7F:00:2F:3D`):
`password = MzQzRDdGMDAyRjNES2xpcHNjaFN1cHBvcnQhITg4`. Wired into `auth.py`.

### Signature shape (from asm `generateAuthHeader`)
```
nonce  = base64(SecureRandom)                 // client-side
ts     = DateTime.now().toUtc() micros / N
aesKey = sha256(password)                      // 32 bytes
iv     = random 16 bytes
cipher = base64( AES(aesKey, iv).encrypt(body) )   // the body is ENCRYPTED
sig    = base64( HMAC_SHA256(key, utf8(<dot-joined canonical>)) )
header = "HMAC_SHA256_AES256 " + F1.F2.F3.F4
```
The `HMAC_SHA256_AES256` scheme encrypts the body (AES-CBC, random IV) and signs it.
Blind brute-forcing was off the table — too many unknowns. Decision: capture ground
truth **dynamically**.

### Pivot to an emulator + Frida
No Frida/root on the physical phone, but there is an Android emulator. Stood up
`Pixel_8_API_35` (arm64-v8a — runs the app's native libs directly), `adb root`
available, pushed **frida-server 17.11.0**, installed the Klipsch APK. Goal: hook
`generateAuthHeader` (offset `0x6d7ce0` in libapp.so) and capture the finished
`Authorization` + AES key/IV/canonical string live.

**Status (interim):** emulator `Pixel_8_API_35` up (arm64, `adb root`), frida-server
17.11 pushed, app installed and launched, emulator **pings the bar**.

### Emulator dead-end — three blockers
Capturing a live signature on the emulator is blocked by three things at once:
1. **No BLE** — the app needs Bluetooth to read the MAC and see the bar; the emulator
   has no BLE.
2. **No mDNS through NAT** — ping to `10.0.1.51` works, but Cast/eureka discovery
   (multicast) does not cross the emulator NAT.
3. **TLS without symbols** — Dart-HTTP goes through its own BoringSSL inside
   `libflutter.so`; the `SSL_write`/`SSL_read` symbols are stripped (0 exports, 0
   symbols) → a byte-pattern hook is needed (friTap-style).

Each blocker is solvable, but that's three separate sub-reverses with an unclear outcome.

### Decision: deterministic reconstruction from asm + the bar as oracle
The emulator capture is shelved. We already have: the cracked password, the full
signature **shape** from asm, and an **oracle — the bar itself** (`200` vs `401` on an
idempotent setData). What's left is reading off 4 byte-level details (order of the 4
header fields, order of the canonical string, AES mode, HMAC key) and validating
hypotheses straight against `10.0.1.51`.

(The emulator + frida are left running — useful if we decide to capture ground truth
dynamically after all via friTap + a Frida MAC override.)

### Reconstructing `generateAuthHeader` from asm (in detail)
Decompilers (`r2 pdc`, r2ghidra) don't help with Dart AOT — they don't resolve the
string pool/symbols; the best representation is annotated blutter asm. Tracing the
stack slots (`[fp, x17]`, x17 = negative offset) gave:

| Slot | Holds | How obtained |
|---|---|---|
| `-360` (`-0x168`) | **nonce** | `base64(SecureRandom bytes)` |
| `-368` (`-0x170`) | DateTime / **timestamp** | `micros`, `sub`(epoch), `sdiv /1000` → **milliseconds** |
| `-384` (`-0x180`).field_f | **cipher** | `base64(AES.encrypt(body))` → placed in a map → `JsonStringStringifier.stringify` = request body |
| `-304` (`-0x130`) | function **arg2** | parameter of generateAuthHeader |
| `-312` (`-0x138`) | **arg3** | parameter |
| `-328` (`-0x148`) | **arg6** | parameter |
| `-336` (`-0x150`) | (input to Hmac — probably key/password) | loaded into x2 right before `Hmac::Hmac` |

**Pipeline:**
```
nonce  = base64(SecureRandom)                         // slot -360
ts     = (DateTime.now().toUtc().micros - epoch)/1000 // ms, slot -368
aesKey = sha256(password)   // _Sha256 @0x6d8240, 32 bytes
iv     = SecureRandom 16 bytes
cipher = base64(AES(aesKey, iv).encrypt(jsonBody))    // body is encrypted → JSON
canonical = A.B.C.D.E         // 5 values joined by "." (interpolate @0x6d8be4):
            slot-328 . nonce(-360) . slot-336 . slot-312 . slot-416
msg    = utf8(canonical)
sig    = base64( Hmac(sha256, key).convert(msg) )     // key loaded from -336
header = "HMAC_SHA256_AES256 " + F1.F2.F3.F4           // 4 fields joined by "."  (@0x6d8cd4)
```

**Still NOT pinned byte-exact (the remainder):**
1. The arg-slot mapping (-304/-312/-328) ↔ {method, path, body} — the parameter order of
   `generateAuthHeader(...)` (check the call-site in `stream_unlimited_api_service.dart`).
2. The HMAC key: `utf8(password)` or `aesKey` (what exactly is in slot -336).
3. AES mode (`encrypt` package: `AESMode.sic`/`cbc`) + where the IV goes (one of the 4
   header fields, or prepended to the cipher).
4. The identity of the 4 header fields `F1.F2.F3.F4` (probably username/nonce/ts/sig or
   nonce/ts/iv/sig).

**CONFIRMED (header interpolation @0x6d8cd4, slots resolved):**
```
Authorization: HMAC_SHA256_AES256 {ts_ms}.{nonce}.{username}.{base64_sig}
                                   -368    -360    -336        -432
```
- `ts_ms` = `DateTime.now().toUtc().micros/1000` (milliseconds), NOT part of the signature.
- `nonce` = `base64(SecureRandom)`.
- `username` = `user` (slot -336 — also in the canonical string, so it is NOT the secret).
- `sig` = `base64(HMAC_SHA256(key, utf8(canonical)))`.

The canonical string (signed) = dot-join of the set
`{arg6(-328), nonce(-360), username(-336), arg3(-312), cipher(-416)}` — the order and the
exact identity of the arg-slots (method/path/body) are not yet 100% pinned.

**Assessment:** a binary oracle (401 with no hint) + AES-over-the-body + the residual
uncertainty in the canonical-string order make the last few percent disproportionately
expensive by static analysis. The header and password are closed; for a byte-exact
`build_signature` the most efficient path is **dynamic capture**.

### 🎯 Capturing the signature — SUCCESS (iPhone + WireGuard-MITM)
An HTTP proxy didn't catch the bar traffic (Flutter sends to the local IP bypassing the
proxy; and iOS Flutter ignores the system proxy). The fix: **mitmproxy in WireGuard
mode**, `AllowedIPs = 10.0.1.51/32` (only the bar through the tunnel, discovery stays on
the direct Wi-Fi), `--ssl-insecure` (accept the bar's Klipsch-CA cert). The app does
**not** pin to the bar — mitmproxy decrypted it. Captured 17 live signed setData calls:

```
POST https://10.0.1.51/api/setData
Authorization: HMAC_SHA256_AES256 dXNlcg==.UpnlFt5z.1781204748147.gncG+ZgSG5WsjzMtVoWOsRpZNw3c4VAo5AS2NLwXtyQ=
Body: {"path":"settings:/cinema/dialogMode","role":"value","value":"<base64 AES, 80B>"}
```
Header (exact): `HMAC_SHA256_AES256 {base64(username)}.{nonce}.{ts_ms}.{base64(sig)}`
where `dXNlcg==`=base64("user"), nonce=6 bytes, ts=ms, sig=32 bytes.

### The offline-crack wall
With a real `sig` as an EXACT oracle, brute-forced offline:
- HMAC: ~10 key derivations × all orderings of 2–5 fields (method/path/role/ts/user/nonce/
  cipher as strings and raw bytes), both MACs → **0 matches**.
- AES body: ~7 keys × 6 MAC forms × {CBC,CTR,CFB,OFB} × {IV=ct[:16]/ct[-16:]/zero/
  sha256(nonce)/sha256(ts)} × {full/skip16/trim16} → **0 readable**.

Conclusion: the key derivation is **NOT a simple** function of the derived password
(maybe a PBKDF / extra salt / a different MAC), or the app obtains the password
differently. Ground truth is needed: a Frida hook on an emulator with the app connected
to the bar. The emulator blocker (no BLE/mDNS) is bypassable if the app shows the bar
from a **Klipsch cloud account** (connect by IP, not mDNS) — then a hook on
`generateAuthHeader`/`_getPassword`/`Hmac.convert` yields the exact key+canonical.

Capture artifacts: `/tmp/klip_flows.log` (17 signatures).

### Full header capture + ground-truth attempts (Frida)
Re-captured with ALL headers: **there is no separate IV header** (the IV is embedded in
the cipher or derived). The 200 responses have a known plaintext
(`postProcessorMode="music"`). Offline AES/HMAC cracking even with the known plaintext
still didn't converge (the key derivation is non-trivial, probably from the bar's
BLE-MAC, which isn't in the Product Info).

**Frida ground-truth — device matrix:**
- **iPhone** (working MITM capture) — no JB, no Frida.
- **Samsung Galaxy Z Fold6** — built a frida-gadget APK (objection: merge split→universal
  + inject gadget into `lib/arm64-v8a/`, re-sign), installed it. But **Knox/RKP blocks the
  Interceptor**: the gadget loads, memory reads work, `attach` succeeds with no error, BUT
  trampolines aren't written — even hooks on `memcpy`/`clock_gettime` (thousands of
  calls/sec) fire 0 times. A dead wall on locked Samsung flagships.
- **Android emulator (Pixel_8_API_35)** — Frida **WORKS** (`[HB] clock_gettime fired` —
  Interceptor alive, no Knox), the app launches. BUT it **can't see the bar**: discovery =
  mDNS `_sues800device._tcp` (+ISCP, the bar doesn't answer it), and multicast doesn't
  reach the bar through the emulator NAT; the mDNS query itself is sent by the **system
  mdnsd**, not the app (Frida on the app doesn't catch it). An ISCP request to
  `10.0.1.51:60128` — no answer.

**Bottom line:** device asymmetry — Samsung sees the bar but has no Frida (Knox); the
emulator has Frida but can't see the bar (NAT/multicast). Neither alone yields ground
truth. **A clean finish needs any NON-Samsung physical Android** (native discovery there
*and* Frida works; the gadget APK is already built: `~/Desktop/Klipsch-frida.apk`).

### Day 2 — rig on a OnePlus Nord CE (rooted, Android 13)

The device hunt continued. First we tried a **Redmi 5 Plus** (rooted, WiFi ADB) — but it's
**Android 7.1.2 (SDK 25)**, and the app needs minSdk 28; even with a lowered minSdk
(apktool: drop the adaptive-icon, `minSdkVersion 25`, re-sign, `su -c pm install` around
the MIUI block) Android 7 is too old. What worked was a **OnePlus Nord CE (EB2103)**:
Android 13 (SDK 33), arm64, **Magisk root**, NOT Samsung. Connected over **USB** (also
tried WiFi ADB as root: `setprop service.adb.tcp.port 5555; stop/start adbd`); install as
root via `su -c pm install`.

**What was confirmed:**
- **Frida Interceptor WORKS** (self-test: hook `malloc` + call it from the script → fired;
  trampoline check: the `malloc` bytes change after `attach`). No Knox.
- frida-server 17.11 + the app installed and launch.

**Technical gotchas (solvable):**
1. **`extractNativeLibs`**: when `false` (apktool rebuild `patched-a.apk`) libapp.so is
   mapped straight from the APK and file offsets don't match runtime. Fix — install an APK
   with `extractNativeLibs=true` (`Klipsch-frida.apk`, objection) → libapp.so is extracted
   to disk.
2. **The "16KB page alignment" turned out to be a FALSE diagnosis (red herring).** At first
   it looked like some offsets "drifted" because of 16KB gaps. Re-checking disproved it:
   with `extractNativeLibs=true` (libapp.so on disk) **all** blutter offsets match (they
   read as the prologue `fd79bfa9`), and the "shift" was an artifact of
   `extractNativeLibs=false` (the APK-loaded `patched-a.apk`) + reading from a
   foreign/restarted process (the gadget). The real causes of the "zeros": ① the wrong APK
   variant, ② **attaching to an idle app** (with no bar it executes almost no Dart). A
   signature scan wasn't needed.

### 🎯 RIG VALIDATION — PASSED (OnePlus, away from the bar)

Before going home, we ran the whole Frida pipeline first on the emulator
(`Pixel_8_API_35`, 4KB — an exact copy), then on the OnePlus itself. **Everything works:**

| Check | Emulator | OnePlus (live) |
|---|---|---|
| PAGE_SIZE | 4096 | 4096 |
| Offsets (`0x6d7ce0`/`0x5dfff0`/`0x6213b0`/`0x6d49a4`) | ✅ prologue `fd79bfa9` | ✅ prologue `fd79bfa9` |
| Interceptor patches libapp (trampoline written) | ✅ | ✅ |
| Hooks **fire** | ✅ interp+print | ✅ **interp=182, print=19 / 10s** |
| Reading Dart string **contents** | — | ✅ reading live logs |

Real strings captured live from the OnePlus (proof we see both structure and content):
```
[PRINT]  HomePage: Cleared navigation flags on return to home
[STRING] HomePage: Currently connected devices: []      ← no bar (we're not home)
[STRING] HomePage: Building with 0 devices
[PRINT]  AppUpdateService: App is up to date. Current version: 2.3.7
[STRING] 2026-06-12T06:34:13.926Z
```

**Two keys to success** (after a run of "zeros"):
1. **`spawn`, not `attach`**: Frida launches the app from scratch and catches active
   initialization (a lot of Dart runs at startup). Attaching to an idle app (the "search"
   screen, `connected devices: []`) catches almost nothing.
2. **An APK with `extractNativeLibs=true`** (`Klipsch-frida.apk`) → libapp.so on disk →
   blutter offsets match 1:1.

`generatePasswordFromMac`/`generateAuthHeader` stay silent **only because the bar isn't
present** (the `connected devices: []` line). Calling these functions directly from Frida
is impossible (Dart-AOT, not C-ABI: they need the `THR`/`PP` registers) — so ground truth
is captured by **natural execution**: onboarding to the bar calls
`generatePasswordFromMac`, switching a mode calls `generateAuthHeader`.

### Endgame — exactly one step left (at home, next to the bar)
1. Connect the OnePlus, `spawn` the app under Frida with the hook (the hook is ready:
   catches `generatePasswordFromMac` onLeave = password, `generateAuthHeader`/the canonical
   interpolation = canonical+key+nonce+ts).
2. In the app, go through onboarding to the bar + switch a mode.
3. Capture the exact **password + canonical string + HMAC key + AES params** → finish
   `build_signature` in `auth.py` → verify against the bar to **200** → the integration
   controls mode/EQ/channels again.

**Key offsets** (blutter, libapp.so v2.3.7, `extractNativeLibs=true`):
`generatePasswordFromMac` `0x6d49a4` (arg=MAC in x1), `generateAuthHeader` `0x6d7ce0`,
`base64Encode` `0x6d4838`, canonical interpolation (return) `0x6d8be8`, Dart `print`
`0x6213b0`, `_interpolate` `0x5dfff0`. Capture via **`frida spawn`** + an onLeave/onEnter hook.

**Artifacts:** capture of 17 signatures `/tmp/klip_flows.log`; gadget APK
`~/Desktop/Klipsch-frida.apk`; working hook `/tmp/hook.js` + driver `/tmp/op_spawn.py`;
decompilation in `.reverse/blutter_out/`.

### 🏁 FINALE — at home next to the bar: signature cracked and working (HTTP 200)

At home (OnePlus on the same WiFi as the bar) we built the rig and captured ground truth.
The path to success:

1. **With attach to the live process the hooks did NOT fire** (the trampoline is written
   to memory, but the CPU executes the old code of the hot Dart function from icache).
   Cured only by **spawn** — patch before the first execution. Python `device.spawn`
   intermittently times out → it landed reliably via the **frida CLI**:
   `sleep 600 | frida -D <serial> -f <pkg> -l hook.js` (keep stdin alive).
2. **Writes are NOT Basic-auth** (curl Basic → 401). The app logs showed: `setData`
   succeeds on the first try (200), `HmacAuthHelper: hasCredentials user / MzQz...` — i.e.
   an HMAC_SHA256_AES256 signature, and the 401-challenge is only a fallback before
   provisioning.
3. **Captured via hooks** `generateAuthHeader` (method/url/body), `Hmac.convert`
   (key+canonical), `Encrypter.encrypt` (AES key/iv/plaintext/cipher).

**The cracked algorithm** (reproduced in Python, the bar answered **200**, state really
changed — nightMode, dialogMode):

```
nonce = base64(6 rand);  ts = ms
key   = SHA256(base64decode(nonce) + password)     # one key for both AES and HMAC
value = base64(iv + AES_256_CBC(key, iv, PKCS7(compact_json(value))))
body  = json_pretty4(path, role=value, value)
sig   = base64(HMAC_SHA256(key, "user."+nonce+"."+ts+"."+url+"."+body))
Authorization: HMAC_SHA256_AES256 base64("user").nonce.ts.sig
```

Verification: the offline `build_set_data` matched the app **byte-for-byte** (value,
canonical, sig); live `set nightMode_1/off`, `dialog_*` → **HTTP 200** + a read-back
confirmed the change.

**Implementation and takeaways:**
- [`auth.py`](../custom_components/klipsch_flexus/auth.py) → `KlipschAuth.build_set_data(path, value)`
  returns `(body, headers)` for a signed `POST /api/setData`.
- [`tools/extract_secret.py`](../tools/extract_secret.py) — extracts the constant
  `KlipschSupport!!88` from an APK (exactly from a known password, or heuristically over
  the `libapp.so` strings — the secret surfaces as #0). For future app versions.
  **Self-contained:** downloads the package itself via `apkeep` (APKPure, ~144 MB **XAPK**)
  → unpacks the bundle and the nested split down to `lib/arm64-v8a/libapp.so` → finds the
  secret → deletes the archive. The full flow (download → extract → delete) is verified live.
- **Expiry:** none — the password is deterministic from MAC + a constant, no time/rotation.
- **Universality:** the secret is a shared constant in every Connect Plus v2.3.7 install →
  the formula `base64(MAC + "KlipschSupport!!88")` works for **every** Flexus owner (only
  the MAC varies, and it auto-discovers). The per-request key/nonce/iv the client generates
  itself — nothing to "catch" at runtime, it's all computed offline.
- **"Security":** theatre — a hardcoded constant + a public MAC; AES/HMAC over the derived
  key add no strength against a LAN attacker, they only raise the cost of interop. Details
  in `PROTOCOL_2026_CHANGES.md` (the "security theatre" section).
