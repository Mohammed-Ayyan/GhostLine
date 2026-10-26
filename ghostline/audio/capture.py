import sys
import time
import math
import logging
import threading
from typing import Optional, Dict, List, Any, Callable, Tuple
import numpy as np

try:
    from scipy.signal import resample_poly
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

# Try importing pyaudiowpatch, then pyaudio
try:
    import pyaudiowpatch as pyaudio
    HAVE_LOOPBACK_SUPPORT = True
except ImportError:
    try:
        import pyaudio
        HAVE_LOOPBACK_SUPPORT = False
    except ImportError:
        pyaudio = None
        HAVE_LOOPBACK_SUPPORT = False

TARGET_SAMPLE_RATE = 16000  # Standard rate for Whisper transcription


class AudioDeviceManager:
    """Discovers and enumerates Windows audio devices for WASAPI Loopback and Microphone."""

    @staticmethod
    def is_available() -> bool:
        return pyaudio is not None

    @staticmethod
    def get_devices() -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns:
            {
                "loopback": [{"index": int, "name": str, "channels": int, "sample_rate": int, "is_default": bool}],
                "mic": [{"index": int, "name": str, "channels": int, "sample_rate": int, "is_default": bool}]
            }
        """
        if pyaudio is None:
            return {"loopback": [], "mic": []}

        loopback_devices = []
        mic_devices = []

        p = None
        try:
            p = pyaudio.PyAudio()
            wasapi_index = None
            try:
                wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                wasapi_index = wasapi_info["index"]
            except Exception:
                pass

            default_loopback_name = ""
            default_loopback_idx = None
            if HAVE_LOOPBACK_SUPPORT and hasattr(p, "get_default_wasapi_loopback"):
                try:
                    def_loop = p.get_default_wasapi_loopback()
                    default_loopback_name = def_loop.get("name", "")
                    default_loopback_idx = def_loop.get("index")
                except Exception:
                    pass

            default_mic_idx = None
            try:
                def_mic = p.get_default_input_device_info()
                default_mic_idx = def_mic.get("index")
            except Exception:
                pass

            for i in range(p.get_device_count()):
                try:
                    dev = p.get_device_info_by_index(i)
                except Exception:
                    continue

                dev_name = dev.get("name", "")
                is_loop = dev.get("isLoopbackDevice", False) or "[Loopback]" in dev_name
                host_api = dev.get("hostApi")

                # Detect loopback devices
                if is_loop or (wasapi_index is not None and host_api == wasapi_index and dev.get("maxInputChannels", 0) > 0 and "[loopback]" in dev_name.lower()):
                    loopback_devices.append({
                        "index": dev["index"],
                        "name": dev_name,
                        "channels": dev.get("maxInputChannels", 2),
                        "sample_rate": int(dev.get("defaultSampleRate", 48000)),
                        "is_default": (dev["index"] == default_loopback_idx or dev_name == default_loopback_name)
                    })
                # Detect standard microphone inputs
                elif dev.get("maxInputChannels", 0) > 0 and not is_loop:
                    mic_devices.append({
                        "index": dev["index"],
                        "name": dev_name,
                        "channels": dev.get("maxInputChannels", 1),
                        "sample_rate": int(dev.get("defaultSampleRate", 44100)),
                        "is_default": (dev["index"] == default_mic_idx)
                    })
        except Exception as ex:
            logging.warning("[AudioDeviceManager] Device enumeration error: %s", ex)
        finally:
            if p is not None:
                try:
                    p.terminate()
                except Exception:
                    pass

        return {"loopback": loopback_devices, "mic": mic_devices}

    @classmethod
    def get_default_wasapi_loopback(cls) -> Optional[Dict[str, Any]]:
        devs = cls.get_devices().get("loopback", [])
        for d in devs:
            if d.get("is_default"):
                return d
        return devs[0] if devs else None

    @classmethod
    def get_default_microphone(cls) -> Optional[Dict[str, Any]]:
        devs = cls.get_devices().get("mic", [])
        for d in devs:
            if d.get("is_default"):
                return d
        return devs[0] if devs else None


class AudioCaptureManager:
    """
    Dual-source audio capture engine for Ghostline.
    Captures Windows system audio (WASAPI loopback) and microphone input concurrently,
    converts audio to 16 kHz mono float32, and delivers chunks via streaming callback.
    """

    def __init__(
        self,
        enable_system: bool = True,
        enable_mic: bool = True,
        system_enabled: Optional[bool] = None,
        mic_enabled: Optional[bool] = None,
        system_device_index: Optional[int] = None,
        mic_device_index: Optional[int] = None,
        system_volume: float = 1.0,
        mic_volume: float = 1.0,
        chunk_duration_sec: float = 2.0,
        save_recordings: bool = False,
        recording_path: Optional[str] = None,
        on_audio_chunk: Optional[Callable[..., None]] = None,
        on_level_update: Optional[Callable[[str, float, float], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None
    ):
        self.enable_system = system_enabled if system_enabled is not None else enable_system
        self.enable_mic = mic_enabled if mic_enabled is not None else enable_mic
        self.system_device_index = system_device_index
        self.mic_device_index = mic_device_index
        self.system_volume = max(0.0, min(2.0, system_volume))
        self.mic_volume = max(0.0, min(2.0, mic_volume))
        self.chunk_duration_sec = chunk_duration_sec
        self.save_recordings = save_recordings
        self.recording_path = recording_path
        self.on_audio_chunk = on_audio_chunk
        self.on_level_update = on_level_update
        self.on_status_change = on_status_change

        self.p: Optional[Any] = None
        self.stream_system: Optional[Any] = None
        self.stream_mic: Optional[Any] = None
        self.stream_system_format: int = pyaudio.paInt16 if pyaudio else 1
        self.stream_mic_format: int = pyaudio.paInt16 if pyaudio else 1

        self.is_running = False
        self.is_paused = False
        self._lock = threading.RLock()

        # Telemetry & Live level metrics
        self.last_capture_time: Dict[str, float] = {"call": 0.0, "mic": 0.0}
        self.sample_counts: Dict[str, int] = {"call": 0, "mic": 0}
        self.current_levels: Dict[str, float] = {"call": 0.0, "mic": 0.0}
        self.peak_levels: Dict[str, float] = {"call": 0.0, "mic": 0.0}
        self.active_device_names: Dict[str, str] = {"call": "None", "mic": "None"}

        # Energy tracking for duplicate / bleed suppression
        self._recent_system_rms = 0.0
        self._recent_mic_rms = 0.0

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns real-time audio capture diagnostics."""
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "system_enabled": self.enable_system,
            "mic_enabled": self.enable_mic,
            "active_devices": dict(self.active_device_names),
            "current_levels": dict(self.current_levels),
            "peak_levels": dict(self.peak_levels),
            "sample_counts": dict(self.sample_counts),
            "last_capture_time": dict(self.last_capture_time)
        }


    @property
    def is_capturing(self) -> bool:
        return self.is_running

    @property
    def system_enabled(self) -> bool:
        return self.enable_system

    @system_enabled.setter
    def system_enabled(self, val: bool):
        self.enable_system = bool(val)

    @property
    def mic_enabled(self) -> bool:
        return self.enable_mic

    @mic_enabled.setter
    def mic_enabled(self, val: bool):
        self.enable_mic = bool(val)

    def set_volume(self, source: str, volume: float):
        vol = max(0.0, min(2.0, float(volume)))
        if source in ("call", "system"):
            self.system_volume = vol
        elif source in ("mic", "microphone"):
            self.mic_volume = vol

    def toggle_pause(self) -> bool:
        self.is_paused = not self.is_paused
        return self.is_paused

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def _resample(self, audio: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
        return self._resample_audio(audio, orig_rate, target_rate)

    def _process_stream_buffer(self, samples: np.ndarray, sample_rate: int, source: str):
        if not self.is_paused and self.on_audio_chunk is not None:
            if sample_rate != TARGET_SAMPLE_RATE:
                samples = self._resample_audio(samples, sample_rate, TARGET_SAMPLE_RATE)
            try:
                self.on_audio_chunk(samples, TARGET_SAMPLE_RATE, source)
            except TypeError:
                self.on_audio_chunk(samples, source)

    def start(self) -> Tuple[bool, str]:
        """Starts audio capture streams on background workers."""
        with self._lock:
            if self.is_running:
                return True, "Capture already running."

            if pyaudio is None:
                msg = "PyAudio library not available. Install pyaudiowpatch."
                self._notify_status(msg)
                return False, msg

            try:
                self.p = pyaudio.PyAudio()
            except Exception as ex:
                msg = f"Failed to initialize PyAudio: {ex}"
                self._notify_status(msg)
                return False, msg

            success_sys = False
            success_mic = False
            errors = []

            # 1. Start System Audio (Loopback)
            if self.enable_system:
                try:
                    s_ok, s_err = self._start_system_stream()
                    if s_ok:
                        success_sys = True
                    else:
                        errors.append(f"System Audio: {s_err}")
                except Exception as ex_sys:
                    logging.exception(f"[AudioCaptureManager] Exception opening system stream: {ex_sys}")
                    errors.append(f"System Audio: {ex_sys}")

            # 2. Start Microphone Audio
            if self.enable_mic:
                try:
                    m_ok, m_err = self._start_mic_stream()
                    if m_ok:
                        success_mic = True
                    else:
                        errors.append(f"Microphone: {m_err}")
                except Exception as ex_mic:
                    logging.exception(f"[AudioCaptureManager] Exception opening mic stream: {ex_mic}")
                    errors.append(f"Microphone: {ex_mic}")

            if not success_sys and not success_mic:
                self.stop()
                err_text = "; ".join(errors) or "No audio sources could be opened."
                self._notify_status(f"Error: {err_text}")
                return False, err_text

            self.is_running = True
            self.is_paused = False
            status_text = "Recording" if (success_sys and success_mic) else ("Recording Call" if success_sys else "Recording Mic")
            self._notify_status(status_text)
            return True, status_text

    def stop(self):
        """Stops all streams and releases audio hardware."""
        with self._lock:
            self.is_running = False
            self.is_paused = False

            # Stop and close system stream
            if self.stream_system is not None:
                try:
                    if self.stream_system.is_active():
                        self.stream_system.stop_stream()
                    self.stream_system.close()
                except Exception:
                    pass
                self.stream_system = None

            # Stop and close mic stream
            if self.stream_mic is not None:
                try:
                    if self.stream_mic.is_active():
                        self.stream_mic.stop_stream()
                    self.stream_mic.close()
                except Exception:
                    pass
                self.stream_mic = None

            # Terminate PyAudio
            if self.p is not None:
                try:
                    self.p.terminate()
                except Exception:
                    pass
                self.p = None

            self._notify_status("Idle")

    def pause(self):
        """Pauses audio chunk processing without destroying streams."""
        with self._lock:
            self.is_paused = True
            self._notify_status("Paused")

    def resume(self):
        """Resumes audio chunk processing."""
        with self._lock:
            self.is_paused = False
            self._notify_status("Recording")

    def set_system_enabled(self, enabled: bool):
        """Toggles system audio capture dynamically."""
        with self._lock:
            self.enable_system = enabled
            if not self.is_running:
                return
        # Restart streams to apply source changes
        self.stop()
        self.start()

    def set_mic_enabled(self, enabled: bool):
        """Toggles microphone capture dynamically."""
        with self._lock:
            self.enable_mic = enabled
            if not self.is_running:
                return
        # Restart streams to apply source changes
        self.stop()
        self.start()

    def _start_system_stream(self) -> Tuple[bool, str]:
        """Initializes WASAPI Loopback stream."""
        try:
            device = None
            if self.system_device_index is not None:
                try:
                    device = self.p.get_device_info_by_index(self.system_device_index)
                except Exception:
                    device = None

            if device is None and HAVE_LOOPBACK_SUPPORT and hasattr(self.p, "get_default_wasapi_loopback"):
                try:
                    device = self.p.get_default_wasapi_loopback()
                except Exception:
                    device = None

            if device is None:
                # Fallback: scan for any device with [Loopback]
                for i in range(self.p.get_device_count()):
                    try:
                        d = self.p.get_device_info_by_index(i)
                        if "[loopback]" in d.get("name", "").lower():
                            device = d
                            break
                    except Exception:
                        continue

            if device is None:
                return False, "No WASAPI loopback device found on this system."

            self.active_device_names["call"] = device.get("name", "Unknown Loopback")
            channels = int(device.get("maxInputChannels", 2))
            rate = int(device.get("defaultSampleRate", 48000))

            def _system_callback(in_data, frame_count, time_info, status):
                if not self.is_running or self.is_paused or not in_data:
                    return (None, pyaudio.paContinue)
                self._process_raw_pcm(in_data, channels, rate, "call", self.system_volume, self.stream_system_format)
                return (None, pyaudio.paContinue)

            # Try paFloat32 first (native for WASAPI loopback on Windows), fallback to paInt16
            stream = None
            last_err = None
            for fmt in (pyaudio.paFloat32, pyaudio.paInt16):
                try:
                    stream = self.p.open(
                        format=fmt,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=device["index"],
                        stream_callback=_system_callback,
                        frames_per_buffer=1024
                    )
                    self.stream_system_format = fmt
                    break
                except Exception as ex:
                    last_err = ex

            if stream is None:
                raise last_err or RuntimeError("Failed to open WASAPI loopback stream.")

            self.stream_system = stream
            self.stream_system.start_stream()
            logging.info("[AudioCaptureManager] WASAPI Loopback started: %s (%d Hz, %d ch, fmt=%s)",
                         device["name"], rate, channels, "float32" if self.stream_system_format == pyaudio.paFloat32 else "int16")
            return True, "Loopback stream started"
        except Exception as ex:
            logging.warning("[AudioCaptureManager] Failed to start WASAPI loopback: %s", ex)
            return False, str(ex)

    def _start_mic_stream(self) -> Tuple[bool, str]:
        """Initializes standard Microphone stream."""
        try:
            device = None
            if self.mic_device_index is not None:
                try:
                    device = self.p.get_device_info_by_index(self.mic_device_index)
                except Exception:
                    device = None

            # Prioritize WASAPI default input device if available
            if device is None:
                try:
                    wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    def_wasapi_in = wasapi_info.get("defaultInputDevice")
                    if def_wasapi_in is not None and def_wasapi_in >= 0:
                        d = self.p.get_device_info_by_index(def_wasapi_in)
                        if not d.get("isLoopbackDevice", False):
                            device = d
                except Exception:
                    pass

            if device is None:
                try:
                    device = self.p.get_default_input_device_info()
                except Exception:
                    device = None

            if device is None:
                return False, "No microphone input device found."

            self.active_device_names["mic"] = device.get("name", "Unknown Mic")
            channels = min(2, max(1, int(device.get("maxInputChannels", 1))))
            rate = int(device.get("defaultSampleRate", 44100))

            def _mic_callback(in_data, frame_count, time_info, status):
                if not self.is_running or self.is_paused or not in_data:
                    return (None, pyaudio.paContinue)
                self._process_raw_pcm(in_data, channels, rate, "mic", self.mic_volume, self.stream_mic_format)
                return (None, pyaudio.paContinue)

            # Try paInt16 first, fallback to paFloat32
            stream = None
            last_err = None
            for fmt in (pyaudio.paInt16, pyaudio.paFloat32):
                try:
                    stream = self.p.open(
                        format=fmt,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=device["index"],
                        stream_callback=_mic_callback,
                        frames_per_buffer=1024
                    )
                    self.stream_mic_format = fmt
                    break
                except Exception as ex:
                    last_err = ex

            if stream is None:
                raise last_err or RuntimeError("Failed to open microphone stream.")

            self.stream_mic = stream
            self.stream_mic.start_stream()
            logging.info("[AudioCaptureManager] Microphone stream started: %s (%d Hz, %d ch, fmt=%s)",
                         device["name"], rate, channels, "float32" if self.stream_mic_format == pyaudio.paFloat32 else "int16")
            return True, "Microphone stream started"
        except Exception as ex:
            logging.warning("[AudioCaptureManager] Failed to start microphone: %s", ex)
            return False, str(ex)

    def _process_raw_pcm(self, pcm_bytes: bytes, channels: int, native_rate: int, source: str, volume: float, format_type: int = pyaudio.paInt16 if pyaudio else 1):
        """Converts raw integer or float PCM into normalized 16 kHz mono float32."""
        try:
            # 1. Convert to numpy float32 array based on stream format
            if format_type == getattr(pyaudio, "paFloat32", 1):
                audio_float = np.frombuffer(pcm_bytes, dtype=np.float32)
                if channels > 1:
                    rem = len(audio_float) % channels
                    if rem != 0:
                        audio_float = audio_float[:-rem]
                    audio_float = audio_float.reshape(-1, channels).mean(axis=1)
            else:
                audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
                if channels > 1:
                    rem = len(audio_int16) % channels
                    if rem != 0:
                        audio_int16 = audio_int16[:-rem]
                    audio_mono = audio_int16.reshape(-1, channels).mean(axis=1)
                else:
                    audio_mono = audio_int16
                audio_float = audio_mono.astype(np.float32) / 32768.0

            # 2. Apply volume gain
            if volume != 1.0:
                audio_float = audio_float * volume
                np.clip(audio_float, -1.0, 1.0, out=audio_float)

            # 3. Resample to 16 kHz target if necessary
            if native_rate != TARGET_SAMPLE_RATE:
                audio_resampled = self._resample_audio(audio_float, native_rate, TARGET_SAMPLE_RATE)
            else:
                audio_resampled = audio_float

            # Sanitize float audio to prevent NaN / Inf errors in VAD or Whisper
            audio_resampled = np.nan_to_num(audio_resampled, nan=0.0, posinf=1.0, neginf=-1.0)
            np.clip(audio_resampled, -1.0, 1.0, out=audio_resampled)

            # 4. Energy calculation and telemetry tracking
            rms = math.sqrt(float(np.mean(audio_resampled ** 2))) if len(audio_resampled) > 0 else 0.0
            peak = float(np.max(np.abs(audio_resampled))) if len(audio_resampled) > 0 else 0.0
            now = time.time()
            self.last_capture_time[source] = now
            self.sample_counts[source] = self.sample_counts.get(source, 0) + len(audio_resampled)
            self.current_levels[source] = rms
            self.peak_levels[source] = max(self.peak_levels.get(source, 0.0) * 0.95, peak)

            if self.on_level_update is not None:
                try:
                    self.on_level_update(source, rms, peak)
                except Exception:
                    pass

            if source == "call":
                self._recent_system_rms = rms
            elif source == "mic":
                self._recent_mic_rms = rms
                # Acoustic bleed suppression: only suppress if system audio was actively playing within the last 0.35s
                sys_is_recent = (now - self.last_capture_time.get("call", 0.0)) < 0.35
                if self.enable_system and sys_is_recent and self._recent_system_rms > 0.08 and rms < (self._recent_system_rms * 0.35):
                    return  # Suppress speaker acoustic bleed into microphone
                # Exponential decay of past system audio energy
                self._recent_system_rms *= 0.85

            # 5. Deliver chunk via callback safely supporting both 3-arg and 2-arg callbacks
            if self.on_audio_chunk is not None:
                try:
                    self.on_audio_chunk(audio_resampled, TARGET_SAMPLE_RATE, source)
                except TypeError:
                    self.on_audio_chunk(audio_resampled, source)
        except Exception as ex:
            logging.debug("[AudioCaptureManager] PCM processing error: %s", ex)


    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """High-efficiency audio resampling using resample_poly or linear interpolation."""
        if orig_sr == target_sr or len(audio) == 0:
            return audio

        if HAVE_SCIPY:
            gcd = math.gcd(orig_sr, target_sr)
            up = target_sr // gcd
            down = orig_sr // gcd
            return resample_poly(audio, up, down).astype(np.float32)

        # Fallback linear interpolation
        orig_indices = np.linspace(0, len(audio), len(audio), endpoint=False)
        target_len = int(len(audio) * target_sr / orig_sr)
        target_indices = np.linspace(0, len(audio), target_len, endpoint=False)
        return np.interp(target_indices, orig_indices, audio).astype(np.float32)

    def _notify_status(self, status: str):
        if self.on_status_change is not None:
            try:
                self.on_status_change(status)
            except Exception:
                pass

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
