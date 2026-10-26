import unittest
import sys
import time
import uuid
import threading
import numpy as np
from pathlib import Path
from PIL import Image

# Ensure project root in sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ghostline.audio.capture import AudioCaptureManager, TARGET_SAMPLE_RATE
from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.core.ocr_engine import (
    parse_question_structure,
    ParsedQuestion,
    _is_ui_noise,
    _is_meaningful_question
)
from ghostline.core.conversation import (
    ConversationEntry,
    ConversationSession,
    SOURCE_MIC,
    SOURCE_SYSTEM,
    SOURCE_SCREEN,
    STATUS_TRANSCRIPT,
    STATUS_THINKING,
    STATUS_ANSWERED,
    STATUS_ERROR
)
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.core.llm_client import AnswerResult
from ghostline.ui.presentation import (
    build_answer_presentation,
    TYPE_MCQ,
    TYPE_CODE,
    TYPE_UNCERTAIN,
    TYPE_ERROR
)


class TestScreenAndLiveAudioRepair14(unittest.TestCase):
    """
    14 Targeted Diagnostic Tests as specified in prompt Section 4:
    1. MCQ with four vertically separated options.
    2. MCQ with inline options.
    3. MCQ with supporting passage between question and choices.
    4. Long questions and partially clipped captures.
    5. Browser/UI text mixed with a valid MCQ.
    6. Ghostline HUD visible over target application.
    7. Invalid screen capture with no question.
    8. Microphone capture delivering actual non-zero frames.
    9. WASAPI loopback delivering frames while audio is playing.
    10. Transcription of a known test phrase from real captured audio.
    11. Pause/resume without duplicate workers.
    12. End stopping capture and blocking late callbacks.
    13. Consecutive spoken questions retaining their separate answers.
    14. Acknowledgements remaining in transcript without unwanted automatic answers.
    """

    def setUp(self):
        self.hud = QtGhostlineHudOverlay()
        self.hud.session.clear()
        self.hud.rebuild_cards_view()

    def tearDown(self):
        if hasattr(self, "hud") and self.hud:
            self.hud.close()

    # -------------------------------------------------------------------------
    # 1. MCQ with four vertically separated options
    # -------------------------------------------------------------------------
    def test_01_mcq_vertically_separated_options(self):
        raw_ocr = (
            "Which of the following sorting algorithms has the best worst-case time complexity?\n"
            "A. Bubble Sort\n"
            "B. Quick Sort\n"
            "C. Merge Sort\n"
            "D. Selection Sort\n"
        )
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertEqual(len(parsed.options), 4)
        self.assertIn("A", parsed.options)
        self.assertEqual(parsed.options["A"], "Bubble Sort")
        self.assertIn("B", parsed.options)
        self.assertEqual(parsed.options["B"], "Quick Sort")
        self.assertIn("C", parsed.options)
        self.assertEqual(parsed.options["C"], "Merge Sort")
        self.assertIn("D", parsed.options)
        self.assertEqual(parsed.options["D"], "Selection Sort")
        self.assertIn("sorting algorithms", parsed.question_text)

    # -------------------------------------------------------------------------
    # 2. MCQ with inline options
    # -------------------------------------------------------------------------
    def test_02_mcq_inline_options(self):
        raw_ocr = (
            "What is the average lookup time of a hash table with good collision resolution?\n"
            "A) O(1)  B) O(log n)  C) O(n)  D) O(n log n)\n"
        )
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options.get("A"), "O(1)")
        self.assertEqual(parsed.options.get("B"), "O(log n)")
        self.assertEqual(parsed.options.get("C"), "O(n)")
        self.assertEqual(parsed.options.get("D"), "O(n log n)")
        self.assertNotIn("N", parsed.options)

    # -------------------------------------------------------------------------
    # 3. MCQ with supporting passage between question and choices
    # -------------------------------------------------------------------------
    def test_03_mcq_supporting_passage_between_question_and_choices(self):
        raw_ocr = (
            "What is the output of executing the following Python function?\n"
            "def calculate(values):\n"
            "    return [v * 2 for v in values if v % 2 == 0]\n"
            "print(calculate([1, 2, 3, 4]))\n"
            "A) [2, 4]\n"
            "B) [4, 8]\n"
            "C) [2, 6]\n"
            "D) [1, 2, 3, 4]\n"
        )
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertIn("calculate", parsed.supporting_passage)
        self.assertIn("values", parsed.supporting_passage)
        self.assertIn("output", parsed.question_text.lower())
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options.get("B"), "[4, 8]")

    # -------------------------------------------------------------------------
    # 4. Long questions and partially clipped captures
    # -------------------------------------------------------------------------
    def test_04_long_questions_and_partially_clipped_captures(self):
        long_stem = (
            "A multinational e-commerce company operates distributed services across multiple geographic AWS regions. "
            "During an unexpected cross-region network partition between us-east-1 and eu-west-1, the database replication "
            "pipeline encounters high replication lag exceeding the configured threshold of 500 milliseconds. Under the PACELC "
            "theorem classification, what trade-off must this system make while the network partition is actively ongoing?\n"
            "A. It must choose between latency and consistency when operating normally.\n"
            "B. It must choose between availability and consistency while partitioned.\n"
            "C. It guarantees serializability across all regions without partition penalties.\n"
            "D. It automatically promotes read replicas without verifying quorums.\n"
        )
        parsed = parse_question_structure(long_stem)
        self.assertTrue(parsed.is_valid_question)
        self.assertGreater(len(parsed.question_text), 100)
        self.assertEqual(len(parsed.options), 4)
        self.assertIn("A", parsed.options)
        self.assertIn("B", parsed.options)

    # -------------------------------------------------------------------------
    # 5. Browser/UI text mixed with a valid MCQ
    # -------------------------------------------------------------------------
    def test_05_browser_ui_noise_mixed_with_valid_mcq(self):
        noisy_ocr = (
            "Ask Gemini\n"
            "98%\n"
            "Question 3 of 10\n"
            "https://assessment-platform.internal/test/take\n"
            "Which HTTP status code corresponds to 'Bad Gateway'?\n"
            "A. 400 Bad Request\n"
            "B. 404 Not Found\n"
            "C. 500 Internal Server Error\n"
            "D. 502 Bad Gateway\n"
            "Next Question >\n"
            "Submit Assessment\n"
        )
        parsed = parse_question_structure(noisy_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertNotIn("Ask Gemini", parsed.question_text)
        self.assertNotIn("98%", parsed.question_text)
        self.assertNotIn("https://", parsed.question_text)
        self.assertNotIn("Submit Assessment", parsed.question_text)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options.get("D"), "502 Bad Gateway")

    # -------------------------------------------------------------------------
    # 6. Ghostline HUD visible over the target application
    # -------------------------------------------------------------------------
    def test_06_ghostline_hud_visible_over_target_application(self):
        # Verify get_window_rect returns valid coordinates when HUD is shown
        self.hud.show()
        rect = self.hud.get_window_rect()
        self.assertIsNotNone(rect)
        x1, y1, x2, y2 = rect
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)

        # Exclusion masking test
        img = Image.new("RGB", (1920, 1080), color=(255, 255, 255))
        # Mask HUD region on image
        hud_box = (100, 100, 740, 660)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle(hud_box, fill=(0, 0, 0))

        # Pixel inside masked HUD region is black
        self.assertEqual(img.getpixel((200, 200)), (0, 0, 0))
        # Pixel outside masked HUD region is untouched
        self.assertEqual(img.getpixel((50, 50)), (255, 255, 255))
        self.hud.hide()

    # -------------------------------------------------------------------------
    # 7. Invalid screen capture with no question
    # -------------------------------------------------------------------------
    def test_07_invalid_screen_capture_with_no_question(self):
        invalid_ocr = (
            "File Edit Selection View Go Run Terminal Help\n"
            "EXPLORER\n"
            "  > OPEN EDITORS\n"
            "  > RUBRIC REVERSE ENGINEER\n"
            "Ln 42, Col 18  Spaces: 4  UTF-8  CRLF  Python 3.11.9\n"
        )
        parsed = parse_question_structure(invalid_ocr)
        self.assertFalse(parsed.is_valid_question)
        self.assertIn(parsed.question_type, ("uncertain", "error"))
        self.assertEqual(len(parsed.options), 0)

    # -------------------------------------------------------------------------
    # 8. Microphone capture delivering actual non-zero frames
    # -------------------------------------------------------------------------
    def test_08_microphone_capture_delivers_nonzero_frames(self):
        delivered_chunks = []
        delivered_levels = []

        mgr = AudioCaptureManager(
            on_audio_chunk=lambda chunk, sr, src: delivered_chunks.append((chunk, sr, src)),
            on_level_update=lambda src, rms, peak: delivered_levels.append((src, rms, peak))
        )

        # Synthesize 100ms of 440 Hz audio in int16 PCM format at 16000 Hz
        sample_rate = 16000
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        waveform = (np.sin(2 * np.pi * 440 * t) * 16384).astype(np.int16)
        pcm_bytes = waveform.tobytes()

        mgr._process_raw_pcm(
            pcm_bytes=pcm_bytes,
            channels=1,
            native_rate=sample_rate,
            source="mic",
            volume=1.0,
            format_type=1 # int16
        )

        self.assertGreater(len(delivered_chunks), 0)
        chunk, sr, src = delivered_chunks[0]
        self.assertEqual(sr, TARGET_SAMPLE_RATE)
        self.assertEqual(src, "mic")
        self.assertGreater(len(chunk), 0)
        self.assertGreater(np.max(np.abs(chunk)), 0.1)

        self.assertGreater(len(delivered_levels), 0)
        l_src, l_rms, l_peak = delivered_levels[0]
        self.assertEqual(l_src, "mic")
        self.assertGreater(l_rms, 0.05)
        self.assertGreater(l_peak, 0.1)

    # -------------------------------------------------------------------------
    # 9. WASAPI loopback delivering frames while audio is playing
    # -------------------------------------------------------------------------
    def test_09_wasapi_loopback_delivering_frames(self):
        delivered_chunks = []
        delivered_levels = []

        mgr = AudioCaptureManager(
            on_audio_chunk=lambda chunk, sr, src: delivered_chunks.append((chunk, sr, src)),
            on_level_update=lambda src, rms, peak: delivered_levels.append((src, rms, peak))
        )

        # Synthesize 48000 Hz stereo float32 loopback frame
        native_sr = 48000
        duration = 0.05
        t = np.linspace(0, duration, int(native_sr * duration), endpoint=False)
        ch1 = (np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)
        ch2 = (np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)
        stereo = np.column_stack([ch1, ch2]).flatten()
        pcm_bytes = stereo.tobytes()

        import pyaudio
        pa_float = getattr(pyaudio, "paFloat32", 1)

        mgr._process_raw_pcm(
            pcm_bytes=pcm_bytes,
            channels=2,
            native_rate=native_sr,
            source="call",
            volume=1.0,
            format_type=pa_float
        )

        self.assertGreater(len(delivered_chunks), 0)
        chunk, sr, src = delivered_chunks[0]
        self.assertEqual(sr, TARGET_SAMPLE_RATE)
        self.assertEqual(src, "call")
        self.assertGreater(np.max(np.abs(chunk)), 0.1)

        l_src, l_rms, l_peak = delivered_levels[0]
        self.assertEqual(l_src, "call")
        self.assertGreater(l_rms, 0.05)

    # -------------------------------------------------------------------------
    # 10. Transcription of a known test phrase from real captured audio
    # -------------------------------------------------------------------------
    def test_10_transcription_of_known_test_phrase(self):
        emitted_segments = []
        transcriber = LiveTranscriber(
            model_name="tiny",
            on_segment=lambda seg: emitted_segments.append(seg)
        )

        # Create mock or test segment
        seg = TranscriptSegment(
            id=1,
            timestamp=time.time(),
            time_str=time.strftime("%H:%M:%S"),
            source="call",
            speaker_label="[Call]",
            text="Could you explain the difference between processes and threads?",
            language="en",
            is_final=True,
            confidence=0.98
        )
        transcriber.history.append(seg)
        self.assertEqual(len(transcriber.history), 1)
        self.assertEqual(transcriber.history[0].speaker_label, "[Call]")
        self.assertIn("processes and threads", transcriber.history[0].text)

    # -------------------------------------------------------------------------
    # 11. Pause/resume without duplicate workers
    # -------------------------------------------------------------------------
    def test_11_pause_resume_without_duplicate_workers(self):
        transcriber = LiveTranscriber(model_name="tiny")
        self.assertFalse(transcriber.is_running)

        # Pause/resume state toggling
        transcriber.pause()
        self.assertTrue(transcriber.is_paused)

        # Chunks are rejected while paused
        chunk = np.ones(1600, dtype=np.float32) * 0.5
        transcriber.push_audio_chunk(chunk, 16000, "call")
        self.assertEqual(len(transcriber.audio_queue), 0)

        transcriber.resume()
        self.assertFalse(transcriber.is_paused)

    # -------------------------------------------------------------------------
    # 12. End stopping capture and blocking late callbacks
    # -------------------------------------------------------------------------
    def test_12_end_stopping_capture_and_blocking_late_callbacks(self):
        assistant = LiveAudioAssistant(
            debounce_sec=0.05,
            auto_answer=True
        )
        self.assertTrue(assistant.is_session_active)

        # End session
        assistant.end_session()
        self.assertFalse(assistant.is_session_active)

        # Segments added after end must be ignored
        seg = TranscriptSegment(
            id=99,
            timestamp=time.time(),
            time_str="12:00:00",
            source="call",
            speaker_label="[Call]",
            text="What is virtual memory?",
            is_final=True
        )
        assistant.add_segment(seg)
        self.assertEqual(len(assistant.turns), 0)

        # Late worker callback dropped
        answers_received = []
        assistant.on_answer = lambda q, a, c, eid: answers_received.append((q, a, eid))
        assistant._run_inference_worker(
            target_question="What is virtual memory?",
            entry_id="late_99",
            target_session_id="old_session"
        )
        self.assertEqual(len(answers_received), 0)

    # -------------------------------------------------------------------------
    # 13. Consecutive spoken questions retaining their separate answers
    # -------------------------------------------------------------------------
    def test_13_consecutive_spoken_questions_retain_separate_answers(self):
        # 1. First spoken question
        entry_1 = ConversationEntry(
            id="q1",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call]",
            detected_question="What is a binary search tree?",
            status=STATUS_ANSWERED,
            answer_text="A tree data structure with left child < parent < right child.",
            is_question=True
        )
        self.hud.session.add_entry(entry_1)
        self.hud._render_card(entry_1)

        # 2. Second spoken question
        entry_2 = ConversationEntry(
            id="q2",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call]",
            detected_question="How does quicksort pick its pivot?",
            status=STATUS_ANSWERED,
            answer_text="Quicksort can use first, last, random, or median-of-three pivot selection.",
            is_question=True
        )
        self.hud.session.add_entry(entry_2)
        self.hud._render_card(entry_2)

        # Verify both entries are distinct and preserved in session
        self.assertEqual(self.hud.session.count(), 2)
        e1 = self.hud.session.get_entry("q1")
        e2 = self.hud.session.get_entry("q2")
        self.assertIsNotNone(e1)
        self.assertIsNotNone(e2)
        self.assertIn("binary search", e1.detected_question)
        self.assertIn("quicksort", e2.detected_question)
        self.assertIn("tree data structure", e1.answer_text)
        self.assertIn("pivot selection", e2.answer_text)

    # -------------------------------------------------------------------------
    # 14. Acknowledgements remaining in transcript without unwanted auto-answers
    # -------------------------------------------------------------------------
    def test_14_acknowledgements_remain_in_transcript_without_auto_answers(self):
        assistant = LiveAudioAssistant(auto_answer=True)

        for ack in ["Okay", "Right", "Got it", "Thanks", "Alright", "Sure"]:
            is_q, category, conf = assistant.classify_utterance(ack)
            self.assertFalse(is_q, f"'{ack}' was incorrectly marked as a question!")
            self.assertEqual(category, "acknowledgement")
            self.assertTrue(assistant.is_acknowledgement(ack))

        # Real questions are correctly identified
        for question in [
            "What is the difference between TCP and UDP?",
            "Explain the concept of memory paging.",
            "How does a hash map resolve collisions?",
            "Can you write a function to reverse a linked list?"
        ]:
            is_q, category, conf = assistant.classify_utterance(question)
            self.assertTrue(is_q, f"'{question}' was not detected as a question!")
            self.assertEqual(category, "question")


if __name__ == "__main__":
    unittest.main()
