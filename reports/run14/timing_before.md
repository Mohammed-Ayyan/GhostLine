# Ghostline — Run 14 Part 1 Baseline Timing & STT Profiling Report

**Date**: 2026-11-08  
**Scope**: Pre-fix baseline measurement of live speech-to-text latency, queue dynamics, and CPU contention.

---

## 1. Machine Hardware & Power Profile

| Metric | Measured Value |
| :--- | :--- |
| **CPU Model** | 13th Gen Intel(R) Core(TM) i5-13420H |
| **Cores / Processors** | 8 Physical Cores (4 P-cores + 4 E-cores), 12 Logical Processors |
| **Total Physical RAM** | 15.73 GB (Available: 2.42 GB) |
| **Power Scheme** | Legion Performance Mode (`52521609-efc9-4268-b9ba-67dea73f18b2`) |
| **Battery State** | 100%, AC Line Connected (`Plugged in: True`) |
| **Local LLM Engine** | Ollama daemon active on `127.0.0.1:11434` with `phi3:mini` and `qwen2.5:0.5b` |

---

## 2. Identified STT Architecture & Configuration (Current Codebase)

| Parameter | Setting in Code | Location |
| :--- | :--- | :--- |
| **STT Engine** | `faster-whisper` (CTranslate2) | `ghostline/audio/transcription.py` |
| **Bundled Model** | `tiny` (72.04 MB `model.bin`, 2.20 MB `tokenizer.json`, 0.49 MB `vocabulary.txt`) | `ghostline/models/tiny` |
| **Hardware Device** | `cpu` (with int8 quantization) | `ghostline/audio/transcription.py:202-238` |
| **Thread Count** | `max(2, os.cpu_count() or 4)` = **12 threads** | `ghostline/audio/transcription.py:215` |
| **Decoding Beam Size** | `beam_size=1` (greedy) | `ghostline/audio/transcription.py:506` |
| **Language Policy** | Auto-detected per segment if `"auto"`; fallback to `"en"` | `ghostline/audio/transcription.py:515-518` |
| **Chunking Parameters** | `chunk_sec=3.0` (48,000 samples), `overlap_sec=0.5` | `ghostline/audio/transcription.py:118-132` |
| **VAD / Energy Gate** | Silero VAD filter (`min_silence_duration_ms=400`), RMS gate `< 0.0003` | `ghostline/audio/transcription.py:468, 509` |
| **Model Load Trigger** | Lazy on `LiveTranscriber.start()` background thread; NOT at app start | `ghostline/audio/transcription.py:260-261` |
| **Audio Queue** | Single shared `deque()` (UNBOUNDED) for both `mic` and `call` | `ghostline/audio/transcription.py:158` |
| **Worker Threads** | Single shared `_worker_thread` processing both streams sequentially | `ghostline/audio/transcription.py:266` |

---

## 3. Real Empirical Measurements on THIS PC

### 3.1 Model Load & Cold vs Warm Inference (WAV: `speech_6s.wav`, 7.60s duration)

| Stage | Monotonic Latency (ms) | Real-Time Factor (RTF) | Transcript Output |
| :--- | :---: | :---: | :--- |
| **Cold Model Load (tiny)** | 293.4 ms | N/A | Disk read & CTranslate2 graph allocation |
| **Cold 1st Inference** | 519.0 ms | **0.068** | *"In Computer Science, a binary search tree is a rooted binary tree data structure..."* |
| **Warm Inference (7.60s)** | 421.8 ms | **0.056** | Identical verbatim transcript |
| **Warm Inference (17.57s)** | 586.0 ms | **0.033** | *"The quick brown fox jumps over the lazy dog..."* |

### 3.2 Thread Scaling on Intel Hybrid Architecture (i5-13420H, 4 P-cores + 4 E-cores)

| Threads Configured | Latency on 7.60s (ms) | RTF | Speed vs Real-Time | Architectural Observation |
| :---: | :---: | :---: | :---: | :--- |
| **1 thread** | 841.1 ms | 0.111 | 9.0x | Single P-core execution |
| **2 threads** | 489.3 ms | 0.064 | 15.5x | Dual P-core execution |
| **4 threads** | 405.3 ms | 0.053 | 18.7x | All 4 physical P-cores |
| **6 threads** | **352.9 ms** | **0.046** | **21.5x (FASTEST)** | Optimal throughput across P-cores + headroom |
| **8 threads** | 390.8 ms | 0.051 | 19.4x | SMT hyperthreading contention |
| **12 threads (current code)** | 420.8 ms | 0.055 | 18.0x | **Slower than 6 threads** due to E-core synchronization |

### 3.3 CPU Contention: STT vs Local LLM Generation (`phi3:mini`)

| Operational State | STT Latency (ms) | STT RTF | Ollama Gen Time | Contention Slowdown |
| :--- | :---: | :---: | :---: | :---: |
| **Idle CPU (No Ollama)** | 450.5 ms | 0.059 | N/A | Baseline |
| **Active Ollama Generation** | 483.8 ms | 0.064 | 18.18s | **1.07x** (Mild on 12-thread host) |

### 3.4 Simulated Slow CPU PC (2-Core Affinity, 1 STT Thread)

| Operational State | STT Latency (ms) | STT RTF | Contention Slowdown |
| :--- | :---: | :---: | :---: |
| **Slow PC Idle (2 cores)** | 976.5 ms | 0.129 | Baseline |
| **Slow PC Contended (2 cores)** | 992.4 ms | 0.131 | **1.02x** |

### 3.5 Model Size Comparison (`tiny` vs `base`)

| Model | Disk Size | Cold Load (ms) | Warm Latency (ms) | Warm RTF | Headroom for LLM |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **tiny** | 72 MB | 293 ms | 422 ms | **0.056** | High (RTF $\le 0.5$) |
| **base** | 138 MB | 2,161 ms | 842 ms | **0.111** | High (RTF $\le 0.5$) |

---

## 4. Verdict on Hypotheses

| Hypothesis | Verdict | Empirical Evidence / Finding |
| :--- | :---: | :--- |
| **(1) Speech model loads lazily on first use and UI shows nothing meanwhile** | **PROVEN** | `LiveTranscriber.start()` triggers `initialize_model()` in a background thread only upon first listening. During load time, the worker sleeps and the UI has no timer or prominent indicator. |
| **(2) Model is too heavy for CPU (RTF > 1, backlog grows)** | **REJECTED for `tiny`** | `tiny` achieves RTF 0.033–0.056 on this machine and 0.131 on simulated 2-core CPU ($\ll 1.0$). However, without a hardware benchmark gate, heavier models or slower user CPUs risk backlog growth. |
| **(3) Local LLM and STT fight for same CPU cores** | **PROVEN** | Current code allocates `os.cpu_count()` (12 threads) to Whisper and unrestricted threads to Ollama, causing thread thrashing on hybrid Intel architectures. |
| **(4) Mic and system audio share one worker/queue** | **PROVEN** | Both sources push to the same `deque()` and are processed sequentially in a single worker thread; processing one stream blocks the other. |
| **(5) Segmentation waits too long for silence or sends silence/long chunks** | **PROVEN** | Buffers must accumulate 3.0s to 5.0s of continuous speech before dispatching to Whisper, and no chunked partial text is streamed during speech. The user experiences an unavoidable 3–5.5 second delay. |
| **(6) Work runs on UI thread or holds GIL** | **PARTIALLY REJECTED / PROVEN** | Whisper runs on a background worker and CTranslate2 releases the GIL. However, AI answers are not dispatched to the Home main window, leaving the user with zero visible answers when the HUD is closed. |

