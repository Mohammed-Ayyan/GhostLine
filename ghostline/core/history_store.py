"""
Ghostline — Unified Session & Interaction History Store
Thread-safe persistent storage for screen solves, audio Q&A, and live call transcripts.
Persists records to %APPDATA%\\Ghostline\\history\\sessions.jsonl with restart recovery,
instant querying, filtering (All, Screen, Audio), and search.
"""

import os
import time
import json
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

def get_history_dir() -> Path:
    """Returns the persistent history directory under %APPDATA%\\Ghostline\\history\\."""
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) / "Ghostline" if app_data else Path.home() / ".ghostline"
    h_dir = base / "history"
    h_dir.mkdir(parents=True, exist_ok=True)
    return h_dir

def get_history_file() -> Path:
    return get_history_dir() / "sessions.jsonl"


class SessionHistoryStore:
    """
    Thread-safe session history storage engine.
    Appends new entries to sessions.jsonl and provides high-speed in-memory caching.
    """
    _instance: Optional["SessionHistoryStore"] = None
    _lock = threading.Lock()

    def __init__(self, storage_path: Optional[Path] = None, history_file: Optional[Path] = None):
        self._file = storage_path or history_file or get_history_file()
        self._file_lock = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._loaded = False
        self._load_from_disk()

    @classmethod
    def get_instance(cls) -> "SessionHistoryStore":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_from_disk(self):
        """Loads previous history entries into memory on startup (newest first)."""
        with self._file_lock:
            if not self._file.exists():
                # Check legacy history.jsonl in app root and migrate if present
                legacy_file = self._file.parent.parent / "history.jsonl"
                if legacy_file.exists():
                    try:
                        self._file.write_text(legacy_file.read_text(encoding="utf-8"), encoding="utf-8")
                    except Exception:
                        pass

            entries = []
            if self._file.exists():
                try:
                    with open(self._file, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            l = line.strip()
                            if l:
                                try:
                                    entry = json.loads(l)
                                    entries.append(entry)
                                except Exception:
                                    continue
                except Exception as e:
                    logging.warning("[HistoryStore] Error reading %s: %s", self._file, e)

            # Sort newest first
            entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            self._entries = entries
            self._loaded = True
            logging.info("[HistoryStore] Loaded %d persistent entries from %s", len(self._entries), self._file)

        # Apply automatic retention policy on startup
        try:
            from ghostline.config import load_config
            retention_days = getattr(load_config(), "history_retention_days", 30)
            if retention_days > 0:
                self.purge_retention(retention_days)
        except Exception:
            pass

    def add_screen_solve(
        self,
        question_text: str = "",
        options: Optional[Dict[str, str]] = None,
        answer_text: str = "",
        badge: str = "",
        code_snippet: Optional[str] = None,
        code_language: str = "",
        question_type: str = "mcq",
        supporting_passage: str = "",
        raw_ocr: str = "",
        is_validated: bool = True,
        question: Optional[str] = None,
        answer_option: Optional[str] = None,
        answer: Optional[str] = None,
        explanation: str = "",
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """Appends a completed screen solve entry."""
        final_q = question_text or question or ""
        final_ans = answer_text or answer_option or answer or ""
        ts = time.time()
        entry_id = f"screen_{int(ts * 1000)}"
        entry = {
            "id": entry_id,
            "timestamp": ts,
            "time_str": time.strftime("%H:%M:%S", time.localtime(ts)),
            "source": "screen",
            "entry_type": "screen_solve",
            "question": final_q,
            "supporting_passage": supporting_passage or explanation,
            "options": options or {},
            "answer": final_ans,
            "badge": badge or ("MCQ" if question_type == "mcq" else "Code"),
            "code_snippet": code_snippet or "",
            "code_language": code_language or "",
            "question_type": question_type,
            "raw_text": raw_ocr or "",
            "confidence": confidence,
            "is_validated": is_validated,
            "status": "answered" if is_validated else "error"
        }
        self._write_entry(entry)
        return entry

    def add_audio_qa(
        self,
        question: str,
        answer: str,
        code_snippet: Optional[str] = None,
        source: str = "call",
        entry_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends a completed audio question & answer entry."""
        ts = time.time()
        eid = entry_id or f"audio_{int(ts * 1000)}"
        entry = {
            "id": eid,
            "timestamp": ts,
            "time_str": time.strftime("%H:%M:%S", time.localtime(ts)),
            "source": "audio",
            "entry_type": "audio_qa",
            "speaker_label": f"[{source.capitalize()}]",
            "question": question,
            "answer": answer,
            "badge": "Audio",
            "code_snippet": code_snippet or "",
            "code_language": "",
            "question_type": "audio_qa",
            "is_validated": True,
            "status": "answered"
        }
        self._write_entry(entry)
        return entry

    def add_transcript_segment(
        self,
        text: str,
        source: str = "call",
        is_question: bool = False,
        speaker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Appends an utterance transcript segment."""
        ts = time.time()
        eid = f"trans_{int(ts * 1000)}"
        if speaker:
            spk_label = f"[{speaker}]" if not speaker.startswith("[") else speaker
        else:
            spk_label = "[You]" if source == "mic" else "[Call]"

        entry = {
            "id": eid,
            "timestamp": ts,
            "time_str": time.strftime("%H:%M:%S", time.localtime(ts)),
            "source": "audio",
            "entry_type": "transcript",
            "speaker_label": spk_label,
            "original_text": text,
            "question": text,
            "is_question": is_question,
            "status": "info"
        }
        self._write_entry(entry)
        return entry

    def purge_retention(self, retention_days: int) -> int:
        """
        Purges records older than retention_days.
        If retention_days <= 0, no purging occurs (keep indefinitely).
        Returns number of purged records.
        """
        if retention_days <= 0:
            return 0
        cutoff = time.time() - (retention_days * 86400.0)
        with self._file_lock:
            original_count = len(self._entries)
            self._entries = [e for e in self._entries if e.get("timestamp", 0) >= cutoff]
            purged = original_count - len(self._entries)
            if purged > 0:
                self._rewrite_disk_file()
                logging.info("[HistoryStore] Purged %d expired history entries older than %d days", purged, retention_days)
            return purged

    def _rewrite_disk_file(self) -> None:
        """Atomically rewrites the disk file with current memory entries."""
        try:
            tmp = self._file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                for item in reversed(self._entries):  # Write chronological
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            tmp.replace(self._file)
        except Exception as e:
            logging.warning("[HistoryStore] Failed rewriting history file: %s", e)

    def _write_entry(self, entry: Dict[str, Any]):
        """Thread-safe append to memory and disk (respects save_history policy)."""
        # Check if history saving is disabled
        try:
            from ghostline.config import load_config
            cfg = load_config()
            if not getattr(cfg, "save_history", True) or not getattr(cfg, "save_history_locally", True):
                with self._file_lock:
                    self._entries.insert(0, entry)
                    if len(self._entries) > 50:
                        self._entries = self._entries[:50]
                return
        except Exception:
            pass

        with self._file_lock:
            # Prepend to in-memory list (newest first)
            self._entries.insert(0, entry)
            # Cap in-memory history to 500 items
            if len(self._entries) > 500:
                self._entries = self._entries[:500]

            try:
                line = json.dumps(entry, ensure_ascii=False)
                with open(self._file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                logging.warning("[HistoryStore] Failed writing history entry: %s", e)

    def get_entries(
        self,
        mode_filter: str = "all",
        search_query: str = "",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieves newest-first history entries.
        mode_filter: 'all', 'screen', or 'audio'
        search_query: case-insensitive text search over questions, answers, and transcripts
        """
        with self._file_lock:
            results = []
            q_clean = search_query.strip().lower()

            for item in self._entries:
                # Mode filter
                src = item.get("source", "screen")
                if mode_filter == "screen" and src != "screen":
                    continue
                if mode_filter == "audio" and src != "audio":
                    continue

                # Text search
                if q_clean:
                    haystack = (
                        str(item.get("question", "")) + " " +
                        str(item.get("answer", "")) + " " +
                        str(item.get("original_text", "")) + " " +
                        str(item.get("code_snippet", "")) + " " +
                        " ".join(item.get("options", {}).values() if isinstance(item.get("options"), dict) else [])
                    ).lower()
                    if q_clean not in haystack:
                        continue

                results.append(item)
                if len(results) >= limit:
                    break

            return results

    def clear(self):
        """Clears memory and wipes the disk file and any legacy history files."""
        with self._file_lock:
            self._entries.clear()
            try:
                if self._file.exists():
                    self._file.write_text("", encoding="utf-8")
                # Also clean legacy history.jsonl if present
                legacy_file = self._file.parent.parent / "history.jsonl"
                if legacy_file.exists():
                    legacy_file.write_text("", encoding="utf-8")
                from ghostline.config import get_app_dir
                legacy_app = get_app_dir() / "history.jsonl"
                if legacy_app.exists():
                    legacy_app.write_text("", encoding="utf-8")
            except Exception as e:
                logging.warning("[HistoryStore] Clear file failed: %s", e)


def get_history_store() -> SessionHistoryStore:
    return SessionHistoryStore.get_instance()
