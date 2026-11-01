"""
Ghostline Audio Pipeline Telemetry & Counter Logger
Maintains thread-safe counters and logs every stage of the live audio pipeline
to %APPDATA%\\Ghostline\\logs\\audio_pipeline.log.
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from ghostline.config import get_app_dir


class AudioPipelineTelemetry:
    _instance: Optional["AudioPipelineTelemetry"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.lock = threading.Lock()
        self.log_file = get_app_dir() / "logs" / "audio_pipeline.log"
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self.counters = {
            "device_open": 0,
            "pcm_frames_received": 0,
            "rms_above_threshold": 0,
            "resample_16k_mono": 0,
            "transcriber_queue_pushed": 0,
            "transcriber_thread_alive": 0,
            "whisper_model_loaded": 0,
            "transcribe_called": 0,
            "segments_returned": 0,
            "non_empty_text": 0,
            "on_segment_callback_fired": 0,
            "signal_emitted": 0,
            "main_thread_slot_called": 0,
            "widget_updated_visible": 0,
            "worker_exceptions": 0,
            "quick_ask_triggered": 0,
            "quick_ask_empty": 0,
            "quick_ask_answered": 0,
        }

    @classmethod
    def get_instance(cls) -> "AudioPipelineTelemetry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = AudioPipelineTelemetry()
            return cls._instance

    def record_stage(self, stage: str, details: str = "", count_increment: int = 1):
        """Thread-safely increments stage counter and appends telemetry log line."""
        with self.lock:
            if stage in self.counters:
                self.counters[stage] += count_increment

            cnt = self.counters.get(stage, 0)
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{now_str}] [COUNTER {stage}={cnt}] {details}\n"

            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass

    def record_device_open(self, name: str, rate: int = 0, ch: int = 0, *args, **kwargs):
        self.record_stage("device_open", f"Opened audio device '{name}' ({rate} Hz, {ch} ch)")

    def record_pcm_frame(self, *args, **kwargs):
        count = args[-1] if args else 1
        self.record_stage("pcm_frames_received", f"Received {count} PCM frames")

    def record_speech_rms(self, *args, **kwargs):
        rms = float(args[-1]) if args else 0.0
        self.record_stage("rms_above_threshold", f"Speech energy detected: RMS={rms:.4f}")

    def record_resample(self, *args, **kwargs):
        self.record_stage("resample_16k_mono", f"Resampled audio frame {args}")

    def record_queue_push(self, count: int = 1):
        self.record_stage("transcriber_queue_pushed", f"Pushed {count} chunks to transcriber queue")

    def record_transcribe_call(self, buf_len: int):
        self.record_stage("transcribe_called", f"Whisper transcribe() invoked on {buf_len} samples")

    def record_segment_returned(self, seg_count: int, text: str):
        self.record_stage("segments_returned", f"Whisper returned {seg_count} segments: '{text[:60]}'")
        if text.strip():
            self.record_stage("non_empty_text", f"Non-empty text: '{text[:60]}'")

    def record_slot_update(self, text: str):
        self.record_stage("main_thread_slot_called", f"Main thread slot updated with: '{text[:60]}'")
        self.record_stage("widget_updated_visible", f"Widget updated visible: '{text[:60]}'")

    def get_counters(self) -> Dict[str, int]:
        with self.lock:
            return dict(self.counters)

    def format_summary(self) -> str:
        with self.lock:
            lines = [f"{k}: {v}" for k, v in self.counters.items()]
            return " | ".join(lines)


def get_audio_telemetry() -> AudioPipelineTelemetry:
    return AudioPipelineTelemetry.get_instance()
