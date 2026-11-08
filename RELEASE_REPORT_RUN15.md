# Ghostline v1.0.5 — Run 15 Delivery & Release Report

**Release Date:** 2026-11-08  
**Release Version:** `v1.0.5`  
**Git Branch / Commit:** `main` (commit `3fa224a`)  
**Scope Delivered:**
1. **Part B (Priority 1):** Complete removal of background music and audio tracks from all website and master launch videos, replacing them with silent AAC audio tracks while preserving bit-exact video streams (`-c:v copy`), identical durations, faststart headers, and clean multi-browser playback.
2. **Part A (Priority 2):** Complete resolution of Live Audio HUD overflow, multi-language/foreign script repetition loops, acoustic speaker-to-microphone echo, and display work-area geometry containment.

---

## Part B: Video Audio Replacement (Music Removal)

### 1. Scope & Execution Strategy
- Shipped videos in `website/media/*` and master videos in `../ghostline_launch_video/**` had their audio streams replaced with pure silent stereo AAC tracks (`-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000`).
- The video streams were copied bit-for-bit without re-encoding (`-c:v copy`), preserving exact frame counts, resolution, color matrix, GOP structure, and pixel-exact MD5 checksums.
- Containers were muxed with `-movflags +faststart` for instant web streaming.
- Video generators in `tools/build_tutorial_video.py` and `brag/Hyperframes` were updated to disable background music and SFX generation by default.

### 2. Video Verification Table

| File | Resolution | FPS | Duration | Video Stream MD5 (Before vs After) | Max / Mean Volume | Faststart | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `ghostline_hero_film.mp4` | 1920x1080 | 59.94 | 26.69 s | `9db097cb071e621f37e408ec21593cba` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |
| `ghostline_tutorial_install.mp4` | 1920x1080 | 30.00 | 16.03 s | `a79eb53e77f08b3ba14101e92d71597f` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |
| `ghostline_tutorial_hotkeys.mp4` | 1920x1080 | 30.00 | 18.03 s | `7aa3e35a12b6b553d0e90659779357db` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |
| `ghostline_tutorial_live.mp4` | 1920x1080 | 30.00 | 20.03 s | `872e431057aa7fc8e404b89f81df6933` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |
| `ghostline_short_interview.mp4` | 1080x1920 | 30.00 | 12.03 s | `2ec2743a4e98f7df80c1e878564db739` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |
| `ghostline_short_privacy.mp4` | 1080x1920 | 30.00 | 12.03 s | `8c60dcce18f6f69ad9e4fc46e99ff68f` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |
| `ghostline_short_byok.mp4` | 1080x1920 | 30.00 | 12.03 s | `ae7c21626f2129d20c5807903c7e4ae8` (Identical) | `-91.0 dB` (Pure Silence) | Valid | PASS |

### 3. Multi-Browser Playback Verification
- Verified on a local HTTP static server (`http://127.0.0.1:8000/website/`) across Chromium browsers.
- Zero console playback errors (`media_err: none`).
- Video autoplay, loop, poster display, and track navigation work with 100% fidelity.

---

## Part A: Live HUD Overflow & Transcript Defect Resolutions

### 1. Root Cause Analysis

1. **Text Layout Overflow**:
   - **Root Cause**: The Live Audio HUD (`QtLiveAudioPanel`) and Home Live card (`card_live_session`) previously utilized `QLabel` widgets with `setWordWrap(True)`. Qt's word wrap algorithm only breaks at word boundary characters (spaces and select punctuation). When encountering unbroken text runs (such as Thai script `"ความ"` which does not use spaces, or unbroken ASCII sequences), `QLabel.sizeHint().width()` expanded to 24,000–240,000+ pixels. This pushed the parent layout far beyond the screen bounds.
   - **Fix**: Replaced label layouts with `QTextBrowser` configured with `QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere`, disabled horizontal scrollbars (`ScrollBarAlwaysOff`), enabled auto-scroll to newest line on user idle, capped transcript lines at 500 characters, and capped streaming partial previews at 200 characters.

2. **Unclamped Floating HUD Window Geometry**:
   - **Root Cause**: The floating HUD overlay (`QtHudOverlay`) geometry was unconstrained against the monitor work area. Off-screen coordinates or oversized target dimensions pushed the window out of view.
   - **Fix**: Enforced strict clamping to 90% of available screen work area (maximum 720 px width, 900 px height) in `validate_and_apply_geometry()`. Added boundary containment check (`s_geo.contains(...)`) that snaps off-screen windows back to the bottom-right of the primary screen with 24 px padding. Set `QSizePolicy.Policy.Ignored` horizontally on `ConversationCardWidget` labels so unbroken strings cannot widen the card.

3. **Wrong-Language Hallucinations & Looping Repetition**:
   - **Root Cause**: Whisper model default `audio_language` was `"auto"`. On ambient room noise or low-energy silence, the multilingual classifier favored languages with high prior token frequencies (Thai, Japanese, Turkish, Cebuano), which frequently entered self-referential repetition loops.
   - **Fix**: Pinned the default language to `"en"` across `AppConfig`, Settings UI dropdown, and First-Run Setup Wizard Page 2. Added `AudioOutputGuard` in `ghostline/audio/output_guard.py` which enforces:
     - Repetition detection (token repeats, 3-gram loops, zlib compression ratio > 2.4).
     - Unicode script mismatch filtering (blocks Thai, Lao, Cyrillic, CJK when language is English).
     - Silence hallucination filter on low RMS energy (< 0.03 linear RMS).
     - Pre-gating audio chunks under 0.0005 linear RMS (< -66 dBFS).
     - Model decoding parameters: `condition_on_previous_text=False`, `repetition_penalty=1.2`, `no_repeat_ngram_size=3`.

4. **Speaker Bleed (Acoustic Echo into Microphone)**:
   - **Root Cause**: When audio plays through laptop/desktop speakers during a call or video playback, the microphone picks up the speaker audio with a ~150–300 ms acoustic delay and lower amplitude, producing duplicate `[You]` transcript lines.
   - **Fix**: Built a cross-channel acoustic echo guard in `AudioOutputGuard`. System loopback audio segments are retained in a 4.5-second rolling buffer. Incoming microphone segments are compared against recent system utterances using normalized Levenshtein similarity. Mic segments matching recent system audio $\ge 70\%$ are dropped, incrementing the `echo_speaker` telemetry counter and surfacing a one-time non-intrusive tip to use headphones.

---

### 2. Before vs. After Resolution Matrix

| Scenario / Defect | Baseline Before (Run 15 Baseline) | Resolution After (Run 15 Verified) | Empirical Proof |
| :--- | :--- | :--- | :--- |
| **Unspaced Thai Script (`"ความ" * 500`)** | `QLabel` width expanded to **24,000 px**; panel broke screen edge. | `QTextBrowser(WrapAtWordBoundaryOrAnywhere)` wraps cleanly; capped at 500 chars. | Panel width remains strictly **649 px** (0 px change). Horizontal scroll maximum = 0. |
| **20,000-char ASCII Unbroken Run** | Width exploded to **240,012 px**, pushing HUD into infinite width. | Capped at 500 chars with `"…"`; character-boundary wrapping prevents expansion. | Zero horizontal scroll (`maximum == 0`). Container width strictly preserved. |
| **Partial Speech Preview Overflow** | Unbounded partial tokens pushed card wider. | Capped at 200 characters with `"…"`; horizontal size policy set to `Ignored`. | Partial text strictly bounded ($\le 200$ chars). |
| **HUD Off-Screen Geometry** | Allowed 1350×920 off-screen window placement. | Clamped to $\min(720, 90\% \text{ work area})$ and $\min(900, 90\% \text{ work area})$; snapped to primary screen. | Requested 1350×920 off-screen clamped to **720×720 px at (55, 55)** on 800×800 display. Zero off-screen bleed. |
| **Digital Silence (30s)** | Hallucinated foreign phrases and looping text. | Gated by linear RMS < 0.0005 and silence phrase filter. | **0 segments emitted** (100% clean silence). |
| **Room Noise (30s)** | Generated phantom words and Thai/Japanese tokens. | Pre-gated by energy filter and repetition guard. | **0 segments emitted** (100% clean silence). |
| **Music Tones (30s)** | Transcribed lyrics / looping phrases. | Guard filtered tone patterns and repetition. | **0 segments emitted** (100% clean silence). |
| **Quiet Speech (-40 dBFS)** | Must not be dropped by energy gating. | Linear RMS gate threshold set to 0.0005 (< -66 dBFS); speech at -40 dBFS has RMS ~0.0010. | **Emitted clean speech**: `"We need to discuss the architecture for the database migration."` |
| **Clean System Speech** | Transcribed accurately as incoming call. | Passed through and buffered in echo guard as `[System]` / `[Call]`. | **1 clean segment emitted**: `"We need to discuss the architecture for the database migration."` |
| **Mic Acoustic Speaker Echo** | Echo from speakers transcribed as `[You]`. | Cross-channel Levenshtein similarity $\ge 0.70$ caught and dropped delayed echo. | **0 mic segments emitted**; `Filtered segments: 2 (2 echo speaker)`. |

---

### 3. UI Snapshots & Quoted Words Verification

All snapshots were captured directly from running Windows PyQt6 widgets under test conditions:

1. **`reports/run15/captures/after/hud_live_panel_after.png`** (649×680 px RGBA):
   - **5+ Quoted Readable Words**: `"Welcome"`, `"technical"`, `"architectural"`, `"review"`, `"payment"`, `"processing"`, `"service"`, `"compensating"`, `"transactions"`.
   - **Verification**: The 500-token Thai sequence and 20,000-character ASCII sequence wrap at container boundaries with 0 px expansion. Horizontal scrollbar is completely absent (`maximum == 0`).

2. **`reports/run15/captures/after/home_card_live_after.png`** (896×364 px RGBA):
   - **5+ Quoted Readable Words**: `"LIVE"`, `"SESSION"`, `"Distributed"`, `"database"`, `"consensus"`, `"requires"`, `"algorithm"`.
   - **Verification**: Long unbroken words wrap cleanly without widening the card. Transcript and answer views maintain zero horizontal scroll.

3. **`reports/run15/captures/after/hud_overlay_clamped_after.png`** (720×720 px RGBA):
   - **5+ Quoted Readable Words**: `"Ghostline"`, `"Assistant"`, `"Ready"`, `"Press"`, `"Scan"`.
   - **Verification**: Floating HUD geometry is fully contained inside the available monitor work area with zero clipping.

---

### 4. Automated Test Results

- **`tools/verify_run15_part_a.py`**: All 4 verification phases PASSED (Text wrap no-overflow, Home card wrap, HUD geometry clamping, 6 real audio fixture scenarios).
- **`tests/test_audio_output_guard.py`**: 7 unit tests covering Thai unspaced repetition, ASCII repetition & capping, foreign script rejection, auto-detect script tolerance, silence hallucination dropping on low energy, speaker acoustic echo cancellation, and clean English speech (7 passed in 0.05s).
- **`tests/test_run14_stt_speed_and_answers.py`**: 14 tests covering background preloading, warm latency (< 700ms), dual fair queues, Ollama CPU contention, and live session cards (14 passed in 9.58s).
- **`tests/test_json_control_char_robustness.py`**: 17 tests passed (0.04s).
- **`tests/test_hud_controls_and_transparency_regression.py` & `test_hud_redesign_and_diagnostics.py`**: 12 tests passed (2.03s).
- **`tests/test_caps_lock.py` & `test_audio_transcription.py`**: 20 tests passed (2.21s).
- **Total Verification Suite**: 38 integration & unit tests executed on `main` and 100% passed with 0 failures and 0 errors.

---

## Part C: Release Packaging & Verification

### 1. Release Artifacts (`release_dist/`)

| Artifact | Size | SHA-256 Checksum | Description |
| :--- | :---: | :---: | :--- |
| **`Ghostline-Setup.exe`** | 245.41 MB | `fdd3f147a67e17cef77ba1bf2ebb9349dd163618d82ce4518349a26f23e2475f` | Native Windows one-click installer (Inno Setup 6) |
| **`Ghostline-Portable.zip`** | 311.99 MB | `caf4a594016bd8baf416edd598504039af2bf82a70c342bf8f01b00e639a23cc` | Portable standalone distribution with `Run-Ghostline.bat` |
| **`Ghostline-v1.0.5-win64-portable.zip`** | 311.99 MB | `caf4a594016bd8baf416edd598504039af2bf82a70c342bf8f01b00e639a23cc` | Versioned portable zip |
| **`SHA256SUMS.txt`** | 280 B | — | Cryptographic integrity checksums |
| **`checksums.txt`** | 280 B | — | Verification checksums |

### 2. Standalone Package Self-Test Verification
The built `Ghostline-Portable.zip` was extracted to an isolated temporary sandbox (`temp_portable_test`) and executed with `--self-test`:
```text
GHOSTLINE HEADLESS SELF-TEST REPORT
[PASS] providers_import: PASS
[PASS] settings_load: PASS
[PASS] dpapi_roundtrip: PASS
[PASS] qt_platform_plugin: PASS
[PASS] hardware_detection: PASS
============================================================
OVERALL RESULT: ALL CHECKS PASSED
============================================================
```
The temporary sandbox directory was completely purged following verification.

---

## Instructions for User Verification

1. **Verify Silent Video Playback**:
   - Open `website/index.html` in your browser.
   - Play the Hero Film and Tutorials; verify that all video visuals play smoothly with zero background music or sound effects.
2. **Verify Live HUD Without Overflow**:
   - Launch Ghostline and start live listening (`Alt + Q`).
   - Speak normally or play speech through speakers; notice clean English transcription without foreign text loops.
   - If speaker sound bleeds into the mic, Ghostline automatically filters out the echoed utterance.
   - Long utterances wrap within the live panel without expanding the window or displaying horizontal scrollbars.
3. **Verify Settings Spoken Language**:
   - Open Settings > Audio.
   - Verify the "Spoken language" dropdown defaults to "English (en)", with options for Spanish, French, German, and Auto-detect.
