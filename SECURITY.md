# Security Policy & Privacy Architecture

## 1. Supported Versions

| Version | Supported | Security Notes |
|:---|:---:|:---|
| 1.0.x | Yes | Current public release |
| < 1.0.0 | No | Legacy prototype / development versions |

---

## 2. Privacy & Local Architecture Guarantees

Ghostline is engineered from the ground up under a strict **Zero-Cloud, Zero-Telemetry** paradigm:

- **100% Offline Execution:** Ghostline contains zero tracking libraries, analytics SDKs, error reporting webhooks, or cloud phone-home routines.
- **Loopback-Only Socket Communication:** The only network socket initialized by Ghostline is a local HTTP connection to `http://127.0.0.1:11434` for communication with the user's locally installed Ollama daemon.
- **Ephemeral Screen Capture:** When the user initiates a capture (via `Alt + /` or hover), the captured screen bitmap exists in system RAM only for the duration of the OCR process. Temporary image files written to the Windows Temp directory are explicitly unlinked and purged immediately upon OCR completion.
- **Local User Data Isolation:** User configuration (`config.json`) and session logs (`history.jsonl`, `app.log`) are stored strictly within the user's local application data directory (`%APPDATA%\Ghostline`). They are never uploaded or synced to external servers.

---

## 3. Reporting a Vulnerability

If you discover a security vulnerability or unintended network egress in Ghostline, please report it responsibly:

1. **Do not create a public GitHub issue** for undisclosed security vulnerabilities.
2. Please email a description of the issue, reproduction steps, and platform details to:
   **mohammedsafwaan780@gmail.com**
3. You will receive an initial response within 48 hours acknowledging receipt of the report.
4. Once verified, a security patch will be prepared and released in a point release.
