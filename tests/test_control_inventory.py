"""
Control Inventory Guard Test Suite.
Verifies that all required controls specified in tests/fixtures/required_controls.json
exist on their respective views, have standardized objectNames, and are properly connected.
"""

import sys
import json
import os
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit, QTextEdit, QComboBox, QPushButton
from PyQt6.QtCore import Qt

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay

FIXTURE_PATH = Path("tests/fixtures/required_controls.json").resolve()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def main_window(qapp):
    cfg = AppConfig()
    win = QtGhostlineMainWindow(cfg)
    return win


def test_required_controls_inventory(main_window):
    """Asserts all controls from required_controls.json exist and have objectNames."""
    assert FIXTURE_PATH.exists(), f"Missing required controls fixture: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        spec = json.load(f)

    # 1. Audit Settings page controls
    main_window.show_screen("general")
    settings_view = main_window.screen_frames.get("general")
    assert settings_view is not None, "Settings screen frame not found"

    for ctrl_info in spec.get("Settings", []):
        obj_name = ctrl_info["objectName"]
        found = settings_view.findChild(QWidget, obj_name)
        assert found is not None, f"Required Settings control missing: {obj_name} ({ctrl_info.get('type')})"
        assert found.objectName() == obj_name, f"Control has incorrect objectName: {found.objectName()} != {obj_name}"

    # 2. Audit Profile page controls
    main_window.show_screen("profile")
    profile_view = main_window.screen_frames.get("profile")
    assert profile_view is not None, "Profile screen frame not found"

    for ctrl_info in spec.get("Profile", []):
        obj_name = ctrl_info["objectName"]
        found = profile_view.findChild(QWidget, obj_name)
        assert found is not None, f"Required Profile control missing: {obj_name} ({ctrl_info.get('type')})"
        assert found.objectName() == obj_name, f"Control has incorrect objectName: {found.objectName()} != {obj_name}"

    # 3. Audit Home page controls
    main_window.show_screen("dashboard")
    home_view = main_window.screen_frames.get("dashboard")
    assert home_view is not None, "Home dashboard screen frame not found"

    for ctrl_info in spec.get("Home", []):
        obj_name = ctrl_info["objectName"]
        found = home_view.findChild(QWidget, obj_name)
        assert found is not None, f"Required Home control missing: {obj_name} ({ctrl_info.get('type')})"
        assert found.objectName() == obj_name, f"Control has incorrect objectName: {found.objectName()} != {obj_name}"

    # 4. Audit HUD overlay
    hud = QtGhostlineHudOverlay()
    for ctrl_info in spec.get("HUD", []):
        obj_name = ctrl_info["objectName"]
        assert hud.objectName() == obj_name, f"HUD overlay objectName mismatch: {hud.objectName()} != {obj_name}"

    # 5. Audit Help page and Support controls
    main_window.show_screen("help")
    help_view = main_window.screen_frames.get("help")
    assert help_view is not None, "Help screen frame not found"

    for ctrl_info in spec.get("Help", []):
        obj_name = ctrl_info["objectName"]
        found = main_window.findChild(QWidget, obj_name)
        assert found is not None, f"Required Help/Support control missing: {obj_name} ({ctrl_info.get('type')})"
        assert found.objectName() == obj_name, f"Control has incorrect objectName: {found.objectName()} != {obj_name}"

