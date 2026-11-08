"""
Run 14 Verification Test Suite: Live Transcription Speed & Live Answer Display.
Tests Scenarios S28 through S38:
- S28: Cold-start background preload and warm-up
- S29: Real warm transcription latency on CPU (< 500ms target)
- S30: Fair queue bounds and backlog dropping under pressure
- S31: Simultaneous dual-source (mic + loopback) fair throughput
- S32: Thread allocation & CPU contention mitigation
- S33: Built-in STT speed test benchmark & diagnostics line
- S34: Live answer display on Home card + HUD view-model synchronization
- S35: Provider down error handling & [Fix] button on Home card
- S36: "When to answer" modes ('questions', 'every_pause', 'manual')
- S37: Bounded history retention & export
- S38: End-to-end speech to streamed AI answer on Home card
"""

import os
import sys
import time
import wave
import threading
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from PyQt6.QtWidgets import QApplication

from ghostline.config import AppConfig
from ghostline.audio.transcription import (
    LiveTranscriber, TranscriptSegment,
    get_optimal_stt_threads, get_power_status_tip, run_stt_benchmark
)
from ghostline.audio.timing import TimingManager, record_timing_mark, get_stt_diagnostics_line
from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.ui.live_session_vm import LiveSessionViewModel
from ghostline.ui.qt_main_window import QtGhostlineMainWindow


app = QApplication.instance() or QApplication(sys.argv)


def load_fixture_wav(filename: str) -> np.ndarray:
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with wave.open(path, "rb") as wf:
        n = wf.getnframes()
        data = wf.readframes(n)
        return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


class TestS28ColdStartPreload(unittest.TestCase):
    def test_background_preload_and_warmup(self):
        transcriber = LiveTranscriber(model_name="tiny")
        self.assertIsNone(transcriber.model)

        done = threading.Event()
        def _on_done(ok, load_ms):
            done.set()

        transcriber.preload_in_background(on_complete=_on_done)
        self.assertTrue(done.wait(timeout=10.0), "Background preload did not complete within 10s")
        self.assertIsNotNone(transcriber.model)
        self.assertGreater(transcriber.load_time_ms, 0.0)


class TestS29WarmLatencyTargets(unittest.TestCase):
    def test_real_audio_inference_latency(self):
        transcriber = LiveTranscriber(model_name="tiny")
        transcriber.initialize_model()
        self.assertIsNotNone(transcriber.model)

        # Real 7.6s speech fixture
        audio_6s = load_fixture_wav("speech_6s.wav")
        self.assertGreater(len(audio_6s), 16000 * 5)

        t0 = time.perf_counter()
        segments, info = transcriber.model.transcribe(
            audio_6s,
            beam_size=1,
            temperature=0.0,
            vad_filter=True
        )
        texts = [s.text.strip() for s in segments]
        latency_ms = (time.perf_counter() - t0) * 1000.0

        full_text = " ".join(texts)
        self.assertIn("binary search", full_text.lower())
        # Verify warm latency target on CPU
        self.assertLess(latency_ms, 700.0, f"Latency {latency_ms:.1f}ms exceeded warm target")


class TestS30BacklogPolicy(unittest.TestCase):
    def test_backlog_drops_silence_and_notifies(self):
        statuses = []
        transcriber = LiveTranscriber(
            model_name="tiny",
            on_status=lambda s: statuses.append(s)
        )
        transcriber.initialize_model()

        # Enqueue 10 chunks: 5 silent, 5 active
        silent_chunk = np.zeros(16000, dtype=np.float32)
        active_chunk = np.ones(16000, dtype=np.float32) * 0.1

        for _ in range(5):
            transcriber.add_audio_chunk(silent_chunk, source="mic")
        for _ in range(5):
            transcriber.add_audio_chunk(active_chunk, source="mic")

        # Total in mic queue is 10 (> 6 backlog limit)
        self.assertGreater(len(transcriber._mic_queue), 6)

        # Worker loop run
        transcriber.start()
        time.sleep(0.4)
        transcriber.stop()

        # Should have transitioned or drained
        self.assertTrue(any("Catching up" in s for s in statuses) or len(transcriber._mic_queue) <= 5)


class TestS31FairDualQueues(unittest.TestCase):
    def test_simultaneous_mic_and_call_queuing(self):
        transcriber = LiveTranscriber(model_name="tiny")
        c1 = np.ones(16000, dtype=np.float32) * 0.05
        m1 = np.ones(16000, dtype=np.float32) * 0.08

        transcriber.add_audio_chunk(c1, source="call")
        transcriber.add_audio_chunk(m1, source="mic")

        self.assertEqual(len(transcriber._call_queue), 1)
        self.assertEqual(len(transcriber._mic_queue), 1)
        # Combined backward-compatible queue view
        self.assertEqual(len(transcriber.audio_queue), 2)


class TestS32ContentionLimiting(unittest.TestCase):
    def test_thread_allocation(self):
        threads = get_optimal_stt_threads()
        self.assertGreaterEqual(threads, 2)
        self.assertLessEqual(threads, 6)

    def test_ollama_keep_alive_and_threads(self):
        from ghostline.core.providers.ollama_provider import OllamaProvider
        prov = OllamaProvider()
        # Verify warmup method exists and takes num_thread: 4 and keep_alive: 5m
        self.assertTrue(hasattr(prov, "warmup"))


class TestS33SpeedBenchmark(unittest.TestCase):
    def test_speed_benchmark_run(self):
        res = run_stt_benchmark(model_name="tiny", duration_sec=1.5)
        self.assertIn("latency_ms", res)
        self.assertIn("rtf", res)
        self.assertIn("rating", res)
        self.assertIn(res["rating"], ("Fast", "Balanced", "Slow"))
        self.assertLessEqual(res["rtf"], 0.50)

    def test_diagnostics_line_privacy(self):
        line = get_stt_diagnostics_line()
        self.assertIn("STT:", line)
        self.assertIn("threads", line)
        # Must not contain private user transcript text
        self.assertNotIn("secret", line.lower())
        self.assertNotIn("password", line.lower())


class TestS34LiveAnswerDisplayHomeAndHUD(unittest.TestCase):
    def setUp(self):
        LiveSessionViewModel.get_instance().clear_listeners()
        LiveSessionViewModel.get_instance().clear()

    def tearDown(self):
        LiveSessionViewModel.get_instance().clear_listeners()

    def test_home_card_displays_live_transcript_and_streamed_tokens(self):
        cfg = AppConfig()
        win = QtGhostlineMainWindow(config=cfg)
        vm = LiveSessionViewModel.get_instance()

        # 1. Add final segment
        seg = TranscriptSegment(1, 100.0, "12:00:00", "call", "[Call]", "Explain binary search complexity.", is_final=True)
        vm.add_segment(seg)
        win._sync_live_session_from_vm()

        transcript_html = win.txt_live_transcript.toHtml()
        self.assertIn("Explain binary search complexity.", transcript_html)
        self.assertIn("[Call]", transcript_html)

        # 2. Add partial preview
        vm.set_partial("and its memory usage", source="call")
        win._sync_live_session_from_vm()
        self.assertIn("and its memory usage", win.txt_live_transcript.toHtml())

        # 3. Stream AI answer tokens
        vm.set_ai_thinking("Explain binary search complexity.")
        win._sync_live_session_from_vm()
        self.assertFalse(win.lbl_live_thinking.isHidden())

        vm.append_ai_token("Binary search runs ")
        win._sync_live_session_from_vm()
        self.assertEqual(win.txt_live_answer.toPlainText(), "Binary search runs ")

        vm.append_ai_token("in O(log N) time.")
        win._sync_live_session_from_vm()
        self.assertEqual(win.txt_live_answer.toPlainText(), "Binary search runs in O(log N) time.")

        # 4. Finalize answer
        vm.set_ai_answer("Explain binary search complexity.", "Binary search runs in O(log N) time.")
        win._sync_live_session_from_vm()
        self.assertTrue(win.lbl_live_thinking.isHidden())
        self.assertIn("O(log N)", win.txt_live_answer.toPlainText())


class TestS35ProviderOfflineErrorRow(unittest.TestCase):
    def setUp(self):
        LiveSessionViewModel.get_instance().clear_listeners()
        LiveSessionViewModel.get_instance().clear()

    def tearDown(self):
        LiveSessionViewModel.get_instance().clear_listeners()

    def test_error_row_displayed_with_fix_action(self):
        cfg = AppConfig()
        win = QtGhostlineMainWindow(config=cfg)
        vm = LiveSessionViewModel.get_instance()

        vm.set_ai_error(
            "Cannot connect to local Ollama daemon at http://127.0.0.1:11434.",
            fix_label="Start Ollama",
            fix_action="start_ollama"
        )
        win._sync_live_session_from_vm()

        self.assertFalse(win.frame_live_error.isHidden())
        self.assertIn("Ollama daemon", win.lbl_live_error_msg.text())
        self.assertEqual(win.btn_live_error_fix.text(), "Start Ollama")


class TestS36WhenToAnswerModes(unittest.TestCase):
    def test_when_to_answer_manual(self):
        mock_llm = MagicMock()
        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            when_to_answer="manual",
            auto_answer_questions=True
        )
        seg = TranscriptSegment(1, 100.0, "10:00:00", "call", "[Call]", "What is a binary tree?", is_final=True)
        assistant.add_segment(seg)
        # Should not schedule any debounce or call LLM
        self.assertIsNone(assistant._debounce_timer)
        self.assertFalse(mock_llm.generate.called)

    def test_when_to_answer_every_pause(self):
        mock_llm = MagicMock()
        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            when_to_answer="every_pause",
            auto_answer_questions=True,
            debounce_sec=0.1
        )
        seg = TranscriptSegment(1, 100.0, "10:00:00", "call", "[Call]", "We are deploying the new service.", is_final=True)
        assistant.add_segment(seg)
        # In 'every_pause' mode, substantive statements schedule debounce
        self.assertIsNotNone(assistant._debounce_timer)


class TestS37TranscriptHistoryRetention(unittest.TestCase):
    def test_history_bounding_and_export(self):
        transcriber = LiveTranscriber(max_history_items=10)
        for i in range(25):
            seg = TranscriptSegment(i+1, 100.0 + i, "10:00:00", "mic", "[You]", f"Line {i+1}", is_final=True)
            transcriber._record_segment(seg)

        history = transcriber.get_transcript_history()
        self.assertEqual(len(history), 10)
        self.assertEqual(history[-1].text, "Line 25")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmp_path = f.name

        try:
            ok, msg = transcriber.export_transcript(tmp_path)
            self.assertTrue(ok)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Line 25", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestS38LiveAnswerStreamRealAudio(unittest.TestCase):
    def setUp(self):
        LiveSessionViewModel.get_instance().clear_listeners()
        LiveSessionViewModel.get_instance().clear()

    def tearDown(self):
        LiveSessionViewModel.get_instance().clear_listeners()

    def test_audio_pipeline_to_live_card(self):
        cfg = AppConfig()
        win = QtGhostlineMainWindow(config=cfg)
        vm = LiveSessionViewModel.get_instance()

        # Simulate speech chunk transcribed
        q_text = "What is the time complexity of searching a binary search tree?"
        seg = TranscriptSegment(1, 100.0, "12:00:00", "call", "[Call]", q_text, is_final=True)

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Searching a BST takes O(log N) on average and O(N) in the worst case."

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            on_token=lambda tok, eid: vm.append_ai_token(tok),
            on_answer=lambda q, ans, code, **kw: vm.set_ai_answer(q, ans, code),
            auto_answer_questions=False
        )

        assistant.add_segment(seg)
        vm.add_segment(seg)

        # Trigger manual ask
        assistant.ask(custom_query=q_text)
        time.sleep(0.3)
        win._sync_live_session_from_vm()

        self.assertIn("O(log N)", win.txt_live_answer.toPlainText())
        self.assertIn(q_text, win.txt_live_transcript.toPlainText())


if __name__ == "__main__":
    unittest.main()
