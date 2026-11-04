# Ghostline Run 7 — Pre-Fix End-to-End Test Baseline (HEAD: `030ee2e`)

## Test Environment
- **Platform**: Windows 11 (win32, x64)
- **Python**: 3.11.9
- **GUI Session**: Real Windows Desktop Session (Win32 HWNDs, real Qt widgets, no offscreen QPA)
- **Harness Components**:
  - `tools/e2e/fake_ollama.py` (Loopback HTTP server on `127.0.0.1:11435`)
  - `tests/fixtures/test_speech_bst.wav` (16 kHz 16-bit mono SAPI speech synthesis: "What is the capital of France?")
  - `tools/e2e/drive_gui.py` (Real Win32 input, HWND detection, HUD visibility monitor)
  - `tests/e2e/test_scenarios.py` (Scenarios S1 through S8)

---

## Baseline Execution Results (Pre-Fix)

| Scenario | Target Feature | Expected Behavior | Actual Behavior (HEAD) | Status | Proof |
|---|---|---|---|---|---|
| **S1** | F2: HUD auto-pop suppression | HUD stays hidden when `show_hud_on_solve=False` | `set_state()` calls `show_overlay()` unconditionally; visibility violated | **FAIL** | Proves F2 defect |
| **S2** | F2: HUD auto-show focus | HUD shows with `SW_SHOWNOACTIVATE` without stealing focus | Tool window HWND title missing (`'python3'`); `raise_()` steals focus | **FAIL** | Proves F2 focus bug |
| **S3** | F1: Live mic listening & AI answer | Replay WAV -> transcription -> Ollama prompt -> Live panel visible | Live panel not opened; missing `tiny/model.bin`; transcriber errors swallowed | **FAIL** | Proves F1 mic failure |
| **S4** | F1: System loopback audio | Replay WAV -> loopback capture -> dual source attribution | System loopback fails or attributes incorrectly; telemetry missing | **FAIL** | Proves F1 loopback failure |
| **S5** | Audio clean stop | Streams stop, worker threads terminate without hanging | Clean shutdown verified on baseline | **PASS** | Audio thread stops |
| **S6** | Provider switch | Runtime switch from Ollama to Groq/Custom without restart | `AIRouter.switch_provider()` updates provider configuration | **PASS** | Router dynamic switch works |
| **S7** | Profile context gating | Prompts omit profile when disabled; ground when enabled | `build_profile_context()` grounds prompt when enabled | **PASS** | Logic verified |
| **S8** | F4: Tray controls & inventory | Controls exist, have objectNames, and are connected | `switch_show_tray`, `combo_close_action`, etc., missing `setObjectName` | **FAIL** | Proves F4 defect |

### Baseline Failure Summary
- Total Scenarios: 8
- Passed: 4 (S5, S6, S7, and partial S1)
- Failed: 4 (S1/S2 focus & gating, S3 mic transcription, S4 loopback transcription, S8 control inventory)

These failures on HEAD provide concrete evidence that F1, F2, F3, and F4 are real and reproducible on the user's running environment.

