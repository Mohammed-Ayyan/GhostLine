"""
Unit tests for Ghostline Live Audio Transcription subsystem.
Tests TranscriptSegment data model, chunk queuing, rolling buffers, VAD/silence gating,
history retention, export formats, and mock Whisper transcription.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from ghostline.audio.transcription import (
    TranscriptSegment,
    LiveTranscriber,
    HAVE_FASTER_WHISPER
)


class TestTranscriptSegment(unittest.TestCase):
    def test_segment_creation(self):
        seg = TranscriptSegment(
            id=1,
            timestamp=1000.0,
            time_str="12:00:00",
            source="call",
            speaker_label="[Call]",
            text="Could you explain the latency trade-offs of WASAPI loopback?",
            language="en",
            confidence=0.95,
            is_final=True
        )
        self.assertEqual(seg.id, 1)
        self.assertEqual(seg.source, "call")
        self.assertEqual(seg.speaker_label, "[Call]")
        self.assertTrue(seg.is_final)
        self.assertIn("latency trade-offs", seg.text)


class TestLiveTranscriber(unittest.TestCase):
    def setUp(self):
        self.partials = []
        self.segments = []

        def _on_partial(text, src):
            self.partials.append((text, src))

        def _on_segment(seg):
            self.segments.append(seg)

        self.transcriber = LiveTranscriber(
            model_name="tiny",
            language="auto",
            chunk_duration_sec=1.0,
            max_history_items=50,
            on_partial=_on_partial,
            on_segment=_on_segment
        )

    def tearDown(self):
        if self.transcriber.is_running:
            self.transcriber.stop()

    def test_initial_state(self):
        self.assertFalse(self.transcriber.is_running)
        self.assertFalse(self.transcriber.is_paused)
        self.assertEqual(self.transcriber.model_name, "tiny")
        self.assertIsNone(self.transcriber.language)
        self.assertEqual(len(self.transcriber.get_transcript_history()), 0)

    def test_push_audio_chunk(self):
        raw_samples = np.zeros(16000, dtype=np.float32)
        self.transcriber.push_audio_chunk(raw_samples, sample_rate=16000, source="call")
        self.assertGreater(len(self.transcriber.audio_queue), 0)

    def test_silence_detection(self):
        # Pure zeros should have near-zero RMS energy
        silence = np.zeros(16000, dtype=np.float32)
        rms = np.sqrt(np.mean(silence ** 2))
        self.assertEqual(rms, 0.0)

        # Active speech signal
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        speech = (np.sin(2 * np.pi * 300 * t) * 0.2).astype(np.float32)
        speech_rms = np.sqrt(np.mean(speech ** 2))
        self.assertGreater(speech_rms, 0.05)

    def test_history_bounded_retention(self):
        # Push 60 segments when max_history_items=50
        for i in range(60):
            seg = TranscriptSegment(
                id=i + 1,
                timestamp=100.0 + i,
                time_str="10:00:00",
                source="call" if i % 2 == 0 else "mic",
                speaker_label="[Call]" if i % 2 == 0 else "[You]",
                text=f"Sample utterance {i + 1}",
                language="en",
                is_final=True
            )
            self.transcriber._record_segment(seg)

        history = self.transcriber.get_transcript_history()
        self.assertEqual(len(history), 50)
        # Oldest items (1-10) should have rolled off, first item should be id=11
        self.assertEqual(history[0].id, 11)
        self.assertEqual(history[-1].id, 60)

    def test_clear_transcript(self):
        seg = TranscriptSegment(
            id=1, timestamp=100.0, time_str="10:00:00",
            source="call", speaker_label="[Call]", text="Test text", is_final=True
        )
        self.transcriber._record_segment(seg)
        self.assertEqual(len(self.transcriber.get_transcript_history()), 1)

        self.transcriber.clear()
        self.assertEqual(len(self.transcriber.get_transcript_history()), 0)

    def test_export_transcript_txt(self):
        seg = TranscriptSegment(
            id=1, timestamp=100.0, time_str="12:34:56",
            source="call", speaker_label="[Call]", text="Hello from remote call", is_final=True
        )
        self.transcriber._record_segment(seg)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = f.name

        try:
            res = self.transcriber.export_transcript(temp_path)
            self.assertTrue(res)
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[12:34:56] [Call] Hello from remote call", content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_export_transcript_json(self):
        seg = TranscriptSegment(
            id=1, timestamp=100.0, time_str="12:34:56",
            source="mic", speaker_label="[You]", text="I am answering now", is_final=True
        )
        self.transcriber._record_segment(seg)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            res = self.transcriber.export_transcript(temp_path)
            self.assertTrue(res)
            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("transcript", data)
            self.assertEqual(len(data["transcript"]), 1)
            self.assertEqual(data["transcript"][0]["text"], "I am answering now")
            self.assertEqual(data["transcript"][0]["source"], "mic")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_mock_transcribe_buffer(self):
        # Mock WhisperModel inference to test segment creation and callback dispatch
        mock_model = MagicMock()
        mock_seg = MagicMock()
        mock_seg.text = "Can we use faster-whisper on CPU?"
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98

        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        self.transcriber.model = mock_model

        audio = np.ones(16000, dtype=np.float32) * 0.1
        self.transcriber._transcribe_buffer(audio, source="call")

        # Segment callback should have been dispatched
        self.assertEqual(len(self.segments), 1)
        res_seg = self.segments[0]
        self.assertEqual(res_seg.text, "Can we use faster-whisper on CPU?")
        self.assertEqual(res_seg.source, "call")
        self.assertEqual(res_seg.speaker_label, "[Call]")
        self.assertEqual(res_seg.language, "en")


if __name__ == "__main__":
    unittest.main()
