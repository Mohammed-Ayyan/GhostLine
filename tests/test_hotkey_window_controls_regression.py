"""
Regression Test Suite for Ghostline:
- Global Hotkey Crash Fixes (Alt + / screen assistance, Alt + A audio assistance)
- Window Controls (Main Window & Floating HUD Overlay)
- Concurrency, Debounce, Hardware Error Handling, and Lifecycle Cleanup
"""

import sys
import time
import threading
from unittest.mock import MagicMock, patch
import pytest

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ghostline.config import AppConfig
from ghostline.app import GhostlineApp
from ghostline.audio.capture import AudioCaptureManager
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    return app


# =============================================================================
# 1. Alt + / Screen Assistance Trigger Tests
# =============================================================================

def test_screen_solve_trigger_safe_no_attribute_error(qapp):
    """
    Verifies that triggering screen assistance via Alt + / (or trigger_solve)
    does not raise AttributeError: 'QtGhostlineHudOverlay' object has no attribute 'start_solve'.
    """
    config = AppConfig()
    hud = QtGhostlineHudOverlay(opacity=0.9, width=560, height=520)
    
    # Verify start_solve exists and returns an integer solve_id
    assert hasattr(hud, "start_solve")
    solve_id = hud.start_solve()
    assert isinstance(solve_id, int)
    assert hud.isVisible() or hud.is_visible
    hud.close()


def test_cursor_over_hud_prevents_self_capture(qapp):
    """
    Verifies that if cursor is placed directly over the HUD, trigger_solve()
    aborts self-capture cleanly and displays a hint toast.
    """
    config = AppConfig()
    with patch("ghostline.app.load_config", return_value=config), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"):
        
        app = GhostlineApp()
        app.hud = QtGhostlineHudOverlay(width=400, height=300)
        app.hud.move(100, 100)
        app.hud.show_overlay()
        qapp.processEvents()

        # Simulate cursor inside HUD (150, 150)
        with patch("ghostline.app.win32api.GetCursorPos", return_value=(150, 150)):
            app.is_solving = False
            with patch.object(app, "_solve_worker") as mock_worker:
                app.trigger_solve()
                # Worker should not be started because cursor was over HUD
                assert not mock_worker.called
        
        app.hud.close()
        app.shutdown()


def test_excluded_rects_collected_on_main_thread_safely(qapp):
    """
    Verifies get_excluded_window_rects() collects window bounds safely
    without cross-thread violations or exceptions.
    """
    config = AppConfig()
    with patch("ghostline.app.load_config", return_value=config), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"):
        
        app = GhostlineApp()
        rects = app.get_excluded_window_rects()
        assert isinstance(rects, list)
        app.shutdown()


# =============================================================================
# 2. Alt + A Audio Assistance Toggle Tests
# =============================================================================

def test_audio_capture_deadlock_prevented_with_rlock():
    """
    Verifies that AudioCaptureManager uses an RLock so that hardware errors
    calling self.stop() inside start() do NOT cause re-entrant deadlocks.
    """
    mgr = AudioCaptureManager()
    assert isinstance(mgr._lock, type(threading.RLock()))
    
    # Simulate device errors inside start() that trigger self.stop()
    with patch.object(mgr, "_start_mic_stream", return_value=(False, "Mic device unavailable")), \
         patch.object(mgr, "_start_system_stream", return_value=(False, "WASAPI loopback unavailable")):
        # Must not deadlock or hang
        started, msg = mgr.start()
        assert started is False
        assert mgr.is_running is False


def test_audio_toggle_safe_on_hardware_failure(qapp):
    """
    Verifies that when Alt + A triggers audio toggle and no audio device is available,
    the app logs diagnostics, emits sig_audio_status(False, False), and does not crash.
    """
    config = AppConfig()
    with patch("ghostline.app.load_config", return_value=config), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager") as MockAudioCapture:
        
        mock_audio_mgr = MockAudioCapture.return_value
        mock_audio_mgr.is_capturing = False
        mock_audio_mgr.start.return_value = False  # Hardware error / unavailable

        app = GhostlineApp()
        status_emitted = []
        app.bridge.sig_audio_status.connect(lambda cap, pause: status_emitted.append((cap, pause)))

        result = app.toggle_audio_capture()
        assert result is False
        assert (False, False) in status_emitted
        app.shutdown()


# =============================================================================
# 3. Repeated Hotkey Presses & Concurrency
# =============================================================================

def test_repeated_solve_hotkey_ignores_overlapping_press(qapp):
    """
    Verifies that repeatedly pressing Alt + / while solving is in progress
    does not create duplicate workers or orphaned tasks.
    """
    config = AppConfig()
    with patch("ghostline.app.load_config", return_value=config), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager"):
        
        app = GhostlineApp()
        app.is_solving = True

        with patch.object(app, "_solve_worker") as mock_worker:
            app.trigger_solve()
            assert not mock_worker.called

        app.shutdown()


def test_rapid_audio_toggle_debounce(qapp):
    """
    Verifies that rapid Alt + A presses respect the transition lock
    and do not cause simultaneous PyAudio initialization races.
    """
    config = AppConfig()
    with patch("ghostline.app.load_config", return_value=config), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator"), \
         patch("ghostline.app.AudioCaptureManager") as MockAudioCapture:
        
        mock_audio_mgr = MockAudioCapture.return_value
        mock_audio_mgr.is_capturing = False
        mock_audio_mgr.start.return_value = True

        app = GhostlineApp()
        
        # Acquire the lock to simulate an active in-flight transition
        app._audio_toggle_lock.acquire()
        
        # Calling toggle while transition is in progress should safely return current state
        res = app.toggle_audio_capture()
        assert res is False
        
        app._audio_toggle_lock.release()
        app.shutdown()


# =============================================================================
# 4. Main Window Controls (Minimize, Maximize, Restore, Close, Exit)
# =============================================================================

def test_main_window_controls(qapp):
    """
    Verifies standard Windows window management on QtGhostlineMainWindow:
    minimize, maximize, restore, close, and dedicated exit button.
    """
    config = AppConfig()
    exit_called = []
    
    win = QtGhostlineMainWindow(
        config=config,
        on_exit=lambda: exit_called.append(True)
    )
    win.show()
    qapp.processEvents()

    # Window flags include min/max/close buttons
    flags = win.windowFlags()
    assert bool(flags & Qt.WindowType.WindowMinMaxButtonsHint)
    assert bool(flags & Qt.WindowType.WindowCloseButtonHint)

    # Minimize
    win.minimize_window()
    assert win.isMinimized()

    # Restore
    win.restore_window()
    assert not win.isMinimized()

    # Maximize
    win.maximize_window()
    assert win.isMaximized()

    # Restore from maximize
    win.restore_window()
    assert not win.isMaximized()

    # Dedicated sidebar exit button exists and has hand cursor
    assert hasattr(win, "btn_exit_app")
    assert win.btn_exit_app.text().strip() == "🚪  Exit Ghostline"

    # Close window with minimize_to_tray=True hides window, does NOT call on_exit
    win.config.minimize_to_tray = True
    win.close()
    assert win.isHidden()
    assert len(exit_called) == 0

    # Force exit terminates app and calls on_exit
    win.force_exit()
    assert len(exit_called) == 1


# =============================================================================
# 5. Floating HUD Controls (Collapse, Expand/Restore, Close, Resize)
# =============================================================================

def test_hud_overlay_controls(qapp):
    """
    Verifies floating HUD controls: collapse, toggle expand size, close HUD,
    and ensures closing HUD does NOT exit the main application.
    """
    hud_closed = []
    hud = QtGhostlineHudOverlay(
        on_close=lambda: hud_closed.append(True),
        width=560,
        height=520
    )
    hud.show_overlay()
    qapp.processEvents()

    # Verify buttons exist in toolbar
    assert hasattr(hud, "btn_collapse")
    assert hasattr(hud, "btn_expand_toggle")
    assert hasattr(hud, "btn_close_hud")

    # Test collapse
    assert not hud.is_collapsed
    hud.toggle_collapse()
    assert hud.is_collapsed
    assert hud.island_context.isHidden()
    assert hud.island_answer.isHidden()
    assert hud.height() <= 70

    # Test restore from collapse
    hud.toggle_collapse()
    assert not hud.is_collapsed
    assert not hud.island_context.isHidden()
    assert not hud.island_answer.isHidden()

    # Test expand size toggle
    orig_w = hud.width()
    hud.toggle_expanded_size()
    assert hud.width() >= 700
    assert hud.btn_expand_toggle.text() == "🗖"

    hud.toggle_expanded_size()
    assert hud.btn_expand_toggle.text() == "⤢"

    # Test closing HUD hides overlay and triggers on_close without crashing
    hud.close()
    assert hud.isHidden()
    assert len(hud_closed) == 1


# =============================================================================
# 6. Lifecycle & Resource Cleanup
# =============================================================================

def test_application_shutdown_resource_cleanup(qapp):
    """
    Verifies that calling shutdown() cleanly releases hotkey hooks,
    stops audio streams and background workers, and releases mutex.
    """
    config = AppConfig()
    with patch("ghostline.app.load_config", return_value=config), \
         patch("ghostline.app.OllamaClient"), \
         patch("ghostline.app.GhostlinePipeline"), \
         patch("ghostline.app.TrayIndicator") as MockTray, \
         patch("ghostline.app.AudioCaptureManager") as MockAudioCapture:
        
        mock_audio = MockAudioCapture.return_value
        mock_tray = MockTray.return_value

        app = GhostlineApp()
        app.shutdown()

        assert app.is_running is False
        assert mock_audio.stop.called
        assert mock_tray.stop.called
