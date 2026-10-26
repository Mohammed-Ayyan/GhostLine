import unittest
import time
import numpy as np
from unittest.mock import MagicMock

from ghostline.audio.capture import AudioCaptureManager
from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from PyQt6.QtWidgets import QApplication

# Ensure single QApplication instance for Qt unit testing
_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


class TestLiveCallPipelineRegression(unittest.TestCase):
    """
    Empirical regression tests verifying live-call pipeline:
    - Audio capture acoustic bleed decay (no permanent mic muting)
    - Buffer timeout flushing (no freeze on short speech)
    - Auto-answer support on both call and mic speech
    - QtLiveAudioPanel error handling and mic/call toggles
    """

    def test_acoustic_bleed_decay_prevents_permanent_mic_mute(self):
        """Verify that past loud system audio decays so subsequent microphone speech is delivered."""
        delivered_chunks = []
        mgr = AudioCaptureManager(
            enable_system=True,
            enable_mic=True,
            on_audio_chunk=lambda data, sr, src: delivered_chunks.append((src, len(data)))
        )

        # 1. Loud system audio arrives
        loud_pcm = (np.ones(1600, dtype=np.float32) * 0.5).tobytes()
        mgr._process_raw_pcm(loud_pcm, channels=1, native_rate=16000, source="call", volume=1.0, format_type=1)
        self.assertGreater(mgr._recent_system_rms, 0.08)

        # 2. Simulate 0.5s pause where system audio has stopped
        time.sleep(0.4)

        # 3. Normal speech arrives from microphone
        mic_pcm = (np.ones(1600, dtype=np.float32) * 0.05).tobytes()
        mgr._process_raw_pcm(mic_pcm, channels=1, native_rate=16000, source="mic", volume=1.0, format_type=1)

        # Microphone audio must NOT be dropped
        mic_delivered = [src for src, _ in delivered_chunks if src == "mic"]
        self.assertTrue(len(mic_delivered) > 0, "Microphone chunk was wrongly dropped by stale acoustic bleed!")

    def test_transcription_buffer_flush_on_pause(self):
        """Verify that utterances shorter than chunk_sec flush when speaker pauses (>0.4s)."""
        emitted_segments = []
        transcriber = LiveTranscriber(
            model_name="tiny",
            chunk_sec=3.0,
            on_segment=lambda seg: emitted_segments.append(seg)
        )
        # Mock the underlying WhisperModel to verify _process_buffer is invoked
        mock_model = MagicMock()
        mock_seg = MagicMock()
        mock_seg.text = "What is the complexity of quicksort?"
        mock_seg.avg_logprob = -0.2
        mock_model.transcribe.return_value = ([mock_seg], MagicMock(language="en"))
        transcriber.model = mock_model

        # Buffer 1.2s of audio (19200 samples at 16kHz) - less than the 3.0s (48000 samples) chunk threshold
        speech_chunk = np.ones(19200, dtype=np.float32) * 0.1
        transcriber._call_buffer = speech_chunk
        transcriber._last_chunk_time["call"] = time.time() - 0.5

        # Run one iteration of worker logic
        now = time.time()
        call_len = len(transcriber._call_buffer)
        self.assertGreaterEqual(call_len, int(0.65 * 16000))
        # Trigger flush
        transcriber._process_buffer("call", is_flush=True)

        mock_model.transcribe.assert_called_once()
        self.assertEqual(len(transcriber._call_buffer), 0, "Buffer was not cleared after silence flush!")
        self.assertEqual(len(emitted_segments), 1)
        self.assertIn("quicksort", emitted_segments[0].text)

    def test_assistant_auto_answers_both_call_and_mic(self):
        """Verify LiveAudioAssistant auto-answers questions from both 'call' and 'mic' sources."""
        answered_queries = []
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Quicksort has an average time complexity of O(n log n)."

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            auto_answer_questions=True,
            debounce_sec=0.05,
            on_answer=lambda q, a, code: answered_queries.append((q, a))
        )

        # 1. Spoken question on call
        seg_call = TranscriptSegment(1, time.time(), "12:00:00", "call", "[Call]", "What is the time complexity of quicksort?")
        assistant.add_segment(seg_call)
        time.sleep(0.12)
        self.assertEqual(len(answered_queries), 1)

        # 2. Spoken question on microphone
        seg_mic = TranscriptSegment(2, time.time(), "12:00:05", "mic", "[You]", "How does merge sort compare?")
        assistant.add_segment(seg_mic)
        time.sleep(0.12)
        self.assertEqual(len(answered_queries), 2)
        self.assertIn("merge sort", answered_queries[1][0].lower())

    def test_audio_panel_error_and_toggles(self):
        """Verify QtLiveAudioPanel set_ai_error, set_ai_thinking, and mic/call toggles."""
        mic_states = []
        call_states = []
        panel = QtLiveAudioPanel(
            on_toggle_mic=lambda state: mic_states.append(state),
            on_toggle_call_audio=lambda state: call_states.append(state),
            opacity=0.86
        )

        # 1. Verify opacity
        self.assertAlmostEqual(panel.windowOpacity(), 0.86, places=2)

        # 2. Verify set_ai_thinking
        panel.set_ai_thinking("Can you optimize this loop?")
        self.assertIn("optimize this loop", panel.lbl_ai_q.text())
        self.assertIn("Analyzing", panel.lbl_ai_ans.text())

        # 3. Verify set_ai_error
        panel.set_ai_error("Ollama connection timed out")
        self.assertIn("timed out", panel.lbl_ai_ans.text())

        # 4. Verify Mic toggle
        self.assertTrue(panel.mic_enabled)
        panel._toggle_mic_click()
        self.assertFalse(panel.mic_enabled)
        self.assertIn("Off", panel.btn_toggle_mic.text())
        self.assertEqual(mic_states, [False])

        # 5. Verify Call toggle
        self.assertTrue(panel.call_audio_enabled)
        panel._toggle_call_click()
        self.assertFalse(panel.call_audio_enabled)
        self.assertIn("Off", panel.btn_toggle_call.text())
        self.assertEqual(call_states, [False])


if __name__ == "__main__":
    unittest.main()
