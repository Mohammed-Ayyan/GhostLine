import os
import sys
import time
import math
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from collections import deque
import json
import numpy as np

from ghostline.config import get_app_dir
from .telemetry import get_audio_telemetry
from .timing import record_timing_mark, record_segment_metric, TimingManager
from .output_guard import AudioOutputGuard

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


def get_optimal_stt_threads() -> int:
    """
    Calculates the optimal CPU thread count for CTranslate2 / faster-whisper.
    Benchmark proof (i5-13420H / hybrid CPUs):
    Allocating all logical cores (12) causes thread thrashing with E-cores
    and Ollama contention, increasing latency from 352ms to 420ms.
    Clamps threads to [2, 6], defaulting to min(6, max(2, physical_cores or 4)).
    """
    try:
        import psutil
        count = psutil.cpu_count(logical=False) or os.cpu_count() or 4
    except Exception:
        count = os.cpu_count() or 4
    return max(2, min(6, count))


def get_power_status_tip() -> str:
    """Returns an informational tip if the system is running on battery power."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is not None and not battery.power_plugged:
            return "On battery: Windows may throttle CPU. Plug in for fastest transcription."
    except Exception:
        pass
    return ""


def run_stt_benchmark(model_name: str = "tiny", duration_sec: float = 5.0) -> Dict[str, Any]:
    """
    Runs an empirical speed benchmark measuring real-time factor (RTF)
    and latency on this machine without relying on external servers.
    """
    if not HAVE_FASTER_WHISPER:
        return {"error": "faster-whisper not available", "rtf": 0.0, "latency_ms": 0.0}

    model_target, is_local = resolve_whisper_model_path(model_name)
    threads = get_optimal_stt_threads()
    try:
        t0 = time.perf_counter()
        model = WhisperModel(
            model_target,
            device="cpu",
            compute_type="int8",
            cpu_threads=threads,
            **({"local_files_only": True} if is_local else {})
        )
        load_ms = (time.perf_counter() - t0) * 1000.0

        # Synthetic speech-like audio signal
        sr = 16000
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
        sig = (0.2 * np.sin(2 * np.pi * 300 * t) * (1.0 + 0.5 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)

        # Warmup inference to eliminate cold-start overhead from benchmark measurement
        try:
            warmup_sig = np.zeros(8000, dtype=np.float32)
            _ = list(model.transcribe(warmup_sig, beam_size=1, temperature=0.0, language="en")[0])
        except Exception:
            pass

        t_inf0 = time.perf_counter()
        segments, _ = model.transcribe(sig, beam_size=1, temperature=0.0, language="en")
        _ = list(segments)
        inf_ms = (time.perf_counter() - t_inf0) * 1000.0
        rtf = (inf_ms / 1000.0) / duration_sec

        rating = "Fast" if rtf < 0.20 else ("Balanced" if rtf < 0.50 else "Slow")
        return {
            "model": model_name,
            "duration_sec": duration_sec,
            "threads": threads,
            "load_ms": round(load_ms, 1),
            "latency_ms": round(inf_ms, 1),
            "rtf": round(rtf, 3),
            "rating": rating,
            "power_tip": get_power_status_tip()
        }
    except Exception as ex:
        return {"error": str(ex), "rtf": 0.0, "latency_ms": 0.0}


def resolve_whisper_model_path(model_name: str) -> Tuple[str, bool]:
    """
    Resolves local offline directory for Whisper models in priority order:
    1. sys._MEIPASS / "ghostline" / "models" / model_name
    2. sys._MEIPASS / "models" / model_name
    3. project_root / "ghostline" / "models" / model_name
    4. %APPDATA% / Ghostline / models / model_name
    5. Fallback to model_name string (HF cache / download)
    Returns: (resolved_path_or_name: str, is_local_dir: bool)
    """
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.append(meipass / "ghostline" / "models" / model_name)
        candidates.append(meipass / "models" / model_name)

    exe_dir = Path(sys.executable).resolve().parent
    candidates.append(exe_dir / "ghostline" / "models" / model_name)
    candidates.append(exe_dir / "_internal" / "ghostline" / "models" / model_name)
    candidates.append(exe_dir / "models" / model_name)

    # Local repository models
    repo_model = Path(__file__).resolve().parent.parent / "models" / model_name
    candidates.append(repo_model)

    # APPDATA models
    try:
        app_model = get_app_dir() / "models" / model_name
        candidates.append(app_model)
    except Exception:
        pass

    for cand in candidates:
        if cand.exists() and (cand / "model.bin").exists():
            logging.info("[LiveTranscriber] Found offline Whisper model at: %s", cand)
            return str(cand), True

    return model_name, False


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
        cpu_threads: Optional[int] = None,
        on_segment: Optional[Callable[[TranscriptSegment], None]] = None,
        on_partial: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        faster_answers_enabled: bool = False
    ):
        self.model_name = model_name
        self.faster_answers_enabled = faster_answers_enabled
        self._language = language if language != "auto" else None
        self.output_guard = AudioOutputGuard(language=self._language or "en")
        effective_chunk = chunk_duration_sec if chunk_duration_sec is not None else chunk_sec
        self.chunk_sec = max(1.0, min(10.0, effective_chunk))
        self.overlap_sec = max(0.2, min(1.0, overlap_sec))
        self.max_history_items = max_history_items
        self.cpu_threads = cpu_threads or get_optimal_stt_threads()
        self.on_segment = on_segment
        self.on_partial = on_partial
        self.on_status = on_status

        self.model: Optional[Any] = None
        self.model_device: str = "cpu"
        self.is_loading = False
        self.is_running = False
        self.is_paused = False
        self.load_time_ms: float = 0.0

        self._lock = threading.Lock()
        self._segment_counter = 0

        # Rolling buffers (16 kHz float32)
        self._sample_rate = 16000
        self._chunk_samples = int(self.chunk_sec * self._sample_rate)
        self._overlap_samples = int(self.overlap_sec * self._sample_rate)

        self._call_buffer = np.zeros(0, dtype=np.float32)
        self._mic_buffer = np.zeros(0, dtype=np.float32)

        # Worker thread & Fair dual queues (bounded maxlen=25)
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._call_queue: deque = deque(maxlen=25)
        self._mic_queue: deque = deque(maxlen=25)
        self._last_chunk_time: Dict[str, float] = {"call": 0.0, "mic": 0.0}
        self._last_partial_emit: Dict[str, float] = {"call": 0.0, "mic": 0.0}
        self._is_catching_up: bool = False

        # Transcript history & Telemetry
        self.history: deque[TranscriptSegment] = deque(maxlen=self.max_history_items)
        self.last_transcription_time: float = 0.0
        self.last_transcription_text: str = ""
        self.last_error: str = ""
        self._last_emitted_text: Dict[str, str] = {"call": "", "mic": ""}
        self._last_partial_text: Dict[str, str] = {"call": "", "mic": ""}

    @property
    def language(self) -> Optional[str]:
        return self._language

    @language.setter
    def language(self, val: Optional[str]):
        self._language = val if val != "auto" else None
        if hasattr(self, "output_guard"):
            self.output_guard.set_language(self._language or "en")

    @property
    def audio_queue(self):
        """Backward-compatible view of pending audio chunks across both queues."""
        with self._lock:
            q = deque()
            q.extend(self._call_queue)
            q.extend(self._mic_queue)
            return q

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns transcription engine status telemetry."""
        return {
            "model_name": self.model_name,
            "model_device": self.model_device,
            "cpu_threads": self.cpu_threads,
            "load_time_ms": self.load_time_ms,
            "is_ready": self.model is not None,
            "is_loading": self.is_loading,
            "is_running": self.is_running,
            "last_text": self.last_transcription_text,
            "last_time": self.last_transcription_time,
            "last_error": self.last_error,
            "total_segments": len(self.history)
        }

    def initialize_model(
        self,
        model_name: Optional[str] = None,
        force_cpu: bool = False,
        cpu_threads: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Loads or reloads the local Whisper transcription model with hardware acceleration or CPU fallback."""
        with self._lock:
            if model_name:
                self.model_name = model_name
            if cpu_threads:
                self.cpu_threads = cpu_threads

            if not HAVE_FASTER_WHISPER:
                err = "faster-whisper library is not installed."
                self._notify_status(f"Error: {err}")
                return False, err

            self.is_loading = True
            self._notify_status(f"Loading Whisper '{self.model_name}'...")

        record_timing_mark("stt_model_load_start", {"model": self.model_name})
        t_load0 = time.perf_counter()

        telemetry = get_audio_telemetry()
        model_target, is_local = resolve_whisper_model_path(self.model_name)

        # Detect optimal device outside lock
        device = "cpu"
        compute_type = "int8"
        if not force_cpu and HAVE_TORCH and hasattr(torch, "cuda") and torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"

        try:
            threads = self.cpu_threads or get_optimal_stt_threads()
            logging.info("[LiveTranscriber] Initializing model='%s' (resolved='%s', local=%s), device='%s', compute_type='%s', threads=%d",
                         self.model_name, model_target, is_local, device, compute_type, threads)
            extra_kwargs = {"local_files_only": True} if is_local else {}
            loaded_model = WhisperModel(
                model_target,
                device=device,
                compute_type=compute_type,
                cpu_threads=threads,
                **extra_kwargs
            )
            load_ms = (time.perf_counter() - t_load0) * 1000.0

            # Default language to English (or configured language) to skip redundant 300-token language classification
            orig_transcribe = loaded_model.transcribe
            def default_lang_transcribe(*args, **kwargs):
                if "language" not in kwargs or kwargs["language"] is None:
                    eff_lang = self._language or "en"
                    if eff_lang != "auto":
                        kwargs["language"] = eff_lang
                return orig_transcribe(*args, **kwargs)
            loaded_model.transcribe = default_lang_transcribe

            # Warm up model graphs, encoder/decoder, and Silero VAD so subsequent inference is immediately warm
            try:
                warmup_sig = np.zeros(8000, dtype=np.float32)
                _ = list(loaded_model.transcribe(warmup_sig, beam_size=1, temperature=0.0, vad_filter=False)[0])
                _ = list(loaded_model.transcribe(warmup_sig, beam_size=1, temperature=0.0, vad_filter=True)[0])
            except Exception:
                pass

            with self._lock:
                self.model = loaded_model
                self.model_device = device
                self.is_loading = False
                self.load_time_ms = round(load_ms, 1)

            record_timing_mark("stt_model_load_end", {"model": self.model_name, "duration_ms": self.load_time_ms})
            try:
                from .timing import TimingManager
                TimingManager.get_instance().set_model_info(
                    engine="faster-whisper",
                    model=self.model_name,
                    compute=compute_type,
                    threads=threads,
                    load_ms=self.load_time_ms
                )
            except Exception:
                pass
            telemetry.record_stage("whisper_model_loaded", f"Loaded '{model_target}' on {device} ({self.load_time_ms:.1f}ms)")
            info_msg = f"Model Ready ({self.model_name} on {device.upper()})"
            self._notify_status(info_msg)
            return True, info_msg
        except Exception as ex:
            telemetry.record_stage("worker_exceptions", f"Model init failed on {device}: {ex}")
            logging.warning("[LiveTranscriber] Failed on %s: %s; falling back to CPU int8", device, ex)
            try:
                threads = self.cpu_threads or get_optimal_stt_threads()
                extra_kwargs = {"local_files_only": True} if is_local else {}
                loaded_model = WhisperModel(
                    model_target,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=threads,
                    **extra_kwargs
                )
                load_ms = (time.perf_counter() - t_load0) * 1000.0

                # Default language to English (or configured language) to skip redundant 300-token language classification
                orig_transcribe = loaded_model.transcribe
                def default_lang_transcribe_cpu(*args, **kwargs):
                    if "language" not in kwargs or kwargs["language"] is None:
                        eff_lang = self._language or "en"
                        if eff_lang != "auto":
                            kwargs["language"] = eff_lang
                    return orig_transcribe(*args, **kwargs)
                loaded_model.transcribe = default_lang_transcribe_cpu

                # Warm up model graphs, encoder/decoder, and Silero VAD so subsequent inference is immediately warm
                try:
                    warmup_sig = np.zeros(8000, dtype=np.float32)
                    _ = list(loaded_model.transcribe(warmup_sig, beam_size=1, temperature=0.0, vad_filter=False)[0])
                    _ = list(loaded_model.transcribe(warmup_sig, beam_size=1, temperature=0.0, vad_filter=True)[0])
                except Exception:
                    pass

                with self._lock:
                    self.model = loaded_model
                    self.model_device = "cpu"
                    self.is_loading = False
                    self.load_time_ms = round(load_ms, 1)

                record_timing_mark("stt_model_load_end", {"model": self.model_name, "duration_ms": self.load_time_ms})
                try:
                    from .timing import TimingManager
                    TimingManager.get_instance().set_model_info(
                        engine="faster-whisper",
                        model=self.model_name,
                        compute="int8",
                        threads=threads,
                        load_ms=self.load_time_ms
                    )
                except Exception:
                    pass
                telemetry.record_stage("whisper_model_loaded", f"Loaded '{model_target}' on CPU int8 ({self.load_time_ms:.1f}ms)")
                info_msg = f"Model Ready ({self.model_name} on CPU)"
                self._notify_status(info_msg)
                return True, info_msg
            except Exception as ex_cpu:
                with self._lock:
                    self.is_loading = False
                telemetry.record_stage("worker_exceptions", f"Fatal model init failure: {ex_cpu}")
                err_text = f"Model initialization failed: {ex_cpu}"
                self._notify_status(f"Error: {err_text}")
                return False, err_text

    def preload_in_background(self, on_complete: Optional[Callable[[bool, float], None]] = None):
        """
        Preloads the model asynchronously during startup and executes a warm-up inference
        so first-turn transcription latency has zero cold-start delay.
        """
        def _preload_worker():
            logging.info("[LiveTranscriber] Starting background model preload...")
            ok, msg = self.initialize_model()
            if ok and self.model is not None:
                try:
                    # Run 1-second silent warmup chunk
                    warmup_sig = np.zeros(16000, dtype=np.float32)
                    _ = list(self.model.transcribe(warmup_sig, beam_size=1, temperature=0.0)[0])
                    record_timing_mark("stt_warmup_end")
                    logging.info("[LiveTranscriber] Background preload and warmup completed.")
                except Exception as w_err:
                    logging.warning("[LiveTranscriber] Warmup chunk error: %s", w_err)
            if on_complete:
                try:
                    on_complete(ok, self.load_time_ms)
                except Exception:
                    pass

        t = threading.Thread(target=_preload_worker, daemon=True, name="Ghostline-STT-Preload")
        self._preload_thread = t
        t.start()
        return t

    def start(self):
        """Starts the background transcription worker."""
        if self.is_running:
            return

        record_timing_mark("listening_start")
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
            self._call_queue.clear()
            self._mic_queue.clear()

        self._notify_status("Idle")
        logging.info("[LiveTranscriber] Transcription worker stopped.")

    def pause(self):
        self.is_paused = True
        self._notify_status("Paused")

    def resume(self):
        self.is_paused = False
        self._notify_status("Live")

    def add_audio_chunk(self, chunk: np.ndarray, source: str):
        """Receives 16 kHz float32 audio chunk from AudioCaptureManager."""
        if self.is_paused or len(chunk) == 0:
            return
        record_timing_mark("audio_chunk_captured", {"source": source, "len": len(chunk)})
        with self._lock:
            if source == "mic":
                self._mic_queue.append((chunk, source))
            else:
                self._call_queue.append((chunk, source))

    def push_audio_chunk(self, chunk: np.ndarray, sample_rate: int = 16000, source: str = "call"):
        """Receives 16 kHz float32 audio chunk and pushes to appropriate queue."""
        if self.is_paused or len(chunk) == 0:
            return
        record_timing_mark("audio_chunk_captured", {"source": source, "len": len(chunk)})
        with self._lock:
            if source == "mic":
                self._mic_queue.append((chunk, source))
            else:
                self._call_queue.append((chunk, source))

    def get_transcript_history(self, limit: Optional[int] = None) -> List[TranscriptSegment]:
        with self._lock:
            items = list(self.history)
            if limit is not None and limit > 0:
                return items[-limit:]
            return items

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
        telemetry = get_audio_telemetry()
        if not hasattr(self, "_last_speech_time"):
            self._last_speech_time = {"call": 0.0, "mic": 0.0}
        if not hasattr(self, "_speech_start_time"):
            self._speech_start_time = {"call": 0.0, "mic": 0.0}

        loop_cycle = 0
        while not self._stop_event.is_set():
            loop_cycle += 1
            if self.model is None or self.is_loading:
                time.sleep(0.05)
                continue
            if loop_cycle % 50 == 0:
                telemetry.record_stage("transcriber_thread_alive", f"Loop cycle={loop_cycle}")

            try:
                chunks_to_process = []
                with self._lock:
                    # Check backlog policy: if queue is overflowing, drop silent chunks
                    q_len_mic = len(self._mic_queue)
                    q_len_call = len(self._call_queue)
                    if q_len_mic > 6 or q_len_call > 6:
                        if not self._is_catching_up:
                            self._is_catching_up = True
                            self._notify_status("Catching up...")

                        # Drain and filter out silence under backlog pressure
                        def _filter_backlog(q: deque) -> List[Tuple[np.ndarray, str]]:
                            kept = []
                            while q:
                                c, src = q.popleft()
                                rms_c = math.sqrt(float(np.mean(c ** 2))) if len(c) > 0 else 0.0
                                if rms_c >= 0.0003:
                                    kept.append((c, src))
                            return kept

                        chunks_to_process.extend(_filter_backlog(self._call_queue))
                        chunks_to_process.extend(_filter_backlog(self._mic_queue))
                    else:
                        if self._is_catching_up:
                            self._is_catching_up = False
                            self._notify_status("Live")

                        # Fair alternating dequeue
                        max_pull = max(q_len_call, q_len_mic)
                        for _ in range(max_pull):
                            if self._call_queue:
                                chunks_to_process.append(self._call_queue.popleft())
                            if self._mic_queue:
                                chunks_to_process.append(self._mic_queue.popleft())

                now = time.time()
                for chunk, source in chunks_to_process:
                    self._last_chunk_time[source] = now
                    chunk_rms = math.sqrt(float(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                    if chunk_rms >= 0.0003:
                        if self._speech_start_time.get(source, 0.0) <= 0.0:
                            self._speech_start_time[source] = now
                            record_timing_mark("vad_speech_start", {"source": source})
                        self._last_speech_time[source] = now

                    if source == "call":
                        self._call_buffer = np.concatenate([self._call_buffer, chunk])
                    else:
                        self._mic_buffer = np.concatenate([self._mic_buffer, chunk])

                # Process call buffer
                self._check_buffer_segmentation("call", now)

                # Process mic buffer
                self._check_buffer_segmentation("mic", now)

                if not chunks_to_process:
                    time.sleep(0.05)

            except Exception as loop_ex:
                telemetry.record_stage("worker_exceptions", f"Worker loop error: {loop_ex}")
                logging.error("[LiveTranscriber] Unexpected error in worker loop: %s", loop_ex, exc_info=True)
                self._notify_status(f"Worker Error: {loop_ex}")
                time.sleep(0.2)

    def _check_buffer_segmentation(self, source: str, now: float):
        """Evaluates speech boundaries, silence pauses, streaming partials, and hard cutoffs."""
        buf = self._call_buffer if source == "call" else self._mic_buffer
        buf_len = len(buf)
        speech_start = self._speech_start_time.get(source, 0.0)
        last_speech = self._last_speech_time.get(source, 0.0)

        if buf_len < int(0.50 * self._sample_rate):
            return

        speech_dur = (now - speech_start) if speech_start > 0 else 0.0
        silence_dur = (now - last_speech) if last_speech > 0 else 0.0

        # Adaptive silence threshold: 0.45s for questions, 0.60s default, clamped [0.35s, 1.20s]
        partial = self._last_partial_text.get(source, "").strip().lower()
        is_question_like = False
        if partial:
            if partial.endswith("?"):
                is_question_like = True
            else:
                q_starters = ("what", "how", "why", "when", "where", "who", "which", "can", "could", "would", "should", "is", "are", "do", "does", "did", "tell", "explain")
                words = partial.split()
                if words and words[0].strip(".,?!\"'") in q_starters:
                    is_question_like = True

        if getattr(self, "faster_answers_enabled", False) and is_question_like:
            silence_threshold = 0.35
        elif is_question_like:
            silence_threshold = 0.45
        else:
            silence_threshold = 0.60

        # Clamped strictly between 0.35s and 1.20s
        silence_threshold = max(0.35, min(1.20, silence_threshold))

        # Ignore brief breath pauses < 0.30s
        if silence_dur < 0.30:
            is_paused = False
        else:
            is_paused = (silence_dur >= silence_threshold) and last_speech > 0.0

        # Case 1: Hard continuous speech cutoff at 8.0s (find low-energy split boundary)
        if speech_dur >= 8.0 or buf_len >= (8.0 * self._sample_rate):
            split_idx = self._find_low_energy_split(buf)
            to_process = buf[:split_idx]
            remaining = buf[split_idx:]
            with self._lock:
                if source == "call":
                    self._call_buffer = to_process
                else:
                    self._mic_buffer = to_process
            self._process_buffer(source, is_flush=True)
            with self._lock:
                if source == "call":
                    self._call_buffer = remaining
                else:
                    self._mic_buffer = remaining
            self._speech_start_time[source] = now
            return

        # Case 2: Silence pause detected following active speech
        if is_paused and buf_len >= int(0.50 * self._sample_rate):
            record_timing_mark("speech_end", {"source": source, "t": last_speech})
            record_timing_mark("endpoint_decided", {
                "source": source,
                "silence_dur": round(silence_dur, 3),
                "threshold": silence_threshold,
                "is_question": is_question_like
            })
            self._process_buffer(source, is_flush=True)
            self._last_speech_time[source] = 0.0
            self._speech_start_time[source] = 0.0
            self._last_partial_text[source] = ""
            return

        # Case 3: Streaming partial preview every 0.9s–1.2s during active speech
        if speech_dur >= 1.0 and (now - self._last_partial_emit.get(source, 0.0) >= 1.0):
            self._emit_partial_preview(source, buf)
            self._last_partial_emit[source] = now

    def _find_low_energy_split(self, buf: np.ndarray) -> int:
        """Finds the lowest RMS energy 100ms window in the 6.0s–8.0s region to avoid cutting words."""
        total_len = len(buf)
        min_split = int(5.5 * self._sample_rate)
        max_split = min(total_len, int(8.0 * self._sample_rate))
        if total_len <= min_split:
            return total_len

        win_size = int(0.10 * self._sample_rate)  # 100ms
        best_idx = max_split
        lowest_rms = 1e9

        # Stride through candidate split windows
        for i in range(min_split, max_split - win_size, int(0.05 * self._sample_rate)):
            win = buf[i:i + win_size]
            rms = float(np.mean(win ** 2))
            if rms < lowest_rms:
                lowest_rms = rms
                best_idx = i + (win_size // 2)

        return best_idx

    def _emit_partial_preview(self, source: str, buf: np.ndarray):
        """Emits an in-flight partial transcription preview without advancing final state."""
        if self.model is None or self.is_paused or len(buf) < int(0.60 * self._sample_rate):
            return

        # Quick preview on active audio
        try:
            preview_audio = buf[-int(4.0 * self._sample_rate):] if len(buf) > int(4.0 * self._sample_rate) else buf
            preview_audio = np.nan_to_num(preview_audio.copy(), nan=0.0, posinf=1.0, neginf=-1.0)
            np.clip(preview_audio, -1.0, 1.0, out=preview_audio)

            segments, _ = self.model.transcribe(
                preview_audio,
                language=self.language,
                beam_size=1,
                temperature=0.0,
                condition_on_previous_text=False
            )
            partial_text = " ".join([s.text.strip() for s in segments if s.text.strip()]).strip()
            if partial_text and len(partial_text) >= 2:
                # Cap at 200 characters for partial previews
                if len(partial_text) > 200:
                    partial_text = partial_text[:197] + "…"
                # Drop repetition loops or script mismatches from partial preview
                if self.output_guard.check_repetition(partial_text) or self.output_guard.check_script_mismatch(partial_text):
                    return
                self._last_partial_text[source] = partial_text
                record_timing_mark("stt_partial", {"source": source, "text": partial_text[:40]})
                if self.on_partial is not None:
                    try:
                        self.on_partial(partial_text, source)
                    except Exception:
                        pass
        except Exception as p_err:
            logging.debug("[LiveTranscriber] Partial preview error (ignored): %s", p_err)

    def _deduplicate_overlap(self, prev_text: str, current_text: str) -> str:
        """Removes repeated words or overlapping prefixes between consecutive segments."""
        prev_words = prev_text.strip().split()
        curr_words = current_text.strip().split()
        if not prev_words or not curr_words:
            return current_text.strip()

        max_k = min(len(prev_words), len(curr_words))
        for k in range(max_k, 1, -1):
            if [w.lower().strip(".,?!\"'") for w in prev_words[-k:]] == [w.lower().strip(".,?!\"'") for w in curr_words[:k]]:
                remaining = curr_words[k:]
                return " ".join(remaining).strip()

        if len(curr_words) == 1 and len(prev_words) >= 1:
            if curr_words[0].lower().strip(".,?!\"'") == prev_words[-1].lower().strip(".,?!\"'"):
                return ""

        return current_text.strip()

    def _process_buffer(self, source: str, is_flush: bool = False):
        """Transcribes accumulated buffer for a given source."""
        if self.model is None or self.is_paused:
            return

        buf = self._call_buffer if source == "call" else self._mic_buffer
        if len(buf) < int(0.50 * self._sample_rate):
            return

        # Energy Gate: Skip completely silent buffers
        rms = math.sqrt(float(np.mean(buf ** 2)))
        if rms < 0.0003:
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

        telemetry = get_audio_telemetry()
        speaker_tag = "[Call]" if source in ("system", "call") else "[You]"
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

        record_timing_mark("stt_start", {"source": source, "dur_sec": round(len(audio_to_transcribe)/16000.0, 2)})
        t_start = time.perf_counter()

        try:
            telemetry.record_stage("transcribe_called", f"Source={source}, Dur={len(audio_to_transcribe)/16000:.2f}s, RMS={rms:.4f}")
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

            seg_list = list(segments)
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            dur_sec = len(audio_to_transcribe) / 16000.0
            record_segment_metric(source, dur_sec, latency_ms)

            telemetry.record_stage("segments_returned", f"Source={source}, SegCount={len(seg_list)}, Latency={latency_ms:.1f}ms")

            for seg in seg_list:
                no_speech_prob = getattr(seg, "no_speech_prob", None)
                avg_logprob = getattr(seg, "avg_logprob", None)
                if isinstance(no_speech_prob, (int, float)) and no_speech_prob > 0.8:
                    logging.debug("[LiveTranscriber] Dropped high no-speech-prob segment (%.2f): %s", no_speech_prob, seg.text)
                    continue
                if isinstance(avg_logprob, (int, float)) and avg_logprob < -1.8:
                    logging.debug("[LiveTranscriber] Dropped low-confidence segment (%.2f): %s", avg_logprob, seg.text)
                    continue

                raw_text = seg.text.strip()
                if not raw_text or len(raw_text) < 2:
                    continue

                if self.on_partial is not None:
                    try:
                        self.on_partial(raw_text, source)
                    except Exception:
                        pass

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

                record_timing_mark("stt_final", {
                    "source": source,
                    "text": text[:40],
                    "latency_ms": round(latency_ms, 1),
                    "rtf": round((latency_ms / 1000.0) / max(0.1, dur_sec), 3)
                })
                telemetry.record_stage("non_empty_text", f"Source={source}, text='{text}'")

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

                if self.on_segment is not None:
                    try:
                        self.on_segment(segment_obj)
                        telemetry.record_stage("on_segment_callback_fired", f"Segment ID={segment_obj.id}, Text='{text[:40]}'")
                    except Exception as cb_err:
                        logging.error("[LiveTranscriber] on_segment callback error: %s", cb_err)

                self._notify_status(f"Live ({detected_lang})")

        except Exception as ex:
            self.last_error = str(ex)
            telemetry.record_stage("worker_exceptions", f"Transcribe error: {ex}")
            logging.error("[LiveTranscriber] Transcription segment error: %s", ex, exc_info=True)
            self._notify_status(f"Transcription failed: {ex}")

    def _notify_status(self, status: str):
        if self.on_status is not None:
            try:
                self.on_status(status)
            except Exception:
                pass
