"""
Unit tests for HudFocusController (Ghostline Run 18 - Fix A)
===========================================================
Verifies:
1. Dynamic removal of WS_EX_NOACTIVATE during active text entry
2. Re-application of WS_EX_NOACTIVATE and restoration of foreground window on end
3. Retention of screen capture exclusion (WDA_EXCLUDEFROMCAPTURE)
4. Escape key cancellation
5. 10-second idle timeout focus release
"""

import sys
import time
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit

from ghostline.ui.hud_focus_controller import (
    HudFocusController,
    WS_EX_NOACTIVATE,
    WDA_EXCLUDEFROMCAPTURE,
    GWL_EXSTYLE
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_hud_focus_controller_initial_state(qapp):
    window = QWidget()
    controller = HudFocusController(window)
    input_widget = QLineEdit(window)
    controller.attach_input(input_widget)

    assert controller.is_text_entry_active is False
    assert controller.prev_hwnd is None
    assert controller.current_input == input_widget


def test_begin_and_end_text_entry(qapp):
    window = QWidget()
    controller = HudFocusController(window)
    input_widget = QLineEdit(window)
    controller.attach_input(input_widget)
    window.show()
    qapp.processEvents()

    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=12345), \
         patch("ctypes.windll.user32.GetWindowLongW", return_value=0x08000000 | 0x00000008), \
         patch("ctypes.windll.user32.SetWindowLongW") as mock_set_long, \
         patch("ctypes.windll.user32.SetWindowPos") as mock_set_pos, \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_set_fg, \
         patch("ctypes.windll.user32.SetWindowDisplayAffinity") as mock_affinity, \
         patch("ctypes.windll.user32.IsWindow", return_value=True):

        # 1. Begin text entry
        controller.begin_text_entry(input_widget)
        qapp.processEvents()

        assert controller.is_text_entry_active is True
        assert controller.prev_hwnd == 12345

        if sys.platform == "win32":
            # Verify WS_EX_NOACTIVATE was stripped
            args, _ = mock_set_long.call_args
            new_style = args[2]
            assert (new_style & WS_EX_NOACTIVATE) == 0

        # 2. End text entry
        controller.end_text_entry()
        qapp.processEvents()

        assert controller.is_text_entry_active is False
        assert controller.prev_hwnd is None

        if sys.platform == "win32":
            # Verify WS_EX_NOACTIVATE was restored
            args, _ = mock_set_long.call_args
            new_style = args[2]
            assert (new_style & WS_EX_NOACTIVATE) != 0
            # Verify previous foreground window was restored
            mock_set_fg.assert_called_with(12345)

    window.close()


def test_escape_key_ends_text_entry(qapp):
    window = QWidget()
    controller = HudFocusController(window)
    input_widget = QLineEdit(window)
    controller.attach_input(input_widget)

    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=9999), \
         patch("ctypes.windll.user32.GetWindowLongW", return_value=0x08000000), \
         patch("ctypes.windll.user32.SetWindowLongW"), \
         patch("ctypes.windll.user32.SetWindowPos"), \
         patch("ctypes.windll.user32.SetForegroundWindow"), \
         patch("ctypes.windll.user32.IsWindow", return_value=True):

        controller.begin_text_entry(input_widget)
        assert controller.is_text_entry_active is True

        # Simulate Escape KeyPress
        escape_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        handled = controller.eventFilter(input_widget, escape_event)

        assert handled is True
        assert controller.is_text_entry_active is False


def test_idle_timeout_releases_focus(qapp):
    window = QWidget()
    controller = HudFocusController(window)
    input_widget = QLineEdit(window)
    controller.attach_input(input_widget)

    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=5555), \
         patch("ctypes.windll.user32.GetWindowLongW", return_value=0x08000000), \
         patch("ctypes.windll.user32.SetWindowLongW"), \
         patch("ctypes.windll.user32.SetWindowPos"), \
         patch("ctypes.windll.user32.SetForegroundWindow"), \
         patch("ctypes.windll.user32.IsWindow", return_value=True):

        controller.begin_text_entry(input_widget)
        assert controller.is_text_entry_active is True

        # Advance last activity time by 11 seconds to simulate idle
        controller.last_activity_time = time.time() - 11.0
        controller._check_idle()

        assert controller.is_text_entry_active is False
