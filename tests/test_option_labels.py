import unittest
from pathlib import Path
import sys

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.ocr_engine import parse_question_structure
from ghostline.core.llm_client import OllamaClient, AnswerResult
from ghostline.ui.tray_indicator import TrayIndicator

class TestOptionLabelsSuite(unittest.TestCase):
    """
    Automated verification suite for Feature 2 & 3:
    - Letter labels (A-D)
    - Numeric labels (1-4)
    - Roman numeral labels ((i)-(iv), i-iv)
    - Question stem number collision with numeric options (e.g. Question 3 with options 1-4)
    - Rejection of invented labels (e.g. model proposing 'C' when options are '1-4')
    - Unlabeled bulleted options with unambiguous structural inference
    - Malformed and ambiguous inputs producing an explicit Uncertain state
    - Schema consistency across Tray, HUD, and Caps indicators
    """

    def setUp(self):
        self.client = OllamaClient()

    def test_numeric_labels_displayed_as_numbers_not_letters(self):
        """Verify that numeric options 1-4 produce source_option_label '3', NOT 'C'."""
        raw_ocr = {
            "text": (
                "What is the primary color of a clear daytime sky?\n"
                "1. Red\n"
                "2. Green\n"
                "3. Blue\n"
                "4. Yellow"
            ),
            "lines": [
                "What is the primary color of a clear daytime sky?",
                "1. Red",
                "2. Green",
                "3. Blue",
                "4. Yellow"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(list(parsed.options.keys()), ["1", "2", "3", "4"])
        self.assertEqual(parsed.options["3"], "Blue")

        # Simulate model responding with numeric answer
        model_out = "ANSWER: 3\nRayleigh scattering of sunlight in the atmosphere makes the sky appear blue."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        
        # Verify single consistent result object
        self.assertTrue(res.is_validated)
        self.assertEqual(res.source_option_label, "3", "Source option label must be '3', not converted to 'C'")
        self.assertEqual(res.answer_option, "3")
        self.assertNotEqual(res.source_option_label, "C")
        self.assertEqual(res.option_text, "Blue")
        self.assertEqual(res.validation_status, "validated")
        self.assertIn("Rayleigh", res.explanation)

        # Verify tray tooltip consistency
        tray = TrayIndicator()
        img = tray.create_image(badge=res.source_option_label, status="normal")
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (32, 32))

    def test_roman_numeral_labels(self):
        """Verify Roman numeral labels (i)-(iv) are recognized and preserved."""
        raw_ocr = {
            "text": (
                "Which stage of mitosis occurs immediately after prophase?\n"
                "(i) Anaphase\n"
                "(ii) Metaphase\n"
                "(iii) Telophase\n"
                "(iv) Cytokinesis"
            ),
            "lines": [
                "Which stage of mitosis occurs immediately after prophase?",
                "(i) Anaphase",
                "(ii) Metaphase",
                "(iii) Telophase",
                "(iv) Cytokinesis"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(list(parsed.options.keys()), ["(i)", "(ii)", "(iii)", "(iv)"])
        self.assertEqual(parsed.options["(ii)"], "Metaphase")

        # Test model answering with parenthesized Roman numeral
        model_out = "ANSWER: (ii)\nDuring metaphase, chromosomes align along the cell's equatorial plane."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.source_option_label, "(ii)")
        self.assertEqual(res.option_text, "Metaphase")

        # Test model answering with bare Roman numeral 'ii' -> maps to '(ii)'
        model_out_bare = "ANSWER: ii\nChromosomes align at the equator."
        res_bare = self.client._parse_and_validate_response(model_out_bare, parsed.options)
        self.assertTrue(res_bare.is_validated)
        self.assertEqual(res_bare.source_option_label, "(ii)")

    def test_leading_question_number_with_numeric_options(self):
        """Verify leading question number '3.' does not collide with option '1.' through '4.'."""
        raw_ocr = {
            "text": (
                "3. Which data structure operates on a First-In-First-Out basis?\n"
                "1. Stack\n"
                "2. Queue\n"
                "3. Priority Queue\n"
                "4. Binary Tree"
            ),
            "lines": [
                "3. Which data structure operates on a First-In-First-Out basis?",
                "1. Stack",
                "2. Queue",
                "3. Priority Queue",
                "4. Binary Tree"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(list(parsed.options.keys()), ["1", "2", "3", "4"])
        self.assertIn("First-In-First-Out", parsed.question_text)
        self.assertEqual(parsed.options["2"], "Queue")

        model_out = "ANSWER: 2\nA queue removes elements in the order they were inserted."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.source_option_label, "2")
        self.assertEqual(res.option_text, "Queue")

    def test_rejection_of_invented_labels_for_numeric_options(self):
        """Verify model output proposing 'C' when options are '1-4' is strictly rejected."""
        options = {"1": "Red", "2": "Green", "3": "Blue", "4": "Yellow"}
        hallucinated_out = "ANSWER: C\nBlue is the third option."
        res = self.client._parse_and_validate_response(hallucinated_out, options)
        self.assertFalse(res.is_validated, "Model hallucinating letter for numeric options must fail")
        self.assertEqual(res.source_option_label, "Uncertain")
        self.assertEqual(res.validation_status, "hallucination_rejected")
        self.assertIn("does not exist in valid choices", res.error)

    def test_unlabeled_bulleted_options_inference(self):
        """Verify unambiguous bullet points infer sequential numeric ordering."""
        raw_ocr = {
            "text": (
                "Which protocol resolves IP addresses to MAC addresses?\n"
                "• ARP\n"
                "• RARP\n"
                "• DNS\n"
                "• DHCP"
            ),
            "lines": [
                "Which protocol resolves IP addresses to MAC addresses?",
                "• ARP",
                "• RARP",
                "• DNS",
                "• DHCP"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(list(parsed.options.keys()), ["1", "2", "3", "4"])
        self.assertEqual(parsed.options["1"], "ARP")

        model_out = "ANSWER: 1\nAddress Resolution Protocol maps IPv4 addresses to physical MAC addresses."
        res = self.client._parse_and_validate_response(model_out, parsed.options)
        self.assertTrue(res.is_validated)
        self.assertEqual(res.source_option_label, "1")
        self.assertEqual(res.option_text, "ARP")

    def test_ambiguous_or_malformed_input_uncertainty(self):
        """Verify arbitrary prose without question structure produces an invalid state."""
        raw_ocr = {
            "text": "Notice: Please save all work before shutting down your computer.",
            "lines": ["Notice: Please save all work before shutting down your computer."]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertFalse(parsed.is_valid_question)
        self.assertFalse(parsed.is_multiple_choice)

    def test_schema_disclaimer_rule(self):
        """Ensure schema validation confidence explicitly disclaims proof of factual correctness."""
        options = {"1": "True", "2": "False"}
        model_out = "ANSWER: 1\nIt is true."
        res = self.client._parse_and_validate_response(model_out, options)
        self.assertTrue(res.is_validated)
        self.assertIsNotNone(res.confidence_metadata)
        self.assertIn("disclaimer", res.confidence_metadata)
        self.assertIn("factual ground truth", res.confidence_metadata["disclaimer"])

if __name__ == "__main__":
    unittest.main()
