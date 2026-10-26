"""
Regression Test Suite for Ghostline PyQt6 UI, Hotkey System, and Threading Architecture.
Validates:
- Hotkey string parsing and Win32 keycodes for all global shortcuts:
  Alt + /, Alt + A, Alt + L, Alt + T, Alt + Q
- QtEventBridge cross-thread signals and queued slot invocation
- QtGhostlineHudOverlay methods (update_audio_status, update_answer, set_state, error handling)
- QtLiveAudioPanel methods (set_capture_state, set_pause_state, update_level, update_partial, append_final_segment)
- QtGhostlineMainWindow methods (update_audio_status, _save_settings, history refresh)
- Error recovery and graceful non-blocking behavior
"""

import os
import sys
import json
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import win32con
from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists for GUI component testing
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ghostline.app import QtEventBridge, parse_hotkey_string
from ghostline.config import AppConfig
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.core.pipeline import AnswerResult, ParsedQuestion, PipelineExecutionResult
from ghostline.ui.presentation import (
    build_answer_presentation,
    TYPE_MCQ,
    TYPE_UNCERTAIN,
    TYPE_ERROR
)


class TestHotkeyParsing(unittest.TestCase):
    """Test hotkey string parsing across standard and custom shortcuts."""

    def test_parse_default_solve_hotkey(self):
        mod, vk = parse_hotkey_string("Alt + /")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, 0xBF)  # VK_OEM_2

    def test_parse_audio_toggle_hotkey(self):
        mod, vk = parse_hotkey_string("Alt + L")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, ord('L'))

    def test_parse_audio_assist_hotkey(self):
        mod, vk = parse_hotkey_string("Alt + A")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, ord('A'))

    def test_parse_hud_toggle_hotkey(self):
        mod, vk = parse_hotkey_string("Alt + T")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, ord('T'))

    def test_parse_audio_ask_hotkey(self):
        mod, vk = parse_hotkey_string("Alt + Q")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, ord('Q'))

    def test_parse_complex_hotkey(self):
        mod, vk = parse_hotkey_string("Ctrl + Alt + S")
        self.assertEqual(mod, win32con.MOD_CONTROL | win32con.MOD_ALT)
        self.assertEqual(vk, ord('S'))

    def test_parse_function_key(self):
        mod, vk = parse_hotkey_string("Win + Shift + F5")
        self.assertEqual(mod, win32con.MOD_WIN | win32con.MOD_SHIFT)
        self.assertEqual(vk, win32con.VK_F5)


class TestQtEventBridge(unittest.TestCase):
    """Test that all cross-thread signals are defined and can be emitted and received."""

    def setUp(self):
        self.bridge = QtEventBridge()

    def test_signals_emission(self):
        received = {}

        def on_solve_started():
            received["started"] = True

        def on_solve_completed(res):
            received["completed"] = res

        def on_audio_status(capturing, paused):
            received["audio_status"] = (capturing, paused)

        self.bridge.sig_solve_started.connect(on_solve_started)
        self.bridge.sig_solve_completed.connect(on_solve_completed)
        self.bridge.sig_audio_status.connect(on_audio_status)

        self.bridge.sig_solve_started.emit()
        self.bridge.sig_solve_completed.emit("test_result")
        self.bridge.sig_audio_status.emit(True, False)

        QApplication.processEvents()

        self.assertTrue(received.get("started"))
        self.assertEqual(received.get("completed"), "test_result")
        self.assertEqual(received.get("audio_status"), (True, False))


class TestQtHudOverlayRegression(unittest.TestCase):
    """Test HUD overlay state transitions and missing-method regression fixes."""

    def setUp(self):
        self.config = AppConfig()
        self.hud = QtGhostlineHudOverlay(self.config)

    def tearDown(self):
        self.hud.close()

    def test_update_audio_status(self):
        # 1. Capturing and unpaused
        self.hud.update_audio_status(is_capturing=True, is_paused=False)
        self.assertIn("Listening", self.hud.lbl_a_text.text())

        # 2. Capturing and paused
        self.hud.update_audio_status(is_capturing=True, is_paused=True)
        self.assertIn("paused", self.hud.lbl_a_text.text())

        # 3. Not capturing
        self.hud.update_audio_status(is_capturing=False, is_paused=False)
        self.assertIn("Hover or press", self.hud.lbl_a_text.text())

    def test_update_answer_presentation_with_explanation(self):
        pq = ParsedQuestion(
            question_text="What is the time complexity of binary search?",
            options={"A": "O(1)", "B": "O(log n)", "C": "O(n)", "D": "O(n^2)"},
            question_type="mcq"
        )
        ar = AnswerResult(
            source_option_label="B",
            answer_option="B",
            proposed_option="B",
            validation_status="validated",
            is_validated=True,
            confidence=0.98,
            explanation="Binary search divides search interval in half every step.",
            question_type="mcq"
        )
        presentation = build_answer_presentation(pq, ar)
        self.hud.update_answer(presentation)

        # Check that answer is displayed in lbl_a_text
        self.assertIn("B", self.hud.lbl_a_text.text())
        # Check that explanation is displayed in lbl_tradeoff
        self.assertIn("Binary search divides", self.hud.lbl_tradeoff.text())
        # Check badge is green/gold star
        self.assertIn("Answer", self.hud.lbl_a_star.text())

    def test_error_and_uncertainty_handling(self):
        pq = ParsedQuestion(
            question_text="Unclear text",
            options={},
            question_type="mcq"
        )
        ar = AnswerResult(
            source_option_label="?",
            proposed_option="?",
            answer_option="?",
            validation_status="uncertain",
            is_validated=False,
            error="Unreliable question extraction: does not contain question indicators",
            question_type="uncertain"
        )
        presentation = build_answer_presentation(pq, ar)
        self.hud.set_state("error", presentation=presentation)

        self.assertIn("Notice", self.hud.lbl_a_star.text())
        self.assertIn("Hover cursor", self.hud.lbl_tradeoff.text())


class TestQtLiveAudioPanelRegression(unittest.TestCase):
    """Test Live Audio Panel methods, capture state toggles, and UI updates."""

    def setUp(self):
        self.config = AppConfig()
        self.panel = QtLiveAudioPanel(self.config)

    def tearDown(self):
        self.panel.close()

    def test_set_capture_state(self):
        # Test start capturing
        self.panel.set_capture_state(True)
        self.assertTrue(self.panel.is_recording)
        self.assertIn("Stop Listening", self.panel.btn_capture.text())

        # Test stop capturing
        self.panel.set_capture_state(False)
        self.assertFalse(self.panel.is_recording)
        self.assertIn("Start Listening", self.panel.btn_capture.text())

    def test_set_pause_state(self):
        self.panel.set_pause_state(True)
        self.assertTrue(self.panel.is_paused)
        self.assertEqual(self.panel.btn_pause.text(), "Resume")

        self.panel.set_pause_state(False)
        self.assertFalse(self.panel.is_paused)
        self.assertEqual(self.panel.btn_pause.text(), "Pause")

    def test_update_level_and_partial(self):
        # Update audio level meters without throwing
        self.panel.update_level("mic", 0.65, 0.90)
        self.panel.update_level("call", 0.40, 0.70)

        # Update partial transcription
        self.panel.update_partial("Testing speech transcription live", "mic")
        self.assertIn("Testing speech transcription live", self.panel.lbl_partial.text())


class TestQtMainWindowRegression(unittest.TestCase):
    """Test Main Window audio controls, settings save, and history display."""

    def setUp(self):
        self.config = AppConfig()
        self.main_win = QtGhostlineMainWindow(self.config)

    def tearDown(self):
        self.main_win.close()

    def test_update_audio_status(self):
        self.main_win.update_audio_status(is_capturing=True, is_paused=False)
        self.assertIn("Stop Listening", self.main_win.btn_audio.text())

        self.main_win.update_audio_status(is_capturing=False, is_paused=False)
        self.assertIn("Start Listening", self.main_win.btn_audio.text())

    @patch("PyQt6.QtWidgets.QMessageBox.information")
    def test_save_settings_persists_model_and_endpoint(self, mock_msgbox):
        saved = []
        self.main_win.on_settings_saved = lambda cfg: saved.append(cfg)

        # Change model in combo box and endpoint in text field
        self.main_win.combo_model.setCurrentText("mistral:7b")
        self.main_win.txt_endpoint.setText("http://127.0.0.1:11434")

        self.main_win._save_settings()

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].model_name, "mistral:7b")
        self.assertEqual(saved[0].ollama_url, "http://127.0.0.1:11434")

    def test_history_refresh_renders_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_history = Path(tmpdir) / "history.jsonl"
            entry = {
                "timestamp": time.time(),
                "cursor_pos": [100, 200],
                "question": "What is 2 + 2?",
                "options": ["A) 3", "B) 4", "C) 5"],
                "proposed_answer": "B",
                "answer": "B",
                "is_validated": True,
                "confidence": 1.0,
                "explanation": "Basic arithmetic addition.",
                "timing_ms": {"capture": 10, "ocr": 20, "llm": 150, "total": 180}
            }
            with open(tmp_history, "w", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            with patch("ghostline.ui.qt_main_window.get_app_dir", return_value=Path(tmpdir)):
                self.main_win._refresh_history()
                # Ensure card was added to history list layout
                self.assertGreater(self.main_win.history_list_layout.count(), 0)


if __name__ == "__main__":
    unittest.main()
