# Ghostline Run 7 — Forensic Analysis & Defect Root Causes

## Executive Summary
This forensic investigation analyzes the root causes of the four user-reported failures on Release build 1.0.2 at git HEAD (`030ee2e`). Every finding is grounded in verifiable code lines (`file:line`) and commit history (`commit_sha:file:line`).

---

## 1. Defect F1: Live Audio & Video-Call Mode Failure

### 1.1 Microphone & WASAPI Loopback Audio Capture Path
- **Microphone path**: `ghostline/audio/capture.py:294-304` opens PyAudio WASAPI microphone stream.
- **System loopback path**: `ghostline/audio/capture.py:281-292` and `ghostline/audio/capture.py:385-445` attempts WASAPI loopback capture.
- **Resampling & Queue**: `ghostline/audio/capture.py:250-258` converts incoming audio to 16 kHz float32 mono and delivers chunks via `on_audio_chunk`.
- **Transcription**: `ghostline/audio/transcription.py:255-295` worker thread passes buffers to `faster_whisper.WhisperModel`.
- **Question detection**: `ghostline/audio/assistant.py:120-190` monitors transcription segments and invokes `ollama_client`.
- **UI presentation**: `ghostline/app.py:1177-1186` receives AI answer via `_on_audio_answer` and emits `self.bridge.sig_audio_answer`.

### 1.2 Root Causes of F1 Breakdown
1. **Missing Offline Model File**:
   - `ghostline/audio/transcription.py:31-69` (`resolve_whisper_model_path`) looks for `model.bin` in frozen bundle, exe directory, repo directory (`ghostline/models/tiny/model.bin`), and `%APPDATA%\Ghostline\models\tiny\model.bin`.
   - `.gitignore:17` ignores `ghostline/models/tiny/model.bin` and binary model assets.
   - On the current working tree, `ghostline/models/tiny/model.bin` is completely missing.
   - When missing, `resolve_whisper_model_path("tiny")` returns `("tiny", False)`.
   - `ghostline/audio/transcription.py:211-217` attempts to download `systran/faster-whisper-tiny` via HuggingFace Hub. In offline environments or without user consent, this throws `requests.exceptions.ConnectionError` or `urllib3.exceptions.MaxRetryError`.
   - `ghostline/audio/transcription.py:227-253` catches the exception and falls back to CPU `int8`, which again fails with the exact same offline exception.

2. **Swallowed Model Initialization Errors**:
   - In `ghostline/app.py:460-466`, `self.transcriber = LiveTranscriber(...)` is initialized without passing an `on_status` callback.
   - When model initialization fails in `ghostline/audio/transcription.py:252`, `self._notify_status(f"Error: {err_text}")` is called, but because `on_status is None`, the failure message is dropped silently. The user is never informed that the speech engine failed to load.

3. **Invisible Live Interface**:
   - When the user presses the live audio hotkey (Alt + \) or toggles capture, `ghostline/app.py:1717-1766` (`start_audio_capture`) emits `self.bridge.sig_audio_status(True, False)`.
   - In `ghostline/app.py:879-886`, `_main_thread_audio_status` only updates internal state booleans on `self.hud` and `self.audio_panel`.
   - Neither `self.audio_panel.show_panel()` nor `self.hud_manager.show_mode(HudMode.LIVE)` is called.
   - Consequently, the user sees no UI feedback, no audio level meters, no transcript window, and has no indication that listening is active.

4. **WASAPI Loopback Silence & Endpoint Invalidation**:
   - In `ghostline/audio/capture.py:385-445`, WASAPI loopback requires an active Windows audio rendering endpoint. If no application is playing audio or headphones are put in standby, Windows WASAPI delivers no stream callbacks or throws `AUDCLNT_E_DEVICE_INVALIDATED`.
   - In `ghostline/audio/capture.py:284-291`, if system stream opening fails, the error is appended to `errors` but discarded if microphone opens successfully (`ghostline/audio/capture.py:313`). No warning is displayed to the user explaining that system loopback is unavailable.

5. **Inaccessible Audio Device Controls**:
   - In commit `4ef0abc:ghostline/ui/qt_main_window.py:58-65`, sidebar navigation was reduced from 8 screens to 6 screens.
   - `self.screen_frames["audio"]` (built by `_build_audio_view` at `ghostline/ui/qt_main_window.py:2260`) was disconnected from navigation, leaving device pickers for Microphone and System Audio unreachable.

---

## 2. Defect F2: HUD Auto-Popping on Alt + / When Setting is OFF

### 2.1 Trace of Alt + / (`solve_selection_hotkey`)
1. User presses Alt + /: Global hotkey handler in `ghostline/app.py:2050` triggers `solve_selection_hotkey()`.
2. `solve_selection_hotkey()` checks `show_hud = getattr(self.config, "show_hud_on_solve", True)`.
3. In `ghostline/app.py:2066`: If `show_hud` is False, `app.py` avoids calling `self.hud.show_overlay()`.
4. However, `app.py:2067` proceeds to call `self.hud.set_state("capturing", solve_id=solve_id)`.
5. When OCR completes, worker calls `self.hud.set_state("ocr")`.
6. When LLM query begins, worker calls `self.hud.set_state("thinking")`.
7. When answer arrives, `app.py:700-715` calls `self.hud.set_state("answer", presentation=...)`.
8. When an error occurs, `app.py:765-779` calls `self.hud.set_state("error", presentation=...)`.

### 2.2 Root Cause of F2 Auto-Popping
- In `ghostline/ui/qt_hud_overlay.py:1487-1507`:
  ```python
  def set_state(self, state: str, presentation: Optional[Any] = None, solve_id: int = 0):
      if state == "capturing":
          self.set_keyword_chips(["Capture", "Screen"])
          self.show_overlay()   # <-- UNCONDITIONAL SHOW
      elif state == "ocr":
          self.set_keyword_chips(["OCR", "Extracting"])
          self.show_overlay()   # <-- UNCONDITIONAL SHOW
      elif state == "thinking":
          self.set_keyword_chips(["Ollama", "Thinking"])
          self.show_overlay()   # <-- UNCONDITIONAL SHOW
      elif state == "answer":
          if presentation:
              self.update_answer(presentation, entry_id=f"solve_{solve_id}" if solve_id else None)
          self.show_overlay()   # <-- UNCONDITIONAL SHOW
      elif state == "error":
          ...
          self.show_overlay()   # <-- UNCONDITIONAL SHOW
  ```
- Every state transition invokes `self.show_overlay()` without checking `self.config.show_hud_on_solve`.
- At `ghostline/ui/qt_hud_overlay.py:2386-2389`:
  ```python
  def show_overlay(self):
      self.show()
      self.raise_()
  ```
- This forces the HUD window to become visible and calls `raise_()`, which can steal focus or disrupt user workflow even when the user explicitly disabled auto-showing.

---

## 3. Defect F3: My Profile Input Visibility & Styling

### 3.1 Color Collision & Contrast Ratio
- `ghostline/ui/theme/tokens.py:7`: `SURFACE_CARD = "#292929"`.
- `ghostline/ui/theme/tokens.py:9`: `SURFACE_INPUT = "#292929"`.
- In `ghostline/ui/theme/builder.py:379-388`, `QLineEdit` background is set to `{SURFACE_INPUT}` (`#292929`).
- When `QLineEdit` is placed inside `QFrame#CardFrame` (`#292929`), the relative luminance of both elements is identical ($L = 0.021$).
- Calculated WCAG 2.1 contrast ratio:
  $$\text{Contrast} = \frac{0.021 + 0.05}{0.021 + 0.05} = 1.00:1$$
  This fails the WCAG minimum threshold for graphical controls ($\ge 3:1$). The input fields have no visual boundary against the card surface.

### 3.2 Missing Styles for Multi-Line Text Inputs
- In `ghostline/ui/theme/builder.py:379-420`, styles are defined only for `QLineEdit` and `QComboBox`.
- `QTextEdit` and `QPlainTextEdit` are completely omitted from the stylesheet builder, leaving multi-line inputs with unstyled or default Qt borders and background fills.

### 3.3 Layout & Structural Defects in `_build_profile_view`
- In `ghostline/ui/qt_main_window.py:3338-3358`:
  - `txt_profile_name` (`ProfileName`) and `txt_profile_role` (`ProfileRole`) have placeholder text but NO `<QLabel>` above them.
  - `txt_profile_target_role` (`ProfileTargetRole`) has NO `<QLabel>` above it.
  - `txt_profile_skills` (`ProfileSkills`) at line 3370 has NO `<QLabel>` above it.
  - `txt_profile_education` and `txt_profile_languages` at lines 3401-3410 have NO `<QLabel>` above them.
- In `ghostline/ui/qt_main_window.py:3365, 3383, 3394`:
  - `txt_profile_bio` has fixed height 64px (violates requirement $\ge 96$px).
  - `txt_profile_experience` has fixed height 76px (violates requirement $\ge 96$px).
  - `txt_profile_projects` has fixed height 64px (violates requirement $\ge 96$px).
- Profile inputs are arranged in an unorganized vertical list rather than structured collapsible/expander sections ("Basics", "Background", "Preferences").

---

## 4. Defect F4: Missing Settings Options & Navigation Drift

### 4.1 Historical Comparison: Commit `6a6895d` vs HEAD (`030ee2e`)
In commit `6a6895d` (baseline prior to Run 1 restyle):
- `ghostline/ui/qt_main_window.py:68-77` featured 8 navigation sidebar items:
  1. `general` (General Settings)
  2. `mode` (Mode Configuration: Video Call, Interview, Stealth)
  3. `dashboard` (System Dashboard)
  4. `audio` (Audio Settings: Mic, Loopback, Testing)
  5. `model` (AI Models & Providers)
  6. `history` (Audit Log)
  7. `security` (Security & Encryption)
  8. `diagnostics` (Hardware & System Diagnostics)

In commit `4ef0abc` (Run 1) and refined in Run 6:
- The sidebar was reduced to 6 items: `dashboard` (Home), `profile` (My Profile), `model` (AI), `history` (History), `general` (Settings), `help` (Help).
- The views `_build_mode_view`, `_build_audio_view`, `_build_security_view`, and `_build_diagnostics_view` remained instantiated in `self.screen_frames`, but the buttons to access them were removed.
- In `_build_general_view`, Section 5 ("Tray & Startup Preferences") was added at line 1339. However:
  - The controls (`switch_show_tray`, `combo_close_action`, `switch_start_minimized`, `switch_start_with_windows`) lacked standardized `setObjectName` declarations, causing control inventory queries to miss them.
  - Audio device selectors were entirely absent from `Settings` (`general`), leaving users with no accessible UI to choose microphones or loopback endpoints.
  - Mode configurations (Stealth, Interview, Video Call) were stranded on the unreachable `screen_frames["mode"]`.

---

## 5. Architectural Remediation Plan
1. **F1 (Live Audio)**:
   - Restore bundled `tiny/model.bin` to `ghostline/models/tiny/model.bin` and ensure `%APPDATA%\Ghostline\models\tiny\model.bin` fallback.
   - Connect `LiveTranscriber(on_status=...)` to `self.bridge.sig_audio_status_message` and display live status in UI.
   - Automatically display the Live Audio panel upon listening start or Alt + \ press (`open_live_panel_on_listen = True`).
   - Add a compact status strip in the Live panel indicating Mic (name/level), Loopback (name/level), Speech Engine (Ready/Error), and AI Provider (Connected/Error).
   - Restore Audio device selector card and Audio Test button in Settings.

2. **F2 (HUD Gating & Focus)**:
   - Introduce a centralized `HudController` in `ghostline/ui/hud_manager.py` with `request_show(reason: ShowReason)`.
   - Gate all solve-driven visibility requests (`SOLVE_COMPLETE`, `AUTO_STREAM`, `CAPTURING`, `OCR`) behind `self.config.show_hud_on_solve`.
   - In `qt_hud_overlay.py`, remove unconditional `self.show_overlay()` calls from `set_state()`.
   - Enforce `SW_SHOWNOACTIVATE` via `user32.ShowWindow` and set `WS_EX_NOACTIVATE` window style so the HUD never steals focus on show.

3. **F3 (Profile Contrast & Controls)**:
   - Update `SURFACE_INPUT = "#202020"` in `tokens.py` (contrast $\ge 3:1$ against `#292929` card surface).
   - Add `QTextEdit, QPlainTextEdit` styling in `builder.py` with minimum height 96px, 1px `#858585` border, and 2px `#60CDFF` bottom focus line.
   - Insert explicit `<QLabel>` elements with `font-weight: 500` above every profile field.
   - Organize profile fields into categorized expanders ("Basics", "Background", "Preferences") with unsaved changes indicator and prominent Save button.

4. **F4 (Settings & Control Inventory Guard)**:
   - Re-integrate System Tray controls, Audio device pickers, and Mode settings into the Settings view with explicit `setObjectName` attributes.
   - Create `tests/fixtures/required_controls.json` and `tests/test_control_inventory.py` asserting all required controls exist and remain visible.

