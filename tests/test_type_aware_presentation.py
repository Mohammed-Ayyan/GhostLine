import os
import sys
import unittest
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is in sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from ghostline.core.llm_client import AnswerResult
from ghostline.core.ocr_engine import ParsedQuestion
from ghostline.ui.presentation import (
    build_answer_presentation,
    PresentedAnswer,
    TYPE_MCQ,
    TYPE_CODE,
    TYPE_THEORY,
    TYPE_TRUE_FALSE,
    TYPE_NUMERICAL,
    TYPE_FILL_BLANK,
    TYPE_GENERIC,
    TYPE_UNCERTAIN,
    TYPE_ERROR
)
from ghostline.ui.hud_overlay import GhostlineHudOverlay


class TestAnswerResultSchemaAndImmunity(unittest.TestCase):
    """
    Verifies that AnswerResult schema safely provides optional fields with defaults
    and that no consumer crashes when code_snippet or other fields are missing.
    """

    def test_answer_result_defaults_without_code_snippet(self):
        """AnswerResult must be instantiable without code_snippet and provide safe defaults."""
        res = AnswerResult(
            answer_option="B",
            proposed_option="B",
            validation_status="match",
            is_validated=True,
            confidence=0.98,
            explanation="201 Created is the standard HTTP status code for resource creation.",
            option_text="201 Created",
            tray_badge="B"
        )
        # Verify fields exist and have canonical defaults
        self.assertIsNone(res.code_snippet)
        self.assertEqual(res.code_language, "")
        self.assertEqual(res.question_type, "mcq")
        self.assertEqual(res.direct_answer, "")
        # Accessing attribute directly must not raise AttributeError
        has_code = bool(res.code_snippet)
        self.assertFalse(has_code)

    def test_legacy_object_attribute_immunity(self):
        """Objects missing code_snippet accessed via getattr must not raise AttributeError."""
        class LegacyAnswer:
            def __init__(self):
                self.answer_option = "A"
                self.tray_badge = "A"
                self.explanation = "Legacy result"

        legacy = LegacyAnswer()
        # Ensure getattr defensive pattern works
        snippet = getattr(legacy, "code_snippet", None)
        self.assertIsNone(snippet)
        self.assertFalse(bool(snippet))

        # Presentation layer must handle legacy object gracefully
        pres = build_answer_presentation(None, legacy)
        self.assertIsNotNone(pres)
        self.assertFalse(pres.has_code)
        self.assertEqual(pres.badge, "A")


class TestTypeAwarePresentation(unittest.TestCase):
    """
    Tests centralized type detection and presentation building for:
    MCQ, Code, Theory, True/False, Numerical, and Edge Cases.
    """

    def test_mcq_with_labelled_options(self):
        """Labelled options (A/B/C/D) display prominent label and option text without duplicate prefix."""
        pq = ParsedQuestion(
            question_text="Which HTTP status code indicates a new resource was created?",
            options={
                "A": "200 OK",
                "B": "B) 201 Created",  # Raw OCR includes label prefix
                "C": "400 Bad Request",
                "D": "500 Internal Server Error"
            },
            is_multiple_choice=True
        )
        ans = AnswerResult(
            answer_option="B",
            proposed_option="B",
            source_option_label="B",
            validation_status="match",
            is_validated=True,
            confidence=0.99,
            explanation="Option B: 201 Created is returned upon successful POST.",
            option_text="B) 201 Created",
            tray_badge="B"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.question_type, TYPE_MCQ)
        self.assertEqual(pres.badge, "B")
        self.assertEqual(pres.headline, "Option B: 201 Created")
        # Explanation duplicate prefix stripped
        self.assertFalse(pres.explanation.startswith("Option B:"))
        self.assertIn("201 Created is returned", pres.explanation)
        self.assertFalse(pres.has_code)

    def test_mcq_with_roman_numerals(self):
        """MCQs with Roman numeral option labels (I, II, III, IV) are preserved."""
        pq = ParsedQuestion(
            question_text="Select the correct Roman numeral step:",
            options={
                "I": "Initialization",
                "II": "Execution",
                "III": "Termination"
            },
            is_multiple_choice=True
        )
        ans = AnswerResult(
            answer_option="II",
            source_option_label="II",
            validation_status="match",
            is_validated=True,
            option_text="Execution",
            tray_badge="II"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.question_type, TYPE_MCQ)
        self.assertEqual(pres.badge, "II")
        self.assertEqual(pres.headline, "Option II: Execution")

    def test_mcq_with_unlabelled_options(self):
        """Unlabelled options preserve original order with sequential numeric badges 1..N."""
        pq = ParsedQuestion(
            question_text="What is the capital of France?",
            options={
                "1": "Paris",
                "2": "London",
                "3": "Rome",
                "4": "Madrid"
            },
            is_multiple_choice=True
        )
        ans = AnswerResult(
            answer_option="1",
            source_option_label="1",
            validation_status="match",
            is_validated=True,
            option_text="Paris",
            tray_badge="1"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.question_type, TYPE_MCQ)
        self.assertEqual(pres.badge, "1")
        self.assertEqual(pres.headline, "Option 1: Paris")
        self.assertEqual(pres.direct_answer, "Paris")

    def test_question_numbers_not_mistaken_for_option_labels(self):
        """Question numbers in question text (e.g. '12. What is 2 + 2?') never become option labels."""
        pq = ParsedQuestion(
            question_text="12. What is 2 + 2?",
            options={
                "1": "3",
                "2": "4",
                "3": "5"
            },
            is_multiple_choice=True
        )
        ans = AnswerResult(
            answer_option="2",
            source_option_label="2",
            validation_status="match",
            is_validated=True,
            option_text="4",
            tray_badge="2"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.badge, "2")
        self.assertNotEqual(pres.badge, "12")
        self.assertNotEqual(pres.badge, "4")
        self.assertEqual(pres.headline, "Option 2: 4")

    def test_programming_code_question(self):
        """Code questions preserve code snippet, syntax language, and monospace structure."""
        code_body = "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    return -1"
        ans = AnswerResult(
            answer_option=code_body,
            validation_status="match",
            is_validated=True,
            confidence=0.95,
            explanation="Binary search runs in O(log n) time complexity.",
            code_snippet=code_body,
            code_language="python",
            question_type="code",
            direct_answer="Binary Search Implementation"
        )
        pres = build_answer_presentation(None, ans)
        self.assertEqual(pres.question_type, TYPE_CODE)
        self.assertEqual(pres.badge, "Code")
        self.assertTrue(pres.has_code)
        self.assertEqual(pres.code, code_body)
        self.assertEqual(pres.code_language, "python")
        self.assertIn("```python", pres.formatted_clipboard_text)

    def test_code_auto_extracted_from_markdown_fences(self):
        """When code_snippet is not pre-populated, extract code from markdown fences in explanation."""
        explanation_with_fence = (
            "Here is the solution function:\n\n"
            "```python\n"
            "def solve(n):\n"
            "    return n * 2\n"
            "```\n\n"
            "This doubles the input value."
        )
        ans = AnswerResult(
            answer_option="solve(n)",
            validation_status="match",
            is_validated=True,
            explanation=explanation_with_fence
        )
        pres = build_answer_presentation(None, ans)
        self.assertEqual(pres.question_type, TYPE_CODE)
        self.assertTrue(pres.has_code)
        self.assertIn("def solve(n):", pres.code)
        self.assertEqual(pres.code_language, "python")

    def test_open_ended_theory_question(self):
        """Theory questions present direct answer first, with full explanation multiline support."""
        pq = ParsedQuestion(
            question_text="Explain the principle of idempotency in REST APIs.",
            options={},
            is_multiple_choice=False
        )
        ans = AnswerResult(
            answer_option="An operation can be applied multiple times without changing the result.",
            direct_answer="An operation can be applied multiple times without changing the result.",
            validation_status="match",
            is_validated=True,
            explanation=(
                "GET, PUT, and DELETE methods are idempotent according to RFC 7231.\n"
                "Key characteristics:\n"
                "- Multiple identical requests have the same effect as a single request.\n"
                "- POST is typically not idempotent."
            ),
            question_type="theory"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.question_type, TYPE_THEORY)
        self.assertEqual(pres.badge, "✓")
        self.assertIn("idempotent", pres.explanation.lower())
        self.assertFalse(pres.has_code)

    def test_binary_true_false_question(self):
        """True/False questions detect binary choices and assign T/F badges."""
        pq = ParsedQuestion(
            question_text="HTTP/2 uses binary framing instead of textual commands.",
            options={"A": "True", "B": "False"},
            is_multiple_choice=True
        )
        ans = AnswerResult(
            answer_option="A",
            source_option_label="A",
            option_text="True",
            validation_status="match",
            is_validated=True,
            explanation="HTTP/2 encapsulates all protocol units into binary frames.",
            tray_badge="A"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.question_type, TYPE_TRUE_FALSE)
        self.assertEqual(pres.badge, "T")
        self.assertEqual(pres.headline, "Answer: True")

    def test_numerical_calculation_question(self):
        """Numerical calculation questions display result directly without mistaking number for option."""
        pq = ParsedQuestion(
            question_text="Calculate the derivative of f(x) = 4x^2 at x = 3.",
            options={},
            is_multiple_choice=False
        )
        ans = AnswerResult(
            answer_option="24",
            direct_answer="f'(3) = 24",
            validation_status="match",
            is_validated=True,
            explanation="f'(x) = 8x. At x = 3, f'(3) = 8 * 3 = 24.",
            question_type="numerical"
        )
        pres = build_answer_presentation(pq, ans)
        self.assertEqual(pres.question_type, TYPE_NUMERICAL)
        self.assertEqual(pres.badge, "✓")
        self.assertEqual(pres.headline, "Result: f'(3) = 24")

    def test_uncertain_and_error_states(self):
        """Uncertain and error results format clear diagnostic headlines and ?/! badges."""
        err_ans = AnswerResult(
            answer_option="!",
            validation_status="error",
            is_validated=False,
            error="Connection refused to Ollama daemon on port 11434.",
            tray_badge="!"
        )
        pres_err = build_answer_presentation(None, err_ans)
        self.assertEqual(pres_err.question_type, TYPE_ERROR)
        self.assertEqual(pres_err.badge, "!")
        self.assertFalse(pres_err.is_validated)

        uncert_ans = AnswerResult(
            answer_option="?",
            validation_status="uncertain",
            is_validated=False,
            explanation="LLM proposed option 'E' which does not exist in detected options.",
            tray_badge="?"
        )
        pres_unc = build_answer_presentation(None, uncert_ans)
        self.assertEqual(pres_unc.question_type, TYPE_UNCERTAIN)
        self.assertEqual(pres_unc.badge, "?")
        self.assertFalse(pres_unc.is_validated)


class TestHudOverlayEnhancements(unittest.TestCase):
    """
    Tests HUD Overlay UI controls:
    - Dedicated scrollable viewport
    - Stale response / solve ID protection
    - Expand / Collapse controls
    - Retry callback execution
    - Copy Answer & Copy Code operations
    """

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.retry_called = False

        def _on_retry():
            self.retry_called = True

        self.hud = GhostlineHudOverlay(
            on_retry=_on_retry,
            width=360,
            height=280
        )
        self.hud.launch(parent=self.root, start_visible=False)

    def tearDown(self):
        if self.hud:
            self.hud.destroy()
        if self.root:
            self.root.destroy()

    def test_stale_response_protection(self):
        """A stale solve update from an older solve_id must be discarded and not overwrite newer state."""
        # Start solve 1
        id_1 = self.hud.start_solve()
        self.assertEqual(id_1, 1)
        self.hud._apply_state("thinking", "Thinking 1...", badge="", solve_id=id_1)
        self.assertEqual(self.hud.phase, "thinking")

        # Start solve 2 (newer)
        id_2 = self.hud.start_solve()
        self.assertEqual(id_2, 2)
        pres_2 = PresentedAnswer(
            question_type=TYPE_MCQ,
            badge="B",
            headline="Option B: Correct",
            direct_answer="Correct",
            explanation="Newest solve result."
        )
        self.hud._apply_state("answer", presentation=pres_2, solve_id=id_2)
        self.assertEqual(self.hud.phase, "answer")
        self.assertEqual(self.hud.answer_badge, "B")

        # Now an out-of-order delayed update from solve 1 arrives
        pres_stale = PresentedAnswer(
            question_type=TYPE_MCQ,
            badge="A",
            headline="Option A: Stale Old Answer",
            direct_answer="Old",
            explanation="Stale solve result."
        )
        self.hud._apply_state("answer", presentation=pres_stale, solve_id=id_1)

        # Must NOT have overwritten solve 2!
        self.assertEqual(self.hud.answer_badge, "B")
        self.assertEqual(self.hud.ans_summary_label.cget("text"), "Option B: Correct")

    def test_code_block_expand_collapse(self):
        """Code block expand/collapse toggle shows and hides code_text_frame."""
        pres = PresentedAnswer(
            question_type=TYPE_CODE,
            badge="Code",
            headline="Code Solution",
            direct_answer="def f(): pass",
            explanation="Implementation",
            code="def f():\n    return 42",
            code_language="python"
        )
        self.hud._apply_state("answer", presentation=pres)
        self.assertTrue(self.hud.code_container.winfo_manager() != "")

        # Initial state is expanded
        self.assertFalse(self.hud.is_code_collapsed)
        self.assertEqual(self.hud.btn_toggle_code.cget("text"), "[-] Collapse")

        # Collapse
        self.hud.toggle_code_collapse()
        self.assertTrue(self.hud.is_code_collapsed)
        self.assertEqual(self.hud.btn_toggle_code.cget("text"), "[+] Expand")

        # Expand again
        self.hud.toggle_code_collapse()
        self.assertFalse(self.hud.is_code_collapsed)
        self.assertEqual(self.hud.btn_toggle_code.cget("text"), "[-] Collapse")

    def test_retry_control_triggers_callback(self):
        """Clicking retry button triggers registered on_retry callback."""
        self.assertFalse(self.retry_called)
        self.hud.retry_solve()
        self.assertTrue(self.retry_called)

    def test_copy_answer_and_code(self):
        """Copy answer and copy code format and copy text to system clipboard without crashing."""
        pres = PresentedAnswer(
            question_type=TYPE_CODE,
            badge="Code",
            headline="Code Solution: Fib",
            direct_answer="fib(n)",
            explanation="Computes nth Fibonacci number.",
            code="def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)",
            code_language="python"
        )
        self.hud._apply_state("answer", presentation=pres)

        # Execute copy answer and copy code
        self.hud.copy_answer_to_clipboard()
        self.hud.copy_code_to_clipboard()
        # Verify text was written to clipboard
        clip_content = self.root.clipboard_get()
        self.assertIn("def fib(n):", clip_content)


if __name__ == "__main__":
    unittest.main()
