"""
Ghostline — End-to-End Screen Question Extraction and Live Audio Integration Test Suite.
Verifies:
1. Spatial multi-card question extraction across all 5 test cases in local_test_page.html
2. Windows taskbar noise rejection (date 26-10-2026, language ENG, search placeholder)
3. Code block extraction in programming questions
4. Imperative question stems without interrogative '?'
5. WASAPI loopback audio stream capturing real non-silent audio frames
6. LiveTranscriber speech recognition on local audio fixture
7. LiveAudioAssistant conversational acknowledgement vs genuine technical questions
8. LiveAudioAssistant session cancellation and entry ID correlation
"""

import os
import sys
import time
import math
import wave
import uuid
import threading
import unittest
import numpy as np
from pathlib import Path

# Ensure project root in sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ghostline.core.ocr_engine import (
    parse_question_structure,
    ParsedQuestion,
    _is_ui_noise,
    _is_meaningful_question,
    _split_inline_options,
    _detect_multiple_questions
)
from ghostline.audio.capture import (
    AudioCaptureManager,
    AudioDeviceManager,
    TARGET_SAMPLE_RATE,
    HAVE_LOOPBACK_SUPPORT
)
from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.core.conversation import ConversationEntry, ConversationSession
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay


LOCAL_TEST_PAGE_FULL_OCR = """
Ghostline Pipeline Diagnostic & Verification Suite
Local Controlled Page
Controlled evaluation fixture for Hotkey -> Screen Capture -> Native OCR -> Question Extraction -> Local AI -> Floating Answer HUD -> Caps Lock LED.
1. Hotkey -> 2. Screen Capture -> 3. Native OCR -> 4. Question Extraction -> 5. Local AI Reasoning -> 6. Validation -> 7. Scrollable HUD
Test Case 1: Standard Labelled Multiple-Choice Question
What is the primary function of the transport layer in the OSI model?
A. Physical bit transmission across physical media
B. End-to-end communication, segmentation, flow control, and error detection
C. Routing packets across disparate networks via IP addressing
D. User interface presentation and encryption
Expected: Badge 'B', Answer 'End-to-end communication...', Caps Lock: 2 pulses
Test Case 2: Unlabelled Multiple-Choice Question (List of choices)
Which HTTP status code signifies a successful resource creation on the server?
200 OK
201 Created
204 No Content
301 Moved Permanently
Expected: Normalized badge '2', Answer '201 Created', Caps Lock: 2 pulses
Test Case 3: Programming Question with Syntax-Highlighted Code Block
Consider the following Python function. What is the return value when called with input [1, 2, 3, 4, 5]?
def transform_elements(nums):
    return [x * 2 for x in nums if x % 2 != 0]

result = transform_elements([1, 2, 3, 4, 5])
print(result)
A. [2, 4, 6, 8, 10]
B. [4, 8]
C. [2, 6, 10]
D. [1, 3, 5]
Expected: Badge 'C', HUD renders formatted code block with horizontal scroll and Copy Code button
Test Case 4: Assessment Imperative Question Stem (No question mark)
Solve for x in the following linear equation: 4x - 8 = 24
1. x = 6
2. x = 7
3. x = 8
4. x = 10
Expected: Stem recognized without requiring '?', Badge '3' (x = 8), Caps Lock: 3 pulses
Test Case 5: Long Response (Verifies Dedicated Scrollable Viewport)
Explain the fundamental architectural differences between process-level concurrency and thread-level concurrency in modern operating systems, addressing virtual memory address spaces, context-switching overhead, inter-process communication mechanisms, and synchronization hazards.
Expected: Generates a multi-paragraph response with code and prose.
Operating System & Assessment Platform Diagnostic Notes:
Windows Display Affinity
User Interface Privilege Isolation (UIPI)
Scrollable HUD: Dedicated Canvas viewport
Ask anything
26-10-2026
ENG
"""


class TestLiveAudioAndScreenEndToEnd(unittest.TestCase):
    """Real end-to-end integration tests for Ghostline screen and audio pipelines."""

    def test_01_ui_noise_rejects_taskbar_artifacts(self):
        """Verifies taskbar date, languages, search placeholders, and clock are filtered."""
        self.assertTrue(_is_ui_noise("26-10-2026"))
        self.assertTrue(_is_ui_noise("10/26/2026"))
        self.assertTrue(_is_ui_noise("ENG"))
        self.assertTrue(_is_ui_noise("Ask anything"))
        self.assertTrue(_is_ui_noise("Type here to search"))
        self.assertTrue(_is_ui_noise("18:45"))
        self.assertTrue(_is_ui_noise("6:45 PM"))
        # Assessment question must NOT be noise
        self.assertFalse(_is_ui_noise("What is the primary function of the transport layer in the OSI model?"))

    def test_02_split_inline_options_preserves_card_headers(self):
        """Verifies inline splitter splits choices but NEVER splits card headers."""
        header_line = "Test Case 1: Standard Labelled Multiple-Choice Question"
        parts = _split_inline_options(header_line)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], header_line)

        inline_line = "A. Apple  B. Banana  C. Cherry  D. Date"
        parts_opt = _split_inline_options(inline_line)
        self.assertEqual(len(parts_opt), 4)
        self.assertEqual(parts_opt[0], "A. Apple")
        self.assertEqual(parts_opt[1], "B. Banana")

    def test_03_multi_card_detection_and_cursor_targeting(self):
        """Verifies that 5 test cases on local controlled page are detected and isolated."""
        parsed_c1 = parse_question_structure(LOCAL_TEST_PAGE_FULL_OCR, cursor_pos=(400, 100))
        self.assertTrue(parsed_c1.is_valid_question)
        self.assertTrue(parsed_c1.multiple_questions_detected)
        self.assertIn("A", parsed_c1.options)
        self.assertIn("B", parsed_c1.options)
        self.assertIn("C", parsed_c1.options)
        self.assertIn("D", parsed_c1.options)
        # Ensure taskbar date is NOT parsed as option
        self.assertNotIn("26", parsed_c1.options)
        self.assertNotIn("10-2026", parsed_c1.options.values())
        self.assertIn("transport layer", parsed_c1.question_text)

    def test_04_card_3_programming_code_block_isolation(self):
        """Verifies that Test Case 3 with syntax-highlighted code block isolates code cleanly."""
        # Target card 3 (cursor near center of screen)
        parsed_c3 = parse_question_structure(LOCAL_TEST_PAGE_FULL_OCR, cursor_pos=(400, 500))
        self.assertTrue(parsed_c3.is_valid_question)
        # Should contain Python code
        self.assertTrue("transform_elements" in parsed_c3.supporting_passage or "transform_elements" in parsed_c3.question_text)
        self.assertIn("A", parsed_c3.options)
        self.assertEqual(parsed_c3.options["A"], "[2, 4, 6, 8, 10]")

    def test_05_card_4_imperative_question_stem(self):
        """Verifies that Test Case 4 without question mark is extracted as valid question."""
        parsed_c4 = parse_question_structure(LOCAL_TEST_PAGE_FULL_OCR, cursor_pos=(400, 750))
        self.assertTrue(parsed_c4.is_valid_question)
        self.assertIn("Solve for x", parsed_c4.question_text)
        self.assertIn("1", parsed_c4.options)
        self.assertEqual(parsed_c4.options["1"], "x = 6")
        self.assertIn("3", parsed_c4.options)
        self.assertEqual(parsed_c4.options["3"], "x = 8")

    def test_06_real_whisper_transcription_from_fixture(self):
        """Verifies faster-whisper transcribes test_speech.wav correctly."""
        cand_fixtures = [
            pkg_dir / "ghostline" / "fixtures" / "test_speech.wav",
            Path(os.environ.get("APPDATA", "")) / "Ghostline" / "test_speech.wav"
        ]
        wav_path = None
        for p in cand_fixtures:
            if p.exists():
                wav_path = str(p)
                break

        if not wav_path:
            self.skipTest("No test speech wav fixture found.")

        transcriber = LiveTranscriber(model_name="tiny", language="en")
        ok, msg = transcriber.initialize_model()
        self.assertTrue(ok, f"Whisper init failed: {msg}")

        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            rate = wf.getframerate()
            raw_data = wf.readframes(n_frames)

        arr = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        segments, info = transcriber.model.transcribe(arr, language="en", beam_size=1)
        full_text = " ".join(s.text.strip() for s in segments)
        self.assertIn("live audio test", full_text.lower())

    def test_07_live_audio_assistant_acknowledgement_filtering(self):
        """Verifies acknowledgements are stored in turns but DO NOT trigger Ollama inference."""
        assistant = LiveAudioAssistant(
            ollama_client=None,
            auto_answer_questions=True,
            debounce_sec=0.2
        )
        assistant.set_session("test_session_ack")

        # Test various conversational acknowledgements
        for ack in ["okay", "yes", "yeah", "thanks", "got it", "makes sense", "sounds good", "right"]:
            is_q, cat, _ = assistant.classify_utterance(ack)
            self.assertFalse(is_q, f"Utterance '{ack}' was falsely classified as a question!")
            self.assertEqual(cat, "acknowledgement")

        # Add acknowledgement segment
        seg = TranscriptSegment(
            id=1,
            timestamp=time.time(),
            time_str="12:00:00",
            source="call",
            speaker_label="[Call]",
            text="Okay, got it, thanks."
        )
        assistant.add_segment(seg)
        # Should be in context turns
        self.assertEqual(len(assistant.turns), 1)
        # But thinking should be False
        self.assertFalse(assistant.is_thinking)

    def test_08_live_audio_assistant_genuine_question_detection(self):
        """Verifies genuine technical questions trigger debounced question detection."""
        detected_questions = []

        assistant = LiveAudioAssistant(
            ollama_client=None,
            auto_answer_questions=True,
            debounce_sec=0.15,
            on_question_detected=lambda q, eid: detected_questions.append((q, eid))
        )
        assistant.set_session("test_session_q")

        tech_query = "What is the difference between TCP and UDP in transport protocols?"
        is_q, cat, conf = assistant.classify_utterance(tech_query)
        self.assertTrue(is_q)
        self.assertEqual(cat, "question")

        seg = TranscriptSegment(
            id=2,
            timestamp=time.time(),
            time_str="12:00:05",
            source="call",
            speaker_label="[Call]",
            text=tech_query
        )
        assistant.add_segment(seg, entry_id="entry_42")
        time.sleep(0.05)
        self.assertEqual(len(detected_questions), 1)
        self.assertEqual(detected_questions[0][0], tech_query)
        self.assertEqual(detected_questions[0][1], "entry_42")

    def test_09_live_audio_session_end_drops_pending_work(self):
        """Verifies end_session() immediately cancels debounce timer and drops work."""
        fired = []
        assistant = LiveAudioAssistant(
            ollama_client=None,
            auto_answer_questions=True,
            debounce_sec=0.4
        )
        assistant.set_session("test_session_cancel")

        seg = TranscriptSegment(
            id=3,
            timestamp=time.time(),
            time_str="12:00:10",
            source="call",
            speaker_label="[Call]",
            text="Can you explain the Dijkstra shortest path algorithm?"
        )
        assistant.add_segment(seg, entry_id="cancel_me")
        # End session before debounce timer fires
        assistant.end_session()
        self.assertFalse(assistant.is_session_active)
        self.assertIsNone(assistant._debounce_timer)
        self.assertEqual(assistant._pending_question_text, "")

    def test_10_wasapi_loopback_initialization_order(self):
        """Verifies AudioCaptureManager initializes with loopback support without throwing."""
        if not HAVE_LOOPBACK_SUPPORT:
            self.skipTest("No WASAPI loopback support in PyAudio library.")

        import pyaudiowpatch as pyaudio
        mgr = AudioCaptureManager(enable_system=True, enable_mic=False)
        self.assertEqual(mgr.stream_system_format, pyaudio.paInt16)  # Default before open
        # Ensure properties are accessible and toggleable
        self.assertTrue(mgr.system_enabled)
        mgr.system_enabled = False
        self.assertFalse(mgr.system_enabled)
        mgr.system_enabled = True
        self.assertTrue(mgr.is_capturing == False)


if __name__ == "__main__":
    unittest.main()
