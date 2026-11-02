# Phase 2 Report: Crash Fix and Hardening

**Status**: VERIFIED-AUTOMATED  
**Date**: 2026-11-01  

---

## 1. Crash Fix Implementation

### A. Missing `set_mode()` in `HudManager`
- Added `set_mode(self, mode: HudMode)` in `ghostline/ui/hud_manager.py`. It correctly transitions to the requested `HudMode` or executes `hide_all()` when passed `HudMode.HIDDEN`.
- Prevents `AttributeError: 'HudManager' object has no attribute 'set_mode'` previously triggered in `on_hud_close()`, `on_audio_panel_close()`, and `on_history_panel_close()`.

### B. Missing `logging` Import in `QtGhostlineHudOverlay`
- Added `import logging` to `ghostline/ui/qt_hud_overlay.py`.
- Prevents `NameError: name 'logging' is not defined` inside `hide_overlay()`, which previously caused PyQt6 to abort via `qFatal` (`0xC0000409` in `Qt6Core.dll`).

### C. WMI Parameter Dispatch in `WindowsBrightnessBackend`
- Replaced late-bound `m.WmiSetBrightness(1, snapped)` with direct `m.ExecMethod_('WmiSetBrightness', in_params)` in `ghostline/hardware/brightness.py`.
- Prevents `SWbemObjectEx: Invalid parameter (-2147217400)`.

---

## 2. Crash Instrumentation & Hardening

1. **Faulthandler**:
   - `faulthandler.enable(file=open(get_app_dir() / 'crash_fault.log', 'a'))` enabled on startup. Writes low-level C/C++ fault dumps directly to disk.
2. **Global Exception Hooks**:
   - `sys.excepthook` installed: records uncaught Python exceptions with full tracebacks to `ghostline.log` via `logging.critical`.
   - `threading.excepthook` installed: records thread worker exceptions with thread name and tracebacks.
3. **Qt Message Handler**:
   - `qInstallMessageHandler(_qt_message_handler)` intercepts Qt internal messages (`QtFatalMsg`, `QtCriticalMsg`, `QtWarningMsg`) and routes them through Python `logging`.
4. **Guarded Stdout/Stderr**:
   - Added `_SafeNullWriter` fallback in `setup_file_logging()` so windowed PyInstaller builds (`stdout`/`stderr` is None) never crash on unguarded `sys.stdout.write`.
5. **Log Rotation**:
   - Converted standard `FileHandler` to `RotatingFileHandler` with 5MB max size and 3 backups in `AppData\Roaming\Ghostline\ghostline.log`.

---

## 3. Automated Regression Verification
- Added `tests/test_crash_hardening.py` covering:
  - `HudManager.set_mode` transition and hiding.
  - `QtGhostlineHudOverlay.hide_overlay` exception tolerance without `NameError`.
  - Crash handler registration (`faulthandler`, `sys.excepthook`, `threading.excepthook`).
- Execution: `Ran 3 tests in 0.786s. OK.`

