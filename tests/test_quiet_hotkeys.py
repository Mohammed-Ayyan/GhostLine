import unittest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from ghostline.config import AppConfig
from ghostline.ui.quiet_output import dispatch_quiet_result, dispatch_quiet_error
from ghostline.ui.presentation import PresentedAnswer


class TestQuietHotkeys(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            show_hud_on_solve=False,
            hotkey_hud_toggle="alt+t",
            hotkey_quit="ctrl+alt+q",
            quiet_taskbar_flash=True,
            quiet_taskbar_badge=True,
            quiet_tray_notification=True,
            quiet_hardware_signal=False
        )

    def test_default_config_hides_hud_on_solve(self):
        """Verify show_hud_on_solve is False by default so Alt+/ runs silently."""
        cfg = AppConfig()
        self.assertFalse(cfg.show_hud_on_solve)
        self.assertEqual(cfg.hotkey_hud_toggle.lower(), "alt+t")
        self.assertEqual(cfg.hotkey_quit.lower(), "ctrl+alt+q")

    def test_quiet_output_dispatch_success(self):
        """Verify dispatch_quiet_result triggers quiet channels without throwing."""
        pres = PresentedAnswer(
            headline="Option C is correct",
            direct_answer="Option C",
            explanation="Binary Heap",
            badge="C",
            question_type="multiple_choice",
            is_validated=True
        )
        mock_tray = MagicMock()
        mock_lighting = MagicMock()

        # Test dispatch with all quiet channels enabled
        with patch("ghostline.ui.quiet_output.flash_window") as mock_flash, \
             patch("ghostline.ui.quiet_output.get_taskbar_badge_manager") as mock_get_badge_mgr:
            mock_badge_mgr = MagicMock()
            mock_get_badge_mgr.return_value = mock_badge_mgr
            dispatch_quiet_result(
                config=self.config,
                presentation=pres,
                hwnd=12345,
                tray=mock_tray,
                lighting_mgr=mock_lighting
            )
            mock_flash.assert_called_once_with(12345, count=2)
            mock_badge_mgr.set_badge.assert_called_once()
            mock_tray.show_balloon.assert_called_once()

    def test_quiet_output_dispatch_error(self):
        """Verify dispatch_quiet_error flashes window and updates tray balloon."""
        mock_tray = MagicMock()
        mock_lighting = MagicMock()

        with patch("ghostline.ui.quiet_output.flash_window") as mock_flash, \
             patch("ghostline.ui.quiet_output.get_taskbar_badge_manager") as mock_get_badge_mgr:
            mock_badge_mgr = MagicMock()
            mock_get_badge_mgr.return_value = mock_badge_mgr
            dispatch_quiet_error(
                config=self.config,
                error_message="No API key provided",
                hwnd=12345,
                tray=mock_tray,
                lighting_mgr=mock_lighting
            )
            mock_flash.assert_called_once_with(12345, count=3)
            mock_badge_mgr.set_badge.assert_called_once()
            mock_tray.show_balloon.assert_called_once_with(
                title="Ghostline Error",
                text="No API key provided",
                icon_type="error"
            )

    def test_hud_solve_respects_show_hud_on_solve_flag(self):
        """Verify solving leaves HUD hidden when show_hud_on_solve is False."""
        mock_hud = MagicMock()
        mock_hud.isVisible.return_value = False
        mock_hud_manager = MagicMock()
        mock_hud_manager.is_visible.return_value = False

        from ghostline.app import GhostlineApp
        # Minimal mock app
        with patch.object(GhostlineApp, "__init__", lambda s: None):
            app = GhostlineApp()
            app.config = AppConfig(show_hud_on_solve=False)
            app.hud = mock_hud
            app.hud_manager = mock_hud_manager
            app.main_window = None
            app.tray = None
            app.caps_indicator = None

            # Mock result
            res = MagicMock()
            res.parsed_question = None
            res.answer_result = MagicMock(
                answer_option="B",
                proposed_option="B",
                validation_status="success",
                is_validated=True,
                error=None,
                tray_badge="B"
            )

            with patch("ghostline.ui.quiet_output.dispatch_quiet_result"):
                app._main_thread_solve_completed(res)

            # Assert HUD was not shown
            mock_hud.show_overlay.assert_not_called()
            mock_hud_manager.show_mode.assert_not_called()
            # Assert answer is saved
            self.assertIsNotNone(app.last_answer_presentation)
            self.assertEqual(app.last_answer_presentation.badge, "B")

            # Now test toggle_hud shows the HUD
            app.toggle_hud()
            mock_hud_manager.toggle_mode.assert_called_once()


if __name__ == "__main__":
    unittest.main()
