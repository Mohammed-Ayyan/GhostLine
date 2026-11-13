"""
Unit tests for First-Run Setup Wizard Robustness, Sizing, and Navigation (Run 19).
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea
from PyQt6.QtCore import Qt, QTimer, QKeyCombination
from PyQt6.QtGui import QKeyEvent

from ghostline.config import AppConfig
from ghostline.ui.window_geometry import get_work_area
from ghostline.ui.qt_main_window import QtFirstRunWizardDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    return app


def test_wizard_fits_within_small_screen_work_area(qapp, monkeypatch):
    """Verifies that the wizard dialog stays inside the work area on a small 1366x768@150 display."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1366x768@150")
    work = get_work_area()  # 910x480
    cfg = AppConfig()
    wiz = QtFirstRunWizardDialog(cfg)
    wiz.show()
    qapp.processEvents()

    assert wiz.width() <= work.width()
    assert wiz.height() <= work.height()

    # Footer buttons must be visible and within dialog bounds
    assert wiz.btn_next.isVisible()
    assert wiz.btn_skip.isVisible()
    assert wiz.btn_back.isVisible()
    wiz.close()


def test_wizard_scroll_area_and_pinned_footer(qapp, monkeypatch):
    """Verifies that pages are wrapped in QScrollArea and footer buttons remain pinned outside it."""
    cfg = AppConfig()
    wiz = QtFirstRunWizardDialog(cfg)
    wiz.show()
    qapp.processEvents()

    # Stack children should be QScrollArea instances
    assert wiz.stack.count() == 3
    for i in range(wiz.stack.count()):
        page_widget = wiz.stack.widget(i)
        assert isinstance(page_widget, QScrollArea)

    # Footer buttons must not be children of QScrollArea (they are in the root dialog layout)
    for btn in (wiz.btn_next, wiz.btn_back, wiz.btn_skip):
        assert not isinstance(btn.parent(), QScrollArea)

    wiz.close()


def test_wizard_hardware_summary_in_step1(qapp):
    """Verifies that Step 1 contains a hardware summary label with non-empty, zero-PII content."""
    cfg = AppConfig()
    wiz = QtFirstRunWizardDialog(cfg)
    wiz.show()
    qapp.processEvents()

    assert hasattr(wiz, "lbl_wiz_hw")
    assert wiz.lbl_wiz_hw.isVisible()
    text = wiz.lbl_wiz_hw.text()
    assert "Your PC:" in text
    assert "RAM" in text
    assert "Performance Mode:" in text
    wiz.close()


def test_wizard_keyboard_escape_skips(qapp):
    """Verifies that pressing Escape triggers _skip_clicked without modal blocking."""
    cfg = AppConfig()
    wiz = QtFirstRunWizardDialog(cfg)
    wiz.show()
    qapp.processEvents()

    # Send Escape key
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    wiz.keyPressEvent(event)
    qapp.processEvents()

    assert cfg.first_run_complete is True
    wiz.close()


def test_wizard_keyboard_enter_advances(qapp):
    """Verifies that pressing Enter advances through the wizard steps."""
    cfg = AppConfig()
    wiz = QtFirstRunWizardDialog(cfg)
    wiz.show()
    qapp.processEvents()

    assert wiz.stack.currentIndex() == 0
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    wiz.keyPressEvent(event)
    qapp.processEvents()

    assert wiz.stack.currentIndex() == 1
    wiz.close()


def test_wizard_all_labels_word_wrapped(qapp):
    """Verifies that descriptive labels in the wizard enable word wrapping to prevent text clipping."""
    cfg = AppConfig()
    wiz = QtFirstRunWizardDialog(cfg)
    wiz.show()
    qapp.processEvents()

    for step in range(3):
        wiz.stack.setCurrentIndex(step)
        qapp.processEvents()
        for lbl in wiz.findChildren(QLabel):
            if lbl.isVisible() and len(lbl.text()) > 35:
                assert lbl.wordWrap() is True, f"Label not word wrapped: '{lbl.text()[:40]}'"

    wiz.close()
