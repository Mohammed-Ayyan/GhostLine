"""
Integration test verifying real saved screenshots of MCQs feeding OCR/parsing,
plus checking that the signal/slot path ends in a HUD widget with visible text.
"""

import sys
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ghostline.config import AppConfig
from ghostline.core.ocr_engine import run_native_ocr, parse_question_structure
from ghostline.core.pipeline import GhostlinePipeline, QuestionExtractionError
from ghostline.core.llm_client import OllamaClient
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay, ConversationCardWidget
from ghostline.audio.transcription import TranscriptSegment


def render_test_mcq_image(title: str, question: str, options: list, bg=(255, 255, 255), fg=(0, 0, 0), font_size=20):
    img = Image.new("RGB", (1200, 800), bg)
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arial.ttf", font_size + 4)
        font_q = ImageFont.truetype("arial.ttf", font_size)
        font_opt = ImageFont.truetype("arial.ttf", font_size - 1)
    except Exception:
        font_title = font_q = font_opt = ImageFont.load_default()

    y = 50
    draw.text((60, y), title, fill=fg, font=font_title)
    y += font_size + 30
    draw.text((60, y), question, fill=fg, font=font_q)
    y += (font_size * 2) + 20
    for opt in options:
        draw.text((90, y), opt, fill=fg, font=font_opt)
        y += font_size + 18
    return img


class TestRealWorldScreenshotsAndWidgetOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance()
        if cls.qt_app is None:
            cls.qt_app = QApplication(sys.argv)

    def test_01_real_mcq_screenshot_pipeline_end_to_end(self):
        """Feeds realistic rendered screenshot into OCR, structure parser, and verifies readable extraction."""
        img = render_test_mcq_image(
            title="Database Concurrency Assessment",
            question="Which isolation level in ANSI SQL prevents dirty reads but permits non-repeatable reads?",
            options=["A. Read Uncommitted", "B. Read Committed", "C. Repeatable Read", "D. Serializable"],
            bg=(248, 250, 252),
            fg=(30, 41, 59),
            font_size=18
        )
        ocr_res = run_native_ocr(img)
        self.assertGreater(len(ocr_res.get("text", "")), 50)
        parsed = parse_question_structure(ocr_res, cursor_pos=(600, 400))
        self.assertTrue(parsed.is_valid_question)
        self.assertIn("A", parsed.options)
        self.assertIn("B", parsed.options)
        self.assertIn("C", parsed.options)
        self.assertIn("D", parsed.options)

    def test_02_dark_theme_screenshot_pipeline(self):
        """Feeds realistic dark-theme screenshot into OCR and verifies contrast inversion & block extraction."""
        img = render_test_mcq_image(
            title="Python Concurrency & GIL Deep Dive",
            question="In CPython 3.11, how does the Global Interpreter Lock (GIL) affect multithreaded CPU-bound Python programs?",
            options=[
                "A. It allows multiple Python bytecodes to execute concurrently across CPU cores",
                "B. It prevents concurrent Python bytecode execution across OS threads, bottlenecking pure CPU workloads to single-core throughput",
                "C. It automatically offloads pure numerical loops to the GPU runtime",
                "D. It replaces operating system threads with greenlet coroutines"
            ],
            bg=(13, 17, 23),
            fg=(230, 237, 243),
            font_size=18
        )
        ocr_res = run_native_ocr(img)
        self.assertGreater(len(ocr_res.get("text", "")), 100)
        parsed = parse_question_structure(ocr_res, cursor_pos=(600, 400))
        self.assertTrue(parsed.is_valid_question)
        self.assertIn("B", parsed.options)

    def test_03_signal_slot_path_terminates_in_widget_with_visible_text(self):
        """Verifies that worker signals / assistant answers update the HUD into a widget containing visible text."""
        cfg = AppConfig()
        hud = QtGhostlineHudOverlay(cfg)

        # 1. Spoken Question -> sets thinking card
        hud.set_ai_thinking("Explain Dijkstra algorithm", entry_id="solve_test_1")
        QApplication.processEvents()

        entry = hud.session.get_entry("solve_test_1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.detected_question, "Explain Dijkstra algorithm")

        # 2. Spoken Answer -> finalizes card
        hud.append_ai_answer(
            full_ans="Dijkstra's algorithm finds the shortest path between nodes in a graph with non-negative edge weights using a priority queue.",
            question="Explain Dijkstra algorithm",
            entry_id="solve_test_1"
        )
        QApplication.processEvents()

        # Verify entry in session
        updated_entry = hud.session.get_entry("solve_test_1")
        self.assertEqual(updated_entry.status, "answered")
        self.assertIn("shortest path", updated_entry.answer_text)

        # Verify that cards_layout contains ConversationCardWidget with visible text
        card_widget = None
        for i in range(hud.cards_layout.count()):
            item = hud.cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ConversationCardWidget):
                if getattr(item.widget(), "entry", None) and item.widget().entry.id == "solve_test_1":
                    card_widget = item.widget()
                    break

        self.assertIsNotNone(card_widget, "ConversationCardWidget for solve_test_1 must be present in layout")
        self.assertIsNotNone(card_widget.lbl_answer, "lbl_answer widget must exist")
        self.assertTrue(len(card_widget.lbl_answer.text()) > 20, "lbl_answer must contain visible answer text")
        self.assertIn("shortest path", card_widget.lbl_answer.text())


if __name__ == "__main__":
    unittest.main()
