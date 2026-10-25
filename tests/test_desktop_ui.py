import unittest
import os
import json
import time
from pathlib import Path
import tempfile
import sys
import tkinter as tk

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.config import AppConfig, load_config, save_config
from ghostline.ui.main_window import GhostlineMainWindow

class TestDesktopUIAndSettings(unittest.TestCase):
    """
    Automated verification for Ghostline Desktop UI, Navigation, History,
    Diagnostics, and Settings Persistence.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.history_path = Path(self.temp_dir.name) / "history.jsonl"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_config_defaults_and_serialization(self):
        """Verify all Phase 1-3 configuration fields load and persist properly."""
        cfg = AppConfig()
        self.assertEqual(cfg.caps_pulse_on_ms, 300)
        self.assertEqual(cfg.caps_pulse_off_ms, 250)
        self.assertEqual(cfg.caps_sequence_cooldown_ms, 700)
        self.assertFalse(cfg.caps_lock_indicator)
        self.assertTrue(cfg.show_hud_on_solve)
        self.assertFalse(cfg.start_minimized)

        # Modify settings
        cfg.caps_pulse_on_ms = 350
        cfg.caps_pulse_off_ms = 280
        cfg.caps_lock_indicator = True
        cfg.show_hud_on_solve = False
        cfg.start_minimized = True

        save_config(cfg, custom_path=self.config_path)
        self.assertTrue(self.config_path.exists())

        loaded = load_config(custom_path=self.config_path)
        self.assertEqual(loaded.caps_pulse_on_ms, 350)
        self.assertEqual(loaded.caps_pulse_off_ms, 280)
        self.assertTrue(loaded.caps_lock_indicator)
        self.assertFalse(loaded.show_hud_on_solve)
        self.assertTrue(loaded.start_minimized)

    def test_main_window_screen_navigation(self):
        """Verify GhostlineMainWindow builds and navigates between all 6 screens."""
        cfg = AppConfig()
        window = GhostlineMainWindow(config=cfg)
        root = window.build()
        self.assertIsNotNone(root)
        self.assertIsInstance(root, tk.Tk)

        try:
            # Check default screen
            self.assertEqual(window.current_screen, "dashboard")

            # Navigate to each screen (all 7 screens)
            screens = ["answer", "history", "settings", "setup", "diagnostics", "about", "dashboard"]
            for scr in screens:
                window.show_screen(scr)
                self.assertEqual(window.current_screen, scr)
                self.assertIn(scr, window.screen_frames)

            # Test window minimization and restoration states
            window.hide_to_tray()
            self.assertTrue(window._is_minimized_to_tray)

            window.show_window()
            # Process idle tasks
            root.update_idletasks()
            self.assertFalse(window._is_minimized_to_tray)
        finally:
            window.destroy()

    def test_history_loading_and_filtering(self):
        """Verify History screen handles empty files, multiple entries, and search filtering."""
        # Create dummy history entries
        entries = [
            {
                "timestamp": time.time() - 100,
                "cursor_pos": [500, 300],
                "question": "What is the capital of France?",
                "options": {"A": "Berlin", "B": "Madrid", "C": "Paris", "D": "Rome"},
                "proposed_answer": "C",
                "answer": "C",
                "is_validated": True,
                "confidence": 0.98,
                "explanation": "Paris is the capital of France.",
                "timing_ms": {"capture": 12, "ocr": 45, "llm": 250, "total": 307}
            },
            {
                "timestamp": time.time(),
                "cursor_pos": [600, 400],
                "question": "Which algorithm finds the shortest path?",
                "options": {"A": "Dijkstra", "B": "Bubble Sort", "C": "Binary Search", "D": "DFS"},
                "proposed_answer": "A",
                "answer": "A",
                "is_validated": True,
                "confidence": 0.99,
                "explanation": "Dijkstra's algorithm solves shortest paths.",
                "timing_ms": {"capture": 15, "ocr": 50, "llm": 310, "total": 375}
            }
        ]

        with open(self.history_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        cfg = AppConfig()
        window = GhostlineMainWindow(config=cfg)
        root = window.build()

        try:
            window.show_screen("history")
            window.refresh_history_list(custom_path=self.history_path)
            self.assertEqual(len(window._history_entries), 2)
            self.assertEqual(window._history_entries[0]["answer"], "A")  # Most recent first

            # Test search query filtering
            window.hist_search_var.set("France")
            window.refresh_history_list(custom_path=self.history_path)
            self.assertEqual(window.hist_listbox.size(), 1)
            self.assertIn("[C]", window.hist_listbox.get(0))
        finally:
            window.destroy()

    def test_solve_workflow_ui_lifecycle(self):
        """Verify on_solve_started and on_solve_completed update the UI without throwing exceptions."""
        cfg = AppConfig()
        window = GhostlineMainWindow(config=cfg)
        root = window.build()

        try:
            window.on_solve_started()
            root.update_idletasks()

            # Mock pipeline result
            class MockAnswer:
                source_option_label = "B"
                option_text = "Photosynthesis"
                explanation = "Plants convert sunlight into chemical energy via photosynthesis."
                is_validated = True
                confidence = 0.97
                proposed_option = "B"
                answer_option = "B"
                error = None

            class MockQuestion:
                question_text = "What process do plants use to make food?"
                options = {"A": "Respiration", "B": "Photosynthesis", "C": "Fermentation", "D": "Digestion"}

            class MockResult:
                answer_result = MockAnswer()
                parsed_question = MockQuestion()
                capture_time_ms = 14
                ocr_time_ms = 35
                llm_time_ms = 220
                total_time_ms = 269
                cursor_pos = (500, 500)

            window.on_solve_completed(MockResult())
            root.update_idletasks()

            self.assertEqual(window.ans_badge_label.cget("text"), "B")
            self.assertIn("Photosynthesis", window.ans_option_text_lbl.cget("text"))
        finally:
            window.destroy()

if __name__ == "__main__":
    unittest.main()
