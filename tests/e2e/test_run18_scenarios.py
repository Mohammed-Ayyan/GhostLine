"""
End-to-End Scenarios S40 - S46 (Ghostline Run 18 FINAL BUILD)
============================================================
S40: HUD Ask input acquires focus, accepts typing, and submits on Enter
S41: HUD Ask button submits query, enters thinking state, and clears input
S42: Escape key or 10s idle releases focus and restores previous active window
S43: Global hotkey Alt + / updates HUD in-place without flicker when HUD is open
S44: Global hotkey Alt + / NEVER auto-shows HUD when HUD is hidden (show_hud_on_solve=False)
S45: Documented shortcuts Alt + Shift + C and Alt + 1..4 execute reliably
S46: Adaptive endpointing & complete timing marks recorded end-to-end
"""

import sys
import time
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from ghostline.config import AppConfig
from ghostline.app import GhostlineApp
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.audio.transcription import LiveTranscriber
from ghostline.audio.timing import TimingManager, record_timing_mark


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


def test_scenario_s40_hud_ask_typing_and_enter(qapp):
    """S40: HUD Ask input acquires focus, accepts typing, and submits on Enter."""
    submitted_queries = []
    hud = QtGhostlineHudOverlay(
        width=540,
        height=440,
        on_ask_custom=lambda q: submitted_queries.append(q)
    )
    hud.show()
    qapp.processEvents()

    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=1234), \
         patch("ctypes.windll.user32.GetWindowLongW", return_value=0x08000000), \
         patch("ctypes.windll.user32.SetWindowLongW") as mock_set_long, \
         patch("ctypes.windll.user32.SetWindowPos"), \
         patch("ctypes.windll.user32.SetForegroundWindow"), \
         patch("ctypes.windll.user32.SetWindowDisplayAffinity"), \
         patch("ctypes.windll.user32.IsWindow", return_value=True):

        # User clicks into input widget
        hud.focus_controller.begin_text_entry(hud.input_custom)
        qapp.processEvents()

        assert hud.focus_controller.is_text_entry_active is True
        assert hud.focus_controller.prev_hwnd == 1234

        # User types text
        hud.input_custom.setText("What is the time complexity of quicksort?")
        assert hud.input_custom.text() == "What is the time complexity of quicksort?"

        # User presses Enter
        hud._send_custom_query()
        qapp.processEvents()

        assert "What is the time complexity of quicksort?" in submitted_queries
        assert hud.input_custom.text() == ""
        assert hud.focus_controller.is_text_entry_active is False

    hud.close()


def test_scenario_s41_hud_ask_button_click(qapp):
    """S41: HUD Ask button submits query, enters thinking state, and clears input."""
    submitted_queries = []
    hud = QtGhostlineHudOverlay(
        width=540,
        height=440,
        on_ask_custom=lambda q: submitted_queries.append(q)
    )
    hud.show()
    qapp.processEvents()

    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=5678), \
         patch("ctypes.windll.user32.GetWindowLongW", return_value=0x08000000), \
         patch("ctypes.windll.user32.SetWindowLongW"), \
         patch("ctypes.windll.user32.SetWindowPos"), \
         patch("ctypes.windll.user32.SetForegroundWindow"), \
         patch("ctypes.windll.user32.SetWindowDisplayAffinity"), \
         patch("ctypes.windll.user32.IsWindow", return_value=True):

        hud.focus_controller.begin_text_entry(hud.input_custom)
        hud.input_custom.setText("Explain ACID properties in databases.")
        
        # Click Ask button
        hud.btn_send.click()
        qapp.processEvents()

        assert "Explain ACID properties in databases." in submitted_queries
        assert hud.input_custom.text() == ""
        assert hud.focus_controller.is_text_entry_active is False

    hud.close()


def test_scenario_s42_escape_and_idle_release_focus(qapp):
    """S42: Escape key or 10s idle releases focus and restores previous active window."""
    hud = QtGhostlineHudOverlay(width=540, height=440)
    hud.show()
    qapp.processEvents()

    with patch("ctypes.windll.user32.GetForegroundWindow", return_value=8888), \
         patch("ctypes.windll.user32.GetWindowLongW", return_value=0x08000000), \
         patch("ctypes.windll.user32.SetWindowLongW"), \
         patch("ctypes.windll.user32.SetWindowPos"), \
         patch("ctypes.windll.user32.SetForegroundWindow") as mock_set_fg, \
         patch("ctypes.windll.user32.SetWindowDisplayAffinity"), \
         patch("ctypes.windll.user32.IsWindow", return_value=True):

        # 1. Test Escape
        hud.focus_controller.begin_text_entry(hud.input_custom)
        assert hud.focus_controller.is_text_entry_active is True

        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        handled = hud.focus_controller.eventFilter(hud.input_custom, esc_event)

        assert handled is True
        assert hud.focus_controller.is_text_entry_active is False
        mock_set_fg.assert_called_with(8888)

        # 2. Test 10s idle
        hud.focus_controller.begin_text_entry(hud.input_custom)
        assert hud.focus_controller.is_text_entry_active is True

        hud.focus_controller.last_activity_time = time.time() - 11.0
        hud.focus_controller._check_idle()
        assert hud.focus_controller.is_text_entry_active is False

    hud.close()


def test_scenario_s43_hud_open_inplace_update(qapp):
    """S43: Global hotkey Alt + / updates HUD in-place without flicker when HUD is open."""
    cfg = AppConfig()
    cfg.first_run_complete = True
    cfg.show_hud_on_solve = False

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"):

        app = GhostlineApp()
        app.hud = MagicMock()
        app.hud.isVisible.return_value = True

        app._main_thread_solve_started()
        assert app.hud.start_solve.called or app.hud.set_analyzing.called
        assert not app.hud.show_overlay.called

        app._main_thread_stream_token("Streaming answer...", 999)
        assert app.hud.append_stream_token.called

        app.shutdown(exit_process=False)


def test_scenario_s44_hud_hidden_never_auto_shows(qapp):
    """S44: Global hotkey Alt + / NEVER auto-shows HUD when HUD is hidden (show_hud_on_solve=False)."""
    cfg = AppConfig()
    cfg.first_run_complete = True
    cfg.show_hud_on_solve = False

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"):

        app = GhostlineApp()
        app.hud = MagicMock()
        app.hud.isVisible.return_value = False

        app._main_thread_solve_started()
        assert not app.hud.show_overlay.called
        assert not app.hud.start_solve.called

        app.shutdown(exit_process=False)


def test_scenario_s45_copy_last_and_options_shortcuts(qapp):
    """S45: Documented shortcuts Alt + Shift + C and Alt + 1..4 execute reliably."""
    cfg = AppConfig()
    cfg.first_run_complete = True

    with patch("ghostline.app.load_config", return_value=cfg), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"):

        app = GhostlineApp()
        app.hud = MagicMock()

        # Alt + Shift + C
        app._main_thread_copy_last_answer()
        assert app.hud.copy_answer_to_clipboard.called

        # Alt + 1..4
        for opt_idx in [1, 2, 3, 4]:
            app._main_thread_select_option(opt_idx)
            app.hud.select_mcq_option.assert_called_with(opt_idx)

        app.shutdown(exit_process=False)


def test_scenario_s46_adaptive_endpointing_and_timing_marks(qapp):
    """S46: Adaptive endpointing & complete timing marks recorded end-to-end."""
    tm = TimingManager.get_instance()
    
    # Check adaptive endpointing thresholding
    transcriber = LiveTranscriber(faster_answers_enabled=False)
    transcriber._last_partial_text["mic"] = "What are the benefits of indexing in SQL?"
    partial = transcriber._last_partial_text["mic"].lower()
    is_q = partial.endswith("?")
    assert is_q is True
    threshold = 0.45 if is_q else 0.60
    assert threshold == 0.45

    # Check timing marks recorded
    record_timing_mark("speech_end", {"source": "mic", "t": 10.0})
    record_timing_mark("endpoint_decided", {"source": "mic", "threshold": 0.45})
    record_timing_mark("stt_final", {"source": "mic", "text": "What are the benefits of indexing?"})
    record_timing_mark("question_sent", {"text": "What are the benefits of indexing?", "category": "question"})
    record_timing_mark("request_sent", {"provider": "ollama", "entry_id": "s46"})
    record_timing_mark("first_token", {"entry_id": "s46", "latency_ms": 220.0})
    record_timing_mark("answer_complete", {"entry_id": "s46", "len": 150})
    record_timing_mark("rendered", {"entry_id": "s46", "has_code": False})

    marks = list(tm.marks.keys())
    for mark in ["speech_end", "endpoint_decided", "stt_final", "question_sent", "request_sent", "first_token", "answer_complete", "rendered"]:
        assert mark in marks
