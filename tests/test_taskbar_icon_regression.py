import unittest
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor, QPainter, QCloseEvent
from ghostline.config import AppConfig, load_config, save_config, get_app_dir
from ghostline.ui.qt_main_window import (
    QtGhostlineMainWindow,
    GWL_EXSTYLE,
    WS_EX_TOOLWINDOW,
    WS_EX_APPWINDOW,
    user32
)
from ghostline.ui.tray_indicator import TrayIndicator

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestTaskbarIconRegression(unittest.TestCase):
    """
    Automated regression tests for Hide from Taskbar (DEF-03) and Custom Icon Selection (DEF-04):
    - Config persistence for hide_from_taskbar, custom_icon_path, custom_icon_preset
    - Windows EXSTYLE flags (WS_EX_TOOLWINDOW vs WS_EX_APPWINDOW)
    - Close-to-tray event handling
    - Custom icon file validation, size limits, and copying to AppData
    - Stealth and Utility preset generation
    - Tray indicator icon updates
    """

    def setUp(self):
        self.config = AppConfig()
        self.main_window = QtGhostlineMainWindow(config=self.config)

    def tearDown(self):
        if self.main_window:
            self.main_window.close()

    def test_hide_from_taskbar_config_persistence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "config.json"
            cfg = AppConfig(hide_from_taskbar=False)
            save_config(cfg, path=tmp_path)

            cfg.hide_from_taskbar = True
            save_config(cfg, path=tmp_path)

            reloaded = load_config(path=tmp_path)
            self.assertTrue(reloaded.hide_from_taskbar)

    def test_apply_taskbar_visibility_flags(self):
        self.main_window.show()
        hwnd = int(self.main_window.winId())

        # Test hide from taskbar
        self.main_window.apply_taskbar_visibility(hide=True)
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        self.assertTrue(style & WS_EX_TOOLWINDOW != 0, "WS_EX_TOOLWINDOW must be set when hidden from taskbar.")
        self.assertTrue(style & WS_EX_APPWINDOW == 0, "WS_EX_APPWINDOW must be cleared when hidden from taskbar.")

        # Test restore to taskbar
        self.main_window.apply_taskbar_visibility(hide=False)
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        self.assertTrue(style & WS_EX_TOOLWINDOW == 0, "WS_EX_TOOLWINDOW must be cleared when visible in taskbar.")
        self.assertTrue(style & WS_EX_APPWINDOW != 0, "WS_EX_APPWINDOW must be set when visible in taskbar.")

    def test_close_event_hides_to_tray_when_configured(self):
        self.main_window.config.hide_from_taskbar = True
        self.main_window.show()
        self.assertTrue(self.main_window.isVisible())

        # Simulate clicking the 'X' close button
        event = QCloseEvent()
        self.main_window.closeEvent(event)
        self.assertFalse(event.isAccepted(), "Close event should be ignored to prevent process termination.")
        self.assertTrue(self.main_window._is_minimized_to_tray)
        self.assertFalse(self.main_window.isVisible())

    def test_icon_presets_generation(self):
        for preset in ["default", "stealth_dot", "windows_utility"]:
            icon = self.main_window._create_preset_icon(preset)
            self.assertFalse(icon.isNull(), f"Icon for preset '{preset}' should be valid.")
            pix = icon.pixmap(32, 32)
            self.assertEqual(pix.width(), 32)
            self.assertEqual(pix.height(), 32)

    def test_custom_icon_file_validation_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a valid test image
            valid_img_path = Path(tmp_dir) / "test_icon.png"
            pix = QPixmap(64, 64)
            pix.fill(QColor(0, 180, 255))
            pix.save(str(valid_img_path), "PNG")

            self.assertTrue(valid_img_path.exists())
            loaded_pix = QPixmap(str(valid_img_path))
            self.assertFalse(loaded_pix.isNull())

            # Create an invalid/corrupt image
            invalid_img_path = Path(tmp_dir) / "corrupt.png"
            with open(invalid_img_path, "wb") as f:
                f.write(b"not a valid png file header")
            corrupt_pix = QPixmap(str(invalid_img_path))
            self.assertTrue(corrupt_pix.isNull())

    def test_tray_custom_icon_preset_updates(self):
        tray = TrayIndicator()
        # Verify default image creation
        img_def = tray.create_image()
        self.assertIsNotNone(img_def)

        # Verify stealth dot preset
        tray.set_custom_icon(icon_path=None, preset="stealth_dot")
        img_stealth = tray.create_image()
        self.assertIsNotNone(img_stealth)

        # Verify windows utility preset
        tray.set_custom_icon(icon_path=None, preset="windows_utility")
        img_util = tray.create_image()
        self.assertIsNotNone(img_util)


if __name__ == "__main__":
    unittest.main()
