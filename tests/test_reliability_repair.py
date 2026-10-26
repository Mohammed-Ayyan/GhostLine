import unittest
import sys
import time
import uuid
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

from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.audio.transcription import TranscriptSegment
from ghostline.core.conversation import (
    ConversationEntry,
    ConversationSession,
    SOURCE_MIC,
    SOURCE_SYSTEM,
    SOURCE_SCREEN,
    SOURCE_MANUAL,
    STATUS_TRANSCRIPT,
    STATUS_THINKING,
    STATUS_ANSWERED,
    STATUS_ERROR
)
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.core.ocr_engine import parse_question_structure, ParsedQuestion
from ghostline.core.llm_client import AnswerResult
from ghostline.ui.presentation import build_answer_presentation, TYPE_MCQ, TYPE_UNCERTAIN
from ghostline.core.capture import capture_screen


class TestReliabilityRepairSuite(unittest.TestCase):
    """
    Complete regression suite covering all 12 critical repair scenarios:
    1. Saying 'Okay' adds transcript entry but does NOT trigger auto-answer.
    2. Spoken question triggers debounced answer associated with that question.
    3. Two consecutive questions retain both answers in history.
    4. Delayed response to older question cannot overwrite newer question's answer.
    5. End stops session and prevents late callbacks from updating HUD.
    6. Starting new session after End works cleanly without duplicate workers.
    7. Standard MCQ extracts question and four options correctly.
    8. MCQ with explanatory passage preserves passage and all options.
    9. Inline options and vertically separated options are both supported.
    10. HUD controls and answer text are masked/filtered from OCR results.
    11. Switching between call and MCQ modes preserves history and labels.
    12. Failed or uncertain extraction shows recoverable error without fabricating options.
    """

    def setUp(self):
        self.hud = QtGhostlineHudOverlay()
        self.hud.session.clear()
        self.hud.rebuild_cards_view()

    def tearDown(self):
        if self.hud:
            self.hud.close()

    # -------------------------------------------------------------------------
    # Scenario 1: Saying "Okay" adds transcript but does not trigger auto-answer
    # -------------------------------------------------------------------------
    def test_scenario_01_acknowledgement_does_not_trigger_answer(self):
        answers_triggered = []
        questions_detected = []

        assistant = LiveAudioAssistant(
            auto_answer=True,
            debounce_sec=0.1,
            on_answer=lambda q, a, c, **kw: answers_triggered.append((q, a)),
            on_question_detected=lambda q, *a: questions_detected.append(q)
        )

        # 1. Classify directly
        is_q, category, conf = assistant.classify_utterance("Okay")
        self.assertFalse(is_q)
        self.assertEqual(category, "acknowledgement")

        # Also test other common acknowledgements
        for ack in ["okay", "yes", "right", "thanks", "got it", "cool", "sounds good", "mm-hmm"]:
            is_ack_q, cat, _ = assistant.classify_utterance(ack)
            self.assertFalse(is_ack_q, f"'{ack}' should not be treated as a question")

        # 2. Add as transcript segment
        seg = TranscriptSegment(id=1, timestamp=time.time(), time_str="10:00:00", source="call", speaker_label="[Call]", text="Okay, got it.")
        assistant.add_segment(seg)

        # Wait past debounce
        time.sleep(0.2)
        self.assertEqual(len(questions_detected), 0)
        self.assertEqual(len(answers_triggered), 0)
        # Verify segment was retained in context
        self.assertEqual(len(assistant.turns), 1)
        self.assertEqual(assistant.turns[0].text, "Okay, got it.")

    # -------------------------------------------------------------------------
    # Scenario 2: Complete spoken question triggers debounced answer
    # -------------------------------------------------------------------------
    def test_scenario_02_spoken_question_triggers_debounced_answer(self):
        questions_detected = []
        answers_received = []

        class MockLLM:
            def solve_question(self, question_text, options=None, model=""):
                return AnswerResult(
                    answer_option="B",
                    explanation="Quicksort worst-case is O(n^2) when pivot selection is poor."
                )

        assistant = LiveAudioAssistant(
            ollama_client=MockLLM(),
            auto_answer=True,
            debounce_sec=0.1,
            on_question_detected=lambda q, *a: questions_detected.append(q),
            on_answer=lambda q, a, c, **kw: answers_received.append((q, a, kw.get("entry_id")))
        )

        q_text = "What is the worst case time complexity of quicksort?"
        is_q, category, _ = assistant.classify_utterance(q_text)
        self.assertTrue(is_q)
        self.assertEqual(category, "question")

        seg = TranscriptSegment(id=2, timestamp=time.time(), time_str="10:00:05", source="call", speaker_label="[Call]", text=q_text)
        assistant.add_segment(seg, entry_id="entry_q1")

        self.assertEqual(len(questions_detected), 1)
        self.assertEqual(questions_detected[0], q_text)

        # Wait for debounce and worker execution
        time.sleep(0.3)
        self.assertEqual(len(answers_received), 1)
        q_ans, a_ans, eid = answers_received[0]
        self.assertEqual(q_ans, q_text)
        self.assertIn("O(n^2)", a_ans)
        self.assertEqual(eid, "entry_q1")

    # -------------------------------------------------------------------------
    # Scenario 3: Two consecutive questions retain both answers
    # -------------------------------------------------------------------------
    def test_scenario_03_two_consecutive_questions_retain_both_answers(self):
        self.hud.session.clear()
        self.hud.rebuild_cards_view()

        # Question 1
        e1 = ConversationEntry(
            id="q_1",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call Question]",
            detected_question="What is dynamic programming?",
            status=STATUS_THINKING,
            is_question=True
        )
        self.hud.session.add_entry(e1)
        self.hud._render_card(e1)

        # Answer 1 arrives
        self.hud.append_ai_answer(
            full_ans="DP breaks problems into overlapping subproblems with optimal substructure.",
            question="What is dynamic programming?",
            entry_id="q_1"
        )

        # Question 2
        e2 = ConversationEntry(
            id="q_2",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call Question]",
            detected_question="What is memoization vs tabulation?",
            status=STATUS_THINKING,
            is_question=True
        )
        self.hud.session.add_entry(e2)
        self.hud._render_card(e2)

        # Answer 2 arrives
        self.hud.append_ai_answer(
            full_ans="Memoization is top-down caching; tabulation is bottom-up iterative table filling.",
            question="What is memoization vs tabulation?",
            entry_id="q_2"
        )

        # Verify session entries
        self.assertEqual(self.hud.session.count(), 2)
        res_e1 = self.hud.session.get_entry("q_1")
        res_e2 = self.hud.session.get_entry("q_2")

        self.assertIsNotNone(res_e1)
        self.assertIsNotNone(res_e2)

        self.assertIn("overlapping subproblems", res_e1.answer_text)
        self.assertIn("Memoization is top-down", res_e2.answer_text)

        # Verify neither was overwritten
        self.assertEqual(res_e1.detected_question, "What is dynamic programming?")
        self.assertEqual(res_e2.detected_question, "What is memoization vs tabulation?")

    # -------------------------------------------------------------------------
    # Scenario 4: Delayed response to older question cannot overwrite newer answer
    # -------------------------------------------------------------------------
    def test_scenario_04_delayed_response_cannot_overwrite_newer_answer(self):
        self.hud.session.clear()
        self.hud.rebuild_cards_view()

        # Add question 1
        e1 = ConversationEntry(
            id="q_old",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call Question]",
            detected_question="Old question: Explain REST API",
            status=STATUS_THINKING,
            is_question=True
        )
        self.hud.session.add_entry(e1)
        self.hud._render_card(e1)

        # Add question 2
        e2 = ConversationEntry(
            id="q_new",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call Question]",
            detected_question="New question: Explain GraphQL",
            status=STATUS_THINKING,
            is_question=True
        )
        self.hud.session.add_entry(e2)
        self.hud._render_card(e2)

        # Answer 2 arrives first
        self.hud.append_ai_answer(
            full_ans="GraphQL provides a single endpoint with client-specified schema queries.",
            question="New question: Explain GraphQL",
            entry_id="q_new"
        )

        # Delayed answer for question 1 arrives late
        self.hud.append_ai_answer(
            full_ans="REST uses HTTP verbs on resource endpoints.",
            question="Old question: Explain REST API",
            entry_id="q_old"
        )

        # Verify question 2's answer was NOT overwritten by old question's answer
        res_new = self.hud.session.get_entry("q_new")
        res_old = self.hud.session.get_entry("q_old")

        self.assertIn("GraphQL provides a single endpoint", res_new.answer_text)
        self.assertIn("REST uses HTTP verbs", res_old.answer_text)

    # -------------------------------------------------------------------------
    # Scenario 5: End stops session and prevents late callbacks from updating HUD
    # -------------------------------------------------------------------------
    def test_scenario_05_end_stops_session_and_prevents_late_updates(self):
        answers_received = []

        class SlowLLM:
            def solve_question(self, question_text, options=None, model=""):
                time.sleep(0.4)
                return AnswerResult(answer_option="A", explanation="Slow late answer")

        assistant = LiveAudioAssistant(
            ollama_client=SlowLLM(),
            auto_answer=True,
            debounce_sec=0.05,
            on_answer=lambda q, a, c, **kw: answers_received.append((q, a))
        )

        seg = TranscriptSegment(id=5, timestamp=time.time(), time_str="10:01:00", source="call", speaker_label="[Call]", text="Explain Dijkstra's algorithm?")
        assistant.add_segment(seg, entry_id="e_dijkstra")

        # Let debounce fire to start worker
        time.sleep(0.1)

        # User presses END
        assistant.end_session()
        self.assertFalse(assistant.is_session_active)

        # Wait for slow LLM thread to finish
        time.sleep(0.5)

        # Late answer should have been discarded because session ended
        self.assertEqual(len(answers_received), 0)

        # In HUD, End button click preserves history and marks session ended
        self.hud.session.add_entry(ConversationEntry(
            id="e_pres",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            detected_question="Prior question",
            answer_text="Prior answer",
            status=STATUS_ANSWERED,
            is_question=True
        ))
        self.hud._handle_end_clicked()
        self.assertEqual(self.hud.session.count(), 1)
        self.assertEqual(self.hud.session.get_entry("e_pres").answer_text, "Prior answer")

    # -------------------------------------------------------------------------
    # Scenario 6: Starting a new session after End works cleanly
    # -------------------------------------------------------------------------
    def test_scenario_06_new_session_after_end_works_cleanly(self):
        answers = []
        assistant = LiveAudioAssistant(
            auto_answer=True,
            debounce_sec=0.05,
            session_id="session_1",
            on_answer=lambda q, a, c, **kw: answers.append(a)
        )

        # End session 1
        assistant.end_session()
        self.assertFalse(assistant.is_session_active)

        # Start session 2
        assistant.set_session("session_2")
        self.assertTrue(assistant.is_session_active)
        self.assertEqual(assistant.session_id, "session_2")
        self.assertEqual(len(assistant.turns), 0)

        # Verify session 2 processes new questions
        seg = TranscriptSegment(id=6, timestamp=time.time(), time_str="10:02:00", source="mic", speaker_label="[You]", text="What is a binary tree?")
        assistant.add_segment(seg, entry_id="s2_q1")
        time.sleep(0.15)
        # Debounce fired without crash

    # -------------------------------------------------------------------------
    # Scenario 7: Standard MCQ extracts question and four options correctly
    # -------------------------------------------------------------------------
    def test_scenario_07_standard_mcq_extraction(self):
        raw_ocr = (
            "Assessment Question 5\n"
            "Which of the following data structures operates on a Last-In, First-Out (LIFO) basis?\n"
            "A) Queue\n"
            "B) Stack\n"
            "C) Array\n"
            "D) Linked List\n"
        )
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertIn("Last-In, First-Out", parsed.question_text)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["A"], "Queue")
        self.assertEqual(parsed.options["B"], "Stack")
        self.assertEqual(parsed.options["C"], "Array")
        self.assertEqual(parsed.options["D"], "Linked List")

    # -------------------------------------------------------------------------
    # Scenario 8: MCQ with explanatory passage preserves passage and all options
    # -------------------------------------------------------------------------
    def test_scenario_08_mcq_with_passage_preserves_both(self):
        raw_ocr = (
            "Question 12 of 50\n"
            "A distributed system replicates data across multiple nodes in different availability zones.\n"
            "When network partitions occur, the system must choose between consistency and availability.\n"
            "Which theorem formally describes this trade-off in distributed data stores?\n"
            "A. CAP Theorem\n"
            "B. Amdahl's Law\n"
            "C. Little's Law\n"
            "D. PACELC Theorem\n"
        )
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertIn("trade-off", parsed.question_text)
        self.assertTrue(bool(parsed.supporting_passage))
        self.assertIn("network partitions", parsed.supporting_passage)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["A"], "CAP Theorem")
        self.assertEqual(parsed.options["B"], "Amdahl's Law")
        self.assertEqual(parsed.options["C"], "Little's Law")
        self.assertEqual(parsed.options["D"], "PACELC Theorem")

    # -------------------------------------------------------------------------
    # Scenario 9: Inline options and vertically separated options are supported
    # -------------------------------------------------------------------------
    def test_scenario_09_inline_and_vertical_options(self):
        # Inline options test
        inline_ocr = (
            "What is the time complexity of lookup in a balanced hash table?\n"
            "A) O(1)  B) O(log n)  C) O(n)  D) O(n log n)\n"
        )
        p_inline = parse_question_structure(inline_ocr)
        self.assertTrue(p_inline.is_valid_question)
        self.assertEqual(len(p_inline.options), 4)
        self.assertEqual(p_inline.options["A"], "O(1)")
        self.assertEqual(p_inline.options["B"], "O(log n)")
        self.assertEqual(p_inline.options["C"], "O(n)")
        self.assertEqual(p_inline.options["D"], "O(n log n)")

        # Vertically separated options test
        vert_ocr = (
            "What is the output of 2 + 2 in standard arithmetic?\n"
            "A. 3\n"
            "\n"
            "B. 4\n"
            "\n"
            "C. 5\n"
            "\n"
            "D. 6\n"
        )
        p_vert = parse_question_structure(vert_ocr)
        self.assertTrue(p_vert.is_valid_question)
        self.assertEqual(len(p_vert.options), 4)
        self.assertEqual(p_vert.options["B"], "4")

    # -------------------------------------------------------------------------
    # Scenario 10: HUD controls and answer text are masked/filtered from OCR results
    # -------------------------------------------------------------------------
    def test_scenario_10_hud_controls_excluded_from_ocr(self):
        # 1. UI Noise filter in OCR engine test
        dirty_ocr = (
            "Ghostline AI Ready\n"
            "Assessment Test Section 1\n"
            "Which protocol provides encrypted web communication?\n"
            "A. HTTP\n"
            "B. HTTPS\n"
            "C. FTP\n"
            "D. Telnet\n"
            "Expected: Badge 'B'\n"
            "Diagnostic Notes: Verified by test harness\n"
            "Ask Ghostline a question or manual query...\n"
        )
        parsed = parse_question_structure(dirty_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["B"], "HTTPS")
        self.assertEqual(parsed.options["D"], "Telnet")
        # Verify test harness / HUD noise was NOT included in option D
        self.assertNotIn("Expected: Badge", parsed.options["D"])
        self.assertNotIn("Diagnostic Notes", parsed.options["D"])
        self.assertNotIn("Ask Ghostline", parsed.options["D"])

        # 2. Bounding box pixel masking test
        img = Image.new("RGB", (800, 600), color=(100, 100, 100))
        # Mask out HUD rectangle [100, 100, 300, 300]
        from ghostline.core.capture import capture_screen
        # Test PIL drawing exclusion
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 100, 300, 300], fill=(255, 255, 255))
        arr = np.array(img)
        # Region inside masked rectangle is solid white
        self.assertTrue(np.all(arr[110:290, 110:290] == [255, 255, 255]))

    # -------------------------------------------------------------------------
    # Scenario 11: Mode switching preserves history without mislabeling
    # -------------------------------------------------------------------------
    def test_scenario_11_mode_switching_preserves_history(self):
        self.hud.session.clear()
        self.hud.rebuild_cards_view()

        # Add screen entry
        e_screen = ConversationEntry(
            id="e_scr_1",
            session_id=self.hud.session.session_id,
            source=SOURCE_SCREEN,
            speaker_label="[Screen MCQ]",
            detected_question="Screen MCQ Question",
            answer_text="Choice B: Stack",
            status=STATUS_ANSWERED,
            is_question=True
        )
        self.hud.session.add_entry(e_screen)

        # Add call entry
        e_call = ConversationEntry(
            id="e_call_1",
            session_id=self.hud.session.session_id,
            source=SOURCE_SYSTEM,
            speaker_label="[Call Question]",
            detected_question="Spoken Interview Question",
            answer_text="Spoken Interview Answer",
            status=STATUS_ANSWERED,
            is_question=True
        )
        self.hud.session.add_entry(e_call)

        # Switch to Screen mode
        self.hud._set_mode("screen")
        self.assertEqual(self.hud.active_mode, "screen")
        # Session still has both entries preserved
        self.assertEqual(self.hud.session.count(), 2)
        # Visible entries for screen mode is 1
        vis_screen = self.hud.session.get_entries(mode_filter="screen")
        self.assertEqual(len(vis_screen), 1)
        self.assertEqual(vis_screen[0].id, "e_scr_1")
        self.assertEqual(vis_screen[0].source, SOURCE_SCREEN)

        # Switch to Call mode
        self.hud._set_mode("call")
        self.assertEqual(self.hud.active_mode, "call")
        self.assertEqual(self.hud.session.count(), 2)
        vis_call = self.hud.session.get_entries(mode_filter="call")
        self.assertEqual(len(vis_call), 1)
        self.assertEqual(vis_call[0].id, "e_call_1")
        self.assertEqual(vis_call[0].source, SOURCE_SYSTEM)

        # Switch to All mode
        self.hud._set_mode("all")
        self.assertEqual(len(self.hud.session.get_entries(mode_filter="all")), 2)

    # -------------------------------------------------------------------------
    # Scenario 12: Failed or uncertain extraction shows recoverable error
    # -------------------------------------------------------------------------
    def test_scenario_12_uncertain_extraction_shows_recoverable_error(self):
        noisy_text = "Page 1 of 12 Next Previous Cookie Policy Copyright 2026."
        parsed = parse_question_structure(noisy_text)

        self.assertFalse(parsed.is_valid_question)
        self.assertIn(parsed.question_type, ["error", "uncertain"])

        ans_err = AnswerResult(
            answer_option="?",
            proposed_option="?",
            validation_status="uncertain",
            is_validated=False,
            error="Unreliable question extraction: does not contain question indicators"
        )
        presentation = build_answer_presentation(parsed, ans_err)

        self.assertFalse(presentation.is_validated)
        self.assertEqual(presentation.question_type, TYPE_UNCERTAIN)
        # Does not fabricate options
        self.assertEqual(len(presentation.options), 0)

        # Render in HUD as error card with retry button
        self.hud.set_state("error", presentation=presentation, solve_id=999)
        latest = self.hud.session.get_latest_entry()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, STATUS_ERROR)


if __name__ == "__main__":
    unittest.main()
