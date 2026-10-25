import time
import math
import hashlib
import logging
import threading
from typing import Optional, Callable, List, Tuple, Dict
from collections import OrderedDict

from .capture import get_cursor_position


class HoverQuestionCache:
    """
    LRU cache storing recent question fingerprints with Time-To-Live (TTL).
    Prevents repeated inference triggers on unchanged questions when mouse hovers nearby.
    """
    def __init__(self, max_size: int = 50, ttl_sec: float = 90.0):
        self.max_size = max_size
        self.ttl_sec = ttl_sec
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def compute_fingerprint(text: str) -> str:
        """Generates normalized alphanumeric SHA256 hash of question text."""
        normalized = "".join(c.lower() for c in text if c.isalnum())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def contains(self, text: str) -> bool:
        """Returns True if the normalized question was recently seen within TTL."""
        fp = self.compute_fingerprint(text)
        now = time.time()
        with self._lock:
            if fp in self._cache:
                timestamp = self._cache[fp]
                if now - timestamp < self.ttl_sec:
                    return True
                else:
                    del self._cache[fp]
            return False

    def add(self, text: str):
        """Adds question fingerprint with current timestamp."""
        fp = self.compute_fingerprint(text)
        now = time.time()
        with self._lock:
            if fp in self._cache:
                del self._cache[fp]
            elif len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[fp] = now

    def clear(self):
        with self._lock:
            self._cache.clear()


class HoverDetector:
    """
    Automatic hover-to-answer background engine.
    Monitors cursor stability and triggers question detection when stationary,
    with debounce, cooldown, window exclusions, and duplicate question filtering.
    """
    def __init__(
        self,
        on_trigger: Callable[[], None],
        is_solving_fn: Optional[Callable[[], bool]] = None,
        get_excluded_rects: Optional[Callable[[], List[Tuple[int, int, int, int]]]] = None,
        enabled: bool = False,
        hover_delay_ms: int = 800,
        cooldown_sec: float = 3.0,
        movement_threshold_px: int = 15,
        is_paused: bool = False
    ):
        self.on_trigger = on_trigger
        self.is_solving_fn = is_solving_fn or (lambda: False)
        self.get_excluded_rects = get_excluded_rects or (lambda: [])
        
        self.enabled = enabled
        self.hover_delay_sec = max(0.2, hover_delay_ms / 1000.0)
        self.cooldown_sec = max(0.5, cooldown_sec)
        self.movement_threshold_px = max(5, movement_threshold_px)
        self.is_paused = is_paused

        self.question_cache = HoverQuestionCache(max_size=50, ttl_sec=90.0)

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Tracking state
        self._anchor_pos: Optional[Tuple[int, int]] = None
        self._stationary_start: Optional[float] = None
        self._has_triggered_for_current_hover = False
        self._last_trigger_time: float = 0.0

    def start(self):
        """Starts the background cursor monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="HoverDetectorThread")
            self._thread.start()
            logging.info("[HoverDetector] Background hover monitoring started (enabled=%s, delay=%.1fs, cooldown=%.1fs)",
                         self.enabled, self.hover_delay_sec, self.cooldown_sec)

    def stop(self):
        """Stops the monitoring thread."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
            self._thread = None
        logging.info("[HoverDetector] Background hover monitoring stopped.")

    def pause(self):
        """Temporarily pauses automatic hover detection."""
        self.is_paused = True
        logging.info("[HoverDetector] Automatic hover detection PAUSED.")

    def resume(self):
        """Resumes automatic hover detection."""
        self.is_paused = False
        self._reset_hover_state()
        logging.info("[HoverDetector] Automatic hover detection RESUMED.")

    def toggle_pause(self) -> bool:
        """Toggles pause/resume state and returns new paused state."""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
        return self.is_paused

    def update_config(
        self,
        enabled: Optional[bool] = None,
        hover_delay_ms: Optional[int] = None,
        cooldown_sec: Optional[float] = None,
        movement_threshold_px: Optional[int] = None
    ):
        """Updates detector settings dynamically at runtime."""
        with self._lock:
            if enabled is not None:
                self.enabled = enabled
            if hover_delay_ms is not None:
                self.hover_delay_sec = max(0.2, hover_delay_ms / 1000.0)
            if cooldown_sec is not None:
                self.cooldown_sec = max(0.5, cooldown_sec)
            if movement_threshold_px is not None:
                self.movement_threshold_px = max(5, movement_threshold_px)
        logging.info("[HoverDetector] Settings updated: enabled=%s, delay=%.2fs, cooldown=%.1fs",
                     self.enabled, self.hover_delay_sec, self.cooldown_sec)

    def notify_solve_completed(self):
        """Called when a solve finishes to set the cooldown timer."""
        self._last_trigger_time = time.time()
        self._has_triggered_for_current_hover = True

    def _reset_hover_state(self):
        self._anchor_pos = None
        self._stationary_start = None
        self._has_triggered_for_current_hover = False

    def is_cursor_in_excluded_area(self, cx: int, cy: int) -> bool:
        """Checks if the mouse cursor is located inside any excluded window (e.g. HUD or Main Window)."""
        try:
            excluded_rects = self.get_excluded_rects()
            for rect in excluded_rects:
                if not rect:
                    continue
                left, top, right, bottom = rect
                # Add 4px margin around window bounds
                if (left - 4) <= cx <= (right + 4) and (top - 4) <= cy <= (bottom + 4):
                    return True
        except Exception:
            pass
        return False

    def _monitor_loop(self):
        """Main sampling loop running at 20Hz (every 50ms)."""
        while self._running:
            time.sleep(0.05)

            if not self.enabled or self.is_paused:
                self._reset_hover_state()
                continue

            # Don't start hover tracking while a solve is already running
            if self.is_solving_fn():
                self._reset_hover_state()
                continue

            now = time.time()

            # Respect post-solve cooldown
            if (now - self._last_trigger_time) < self.cooldown_sec:
                continue

            cx, cy = get_cursor_position()

            # Never trigger if cursor is inside the HUD itself or application windows
            if self.is_cursor_in_excluded_area(cx, cy):
                self._reset_hover_state()
                continue

            if self._anchor_pos is None:
                self._anchor_pos = (cx, cy)
                self._stationary_start = now
                self._has_triggered_for_current_hover = False
                continue

            # Calculate displacement from anchor
            ax, ay = self._anchor_pos
            distance = math.hypot(cx - ax, cy - ay)

            if distance <= self.movement_threshold_px:
                # Cursor remained stationary within threshold
                if not self._has_triggered_for_current_hover and self._stationary_start is not None:
                    elapsed = now - self._stationary_start
                    if elapsed >= self.hover_delay_sec:
                        # Conditions met: trigger automatic solve!
                        logging.info("[HoverDetector] Stationary hover threshold reached (%.2fs at %d, %d). Triggering solve.",
                                     elapsed, cx, cy)
                        self._has_triggered_for_current_hover = True
                        self._last_trigger_time = now
                        try:
                            self.on_trigger()
                        except Exception as e:
                            logging.exception("[HoverDetector] Error invoking hover trigger callback: %s", e)
            else:
                # Mouse moved beyond threshold: reset anchor to current position
                self._anchor_pos = (cx, cy)
                self._stationary_start = now
                self._has_triggered_for_current_hover = False
