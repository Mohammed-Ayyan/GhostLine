import unittest
import sys
import threading
from pathlib import Path

# Add project root to path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.app import QtEventBridge

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestSecondaryControlsRegression(unittest.TestCase):
    """
    Verification tests for DEF-07: Broken or Disconnected Secondary Controls.
    Verifies that all secondary controls (Mode combo, preview, HUD toolbar,
    Audio panel controls, and thread-safe tray bridge signals) operate correctly.
    """

    def setUp(self):
        self.tmp_config = AppConfig(
            hotkey="Ctrl + Alt + K",
            indicator_mode="caps_lock",
            hide_from_taskbar=False,
            custom_icon_preset="stealth_dot"
        )
        self.settings_saved_called = 0
        self.last_saved_config = None

    def _on_settings_saved(self, cfg):
        self.settings_saved_called += 1
        self.last_saved_config = cfg

    def test_mode_combo_initialization_and_preview(self):
        """Mode combobox must reflect config.indicator_mode on creation and update preview."""
        win = QtGhostlineMainWindow(
            config=self.tmp_config,
            on_settings_saved=self._on_settings_saved
        )
        # indicator_mode was "caps_lock" -> index 2 in ["tray", "hud", "caps_lock", "silent"]
        self.assertEqual(win.combo_mode.currentIndex(), 2)
        self.assertIn("Caps Lock Physical LED Active", win.preview_lbl.text())
        self.assertIn("Ctrl + Alt + K", win.preview_lbl.text())

        # Change to "tray" (index 0)
        win.combo_mode.setCurrentIndex(0)
        self.assertEqual(win.config.indicator_mode, "tray")
        self.assertEqual(self.settings_saved_called, 1)
        self.assertIn("System Tray Icon Active", win.preview_lbl.text())
        win.close()

    def test_bridge_open_settings_and_shutdown_signals(self):
        """Bridge signals must route open_settings and shutdown to slots safely."""
        bridge = QtEventBridge()
        opened_screens = []
        shutdown_called = [False]

        def on_open_settings(screen_id):
            opened_screens.append(screen_id)

        def on_shutdown():
            shutdown_called[0] = True

        bridge.sig_open_settings.connect(on_open_settings)
        bridge.sig_shutdown.connect(on_shutdown)

        # Emit from a background worker thread
        def worker():
            bridge.sig_open_settings.emit("mode")
            bridge.sig_shutdown.emit()

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        app.processEvents()
        self.assertEqual(opened_screens, ["mode"])
        self.assertTrue(shutdown_called[0])

    def test_hud_toolbar_and_utility_buttons(self):
        """HUD toolbar buttons (retry, screenshot, clear, size_mode, copy) must be wired without errors."""
        retry_called = [False]
        screenshot_called = [False]
        close_called = [False]

        hud = QtGhostlineHudOverlay(
            on_retry=lambda: retry_called.__setitem__(0, True),
            on_trigger_screenshot=lambda: screenshot_called.__setitem__(0, True),
            on_close=lambda: close_called.__setitem__(0, True)
        )

        hud.btn_ans.click()
        self.assertTrue(retry_called[0])

        hud.btn_shot.click()
        self.assertTrue(screenshot_called[0])

        # Test toggle size mode
        hud.btn_size_mode.click()
        self.assertTrue(hud.is_expanded)
        self.assertEqual(hud.width(), 760)
        hud.btn_size_mode.click()
        self.assertFalse(hud.is_expanded)
        self.assertEqual(hud.width(), 560)

        # Test clear question
        hud.lbl_q_text.setText("Some temporary question")
        hud._clear_question()
        self.assertEqual(hud.lbl_q_text.text(), "Ready for next question.")

        # Test copy question to clipboard
        hud.lbl_q_text.setText("Target Question For Clipboard")
        hud._copy_question()
        clip_txt = QApplication.clipboard().text()
        self.assertEqual(clip_txt, "Target Question For Clipboard")

        hud.close()

    def test_audio_panel_controls_and_callbacks(self):
        """Audio panel buttons (capture toggle, pause toggle, clear) must trigger callbacks cleanly."""
        start_cap = [False]
        stop_cap = [False]
        toggle_pause = [False]
        clear_trans = [False]

        panel = QtLiveAudioPanel(
            on_start_capture=lambda: start_cap.__setitem__(0, True),
            on_stop_capture=lambda: stop_cap.__setitem__(0, True),
            on_toggle_pause=lambda: toggle_pause.__setitem__(0, True),
            on_clear_transcript=lambda: clear_trans.__setitem__(0, True)
        )

        # Toggle capture click (Start)
        panel.btn_capture.click()
        self.assertTrue(panel.is_recording)
        self.assertTrue(start_cap[0])
        self.assertEqual(panel.btn_capture.text(), "Stop Listening")

        # Toggle capture click (Stop)
        panel.btn_capture.click()
        self.assertFalse(panel.is_recording)
        self.assertTrue(stop_cap[0])
        self.assertEqual(panel.btn_capture.text(), "Start Listening")

        # Toggle pause
        panel.btn_pause.click()
        self.assertTrue(panel.is_paused)
        self.assertTrue(toggle_pause[0])
        self.assertEqual(panel.btn_pause.text(), "Resume")

        # Clear transcript
        panel._clear_transcript_click()
        self.assertTrue(clear_trans[0])

        panel.close()


if __name__ == "__main__":
    unittest.main()
