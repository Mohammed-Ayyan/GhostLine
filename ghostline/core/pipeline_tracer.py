import os
import sys
import time
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

def get_foreground_window_info() -> Dict[str, Any]:
    """Inspects active foreground window without raising exceptions."""
    info = {"hwnd": 0, "title": "", "class_name": "", "is_fullscreen": False}
    if sys.platform != "win32":
        return info

    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return info

        info["hwnd"] = hwnd

        # Window Title
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        info["title"] = title_buf.value

        # Window Class
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        info["class_name"] = class_buf.value

        # Check if window covers entire screen (fullscreen)
        rect = (ctypes.c_long * 4)()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            left, top, right, bottom = rect[0], rect[1], rect[2], rect[3]
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            if left <= 0 and top <= 0 and right >= sw and bottom >= sh:
                info["is_fullscreen"] = True
    except Exception as e:
        info["error"] = str(e)

    return info


@dataclass
class StageRecord:
    stage: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class PipelineTracer:
    """
    End-to-end diagnostics and tracing engine for Ghostline.
    Tracks each stage:
    Hotkey -> Screen Capture -> OCR -> Question Extraction -> Answer Generation -> Validation -> HUD Update
    """
    def __init__(self):
        self.process_id = os.getpid()
        self.trace_id = f"{int(time.time() * 1000)}"
        self.stages: List[StageRecord] = []
        self.foreground_window: Dict[str, Any] = {}
        self.start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.t_start = time.perf_counter()

    def start_trace(self):
        """Initializes trace with process ID and active foreground window snapshot."""
        self.foreground_window = get_foreground_window_info()
        logging.info("[PipelineTracer] Trace %s started (PID=%d, ActiveWindow='%s' [HWND %s, Fullscreen=%s])",
                     self.trace_id, self.process_id,
                     self.foreground_window.get("title", ""),
                     self.foreground_window.get("hwnd", 0),
                     self.foreground_window.get("is_fullscreen", False))

    def begin_stage(self, stage_name: str, details: Optional[Dict[str, Any]] = None) -> StageRecord:
        rec = StageRecord(
            stage=stage_name,
            start_time=time.perf_counter(),
            details=details or {}
        )
        self.stages.append(rec)
        return rec

    def end_stage(self, rec: StageRecord, success: bool = True, details: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        rec.end_time = time.perf_counter()
        rec.duration_ms = (rec.end_time - rec.start_time) * 1000.0
        rec.success = success
        if details:
            rec.details.update(details)
        if error:
            rec.error = error

        status_str = "SUCCESS" if success else f"FAILED: {error}"
        logging.info("[PipelineTracer %s] Stage '%s' completed in %.1fms [%s]",
                     self.trace_id, rec.stage, rec.duration_ms, status_str)

    def to_dict(self) -> Dict[str, Any]:
        total_dur = (time.perf_counter() - self.t_start) * 1000.0
        return {
            "trace_id": self.trace_id,
            "timestamp": self.start_timestamp,
            "process_id": self.process_id,
            "total_duration_ms": round(total_dur, 2),
            "foreground_window": self.foreground_window,
            "stages": [asdict(s) for s in self.stages],
            "overall_success": all(s.success for s in self.stages) if self.stages else False
        }

    def get_summary_report(self) -> str:
        """Returns clean human-readable diagnostic report for UI or telemetry log."""
        data = self.to_dict()
        fw = data.get("foreground_window", {})
        lines = [
            f"=== Pipeline Trace {data['trace_id']} ===",
            f"Timestamp:       {data['timestamp']}",
            f"Process ID:      {data['process_id']}",
            f"Total Duration:  {data['total_duration_ms']:.1f}ms",
            f"Target Window:   '{fw.get('title', 'Unknown')}' (Class: {fw.get('class_name', '')}, HWND: {fw.get('hwnd', 0)}, Fullscreen: {fw.get('is_fullscreen', False)})",
            "--- Stages ---"
        ]
        for s in data["stages"]:
            status = "✓ OK" if s["success"] else f"✗ FAIL ({s.get('error', 'Unknown')})"
            lines.append(f"  • {s['stage']:<20} {s['duration_ms']:6.1f}ms  [{status}]")
            for k, v in s.get("details", {}).items():
                lines.append(f"      - {k}: {v}")
        return "\n".join(lines)
