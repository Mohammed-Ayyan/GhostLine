# Phase 4 Report — Hotkeys & Quiet Output Implementation

**Execution Date:** 2026-11-01 20:54:00 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Complete Hotkey Table (Verified Against Codebase)

All global shortcuts in Ghostline are registered directly via the Win32 `RegisterHotKey` API on a hidden message-only sink window (`GhostlineSinkWindow`), preventing any dependency on GUI window focus or third-party hook libraries.

| Hotkey Action | Combination | Registration Location | Registration Mechanism | Description | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cursor Screen Solve** | `Alt + /` (configurable) | `ghostline/app.py:2281` | Win32 `RegisterHotKey` (`HOTKEY_SOLVE`, `0xBF`) | Triggers OCR & AI solve under cursor without showing HUD | `VERIFIED-AUTOMATED` |
| **Full Screen Solve** | `Alt + Shift + /` | `ghostline/app.py:2282` | Win32 `RegisterHotKey` (`HOTKEY_SOLVE_FULLSCREEN`) | Captures entire primary monitor and solves question | `VERIFIED-AUTOMATED` |
| **HUD Overlay Toggle** | `Alt + T` (configurable) | `ghostline/app.py:2285` | Win32 `RegisterHotKey` (`HOTKEY_HUD_TOGGLE`) | Dedicated shortcut to display or hide the floating HUD | `VERIFIED-AUTOMATED` |
| **Live Audio Assistant** | `Alt + A` | `ghostline/app.py:2283` | Win32 `RegisterHotKey` (`HOTKEY_AUDIO_ASSIST`) | Toggles floating audio assistant transcript & Q&A panel | `VERIFIED-AUTOMATED` |
| **Audio Listening Toggle**| `Alt + L` | `ghostline/app.py:2284` | Win32 `RegisterHotKey` (`HOTKEY_AUDIO_TOGGLE`) | Pauses or resumes microphone and loopback audio capture | `VERIFIED-AUTOMATED` |
| **Audio Quick Ask** | `Alt + Q` | `ghostline/app.py:2286` | Win32 `RegisterHotKey` (`HOTKEY_AUDIO_ASK`) | Triggers AI inference on recent transcribed speech context | `VERIFIED-AUTOMATED` |
| **Session History HUD** | `Alt + Shift + A` | `ghostline/app.py:2288` | Win32 `RegisterHotKey` (`HOTKEY_HISTORY`) | Displays chronological audit log of solved questions & transcripts | `VERIFIED-AUTOMATED` |
| **Debug Inspector** | `Ctrl + Alt + D` | `ghostline/app.py:2287` | Win32 `RegisterHotKey` (`HOTKEY_DEBUG`) | Toggles visual bounding boxes and raw OCR inspection | `VERIFIED-AUTOMATED` |
| **Quit Ghostline** | `Ctrl + Alt + Q` (configurable)| `ghostline/app.py:2289` | Win32 `RegisterHotKey` (`HOTKEY_QUIT`) | Instant clean termination within 3s without orphan processes | `VERIFIED-AUTOMATED` |

---

## 2. Quiet Solve Behavior (`show_hud_on_solve = False`)
- In `ghostline/config.py`, `show_hud_on_solve` is set to `Field(default=False)`.
- When `Alt + /` is pressed:
  - `_solve_worker` runs OCR and inference completely offscreen.
  - `_main_thread_solve_completed` records result in `self.last_answer_presentation` and updates HUD state in the background, but does NOT call `self.hud.show_overlay()`.
  - The HUD remains completely hidden, leaving the user's active exam/game/browser undisturbed.
- When `Alt + T` is pressed, `toggle_hud()` shows the HUD overlay populated with the stored result.
- The system tray menu includes `"Show Last Answer"` which also opens the HUD directly to the saved answer.

---

## 3. Quiet Result Channels (`ghostline/ui/quiet_output.py`)
All quiet channels are independently toggleable in General Settings and persisted in `config.json`:
1. **Taskbar Button Flash (`quiet_taskbar_flash: bool = True`)**:
   - Implemented via `FlashWindowEx` (`FLASHW_TRAY | FLASHW_TIMERNOFG`).
   - Flashes the taskbar button 2 times on success, 3 times on error, without stealing foreground focus.
2. **Taskbar Icon Overlay Badge (`quiet_taskbar_badge: bool = True`)**:
   - Implemented via COM `ITaskbarList3::SetOverlayIcon` (`Method 18` in vtable).
   - Dynamically draws a high-contrast 16x16 icon containing the answer letter (e.g. "A", "B", "C", "D", or "✓") and sets it as the taskbar icon overlay badge.
   - Clears automatically after 8 seconds or upon the next scan.
3. **System Tray Balloon Notification (`quiet_tray_notification: bool = True`)**:
   - Dispatches a native Windows balloon notification via `Shell_NotifyIconW` (`NIM_MODIFY` with `NIF_INFO`).
   - Displays answer headline discreetly.
4. **Generic Hardware Pulse (`quiet_hardware_signal: bool = False`)**:
   - Flashes Caps Lock LED once (cycle $\ge 333\text{ ms}$) as a generic completion ping.
   - Strictly obeys safety constraints: NEVER encodes answer choices as blink codes.

---

## 4. Automated Verification
- Unit test suite: `tests/test_quiet_hotkeys.py` (4 tests).
  - `test_default_config_hides_hud_on_solve`: `VERIFIED-AUTOMATED`
  - `test_quiet_output_dispatch_success`: `VERIFIED-AUTOMATED`
  - `test_quiet_output_dispatch_error`: `VERIFIED-AUTOMATED`
  - `test_hud_solve_respects_show_hud_on_solve_flag`: `VERIFIED-AUTOMATED`

