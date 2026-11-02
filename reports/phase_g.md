# Phase G Report — Full Test Run & Self-Test Verification

**Execution Timestamp:** 2026-11-01 19:11:30 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Test Suite Comparison (Baseline vs Final)

| Metric | Phase B Baseline | Phase G Final | Difference | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Total Tests Discovered** | 359 | **371** | +12 tests | `VERIFIED-AUTOMATED` |
| **Tests Passed** | 356 | **369** | +13 tests | `VERIFIED-AUTOMATED` |
| **Tests Skipped** | 2 | 2 | 0 | `DOC-ONLY` |
| **Tests Failed** | 1 (`test_repeat_launch_stability`) | **0** | -1 (resolved) | `VERIFIED-AUTOMATED` |
| **Execution Duration** | 129.56s | 134.18s | +4.62s | `VERIFIED-AUTOMATED` |

### New Tests Added
1. `tests/test_hardware_lighting.py` (6 tests):
   - `test_frequency_rate_limit_compliance` (<= 3.0 Hz, cycle >= 333ms limit)
   - `test_fake_backend_state_tracking_and_restoration`
   - `test_manager_flashing_sequence_and_count`
   - `test_manager_stop_and_cancel_mid_sequence`
   - `test_lamparray_honest_detection_without_winrt`
   - `test_indicator_backend_capabilities`
2. `tests/test_hardware_brightness.py` (5 tests):
   - `test_safe_minimum_clamp` (5% blackout prevention)
   - `test_discrete_level_snapping`
   - `test_step_adjustment_controls`
   - `test_debounced_slider_updates`
   - `test_windows_brightness_detection_smoke`
3. BYOK and Redaction coverage in `tests/test_byok_providers.py`.

Full test execution log archived at: `reports/final_tests.txt`.

---

## 2. Headless CLI `--self-test` Verification
Added `run_self_test()` in `ghostline/app.py` invoked via `python ghostline/app.py --self-test` (and `--self-test` on packaged binary):
```
============================================================
GHOSTLINE HEADLESS SELF-TEST REPORT
============================================================
[PASS] providers_import: PASS
[PASS] settings_load: PASS
[PASS] dpapi_roundtrip: PASS
[PASS] qt_platform_plugin: PASS
[PASS] hardware_detection: PASS
============================================================
OVERALL RESULT: ALL CHECKS PASSED
============================================================
```
- Status: `VERIFIED-AUTOMATED` (Exit code 0).

---

## 3. Manual Testing Checklist (for Human Inspection)
The following behaviors require human observation on physical hardware:

| Check # | Feature Description | Observation Required | Status Label |
| :--- | :--- | :--- | :--- |
| **M-01** | Start application | Process starts, tray icon appears in system notification area | `NEEDS-USER-CHECK` |
| **M-02** | Open HUD Overlay (`Alt + T`) | Floating frameless HUD displays on top without stealing active focus | `NEEDS-USER-CHECK` |
| **M-03** | Scan MCQ Question (`Alt + /`) | Bounding box captures question stem and options, correct answer displays | `NEEDS-USER-CHECK` |
| **M-04** | Live Audio Assistant (`Alt + A`) | Floating call HUD appears, microphone & system audio transcribed live | `NEEDS-USER-CHECK` |
| **M-05** | BYOK Provider Switch | Switching to Gemini / Groq / OpenAI in Settings successfully routes inference | `NEEDS-USER-CHECK` |
| **M-06** | Hardware Controls Drawer | Clicking 🔆 in HUD expands drawer smoothly with brightness & LED options | `NEEDS-USER-CHECK` |
| **M-07** | Screen Brightness Slider | Moving slider adjusts physical display brightness within safe range | `NEEDS-USER-CHECK` |
| **M-08** | Screen Brightness Step Buttons | Clicking +1 / -1 / +4 / -4 steps brightness up/down by 5% / 20% | `NEEDS-USER-CHECK` |
| **M-09** | Keyboard LED Flash | Clicking "Flash" blinks Caps/Num Lock LED at <= 3 Hz and restores initial state | `NEEDS-USER-CHECK` |
| **M-10** | Stop Mid-Flash | Clicking "Stop" cancels flash sequence immediately and restores lock state | `NEEDS-USER-CHECK` |
| **M-11** | Restart App Persistence | Closing and restarting preserves HUD drawer collapsed state and settings | `NEEDS-USER-CHECK` |

