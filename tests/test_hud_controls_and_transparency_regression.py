import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.presentation import PresentedAnswer

# Ensure QApplication exists
_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


class TestHUDControlsAndTransparencyRegression(unittest.TestCase):
    """
    Empirical regression tests verifying:
    - Every button and clickable region on QtGhostlineHudOverlay
    - MCQ End button full session teardown
    - HUD chat submission, loading, response, and error
    - Translucent glass styling and window opacity
    """

    def setUp(self):
        self.retry_called = False
        self.screenshot_called = False
        self.end_called = False
        self.pause_called = False
        self.chat_queries = []

        self.hud = QtGhostlineHudOverlay(
            on_retry=lambda: setattr(self, "retry_called", True),
            on_trigger_screenshot=lambda: setattr(self, "screenshot_called", True),
            on_end=lambda: setattr(self, "end_called", True),
            on_toggle_pause=lambda: (setattr(self, "pause_called", True), True)[1],
            on_ask_custom=lambda q: self.chat_queries.append(q),
            opacity=0.86
        )

    def tearDown(self):
        if hasattr(self, "hud") and self.hud:
            self.hud.close()

    def test_window_transparency_and_island_styling(self):
        """Verify window opacity is 0.86 and island frames have translucent styling."""
        self.assertAlmostEqual(self.hud.windowOpacity(), 0.86, places=2)

        tb_style = self.hud.island_toolbar.styleSheet()
        self.assertIn("rgba(18, 21, 28, 0.86)", tb_style)
        self.assertIn("#334155", tb_style)

        ans_style = self.hud.island_answer.styleSheet()
        self.assertIn("rgba(18, 21, 28, 0.86)", ans_style)
        self.assertIn("#334155", ans_style)

    def test_all_toolbar_action_buttons(self):
        """Verify Answer, Screenshot, Chat, Pause, and Size Mode controls."""
        # 1. Answer button
        self.hud.btn_ans.click()
        self.assertTrue(self.retry_called)

        # 2. Screenshot button
        self.hud.btn_shot.click()
        self.assertTrue(self.screenshot_called)

        # 3. Chat button (triggers focus on custom input)
        self.hud.btn_chat.click()
        self.assertTrue(self.hud.input_custom.isEnabled())

        # 4. Pause button
        self.hud.btn_pause.click()
        self.assertTrue(self.pause_called)
        self.assertIn("Resume", self.hud.btn_pause.text())

        # 5. Size mode toggle
        init_w, init_h = self.hud.width(), self.hud.height()
        self.hud.btn_size_mode.click()
        self.assertTrue(self.hud.is_expanded)
        self.assertEqual(self.hud.width(), 760)
        self.hud.btn_size_mode.click()
        self.assertFalse(self.hud.is_expanded)
        self.assertEqual(self.hud.width(), 560)

    def test_mcq_end_button_teardown(self):
        """Verify End button hides overlay, stops timers, and invokes on_end teardown."""
        self.hud.show_overlay()
        self.assertTrue(self.hud.isVisible())

        # Click End
        self.hud._handle_end_clicked()
        self.assertTrue(self.end_called, "on_end handler was not invoked by End button!")
        self.assertFalse(self.hud.isVisible(), "Overlay was not hidden after End click!")

    def test_copy_buttons(self):
        """Verify Copy Question, Copy Answer, and Copy Code clipboard operations."""
        cb = QApplication.clipboard()

        # Set content
        self.hud.lbl_q_text.setText("Sample Test Question")
        self.hud.lbl_a_text.setText("Sample Test Answer Option B")
        self.hud.txt_code.setText("def solve(): return 42")
        self.hud.code_frame.show()

        # 1. Copy Question
        self.hud._copy_question()
        QApplication.processEvents()
        self.assertEqual(cb.text(), "Sample Test Question")

        # 2. Copy Answer
        self.hud.copy_answer_to_clipboard()
        QApplication.processEvents()
        self.assertIn("Sample Test Answer Option B", cb.text())
        self.assertIn("def solve(): return 42", cb.text())

        # 3. Copy Code
        self.hud._copy_code()
        QApplication.processEvents()
        self.assertEqual(cb.text(), "def solve(): return 42")

    def test_hud_chat_lifecycle(self):
        """Verify HUD chat submission, loading state, response display, and error handling."""
        # 1. Empty message rejection
        self.hud.input_custom.setText("   ")
        self.hud._send_custom_query()
        self.assertEqual(len(self.chat_queries), 0)

        # 2. Valid submission
        self.hud.input_custom.setText("What is a race condition?")
        self.hud._send_custom_query()
        self.assertEqual(self.chat_queries, ["What is a race condition?"])
        self.assertEqual(self.hud.input_custom.text(), "")

        # 3. Loading state
        self.hud.set_chat_loading("What is a race condition?")
        self.assertFalse(self.hud.input_custom.isEnabled())
        self.assertFalse(self.hud.btn_send.isEnabled())
        self.assertIn("Thinking", self.hud.lbl_a_star.text())

        # 4. Response state
        res = PresentedAnswer(
            question_text="What is a race condition?",
            headline="A race condition occurs when concurrent threads access shared state without synchronization.",
            direct_answer="A race condition occurs when concurrent threads access shared state without synchronization.",
            explanation="Threads interleave unexpectedly causing non-deterministic bugs.",
            code="import threading\nlock = threading.Lock()",
            code_language="python",
            badge="✓",
            question_type="conceptual",
            confidence=0.95
        )
        self.hud.set_chat_response(res)
        self.assertTrue(self.hud.input_custom.isEnabled())
        self.assertTrue(self.hud.btn_send.isEnabled())
        self.assertIn("race condition occurs", self.hud.lbl_a_text.text())
        self.assertIn("import threading", self.hud.txt_code.text())

        # 5. Error state
        self.hud.set_chat_error("Model phi3:mini not found locally")
        self.assertTrue(self.hud.input_custom.isEnabled())
        self.assertIn("Error:", self.hud.lbl_a_star.text())
        self.assertIn("not found locally", self.hud.lbl_a_text.text())


if __name__ == "__main__":
    unittest.main()
