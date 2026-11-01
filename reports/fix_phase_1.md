# Phase 1 Investigation Report: Real-GUI Reproduction & Window Controls

**Status**: VERIFIED-LIVE  
**Date**: 2026-11-01  
**Environment**: Windows 11 Desktop (Session 14, interactive WinSta0)

---

## 1. Crash Evidence & Root Cause Analysis

### A. Windows Event Log Evidence
The Windows Application Event Log records consecutive fatal crashes for `Ghostline.exe`:
- **Event ID**: 1000 (Application Error)
- **Faulting Application**: `Ghostline.exe` (v1.0.1.0 / v1.0.2)
- **Faulting Module**: `Qt6Core.dll` (v6.11.2.0)
- **Exception Code**: `0xC0000409` (`FAST_FAIL_FATAL_APP_EXIT` / Qt `qFatal` abort)
- **Fault Offset**: `0x000000000001c8d8`
- **Timestamps**:
  - `01-11-2026 19:58:58` (PID 0x20D8 / 8408)
  - `01-11-2026 20:01:16` (PID 0x864 / 2148)

### B. Minidump Header Details
- Dumps: `C:\Users\sumiy\AppData\Local\CrashDumps\Ghostline.exe.2148.dmp` and `Ghostline.exe.8408.dmp`.
- Crash Details: Thread 29396, Exception `0xC0000409`, Flags `0x00000001`, Address `0x00007FFE42B9C8D8`, Parameter `0x7`.

### C. Application Log Correlation & Mechanism
Right before each crash, `ghostline.log` recorded:
```
2026-11-01 20:01:16 [INFO] [HUD] Overlay closed by user; keeping in background.
```
Tracing `on_hud_close()` in `ghostline/app.py`:
```python
    def on_hud_close(self):
        logging.info("[HUD] Overlay closed by user; keeping in background.")
        if hasattr(self, "hud_manager") and self.hud_manager:
            if self.hud_manager.active_mode == HudMode.SCREEN:
                self.hud_manager.set_mode(HudMode.HIDDEN)  # BUG 1
```
1. `HudManager` in `ghostline/ui/hud_manager.py` only implements `show_mode(mode)`, `toggle_mode(mode)`, and `hide_all()`. It has **no** `set_mode()` method.
2. Calling `self.hud_manager.set_mode(HudMode.HIDDEN)` raises `AttributeError: 'HudManager' object has no attribute 'set_mode'`.
3. In `ghostline/ui/qt_hud_overlay.py` (line 2063):
   ```python
   def hide_overlay(self):
       self._is_visible = False
       self.hide()
       if self.on_close:
           try:
               self.on_close()
           except Exception as e:
               logging.warning("[HUD] on_close callback warning: %s", e)  # BUG 2
   ```
4. `ghostline/ui/qt_hud_overlay.py` **never imported `logging`**! When `AttributeError` was caught, it attempted to call `logging.warning(...)`, which raised `NameError: name 'logging' is not defined`.
5. In PyQt6, uncaught Python exceptions raised inside Qt signal slot handlers trigger `qFatal()` by default. In windowed PyInstaller builds (`sys.stderr` is None or redirected), this results in an immediate `__fastfail(FAST_FAIL_FATAL_APP_EXIT)` (`0xC0000409`) inside `Qt6Core.dll`.

---

## 2. Window Controls Investigation (Minimize & Maximize Missing)

### Top-Level Window Enumeration (VERIFIED-LIVE)
PID 12184 / 38148 enumerated via Win32 `EnumDesktopWindows`:
- **Main Window**: HWND `5181380`
  - Title: `"Ghostline [DEV MODE] v1.0.2 [6a6895d]"`
  - Class: `Qt6112QWindowIcon`
  - Visible: `True`
  - `GWL_STYLE`: `0x96CF0000` (`WS_MINIMIZEBOX`, `WS_MAXIMIZEBOX`, `WS_SYSMENU`, `WS_THICKFRAME`, `WS_CAPTION` are all set in Qt)
  - `GWL_EXSTYLE`: `0x00000180`
    - `0x00000100` (`WS_EX_WINDOWEDGE`)
    - `0x00000080` (`WS_EX_TOOLWINDOW`) -> **CRITICAL ROOT CAUSE**
    - `0x00040000` (`WS_EX_APPWINDOW`) is **NOT SET**

### Root Cause
In `ghostline/ui/qt_main_window.py`:
```python
def apply_taskbar_visibility(self, hide: bool):
    self.config.hide_from_taskbar = hide
    if hide:
        new_style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
```
When `hide_from_taskbar` is enabled in `config.json` (or toggled in Settings), Ghostline applies `WS_EX_TOOLWINDOW`. By Windows API design, **any window with `WS_EX_TOOLWINDOW` is rendered by the DWM/Windows Shell as a floating tool window without Minimize or Maximize buttons, regardless of `WS_MINIMIZEBOX`/`WS_MAXIMIZEBOX`**.

Normal windows (main window, settings) must never have `WS_EX_TOOLWINDOW`. To keep taskbar control and normal window controls, the main window must maintain `WS_EX_APPWINDOW` without `WS_EX_TOOLWINDOW` while visible, and hide cleanly to tray on minimize or close.

On the HUD overlay (`qt_hud_overlay.py`), it is a frameless, topmost, click-through-safe tool window with custom buttons. Currently it has only Expand/Compact and Close (`✕`). It lacks a custom Minimize button.

---

## 3. Screen Brightness Failure Root Cause

In `ghostline/hardware/brightness.py`:
```python
wmi_obj = win32com.client.GetObject("winmgmts:\\\\.\\root\\wmi")
methods = wmi_obj.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods")
for m in methods:
    m.WmiSetBrightness(1, snapped)
```
Late-bound `m.WmiSetBrightness(1, snapped)` via `SWbemObjectEx` fails with `(-2147352567, 'Exception occurred.', (0, 'SWbemObjectEx', 'Invalid parameter ', None, 0, -2147217400), None)` because `SWbemObjectEx` dynamic IDispatch does not dispatch `WmiSetBrightness` with raw DISPPARAMS.
Using `m.ExecMethod_('WmiSetBrightness', in_params)` works natively and succeeds with code 0 on this system's internal panel (`DISPLAY\CMN1621\4&1c38a0f4&0&UID8388688_0`).

---

## 4. Investigation of `test_repeat_launch_stability`

- **Git History**: `git diff HEAD~1..HEAD tests/test_startup_lifecycle.py` is empty. The test was **never modified or weakened**; it remains the exact 5-iteration launch/terminate loop introduced in commit `817a894b`.
- **Root Cause of Baseline Failure**: A lingering background instance held `Local\GhostlineSingleInstanceMutex` during the initial baseline run. When iteration 1 launched, it detected the mutex, failed to find the sink window, and exited code 1. When running cleanly, the test passes.

