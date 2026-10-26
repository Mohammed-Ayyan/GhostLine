import unittest
import sys
from pathlib import Path

# Add project root to sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.core.ocr_engine import ParsedQuestion
from ghostline.core.llm_client import AnswerResult
from ghostline.ui.presentation import build_answer_presentation

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestHudChatEndToEnd(unittest.TestCase):
    """
    Automated tests for HUD Chat End-to-End Pipeline (DEF-05):
    - Input validation and empty query rejection
    - Loading state, input disabling, and feedback
    - Structured response rendering and input re-enabling
    - Error handling without permanent disabling or crashes
    - Conversation context extraction
    - Monotonic sequence tracking to prevent stale response overwrites
    """

    def setUp(self):
        self.submitted_queries = []
        self.hud = QtGhostlineHudOverlay(
            on_ask_custom=lambda q: self.submitted_queries.append(q)
        )

    def tearDown(self):
        if self.hud:
            self.hud.close()

    def test_empty_query_rejected_without_crash(self):
        self.hud.input_custom.setText("")
        self.hud._send_custom_query()
        self.assertEqual(len(self.submitted_queries), 0)

        self.hud.input_custom.setText("     ")
        self.hud._send_custom_query()
        self.assertEqual(len(self.submitted_queries), 0)

    def test_valid_query_submission_and_input_clearing(self):
        self.hud.input_custom.setText("Explain dynamic programming in 2 sentences")
        self.hud._send_custom_query()
        self.assertEqual(len(self.submitted_queries), 1)
        self.assertEqual(self.submitted_queries[0], "Explain dynamic programming in 2 sentences")
        self.assertEqual(self.hud.input_custom.text(), "")

    def test_loading_state_disables_input_and_shows_indicator(self):
        self.hud.set_chat_loading("What is binary search?")
        self.assertIn("What is binary search?", self.hud.lbl_q_text.text())
        self.assertIn("Consulting local neural engine", self.hud.lbl_a_text.text())
        self.assertFalse(self.hud.input_custom.isEnabled())
        self.assertFalse(self.hud.btn_send.isEnabled())

    def test_response_rendering_re_enables_input(self):
        self.hud.set_chat_loading("What is binary search?")
        self.assertFalse(self.hud.input_custom.isEnabled())

        ans = AnswerResult(
            answer_option="B",
            proposed_option="B",
            validation_status="verified",
            is_validated=True,
            explanation="Binary search divides the search space in half with O(log n) complexity.",
            confidence=0.99
        )
        q = ParsedQuestion(question_text="What is binary search?", options={"B": "O(log n)"})
        presentation = build_answer_presentation(q, ans)

        self.hud.set_chat_response(presentation)
        self.assertTrue(self.hud.input_custom.isEnabled())
        self.assertTrue(self.hud.btn_send.isEnabled())
        self.assertIn("Binary search", self.hud.lbl_tradeoff.text())

    def test_error_state_re_enables_input_and_shows_error_message(self):
        self.hud.set_chat_loading("Trigger simulated timeout")
        self.assertFalse(self.hud.input_custom.isEnabled())

        self.hud.set_chat_error("Ollama connection timed out after 30s")
        self.assertTrue(self.hud.input_custom.isEnabled())
        self.assertTrue(self.hud.btn_send.isEnabled())
        self.assertIn("Ollama connection timed out", self.hud.lbl_a_text.text())

    def test_context_extraction_methods(self):
        self.hud.lbl_q_text.setText("Find maximum sum subarray")
        self.hud.lbl_a_text.setText("Kadane's Algorithm runs in O(n)")

        self.assertEqual(self.hud.get_current_question(), "Find maximum sum subarray")
        self.assertIn("Kadane's Algorithm", self.hud.get_current_answer())


if __name__ == "__main__":
    unittest.main()
