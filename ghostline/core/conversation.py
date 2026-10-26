"""
Ghostline — Session-Scoped Conversation Model.
Maintains persistent, timestamped, source-attributed entries for:
- Live call transcripts and spoken questions (Microphone, System Audio)
- Screen-captured questions and MCQs (Screen Capture)
- Explicit user queries (Manual Ask)
Guarantees question-answer association, prevents delayed overwrite,
and preserves conversation history across mode switches.
"""

import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable


SOURCE_MIC = "mic"
SOURCE_SYSTEM = "call"
SOURCE_SCREEN = "screen"
SOURCE_MANUAL = "manual"

STATUS_TRANSCRIPT = "transcript"
STATUS_THINKING = "thinking"
STATUS_ANSWERED = "answered"
STATUS_ERROR = "error"


@dataclass
class ConversationEntry:
    """Represents a single persistent interaction or utterance in the session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    time_str: str = ""
    source: str = SOURCE_SCREEN          # 'mic', 'call', 'screen', 'manual'
    speaker_label: str = ""              # '[You]', '[Call]', '[Screen MCQ]', '[Manual]'
    original_text: str = ""              # Raw speech transcript or raw OCR text
    detected_question: str = ""          # Cleaned question stem
    supporting_passage: str = ""         # Supporting text, reading passage, or code block
    options: Any = field(default_factory=dict) # e.g. {'A': '...', 'B': '...'} or list
    question_type: str = "mcq"           # 'mcq', 'code', 'theory', 'uncertain'
    question_heading: str = ""           # e.g. 'Question 12 of 50'
    status: str = STATUS_TRANSCRIPT      # 'transcript', 'thinking', 'answered', 'error'
    answer_text: str = ""                # Direct headline or chosen option
    explanation: str = ""                # Bullets and explanation paragraphs
    code_snippet: Optional[str] = None
    code_language: str = ""
    badge: str = ""                      # e.g. 'A', 'B', '3', '✓'
    error: Optional[str] = None          # Error message if inference failed
    is_question: bool = False
    is_final: bool = True
    confidence: float = 1.0

    def __post_init__(self):
        if not self.time_str:
            self.time_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        if not self.speaker_label:
            if self.source == SOURCE_MIC:
                self.speaker_label = "[You]"
            elif self.source == SOURCE_SYSTEM:
                self.speaker_label = "[Call]"
            elif self.source == SOURCE_SCREEN:
                self.speaker_label = "[Screen MCQ]"
            elif self.source == SOURCE_MANUAL:
                self.speaker_label = "[Manual]"
            else:
                self.speaker_label = f"[{self.source.title()}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "time_str": self.time_str,
            "source": self.source,
            "speaker_label": self.speaker_label,
            "original_text": self.original_text,
            "detected_question": self.detected_question,
            "supporting_passage": self.supporting_passage,
            "options": self.options,
            "status": self.status,
            "answer_text": self.answer_text,
            "explanation": self.explanation,
            "code_snippet": self.code_snippet,
            "code_language": self.code_language,
            "badge": self.badge,
            "error": self.error,
            "is_question": self.is_question,
            "is_final": self.is_final,
            "confidence": self.confidence,
        }


class ConversationSession:
    """
    Manages session-scoped conversation history.
    Preserves all questions, answers, and transcripts in sequence.
    Thread-safe and decoupled from single UI widgets.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self.created_at = time.time()
        self.is_active = True
        self._entries: List[ConversationEntry] = []
        self._lock = threading.RLock()
        self._on_update_callbacks: List[Callable[[ConversationEntry], None]] = []

    def add_update_listener(self, callback: Callable[[ConversationEntry], None]):
        with self._lock:
            if callback not in self._on_update_callbacks:
                self._on_update_callbacks.append(callback)

    def remove_update_listener(self, callback: Callable[[ConversationEntry], None]):
        with self._lock:
            if callback in self._on_update_callbacks:
                self._on_update_callbacks.remove(callback)

    def _notify_listeners(self, entry: ConversationEntry):
        for cb in list(self._on_update_callbacks):
            try:
                cb(entry)
            except Exception:
                pass

    def add_entry(self, entry: ConversationEntry) -> ConversationEntry:
        """Appends a new conversation entry to history."""
        with self._lock:
            if not entry.session_id:
                entry.session_id = self.session_id
            self._entries.append(entry)
        self._notify_listeners(entry)
        return entry

    def create_entry(self, **kwargs) -> ConversationEntry:
        """Creates and appends a new conversation entry to history."""
        if "session_id" not in kwargs:
            kwargs["session_id"] = self.session_id
        if "raw_text" in kwargs and "original_text" not in kwargs:
            kwargs["original_text"] = kwargs.pop("raw_text")
        if "question_text" in kwargs and "detected_question" not in kwargs:
            kwargs["detected_question"] = kwargs.pop("question_text")
        entry = ConversationEntry(**kwargs)
        return self.add_entry(entry)

    def complete_entry(self, entry_id: str, presented_answer: Any):
        """Marks entry as answered with presented answer data."""
        headline = getattr(presented_answer, "headline", "") or getattr(presented_answer, "direct_answer", "")
        exp = getattr(presented_answer, "explanation", "")
        code = getattr(presented_answer, "code", None)
        lang = getattr(presented_answer, "code_language", None)
        badge = getattr(presented_answer, "badge", None)
        self.update_entry(
            entry_id,
            status=STATUS_ANSWERED,
            answer_text=headline,
            explanation=exp,
            code_snippet=code,
            code_language=lang,
            badge=badge,
            is_question=True
        )

    def update_entry(self, entry_id: str, **kwargs) -> Optional[ConversationEntry]:
        """Updates fields of an existing entry (e.g. adding answer or error)."""
        target = None
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    for k, v in kwargs.items():
                        if hasattr(e, k):
                            setattr(e, k, v)
                    target = e
                    break
        if target:
            self._notify_listeners(target)
        return target

    def get_entry(self, entry_id: str) -> Optional[ConversationEntry]:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    return e
        return None

    def get_latest_entry(self, mode_filter: Optional[str] = None) -> Optional[ConversationEntry]:
        with self._lock:
            for e in reversed(self._entries):
                if mode_filter is None:
                    return e
                if mode_filter == "call" and e.source in (SOURCE_MIC, SOURCE_SYSTEM):
                    return e
                if mode_filter == "screen" and e.source == SOURCE_SCREEN:
                    return e
                if mode_filter == "manual" and e.source == SOURCE_MANUAL:
                    return e
        return None

    def get_history(self, mode_filter: Optional[str] = None) -> List[ConversationEntry]:
        """Returns entries filtered by mode, or all entries."""
        with self._lock:
            if not mode_filter or mode_filter == "all":
                return list(self._entries)
            if mode_filter == "call":
                return [e for e in self._entries if e.source in (SOURCE_MIC, SOURCE_SYSTEM)]
            if mode_filter == "screen":
                return [e for e in self._entries if e.source == SOURCE_SCREEN]
            if mode_filter == "manual":
                return [e for e in self._entries if e.source == SOURCE_MANUAL]
            return [e for e in self._entries if e.source == mode_filter]

    get_entries = get_history

    def clear(self):
        """Clears entries explicitly with reset."""
        with self._lock:
            self._entries.clear()

    def end_session(self):
        with self._lock:
            self.is_active = False

    def count(self) -> int:
        with self._lock:
            return len(self._entries)
