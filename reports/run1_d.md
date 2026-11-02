# Run 1 — Part D Report: System Tray & Windows Startup Configuration

**Date**: 2026-11-02  
**Status**: VERIFIED-AUTOMATED & VERIFIED-VISUAL  
**Branch**: `feature/hardware-controls-and-release`  

---

## 1. Executive Summary

Part D implements system tray management, per-user Windows startup registration via standard registry APIs, deep linking to Windows 11 notification area settings, and an unreachable-state guard preventing Ghostline from becoming an invisible orphan process.

---

## 2. Windows Startup Registry Management

### Module: `ghostline/core/win_startup.py`
- **Registry Key**: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
- **Value Name**: `Ghostline`
- **API Implementation**: Pure Python standard library `winreg` (no external binaries or elevated UAC prompts):
  - `set_start_with_windows(enable: bool, exe_path: Optional[str] = None)`
    - Quotes path correctly and appends `--minimized` when `start_minimized` is active.
    - Writes `REG_SZ` on enable.
    - Deletes value safely on disable (`winreg.DeleteValue`).
  - `get_start_with_windows() -> bool`:
    - Queries key and returns True if registered, False if missing or inaccessible.

---

## 3. Deep Linking: `ms-settings:taskbar`

Windows 11 automatically places new system tray icons into the overflow drawer (`^`). To prevent user confusion:
- Implemented `open_taskbar_settings()` using `os.startfile("ms-settings:taskbar")`.
- Directly opens the Windows Settings page at **Personalization > Taskbar > Other system tray icons**.
- Bound to `btn_open_taskbar_settings` in Settings (`_build_general_view`).

---

## 4. UI Controls in Settings View

Added a dedicated "System Tray & Windows Startup" section to `ghostline/ui/qt_main_window.py`:
1. `switch_show_tray`: Toggles system tray icon visibility (`show_tray_icon`).
2. `combo_close_action`: ComboBox with options:
   - "Minimize to system tray" (sets `minimize_to_tray = True`)
   - "Quit application" (sets `minimize_to_tray = False`)
3. `switch_start_minimized`: Launches quietly in background (`start_minimized`).
4. `switch_start_with_windows`: Registers HKCU Run key (`start_with_windows`).
5. `switch_tray_notifications`: Native Windows balloon alerts (`tray_notifications`).
6. `btn_open_taskbar_settings`: One-click button to open Windows 11 taskbar settings.

### Unreachable State Guard
If the user attempts to disable the tray icon (`show_tray_icon = False`) while `minimize_to_tray` is enabled, the UI automatically updates `minimize_to_tray` to False and notifies the user via `FluentInfoBar`. This guarantees the window close action will cleanly exit rather than hiding into an invisible tray with no user recourse.

---

## 5. Verification & Test Results

### 1. Pytest Unit Tests (`tests/test_tray_and_startup.py`)
- `test_old_config_loads_with_tray_and_startup_defaults`: PASSED (Backward compatibility verified).
- `test_win_startup_registry_roundtrip`: PASSED (HKCU Run registration and clean removal verified).

### 2. Layout & Render Verification
- No horizontal scrollbars or overflow at 900x640, 1100x720, or 1400x900.
- Labels inside `card_tray` wrap properly and respect viewport bounds.

---

## 6. Verification Status

- **Automated Verification**: `VERIFIED-AUTOMATED`
  - HKCU registry read/write/delete roundtrip verified.
  - Backward compatibility with legacy configuration files verified.
- **Visual Verification**: `VERIFIED-VISUAL`
  - Settings view renders all 6 tray/startup controls cleanly with Fluent styling.
- **Real OS Integration**: `NEEDS-USER-CHECK` (Windows 11 taskbar overflow pin state).

