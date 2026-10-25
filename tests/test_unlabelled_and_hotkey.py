import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from PIL import Image
from ghostline.core.ocr_engine import run_native_ocr, parse_question_structure
from ghostline.core.llm_client import OllamaClient, AnswerResult, normalize_tray_badge
from ghostline.ui.tray_indicator import TrayIndicator
from ghostline.ui.hud_overlay import GhostlineHudOverlay
from ghostline.config import AppConfig


class TestUnlabelledMCQAndBadgeNormalization(unittest.TestCase):
    def setUp(self):
        self.llm = OllamaClient()

    def test_bulleted_unlabelled_mcq_parsing(self):
        """Verify bulleted options are parsed as 1-based indexed unlabelled MCQ."""
        ocr_text = (
            "What is the capital of France?\n"
            "- Paris\n"
            "- London\n"
            "- Rome\n"
            "- Madrid\n"
        )
        parsed = parse_question_structure(ocr_text)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertTrue(parsed.is_unlabelled_mcq)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["1"], "Paris")
        self.assertEqual(parsed.options["2"], "London")
        self.assertEqual(parsed.options["3"], "Rome")
        self.assertEqual(parsed.options["4"], "Madrid")

    def test_genuinely_unlabelled_plain_list_parsing(self):
        """Verify plain candidate option lines without bullets are recognized as unlabelled MCQ."""
        ocr_text = (
            "Which element has atomic number 1?\n"
            "Hydrogen\n"
            "Helium\n"
            "Lithium\n"
            "Beryllium\n"
        )
        parsed = parse_question_structure(ocr_text)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertTrue(parsed.is_unlabelled_mcq)
        self.assertEqual(parsed.options["1"], "Hydrogen")
        self.assertEqual(parsed.options["2"], "Helium")
        self.assertEqual(parsed.options["3"], "Lithium")
        self.assertEqual(parsed.options["4"], "Beryllium")

    def test_labelled_options_preserve_original_labels(self):
        """Verify letter, numeric, and Roman numeral labels are preserved."""
        # Letter labels
        text_letters = "What color is the sky?\nA. Blue\nB. Green\nC. Red\nD. Yellow"
        p_letters = parse_question_structure(text_letters)
        self.assertFalse(p_letters.is_unlabelled_mcq)
        self.assertEqual(list(p_letters.options.keys()), ["A", "B", "C", "D"])

        # Numeric labels
        text_num = "Select choice:\n1. Alpha\n2. Beta\n3. Gamma"
        p_num = parse_question_structure(text_num)
        self.assertFalse(p_num.is_unlabelled_mcq)
        self.assertEqual(list(p_num.options.keys()), ["1", "2", "3"])

        # Roman numerals
        text_roman = "Match statement:\n(i) First item\n(ii) Second item"
        p_roman = parse_question_structure(text_roman)
        self.assertFalse(p_roman.is_unlabelled_mcq)
        self.assertIn("(i)", p_roman.options)
        self.assertIn("(ii)", p_roman.options)

    def test_no_false_option_from_years_decimals_arithmetic(self):
        """Verify years, decimals (3.14), and arithmetic are not parsed as option prefixes."""
        text = (
            "In 1999, the constant pi was estimated as 3.14 in school.\n"
            "Calculate 2 + 2 = 4 and choose:\n"
            "A) Correct\n"
            "B) Incorrect"
        )
        parsed = parse_question_structure(text)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertFalse(parsed.is_unlabelled_mcq)
        self.assertEqual(list(parsed.options.keys()), ["A", "B"])
        self.assertNotIn("1999", parsed.options)
        self.assertNotIn("3", parsed.options)

    def test_unlabelled_mcq_model_selection_and_tray_badge(self):
        """Verify unlabelled MCQ produces 1-based index badge in tray, full text in answer panel."""
        options = {
            "1": "Paris",
            "2": "London",
            "3": "Rome",
            "4": "Madrid"
        }
        mock_raw = "ANSWER: 1\nParis is the capital of France."
        
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"response": mock_raw}
            mock_post.return_value.raise_for_status = MagicMock()
            ans = self.llm.solve_question(
                question_text="What is the capital of France?",
                options=options,
                is_unlabelled_mcq=True
            )
            self.assertTrue(ans.is_validated)
            self.assertEqual(ans.source_option_label, "1")
            self.assertEqual(ans.tray_badge, "1")
            self.assertEqual(ans.option_text, "Paris")
            self.assertIn("Paris is the capital", ans.explanation)

    def test_open_ended_question_tray_badge_and_answer_panel(self):
        """Verify open-ended questions produce '✓' tray badge, full text in explanation and answer."""
        mock_raw = "Canberra\nCanberra is the federal capital of Australia."
        
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"response": mock_raw}
            mock_post.return_value.raise_for_status = MagicMock()
            ans = self.llm.solve_question(
                question_text="What is the capital of Australia?",
                options={},
                is_unlabelled_mcq=False
            )
            self.assertTrue(ans.is_validated)
            self.assertEqual(ans.tray_badge, "✓")
            self.assertEqual(ans.option_text, "Canberra")
            self.assertIn("Canberra", ans.explanation)

    def test_centralized_tray_badge_normalization(self):
        """Ensure normalize_tray_badge never allows long strings to reach the tray renderer."""
        # Genuinely unlabelled index
        self.assertEqual(normalize_tray_badge("1", is_validated=True, is_multiple_choice=True), "1")
        # Labelled MCQ
        self.assertEqual(normalize_tray_badge("B", is_validated=True, is_multiple_choice=True), "B")
        self.assertEqual(normalize_tray_badge("(iv)", is_validated=True, is_multiple_choice=True), "(iv)")
        # Open-ended
        self.assertEqual(normalize_tray_badge("Canberra", is_validated=True, is_multiple_choice=False), "✓")
        # Accidental full answer passed with is_multiple_choice=True
        self.assertEqual(normalize_tray_badge("Paris is the capital of France", is_validated=True, is_multiple_choice=True), "✓")
        # Uncertain / Malformed
        self.assertEqual(normalize_tray_badge("?", is_validated=False), "?")
        self.assertEqual(normalize_tray_badge("Uncertain", is_validated=False), "?")
        self.assertEqual(normalize_tray_badge("!", status="error"), "!")
        # Ready / Thinking
        self.assertEqual(normalize_tray_badge("", status="thinking"), "")
        self.assertEqual(normalize_tray_badge("", status="ready"), "R")

    def test_tray_indicator_rejects_full_string_badge(self):
        """Verify TrayIndicator renders concise glyph even if full string is passed to update_badge."""
        tray = TrayIndicator()
        tray.start()
        try:
            # Pass long string directly to update_badge
            tray.update_badge(badge="Paris is the capital", is_multiple_choice=True)
            self.assertLessEqual(len(tray.current_badge), 4)
            self.assertEqual(tray.current_badge, "✓")
        finally:
            tray.stop()

    def test_malformed_ocr_uncertainty_badge(self):
        """Verify malformed OCR or ambiguous choices result in uncertainty badge '?'."""
        mock_raw = "ANSWER: Z\nHallucinated choice not in options."
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"response": mock_raw}
            mock_post.return_value.raise_for_status = MagicMock()
            ans = self.llm.solve_question(
                question_text="Sample question?",
                options={"A": "Alpha", "B": "Beta"}
            )
            self.assertFalse(ans.is_validated)
            self.assertEqual(ans.tray_badge, "?")


class TestAltSlashHotkeyAndLifecycle(unittest.TestCase):
    def test_native_ocr_uses_create_no_window(self):
        """Verify run_native_ocr passes CREATE_NO_WINDOW and SW_HIDE to prevent console flashing."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"lines": ["Sample OCR"]}')
            img = Image.new("RGB", (100, 100), color="white")
            
            run_native_ocr(img)
            self.assertTrue(mock_run.called)
            kwargs = mock_run.call_args[1]
            
            # Check creationflags
            if sys.platform == "win32":
                self.assertEqual(kwargs.get("creationflags"), 0x08000000)
                startupinfo = kwargs.get("startupinfo")
                self.assertIsNotNone(startupinfo)
                self.assertEqual(startupinfo.wShowWindow, 0)

    def test_hud_timeout_and_dismiss_timer(self):
        """Verify GhostlineHudOverlay manages timeout_sec and cancels dismiss timer properly."""
        hud = GhostlineHudOverlay()
        self.assertEqual(hud.timeout_sec, 0.0)
        self.assertIsNone(hud._dismiss_timer)

        # Launch HUD headless/dummy
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            hud.launch(parent=root, start_visible=False)
            hud.timeout_sec = 5.0
            
            # Apply answer state
            hud._apply_state("answer", "Paris", "1")
            self.assertIsNotNone(hud._dismiss_timer)
            
            # State change cancels timer
            hud._apply_state("ready", "", "")
            self.assertIsNone(hud._dismiss_timer)
        finally:
            hud.destroy()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
