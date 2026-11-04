# Ghostline Run 7 — Architectural & Execution Decisions

## DEC-701: Autonomous Execution Strategy
- **Context**: The user specified that nobody is available to answer questions.
- **Decision**: Safest defaults must be selected automatically and documented in this registry. All actions adhere strictly to non-destructive workflows (backup created: `backup/pre-run7` and `../ghostline_backups/20261102_225341`).

## DEC-702: Evidence Standard for Run 7
- **Context**: Mocked tests and offscreen rendering can produce false confidence.
- **Decision**: E2E scenarios S1–S8 drive real GUI sessions with real audio pipeline classes, real provider communication via local HTTP fake server (`fake_ollama.py`), and real HWND window verification.

## DEC-703: UIPI and Sink Window Architecture
- **Context**: Win32 `WM_GHOSTLINE_AUDIO_TOGGLE` IPC messages sent from external processes could be blocked by User Interface Privilege Isolation (UIPI) or missed if a redundant main-thread sink window shadowed the hotkey worker sink.
- **Decision**: Removed the redundant main-thread sink window so only the message-pumping hotkey worker window receives window messages. Registered `WM_GHOSTLINE_AUDIO_TOGGLE` in `user32.ChangeWindowMessageFilter` (MSGFLT_ADD = 1) to ensure unblocked cross-process IPC delivery.

## DEC-704: Message Loop Dispatch De-duplication
- **Context**: When external IPC or hotkey thread received `WM_GHOSTLINE_AUDIO_TOGGLE`, the message pump loop emitted the bridge signal and then called `win32gui.DispatchMessage(msg)`, which forwarded the message to `_wndproc`, immediately firing the bridge signal a second time (causing an instant stop right after start).
- **Decision**: Added explicit `continue` in `_hotkey_listener_loop` after handling `msg_id == WM_GHOSTLINE_*` so that internal custom IPC messages are dispatched exactly once.

## DEC-705: Endpoint Synchronization (ollama_url vs provider_base_urls)
- **Context**: When `ollama_url` was passed in configuration, `AIRouter` preferred `provider_base_urls["ollama"]` which defaulted to `http://127.0.0.1:11434`, ignoring test overrides targeting fake endpoints.
- **Decision**: Added a Pydantic `model_validator` in `AppConfig` to synchronize `ollama_url` and `provider_base_urls["ollama"]`, and updated `AIRouter` to respect explicit `ollama_url` values.

## DEC-706: Strict HUD Auto-Popping Gating (F2)
- **Context**: `QtHudOverlay.update_answer` and `start_solve` previously called `self.show_overlay()` unconditionally, making the HUD pop up even when `show_hud_on_solve = False`.
- **Decision**: Introduced `self.auto_show_on_solve` attribute on `QtHudOverlay`, synchronized from `AppConfig.show_hud_on_solve`. `update_answer` and `start_solve` now check `if getattr(self, "auto_show_on_solve", False): self.show_overlay()`, ensuring Alt + / never shows or raises any window when the setting is OFF.

## DEC-707: High-Contrast Profile Input Contrast (F3)
- **Context**: Profile inputs had weak boundary contrast against `#292929` card surface.
- **Decision**: Styled profile fields with `SURFACE_INPUT = "#202020"`, high-contrast border `rgba(255, 255, 255, 0.45)` / `#858585` (achieving 3.94:1 contrast ratio, exceeding the 3:1 WCAG requirement), standard 34px single-line height, $\ge 96$px multi-line height, visible `<QLabel>` titles, and a working dirty indicator Save button.

## DEC-708: Settings Inventory Guard & Audio Testing (F4)
- **Context**: Settings controls for System Tray, close-to-tray behavior, and audio devices were previously missing or renamed.
- **Decision**: Standardized all `objectName` identifiers, added Audio Test diagnostic button (`btn_test_audio_hw`), and enforced control retention with `tests/fixtures/required_controls.json` and `tests/test_control_inventory.py`.
