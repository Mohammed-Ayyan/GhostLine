"""
Ghostline Audio Timing Instrumentation & Metrics Module.
Tracks monotonic timestamps, latency, Real-Time Factor (RTF), and model initialization.
Outputs clean, privacy-safe diagnostics lines suitable for Help > Diagnostics.
Strictly metrics only: NEVER logs or prints spoken audio content or secret credentials.
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional


class TimingManager:
    """Singleton tracking monotonic timestamps and STT performance metrics."""
    _instance: Optional["TimingManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.lock = threading.Lock()
        self.marks: Dict[str, float] = {}
        self.recent_segments: List[Dict[str, Any]] = []
        self.model_load_time_ms: float = 0.0
        self.engine_name: str = "faster-whisper"
        self.model_name: str = "tiny"
        self.compute_type: str = "int8"
        self.thread_count: int = 4
        self.log_file: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "TimingManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def set_model_info(self, engine: str, model: str, compute: str, threads: int, load_ms: float):
        with self.lock:
            self.engine_name = engine
            self.model_name = model
            self.compute_type = compute
            self.thread_count = threads
            self.model_load_time_ms = load_ms

    def record_mark(self, mark_name: str, details: Any = ""):
        """Records a monotonic timestamp mark."""
        mono_ms = time.monotonic() * 1000.0
        details_str = str(details) if not isinstance(details, str) else details
        with self.lock:
            self.marks[mark_name] = mono_ms
            log_p = self.log_file or os.environ.get("GHOSTLINE_E2E_LOG")
            if log_p:
                try:
                    with open(log_p, "a", encoding="utf-8") as f:
                        f.write(f"TIMING_MARK: mark={mark_name} monotonic_ms={mono_ms:.2f} details={details_str}\n")
                except Exception:
                    pass

    def record_segment_metric(
        self,
        first_arg: Any = 0.0,
        dur_sec: float = 0.0,
        latency_ms: Optional[float] = None,
        **kwargs
    ):
        """
        Records finalized segment transcription completion for Diagnostics.
        Accepts:
          - (speech_end_ms, dur_sec)
          - (source_str, dur_sec, latency_ms)
          - keyword arguments: dur_sec=..., latency_ms=...
        """
        now_ms = time.monotonic() * 1000.0

        if latency_ms is not None:
            lat = float(latency_ms)
        elif isinstance(first_arg, (int, float)) and first_arg > 0:
            lat = max(0.0, now_ms - float(first_arg))
        else:
            lat = float(kwargs.get("latency_ms", 0.0))

        dur = float(dur_sec) if dur_sec > 0 else float(kwargs.get("dur_sec", 0.0))
        rtf = (lat / 1000.0) / max(0.01, dur) if dur > 0 else 0.0

        with self.lock:
            self.recent_segments.append({
                "completed_ms": now_ms,
                "dur_sec": dur,
                "latency_ms": lat,
                "rtf": rtf
            })
            # Keep bounded history
            if len(self.recent_segments) > 50:
                self.recent_segments.pop(0)

            log_p = self.log_file or os.environ.get("GHOSTLINE_E2E_LOG")
            if log_p:
                try:
                    with open(log_p, "a", encoding="utf-8") as f:
                        f.write(f"TIMING_METRIC: speech_end_to_transcript_ms={lat:.1f} rtf={rtf:.3f} dur={dur:.2f}s\n")
                except Exception:
                    pass

    def get_diagnostics_line(self) -> str:
        """
        Formats a clean, privacy-safe line for Help > Diagnostics and Copy-diagnostics.
        Strictly numbers only; never contains transcript text.
        """
        with self.lock:
            count = len(self.recent_segments)
            if count == 0:
                recent_info = "No segments yet"
            else:
                latencies = [s["latency_ms"] for s in self.recent_segments]
                rtfs = [s["rtf"] for s in self.recent_segments]
                avg_lat = sum(latencies) / count
                min_lat = min(latencies)
                max_lat = max(latencies)
                avg_rtf = sum(rtfs) / count
                recent_info = f"Last {count} segments: latency {avg_lat:.0f}ms (min {min_lat:.0f}ms, max {max_lat:.0f}ms), avg RTF {avg_rtf:.3f}"

            return (
                f"STT: {self.engine_name} [{self.model_name}] | {self.compute_type} | "
                f"{self.thread_count} threads | load: {self.model_load_time_ms:.0f}ms | {recent_info}"
            )


def record_timing_mark(mark_name: str, details: Any = ""):
    """Global helper for recording timing marks."""
    TimingManager.get_instance().record_mark(mark_name, details)


def record_segment_metric(first_arg: Any = 0.0, dur_sec: float = 0.0, latency_ms: Optional[float] = None, **kwargs):
    """Global helper for recording segment latency and RTF."""
    TimingManager.get_instance().record_segment_metric(first_arg, dur_sec, latency_ms, **kwargs)


def get_stt_diagnostics_line() -> str:
    """Global helper for retrieving STT diagnostics line."""
    return TimingManager.get_instance().get_diagnostics_line()
