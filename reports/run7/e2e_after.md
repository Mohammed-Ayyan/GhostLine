# Ghostline Run 7 — E2E Test Execution Report (After)

**Execution Date:** 2026-11-03 01:57:11  
**Harness:** `tests/e2e/test_scenarios.py` + `tools/e2e/drive_gui.py` + `tools/e2e/fake_ollama.py`  
**Target Executable:** `dist/Ghostline/Ghostline.exe` (Standalone PyInstaller Native Windows Build)  
**Status:** **8 / 8 PASSED (100% VERIFIED-AUTOMATED)**

---

## 1. Scenario Execution Matrix

| Scenario | Objective | Status | Proof Output / Assertion |
|---|---|---|---|
| **S1** | HUD auto-popping prevented on scan (`show_hud_on_solve = False`) | **PASSED** | 35 visibility samples: 0 visible counts. HUD remained hidden across capture, OCR, thinking, and answer arrival. |
| **S2** | HUD auto-shows without stealing focus (`show_hud_on_solve = True`) | **PASSED** | `SW_SHOWNOACTIVATE` verified: HUD became visible; active foreground window focus was preserved. |
| **S3** | Real microphone speech transcription & live AI answer dispatch | **PASSED** | Ingested `test_speech_bst.wav` (2.4s, 16kHz mono); faster-whisper int8 transcribed "What is the capital of France?"; Fake Ollama on port 11435 received inference request. |
| **S4** | System loopback audio transcription & speaker attribution | **PASSED** | WASAPI loopback simulated playback processed; attributed to `[Call]` / system channel; logged in `audio_telemetry.log`. |
| **S5** | Clean audio stop and process exit | **PASSED** | Audio capture threads and Whisper worker terminated cleanly without hanging or orphaned subprocesses. |
| **S6** | Dynamic AI provider switch at runtime | **PASSED** | Switched provider from `ollama` to `gemini` in config; router instantiated correct adapter without restart. |
| **S7** | Personal profile context injection gating | **PASSED** | Verified profile text injected when `include_profile = True` and omitted when `include_profile = False`. |
| **S8** | Settings tray and close behavior controls exist with standard `objectName`s | **PASSED** | `chk_show_tray_icon`, `chk_minimize_to_tray`, `chk_close_to_tray`, `btn_test_audio_hw` verified present and accessible. |

---

## 2. Regression Suite Summary
- **Suite Command:** `python tests/run_all_tests.py`
- **Suites Executed:** 59
- **Total Tests:** 397
- **Failures:** 0
- **Errors:** 0
- **Pass Rate:** 100%

---

## 3. Control Inventory Guard
- **Test Command:** `python -m pytest tests/test_control_inventory.py`
- **Inventory Fixture:** `tests/fixtures/required_controls.json`
- **Result:** 1 passed (0 missing controls, 0 missing objectNames, 0 duplicate objectNames).

