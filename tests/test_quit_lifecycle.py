import unittest
import os
import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from ghostline.config import AppConfig


class TestQuitLifecycle(unittest.TestCase):
    def test_shutdown_cleans_up_resources(self):
        """Verify shutdown releases hotkeys, restores lock keys, and closes windows."""
        from ghostline.app import GhostlineApp

        with patch.object(GhostlineApp, "__init__", lambda s: None):
            app = GhostlineApp()
            app.is_running = True
            app.is_solving = False
            app.config = AppConfig()
            app.hotkey_hwnd = 9999
            app.hotkey_thread_id = 8888
            app.hotkey_thread = None
            app.registered_hotkey_ids = [100, 101, 102]
            app.qapp = MagicMock()
            app.main_window = MagicMock()
            app.hud = MagicMock()
            app.hud.lighting_mgr = MagicMock()
            app.audio_panel = MagicMock()
            app.history_panel = MagicMock()
            app.tray = MagicMock()
            app.audio_capture = MagicMock()
            app.transcriber = MagicMock()
            app.hover_detector = MagicMock()
            app.caps_indicator = MagicMock()

            with patch("ghostline.app.user32.UnregisterHotKey") as mock_unreg, \
                 patch("threading.Thread") as mock_thread, \
                 patch("ghostline.app.win32gui.PostMessage") as mock_post, \
                 patch("sys.exit") as mock_exit:

                app.shutdown()

                self.assertFalse(app.is_running)
                # Lighting and lock keys restored
                app.hud.lighting_mgr.backend.restore.assert_called_once()
                app.caps_indicator.restore_safety_state.assert_called_once()
                # UnregisterHotKey called for each registered id
                self.assertEqual(mock_unreg.call_count, 3)
                # Audio and background components stopped
                app.audio_capture.stop.assert_called_once()
                app.transcriber.stop.assert_called_once()
                app.hover_detector.stop.assert_called_once()
                # Windows destroyed
                app.main_window.destroy.assert_called_once()
                app.hud.destroy.assert_called_once()
                app.audio_panel.destroy.assert_called_once()
                app.history_panel.close.assert_called_once()
                app.tray.stop.assert_called_once()
                # Watchdog timer was launched
                mock_thread.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_shutdown_idempotent(self):
        """Verify multiple calls to shutdown do not fail or duplicate cleanup."""
        from ghostline.app import GhostlineApp

        with patch.object(GhostlineApp, "__init__", lambda s: None):
            app = GhostlineApp()
            app._is_shutting_down = True  # already shut down
            app.caps_indicator = MagicMock()
            with patch("sys.exit") as mock_exit:
                app.shutdown()
                app.caps_indicator.restore_safety_state.assert_not_called()
                mock_exit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
