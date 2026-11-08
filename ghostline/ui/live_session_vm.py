"""
Ghostline Live Session View-Model.
Single source of truth for real-time speech transcription, partial text,
streaming AI responses, elapsed thinking timers, and state-aware error handling.
Synchronizes the Home window Live card and the floating HUD overlay.
"""

import time
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

from ghostline.audio.transcription import TranscriptSegment

logger = logging.getLogger("ghostline.live_session_vm")


class LiveSessionViewModel:
    """Central observable view-model for live audio and AI assistant states."""
    _instance: Optional["LiveSessionViewModel"] = None

    def __init__(self):
        self.session_id: str = ""
        self.is_capturing: bool = False
        self.is_paused: bool = False
        self.engine_status: str = "Ready"
        self.latency_ms: float = 0.0
        
        # Transcript turns and in-flight streaming partial text
        self.segments: List[TranscriptSegment] = []
        self.partial_text: Dict[str, str] = {"mic": "", "call": ""}

        # AI Answer generation state
        self.current_question: str = ""
        self.is_thinking: bool = False
        self.thinking_start_time: float = 0.0
        self.streamed_tokens: str = ""
        self.completed_answer: str = ""
        self.code_snippet: Optional[str] = None
        self.error_message: str = ""
        self.fix_label: str = ""
        self.fix_action: str = ""

        # Subscribers (callbacks notified on state change)
        self._listeners: List[Callable[[], None]] = []

    @classmethod
    def get_instance(cls) -> "LiveSessionViewModel":
        if cls._instance is None:
            cls._instance = LiveSessionViewModel()
        return cls._instance

    def subscribe(self, callback: Callable[[], None]):
        """Registers a UI widget to be notified on state updates."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(self):
        """Dispatches update notifications to all UI subscribers."""
        dead_listeners = []
        for cb in list(self._listeners):
            try:
                cb()
            except RuntimeError:
                # Wrapped C/C++ Qt widget object has been deleted
                dead_listeners.append(cb)
            except Exception as e:
                logger.debug("[LiveSessionViewModel] Subscriber callback error: %s", e)
        for dead in dead_listeners:
            if dead in self._listeners:
                self._listeners.remove(dead)

    def clear_listeners(self):
        self._listeners.clear()

    def set_engine_status(self, status: str, latency_ms: Optional[float] = None):
        self.engine_status = status
        if latency_ms is not None:
            self.latency_ms = latency_ms
        self.notify()

    def set_capture_state(self, is_capturing: bool, is_paused: bool = False):
        self.is_capturing = is_capturing
        self.is_paused = is_paused
        if not is_capturing:
            self.partial_text = {"mic": "", "call": ""}
        self.notify()

    def add_segment(self, segment: TranscriptSegment):
        """Adds finalized transcript turn and clears partial preview for that source."""
        self.segments.append(segment)
        if len(self.segments) > 100:
            self.segments = self.segments[-100:]
        src = segment.source
        self.partial_text[src] = ""
        self.notify()

    def set_partial(self, text: str, source: str):
        """Updates in-flight preview partial text."""
        self.partial_text[source] = text
        self.notify()

    def set_ai_thinking(self, question: str):
        self.current_question = question
        self.is_thinking = True
        self.thinking_start_time = time.monotonic()
        self.streamed_tokens = ""
        self.completed_answer = ""
        self.code_snippet = None
        self.error_message = ""
        self.fix_label = ""
        self.fix_action = ""
        self.notify()

    def append_ai_token(self, token: str):
        self.streamed_tokens += token
        self.notify()

    def set_ai_answer(self, question: str, answer: str, code: Optional[str] = None):
        self.current_question = question
        self.completed_answer = answer
        self.code_snippet = code
        self.streamed_tokens = answer
        self.is_thinking = False
        self.error_message = ""
        self.notify()

    def set_ai_error(self, err_msg: str, fix_label: str = "", fix_action: str = ""):
        self.is_thinking = False
        self.error_message = err_msg
        self.fix_label = fix_label or "Open AI settings"
        self.fix_action = fix_action or "open_settings_ai"
        self.notify()

    def clear(self):
        """Clears all transcript and answer history in current session."""
        self.segments.clear()
        self.partial_text = {"mic": "", "call": ""}
        self.current_question = ""
        self.is_thinking = False
        self.streamed_tokens = ""
        self.completed_answer = ""
        self.code_snippet = None
        self.error_message = ""
        self.notify()

