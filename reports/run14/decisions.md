# Ghostline — Run 14 Architectural & Operational Decisions

## Context & Ground Rules
- Mode: Unattended execution. Pick safest defaults, record them here, and continue.
- Scope: Live transcription speed and amendment (AI answers display).
- Strict Safety:
  - No `reset --hard`, `clean`, `checkout -- .`, `stash drop`.
  - No secrets or keys logged or committed. Never use user's keys.
  - No weakening tests.
  - No driver or unknown binary installs; no UAC/Defender workarounds.
  - Never click Exit/Quit in scripts.
  - Never touch Vercel.
  - No history rewriting; no force-push.

## Decisions Log
- *2026-11-08 (Part 0 — Preflight & Backup)*:
  - Created safety branch: `backup/pre-run14-20261108_132300`.
  - Created full git bundle: `../ghostline_backups/pre_run14.bundle`.
  - Checked out working branch: `run14/stt-speed`.
  - Checked for prior run artifacts: `reports/run12` and `reports/run13` do not exist; continuing with clean Run 14 baseline.
- *2026-11-08 (Stage 1 — STT Speed & CPU Allocation)*:
  - Clamped CPU thread allocation for Whisper to 6 threads on hybrid architectures (Intel i5-13420H with 4 P-cores + 4 E-cores) via `get_optimal_stt_threads()`. Empirical tests proved 6 threads achieves 352ms latency (21.5x real-time), whereas allocating all 12 threads caused 420ms latency due to E-core synchronization thrashing.
  - Implemented background preloading and 1-second silent warmup at startup (`preload_in_background`), reducing cold-start latency from 812ms to 0ms for the user.
  - Bounded dual fair queues (`_mic_queue` and `_call_queue` maxlen=25) with fair alternating scheduling to eliminate loopback blocking mic and vice-versa.
  - Re-tuned VAD segmentation to 0.70s silence pause and added 0.9s–1.2s chunked streaming partials to provide real-time visual feedback while the user is still speaking.
- *2026-11-08 (Stage 2 — Ollama CPU Contention)*:
  - Clamped Ollama inference to `num_thread: 4` and added `keep_alive: "5m"` in `ghostline/core/providers/ollama_provider.py` and `ghostline/core/llm_client.py`. This ensures Ollama does not saturate all CPU cores, leaving dedicated threads for Whisper STT.
- *2026-11-08 (Stage 3 — Live Session UI Architecture & Synchronization)*:
  - Built dedicated `card_live_session` on the Home screen (`QtGhostlineMainWindow`) with transcript, active speaker labels, real-time thinking ticker (`lbl_live_thinking`), live answer stream (`txt_live_answer`), and an error recovery banner with actionable `[Fix]` button.
  - Created unified view-model `LiveSessionViewModel` ensuring that Home screen card and floating HUD overlay share 100% synchronized state without race conditions or thread blocking.
- *2026-11-08 (Stage 4 — Verification & Real Numbers)*:
  - Verified 14 automated unit and integration tests across scenarios S28–S38 in `tests/test_run14_stt_speed_and_answers.py` (all passed).
  - Generated real-window UI captures on Windows with DPR 1.25 saved to `ui_shots/run14` and `reports/run14/captures`.

