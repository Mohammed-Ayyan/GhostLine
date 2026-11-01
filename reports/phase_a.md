# Phase A — Safety Snapshot and Read-Only Inspection Report

**Date & Time**: 2026-11-01 18:41:30  
**Branch**: `feature/hardware-controls-and-release`  
**Backup Directory**: `C:\Users\sumiy\OneDrive\Desktop\web development\ghostline_backups\20261101_183856`  
- Working tree patch: `backup.patch` (from `git diff`)
- Untracked files copy: `untracked/`
- User AppData backup: `appdata_ghostline/` (`%APPDATA%\Ghostline\`)

---

## 1. Architectural Inspection

### A. Overlay / HUD Architecture
- **Framework**: PyQt6 (`QWidget`)
- **Key File**: `ghostline/ui/qt_hud_overlay.py` (`QtGhostlineHudOverlay`)
- **Window Flags**: `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool`
- **Win32 Extended Styles**: `GWL_EXSTYLE` with `WS_EX_NOACTIVATE | WS_EX_TOPMOST` (applied via `ctypes.windll.user32.SetWindowLongW`)
- **Screen Capture Exclusion**: Handled via `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` in `ghostline/core/capture_exclusion.py`
- **Focus Behavior**: Focus-free via `WS_EX_NOACTIVATE` so foreground active applications (browsers, IDEs, exam portals) never lose focus.
- **Layout & Styling**: Multi-island frame layout (`island_toolbar`, `island_context`, `island_answer` with `cards_layout` inside a `QScrollArea`). Dark modern theme (`rgba(18, 21, 28, 0.86)` background, `#334155` border, `#38bdf8` accent).

### B. Settings Persistence
- **File Path**: `get_config_path()` in `ghostline/config.py` (points to `%APPDATA%\Ghostline\config.json` or project-local `config.json`).
- **Format & Schema**: JSON validated through Pydantic `AppConfig(BaseModel)`.
- **MSIX / Virtualization Support**: Synchronized via `_sync_msix_appdata()` using cmd.exe type.
- **Atomic Writes**: Currently direct `open(..., "w")`. Needs atomic tempfile + `os.replace` write semantics.

### C. Credential Storage
- **Implementation**: `ghostline/core/credentials.py`
- **DPAPI Usage**: Native Windows `ctypes.windll.crypt32.CryptProtectData` and `CryptUnprotectData` with description `"GhostlineCredentials"` and `CRYPTPROTECT_UI_FORBIDDEN = 0x1`.
- **Storage Location**: `%APPDATA%\Ghostline\credentials.bin` (binary DPAPI ciphertext).
- **Security & Redaction**: Plaintext keys are never saved in `config.json` or logged. UI masking provides `sk-••••••••abcd` via `mask_api_key`.

### D. Existing Keyboard Lighting & Lock State Handling
- **Existing Code**: `ghostline/ui/caps_indicator.py` (`CapsLockIndicator`)
- **Mechanism**: `SendInput` / `GetKeyState` for Caps Lock.
- **Missing / Incomplete**:
  - No generalized hardware abstraction interface for Num Lock and Scroll Lock.
  - No detection for Windows Dynamic Lighting / LampArray (`Windows.Devices.Lights.LampArray`).
  - No hardware controls (flash count, speed, on/off) inside the HUD overlay.

### E. Screen Brightness
- **Existing Code**: None.
- **Needs Implementation**: Hardware detection for internal panels via WMI (`root\wmi` `WmiMonitorBrightness` / `WmiMonitorBrightnessMethods`) and external displays via Windows Physical Monitor / DDC/CI API (`GetPhysicalMonitorsFromHMONITOR`, `GetMonitorBrightness`, `SetMonitorBrightness`).

### F. AI Provider Layer
- **Package**: `ghostline/core/providers/`
- **Supported Providers**: Ollama (`ollama`), Google Gemini (`gemini`), Groq (`groq`), OpenRouter (`openrouter`), OpenAI (`openai`), Anthropic Claude (`anthropic`), xAI Grok (`xai`).
- **Router**: `AIRouter` in `ghostline/core/providers/router.py`.
- **Input Modality**:
  - MCQ solving captures screen -> runs Windows Native OCR -> parses text and structure -> sends structured text prompt to `AIRouter.solve_question(...)`.
  - Audio assistant captures loopback/mic audio -> transcribes via local `faster-whisper` -> sends text prompt to `AIRouter.generate(...)`.
- **Audit Findings**:
  - Gemini REST endpoint in `gemini_provider.py` currently uses query parameter `?key=...`. Must be updated to send the `x-goog-api-key` header to prevent leaking keys into URLs/logs.
  - Vision capability verification needed to ensure text-only models reject raw image payloads gracefully.
  - Need `scripts/live_provider_check.py` for safe user-gated credential verification.

### G. Build / Release Pipeline
- **Spec**: `Ghostline.spec` configured for PyInstaller.
- **Automation**: `build_release.py` compiles PyInstaller dist, portable zip, and self-contained GUI installer `Ghostline-Setup.exe`.
- **Inno Setup**: `installer.iss` present; ISCC.exe is not installed on this machine, so `build_release.py` produces the self-contained PyInstaller GUI installer.
- **Self-Test CLI Flag**: App lacks `--self-test` headless diagnostic verification flag.

---

## 2. Implementation Status Matrix

| Component | Status | File Reference | Action Required |
| :--- | :--- | :--- | :--- |
| **HUD Overlay Framework** | ALREADY IMPLEMENTED | `ghostline/ui/qt_hud_overlay.py` | None |
| **HUD Capture Exclusion & No-Activate** | ALREADY IMPLEMENTED | `ghostline/core/capture_exclusion.py` | None |
| **Hardware Overlay Controls Panel** | INCOMPLETE | `ghostline/ui/qt_hud_overlay.py` | Add collapsible hardware controls section |
| **Config Atomic Writes** | INCOMPLETE | `ghostline/config.py` | Implement tempfile + `os.replace` |
| **DPAPI Credential Storage** | ALREADY IMPLEMENTED | `ghostline/core/credentials.py` | None |
| **Caps Lock Pulse Indicator** | ALREADY IMPLEMENTED | `ghostline/ui/caps_indicator.py` | Keep intact |
| **Hardware Abstraction (LED / LampArray)** | INCOMPLETE | New: `ghostline/hardware/lighting.py` | Implement interface & backends |
| **Screen Brightness Engine** | INCOMPLETE | New: `ghostline/hardware/brightness.py` | Implement WMI & DDC/CI backends |
| **Gemini Header Auth Fix** | NEEDS CHANGE | `ghostline/core/providers/gemini_provider.py` | Switch from `?key=` URL to `x-goog-api-key` header |
| **BYOK Live Verification Script** | INCOMPLETE | New: `scripts/live_provider_check.py` | Implement environment-driven tester |
| **App Headless `--self-test` Flag** | INCOMPLETE | `ghostline/app.py` | Add diagnostic self-test CLI entry |
| **PyInstaller Spec & Release Script** | ALREADY IMPLEMENTED | `Ghostline.spec`, `build_release.py` | Update with new hardware modules |

