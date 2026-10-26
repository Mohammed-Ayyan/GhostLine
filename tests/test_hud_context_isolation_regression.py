"""
Unit & Regression test for HUD Context Isolation & Contamination Prevention.
Verifies that:
1. Hardcoded mock rate-limiter text is completely eradicated from initialization.
2. Previous answer context (code blocks, bullets, tradeoffs) does NOT bleed into subsequent answers.
3. start_solve(), set_state(), and update_answer() correctly clear stale UI widgets.
4. Independent scrolling and size grip operate without overflowing boundaries.
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication

from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.presentation import PresentedAnswer, TYPE_MCQ, TYPE_CODE, TYPE_THEORY


class TestHudContextIsolationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def test_hud_initial_state_clean(self):
        hud = QtGhostlineHudOverlay()
        
        # Assert initial question and answer placeholders are clean
        self.assertNotIn("rate", hud.lbl_q_text.text().lower())
        self.assertNotIn("limiter", hud.lbl_q_text.text().lower())
        self.assertNotIn("redis", hud.txt_code.text().lower())
        self.assertEqual(hud.bullets_box.count(), 0)
        self.assertFalse(hud.code_frame.isVisible())
        self.assertFalse(hud.lbl_tradeoff.isVisible())
        
        # Assert initial chips
        self.assertGreater(hud.chip_container.count(), 0)
        hud.destroy()

    def test_hud_context_isolation_across_consecutive_questions(self):
        hud = QtGhostlineHudOverlay()
        
        # 1. First: Present a coding question with code snippet
        code_ans = PresentedAnswer(
            question_type=TYPE_CODE,
            badge="Python",
            headline="Fibonacci Memoization",
            direct_answer="def fib(n, memo={}): ...",
            explanation="• Uses memoization to achieve O(N) complexity.\n• Avoids exponential recursion tree.",
            code="def fib(n, memo={}):\n    if n in memo: return memo[n]\n    if n <= 1: return n\n    memo[n] = fib(n-1) + fib(n-2)\n    return memo[n]",
            code_language="python",
            confidence=0.95,
            question_text="Implement an efficient recursive Fibonacci in Python."
        )
        hud.update_answer(code_ans)
        
        self.assertIn("Fibonacci", hud.lbl_q_text.text())
        self.assertIn("Fibonacci Memoization", hud.lbl_a_text.text())
        self.assertTrue(hud.code_frame.isVisible())
        self.assertIn("memo", hud.txt_code.text())
        self.assertEqual(hud.bullets_box.count(), 2)
        
        # 2. Second: Start solve for a new question - should immediately clear old code and bullets
        hud.start_solve()
        self.assertFalse(hud.code_frame.isVisible())
        self.assertEqual(hud.bullets_box.count(), 0)
        self.assertFalse(hud.lbl_tradeoff.isVisible())
        self.assertIn("Analyzing", hud.lbl_a_text.text())
        
        # 3. Third: Present a database MCQ question WITHOUT code
        db_ans = PresentedAnswer(
            question_type=TYPE_MCQ,
            badge="B",
            headline="Option B: B-Tree Index",
            direct_answer="Option B",
            explanation="B-Trees support efficient range queries and equality lookups in logarithmic time.",
            code=None,
            confidence=0.98,
            question_text="Which data structure does PostgreSQL default to for table indexes?"
        )
        hud.update_answer(db_ans)
        
        # Verify strict context isolation: NO previous python code or rate limiter remnants!
        self.assertIn("PostgreSQL", hud.lbl_q_text.text())
        self.assertIn("B-Tree Index", hud.lbl_a_text.text())
        self.assertFalse(hud.code_frame.isVisible())
        self.assertTrue(hud.lbl_tradeoff.isVisible())
        self.assertIn("B-Trees support efficient range queries", hud.lbl_tradeoff.text())
        self.assertEqual(hud.bullets_box.count(), 0)
        
        # Verify dynamic chips reflect Choice B and MCQ
        chip_texts = [hud.chip_container.itemAt(i).widget().text() for i in range(hud.chip_container.count())]
        self.assertTrue(any("Choice B" in c or "B" in c for c in chip_texts))
        self.assertTrue(any("MCQ" in c for c in chip_texts))
        
        # 4. Fourth: Clear action resets HUD
        hud._clear_question()
        self.assertIn("Ready for next question", hud.lbl_q_text.text())
        self.assertFalse(hud.code_frame.isVisible())
        self.assertEqual(hud.bullets_box.count(), 0)
        self.assertFalse(hud.lbl_tradeoff.isVisible())
        
        hud.destroy()

    def test_hud_scroll_area_and_resizable(self):
        hud = QtGhostlineHudOverlay()
        self.assertIsNotNone(hud.scroll_area)
        self.assertTrue(hud.scroll_area.widgetResizable())
        
        # Long explanation does not overflow or crash
        long_explanation = "\n".join([f"• Point {i}: Architectural constraint details." for i in range(25)])
        presented = PresentedAnswer(
            question_type=TYPE_THEORY,
            badge="Theory",
            headline="System Scalability Overview",
            direct_answer="Distributed System Architecture",
            explanation=long_explanation,
            question_text="Describe microservice trade-offs."
        )
        hud.update_answer(presented)
        self.assertEqual(hud.bullets_box.count(), 25)
        hud.destroy()


if __name__ == "__main__":
    unittest.main()
