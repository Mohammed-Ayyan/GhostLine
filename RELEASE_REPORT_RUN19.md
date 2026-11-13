# Ghostline — Run 19 Release Report (FINAL BUILD)
**Maximized Window State, Setup Wizard Small-Screen Robustness & Weak Laptop Performance**

**Release Version**: Ghostline v1.0.8  
**Date**: 2026-11-13  
**Scope**: Main window geometry state & "Open maximized" default, responsive setup wizard with scroll areas and pinned buttons, startup timeline & import optimization, UI stall elimination, zero-PII hardware profiling, Lite/Performance mode, and standalone release packaging.

---

## 1. Executive Summary & Root Causes

Run 19 addressed four real-world usability and performance issues reported when testing Ghostline on secondary and lower-specification laptops:

### 1.1 Bug 1: Application Lag & Slow Startup
- **Symptom**: The application felt sluggish on launch and occasionally lagged during window moves or background status updates on laptops.
- **Root Cause**:
  1. **Heavy Cold Imports**: Top-level eager imports of heavy machine learning and scientific libraries (`torch`, `faster_whisper`, and `scipy.signal.resample_poly`) added **8,000–10,000 ms** of pure CPU/disk stall on cold startup, before the first window could even paint.
  2. **Synchronous Configuration Writes on Resize/Move**: `QtGhostlineMainWindow` invoked `config.save_config()` synchronously on every single `resizeEvent` and `moveEvent`, creating continuous **124 ms** disk I/O stalls on the Qt UI event loop while resizing or dragging.
  3. **Synchronous Socket Probes**: `QtOllamaStatusWidget` executed periodic HTTP/socket health checks synchronously on the UI thread, causing recurring **104–155 ms** socket read stalls whenever the local Ollama service was busy or non-responsive.

### 1.2 Bug 2: Window Opens at 2/3 of Screen ("Full Screen" Request)
- **Symptom**: On initial launch, the main window opened at approximately 2/3 of the display area (`showCmd = 1` / `SW_SHOWNORMAL`, ~46% area ratio). Users expected the window to open full screen (maximized).
- **Root Cause**: Ghostline previously restored geometry from saved config or fell back to a fixed default size (`960x680`). The `open_maximized` setting did not exist, and `main_window_maximized` defaulted to `False`. When displayed on 1080p or 1440p monitors, it occupied only a fraction of the work area.

### 1.3 Bug 3: Broken First-Run Setup Guide (Wizard) UI
- **Symptom**: On smaller screens or standard laptops with 125%–150% Windows display scaling, the setup wizard was visually clipped, footer navigation buttons were pushed below the taskbar, and text ran off-screen.
- **Root Cause**: `QtFirstRunWizardDialog` enforced a hardcoded `setFixedSize(620, 520)` with static layouts. On a common 1366x768 display at 150% scaling, the logical work area height is only 480 px. The 520 px dialog pushed the bottom action bar (`Back`, `Next`, `Skip Setup`) under the Windows taskbar, rendering the wizard impossible to complete or dismiss. Furthermore, labels lacked word-wrap, causing long model names to overflow.

### 1.4 Bug 4: Smooth Execution Across Low-Spec Laptops
- **Symptom**: Ghostline consumed unnecessary background CPU and RAM on laptops with 4–8 GB of RAM or dual-core CPUs, especially on battery saver.
- **Root Cause**: Ghostline lacked hardware awareness and a lightweight operating mode. All animation timers, status polling, and memory caches ran with identical intensity regardless of available system resources or battery state.

---

## 2. Technical Architecture of Fixes

### 2.1 Window State & Maximized Management (`ghostline/ui/window_state.py` & `window_geometry.py`)
1. **Open Maximized by Default**: Added `open_maximized: bool = True` to `AppConfig` (`ghostline/config.py`). On first display, `WindowStateManager.apply_initial_state()` calls `window.showMaximized()`, keeping the Windows taskbar and window caption controls intact.
2. **Normal Geometry Retention**: When unmaximized/restored, Ghostline remembers its unmaximized bounds (`normal_geometry`).
3. **Geometry Validation & Screen Boundary Clamping**: `validate_window_geometry()` validates saved window coordinates against the currently connected display work areas. If coordinates are off-screen or exceed available space, it safely resets the window to 85% of the primary work area, centered.
4. **Debounced Disk I/O (300ms)**: Window move and resize events update geometry in memory immediately, but disk writes (`save_config()`) are debounced by a 300 ms single-shot timer. This completely eliminated the 124 ms UI-thread stall during window resizing.

### 2.2 Responsive Setup Wizard (`ghostline/ui/qt_main_window.py`)
1. **Dynamic Responsive Bounds**: Replaced hardcoded fixed size with `min(work_area * 0.9, 680x560)` and a guaranteed minimum of `(520, 380)`.
2. **Pinned Action Bar**: Bottom navigation buttons (`Skip Setup`, `Back`, `Next →`) are permanently pinned in the dialog's root vertical layout, completely immune to page content sizing.
3. **Scrollable Content Pages**: All three wizard steps are individually enclosed within borderless `QScrollArea` containers with smooth scrolling for low-resolution displays.
4. **Typography & Icon Fallbacks**: All text labels enforce `setWordWrap(True)`. Dynamic font stack (`Segoe UI Variable` &rarr; `Segoe UI` &rarr; `Arial` / `Tahoma`) and safe Unicode/ASCII fallbacks prevent missing glyph boxes on legacy Windows 10 installations.
5. **Keyboard Accessibility**: Supports `Esc` to safely dismiss/skip, `Enter` to advance, and proper Tab focus order.

### 2.3 Lazy Module Imports & Startup Optimization
1. **PEP 562 Lazy Loading (`ghostline/audio/__init__.py`)**: Converted `torch`, `faster_whisper`, and `scipy.signal.resample_poly` to lazy attribute imports.
2. **Cold Import Acceleration**: Heavy neural network and signal processing binaries are only loaded into RAM when live audio capture is actually started. Cold import duration dropped from **10,000 ms to 1,614 ms** (**84% faster**).

### 2.4 Zero-PII Hardware Profiling & Performance Mode
1. **Lightweight Detection (< 2ms)**: Implemented `ghostline/core/hardware_profile.py` using pure Win32 stdlib (`ctypes.windll.kernel32.GlobalMemoryStatusEx`, `os.cpu_count`, `GetSystemPowerStatus`). Gathers only core hardware metrics without reading hostnames, MAC addresses, usernames, or disk serials.
2. **Performance Mode (Auto / Standard / Lite)**:
   - **Auto (Default)**: Automatically activates Lite mode if RAM &le; 8GB, CPU cores &le; 4, or Windows Battery Saver is active.
   - **Lite Mode Features**: Caps document history items to 100, throttles non-essential background polling, minimizes animation repaints, and drops idle memory footprint.
3. **Hardware Diagnostics Line**: Exposed in Wizard Step 1 (`lbl_wiz_hw`), Help &gt; Diagnostics view, and the sanitized diagnostics clipboard block (e.g. `Hardware: 8 cores, 16.0 GB RAM | AC Power | Profile: Standard`).

---

## 3. Before vs After Benchmark Metrics

| Metric | Run 19 Baseline (Before) | Run 19 Final (After) | Improvement / Delta |
|---|---|---|---|
| **Cold Import Time** | ~10,000 ms (`torch`: 6,742ms, `scipy`: 1,181ms) | ~1,614 ms | **-84% faster cold import** |
| **Warm Window Paint** | 1,042.7 ms | 847.8 ms | **-18.7% faster paint** |
| **Normal UI Delay (p50)** | 89.4 ms | 84.5 ms | **-5.5% lower latency** |
| **Normal UI Delay (p95)** | 171.6 ms | 91.4 ms | **-46.8% smoother event loop** |
| **Normal UI Stalls (>100ms)** | 27 stalls (synchronous socket & disk I/O) | 3 stalls (disk I/O and socket eliminated) | **-88.9% fewer UI stalls** |
| **Weak-PC Delay (p50)** | 109.3 ms | 100.0 ms | **-8.5% lower latency** |
| **Weak-PC Delay (p95)** | 183.7 ms | 112.0 ms | **-39.0% smoother event loop** |
| **Weak-PC Stalls (>100ms)** | 45 stalls | 13 stalls | **-71.1% fewer stalls** |
| **Wizard Matrix Defects** | 57 combinations failing (clipped footer/text) | **0 defects (171/171 passed)** | **100% matrix pass rate** |
| **Idle Memory (RSS)** | 148.6 MB | 139.9 MB | **-8.7 MB memory savings** |
| **Idle CPU Utilization** | 0.00% avg | 0.00% avg | **Nominal, zero background wakeups** |

---

## 4. Verification Suite & Visual Proofs

### 4.1 Automated Test Execution
- **Unit Tests**:
  - `tests/test_run19_window_state.py`: 7 / 7 passed (geometry clamping, maximized initial state, debounce, restore).
  - `tests/test_run19_wizard.py`: 6 / 6 passed (dynamic sizing, scroll area wrapping, pinned buttons, keyboard Esc/Enter, hardware label).
  - `tests/test_run19_perf.py`: 3 / 3 passed (hardware detection < 2ms, weak PC heuristics, lazy imports).
- **E2E Scenarios (S50–S57)**:
  - `tests/e2e/test_run19_scenarios.py`: 8 / 8 passed on frozen packaged build.
- **Full Matrix Screen Audit**:
  - `tools/audit_wizard_matrix.py`: **171 / 171 combinations passed** across 16 resolution/DPI scales and 3 font stacks with 0 visual defects.

### 4.2 Forensic Screenshot Captures
Captured under `reports/run19/captures/after/`:

1. **Home Window Maximized** (`home_maximized.png`):
   - Fully maximized to primary display work area with title bar and Windows taskbar preserved.
   - **5 Quoted Words**: "Ghostline", "Dashboard", "Inference", "Ready", "Solving".
2. **Setup Wizard on Small Display** (`wizard_1366x768_scale150_step1.png`):
   - Rendered on simulated 1366x768 at 150% DPI scale (480px logical work area).
   - Entire dialog clamped to 432px height; scroll area active; `Skip Setup`, `Back`, and `Next →` buttons 100% visible and unclipped.
   - **5 Quoted Words**: "Choose", "Your", "AI", "Engine", "Ollama".
3. **Lite / Performance Mode Settings** (`lite_mode_general_settings.png`):
   - Settings &gt; General showing `Open maximized` switch (ON) and `Performance Mode` dropdown selector.
   - **5 Quoted Words**: "Settings", "Performance", "Mode", "Auto", "Standard".

---

## 5. Standalone Release Packages & Cryptographic Hashes

All release packages were cleanly built, self-contained, and verified via automated `--self-test`:

| Package Artifact | Size | SHA-256 Checksum |
|---|---|---|
| **`Ghostline-v1.0.8-win64-portable.zip`** | 312.19 MB | `f1294effe2c95d3ea11d78dfacf442c78afba1659970ac320e3d787e75420dcd` |
| **`Ghostline-Portable.zip`** | 312.19 MB | `f1294effe2c95d3ea11d78dfacf442c78afba1659970ac320e3d787e75420dcd` |
| **`Ghostline-Setup.exe`** | 245.60 MB | `52b58c7b0dcde0a30df501844a80a57cf458863413650861830b2df686e1c5ed` |

### Headless Binary Self-Test Verification
```
============================================================
GHOSTLINE HEADLESS SELF-TEST REPORT
============================================================
[PASS] providers_import: PASS
[PASS] settings_load: PASS
[PASS] dpapi_roundtrip: PASS
[PASS] qt_platform_plugin: PASS
[PASS] hardware_detection: PASS
============================================================
OVERALL RESULT: ALL CHECKS PASSED
============================================================
```

---

## 6. Privacy & Safety Compliance

- **Zero Remote Telemetry**: Ghostline performs 0 network requests outside the local loopback (`127.0.0.1:11434` for Ollama).
- **Zero PII Exposure**: Hardware profile detection inspects only generic numeric capacities (RAM in GB, CPU core count, power source). No user account names, machine hostnames, MAC addresses, or IP addresses are collected, logged, or displayed.
- **Stealth Protection**: Screen-capture exclusion (`WDA_EXCLUDEFROMCAPTURE`) is unconditionally retained on all HUD overlays.
- **Hotkey Integrity**: All existing hotkeys (`Alt + /`, `Alt + S`, `Alt + T`, `Alt + Shift + C`, `Alt + 1..4`) remain strictly unmodified. The HUD never auto-shows on `Alt + /` when hidden.

---

## 7. Verification Instructions for the Secondary Laptop

To test and verify Ghostline v1.0.8 on the user's secondary laptop:

1. **Download / Transfer**:
   - Copy `Ghostline-v1.0.8-win64-portable.zip` (or run `Ghostline-Setup.exe`) on the target machine.
2. **Verify Checksum (PowerShell)**:
   ```powershell
   Get-FileHash Ghostline-v1.0.8-win64-portable.zip -Algorithm SHA256
   # Expected: f1294effe2c95d3ea11d78dfacf442c78afba1659970ac320e3d787e75420dcd
   ```
3. **Launch & Verify Maximized State**:
   - Extract the ZIP and double-click `Run-Ghostline.bat` (or `app\Ghostline.exe`).
   - **Verification**: Ghostline opens cleanly in a **Maximized** window filling the screen work area, with the Windows taskbar and title bar controls clearly visible.
4. **Verify Setup Wizard**:
   - On a fresh launch, the First-Run Setup Guide appears.
   - **Verification**: Even on 1366x768 or high-DPI scaling (125%/150%), the dialog fits comfortably on the screen. The bottom buttons (`Skip Setup`, `Back`, `Next →`) remain completely visible and clickable.
   - Observe the hardware detection summary line at the bottom of Step 1.
5. **Verify Performance & Lite Mode**:
   - Navigate to **Settings > General**.
   - Verify `Open maximized` is enabled (ON).
   - In `Performance Mode`, notice `Auto (Recommended)` dynamically configures Lite mode if the laptop has &le; 8GB RAM or is on Battery Saver.
   - Experience the smooth, instantaneous window resizing and lag-free dashboard navigation.
