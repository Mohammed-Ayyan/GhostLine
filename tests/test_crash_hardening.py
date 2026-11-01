import sys
import unittest
import threading
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt

from ghostline.ui.hud_manager import HudManager, HudMode
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.app import install_crash_handlers, setup_file_logging
import logging

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

class TestCrashHardening(unittest.TestCase):
    def test_hud_manager_set_mode(self):
        hm = HudManager()
        self.assertTrue(hasattr(hm, "set_mode"), "HudManager must provide set_mode()")
        hm.set_mode(HudMode.SCREEN)
        self.assertEqual(hm.active_mode, HudMode.SCREEN)
        hm.set_mode(HudMode.HIDDEN)
        self.assertEqual(hm.active_mode, HudMode.HIDDEN)

    def test_qt_hud_overlay_hide_and_callback(self):
        hud = QtGhostlineHudOverlay()
        called = []
        def on_close():
            called.append("closed")
            raise ValueError("simulated callback error")
        hud.on_close = on_close

        # hide_overlay should catch ValueError and log warning without NameError or crash
        hud.hide_overlay()
        self.assertEqual(called, ["closed"])
        self.assertFalse(hud._is_visible)
        hud.close()

    def test_crash_handlers_installation(self):
        install_crash_handlers()
        self.assertIsNotNone(sys.excepthook)
        if hasattr(threading, "excepthook"):
            self.assertIsNotNone(threading.excepthook)

if __name__ == "__main__":
    unittest.main()

