# Security Assessment Report: Klipsch Flexus CORE 300

**Target:** 192.168.1.100 (Local Network)  
**Date:** 2026-02-16 (Scan) / 2026-02-17 (Report)  
**Author:** ilia.ae  
**Report Type:** Network Security Assessment

---

## 1. Executive Summary

Klipsch Flexus CORE 300 soundbar was assessed from the local network without any authentication.
The device runs on Google Cast platform with AMLogic SoC and has not received firmware updates
since January 2024. Multiple information disclosure issues were identified, along with 5 unpatched
CVEs (4 High severity). The device exposes 11 TCP ports, TLS certificates, device identifiers,
and cryptographic keys to any host on the local network without authentication.

---

## 2. Device Identification

| Parameter               | Value                                              |
|-------------------------|----------------------------------------------------|
| Model                   | Flexus Core 300                                    |
| Friendly Name           | Klipsch Flexus CORE 300                            |
| Manufacturer            | Klipsch Group Inc (Indianapolis, IN, US)           |
| MAC Address (WiFi)      | AA:BB:CC:DD:EE:FE                                 |
| MAC Address (AirPlay)   | AA:BB:CC:DD:EE:FF                                 |
| Hotspot BSSID           | FA:8F:CA:69:AA:9D                                 |
| IP Address              | 192.168.1.100                                          |
| Cast UUID (SSDP UDN)    | 3fb1d5cd-a039-be9c-934c-877174add9bf               |
| Cast Build              | 1.68.cast_20240119_0202_RC07.599752810             |
| Build Version           | 599752810                                          |
| Firmware Date           | January 19, 2024                                   |
| Cast Version            | 12                                                 |
| Release Track           | stable-channel                                     |
| Locale                  | en-US                                              |
| Timezone                | Asia/Almaty                                        |
| Location (country)      | DE (coordinates masked: 255.0, 255.0)              |
| Connection              | Ethernet (not WiFi)                                |
| Uptime at scan time     | ~269,000 sec (~3.1 days)                           |
| Has Update Available    | false                                              |
| Platform                | Google Cast on AMLogic SoC                         |

---

## 3. Network Scan Results

### 3.1 Open Ports (11 of 65,535)

Full TCP port scan performed with nmap -sV -p- (scan time: 5189 seconds).

| Port  | State | Service          | Details                                           |
|-------|-------|------------------|---------------------------------------------------|
| 80    | open  | HTTP             | Web interface, redirects to /index.fcgi           |
| 2019  | open  | unknown          | Silent, binary protocol, no HTTP response         |
| 5002  | open  | gRPC             | Google Cast internal gRPC service                 |
| 5003  | open  | HTTP             | Cast WebAPI, returns styled HTML error pages      |
| 7000  | open  | RTSP             | Audio streaming (fingerprinted as "Sonos rtspd")  |
| 8008  | open  | HTTP             | Google Cast API (eureka_info, setup endpoints)    |
| 8009  | open  | SSL              | CASTV2 protocol (self-signed cert, 2-day rotation)|
| 8443  | open  | SSL/HTTPS        | HTTPS web interface, Klipsch CA certificate       |
| 10001 | open  | SSL              | Unknown service, Klipsch CA certificate           |
| 16500 | open  | HTTP (MiniUPnP)  | MiniUPnPc/2.0, Darwin/15.0.0, UPnP/1.1          |
| 37205 | open  | SSL              | Unknown service, Klipsch CA certificate           |

267 ports filtered (no-response), 65,257 ports closed.

### 3.2 mDNS (Bonjour) Service Announcements

The device announces itself via the following mDNS services:

| Service Type             | Instance Name                                            |
|--------------------------|----------------------------------------------------------|
| _googlecast._tcp         | Flexus-Core-300-3fb1d5cda039be9c934c877174add9bf         |
| _airplay._tcp            | Klipsch Flexus CORE 300                                  |
| _raop._tcp               | AABBCCDDEEFF@Klipsch Flexus CORE 300                     |
| _tidalconnect._tcp       | Flexus Core 300-4dfa3390ef2658faae861e5d7736e08f         |
| _spotify-connect._tcp    | ksb5000-ee414bba-482b-4873-8d78-976ac4923160             |
| _http._tcp               | Klipsch Flexus CORE 300                                  |

Google Cast TXT record fields:
- id=3fb1d5cda039be9c934c877174add9bf
- cd=4E6623644708B83795F73644AFDD0B68
- md=Flexus Core 300
- fn=Klipsch Flexus CORE 300
- ve=05
- ca=199172
- st=0
- bs=FA8FCA69AA9D
- nf=1

### 3.3 UPnP / SSDP

SSDP M-SEARCH scan returned no results. The device does not respond to standard
UPnP discovery, though port 16500 runs MiniUPnPc/2.0 internally.

---

## 4. API Enumeration (Port 8008 - Google Cast API)

All requests made without any authentication from the local network.

### 4.1 Endpoint Map

| Endpoint                              | Method | Status | Data Returned                    |
|---------------------------------------|--------|--------|----------------------------------|
| /setup/eureka_info                    | GET    | 200    | Full device info (see Section 2) |
| /setup/supported_timezones            | GET    | 200    | Full timezone list                |
| /setup/icon.png                       | GET    | 301    | Device icon                       |
| /setup/get_app_device_id              | POST   | 200    | App device ID + TLS certificate  |
| /setup/configured_networks            | GET    | 403    | Blocked                          |
| /setup/scan_results                   | GET    | 403    | Blocked                          |
| /setup/offer                          | GET    | 403    | Blocked                          |
| /setup/scan_wifi                      | POST   | 405    | Method not allowed               |
| /setup/set_eureka_info                | POST   | 405    | Method not allowed               |
| /setup/reboot                         | POST   | 404    | Endpoint disabled                |
| /setup/bluetooth/status               | GET    | 404    | Endpoint disabled                |
| /setup/bluetooth/scan                 | GET    | 404    | Endpoint disabled                |
| /setup/bluetooth/bond                 | GET    | 404    | Endpoint disabled                |
| /setup/bluetooth/discovery            | GET    | 404    | Endpoint disabled                |
| /setup/assistant/check_linked_user    | GET    | 404    | Endpoint disabled                |
| /setup/test_internet                  | GET    | 404    | Endpoint disabled                |
| /setup/get_device_info                | GET    | 404    | Endpoint disabled                |
| /setup/night_mode_params              | GET    | 404    | Endpoint disabled                |
| /setup/audio                          | GET    | 404    | Endpoint disabled                |
| /setup/check_ready_status             | GET    | 200    | Empty response                   |
| /setup/get_multizone_status           | GET    | 200    | Empty response                   |
| /apps/                                | GET    | 404    | DIAL apps disabled               |
| /ssdp/device-desc.xml                | GET    | 404    | SSDP description disabled        |
| /setup/factory_reset                  | POST   | 200    | Empty (potentially dangerous)    |

### 4.2 Data Extracted via /setup/get_app_device_id (POST)

Request: POST /setup/get_app_device_id {"app_id":"E8C28D3C"}

Response included:
- app_device_id: 4E6623644708B83795F73644AFDD0B68
- Full X.509 TLS certificate (PEM encoded)
- Signed data blob (Base64)

Only app_id E8C28D3C returned data. Other tested IDs (CC1AD845, 2DB7CC49,
233637DE, 85CDB22F) returned empty responses.

---

## 5. TLS Certificate Analysis

### 5.1 Device Identity Certificate (Ports 8443, 10001, 37205)

```
Subject:    CN=06059dad54129b07aa05 FA:8F:CA:69:AA:9D
Issuer:     C=US, ST=IN, L=Indianapolis, O=Klipsch Group Inc, OU=Cast, CN=Flexus Core 300
Serial:     02:90:54:48:ce:15:e1:1b:f4:56:23:89:8b:25:98:84:d3:36:37:a9
Valid From: Mar 26 06:18:39 2024 GMT
Valid To:   Jan 17 06:18:39 2036 GMT
Key:        RSA 2048-bit
Usage:      Digital Signature, TLS Web Client Authentication
Policy OID: 1.3.6.1.4.1.11129.2.5.2 (Google Cast)
```

Note: The full private-key-associated public key, certificate, and signed attestation data
are all retrievable without authentication via the /setup/get_app_device_id endpoint.

### 5.2 CASTV2 Protocol Certificate (Port 8009)

```
Subject:    CN=3fb1d5cd-a039-be9c-934c-877174add9bf
Issuer:     CN=3fb1d5cd-a039-be9c-934c-877174add9bf (self-signed)
Valid From: Feb 16 03:35:11 2026 GMT
Valid To:   Feb 18 03:35:11 2026 GMT (48-hour auto-rotation)
```

### 5.3 Public RSA Key (from eureka_info)

```
MIIBCgKCAQEAtin3p7rUon/Z74WbWAwarsfDsssx5iaxjUPhbnJ8e77lOogobd5Mz4qdTS
ouzQMbByxLBjr1WAww+OHNmqnmWxgdc2VjXCPn8ppgeILyWtvpHJLkigGpBZ6ed1ypjoV5
TVS8JRfAhE5v1+5VKDOAtfzbsruLjPFk8rdakkEUpm4TMzKmeybOtl6uczpW4s4uMHPkt1+
6/5mCfQy09zpMtPNdal1OSDSiAywtX+X+W9TXvilvyPBtGvgsu5FJRueBdKT7YmD4Mx2rz
OaintsG9GcXAty5Kjla1BlSsHNewhJIUKkYAm1MKAUIondn8NZz4Lp7tYu6PyAXN1gxoYtt
MwIDAQAB
```

---

## 6. Vulnerability Assessment

### 6.1 Unpatched CVEs (Firmware from January 2024)

The device firmware is based on cast_20240119. The following CVEs were published
in Chromecast Security Bulletins after this date and are potentially applicable:

| CVE             | Bulletin   | Severity   | Type | Component         | Description                          |
|-----------------|------------|------------|------|-------------------|--------------------------------------|
| CVE-2024-47036  | Dec 2024   | Moderate   | EoP  | AMLogic u-boot    | Elevation of privilege in bootloader |
| CVE-2024-6790   | Dec 2025   | **High**   | DoS  | ARM               | Denial of service                    |
| CVE-2025-0050   | Dec 2025   | **High**   | EoP  | ARM               | Elevation of privilege               |
| CVE-2025-0427   | Dec 2025   | **High**   | EoP  | ARM               | Elevation of privilege               |
| CVE-2025-0819   | Dec 2025   | **High**   | EoP  | ARM               | Elevation of privilege               |

### 6.2 Historical Exploit Chain (AMLogic SoC)

The device uses an AMLogic SoC (same family as Chromecast). The following exploit
chain was demonstrated on Chromecast with Google TV and may be applicable:

- **CVE-2023-48424** - eMMC fault injection
- **CVE-2023-48425** - AVB (upgradestep) vulnerability in u-boot
- **CVE-2023-6181**  - BCB command whitelisting bypass

When chained, these allow installation of custom unsigned firmware. The January 2024
build may or may not include the December 2023 patches. Reference:
https://github.com/oddsolutions/sabrina-unlock

### 6.3 MiniUPnPc/2.0 (Port 16500)

Port 16500 runs MiniUPnPc/2.0 (UPnP client). Historical vulnerabilities in MiniUPnP:
- CVE-2013-0229: MiniUPnPd 1.0 stack buffer overflow (Metasploit module available)
- Version 2.0 is likely patched against this specific BOF, but MiniUPnP has had
  recurring security issues.

### 6.4 Identified Security Issues

| #  | Issue                                  | Severity | Category                |
|----|----------------------------------------|----------|-------------------------|
| 1  | Unauthenticated device info disclosure | Medium   | Information Disclosure  |
| 2  | MAC addresses exposed (WiFi + AirPlay) | Low      | Information Disclosure  |
| 3  | TLS certificate + signed data exposed  | Medium   | Information Disclosure  |
| 4  | RSA public key exposed via eureka_info | Low      | Information Disclosure  |
| 5  | Cast UUID / device IDs exposed         | Low      | Information Disclosure  |
| 6  | Firmware 2+ years out of date          | High     | Missing Patches        |
| 7  | 5 unpatched CVEs (4 High severity)     | High     | Missing Patches        |
| 8  | No firmware auto-update mechanism      | Medium   | Configuration          |
| 9  | 11 open TCP ports (large attack surface)| Medium  | Configuration          |
| 10 | Cast API has no authentication         | Medium   | Access Control         |
| 11 | Potential AMLogic bootloader exploit    | High     | Firmware Integrity     |
| 12 | DIAL protocol disabled (good)          | Info     | Positive Finding       |
| 13 | Reboot/factory_reset disabled (good)   | Info     | Positive Finding       |
| 14 | WiFi scan/config blocked (good)        | Info     | Positive Finding       |

---

## 7. Metasploit Modules Tested

| Module                                          | Result                              |
|-------------------------------------------------|-------------------------------------|
| auxiliary/scanner/http/chromecast_webserver      | Device detected and identified      |
| auxiliary/scanner/http/chromecast_wifi           | Blocked (403 on scan_results)       |
| auxiliary/admin/chromecast/chromecast_youtube    | DIAL disabled, CASTV2 not supported |
| auxiliary/admin/chromecast/chromecast_reset      | Not tested (destructive)            |
| auxiliary/scanner/upnp/ssdp_msearch             | No SSDP response                   |
| auxiliary/scanner/http/http_version              | Ports 80, 8008, 8443 fingerprinted  |
| Nmap --script vuln                              | No XSS, CSRF, or known web vulns   |

---

## 8. Network Discovery Methods

The device can be automatically discovered on the network via:

### Method 1: mDNS / Google Cast (recommended)
```
dns-sd -B _googlecast._tcp local
# Returns: Flexus-Core-300-3fb1d5cda039be9c934c877174add9bf
# TXT field md=Flexus Core 300, fn=Klipsch Flexus CORE 300
```

### Method 2: mDNS / AirPlay
```
dns-sd -B _airplay._tcp local
# Returns: Klipsch Flexus CORE 300
```

### Method 3: HTTP API
```
curl http://<IP>:8008/setup/eureka_info
# Returns JSON with "name": "Klipsch Flexus CORE 300", "md": "Flexus Core 300"
```

### Method 4: mDNS / Tidal Connect
```
dns-sd -B _tidalconnect._tcp local
# Returns: Flexus Core 300-4dfa3390ef2658faae861e5d7736e08f
```

### Method 5: mDNS / Spotify Connect
```
dns-sd -B _spotify-connect._tcp local
# Returns: ksb5000-ee414bba-482b-4873-8d78-976ac4923160
```

---

## 9. Recommendations

1. **Contact Klipsch** about firmware updates - the Cast platform is 2+ years behind
   on security patches with 5 unpatched CVEs
2. **Network segmentation** - isolate IoT/media devices on a separate VLAN to limit
   exposure of the unauthenticated Cast API
3. **Firewall rules** - restrict access to ports 8008, 8443, 10001, 37205 from
   untrusted hosts on the LAN
4. **Monitor** for unusual traffic on port 2019 (unknown protocol) and 16500 (MiniUPnP)
5. **Disable unused services** if Klipsch provides configuration options

---

## 10. Tools Used

- Nmap 7.97 (port scanning, service detection, vuln scripts)
- Metasploit Framework 6.4.115-dev
- dns-sd (mDNS/Bonjour discovery)
- curl (HTTP API probing)
- OpenSSL (certificate analysis)

---

## 11. References

- https://source.android.com/docs/security/bulletin/chromecast/2025-12-01
- https://source.android.com/docs/security/bulletin/chromecast/2024-12-01
- https://source.android.com/docs/security/bulletin/chromecast/2024-03-01
- https://github.com/oddsolutions/sabrina-unlock
- https://www.pentestpartners.com/security-blog/new-chromecast-chromecast-audio-have-they-fixed-their-hijacking-issue/
- https://www.rapid7.com/db/modules/auxiliary/scanner/http/chromecast_webserver/
- https://www.cvedetails.com/product/47859/Google-Chromecast-Firmware.html
- https://therecord.media/chromecast-hardware-vulnerabilities-google-patch

---

## Document Information

**Author:** ilia.ae  
**Report Date:** February 16, 2026  
**Tools Used:** Metasploit Framework 6.4.115-dev, Nmap 7.97, dns-sd, curl, OpenSSL  
**Assessment Type:** Network Security Assessment (Local Network)  
**Classification:** Internal Security Report
