"""
Unit and integration tests for Ghostline Live Audio UI & HUD integration.
Tests LiveAudioPanel widgets, thread-safe callbacks, capture exclusion (WDA_EXCLUDEFROMCAPTURE),
HUD overlay audio status updates, and app lifecycle hooks.
"""

import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch

from ghostline.audio.transcription import TranscriptSegment
from ghostline.ui.audio_panel import LiveAudioPanel
from ghostline.ui.hud_overlay import GhostlineHudOverlay, GhostlineHudOverlay
from ghostline.core.capture_exclusion import get_capture_exclusion_status, WDA_EXCLUDEFROMCAPTURE


class TestAudioPanelUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.start_called = False
        self.stop_called = False
        self.pause_called = False
        self.custom_query = None

        def _on_start():
            self.start_called = True

        def _on_stop():
            self.stop_called = True

        def _on_pause():
            self.pause_called = True
            return True

        def _on_ask(q):
            self.custom_query = q

        self.panel = LiveAudioPanel(
            on_start_capture=_on_start,
            on_stop_capture=_on_stop,
            on_toggle_pause=_on_pause,
            on_ask_custom=_on_ask,
            width=400,
            height=450,
            exclude_from_capture=True
        )
        self.panel.launch(parent=self.root, start_visible=False)
        self.root.update_idletasks()

    def tearDown(self):
        self.panel.destroy()

    def test_initial_state_and_widgets(self):
        self.assertFalse(self.panel.is_capturing)
        self.assertFalse(self.panel.is_paused)
        self.assertIsNotNone(self.panel.btn_capture)
        self.assertIsNotNone(self.panel.txt_transcript)
        self.assertIsNotNone(self.panel.txt_ai_answer)
        self.assertIsNotNone(self.panel.entry_question)

    def test_capture_state_ui_update(self):
        self.panel.set_capture_state(True)
        self.root.update_idletasks()
        self.assertTrue(self.panel.is_capturing)
        self.assertEqual(self.panel.btn_capture.cget("text"), "⏹ Stop")
        self.assertIn("REC", self.panel.lbl_rec_indicator.cget("text"))

        self.panel.set_capture_state(False)
        self.root.update_idletasks()
        self.assertFalse(self.panel.is_capturing)
        self.assertEqual(self.panel.btn_capture.cget("text"), "▶ Start")

    def test_pause_state_ui_update(self):
        self.panel.set_pause_state(True)
        self.root.update_idletasks()
        self.assertTrue(self.panel.is_paused)
        self.assertEqual(self.panel.btn_pause.cget("text"), "▶ Resume")

        self.panel.set_pause_state(False)
        self.root.update_idletasks()
        self.assertFalse(self.panel.is_paused)
        self.assertEqual(self.panel.btn_pause.cget("text"), "⏸ Pause")

    def test_append_final_segment(self):
        seg = TranscriptSegment(
            id=1, timestamp=100.0, time_str="12:00:00",
            source="call", speaker_label="[Call]",
            text="Can we discuss the database schema?", is_final=True
        )
        self.panel.append_final_segment(seg)
        self.root.update_idletasks()

        content = self.panel.txt_transcript.get("1.0", tk.END)
        self.assertIn("[12:00:00]", content)
        self.assertIn("[Call]", content)
        self.assertIn("Can we discuss the database schema?", content)

    def test_update_partial_preview(self):
        self.panel.update_partial("Testing live partial speech", source="mic")
        self.root.update_idletasks()

        content = self.panel.txt_transcript.get("1.0", tk.END)
        self.assertIn("Testing live partial speech", content)
        self.assertIn("[You]", content)

    def test_set_ai_thinking_and_answer(self):
        self.panel.set_ai_thinking("What is two-phase locking?")
        self.root.update_idletasks()
        status_text = self.panel.lbl_ai_status.cget("text")
        self.assertIn("THINKING", status_text)

        self.panel.set_ai_answer(
            question="What is two-phase locking?",
            answer_text="Two-phase locking (2PL) is a concurrency control method guaranteeing serializability.",
            code_snippet="def acquire_locks(): pass"
        )
        self.root.update_idletasks()
        ai_content = self.panel.txt_ai_answer.get("1.0", tk.END)
        self.assertIn("Two-phase locking", ai_content)
        self.assertIn("def acquire_locks()", ai_content)

    def test_get_window_rect(self):
        self.panel.show()
        self.root.update_idletasks()
        rect = self.panel.get_window_rect()
        self.assertIsNotNone(rect)
        self.assertEqual(len(rect), 4)
        left, top, right, bottom = rect
        self.assertGreater(right, left)
        self.assertGreater(bottom, top)

    def test_capture_exclusion_affinity(self):
        # Verify that WDA_EXCLUDEFROMCAPTURE was applied to the panel HWND
        if self.panel.hwnd:
            val, desc = get_capture_exclusion_status(self.panel.hwnd)
            self.assertEqual(val, WDA_EXCLUDEFROMCAPTURE)

    def test_paned_container_and_dedicated_ai_scrollbar(self):
        # Verify vertical split and dedicated AI response scrollbar
        self.assertTrue(hasattr(self.panel, "paned_container"))
        self.assertTrue(hasattr(self.panel, "ai_scrollbar"))
        self.assertTrue(hasattr(self.panel, "grip_resize"))
        self.assertEqual(self.panel.paned_container.winfo_manager(), "pack")
        self.assertEqual(self.panel.ai_scrollbar.winfo_manager(), "pack")
        self.assertEqual(self.panel.footer.winfo_manager(), "pack")

    def test_long_transcript_and_long_ai_answer_non_clipping(self):
        # Add 30 transcript segments
        for i in range(30):
            seg = TranscriptSegment(
                id=i, timestamp=100.0 + i, time_str=f"12:{i:02d}:00",
                source="call" if i % 2 == 0 else "mic",
                speaker_label="[Call]" if i % 2 == 0 else "[You]",
                text=f"Transcript utterance #{i} with long descriptive prose testing scroll regions.",
                is_final=True
            )
            self.panel.append_final_segment(seg)

        # Set long answer
        long_ans = "Line 1: Beginning of detailed architectural answer\n" + ("Line: Intermediate discussion point\n" * 30) + "Final Line: Conclusion."
        code_block = "def test_func():\n    return 'success'\n"
        self.panel.set_ai_answer("Can you explain the entire architecture?", long_ans, code_block)
        self.root.update_idletasks()

        ai_content = self.panel.txt_ai_answer.get("1.0", tk.END)
        self.assertIn("Beginning of detailed architectural answer", ai_content)
        self.assertIn("def test_func()", ai_content)
        self.assertIn("Conclusion.", ai_content)
        self.assertEqual(self.panel.footer.winfo_manager(), "pack")

    def test_resize_constraints(self):
        # Test simulated resize event
        mock_event = MagicMock()
        mock_event.x_root = 1000
        mock_event.y_root = 1000
        self.panel._start_resize(mock_event)

        # Move to smaller than min bounds
        mock_event.x_root = 0
        mock_event.y_root = 0
        self.panel._on_resize(mock_event)
        self.assertGreaterEqual(self.panel.width, self.panel.min_width)
        self.assertGreaterEqual(self.panel.height, self.panel.min_height)

    def test_minimize_and_restore_preserves_paned_layout(self):
        self.panel.toggle_minimize()
        self.assertTrue(self.panel.is_minimized)
        self.panel.toggle_minimize()
        self.assertFalse(self.panel.is_minimized)
        self.assertEqual(self.panel.paned_container.winfo_manager(), "pack")
        self.assertEqual(self.panel.footer.winfo_manager(), "pack")


class TestAudioDiagnosticsRegression(unittest.TestCase):
    """Verifies that diagnostic tests in GhostlineApp do not suffer from missing numpy or undefined symbols."""

    def test_numpy_imported_in_app(self):
        import ghostline.app as app_mod
        self.assertTrue(hasattr(app_mod, "np"))
        self.assertEqual(app_mod.np.__name__, "numpy")

    def test_audio_modules_import_numpy(self):
        import ghostline.audio.capture as cap_mod
        import ghostline.audio.transcription as trans_mod
        self.assertTrue(hasattr(cap_mod, "np"))
        self.assertTrue(hasattr(trans_mod, "np"))

    def test_transcription_engine_test_defined(self):
        from ghostline.app import GhostlineApp
        from ghostline.config import AppConfig
        app = object.__new__(GhostlineApp)
        app.config = AppConfig()
        app.transcriber = None
        # Should gracefully return dict without NameError: name 'np' is not defined
        res = app.test_transcription_engine()
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)
        # Verify error is not 'name np is not defined'
        msg = res.get("message", "")
        self.assertNotIn("name 'np' is not defined", msg)
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.audio_toggled = False

        def _on_audio_toggle():
            self.audio_toggled = True

        self.hud = GhostlineHudOverlay(
            on_toggle_audio=_on_audio_toggle,
            width=380,
            height=300
        )
        self.hud.launch(parent=self.root, start_visible=False)
        self.root.update_idletasks()

    def tearDown(self):
        self.hud.destroy()

    def test_hud_audio_status_updates(self):
        self.assertIsNotNone(self.hud.btn_audio)
        self.assertEqual(self.hud.btn_audio.cget("text"), "🎙️")

        # When capturing
        self.hud.update_audio_status(is_capturing=True, is_paused=False)
        self.root.update_idletasks()
        self.assertIn("🔴", self.hud.btn_audio.cget("text"))

        # When paused
        self.hud.update_audio_status(is_capturing=True, is_paused=True)
        self.root.update_idletasks()
        self.assertIn("⏸️", self.hud.btn_audio.cget("text"))

        # When stopped
        self.hud.update_audio_status(is_capturing=False, is_paused=False)
        self.root.update_idletasks()
        self.assertEqual(self.hud.btn_audio.cget("text"), "🎙️")

    def test_hud_audio_button_click(self):
        self.hud._on_toggle_audio()
        self.assertTrue(self.audio_toggled)


if __name__ == "__main__":
    unittest.main()
