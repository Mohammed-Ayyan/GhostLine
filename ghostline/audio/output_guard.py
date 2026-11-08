"""
Ghostline Audio Output Guard & Echo Filter (Run 15 Part A).
Engine-agnostic validation, repetition prevention, language-script enforcement,
silence hallucination rejection, and cross-channel speaker echo cancellation.
"""

import zlib
import re
import time
import unicodedata
from difflib import SequenceMatcher
from collections import deque
from typing import Optional, Tuple, Dict, Any, List

KNOWN_HALLUCINATIONS = {
    "thank you",
    "thank you.",
    "thank you for watching",
    "thank you for watching.",
    "thanks for watching",
    "thanks for watching.",
    "subtitles by",
    "please subscribe",
    "subscribe to my channel",
    "see you next time",
    "see you next time.",
    "mbc",
    "amara.org",
    "bye.",
    "bye",
    "you",
    "the end",
    "the end."
}

def get_script_name(char: str) -> str:
    """Returns general Unicode script family for a character."""
    code = ord(char)
    # ASCII / Latin
    if (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A) or (0x00C0 <= code <= 0x024F):
        return "Latin"
    # Thai
    if 0x0E00 <= code <= 0x0E7F:
        return "Thai"
    # Japanese Hiragana / Katakana / Han
    if (0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF):
        return "Japanese"
    if 0x4E00 <= code <= 0x9FFF:
        return "Han"
    # Cyrillic
    if 0x0400 <= code <= 0x04FF:
        return "Cyrillic"
    # Arabic
    if 0x0600 <= code <= 0x06FF:
        return "Arabic"
    # Devanagari
    if 0x0900 <= code <= 0x097F:
        return "Devanagari"
    # Hangul
    if (0xAC00 <= code <= 0xD7AF) or (0x1100 <= code <= 0x11FF):
        return "Hangul"
    return "Other"

class AudioOutputGuard:
    """
    Validates transcript segments before they reach the UI or conversation history.
    Detects repetitions, foreign scripts, acoustic echo, and hallucinated loops.
    """

    def __init__(self, language: str = "en"):
        self.language = language.lower() if language else "en"
        # Bounded buffer of recent system segments: (timestamp, normalized_text)
        self._recent_system_segments = deque(maxlen=30)
        self.filter_counts: Dict[str, int] = {
            "repetition": 0,
            "script_mismatch": 0,
            "speech_rate": 0,
            "hallucination_phrase": 0,
            "low_confidence": 0,
            "echo_speaker": 0
        }
        self.echo_detection_count = 0
        self.echo_tip_triggered = False

    def set_language(self, language: str):
        self.language = (language or "en").lower()

    def record_system_segment(self, text: str):
        """Records a finalized system audio segment for acoustic echo comparison."""
        clean = self._normalize_text(text)
        if clean:
            self._recent_system_segments.append((time.time(), clean))

    def _normalize_text(self, text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"[^\w\s]", "", t)
        return re.sub(r"\s+", " ", t)

    def check_repetition(self, text: str) -> bool:
        """
        Returns True if text contains excessive repetition loops.
        Detects:
        - 4+ identical consecutive tokens/words
        - Repeated n-gram phrases (2-gram or 3-gram repeated >= 3 times)
        - High zlib compression ratio (> 2.4 on strings >= 25 chars)
        """
        clean = text.strip()
        if not clean:
            return False

        # 1. High zlib compression ratio check
        raw_bytes = clean.encode("utf-8")
        if len(raw_bytes) >= 25:
            try:
                comp = zlib.compress(raw_bytes)
                ratio = len(raw_bytes) / max(1, len(comp))
                if ratio > 2.4:
                    return True
            except Exception:
                pass

        # 2. Token-level consecutive repetition (spaces or script blocks)
        # Check words if spaced
        words = clean.split()
        if len(words) >= 4:
            for i in range(len(words) - 3):
                if words[i].lower() == words[i+1].lower() == words[i+2].lower() == words[i+3].lower():
                    return True

        # 3. Unspaced repeated character/substring loops (e.g. Thai 'ความ' repeated)
        for sub_len in range(2, 12):
            pattern = re.compile(r"(.{" + str(sub_len) + r"})\1{3,}")
            if pattern.search(clean):
                return True

        # 4. N-gram loop detection (e.g. "is a test is a test is a test")
        if len(words) >= 6:
            for n in (2, 3):
                ngrams = [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]
                counts: Dict[str, int] = {}
                for ng in ngrams:
                    counts[ng] = counts.get(ng, 0) + 1
                    if counts[ng] >= 4:
                        return True

        return False

    def check_script_mismatch(self, text: str) -> bool:
        """
        Returns True if text is in a foreign script incompatible with the selected language.
        If language is 'auto', no script check is enforced.
        If language is 'en', text must be predominantly Latin/ASCII.
        """
        if self.language in ("auto", "all"):
            return False

        alphas = [c for c in text if c.isalpha()]
        if not alphas:
            return False

        if self.language in ("en", "english"):
            latin_count = sum(1 for c in alphas if get_script_name(c) == "Latin")
            ratio = latin_count / len(alphas)
            if ratio < 0.50:
                return True

        return False

    def check_hallucination_phrase(self, text: str, rms: float = 0.05) -> bool:
        """Returns True if text is a known silence hallucination and audio energy is low."""
        clean = text.lower().strip()
        if clean in KNOWN_HALLUCINATIONS and rms < 0.025:
            return True
        return False

    def check_speech_rate(self, text: str, duration_sec: float) -> bool:
        """Returns True if words per second is implausibly high (> 9.0 wps on chunks with >= 15 words)."""
        if duration_sec <= 0:
            return False
        words = text.strip().split()
        if len(words) < 15:
            return False
        wps = len(words) / duration_sec
        return wps > 9.0

    def check_echo(self, text: str, source: str) -> Tuple[bool, Optional[str]]:
        """
        Cross-channel acoustic echo guard.
        If source is 'mic' and text matches a recent system audio segment from the last 4.5s:
        returns (True, "echo_speaker").
        """
        if source != "mic":
            return False, None

        clean_mic = self._normalize_text(text)
        if not clean_mic or len(clean_mic) < 4:
            return False, None

        now = time.time()
        # Clean expired system segments older than 5.0 seconds
        valid_sys = [(t, s) for t, s in self._recent_system_segments if (now - t) <= 4.5]

        for _, sys_text in valid_sys:
            if not sys_text:
                continue

            # Substring match
            if clean_mic in sys_text or sys_text in clean_mic:
                if len(clean_mic) >= 6:
                    self.echo_detection_count += 1
                    return True, "echo_speaker"

            # SequenceMatcher similarity
            ratio = SequenceMatcher(None, clean_mic, sys_text).ratio()
            if ratio >= 0.70:
                self.echo_detection_count += 1
                return True, "echo_speaker"

        return False, None

    def validate_segment(
        self,
        text: str,
        source: str = "mic",
        duration_sec: float = 2.0,
        rms: float = 0.05,
        confidence: float = 1.0,
        no_speech_prob: Optional[float] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validates segment against all filtering rules.
        Returns (is_valid, processed_text, drop_reason).
        """
        raw = text.strip()
        if not raw:
            return False, "", "empty"

        # 1. Confidence check
        if confidence < 0.25 or (no_speech_prob is not None and no_speech_prob > 0.80):
            self.filter_counts["low_confidence"] += 1
            return False, "", "low_confidence"

        # 2. Known silence hallucination
        if self.check_hallucination_phrase(raw, rms=rms):
            self.filter_counts["hallucination_phrase"] += 1
            return False, "", "hallucination_phrase"

        # 3. Repetition loop check
        if self.check_repetition(raw):
            self.filter_counts["repetition"] += 1
            return False, "", "repetition"

        # 4. Foreign script check
        if self.check_script_mismatch(raw):
            self.filter_counts["script_mismatch"] += 1
            return False, "", "script_mismatch"

        # 5. Speech rate plausibility
        if self.check_speech_rate(raw, duration_sec=duration_sec):
            self.filter_counts["speech_rate"] += 1
            return False, "", "speech_rate"

        # 6. Speaker acoustic echo check
        is_echo, echo_reason = self.check_echo(raw, source=source)
        if is_echo:
            self.filter_counts["echo_speaker"] += 1
            if self.echo_detection_count >= 2:
                self.echo_tip_triggered = True
            return False, "", "echo_speaker"

        # If system audio passed, record it for subsequent echo checks
        if source in ("call", "system"):
            self.record_system_segment(raw)

        # Character capping: max 500 characters
        capped_text = raw
        if len(capped_text) > 500:
            capped_text = capped_text[:497] + "…"

        return True, capped_text, None

    def get_diagnostics_summary(self) -> str:
        total = sum(self.filter_counts.values())
        parts = [f"{v} {k.replace('_', ' ')}" for k, v in self.filter_counts.items() if v > 0]
        details = ", ".join(parts) if parts else "none"
        return f"Filtered segments: {total} ({details})"

    def should_show_echo_tip(self) -> bool:
        """Returns True once when echo tip needs to be displayed."""
        if self.echo_tip_triggered:
            self.echo_tip_triggered = False  # one-time flag
            return True
        return False
