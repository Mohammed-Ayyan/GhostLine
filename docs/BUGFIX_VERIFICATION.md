# Ghostline Critical Bug-Fix Verification & Defect Log

This document tracks all critical defects diagnosed, fixed, and verified across application crashes, custom shortcuts, taskbar behavior, custom icon selection, HUD chat pipeline, HUD layout usability, and secondary UI controls.

---

## Defect Matrix

| ID | Defect Summary | Severity | Status | Automated Test |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-01** | Application crash on worker threads touching Qt widgets and unhandled shutdown | Critical | VERIFIED | `test_qt_ui_hotkey_regression.py`, `test_secondary_controls_regression.py` |
| **DEF-02** | Custom keyboard shortcuts not persisted or re-registered at runtime | Critical | VERIFIED | `test_custom_shortcuts_regression.py` |
| **DEF-03** | "Hide from taskbar" toggle controls wrong config and fails to apply window flags | High | VERIFIED | `test_taskbar_icon_regression.py` |
| **DEF-04** | Custom icon selection dropdown is non-functional mock without file picker or persistence | High | VERIFIED | `test_taskbar_icon_regression.py` |
| **DEF-05** | HUD Chat fails: worker thread calls GUI methods, lacks context, and drops query text | Critical | VERIFIED | `test_hud_chat_end_to_end.py` |
| **DEF-06** | Floating HUD is too compact (default 380x300 clamped to 480x340), squishing toolbar and scroll area | High | VERIFIED | `test_hud_layout_usability.py` |
| **DEF-07** | Broken/disconnected secondary controls & non-thread-safe tray callbacks | High | VERIFIED | `test_secondary_controls_regression.py` |
| **DEF-08** | Live-call audio capture & transcription stalls: mic muting bleed decay and pause flush | Critical | VERIFIED | `test_live_call_pipeline_regression.py` |
| **DEF-09** | HUD control buttons unresponsive & cross-panel signal handling errors | Critical | VERIFIED | `test_hud_controls_and_transparency_regression.py` |
| **DEF-10** | MCQ HUD End button disconnected and lacks session teardown | Critical | VERIFIED | `test_hud_controls_and_transparency_regression.py` |
| **DEF-11** | Windows taskbar icon fails to update due to missing AppUserModelID & WM_SETICON | High | VERIFIED | `test_taskbar_icon_regression.py` |
| **DEF-12** | HUD opacity and translucent glass styling lacking contrast & translucency | Medium | VERIFIED | `test_hud_controls_and_transparency_regression.py` |

---

## Detailed Defect Records

### DEF-01: Application Crashes on Cross-Thread Widget Access & Shutdown
- **Reproduction Steps**:
  1. Trigger manual query in HUD chat, or run multiple solves in quick succession.
  2. Exit the application via tray or main window close button.
- **Expected Behavior**: Background workers communicate purely via thread-safe signals; shutdown exits cleanly without raising `SystemExit` or Win32 access violations (`0xC0000005`).
- **Actual Behavior**: `self.hud.start_solve()` was invoked directly within `_worker()` and `_solve_worker()` background threads. `sys.exit(0)` was called during Qt event handling causing traceback spam.
- **Root Cause**: Non-GUI threads calling PyQt6 widget methods directly instead of routing through `QtEventBridge`; `sys.exit(0)` called inside Qt callbacks.
- **Source Files Changed**: `ghostline/app.py`, `ghostline/ui/qt_hud_overlay.py`
- **Automated Test**: `tests/test_qt_ui_hotkey_regression.py`, `tests/test_secondary_controls_regression.py`
- **Manual Verification Result**: Verified. Solve lifecycle dispatches strictly via `sig_solve_started` and `sig_solve_completed`. Background threads never invoke Qt widget methods. `shutdown()` safely routes to main thread if triggered from pystray thread.
- **Remaining Limitations**: None.

---

### DEF-02: Custom Keyboard Shortcuts Not Working or Persisting
- **Reproduction Steps**:
  1. Open Settings -> General -> Custom Shortcut.
  2. Click shortcut button, enter a new shortcut (e.g. `Ctrl + Shift + S`).
  3. Restart the application or try pressing the new shortcut immediately.
- **Expected Behavior**:
  - The new shortcut is saved to `config.json` and survives restarts.
  - The runtime listener unregisters the old hotkey and registers the new one immediately without requiring restart.
  - Invalid combinations or conflicting keys produce clear user errors.
  - Displayed shortcut and actual registered shortcut match.
- **Actual Behavior**:
  - `save_config()` was never called on hotkey edit.
  - `on_settings_saved` contained zero logic to unregister/re-register the hotkey with the Win32 message pump.
  - `parse_hotkey_string` lacked validation for modifiers and function keys.
- **Root Cause**: Missing persistence call, missing Win32 hotkey re-registration message in `_hotkey_listener_loop`, and incomplete virtual key lookup map.
- **Source Files Changed**: `ghostline/config.py`, `ghostline/app.py`, `ghostline/ui/qt_main_window.py`
- **Automated Test**: `tests/test_custom_shortcuts_regression.py` (7 tests)
- **Manual Verification Result**: Verified. `QtShortcutDialog` validates modifiers, catches conflicts, normalizes strings, and calls `save_config()`. Win32 message `WM_GHOSTLINE_RELOAD_HOTKEYS` is posted to listener loop, dynamically updating registered hotkey without application restart.
- **Remaining Limitations**: None.

---

### DEF-03: "Hide from Taskbar" Setting Fails to Hide Taskbar Button
- **Reproduction Steps**:
  1. Navigate to Settings -> General -> App Visibility.
  2. Enable "Hide from taskbar".
  3. Check the Windows taskbar.
- **Expected Behavior**: When enabled, the main window is hidden from the taskbar (`WS_EX_TOOLWINDOW` / `Qt.WindowType.Tool`), minimizing to the system tray, while remaining accessible via tray click.
- **Actual Behavior**: The toggle switch modified `start_minimized` instead of a dedicated `hide_from_taskbar` flag, and no Windows/Qt window flags were applied.
- **Root Cause**: Missing `hide_from_taskbar` property in `AppConfig` and missing runtime `WS_EX_TOOLWINDOW` style application in `QtGhostlineMainWindow`.
- **Source Files Changed**: `ghostline/config.py`, `ghostline/ui/qt_main_window.py`, `ghostline/app.py`
- **Automated Test**: `tests/test_taskbar_icon_regression.py` (6 tests)
- **Manual Verification Result**: Verified. Dedicated `hide_from_taskbar` boolean field added to `AppConfig`. `apply_taskbar_visibility()` applies `WS_EX_TOOLWINDOW` dynamically via `SetWindowLongW` and `SWP_FRAMECHANGED`. Window hides cleanly to tray on minimize or close.
- **Remaining Limitations**: None.

---

### DEF-04: Custom Icon Selection Broken & Missing Functionality
- **Reproduction Steps**:
  1. Go to Settings -> General -> App Visibility -> Default icon.
  2. Select any item from the dropdown or attempt to select a custom file.
- **Expected Behavior**: User can select from stealth presets or browse for a custom `.ico`/`.png` file with live preview, persistent storage in `%APPDATA%\Ghostline\custom_icon.*`, and immediate update to window and tray icons.
- **Actual Behavior**: The dropdown was an unconnected list with four dummy labels. No file picker, no preview, no config storage, and no icon update logic existed.
- **Root Cause**: Feature was partially stubbed in UI without supporting backend in `AppConfig`, `QtGhostlineMainWindow`, or `TrayIndicator`.
- **Source Files Changed**: `ghostline/config.py`, `ghostline/ui/qt_main_window.py`, `ghostline/ui/tray_indicator.py`, `ghostline/app.py`
- **Automated Test**: `tests/test_taskbar_icon_regression.py`
- **Manual Verification Result**: Verified. Preset dropdown supports `Default Ghostline`, `Stealth Dot`, `Windows Utility`, and `Custom Icon...`. File picker validates image format and size (<5MB), copies custom asset to user data directory, displays live thumbnail preview, and updates both main window and tray icon without restarting.
- **Remaining Limitations**: None.

---

### DEF-05: HUD Chat Input Fails End to End
- **Reproduction Steps**:
  1. Open HUD Overlay.
  2. Type a question into the bottom input field ("Ask a follow-up or custom question...") and click "Ask" or press Enter.
- **Expected Behavior**: Input is validated (empty queries rejected cleanly), query is sent via thread-safe bridge to local Ollama inference with prior conversation context, loading state is displayed, answer renders in scroll area with code blocks if applicable, and input remains responsive.
- **Actual Behavior**:
  - `on_hud_ask_custom` called GUI methods from a background thread.
  - Query was passed without context to `solve_question` (MCQ prompt), erasing the question text in the HUD and displaying "Question text analyzed".
  - Older slow responses could overwrite newer conversations.
- **Root Cause**: Incomplete chat pipeline missing context preservation, thread-safe UI signals, and request sequence tracking.
- **Source Files Changed**: `ghostline/app.py`, `ghostline/ui/qt_hud_overlay.py`, `ghostline/core/llm_client.py`
- **Automated Test**: `tests/test_hud_chat_end_to_end.py` (6 tests)
- **Manual Verification Result**: Verified. `set_chat_loading()`, `set_chat_response()`, and `set_chat_error()` route via `sig_hud_chat_*` Qt signals. Question and answer context from previous solves are preserved and sent as prompt context. Input is disabled during inference and re-enabled on response. Sequence IDs prevent out-of-order response overwrites.
- **Remaining Limitations**: Local Ollama daemon must be running for live AI inference responses.

---

### DEF-06: Floating HUD Layout Far Too Compact
- **Reproduction Steps**:
  1. Press `Alt + /` or toggle the HUD overlay on standard 1080p / 1440p displays.
- **Expected Behavior**: HUD opens at comfortable default desktop dimensions (e.g. 640x560), resizable between 540x440 and 1400x950, with clear toolbar buttons, readable 14px typography, and ample scrolling room.
- **Actual Behavior**: Default dimensions were 380x300, clamped to 480x340. The 7 toolbar items were squished, and Island 3 content was cramped into ~120px.
- **Root Cause**: Extremely restrictive default dimensions in `AppConfig` and `QtGhostlineHudOverlay`.
- **Source Files Changed**: `ghostline/config.py`, `ghostline/ui/qt_hud_overlay.py`
- **Automated Test**: `tests/test_hud_layout_usability.py` (6 tests)
- **Manual Verification Result**: Verified. Config defaults increased to 640x560 (min 540x440, max 1400x950). Added `validate_and_apply_geometry()` to keep HUD inside screen boundaries. Added `_toggle_size_mode()` allowing rapid switching between Compact (560x440) and Expanded (760x640) views.
- **Remaining Limitations**: None.

---

### DEF-07: Broken / Disconnected Secondary Controls & Thread-Safe Tray Bridge
- **Reproduction Steps**:
  1. Open Mode Settings: notice mode combobox always defaulted to index 1 regardless of config value.
  2. Click tray menu items ("Open Ghostline", "Settings", "Show/Hide Mini HUD", "Quit"): actions executed directly on pystray thread touching PyQt6 widgets.
- **Expected Behavior**:
  - Mode combobox reflects saved `indicator_mode` on startup and updates live canvas preview on change.
  - Tray menu actions route safely through `QtEventBridge` queued signals to execute exclusively on the PyQt6 main thread.
- **Actual Behavior**:
  - `combo_mode.setCurrentIndex(1)` was hardcoded, causing UI state drift.
  - `TrayIndicator` invoked Qt window methods directly from background daemon thread.
- **Root Cause**: Hardcoded initial index in `_build_mode_view` and missing thread synchronization in tray callbacks.
- **Source Files Changed**: `ghostline/ui/qt_main_window.py`, `ghostline/app.py`
- **Automated Test**: `tests/test_secondary_controls_regression.py` (4 tests)
- **Manual Verification Result**: Verified. `combo_mode` initializes from `config.indicator_mode`, updates preview label, and removes duplicate save signals. `QtEventBridge` provides `sig_open_settings` and `sig_shutdown` to ensure tray actions execute on the Qt main thread.
- **Remaining Limitations**: None.

---

### DEF-08: Live-Call Audio Pipeline Stalled & Capture Muted
- **Reproduction Steps**:
  1. Start Live Audio Assistant session.
  2. Speak a question or play remote speaker audio.
  3. Notice transcription stalls, trailing words repeat, or microphone input gets completely muted after initial loopback sound.
- **Expected Behavior**:
  - Microphone and Windows WASAPI loopback streams capture continuously without acoustic echo bleed permanently zeroing microphone input.
  - Pausing speech triggers immediate transcription flush (>0.40s silence with >=0.65s buffer) so short 1-2s queries transcribe promptly.
  - Questions spoken on either system call audio or user microphone automatically trigger local Ollama answering when auto-answer is enabled.
- **Actual Behavior**:
  - Acoustic bleed check maintained stale system RMS indefinitely when system audio stopped, permanently suppressing mic frames.
  - Buffers required full 3.0s (48,000 samples) before processing, trapping short utterances in memory indefinitely.
  - Auto-answer only reacted to `source == "call"`, ignoring questions spoken by the user on the microphone.
- **Root Cause**: Stale RMS bleed tracking in `AudioCaptureManager._process_raw_pcm`, lack of pause silence flush in `LiveTranscriber._transcription_worker_loop`, and source filter in `LiveAudioAssistant.add_segment`.
- **Source Files Changed**: `ghostline/audio/capture.py`, `ghostline/audio/transcription.py`, `ghostline/audio/assistant.py`
- **Automated Test**: `tests/test_live_call_pipeline_regression.py` (4 tests)
- **Manual Verification Result**: Verified. Acoustic bleed decays by 0.85 per chunk and resets when inactive (>0.35s). Silence pause triggers buffer flush and clears memory. Both `call` and `mic` question segments trigger LLM generation.
- **Remaining Limitations**: Windows WASAPI loopback requires audio to be playing through an active output endpoint.

---

### DEF-09: Unresponsive HUD Controls & Missing Action Slots
- **Reproduction Steps**:
  1. Open Live Audio HUD or MCQ HUD.
  2. Click Copy Answer, Pause, or toggle Microphone / System Audio.
  3. Notice missing callbacks or unhandled `AttributeError` when background events arrive.
- **Expected Behavior**:
  - Every button has an explicit, active slot connection.
  - Audio panel allows independently toggling microphone and system call capture.
  - HUD overlay provides Answer, Screenshot, Chat, Pause/Resume, Copy Question, Copy Answer, Copy Code, Clear, and Size mode toggle.
- **Actual Behavior**:
  - `QtLiveAudioPanel` lacked `set_ai_error` causing cross-thread signal crashes when Ollama was offline.
  - `QtGhostlineHudOverlay` lacked `append_ai_answer` and `set_ai_thinking` methods called from live audio dispatch.
  - Copy Answer button was missing from the Q&A card layout.
- **Root Cause**: Incomplete method parity between `QtLiveAudioPanel` and `QtGhostlineHudOverlay` event bridges, and missing toolbar button connections.
- **Source Files Changed**: `ghostline/ui/qt_audio_panel.py`, `ghostline/ui/qt_hud_overlay.py`, `ghostline/app.py`
- **Automated Test**: `tests/test_hud_controls_and_transparency_regression.py` (5 tests)
- **Manual Verification Result**: Verified. All buttons audited and connected. Audio toggles update capture state dynamically. Error handling displays clear inline status banners without raising exceptions.
- **Remaining Limitations**: None.

---

### DEF-10: MCQ HUD "End" Button Disconnected & Lacked Session Teardown
- **Reproduction Steps**:
  1. Open the MCQ HUD.
  2. Click the red "End" button in the top toolbar.
- **Expected Behavior**:
  - Stops any active solving session, cancels running timer/inference workers, invalidates in-flight callbacks, pauses auto-hover so the HUD does not immediately pop back up, cleanly hides the HUD, and restores tray and main app to a ready state.
- **Actual Behavior**:
  - The End button only called `self.hide_overlay()` without resetting `self.is_solving`, without notifying the hover detector, and without canceling background threads. If auto-hover was active, the HUD would immediately reappear on cursor hover.
- **Root Cause**: Lack of an `on_end` session lifecycle teardown callback connected to `GhostlineApp`.
- **Source Files Changed**: `ghostline/ui/qt_hud_overlay.py`, `ghostline/app.py`
- **Automated Test**: `tests/test_hud_controls_and_transparency_regression.py`
- **Manual Verification Result**: Verified. `GhostlineApp.on_hud_end` resets solver flags, increments chat sequence counter to drop stale in-flight results, notifies `hover_detector.notify_solve_completed()`, sets HUD state to ready, and resets tray badge.
- **Remaining Limitations**: None.

---

### DEF-11: Custom Taskbar & Window Icon Synchronization
- **Reproduction Steps**:
  1. Select a custom icon or stealth preset in Settings.
  2. Observe the Windows taskbar and main application window.
  3. Restart the application.
- **Expected Behavior**:
  - The Windows taskbar item immediately reflects the selected icon.
  - The icon survives application restart and works in the packaged executable.
- **Actual Behavior**:
  - Windows taskbar retained the default generic Python or PyInstaller icon because Windows groups windows by `AppUserModelID` and queries Win32 `WM_SETICON`.
- **Root Cause**: Missing explicit `SetCurrentProcessExplicitAppUserModelID` call before Qt initialization and lack of Win32 `WM_SETICON` message dispatch.
- **Source Files Changed**: `ghostline/app.py`, `ghostline/ui/qt_main_window.py`
- **Automated Test**: `tests/test_taskbar_icon_regression.py`
- **Manual Verification Result**: Verified. Process sets `SetCurrentProcessExplicitAppUserModelID("Ghostline.AI.Desktop.v1")`. `apply_icon()` writes `active_icon.ico` and dispatches `WM_SETICON` (`ICON_BIG` and `ICON_SMALL`) directly to the window HWND, updating the taskbar instantly.
- **Remaining Limitations**: Windows Explorer icon cache may retain stale thumbnail until refreshed if system cache is full.

---

### DEF-12: HUD Opacity & Translucent Glass Styling
- **Reproduction Steps**:
  1. Open the HUD overlay or Live Audio HUD over dark or light desktop backgrounds.
- **Expected Behavior**:
  - Subtle, premium glass-like appearance (translucent dark charcoal `rgba(18, 21, 28, 0.86)` with `1px solid #334155` border) with window opacity at 0.86.
  - Desktop content underneath is slightly visible, while all text, question titles, gold stars, code blocks, and buttons retain crisp 100% contrast.
- **Actual Behavior**:
  - `setWindowOpacity()` was never called on `QtGhostlineHudOverlay`, leaving it at opaque 1.0 or using opaque card backgrounds.
- **Root Cause**: Missing `setWindowOpacity(self.opacity)` call during HUD construction and missing `hud_opacity` configuration parameter.
- **Source Files Changed**: `ghostline/config.py`, `ghostline/ui/qt_hud_overlay.py`, `ghostline/ui/qt_audio_panel.py`, `ghostline/app.py`
- **Automated Test**: `tests/test_hud_controls_and_transparency_regression.py`
- **Manual Verification Result**: Verified. Window opacity defaults to 0.86 and island containers use sleek translucent styling (`rgba(18, 21, 28, 0.86)` with slate borders). Text and code retain solid contrast and sharp readability.
- **Remaining Limitations**: None.

