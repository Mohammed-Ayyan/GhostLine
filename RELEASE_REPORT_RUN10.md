# Ghostline v1.0.3 — Run 10 Release & Delivery Report

**Release Tag:** `v1.0.3`  
**Execution Date:** November 8, 2026  
**Target Repository:** `https://github.com/Mohammed-Ayyan/GhostLine`  
**Active Branches:** `main` (HEAD synchronized with `origin/main`), `run10/video-and-site` (synchronized with `origin/run10/video-and-site`)  
**Safety Status:** 100% Automated Verification (Zero data loss, zero forced pushes, zero history rewrites, zero plain-text credential leaks, zero unhandled exceptions)

---

## Executive Summary

Run 10 completes the full modernization, brand elevation, hardware signalling restoration, release repackaging, and clean-slate readiness cycle for Ghostline v1.0.3:

1. **Rebuilt Master Video Suite (Part 2):** Eliminated the broken legacy video assets (which suffered from missing `+faststart` atoms, 73 frozen video intervals, inaudible -33.3 LUFS audio, and illegible mobile UI). Engineered an automated PyQt6 QPainter rendering pipeline producing 9 brand-new videos:
   - **H1 Launch Film:** 16:9, 1080p, 92s narrative master with kinetic typography and beat-synced motion.
   - **H2 Homepage Hero Loop:** 16:9, 720p, 8s, 0.53 MB (budget $\le$ 2 MB), perfectly seamless looping preview.
   - **V1 Setup Tutorial:** 16:9, 1080p, 140s step-by-step setup walkthrough.
   - **V2 Usage Walkthrough:** 16:9, 1080p, 180s comprehensive usage guide.
   - **S1–S5 Vertical Shorts:** 9:16, 1080x1920, 35s each, tailored for mobile platforms.
   - Mastered original electronic synth soundtrack to exact **-14.1 LUFS** / $\le -1.5$ dBTP.
   - Verified **0 freezes > 1.2s**, faststart `moov` atom at byte 36, JPEG posters strictly $\le 60$ KB, and full WebVTT / text transcripts.
   - Landed the web bundle in `website/media/` at **88.77 MB** (under the 90 MB budget).

2. **Marketing-Grade Website Overhaul (Part 3):** Redesigned `website/index.html` and subpages in Microsoft Fluent 2 Dark:
   - 3D perspective app replica preview hosting the seamless 8s hero loop.
   - Accessible native HTML5 `<dialog id="video-modal">` with focus trapping, `Escape` key dismiss, and subtitle tracks.
   - Responsive 12-column Bento Grid highlighting 6 core pillars.
   - Dedicated Video Library showcasing all 9 produced films and tutorials.
   - Strictly preserved all Run 9 interactive features: simulated demo sandbox (4 tabs), hardware model advisor slider, install guide, copy blocks.
   - Playwright verification: 0 console errors, 0 page errors, keyboard navigation verified.
   - Performance budget audit: CSS 7.25 KB gz (budget $\le$ 50 KB), JS 6.59 KB gz (budget $\le$ 150 KB).

3. **Multi-Key Hardware Signalling & Silent Operation (Part 4):**
   - Restored physical keyboard LED blinking across Caps Lock, Num Lock, and Scroll Lock keys via Win32 `SendInput`/`keybd_event` without stealing window focus.
   - Answer pulse mapping: 1 pulse for A/Option 1/True, 2 pulses for B/Option 2/False, 3 pulses for C/Option 3, 4 pulses for D/Option 4.
   - Completely removed desktop tray balloon notification popups on answer readiness in favor of silent status badges and keyboard LED signalling.

4. **Release Build v1.0.3 (Part 5):**
   - Single source of truth bumped to `1.0.3` across all metadata and configuration files.
   - Packaged Inno Setup installer (`Ghostline-Setup.exe`, 245.35 MB) and portable standalone package (`Ghostline-Portable.zip`, 311.94 MB) with SHA-256 verification.
   - Verified against INSTALLED binary (`%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe`):
     - `Ghostline.exe --self-test` passed 100% checks.
     - E2E test battery S1–S12 passed 12/12 in 41.99s.
     - 40s soak test under active audio/inference load: RSS leveled off at 364.7 MB, net handle growth +15, 0 crashes in Windows Application Event Log.
     - UI lint: 0 violations (`tools/ui_lint.py`); control inventory passed (`tests/test_control_inventory.py`).

5. **Git Synchronization & Merge (Part 6):**
   - 6 pre-merge quality gates verified.
   - Pushed `run10/video-and-site` to `origin` with 500 MB `http.postBuffer`.
   - Merged `run10/video-and-site` into `main` with `--no-ff`.
   - Plain pushed `main` to `origin/main` (zero force-push, zero history rewriting).

6. **Clean Host PC Reset for Out-of-the-Box Testing (Part 7):**
   - Safe backup of user data and previous installation to `../ghostline_backups/user_data_20261108_121742/`.
   - Ollama left completely untouched and operational (verified HTTP 200 with `phi3:mini` and `qwen2.5:0.5b`).
   - Verified all 7 post-reset verification gates passed: host PC is in a clean out-of-the-box state, ready for the user to double-click `release_dist\Ghostline-Setup.exe`.

---

## 1. Cryptographic Release Assets (v1.0.3)

All release binaries are verified and located in `release_dist/`:

| Asset Name | Distribution Type | File Size | SHA-256 Integrity Checksum |
|---|---|---|---|
| **`Ghostline-Setup.exe`** | Windows Inno Setup Installer | 245.35 MB (257,270,320 bytes) | `642fd709c1d5e59ec1207f03fbf619faf10eff0adc2cada691e66c2ea6c83f4d` |
| **`Ghostline-Portable.zip`** | Portable Standalone ZIP | 311.94 MB (327,089,004 bytes) | `6e4a69ee690408065c58b5c792c2572be8b00ce2275c430fb6203e6e3ce5c103` |
| **`Ghostline-v1.0.3-win64-portable.zip`** | Versioned Portable Alias | 311.94 MB (327,089,004 bytes) | `6e4a69ee690408065c58b5c792c2572be8b00ce2275c430fb6203e6e3ce5c103` |
| **`SHA256SUMS.txt`** | Hash Manifest | 280 bytes | Manifest of SHA-256 checksums |

---

## 2. Master Video Production & Quality Metrics

All 9 videos were rendered via `tools/build_run10_videos.py` using hi-dpi PyQt6 QPainter rendering and mastered electronic synth audio (`tools/generate_synth_audio.py`):

| Video ID | Title | Resolution | Duration | Web Size | Poster Size | Freeze Events > 1.2s | Integrated Loudness |
|---|---|---|---|---|---|---|---|
| **H1** | Ghostline: Launch Film | 1920x1080 | 92.0s | 18.25 MB | 31.0 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **H2** | Homepage Hero Loop | 1280x720 | 8.0s | 0.53 MB | 25.9 KB | **0** | (Silent seamless loop) |
| **V1** | Download & Setup Tutorial | 1920x1080 | 140.0s | 19.01 MB | 53.2 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **V2** | How to Use Walkthrough | 1920x1080 | 180.0s | 26.88 MB | 48.1 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **S1** | Invisible Floating HUD | 1080x1920 | 35.0s | 4.95 MB | 56.0 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **S2** | 100% Offline AI Privacy | 1080x1920 | 35.0s | 4.99 MB | 30.2 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **S3** | Real-Time Interview Copilot | 1080x1920 | 35.0s | 4.60 MB | 30.0 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **S4** | Dual-Stream Audio WASAPI | 1080x1920 | 35.0s | 4.63 MB | 45.9 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **S5** | Zero Lag Local LLMs | 1080x1920 | 35.0s | 4.57 MB | 39.9 KB | **0** | -14.1 LUFS / $\le -1.5$ dBTP |
| **Total** | **9 Web Video Deliverables** | — | — | **88.77 MB** | **All $\le$ 60 KB** | **0 across all** | **Meets YouTube / Web Specs** |

- **Subtitles & Transcripts:** WebVTT files (`.vtt`) and plain text transcripts (`.txt`) accompany every spoken video in `website/media/`.
- **Faststart Byte Verification:** Every MP4 file was verified with `-movflags +faststart` placing the `moov` atom at byte 36 for immediate progressive playback.

---

## 3. Website Redesign & Accessibility Verification

The website (`website/`) was audited and redesigned under `reports/run10/site_style.md`:
- **Hero App Replica:** Features a 3D tilted Fluent card showcasing the 8s 720p hero loop with interactive "Play Master Film" trigger.
- **Accessible Video Modal:** HTML5 `<dialog id="video-modal">` with focus trapping, `Escape` key close listener, and responsive viewport sizing.
- **Interactive Bento Grid:** 12-column responsive layout detailing 6 key pillars (Offline-First Privacy, Live Meeting WASAPI Transcription, Zero-Focus-Steal Floating HUD, Physical Keyboard LED Pulses, Grounded Personal Profile, and BYOK Enterprise Engines).
- **Preserved Interactive Features:** Retained all 4 tabs of the simulated interactive demo sandbox, the hardware model advisor slider, install guide, and copy snippets.
- **Automated Playwright Audits:**
  - `tools/verify_website.py`: 0 console errors, 0 unhandled exceptions across Chromium & WebKit.
  - `tools/verify_video_modal.py`: Verified modal open, video playback, focus trap, and Escape key close.
  - Performance budgets: CSS 7.25 KB gz (budget $\le$ 50 KB), JS 6.59 KB gz (budget $\le$ 150 KB).
  - Visual critique documented in `reports/run10/site_critique.md`.

---

## 4. Installed Binary & E2E Test Suite Results

All tests were executed against the actual installed executable (`%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe`):

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
collected 12 items

tests/e2e/test_scenarios.py::test_s1_hud_auto_popping_prevented PASSED   [  8%]
tests/e2e/test_scenarios.py::test_s2_hud_auto_show_without_stealing_focus PASSED [ 16%]
tests/e2e/test_scenarios.py::test_s3_live_mic_speech_transcription_and_ai_answer PASSED [ 25%]
tests/e2e/test_scenarios.py::test_s4_system_loopback_speech_transcription PASSED [ 33%]
tests/e2e/test_scenarios.py::test_s5_audio_stop_cleanly PASSED           [ 41%]
tests/e2e/test_scenarios.py::test_s6_provider_switch_runtime PASSED      [ 50%]
tests/e2e/test_scenarios.py::test_s7_profile_gating PASSED               [ 58%]
tests/e2e/test_scenarios.py::test_s8_tray_and_close_behavior_controls_exist PASSED [ 66%]
tests/e2e/test_scenarios.py::test_s9_provider_error_mapping_and_ua PASSED [ 75%]
tests/e2e/test_scenarios.py::test_s10_ollama_state_machine_real_start PASSED [ 83%]
tests/e2e/test_scenarios.py::test_s11_hide_from_taskbar_style_and_single_instance PASSED [ 91%]
tests/e2e/test_scenarios.py::test_s12_copy_diagnostics_sanitization PASSED [100%]

============================= 12 passed in 41.99s =============================
```

- **Headless Self-Test (`--self-test`):** `providers_import`, `settings_load`, `dpapi_roundtrip`, `qt_platform_plugin`, `hardware_detection` all PASSED.
- **UI Lint (`tools/ui_lint.py`):** 0 violations.
- **Control Inventory (`tests/test_control_inventory.py`):** 100% controls verified.
- **Installed Soak Test (`reports/run10/soak_test.md`):** Memory stabilized at 364.7 MB, net handle growth +15, 0 crashes in Windows Application Event Log.

---

## 5. Host Reset Verification Matrix (Part 7)

The local machine has been safely cleaned and verified:

| Gate | Check | Outcome | Status |
|---|---|---|---|
| 1 | `tasklist` Ghostline processes | 0 processes active | **PASS** |
| 2 | Start Menu Ghostline shortcut | Absent | **PASS** |
| 3 | Desktop Ghostline shortcut | Absent across standard and OneDrive Desktop | **PASS** |
| 4 | Add/Remove Programs registry | Completely unregistered | **PASS** |
| 5 | Installed program folder | `%LOCALAPPDATA%\Programs\Ghostline` absent | **PASS** |
| 6 | User AppData configuration | `%APPDATA%\Ghostline` archived to backup | **PASS** |
| 7 | Ollama daemon | HTTP 200 with `phi3:mini` and `qwen2.5:0.5b` | **PASS** |

---

## 6. Manual Publication Steps for GitHub Release v1.0.3

Because the `gh` CLI tool is not installed on this system, publish the release via GitHub Web UI:

1. Navigate to: `https://github.com/Mohammed-Ayyan/GhostLine/releases/new`
2. **Choose a tag:** enter `v1.0.3` (Target: `main`).
3. **Release title:**
   ```
   Ghostline v1.0.3 — Master Videos, Website Redesign, Hardware Blinking
   ```
4. **Description:** Copy the `## [1.0.3] - 2026-11-08` section from `CHANGELOG.md`.
5. **Attach release binaries:** Drag and drop the following files from `release_dist/`:
   - `Ghostline-Setup.exe` (`642fd709c1d5e59ec1207f03fbf619faf10eff0adc2cada691e66c2ea6c83f4d`)
   - `Ghostline-Portable.zip` (`6e4a69ee690408065c58b5c792c2572be8b00ce2275c430fb6203e6e3ce5c103`)
   - `SHA256SUMS.txt`
6. Click **Publish release**.

---

## 7. Out-of-the-Box User Verification Instructions

The computer is in an authentic fresh-install state:
1. Double-click `release_dist\Ghostline-Setup.exe`.
2. Follow the setup wizard and complete installation.
3. Launch Ghostline from the Desktop or Start Menu shortcut.
4. Verify the first-run experience, Ollama model auto-detection, and hotkey activation (`Alt + /` for screen scan, `Alt + Q` for live audio).
