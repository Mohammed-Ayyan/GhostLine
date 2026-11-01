# Phase 3 Report: Window Controls (Minimize / Maximize / Close)

**Status**: VERIFIED-AUTOMATED  
**Date**: 2026-11-01  

---

## 1. Normal Windows (Main Window, Settings)

### A. Window Flags and Styles
- Standard window flags are maintained in `ghostline/ui/qt_main_window.py`:
  - `Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint`
  - Win32 Styles verified via `GetWindowLongW`:
    - `WS_MINIMIZEBOX` (`0x00020000`): **True**
    - `WS_MAXIMIZEBOX` (`0x00010000`): **True**
    - `WS_SYSMENU` (`0x00080000`): **True**
    - `WS_THICKFRAME` (`0x00040000`): **True** (freely resizable, minimum size 880x640)

### B. Resolution of Tool Window Issue
- In `apply_taskbar_visibility()`, replaced `(style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW` with `(style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW`.
- Normal windows **never receive `WS_EX_TOOLWINDOW`**, preventing the Windows Desktop Window Manager (DWM) from stripping Minimize and Maximize buttons.
- When `hide_from_taskbar` or `minimize_to_tray` is enabled, the window is hidden from the taskbar on minimize or close by hiding to the system tray (`self.hide()`), keeping full window controls while visible.

### C. Geometry Persistence
- Added configuration fields in `ghostline/config.py`:
  - `main_window_width` (default 960)
  - `main_window_height` (default 680)
  - `main_window_pos_x` (optional int)
  - `main_window_pos_y` (optional int)
  - `main_window_maximized` (boolean)
- Implemented `_save_geometry_to_config()` hooked to `resizeEvent`, `moveEvent`, and `closeEvent` for atomic persistence. Restored on `QtGhostlineMainWindow.__init__`.

---

## 2. Floating HUD Overlay Controls

The HUD overlay preserves its specialized frameless, topmost, click-through focus-free (`WS_EX_NOACTIVATE`) and capture-exclusion (`WDA_EXCLUDEFROMCAPTURE`) flags. Its custom island toolbar now features:
- **Minimize (`btn_minimize_hud`, "🗕")**: Hides the HUD overlay to the background (equivalent to HUD toggle hotkey `Alt + T`).
- **Maximize / Expand (`btn_expand_toggle`, "🗖")**: Toggles between compact view and expanded card view.
- **Close (`btn_close_hud`, "✕")**: Hides HUD overlay while keeping Ghostline active.
- **Quit (`btn_quit_hud`, "⏻")**: Visible quit button in the toolbar calling `on_exit` to terminate Ghostline.

---

## 3. Automated Verification
- Added `tests/test_window_controls.py`.
- Verified style bits, `apply_taskbar_visibility`, geometry persistence, and HUD custom controls.
- Result: `Ran 3 tests in 1.847s. OK.`

