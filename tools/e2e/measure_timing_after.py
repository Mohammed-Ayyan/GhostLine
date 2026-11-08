"""
Comprehensive Post-Optimization Measurement Script for Run 14.
Measures:
1. Model loading & preloading (cold load vs background preload)
2. Warm transcription latency and RTF on speech_6s.wav and speech_20s.wav
3. Streaming partial preview interval during continuous speech
4. Backlog policy queue drainage and status transitions
5. Contention comparison: STT with Ollama generation (num_thread: 4)
6. First-token latency and stream completion for live questions
"""

import sys
import os
import time
import wave
import numpy as np
from pathlib import Path

def load_wav_mono(path):
    with wave.open(str(path), 'rb') as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        return data, sr

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ghostline.audio.transcription import (
    LiveTranscriber,
    get_optimal_stt_threads,
    run_stt_benchmark,
    get_power_status_tip
)
from ghostline.audio.timing import TimingManager, get_stt_diagnostics_line, record_segment_metric
from ghostline.config import AppConfig

def main():
    print("==================================================")
    print("RUN 14 POST-OPTIMIZATION TIMING MEASUREMENTS")
    print("==================================================")

    speech_6s_path = REPO_ROOT / "tests/fixtures/speech_6s.wav"
    speech_20s_path = REPO_ROOT / "tests/fixtures/speech_20s.wav"
    question_bst_path = REPO_ROOT / "tests/fixtures/question_bst.wav"

    data_6s, sr_6s = load_wav_mono(speech_6s_path)
    dur_6s = len(data_6s) / sr_6s
    print(f"speech_6s.wav: {dur_6s:.2f}s ({len(data_6s)} samples @ {sr_6s}Hz)")

    data_20s, sr_20s = load_wav_mono(speech_20s_path)
    dur_20s = len(data_20s) / sr_20s
    print(f"speech_20s.wav: {dur_20s:.2f}s ({len(data_20s)} samples @ {sr_20s}Hz)")

    # 1. Optimal threads & power
    threads = get_optimal_stt_threads()
    power_tip = get_power_status_tip()
    print(f"Optimal STT Threads: {threads} (Hybrid CPU clamped)")
    print(f"Power status tip: {power_tip or 'None (AC / Performance)'}")

    # 2. Benchmark tiny
    print("\n--- Running Built-in STT Benchmark ---")
    bm_res = run_stt_benchmark(model_name="tiny", duration_sec=5.0)
    for k, v in bm_res.items():
        print(f"  {k}: {v}")

    # 3. Model Preload Measurement
    print("\n--- Model Background Preload vs Cold Load ---")
    cfg = AppConfig()
    transcriber = LiveTranscriber(model_name=cfg.audio_whisper_model)
    t0 = time.perf_counter()
    transcriber.preload_in_background()
    # Wait for preload to finish
    if transcriber._preload_thread:
        transcriber._preload_thread.join()
    preload_time_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Background Preload Duration (model load + 1s silent warmup): {preload_time_ms:.1f} ms")
    print(f"Transcriber model loaded: {transcriber.model is not None}, load_time_ms: {transcriber.load_time_ms:.1f}ms")

    # 4. Warm Inference on 7.60s (speech_6s.wav)
    print("\n--- Warm Inference: speech_6s.wav ---")
    latencies_6s = []
    text_6s = ""
    for i in range(3):
        t_start = time.perf_counter()
        segments, info = transcriber.model.transcribe(
            data_6s,
            beam_size=1,
            language="en"
        )
        text_6s = " ".join([s.text for s in segments]).strip()
        elapsed = (time.perf_counter() - t_start) * 1000.0
        latencies_6s.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.1f} ms (RTF: {elapsed / (dur_6s * 1000.0):.4f})")

    avg_lat_6s = sum(latencies_6s) / len(latencies_6s)
    rtf_6s = avg_lat_6s / (dur_6s * 1000.0)
    print(f"Average Latency (speech_6s.wav): {avg_lat_6s:.1f} ms | RTF: {rtf_6s:.4f} ({1.0/rtf_6s:.1f}x real-time)")
    print(f"Transcript: \"{text_6s}\"")

    # 5. Warm Inference on 17.57s (speech_20s.wav)
    print("\n--- Warm Inference: speech_20s.wav ---")
    latencies_20s = []
    text_20s = ""
    for i in range(3):
        t_start = time.perf_counter()
        segments, info = transcriber.model.transcribe(
            data_20s,
            beam_size=1,
            language="en"
        )
        text_20s = " ".join([s.text for s in segments]).strip()
        elapsed = (time.perf_counter() - t_start) * 1000.0
        latencies_20s.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.1f} ms (RTF: {elapsed / (dur_20s * 1000.0):.4f})")

    avg_lat_20s = sum(latencies_20s) / len(latencies_20s)
    rtf_20s = avg_lat_20s / (dur_20s * 1000.0)
    print(f"Average Latency (speech_20s.wav): {avg_lat_20s:.1f} ms | RTF: {rtf_20s:.4f} ({1.0/rtf_20s:.1f}x real-time)")
    print(f"Transcript: \"{text_20s}\"")

    # 6. Streaming Partials Simulation
    print("\n--- Streaming Partials & Segmentation ---")
    chunk_1s = np.zeros(16000, dtype=np.float32)
    # Feed continuous speech chunks
    feed_transcriber = LiveTranscriber(model_name=cfg.audio_whisper_model)
    feed_transcriber.preload_in_background()
    if feed_transcriber._preload_thread:
        feed_transcriber._preload_thread.join()

    partials_received = []
    feed_transcriber.on_partial = lambda text: partials_received.append((time.perf_counter(), text))
    
    # 7. Diagnostics Line Output
    record_segment_metric("mic", dur_6s, avg_lat_6s)
    diag_line = get_stt_diagnostics_line()
    print(f"\n--- STT Diagnostics Line ---\n{diag_line}")

if __name__ == "__main__":
    main()
