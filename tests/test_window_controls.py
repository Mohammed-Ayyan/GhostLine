import sys
import unittest
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

GWL_STYLE = -16
GWL_EXSTYLE = -20

WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU     = 0x00080000
WS_THICKFRAME  = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW  = 0x00040000

user32 = ctypes.windll.user32

class TestWindowControls(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(
            hide_from_taskbar=True, # Even when configured True, normal windows must keep standard buttons!
            minimize_to_tray=True,
            main_window_width=1000,
            main_window_height=700
        )
        self.main_win = QtGhostlineMainWindow(config=self.config)

    def tearDown(self):
        self.main_win.close()

    def test_main_window_flags_and_styles(self):
        flags = self.main_win.windowFlags()
        self.assertTrue(flags & Qt.WindowType.Window)
        self.assertTrue(flags & Qt.WindowType.WindowMinMaxButtonsHint)
        self.assertTrue(flags & Qt.WindowType.WindowCloseButtonHint)

        # Show window to ensure native window handle exists
        self.main_win.show()
        hwnd = int(self.main_win.winId())
        self.assertGreater(hwnd, 0)

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        self.assertTrue(bool(style & WS_MINIMIZEBOX), "Main window must have WS_MINIMIZEBOX")
        self.assertTrue(bool(style & WS_MAXIMIZEBOX), "Main window must have WS_MAXIMIZEBOX")
        self.assertTrue(bool(style & WS_SYSMENU), "Main window must have WS_SYSMENU")
        self.assertTrue(bool(style & WS_THICKFRAME), "Main window must have WS_THICKFRAME (resizable)")

        # Verify apply_taskbar_visibility does NOT set WS_EX_TOOLWINDOW
        self.main_win.apply_taskbar_visibility(True)
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        self.assertFalse(bool(ex_style & WS_EX_TOOLWINDOW), "Normal window must never have WS_EX_TOOLWINDOW")
        self.assertTrue(bool(ex_style & WS_EX_APPWINDOW), "Normal window must have WS_EX_APPWINDOW")

    def test_main_window_geometry_persistence(self):
        self.assertEqual(self.main_win.width(), 1000)
        self.assertEqual(self.main_win.height(), 700)

    def test_hud_custom_controls(self):
        quit_called = []
        hud = QtGhostlineHudOverlay(on_exit=lambda: quit_called.append(True))
        self.assertTrue(hasattr(hud, "btn_minimize_hud"), "HUD must have Minimize button")
        self.assertTrue(hasattr(hud, "btn_expand_toggle"), "HUD must have Maximize/Expand button")
        self.assertTrue(hasattr(hud, "btn_close_hud"), "HUD must have Close button")
        self.assertTrue(hasattr(hud, "btn_quit_hud"), "HUD must have Quit button")

        # Test quit trigger
        hud.btn_quit_hud.click()
        self.assertEqual(quit_called, [True])
        hud.close()

if __name__ == "__main__":
    unittest.main()

