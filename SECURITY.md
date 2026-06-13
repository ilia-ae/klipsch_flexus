# Security Policy

## Reporting a Vulnerability

We take the security of Klipsch Flexus integration seriously. If you discover a security vulnerability, please follow responsible disclosure practices.

### How to Report

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them privately by:

1. **GitHub Security Advisories** (preferred):
   - Go to https://github.com/ilia-ae/klipsch_flexus/security/advisories
   - Click "New draft security advisory"
   - Fill in the details of the vulnerability

2. **Direct Contact**:
   - Email the maintainer directly through GitHub
   - Include detailed information about the vulnerability

### What to Include

Please provide the following information:
- Type of vulnerability (e.g., authentication bypass, injection, etc.)
- Full paths of affected source files
- Location of the affected code (tag/branch/commit)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability
- Potential fixes (if you have suggestions)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Varies based on severity and complexity

We will acknowledge your report, assess the vulnerability, and work with you to understand and resolve the issue. Once fixed, we will publicly credit you (unless you prefer to remain anonymous).

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

Security updates will be provided for the latest stable version only. Please ensure you're running the most recent version from HACS or GitHub releases.

## Security Considerations

### Network Security

This integration communicates with your Klipsch Flexus CORE 300 soundbar over your **local network** using HTTP:

- **No Cloud Connection**: All communication is local (device → soundbar)
- **HTTP Protocol**: Communication uses unencrypted HTTP (not HTTPS) as the soundbar firmware doesn't support TLS
- **Local Network Only**: The soundbar API should NOT be exposed to the internet

#### Best Practices

✅ **Keep your soundbar on an isolated or trusted network segment**
- Consider using VLAN isolation for IoT devices
- Use firewall rules to prevent soundbar from accessing the internet (if desired)

✅ **Secure your Home Assistant instance**
- Use strong authentication
- Enable HTTPS for Home Assistant UI
- Keep Home Assistant core and all integrations updated
- Review [Home Assistant Security Best Practices](https://www.home-assistant.io/docs/configuration/securing/)

✅ **Network Recommendations**
- Don't expose soundbar ports to the internet
- Don't forward port 80 from your soundbar to external networks
- Use WPA3 encryption for WiFi networks

### Home Assistant Integration Security

#### Authentication
- This integration uses Home Assistant's built-in authentication system
- No additional credentials are stored for the soundbar (it has no authentication)
- Configuration data is stored in Home Assistant's encrypted storage

#### Data Privacy
- **No telemetry**: This integration does not send any data outside your local network
- **No external APIs**: All operations are local HTTP requests
- **No cloud dependencies**: Works completely offline (after initial setup)

#### Permissions
The integration requires:
- Network access to communicate with the soundbar (local only)
- Home Assistant config entry management
- Standard Home Assistant entity creation

### Dependencies

This integration has **zero external Python dependencies** (see `manifest.json`):
- Uses only Python standard library and Home Assistant built-in libraries
- Reduces attack surface from third-party packages
- Uses `aiohttp` provided by Home Assistant core

### Code Security

#### Input Validation
- Host/IP addresses are validated during config flow
- API responses are validated before processing
- Timeout protections prevent hanging requests

#### Error Handling
- API errors are caught and logged without exposing sensitive data
- Failed requests are counted and monitored
- Graceful degradation when device is offline

#### Secure Coding Practices
- No use of `eval()` or `exec()`
- No shell command execution
- JSON parsing with proper exception handling
- Type hints for all functions (PEP 484)
- Async/await patterns to prevent blocking

## Security Assessment Report

### Klipsch Flexus CORE 300 Network Security Assessment

A comprehensive security assessment of the Klipsch Flexus CORE 300 soundbar was conducted in February 2026 covering:
- Network port scanning and service enumeration
- API security analysis
- TLS certificate inspection
- Vulnerability assessment (CVE tracking)
- Firmware update status
- Metasploit module testing

**Key Findings:**
- 11 open TCP ports with no authentication
- Firmware from January 2024 (2+ years old)
- 5 unpatched CVEs (4 High severity)
- Unauthenticated device information disclosure
- TLS certificates and cryptographic keys exposed to local network

📄 **[Read Full Security Assessment Report](docs/SECURITY_ASSESSMENT_CORE_300.md)**

The assessment validates the security limitations described in this document and provides detailed recommendations for network hardening.

## Known Limitations

### Soundbar Firmware Limitations
- The Klipsch Flexus CORE 300 firmware **does not provide authentication** for its HTTP API
- Any device on your local network can control the soundbar
- The soundbar API uses **HTTP (not HTTPS)** - this is a firmware limitation
- This integration cannot add security features that the hardware doesn't support

### Mitigation
These are hardware/firmware limitations, not integration bugs. To mitigate:
1. Keep the soundbar on a trusted network
2. Use network segmentation (VLANs) if possible
3. Don't expose the soundbar to untrusted devices or networks

## Security Updates

When security issues are fixed:
1. A patch version will be released immediately
2. A security advisory will be published on GitHub
3. Users will be notified through:
   - GitHub Security Advisories
   - Release notes
   - HACS update notifications

## Acknowledgments

We appreciate the security research community and will credit researchers who responsibly disclose vulnerabilities (with their permission).

## Additional Resources

- [Home Assistant Security](https://www.home-assistant.io/docs/configuration/securing/)
- [OWASP IoT Security](https://owasp.org/www-project-internet-of-things/)
- [CWE - Common Weakness Enumeration](https://cwe.mitre.org/)

---

**Last Updated**: February 17, 2026  
**Integration Version**: 1.4.0  
**Security Assessment**: [Klipsch Flexus CORE 300 Report](docs/SECURITY_ASSESSMENT_CORE_300.md)
