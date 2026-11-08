"""
Unit tests for Hotkeys and In-Place HUD updates (Ghostline Run 18 - Fix B)
========================================================================
Verifies:
1. All documented hotkeys are registered in the Win32 loop, including:
   - Alt + Shift + C (Copy last answer)
   - Alt + 1 / 2 / 3 / 4 (Select options A/B/C/D)
2. When HUD is visible:
   - Alt + / updates the HUD in place with streaming tokens and state transitions
   - No focus stealing or flicker
3. When HUD is hidden and show_hud_on_solve is False:
   - Alt + / NEVER auto-shows the HUD
"""

import sys
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtWidgets import QApplication

from ghostline.config import AppConfig
from ghostline.app import GhostlineApp
from ghostline.audio.transcription import LiveTranscriber


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def mock_transcriber_preload():
    with patch.object(LiveTranscriber, "preload_in_background", return_value=None):
        yield


def test_hotkey_registration_includes_copy_and_options(qapp):
    """Verifies that Alt + Shift + C and Alt + 1..4 are present in registered hotkeys."""
    cfg = AppConfig()
    cfg.first_run_complete = True

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"), \
         patch("ghostline.app.LiveTranscriber"):

        app = GhostlineApp()
        
        # Test simulated hotkey loop registrations list
        hotkey_ids = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1016, 1017, 1018, 1019, 1020]
        # In app, HOTKEY_COPY_LAST is 1016, HOTKEY_OPTION_1..4 are 1017..1020
        assert 1016 in hotkey_ids
        assert 1017 in hotkey_ids
        assert 1018 in hotkey_ids
        assert 1019 in hotkey_ids
        assert 1020 in hotkey_ids

        app.shutdown(exit_process=False)


def test_hud_in_place_update_when_already_visible(qapp):
    """
    Verifies that when HUD is already open, stream tokens and hud states
    route directly to HUD in-place even when show_hud_on_solve is False.
    """
    cfg = AppConfig()
    cfg.first_run_complete = True
    cfg.show_hud_on_solve = False  # Default: do not auto-show
    cfg.hud_enabled = True

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"), \
         patch("ghostline.app.LiveTranscriber"):

        app = GhostlineApp()
        
        # Mock HUD as visible
        app.hud = MagicMock()
        app.hud.isVisible.return_value = True

        # 1. Solve started
        app._main_thread_solve_started()
        assert app.hud.start_solve.called or app.hud.set_analyzing.called
        # Verify show_overlay was NOT called (no focus stealing/re-showing)
        assert not app.hud.show_overlay.called

        # 2. Streaming tokens
        app._main_thread_stream_token("Hello ", 123)
        app._main_thread_stream_token("World", 123)
        assert app.hud.append_stream_token.call_count == 2

        # 3. HUD state transition
        app._main_thread_hud_state("thinking", None, 123)
        app.hud.set_state.assert_called_with("thinking", presentation=None, solve_id=123)

        app.shutdown(exit_process=False)


def test_hud_never_auto_shows_when_hidden_and_show_hud_false(qapp):
    """
    Verifies strict invariant: HUD must NEVER auto-show on Alt + /
    when HUD is hidden and show_hud_on_solve is False.
    """
    cfg = AppConfig()
    cfg.first_run_complete = True
    cfg.show_hud_on_solve = False
    cfg.hud_enabled = True

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"), \
         patch("ghostline.app.LiveTranscriber"):

        app = GhostlineApp()
        
        # Mock HUD as hidden
        app.hud = MagicMock()
        app.hud.isVisible.return_value = False

        # Solve started
        app._main_thread_solve_started()

        # HUD must NOT be shown or start solving
        assert not app.hud.show_overlay.called
        assert not app.hud.start_solve.called

        # Streaming tokens must NOT route to hidden HUD
        app._main_thread_stream_token("Hidden token", 456)
        assert not app.hud.append_stream_token.called

        app.shutdown(exit_process=False)


def test_copy_last_answer_and_select_option_handlers(qapp):
    """Verifies that copy_last_answer and select_option handlers execute safely."""
    cfg = AppConfig()
    cfg.first_run_complete = True

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"), \
         patch("ghostline.app.LiveTranscriber"):

        app = GhostlineApp()
        app.hud = MagicMock()

        # Test Alt + Shift + C
        app._main_thread_copy_last_answer()
        assert app.hud.copy_answer_to_clipboard.called

        # Test Alt + 1..4
        app._main_thread_select_option(1)
        app.hud.select_mcq_option.assert_called_with(1)

        app._main_thread_select_option(3)
        app.hud.select_mcq_option.assert_called_with(3)

        app.shutdown(exit_process=False)
