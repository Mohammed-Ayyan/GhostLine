# Phase 8 Report — Small Safe Improvements

**Execution Date:** 2026-11-01 20:55:15 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Single-Instance Guard & Primary Instance Activation
- **Mutex Implementation (`ghostline/app.py:2748`)**:
  - `Local\\GhostlineSingleInstanceMutex` created at startup via Win32 `CreateMutex`.
  - If `GetLastError() == ERROR_ALREADY_EXISTS`:
    - Locates existing primary instance message sink window via `FindWindow("GhostlineSinkWindowClass", None)`.
    - Dispatches `WM_GHOSTLINE_WAKEUP` (`0x8001`) via `PostMessage` to restore and bring the primary instance to the foreground.
    - Exits immediately with returncode `0`, preventing duplicate Win32 global hotkey registration conflicts or duplicate audio stream hooks.

---

## 2. Log Rotation & "Open Logs Folder" Affordance
- **Log Rotation (`ghostline/app.py:317`)**:
  - Converted file logging to `logging.handlers.RotatingFileHandler`.
  - Max log size: 5 MB (`maxBytes = 5 * 1024 * 1024`).
  - Backup count: 3 archives (`backupCount = 3`), keeping disk consumption bounded.
- **Tray Context Menu Item (`ghostline/ui/tray_indicator.py:122`)**:
  - Added menu action `"Open logs folder"`.
  - Calls `os.startfile(get_app_dir())`, opening `%APPDATA%\\Ghostline` in Windows File Explorer.

---

## 3. Global Hotkeys Catalog & Conflict Indicator
- **Settings UI (`ghostline/ui/qt_main_window.py:640`)**:
  - Added dedicated card `"All Global Hotkeys"` to General Settings.
  - Lists all 9 global shortcuts with human-readable descriptions, key combinations, and interactive configuration dialogs for editable shortcuts (`Alt + /`, `Alt + T`, `Ctrl + Alt + Q`).
  - Conflict indicator: Displays live registration status (`● All 9 Global Hotkeys Registered — No System Conflicts`).
  - If a Windows hotkey conflict occurs during registration, Ghostline catches the error, logs it, and shows a warning balloon notification via the system tray.

---

## 4. First-Run Onboarding Experience
- Added `first_run_complete: bool = False` to `AppConfig` (`ghostline/config.py:65`).
- On initial launch, Ghostline presents a non-intrusive Windows system tray balloon:
  - Title: *"Welcome to Ghostline!"*
  - Content: *"Ghostline is ready:\n• Alt + / : Solve question under cursor\n• Alt + T : Show/hide answer HUD\n• Alt + A : Live audio assistant\n• Ctrl + Alt + Q : Cleanly quit Ghostline"*
- Sets `config.first_run_complete = True` and atomically saves config so the introduction is shown only once.

