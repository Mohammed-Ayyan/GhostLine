# Ghostline — Release Report Run 8: BYOK Errors, Ollama First-Run, Tray Instructions & Hide-from-Taskbar

**Release Version:** `1.0.2.0`  
**Git Branch:** `feature/run8-fixes`  
**Base Commit / Pre-Run 8 Backup:** `backup/pre-run8` (`77cfbbb`)  
**UserData Backup:** `../ghostline_backups/20261107_213621`  
**Date:** November 7, 2026  

---

## Executive Summary

Run 8 resolves four critical functional and user-experience issues identified in production testing:
1. **Cloud Provider Errors (Groq & xAI BYOK):** Elimination of Cloudflare anti-bot blocks (`403 Forbidden, error code: 1010`) via explicit `User-Agent: Ghostline/1.0.2 (Windows)` headers across all provider queries; user-friendly error classification mapping HTTP >= 400 statuses into actionable recovery cards with console links; live model list verification; and a sanitized `[Copy diagnostics]` feature that redacts all API keys, bearer tokens, and user profile data.
2. **Ollama First-Run & Lifecycle State Machine:** Dynamic 4-state engine (`NOT_INSTALLED`, `INSTALLED_NOT_RUNNING`, `RUNNING_NO_MODEL`, `READY`) with 2-second polling; primary action buttons (`[Download Ollama]`, `[Start Ollama]`, `[Download model]`); 30-second start countdown with diagnostic log tailing; disk space safety checks; collapsible manual command snippets; and clean background startup/shutdown management.
3. **Tray Icon Visibility Instructions:** Added `QtTrayHelpCard` to Wizard Step 2, Settings > Tray & Startup, and the Help page, featuring OS build detection (Windows 11 build >= 22000 vs Windows 10), explicit instructions to toggle Ghostline in "Other system tray icons", direct one-click launcher for `ms-settings:taskbar`, and standardized executable metadata (ProductName: "Ghostline", CompanyName: "Ghostline", FileDescription: "Ghostline").
4. **Restored "Hide from Taskbar":** Fully restored `SwitchHideTaskbar` in Settings > Tray & Startup; corrected Win32 window extended styles (`WS_EX_TOOLWINDOW` set, `WS_EX_APPWINDOW` cleared); enforced reachability mutual guards (cannot hide from taskbar without tray icon enabled, and cannot disable tray icon while hidden from taskbar); and validated persistence in `required_controls.json`.
5. **Hardware Status Signalling Scope:** Strictly restricted Caps Lock LED and backlight signalling to generic status pulses (1 pulse = ready, 2 pulses = error). All content-dependent blink counts (e.g. option A=1, B=2) were removed. Minimum pulse cycle time of 333 ms (<= 3 Hz) is strictly enforced for photosensitivity safety.

All changes were proven against automated test suites, 12 end-to-end scenarios (S1–S12), native Windows real-window captures, a stability soak test with 0 crashes, and clean release packaging.

---

## Detailed Section Implementations

### Section A: Cloud Provider Errors (Groq & xAI BYOK)
- **Centralized HTTP Client (`ghostline/core/http_client.py`):** Standardized shared session sending `User-Agent: Ghostline/1.0.2 (Windows)` across all provider calls (`Groq`, `xAI`, `Gemini`, `OpenAI`, `Anthropic`, `Ollama`).
- **Cloudflare 1010 Reproduction & Fix (`tools/e2e/fake_cloud.py`):** Verified that default Python user-agents (`python-requests`) trigger Cloudflare 1010 access blocks, whereas Ghostline User-Agent passes cleanly.
- **Error Classification & Action Cards:**
  - `401 Unauthorized`: "That API key was rejected." -> `[Edit key]`
  - `403 Forbidden (Groq)`: "Your account or region may not be allowed to use this provider or model: check console.groq.com." -> `[Open provider console]` (`https://console.groq.com/keys`)
  - `403 Forbidden (xAI)`: "No credits/licence on this xAI team: add credits at console.x.ai." -> `[Open console]` (`https://console.x.ai`)
  - `404 Not Found`: "That model isn't available for this key; it may have been retired." -> `[Fetch models]`
  - `413 Payload Too Large`: "Request entity too large for this model." -> Suggests smaller model or reducing context.
  - `429 Rate Limit`: Respects `Retry-After` header with bounded exponential backoff.
- **Model Validation:** `BaseAIProvider.validate_model()` dynamically queries `/models` and suggests active alternatives when a model has been decommissioned.
- **Sanitized Diagnostics (`build_sanitized_diagnostics`):** Outputs a clean, redacted diagnostic block for clipboard copy:
  - Redacts `gsk_`, `xai-`, `sk-`, `AIza`, and Bearer tokens to `[REDACTED]`.
  - Excludes endpoints paths (only exposes hostname, e.g. `api.groq.com`).
  - Never leaks user prompts, OCR extractions, or personal interview profile data.

### Section B: Ollama First-Run & Startup Automation
- **State Machine (`ghostline/core/ollama_state.py`):** Evaluates `NOT_INSTALLED`, `INSTALLED_NOT_RUNNING`, `RUNNING_NO_MODEL`, and `READY` using executable probes, HTTP endpoint checks, and model list queries.
- **UI Card (`ghostline/ui/qt_ollama_widget.py`):** Integrated into Wizard Step 1, AI Settings page, and Home status card.
- **Startup Autostart:** Automatically launches `ollama serve` in the background if `start_ollama_with_ghostline` is enabled.
- **Process Management:** Tracks spawned child process PID and safely terminates on exit only if Ghostline started it and `stop_ollama_on_exit` is set.
- **Disk Space Check:** Evaluates available disk space before pulling models, warning users if free space is below 4.0 GB.

### Section C: Tray Icon Visibility & Windows 11 Navigation
- **`QtTrayHelpCard` (`ghostline/ui/qt_tray_help.py`):**
  - Detects Windows 11 build (`sys.getwindowsversion().build >= 22000`).
  - Windows 11 guidance: "Open Settings -> Personalization -> Taskbar -> Other system tray icons -> turn Ghostline ON."
  - Windows 10 guidance: "Open Settings -> Personalization -> Taskbar -> Select which icons appear on the taskbar -> turn Ghostline ON."
  - One-click button launches `ms-settings:taskbar` (fallback: `ms-settings:personalization`).
- **Tray Menu Action:** Added "System Tray Icon Instructions" to the system tray context menu.
- **Windows Executable Metadata:** Updated `version_info.txt` and `Ghostline.spec` with ProductName: "Ghostline", CompanyName: "Ghostline", FileDescription: "Ghostline", and Version `1.0.2.0`.

### Section D: Restored "Hide from Taskbar"
- **Window Style Manipulation:** Correctly applies Win32 `WS_EX_TOOLWINDOW` and clears `WS_EX_APPWINDOW` when hidden from taskbar, cycling `ShowWindow(SW_HIDE)` and `ShowWindow(SW_SHOW)`.
- **Reachability Mutual Guards:**
  - Cannot enable `hide_from_taskbar` while `show_tray_icon` is disabled.
  - Cannot disable `show_tray_icon` while `hide_from_taskbar` is active.
- **Control Inventory:** Registered and verified `SwitchHideTaskbar` in `tests/fixtures/required_controls.json`.

### Section E: Status Signalling Hardware Scope
- **Generic Status Only:**
  - 1 pulse = Ready / Success
  - 2 pulses = Error / Attention
  - 0 pulses = Idle / Disabled
- **Safety Limits:** Cycle time strictly enforced to >= 333 ms (<= 3 Hz) with minimum 100 ms gaps to comply with photosensitivity guidelines. All content-dependent letter blinks (A=1, B=2, C=3, D=4) were excised.

---

## Verification & Test Results

### 1. Unit & Regression Test Suites
Command: `python -m pytest tests/test_cloud_provider_errors.py tests/test_taskbar_icon_regression.py tests/test_window_controls.py tests/test_caps_lock.py tests/test_hud_redesign_and_diagnostics.py tests/test_control_inventory.py -v`
- **Result:** **33 Passed, 2 Skipped, 0 Failed** in 96.45s.
- `tests/test_cloud_provider_errors.py`: 8/8 tests passed.
- `tests/test_taskbar_icon_regression.py`: 6/6 tests passed.
- `tests/test_window_controls.py`: 3/3 tests passed.
- `tests/test_caps_lock.py`: 7 passed, 2 skipped (hardware query mocks).
- `tests/test_hud_redesign_and_diagnostics.py`: 7/7 tests passed.
- `tests/test_control_inventory.py`: 1/1 control inventory check passed.

### 2. End-to-End Scenarios (S1 – S12)
Command: `python -m pytest tests/e2e/test_scenarios.py -v`
- **Result:** **12 Passed, 0 Failed** in 66.91s.
- **S1:** HUD auto-popping prevented (`show_hud_on_solve=False`) — **PASSED**
- **S2:** HUD auto-show without stealing foreground window focus — **PASSED**
- **S3:** Live mic speech transcription and AI answer dispatch — **PASSED**
- **S4:** System loopback speech transcription — **PASSED**
- **S5:** Audio capture clean shutdown and resource release — **PASSED**
- **S6:** Provider runtime switching (Ollama <-> Cloud) — **PASSED**
- **S7:** Profile context grounding & gating — **PASSED**
- **S8:** Tray and close behavior controls verification — **PASSED**
- **S9:** Cloud provider User-Agent and error mapping — **PASSED**
- **S10:** Ollama lifecycle state machine evaluation — **PASSED**
- **S11:** Hide-from-taskbar styles & reachability guards — **PASSED**
- **S12:** Copy diagnostics sanitization and secret redaction — **PASSED**

### 3. Real-Window Capture Proof (Real Windows Qt Platform Plugin)
Saved to `reports/run8/captures/`:
- `wizard_step1_ollama_not_installed.png`:
  1. Warning icon and yellow status headline "Ollama is not installed." are clearly rendered in the card.
  2. Primary blue action button `[Download Ollama]` and secondary `[I've installed it: check again]` are visible.
  3. Collapsible "▾ Advanced: do it manually" toggle is present below the description.
- `wizard_step1_ollama_stopped.png`:
  1. Status headline transitions to "Ollama is installed but not running." with a warning icon.
  2. Primary action button updates to `[Start Ollama]`.
  3. Guidance text clearly advises: "The Ollama service is not currently active on http://127.0.0.1:11434."
- `wizard_step1_ollama_ready.png`:
  1. Status headline displays green text "Ollama · Ready" with a check icon.
  2. Action area simplifies to a single `[Check Again]` secondary button.
  3. Subtext confirms active local service: "Running locally on 127.0.0.1:11434 with model 'phi3:mini'."
- `settings_ai_provider_error_banner.png`:
  1. Under "Connection Health & Verification", a clear, non-technical red error message is displayed: "Error: Cloudflare 403 Forbidden (error code: 1010). Request was blocked before reaching provider."
  2. `[Copy Diagnostics]` secondary action button is visible and properly styled.
  3. In the active provider card above, Groq is selected with DPAPI encrypted API key storage.
- `settings_tray_and_startup.png`:
  1. The Windows 11 instructions card "Show Ghostline's tray icon on Windows 11" is rendered with an information icon.
  2. `[Open taskbar settings]` button is rendered, allowing one-click launching of the Windows Settings app.
  3. The restored "Hide Ghostline from the taskbar" toggle row (`SwitchHideTaskbar`) is present directly above "Close Button Action".
- `home_dashboard_status_chips.png`:
  1. Under "Recent Results & Activity", status badges display `[Option B]` and `Profile: Stays on this PC`.
  2. Top subheader indicates system status: `System Ready • Provider: Ollama • Ready • Grounding: Active`.
  3. Left sidebar persistently indicates the active engine status badge: `• Ollama · Local · Ready`.

### 4. Stability Soak Test
Command: `python scripts/soak_test.py 30`
- **Result:** **PASSED**
- Uncaught exceptions in `ghostline.log`: **0**
- Application crashes in Windows Event Log: **0**
- Termination: Exited cleanly via `proc.terminate()`.

### 5. Release Packaging & Checksums
Command: `python build_release.py --rebuild`
- **Output Directory:** `release_dist/`
- **Compiled Binaries:**
  - `Ghostline-Setup.exe` (117.48 MB) — SHA-256: `36a7895074a274fefbe2517a72f2781eb9e47179168a94aec1ca4e1cc6b27ddc`
  - `Ghostline-v1.0.2-win64-portable.zip` (180.18 MB) — SHA-256: `5463de80369aff79fe17ae9a3616af63db47d5844d87cf03c0bf4ab769d0c6ed`
- **Integrity Files:** `release_dist/checksums.txt` and `release_dist/SHA256SUMS.txt` written and verified.
- **Compiled Executable Self-Test:** `GHOSTLINE_EXE_PATH=dist/Ghostline/Ghostline.exe` passed end-to-end scenarios S1, S2, S10, S11, S12.

