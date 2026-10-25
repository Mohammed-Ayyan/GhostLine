"""
Ghostline Audio Engine
Production-grade dual-source audio capture (WASAPI Loopback + Microphone)
and local speech-to-text transcription with context-aware Ollama AI assistance.
"""

from ghostline.audio.capture import AudioCaptureManager, AudioDeviceManager
from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant

__all__ = [
    "AudioCaptureManager",
    "AudioDeviceManager",
    "LiveTranscriber",
    "TranscriptSegment",
    "LiveAudioAssistant",
]
