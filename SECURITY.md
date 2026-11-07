# Security Policy & Privacy Architecture

Ghostline is designed with a defense-in-depth security model prioritizing user privacy, local data sovereignty, and credential protection.

---

## 1. Supported Versions

| Version | Supported | Security Notes |
| :--- | :---: | :--- |
| **1.0.x** | **Yes** | Active release line with Windows DPAPI encryption and BYOK security |
| < 1.0.0 | No | Legacy prototype / development versions |

---

## 2. Core Security & Privacy Guarantees

### 1. Zero Telemetry & No Auto-Update
- Ghostline contains **zero** third-party telemetry, analytics beacons, user trackers, crash-reporting SDKs, or advertising libraries.
- Ghostline has **no background auto-updater** or silent polling threads. Updates are entirely user-directed.

### 2. Secure Credential & Profile Storage (Windows DPAPI)
- **API Keys (`credentials.bin`)**: All Bring-Your-Own-Key (BYOK) credentials for cloud providers (OpenAI, Anthropic, Gemini, Groq, OpenRouter, xAI) are encrypted using native Windows DPAPI (`CryptProtectData`) tied to the active Windows user account. Keys are never written to disk in plaintext.
- **Candidate Profile (`profile.bin`)**: Personal candidate profile information, resumes, and grounding facts are encrypted with Windows DPAPI.
- **In-Memory Masking**: API keys are masked in the UI (`sk-••••••••cdef`) and automatically redacted from application logs, exception traces, and crash dumps via real-time logging filters.

### 3. Provider Network Boundaries & TLS Enforcement
- **Local Ollama Daemon**: Communicates over local loopback (`http://127.0.0.1:11434`) strictly on the local machine.
- **Cloud Providers**: HTTPS transport encryption is strictly enforced for all cloud API requests. Unencrypted plain HTTP endpoints to remote hosts are blocked.
- **Custom Endpoints**: If a user configures a non-default custom endpoint, Ghostline requires explicit confirmation before transmitting API keys to unverified remote hosts.
- **Local Socket Listeners**: Ghostline creates zero listening TCP/UDP ports or open socket servers. Ghostline functions strictly as an outbound HTTP client.

### 4. Personal Profile Privacy Gating
- Candidate profile context is gated by the `allow_cloud` policy. By default (`allow_cloud=False`), candidate profile background is restricted to local models and is **never** sent to cloud API providers without explicit user consent.

### 5. Ephemeral Screen Captures & Data Retention
- Temporary screen capture bitmaps used during OCR are processed in memory and explicitly unlinked from disk in `finally:` blocks.
- Debug dumps (`debug_dump_enabled`) are disabled by default.
- Interaction history (questions, answers, transcripts) can be toggled off ("Don't save history"), retained for a configurable period (e.g. 30 days), or permanently purged at any time using the **Clear History** feature.

---

## 3. Reporting a Vulnerability

We welcome responsible security disclosures. If you discover a vulnerability or potential security risk in Ghostline:

1. **Do not create a public issue** on GitHub.
2. Please submit your finding through **GitHub Private Vulnerability Reporting** on the repository page:
   - Navigate to the repository's **Security** tab -> **Advisories** -> **Report a vulnerability**.
3. Alternatively, contact the security team directly by email:
   - **174149281+Mohammed-Ayyan@users.noreply.github.com**
4. Please include:
   - Type of issue (e.g. credential exposure, transport issue, path traversal, injection).
   - Step-by-step reproduction instructions or proof-of-concept.
   - Ghostline version and Windows OS build.
5. You will receive an acknowledgment within 48 hours, followed by coordinated disclosure and remediation.
