"""
Test sidebar status badge logic.
Verifies that the sidebar status badge dynamically reflects:
- "Needs API key" when a cloud provider has no API key stored.
- "Can't reach <Provider>" when the endpoint is unreachable.
- "<Provider> · Cloud · Ready" when an API key is present.
- "Ollama · Local · Ready" when Ollama is configured and reachable.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtWidgets import QApplication
from ghostline.config import AppConfig


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_sidebar_badge_cloud_missing_key(qapp):
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    cfg = AppConfig()
    cfg.ai_provider = "groq"

    with patch("ghostline.ui.qt_main_window.has_api_key", return_value=False):
        window = QtGhostlineMainWindow(cfg)
        window.update_sidebar_status_badge()
        assert window.status_text.text() == "Groq · Needs API key"


def test_sidebar_badge_cloud_has_key(qapp):
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    cfg = AppConfig()
    cfg.ai_provider = "groq"

    with patch("ghostline.ui.qt_main_window.has_api_key", return_value=True):
        window = QtGhostlineMainWindow(cfg)
        window.update_sidebar_status_badge()
        assert window.status_text.text() == "Groq · Cloud · Ready"


def test_sidebar_badge_gemini_missing_key(qapp):
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    cfg = AppConfig()
    cfg.ai_provider = "gemini"

    with patch("ghostline.ui.qt_main_window.has_api_key", return_value=False):
        window = QtGhostlineMainWindow(cfg)
        window.update_sidebar_status_badge()
        assert window.status_text.text() == "Gemini · Needs API key"


def test_sidebar_badge_ollama_ready(qapp):
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    cfg = AppConfig()
    cfg.ai_provider = "ollama"

    window = QtGhostlineMainWindow(cfg)
    window.update_sidebar_status_badge(check_reachable=False)
    assert window.status_text.text() == "Ollama · Local · Ready"


def test_sidebar_badge_ollama_unreachable(qapp):
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    cfg = AppConfig()
    cfg.ai_provider = "ollama"

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        window = QtGhostlineMainWindow(cfg)
        window.update_sidebar_status_badge(check_reachable=True)
        assert window.status_text.text() == "Can't reach Ollama"

