import os
import time
import math
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from collections import deque
import json
import numpy as np

try:
    from faster_whisper import WhisperModel
    HAVE_FASTER_WHISPER = True
except ImportError:
    WhisperModel = None
    HAVE_FASTER_WHISPER = False

try:
    import torch
    HAVE_TORCH = True
except ImportError:
    HAVE_TORCH = False


@dataclass
class TranscriptSegment:
    """Represents a finalized or partial speech transcript segment."""
    id: int
    timestamp: float
    time_str: str
    source: str           # 'call' or 'mic'
    speaker_label: str    # '[Call]' or '[You]'
    text: str
    language: str = "auto"
    is_final: bool = True
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "time_str": self.time_str,
            "source": self.source,
            "speaker_label": self.speaker_label,
            "text": self.text,
            "language": self.language,
            "is_final": self.is_final,
            "confidence": self.confidence
        }

    @property
    def formatted_line(self) -> str:
        return f"[{self.time_str}] {self.speaker_label} {self.text}"


class LiveTranscriber:
    """
    Offline local speech-to-text transcription engine using faster-whisper.
    Processes rolling audio buffers, detects voice activity, distinguishes partials
    from finalized segments, and bounds history memory.
    """

    MODEL_SPECS = {
        "tiny": {"size": "39 MB", "ram": "~500 MB", "speed": "Fastest", "accuracy": "Good for common terms"},
        "base": {"size": "74 MB", "ram": "~1 GB", "speed": "Fast", "accuracy": "Balanced"},
        "small": {"size": "244 MB", "ram": "~2 GB", "speed": "Moderate", "accuracy": "High accuracy"},
        "medium": {"size": "769 MB", "ram": "~5 GB", "speed": "Slower", "accuracy": "Very high accuracy"}
    }

    def __init__(
        self,
        model_name: str = "tiny",
        language: str = "auto",
        chunk_sec: float = 3.0,
        chunk_duration_sec: Optional[float] = None,
        overlap_sec: float = 0.5,
        max_history_items: int = 200,
        on_segment: Optional[Callable[[TranscriptSegment], None]] = None,
        on_partial: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ):
        self.model_name = model_name
        self.language = language if language != "auto" else None
        effective_chunk = chunk_duration_sec if chunk_duration_sec is not None else chunk_sec
        self.chunk_sec = max(1.0, min(10.0, effective_chunk))
        self.overlap_sec = max(0.2, min(1.0, overlap_sec))
        self.max_history_items = max_history_items
        self.on_segment = on_segment
        self.on_partial = on_partial
        self.on_status = on_status

        self.model: Optional[Any] = None
        self.model_device: str = "cpu"
        self.is_loading = False
        self.is_running = False
        self.is_paused = False

        self._lock = threading.Lock()
        self._segment_counter = 0

        # Rolling buffers (16 kHz float32)
        self._sample_rate = 16000
        self._chunk_samples = int(self.chunk_sec * self._sample_rate)
        self._overlap_samples = int(self.overlap_sec * self._sample_rate)

        self._call_buffer = np.zeros(0, dtype=np.float32)
        self._mic_buffer = np.zeros(0, dtype=np.float32)

        # Worker thread
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._audio_queue = deque()
        self._last_chunk_time: Dict[str, float] = {"call": 0.0, "mic": 0.0}

        # Transcript history & Telemetry
        self.history: deque[TranscriptSegment] = deque(maxlen=self.max_history_items)
        self.last_transcription_time: float = 0.0
        self.last_transcription_text: str = ""
        self.last_error: str = ""
        self._last_emitted_text: Dict[str, str] = {"call": "", "mic": ""}

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns transcription engine status telemetry."""
        return {
            "model_name": self.model_name,
            "model_device": self.model_device,
            "is_ready": self.model is not None,
            "is_loading": self.is_loading,
            "is_running": self.is_running,
            "last_text": self.last_transcription_text,
            "last_time": self.last_transcription_time,
            "last_error": self.last_error,
            "total_segments": len(self.history)
        }


    def initialize_model(self, model_name: Optional[str] = None, force_cpu: bool = False) -> Tuple[bool, str]:
        """Loads or reloads the local Whisper transcription model with hardware acceleration or CPU fallback."""
        with self._lock:
            if model_name:
                self.model_name = model_name

            if not HAVE_FASTER_WHISPER:
                err = "faster-whisper library is not installed."
                self._notify_status(f"Error: {err}")
                return False, err

            self.is_loading = True
            self._notify_status(f"Loading Whisper '{self.model_name}'...")

        # Detect optimal device outside lock
        device = "cpu"
        compute_type = "int8"
        if not force_cpu and HAVE_TORCH and hasattr(torch, "cuda") and torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"

        try:
            logging.info("[LiveTranscriber] Initializing model='%s', device='%s', compute_type='%s'",
                         self.model_name, device, compute_type)
            loaded_model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=compute_type,
                cpu_threads=max(2, os.cpu_count() or 4)
            )
            with self._lock:
                self.model = loaded_model
                self.model_device = device
                self.is_loading = False
            
            info_msg = f"Model Ready ({self.model_name} on {device.upper()})"
            self._notify_status(info_msg)
            return True, info_msg
        except Exception as ex:
            logging.warning("[LiveTranscriber] Failed on %s: %s; falling back to CPU int8", device, ex)
            try:
                loaded_model = WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=max(2, os.cpu_count() or 4)
                )
                with self._lock:
                    self.model = loaded_model
                    self.model_device = "cpu"
                    self.is_loading = False
                info_msg = f"Model Ready ({self.model_name} on CPU)"
                self._notify_status(info_msg)
                return True, info_msg
            except Exception as ex_cpu:
                with self._lock:
                    self.is_loading = False
                err_text = f"Model initialization failed: {ex_cpu}"
                self._notify_status(f"Error: {err_text}")
                return False, err_text

    def start(self):
        """Starts the background transcription worker."""
        if self.is_running:
            return

        if self.model is None and not self.is_loading:
            threading.Thread(target=self.initialize_model, daemon=True).start()

        self._stop_event.clear()
        self.is_running = True
        self.is_paused = False
        self._worker_thread = threading.Thread(target=self._transcription_worker_loop, daemon=True)
        self._worker_thread.start()
        logging.info("[LiveTranscriber] Transcription worker started.")

    def stop(self):
        """Stops background worker and clears in-flight buffers."""
        self.is_running = False
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

        with self._lock:
            self._call_buffer = np.zeros(0, dtype=np.float32)
            self._mic_buffer = np.zeros(0, dtype=np.float32)
            self._audio_queue.clear()

        self._notify_status("Idle")
        logging.info("[LiveTranscriber] Transcription worker stopped.")

    def pause(self):
        self.is_paused = True
        self._notify_status("Paused")

    def resume(self):
        self.is_paused = False
        self._notify_status("Transcribing")

    def add_audio_chunk(self, chunk: np.ndarray, source: str):
        """Receives 16 kHz float32 audio chunk from AudioCaptureManager."""
        if not self.is_running or self.is_paused or len(chunk) == 0:
            return
        with self._lock:
            self._audio_queue.append((chunk, source))

    @property
    def audio_queue(self):
        return self._audio_queue

    def push_audio_chunk(self, chunk: np.ndarray, sample_rate: int = 16000, source: str = "call"):
        """Receives 16 kHz float32 audio chunk and pushes to queue."""
        if self.is_paused or len(chunk) == 0:
            return
        with self._lock:
            self._audio_queue.append((chunk, source))

    def get_transcript_history(self) -> List[TranscriptSegment]:
        with self._lock:
            return list(self.history)

    def clear_history(self):
        """Clears local transcript history."""
        with self._lock:
            self.history.clear()
            self._last_emitted_text = {"call": "", "mic": ""}

    def clear(self):
        self.clear_history()

    def _record_segment(self, segment: TranscriptSegment):
        with self._lock:
            self.history.append(segment)

    def _transcribe_buffer(self, audio: np.ndarray, source: str):
        if source == "call":
            self._call_buffer = audio
        else:
            self._mic_buffer = audio
        self._process_buffer(source)

    def export_transcript(self, filepath: str, export_format: str = "txt") -> Tuple[bool, str]:
        """Exports transcript history to a local file."""
        with self._lock:
            items = list(self.history)

        if not items:
            return False, "No transcript segments to export."

        try:
            path = os.path.abspath(filepath)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if export_format.lower() == "json" or filepath.lower().endswith(".json"):
                data = {"transcript": [item.to_dict() for item in items]}
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                lines = [item.formatted_line for item in items]
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            return True, f"Exported {len(items)} segments to {path}"
        except Exception as ex:
            return False, f"Failed to export transcript: {ex}"

    def _transcription_worker_loop(self):
        """Main worker loop dequeuing audio chunks and transcribing active speech."""
        while not self._stop_event.is_set():
            chunks_to_process = []
            with self._lock:
                while self._audio_queue:
                    chunks_to_process.append(self._audio_queue.popleft())

            now = time.time()
            for chunk, source in chunks_to_process:
                self._last_chunk_time[source] = now
                if source == "call":
                    self._call_buffer = np.concatenate([self._call_buffer, chunk])
                else:
                    self._mic_buffer = np.concatenate([self._mic_buffer, chunk])

            # Process call buffer if chunk size reached OR if speaker paused (>0.4s)
            call_len = len(self._call_buffer)
            if call_len >= self._chunk_samples:
                self._process_buffer("call", is_flush=False)
            elif call_len >= int(0.65 * self._sample_rate) and (now - self._last_chunk_time.get("call", 0.0) > 0.40):
                self._process_buffer("call", is_flush=True)

            # Process mic buffer if chunk size reached OR if speaker paused (>0.4s)
            mic_len = len(self._mic_buffer)
            if mic_len >= self._chunk_samples:
                self._process_buffer("mic", is_flush=False)
            elif mic_len >= int(0.65 * self._sample_rate) and (now - self._last_chunk_time.get("mic", 0.0) > 0.40):
                self._process_buffer("mic", is_flush=True)

            if not chunks_to_process:
                time.sleep(0.08)

    def _deduplicate_overlap(self, prev_text: str, current_text: str) -> str:
        """Removes repeated words or overlapping prefixes between consecutive segments."""
        prev_words = prev_text.strip().split()
        curr_words = current_text.strip().split()
        if not prev_words or not curr_words:
            return current_text.strip()

        # Check multi-word overlap from max possible down to 2 words
        max_k = min(len(prev_words), len(curr_words))
        for k in range(max_k, 1, -1):
            if [w.lower().strip(".,?!\"'") for w in prev_words[-k:]] == [w.lower().strip(".,?!\"'") for w in curr_words[:k]]:
                remaining = curr_words[k:]
                return " ".join(remaining).strip()

        # If current chunk is solely 1 word and exactly repeats the last word of prev
        if len(curr_words) == 1 and len(prev_words) >= 1:
            if curr_words[0].lower().strip(".,?!\"'") == prev_words[-1].lower().strip(".,?!\"'"):
                return ""

        return current_text.strip()

    def _process_buffer(self, source: str, is_flush: bool = False):
        """Transcribes accumulated buffer for a given source."""
        if self.model is None or self.is_paused:
            return

        buf = self._call_buffer if source == "call" else self._mic_buffer
        if len(buf) < int(0.60 * self._sample_rate):  # Need at least 0.6s
            return

        # Voice Activity Detection / Energy Gate: Skip ambient background hiss / silence
        rms = math.sqrt(float(np.mean(buf ** 2)))
        if rms < 0.0015:
            # Silence / noise floor: advance buffer
            with self._lock:
                if is_flush:
                    if source == "call":
                        self._call_buffer = np.zeros(0, dtype=np.float32)
                    else:
                        self._mic_buffer = np.zeros(0, dtype=np.float32)
                else:
                    if source == "call":
                        self._call_buffer = self._call_buffer[-self._overlap_samples:]
                    else:
                        self._mic_buffer = self._mic_buffer[-self._overlap_samples:]
            return

        speaker_tag = "[Call]" if source == "call" else "[You]"
        audio_to_transcribe = np.nan_to_num(buf.copy(), nan=0.0, posinf=1.0, neginf=-1.0)
        np.clip(audio_to_transcribe, -1.0, 1.0, out=audio_to_transcribe)

        # Advance buffer
        with self._lock:
            if is_flush:
                if source == "call":
                    self._call_buffer = np.zeros(0, dtype=np.float32)
                else:
                    self._mic_buffer = np.zeros(0, dtype=np.float32)
            else:
                if source == "call":
                    self._call_buffer = self._call_buffer[-self._overlap_samples:]
                else:
                    self._mic_buffer = self._mic_buffer[-self._overlap_samples:]

        try:
            segments, info = self.model.transcribe(
                audio_to_transcribe,
                language=self.language,
                beam_size=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                condition_on_previous_text=False,
                repetition_penalty=1.1,
                no_speech_threshold=0.6,
            )

            detected_lang = info.language if info else (self.language or "en")
            lang_prob = getattr(info, "language_probability", None)
            if isinstance(lang_prob, (int, float)) and lang_prob < 0.4 and not self.language:
                detected_lang = "en"

            for seg in segments:
                # Filter out hallucinated or low-confidence segments on ambient noise
                no_speech_prob = getattr(seg, "no_speech_prob", None)
                avg_logprob = getattr(seg, "avg_logprob", None)
                if isinstance(no_speech_prob, (int, float)) and no_speech_prob > 0.6:
                    continue
                if isinstance(avg_logprob, (int, float)) and avg_logprob < -1.1:
                    continue

                raw_text = seg.text.strip()
                if not raw_text or len(raw_text) < 2:
                    continue

                # Deduplicate overlapping phrases across sliding chunks
                prev_text = self._last_emitted_text.get(source, "")
                text = self._deduplicate_overlap(prev_text, raw_text)
                if not text or len(text) < 2:
                    continue

                self._last_emitted_text[source] = raw_text
                self._segment_counter += 1
                now = time.time()
                time_str = time.strftime("%H:%M:%S", time.localtime(now))
                self.last_transcription_time = now
                self.last_transcription_text = text
                self.last_error = ""

                segment_obj = TranscriptSegment(
                    id=self._segment_counter,
                    timestamp=now,
                    time_str=time_str,
                    source=source,
                    speaker_label=speaker_tag,
                    text=text,
                    language=detected_lang,
                    is_final=True,
                    confidence=getattr(seg, "avg_logprob", 1.0)
                )

                with self._lock:
                    self.history.append(segment_obj)

                # Emit finalized segment
                if self.on_segment is not None:
                    try:
                        self.on_segment(segment_obj)
                    except Exception as cb_err:
                        logging.debug("[LiveTranscriber] on_segment callback error: %s", cb_err)

                # Update status
                self._notify_status(f"Live ({detected_lang})")

        except Exception as ex:
            self.last_error = str(ex)
            logging.debug("[LiveTranscriber] Transcription segment error: %s", ex)


    def _notify_status(self, status: str):
        if self.on_status is not None:
            try:
                self.on_status(status)
            except Exception:
                pass
