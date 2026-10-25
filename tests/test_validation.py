import unittest
from pathlib import Path
import sys

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.ocr_engine import parse_question_structure, ParsedQuestion
from ghostline.core.llm_client import OllamaClient, AnswerResult
from ghostline.core.pipeline import GhostlinePipeline
from PIL import Image, ImageDraw, ImageFont

class TestValidationSuite(unittest.TestCase):
    """
    Reproducible test suite covering:
    - Clear multiple-choice questions
    - Wrapped question text and inline options
    - Missing or ambiguous options
    - Unrelated desktop UI text rejection
    - OCR mistake tolerance
    - Invalid model output handling
    - Answers containing nonexistent option labels
    """

    def setUp(self):
        self.client = OllamaClient()

    def test_clear_multiple_choice(self):
        """Verify standard 4-choice question parsing and validation."""
        raw_ocr = {
            "text": (
                "Question: Which protocol is primarily used for secure web browsing?\n\n"
                "A) FTP\n"
                "B) HTTP\n"
                "C) HTTPS\n"
                "D) SSH"
            ),
            "lines": [
                "Question: Which protocol is primarily used for secure web browsing?",
                "A) FTP",
                "B) HTTP",
                "C) HTTPS",
                "D) SSH"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(list(parsed.options.keys()), ["A", "B", "C", "D"])
        self.assertEqual(parsed.options["C"], "HTTPS")

        # Simulate model answering with structured response
        model_out = "ANSWER: C\nHTTPS uses Transport Layer Security (TLS) to encrypt HTTP requests and responses."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.answer_option, "C")
        self.assertEqual(res.confidence, 0.95)
        self.assertIn("TLS", res.explanation)

    def test_wrapped_question_text_and_inline_options(self):
        """Verify wrapped question text and multiple options on a single line."""
        raw_ocr = {
            "text": (
                "A company requires a relational database that ensures\n"
                "strong consistency (ACID) and horizontal scaling across multiple regions.\n"
                "A) Redis  B) Spanner\n"
                "C) MongoDB  D) Memcached"
            ),
            "lines": [
                "A company requires a relational database that ensures",
                "strong consistency (ACID) and horizontal scaling across multiple regions.",
                "A) Redis  B) Spanner",
                "C) MongoDB  D) Memcached"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(sorted(list(parsed.options.keys())), ["A", "B", "C", "D"])
        self.assertEqual(parsed.options["B"], "Spanner")
        self.assertIn("strong consistency", parsed.question_text)

        model_out = "ANSWER: B\nCloud Spanner offers synchronous multi-region replication with strict serializability."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.answer_option, "B")

    def test_missing_or_ambiguous_options(self):
        """Verify open-ended question without options is handled without inventing options."""
        raw_ocr = {
            "text": "What is the capital of Australia?",
            "lines": ["What is the capital of Australia?"]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertFalse(parsed.is_multiple_choice)
        self.assertEqual(parsed.options, {})

        model_out = "Canberra\nCanberra is the federal capital city of Australia."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.answer_option, "Canberra")
        self.assertNotIn("ANSWER: A", res.answer_option)

    def test_unrelated_desktop_ui_text_rejection(self):
        """Verify that captured desktop chrome/sidebar text (Entry 2) is rejected before inference."""
        chrome_text = (
            "New chat Scheduled Library Plugins Codex Explore Projects "
            "EIOT PROJECT Communication Recents Find Quiz Extension "
            "The previous Regis settings.json Untitled Edit View File Iamat"
        )
        raw_ocr = {
            "text": chrome_text,
            "lines": chrome_text.split()
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertFalse(parsed.is_valid_question, "Desktop UI chrome must NOT be classified as a valid question")
        self.assertIn("does not contain question indicators", parsed.validation_reason)

    def test_ocr_mistakes_handling(self):
        """Verify OCR punctuation/number variances (e.g. parenthesized numbers and lowercase)."""
        raw_ocr = {
            "text": (
                "1. Which of the following is an immutable sequence type in Python?\n"
                "(a) list\n"
                "(b) tuple\n"
                "(c) dict\n"
                "(d) set"
            ),
            "lines": [
                "1. Which of the following is an immutable sequence type in Python?",
                "(a) list",
                "(b) tuple",
                "(c) dict",
                "(d) set"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(sorted(list(parsed.options.keys())), ["A", "B", "C", "D"])
        self.assertEqual(parsed.options["B"], "tuple")

        model_out = "ANSWER: B\nTuples in Python are immutable sequences whose elements cannot be modified."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.answer_option, "B")

    def test_invalid_model_output_uncertainty(self):
        """Verify that rambling or unparseable output triggers an explicit Uncertain state."""
        options = {"A": "CPU", "B": "GPU", "C": "RAM", "D": "SSD"}
        rambling_out = (
            "I cannot directly answer this question because computer architecture depends on many factors. "
            "Please review standard memory hierarchy textbooks."
        )
        res = self.client._parse_and_validate_response(rambling_out, options)
        self.assertFalse(res.is_validated, "Unparseable response must not be validated")
        self.assertEqual(res.answer_option, "Uncertain")
        self.assertEqual(res.confidence, 0.0)
        self.assertIsNotNone(res.error)

    def test_answers_containing_nonexistent_option_labels(self):
        """Verify that model hallucinating an unlisted option (e.g. E when options are A-D) is rejected."""
        options = {"A": "Mercury", "B": "Venus", "C": "Earth", "D": "Mars"}
        hallucinated_out = "ANSWER: E\nJupiter is the largest planet in the solar system."
        res = self.client._parse_and_validate_response(hallucinated_out, options)
        self.assertFalse(res.is_validated, "Nonexistent option label must fail validation")
        self.assertEqual(res.answer_option, "Uncertain")
        self.assertEqual(res.confidence, 0.0)
        self.assertIn("does not exist in valid choices", res.error)

if __name__ == "__main__":
    unittest.main()
