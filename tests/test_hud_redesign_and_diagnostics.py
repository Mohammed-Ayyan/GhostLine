import os
import sys
import time
import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch
from PIL import Image

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ghostline.config import AppConfig, save_config, load_config
from ghostline.core.pipeline_tracer import PipelineTracer, StageRecord, get_foreground_window_info
from ghostline.core.capture import capture_screen_around_cursor_with_diagnostics, inspect_capture_environment
from ghostline.core.ocr_engine import parse_question_structure, _is_meaningful_question
from ghostline.core.pipeline import GhostlinePipeline, GhostlinePipeline
from ghostline.core.llm_client import AnswerResult
from ghostline.ui.caps_indicator import CapsLockIndicator
from ghostline.ui.hud_overlay import (
    GhostlineHudOverlay,
    GhostlineHudOverlay,
    C_BG_BASE, C_BG_CARD, C_EMERALD, C_AMBER, C_DANGER
)


class TestHudRedesignAndDiagnostics(unittest.TestCase):
    """
    Focused verification suite for:
    - Complete pipeline tracing (PID, HWND, stages, durations)
    - Redesigned HUD scrollable viewport, mouse-wheel, keyboard navigation
    - Code container with horizontal scrolling and Copy Code button
    - Caps Lock SendInput verification and UIPI diagnostics
    - Assessment stems and imperative question recognition
    - Window constraints and non-overflowing bounds
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.tk_root = tk.Tk()
            cls.tk_root.withdraw()
        except Exception:
            cls.tk_root = None

    @classmethod
    def tearDownClass(cls):
        if cls.tk_root:
            try:
                cls.tk_root.destroy()
            except Exception:
                pass
            cls.tk_root = None

    # -------------------------------------------------------------
    # 1. PipelineTracer & Stage Diagnostics
    # -------------------------------------------------------------
    def test_pipeline_tracer_lifecycle_and_report(self):
        tracer = PipelineTracer()
        tracer.start_trace()
        self.assertEqual(tracer.process_id, os.getpid())
        self.assertIn("hwnd", tracer.foreground_window)

        # Stage 1: Capture
        s1 = tracer.begin_stage("Screen Capture", {"bbox": (0, 0, 900, 600)})
        time.sleep(0.01)
        tracer.end_stage(s1, success=True, details={"grab_method": "all_screens"})
        self.assertTrue(s1.success)
        self.assertGreater(s1.duration_ms, 0)

        # Stage 2: OCR
        s2 = tracer.begin_stage("OCR")
        time.sleep(0.01)
        tracer.end_stage(s2, success=True, details={"char_count": 150})
        self.assertTrue(s2.success)

        # Stage 3: Question Extraction
        s3 = tracer.begin_stage("Question Extraction")
        tracer.end_stage(s3, success=False, error="Empty question text.")
        self.assertFalse(s3.success)
        self.assertEqual(s3.error, "Empty question text.")

        summary = tracer.get_summary_report()
        self.assertIn("Pipeline Trace", summary)
        self.assertIn("Screen Capture", summary)
        self.assertIn("OCR", summary)
        self.assertIn("FAIL (Empty question text.)", summary)

        d = tracer.to_dict()
        self.assertEqual(len(d["stages"]), 3)
        self.assertFalse(d["overall_success"])

    # -------------------------------------------------------------
    # 2. Capture Environment & Display Affinity Telemetry
    # -------------------------------------------------------------
    def test_capture_environment_and_blank_detection(self):
        env = inspect_capture_environment()
        self.assertIn("hwnd", env)
        self.assertIn("display_affinity", env)
        self.assertIn("is_capture_protected", env)

        # Test capture with diagnostics returns valid telemetry
        img, bbox, diag = capture_screen_around_cursor_with_diagnostics(width=200, height=150)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(len(bbox), 4)
        self.assertIn("cursor", diag)
        self.assertIn("is_blank_frame", diag)
        self.assertIn("grab_method", diag)

    # -------------------------------------------------------------
    # 3. Assessment Question Recognition (Imperative & Code Stems)
    # -------------------------------------------------------------
    def test_assessment_imperative_verbs_and_code_stems(self):
        # Math problem without '?'
        q1 = "Solve for x in the equation: 5x + 15 = 40"
        valid, reason = _is_meaningful_question(q1, {})
        self.assertTrue(valid, f"Failed on: {q1} ({reason})")

        # Evaluate imperative stem
        q2 = "Evaluate the following limit as x approaches zero"
        valid, reason = _is_meaningful_question(q2, {})
        self.assertTrue(valid, f"Failed on: {q2} ({reason})")

        # Code-based stem
        q3 = "def calculate_sum(nums):\n    return sum(nums)\nConsider the function above"
        valid, reason = _is_meaningful_question(q3, {})
        self.assertTrue(valid, f"Failed on: {q3} ({reason})")

        # UI desktop garbage must still be rejected
        garbage = "File Edit View Terminal Help Run Debug Settings"
        valid, reason = _is_meaningful_question(garbage, {})
        self.assertFalse(valid, "UI chrome must be rejected")

    # -------------------------------------------------------------
    # 4. Caps Lock Indicator: SendInput, State Verification & Decoupling
    # -------------------------------------------------------------
    def test_caps_indicator_pulse_counts_and_pause(self):
        ind = CapsLockIndicator(enabled=True)
        # Pulse mapping
        self.assertEqual(ind.label_to_pulse_count("A"), 1)
        self.assertEqual(ind.label_to_pulse_count("2"), 2)
        self.assertEqual(ind.label_to_pulse_count("C"), 3)
        self.assertEqual(ind.label_to_pulse_count("D"), 4)
        self.assertEqual(ind.label_to_pulse_count("5"), 5)
        self.assertEqual(ind.label_to_pulse_count("?"), 2)
        self.assertEqual(ind.label_to_pulse_count("!"), 3)

        # Pause / Resume behavior
        ind.pause()
        self.assertTrue(ind.is_paused)
        # Pulse should be ignored while paused
        ind.pulse("A")
        self.assertFalse(ind.is_pulsing)

        ind.resume()
        self.assertFalse(ind.is_paused)

    def test_caps_indicator_hardware_query(self):
        state = CapsLockIndicator.get_caps_state()
        self.assertIn(state, [0, 1])

        # Test toggle verification method
        ind = CapsLockIndicator(enabled=True)
        # Verify test_toggle runs without exception and preserves state
        initial = ind.get_caps_state()
        ind.test_toggle()
        after = ind.get_caps_state()
        self.assertEqual(initial, after, "Initial caps lock state must be restored after test_toggle")

    # -------------------------------------------------------------
    # 5. Redesigned HUD Overlay: Viewport, Scrolling, Constraints
    # -------------------------------------------------------------
    def test_hud_scrollable_viewport_and_controls(self):
        if not self.tk_root:
            self.skipTest("Tkinter display not available")

        hud = GhostlineHudOverlay(
            opacity=0.92,
            width=380,
            height=300,
            max_width=500,
            max_height=420,
            scroll_speed=2
        )
        hud.launch(parent=self.tk_root, start_visible=False)

        # Verify dedicated Canvas viewport exists
        self.assertIsNotNone(hud.canvas)
        self.assertIsNotNone(hud.v_scrollbar)
        self.assertIsNotNone(hud.scrollable_content)

        # Verify Selectable Explanation Text Widget exists
        self.assertIsNotNone(hud.explanation_text)
        self.assertEqual(hud.explanation_text.cget("wrap"), "word")

        # Verify Code container exists
        self.assertIsNotNone(hud.code_container)
        self.assertIsNotNone(hud.code_scroll_x)

        # Verify Header and Footer buttons
        self.assertIsNotNone(hud.btn_copy_ans)
        self.assertIsNotNone(hud.btn_copy_code)
        self.assertIsNotNone(hud.btn_min)
        self.assertIsNotNone(hud.btn_pin)
        self.assertIsNotNone(hud.btn_pause)

        # Test State: Thinking (Spinner starts)
        hud.set_state("thinking")
        self.tk_root.update()
        self.assertEqual(hud.phase, "thinking")
        self.assertTrue(hud._spinner_running)

        # Test State: Long Answer (Viewport populates, scroll position resets to 0.0)
        long_explanation = (
            "This is a comprehensive multi-step explanation designed to test dedicated viewport scrolling.\n" * 12
        )
        code_sample = "```python\ndef solution():\n    return 'verified'\n```"
        full_text = f"{long_explanation}\n{code_sample}"

        hud.set_state("answer", text=full_text, badge="B")
        self.tk_root.update()

        self.assertEqual(hud.phase, "answer")
        self.assertEqual(hud.answer_badge, "B")
        self.assertFalse(hud._spinner_running)
        self.assertEqual(hud.badge_label.cget("text"), "B")

        # Verify canvas yview is at top (0.0)
        yview = hud.canvas.yview()
        self.assertAlmostEqual(yview[0], 0.0, places=1)

        # Test mousewheel & keyboard scroll simulation
        hud._on_key_scroll(1)
        self.tk_root.update()

        hud._on_key_page_scroll(1)
        self.tk_root.update()

        # Test minimize & expand
        hud.toggle_minimize()
        self.tk_root.update()
        self.assertTrue(hud.is_minimized)
        self.assertEqual(hud.btn_min.cget("text"), "⤢")

        hud.toggle_minimize()
        self.tk_root.update()
        self.assertFalse(hud.is_minimized)
        self.assertEqual(hud.btn_min.cget("text"), "—")

        # Test Error State
        hud.set_state("error", text="Capture timeout or unreadable question", badge="!")
        self.tk_root.update()
        self.assertEqual(hud.phase, "error")
        self.assertEqual(hud.status_label.cget("text"), "Error (!)")

        # Test Uncertainty State
        hud.set_state("error", text="Low confidence inference", badge="?")
        self.tk_root.update()
        self.assertEqual(hud.status_label.cget("text"), "Uncertain (?)")

        # Test Clipboard copy
        hud.copy_answer_to_clipboard()
        self.tk_root.update()
        self.assertEqual(hud.btn_copy_ans.cget("text"), "✓ Copied!")

        hud.destroy()

    # -------------------------------------------------------------
    # 6. Configuration Persistence of HUD Bounds
    # -------------------------------------------------------------
    def test_config_hud_scroll_and_dimension_persistence(self):
        import tempfile
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.close()
        p = Path(tmp.name)

        try:
            cfg = AppConfig(
                hud_width=420,
                hud_height=340,
                hud_max_width=540,
                hud_max_height=480,
                hud_scroll_speed=3,
                show_hud_on_solve=True
            )
            save_config(cfg, custom_path=p)
            loaded = load_config(custom_path=p)

            self.assertEqual(loaded.hud_width, 420)
            self.assertEqual(loaded.hud_height, 340)
            self.assertEqual(loaded.hud_max_width, 540)
            self.assertEqual(loaded.hud_max_height, 480)
            self.assertEqual(loaded.hud_scroll_speed, 3)
            self.assertTrue(loaded.show_hud_on_solve)
        finally:
            if p.exists():
                p.unlink()


if __name__ == "__main__":
    unittest.main()
