# Ghostline — Enterprise Security Audit & Hardening Report (Run 2 of 3)

**Date**: 2026-11-02  
**Target Repository**: Ghostline (Windows Desktop AI Assistant)  
**Branch**: `feature/hardware-controls-and-release`  
**Audit Scope**: Secrets, Personal Data, TLS & Endpoints, Code Injection & File Operations, Logging & Redaction, Data at Rest, Local Listeners, Dependencies (`pip-audit`, `bandit`), Licensing (`PyQt6` vs `PySide6`), Telemetry, and Frozen Build Integrity.

---

## 1. Executive Summary & Severity Table

| # | Security Domain | Finding | Severity | Status / Resolution | Evidence (File:Line) |
| :- | :--- | :--- | :---: | :---: | :--- |
| **1** | **Secrets in History & Tree** | Scanned all 46 commits and working tree; 0 live keys leaked; 2 mock test keys found. | **INFORMATIONAL** | **VERIFIED-AUTOMATED** | `ghostline/core/credentials.py:198`, `tests/test_byok_providers.py:42` |
| **2** | **Personal Data in Repo** | 0 personal resumes, logs, or AppData backups tracked in Git. | **PASSED** | **VERIFIED-AUTOMATED** | Git tree scan (`git ls-files`) |
| **3** | **TLS & Endpoint Transport** | Cloud endpoints default to HTTPS, but lacked strict scheme validation; `urllib.request` lacked protocol guard; no host confirmation. | **MEDIUM** | **RESOLVED** (Enforced HTTPS/loopback check; added non-default host confirmation prompt; replaced urllib with requests) | `ghostline/core/providers/base.py:40-95`, `ghostline/ui/qt_main_window.py:435, 875, 4625` |
| **4** | **Code Injection & Path Traversal** | 0 `eval`/`exec`/`pickle`; `cmd.exe` paths lacked quotes in MSIX fallback; resume parser lacked traversal & XML bomb limits. | **MEDIUM** | **RESOLVED** (Replaced cmd.exe with native Python; added path resolution, 25MB file limit, 50-page PDF limit, and 20MB XML decompression guard) | `ghostline/config.py:180, 260`, `ghostline/core/profile.py:100-180` |
| **5** | **Logging & Redaction** | Logging handlers lacked real-time credential filtering; keys or profile text could leak into logs/crash dumps. | **HIGH** | **RESOLVED** (Implemented `ghostline/core/redaction.py`, `RedactingLoggingFilter`, `RedactingFormatter`, and attached to all log handlers) | `ghostline/core/redaction.py:1-120`, `ghostline/app.py:240, 320` |
| **6** | **Data at Rest & Screenshots** | Debug dumps saved unredacted captures by default (`debug_dump_enabled=True`); history lacked retention and UI wipe. | **MEDIUM** | **RESOLVED** (Defaulted `debug_dump_enabled=False`; added retention purging `purge_retention`; added "Clear History" button and dialog) | `ghostline/config.py:43-45`, `ghostline/core/history_store.py:75-220`, `ghostline/ui/qt_main_window.py:2720, 4730` |
| **7** | **Local Listeners & IPC** | Zero TCP/UDP listening server sockets; zero open named pipes; only Windows named mutex for single instance. | **PASSED** | **VERIFIED-AUTOMATED** | Audit across `ghostline/` |
| **8** | **Dependency Audit** | `pip-audit` passed (0 CVEs on requirements.txt); `bandit` flagged 4 Medium items (urllib scheme, docx XML parsing, LLM SQL keyword false positive). | **LOW** | **RESOLVED** (All actionable items fixed; throwaway venv audit complete) | `.agent/tools/audit_venv/`, `reports/bandit_report.json` |
| **9** | **Licensing Analysis** | Project is MIT. PyQt6 is GPLv3 (requires GPL source disclosure on distribution unless commercial license or PySide6). | **LEGAL / NOTICE** | **DOCUMENTED** (Created `THIRD_PARTY_NOTICES.md`; documented PyQt6 vs PySide6) | `LICENSE`, `THIRD_PARTY_NOTICES.md` |
| **10** | **Telemetry & Auto-Update** | Confirmed zero external analytics, zero tracking beacons, zero background auto-update polling. | **PASSED** | **VERIFIED-AUTOMATED** | `ghostline/`, `SECURITY.md` |
| **11** | **Frozen Build Integrity** | `Ghostline.spec` missed dynamic imports (`profile`, `history_store`, `redaction`, `win_startup`); build stamp verified. | **LOW** | **RESOLVED** (Added all missing modules to `hiddenimports`; confirmed `build_info.json`) | `Ghostline.spec:40-50`, `ghostline/build_info.py` |

---

## 2. Detailed Findings & Remediations

### 2.1 Secrets & Git History Scan (Item 1)
- **Methodology**: Automated search across all 46 commits on all git branches using regex patterns for OpenAI (`sk-`), Anthropic (`sk-ant-`), OpenRouter (`sk-or-`), Groq (`gsk_`), Google AI (`AIza`), xAI (`xai-`), GitHub tokens (`ghp_`, `github_pat_`), and Bearer tokens.
- **Result**: Zero live secrets found in Git history or working tree.
- **Evidence**: The only matches were synthetic dummy keys:
  - `ghostline/core/credentials.py:198`: `sk-proj-1234567890abcdef` (docstring example)
  - `tests/test_byok_providers.py:42`: `sk-test-1234567890abcdef` (unit test mock)
- **Status**: **VERIFIED-AUTOMATED**.

### 2.2 Personal Data in Repository (Item 2)
- **Methodology**: Git tracked file inventory inspected for personal logs, real resumes, transcripts, database files, and `%APPDATA%` copies.
- **Result**: No personal data tracked. Datasets in `evaluation/` are synthetic computer science MCQs (`dev_mcq_01`).
- **Status**: **VERIFIED-AUTOMATED**.

### 2.3 TLS and Endpoints (Item 3)
- **Vulnerabilities Identified**:
  1. `ghostline/ui/qt_main_window.py:439` and `878` used `urllib.request.urlopen` with user-configurable endpoints without validating URL schemes, violating security best practices (Bandit B310).
  2. Cloud providers allowed plain HTTP if a user typed `http://...`.
  3. No explicit prompt or consent existed before transmitting API keys to non-default custom base URLs.
- **Remediation**:
  - Implemented `validate_provider_endpoint()` in `ghostline/core/providers/base.py`:
    - Enforces `https://` for cloud providers unless connecting to local loopback (`127.0.0.1`, `localhost`, `::1`).
    - Validates scheme is strictly HTTP or HTTPS.
    - Flags non-default remote hosts with `UNCONFIRMED_HOST:<host>`.
  - Added security confirmation modal in `qt_main_window.py:_save_settings()`: prompts user to explicitly confirm before transmitting keys to an unconfirmed host.
  - Replaced `urllib.request.urlopen` with `requests.get(..., timeout=...)` with scheme validation.
- **Tests Added**: `tests/test_endpoint_security.py` (4 tests, all passing).
- **Status**: **VERIFIED-AUTOMATED**.

### 2.4 Code Injection & Path Traversal (Item 4)
- **Vulnerabilities Identified**:
  1. `ghostline/config.py:183, 256`: Called `cmd.exe /c type <path>` and `copy /y <path>` without quoting, vulnerable to command injection or failure if username/path contained spaces or shell characters (`&`, `;`).
  2. `ghostline/core/profile.py:extract_text_from_file`: Did not resolve paths or check against Windows device names (`CON`, `PRN`, `NUL`), and lacked file size limits.
  3. `ghostline/core/profile.py:export_profile_json`: Allowed exporting without `.json` extension or writing into system directories.
  4. `.docx` extraction: `ET.fromstring(docx.read("word/document.xml"))` lacked decompression ratio/zip bomb limits (Bandit B314).
- **Remediation**:
  - Replaced `cmd.exe` calls in `ghostline/config.py` with native Python `open()` and `shutil.copyfile()`, falling back to safely quoted argument lists.
  - In `ghostline/core/profile.py`:
    - Enforced `.resolve()` and `is_file()` checks.
    - Blocked Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`).
    - Enforced 25MB file size limit for resumes, 20MB uncompressed limit for DOCX archives, and 50-page limit for PDFs.
    - Used `defusedxml.ElementTree` when available.
    - In `export_profile_json`: enforced `.json` extension and blocked writes to `C:\Windows`.
- **Tests Added**: `tests/test_file_security.py` (5 tests, all passing).
- **Status**: **VERIFIED-AUTOMATED**.

### 2.5 Logging & Sensitive Data Redaction (Item 5)
- **Vulnerabilities Identified**:
  - Logging handlers lacked real-time redaction. Exceptions or network errors containing API keys (`sk-`, `gsk_`, `AIza`, `Bearer`) or personal profile facts could be recorded to `%APPDATA%\Ghostline\ghostline.log` or console.
- **Remediation**:
  - Created `ghostline/core/redaction.py`:
    - Implemented `redact_sensitive_text()` covering all cloud provider key formats, bearer tokens, and registered secrets.
    - Implemented `RedactingLoggingFilter(logging.Filter)` and `RedactingFormatter(logging.Formatter)`.
    - Integrated redactor in `ghostline/app.py:setup_file_logging()`, `_qt_message_handler()`, and `ghostline/core/credentials.py`.
- **Tests Added**: `tests/test_security_redaction.py` (3 tests, all passing).
- **Status**: **VERIFIED-AUTOMATED**.

### 2.6 Data at Rest & Screenshot Retention (Item 6)
- **Vulnerabilities Identified**:
  1. `ghostline/core/pipeline.py:342`: `dump_enabled` defaulted to `True`, saving full screen captures (`01_raw_capture.png`) to `%APPDATA%\Ghostline\debug\` on every solve.
  2. Interaction history was persisted indefinitely with no automatic retention purge or "Clear History" button in the UI.
- **Remediation**:
  - Defaulted `debug_dump_enabled = False` in `AppConfig` and `pipeline.py`.
  - Added `save_history: bool = True` toggle and `history_retention_days: int = 30` in `AppConfig`.
  - Implemented `purge_retention(retention_days)` in `SessionHistoryStore`: automatically purges expired records on startup.
  - Implemented `clear()` in `SessionHistoryStore` to wipe active and legacy history files.
  - Added `btn_clear_history` with confirmation modal and unified history retrieval in `ghostline/ui/qt_main_window.py`.
- **Tests Added**: `tests/test_history_security.py` (2 tests, all passing).
- **Status**: **VERIFIED-AUTOMATED**.

### 2.7 Local Listeners & IPC (Item 7)
- **Audit Result**: Zero TCP/UDP server sockets. Zero open named pipes. Ghostline operates strictly as an outbound client.
- **Status**: **VERIFIED-AUTOMATED**.

### 2.8 Dependency Audit (Item 8)
- **Audit Tooling**: Run in throwaway virtual environment `.agent/tools/audit_venv/`.
- **Results**:
  - `pip-audit -r requirements.txt`: **0 vulnerabilities found**.
  - `bandit -r ghostline/`: 181 items (177 Low, 4 Medium).
  - Addressed Medium items (urllib URL scheme audits, DOCX XML parsing).
- **Status**: **VERIFIED-AUTOMATED**.

### 2.9 Licensing & Third-Party Notices (Item 9)
- **Findings**:
  - Project license: `LICENSE` (MIT License).
  - Binding: `PyQt6` is licensed under GPLv3 / Commercial. Binary distribution with PyQt6 requires GPL source distribution unless licensed commercially or migrated to `PySide6` (LGPLv3).
  - Created `THIRD_PARTY_NOTICES.md` detailing all dependencies and licenses.
- **Status**: **VERIFIED-AUTOMATED**.

### 2.10 Telemetry & Auto-Update (Item 10)
- **Audit Result**: Zero external telemetry SDKs, zero webhooks, zero auto-update background threads.
- **Documented In**: `SECURITY.md`.
- **Status**: **VERIFIED-AUTOMATED**.

### 2.11 Frozen Build Integrity (Item 11)
- **Audit Result**: Added missing runtime modules (`ghostline.core.profile`, `ghostline.core.history_store`, `ghostline.core.redaction`, `ghostline.core.win_startup`) to `Ghostline.spec:hiddenimports`.
- **Status**: **VERIFIED-AUTOMATED**.

