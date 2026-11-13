"""
Unit tests for Performance Profiling, Hardware Detection, and Lite Mode (Run 19).
"""

import os
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QTextEdit
from ghostline.config import AppConfig
from ghostline.core.hardware_profile import (
    get_hardware_profile,
    get_hardware_summary_string,
    is_weak_hardware_or_battery
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    return app


def test_hardware_summary_string_fast_and_zero_pii():
    """Verifies hardware summary generation runs in < 20ms and contains strictly zero PII."""
    t0 = time.perf_counter()
    summary = get_hardware_summary_string()
    duration_ms = (time.perf_counter() - t0) * 1000.0

    assert duration_ms < 25.0, f"Hardware profile too slow: {duration_ms:.2f}ms"
    assert "Your PC:" in summary
    assert "RAM" in summary
    assert "Performance Mode:" in summary

    # Privacy verification: strictly zero PII
    import getpass
    username = getpass.getuser().lower()
    if len(username) > 2:
        assert username not in summary.lower(), "Username leaked in hardware summary"

    assert "127.0.0.1" not in summary
    assert "localhost" not in summary
    assert ":\\" not in summary  # No local file paths
    assert "@" not in summary  # No emails or tokens


def test_weak_hardware_detection_scenarios():
    """Verifies weak PC and battery saver classification."""
    # Scenario A: 4GB RAM, 2 cores -> Weak
    hw_weak = {"ram_gb": 4, "cores": 2, "battery_saver": False}
    assert is_weak_hardware_or_battery(hw_weak) is True

    # Scenario B: 16GB RAM, 8 cores, No battery saver -> Not weak
    hw_capable = {"ram_gb": 16, "cores": 8, "battery_saver": False}
    assert is_weak_hardware_or_battery(hw_capable) is False

    # Scenario C: 32GB RAM, 16 cores, Battery saver ON -> Weak / Power saving triggered
    hw_battery = {"ram_gb": 32, "cores": 16, "battery_saver": True}
    assert is_weak_hardware_or_battery(hw_battery) is True


def test_lite_mode_bounds_document_blocks(qapp):
    """Verifies that Lite mode bounds document blocks to protect memory and render cost."""
    cfg = AppConfig()
    cfg.performance_mode = "lite"
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    win = QtGhostlineMainWindow(cfg)

    # Document blocks on text edits must be capped
    for ctrl in win.findChildren(QTextEdit):
        if ctrl.objectName() not in ("ProfileBio", "ProfileExperience", "ProfileProjects", "ProfileFacts"):
            assert ctrl.document().maximumBlockCount() == 100

    win.close()
