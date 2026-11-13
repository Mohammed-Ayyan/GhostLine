"""
Unit tests for Window State Management, Screen Boundary Validation, and Geometry Persistence (Run 19).
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QRect, QTimer

from ghostline.config import AppConfig
from ghostline.ui.window_geometry import (
    get_work_area,
    validate_window_geometry,
    get_default_centered_geometry
)
from ghostline.ui.window_state import WindowStateManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    return app


def test_get_work_area_fake_screen(monkeypatch):
    """Verifies that GHOSTLINE_E2E_FAKE_SCREEN returns accurate logical work area dimensions."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1366x768@150")
    work = get_work_area()
    # 1366 / 1.5 = 910 logical width, (768 - 48) / 1.5 = 480 logical height
    assert work.width() == 910
    assert work.height() == 480

    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1920x1080@100")
    work2 = get_work_area()
    assert work2.width() == 1920
    assert work2.height() == 1032  # 1080 - 48 taskbar


def test_validate_window_geometry_valid(monkeypatch):
    """A valid geometry inside work area must be retained."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1920x1080@100")
    rect = validate_window_geometry(pos_x=100, pos_y=100, width=960, height=680)
    assert rect.x() == 100
    assert rect.y() == 100
    assert rect.width() == 960
    assert rect.height() == 680


def test_validate_window_geometry_offscreen_or_huge(monkeypatch):
    """Offscreen coordinates or geometry larger than work area must reset to 85% centered."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1366x768@150")
    # Work area is 910x480
    rect = validate_window_geometry(pos_x=-9999, pos_y=-9999, width=5000, height=5000)
    assert rect.width() <= 910
    assert rect.height() <= 480
    assert rect.x() >= 0
    assert rect.y() >= 0


def test_window_state_manager_open_maximized(qapp, monkeypatch):
    """Verifies that when open_maximized is True, window shows maximized."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1920x1080@100")
    cfg = AppConfig()
    cfg.open_maximized = True
    win = QMainWindow()

    mgr = WindowStateManager(win, cfg)
    mgr.apply_initial_geometry_and_state(start_minimized=False)

    assert win.isMaximized()
    win.close()


def test_window_state_manager_open_normal(qapp, monkeypatch):
    """Verifies that when open_maximized is False, window shows normal geometry."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1920x1080@100")
    cfg = AppConfig()
    cfg.open_maximized = False
    cfg.main_window_maximized = False
    cfg.main_window_width = 850
    cfg.main_window_height = 600
    win = QMainWindow()

    mgr = WindowStateManager(win, cfg)
    mgr.apply_initial_geometry_and_state(start_minimized=False)

    assert not win.isMaximized()
    assert win.width() == 850
    assert win.height() == 600
    win.close()


def test_window_state_manager_restore_from_tray(qapp, monkeypatch):
    """Verifies restore from tray honors maximized preference."""
    monkeypatch.setenv("GHOSTLINE_E2E_FAKE_SCREEN", "1920x1080@100")
    cfg = AppConfig()
    cfg.open_maximized = True
    win = QMainWindow()

    mgr = WindowStateManager(win, cfg)
    mgr.apply_initial_geometry_and_state(start_minimized=True)
    assert not win.isVisible()

    mgr.restore_from_tray()
    assert win.isVisible()
    assert win.isMaximized()
    win.close()


def test_window_state_manager_debounced_save(qapp, monkeypatch):
    """Verifies that resize/move triggers debounced timer instead of synchronous disk write."""
    cfg = AppConfig()
    win = QMainWindow()
    mgr = WindowStateManager(win, cfg)
    win.show()

    assert not mgr._save_timer.isActive()
    mgr.on_window_resized_or_moved()
    assert mgr._save_timer.isActive()

    # Flush
    with patch("ghostline.ui.window_state.save_config") as mock_save:
        mgr._do_save_config()
        assert mock_save.called

    win.close()
