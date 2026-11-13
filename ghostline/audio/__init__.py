"""
Ghostline Audio Engine
Production-grade dual-source audio capture (WASAPI Loopback + Microphone)
and local speech-to-text transcription with context-aware Ollama AI assistance.
Uses lazy imports to prevent loading heavy torch/ctranslate2 neural runtimes on startup.
"""

from typing import Any

__all__ = [
    "AudioCaptureManager",
    "AudioDeviceManager",
    "LiveTranscriber",
    "TranscriptSegment",
    "LiveAudioAssistant",
]


def __getattr__(name: str) -> Any:
    if name in ("AudioCaptureManager", "AudioDeviceManager"):
        from ghostline.audio.capture import AudioCaptureManager, AudioDeviceManager
        if name == "AudioCaptureManager":
            return AudioCaptureManager
        return AudioDeviceManager
    if name in ("LiveTranscriber", "TranscriptSegment"):
        from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
        if name == "LiveTranscriber":
            return LiveTranscriber
        return TranscriptSegment
    if name == "LiveAudioAssistant":
        from ghostline.audio.assistant import LiveAudioAssistant
        return LiveAudioAssistant
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

