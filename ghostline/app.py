import os
import sys
from pathlib import Path

# Add parent directory to sys.path if run directly
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import time
import json
import threading
from typing import Optional, Dict, Any, List, Tuple, Callable
import numpy as np

import ctypes
from ctypes import wintypes
import win32con
import win32gui
import win32api
import win32event
import winerror
import pywintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL


import logging
from ghostline.config import load_config, save_config, get_app_dir, get_config_path
from ghostline.core.pipeline import GhostlinePipeline, DuplicateQuestionError
from ghostline.core.pipeline_tracer import PipelineTracer
from ghostline.core.hover_detector import HoverDetector
from ghostline.core.llm_client import OllamaClient, AnswerResult
from ghostline.ui.presentation import (
    build_answer_presentation,
    PresentedAnswer,
    TYPE_MCQ,
    TYPE_UNCERTAIN,
    TYPE_ERROR
)
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.ui.main_window import GhostlineMainWindow
from ghostline.ui.hud_overlay import GhostlineHudOverlay
from ghostline.ui.tray_indicator import TrayIndicator
from ghostline.ui.caps_indicator import CapsLockIndicator
from ghostline.audio.capture import AudioCaptureManager, AudioDeviceManager
from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.ui.audio_panel import LiveAudioPanel

from ghostline import __version__

# Register custom Win32 messages for single-instance activation and IPC solve triggers
WM_GHOSTLINE_WAKEUP = win32gui.RegisterWindowMessage("GhostlineWakeUpMsg")
WM_GHOSTLINE_SOLVE = win32gui.RegisterWindowMessage("GhostlineSolveMsg")
SINGLE_INSTANCE_SINK_CLASS = "GhostlineSingleInstanceSink"


class QtEventBridge(QObject):
    """
    Centralized thread-safe event dispatcher for Ghostline.
    All background threads (Win32 hotkey loop, audio capture, transcription,
    solve worker, Ollama assistant) emit signals through this bridge.
    Connected slots execute safely on the PyQt6 main GUI thread via queued connections.
    """
    # Hotkey / Window Actions
    sig_trigger_solve = pyqtSignal(bool)       # is_auto_hover
    sig_toggle_hud = pyqtSignal()
    sig_toggle_audio_capture = pyqtSignal()
    sig_toggle_audio_panel = pyqtSignal()
    sig_show_main_window = pyqtSignal()

    # Screen Solve Lifecycle
    sig_solve_started = pyqtSignal()
    sig_solve_completed = pyqtSignal(object)   # res (PipelineExecutionResult)
    sig_solve_error = pyqtSignal(str, str, object)  # err_msg, raw_text, parsed_q
    sig_stream_token = pyqtSignal(str, int)    # token, solve_id
    sig_hud_state = pyqtSignal(str, object, int) # stage, presentation, solve_id

    # Audio & Transcription Streaming
    sig_audio_level = pyqtSignal(str, float, float) # source, rms, peak
    sig_audio_partial = pyqtSignal(str, str)        # text, source
    sig_audio_segment = pyqtSignal(object)          # segment (TranscriptSegment)
    sig_audio_thinking = pyqtSignal(str)            # question
    sig_audio_answer = pyqtSignal(str, str, object) # question, answer, code
    sig_audio_error = pyqtSignal(str)               # err
    sig_audio_status = pyqtSignal(bool, bool)       # is_capturing, is_paused


def parse_hotkey_string(hotkey_str: str) -> Tuple[int, int]:
    """Parses a hotkey string like 'alt+/', 'ctrl+alt+a', 'win+shift+f1' into (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in hotkey_str.replace("+", " ").split()]
    mod = 0
    vk = 0
    for p in parts:
        if p in ("alt", "menu"):
            mod |= win32con.MOD_ALT
        elif p in ("ctrl", "control"):
            mod |= win32con.MOD_CONTROL
        elif p in ("shift",):
            mod |= win32con.MOD_SHIFT
        elif p in ("win", "windows"):
            mod |= win32con.MOD_WIN
        elif p == "/":
            vk = 0xBF  # VK_OEM_2
        elif len(p) == 1 and p.isalnum():
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            fn = int(p[1:])
            if 1 <= fn <= 24:
                vk = win32con.VK_F1 + (fn - 1)
    if vk == 0:
        vk = 0xBF
    if mod == 0:
        mod = win32con.MOD_ALT
    return mod, vk


def setup_file_logging():
    try:
        log_file = get_app_dir() / "ghostline.log"
        handlers = [
            logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
        ]
        if sys.stdout is not None:
            handlers.append(logging.StreamHandler(sys.stdout))
        logging.basicConfig(
            handlers=handlers,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            force=True
        )
    except Exception:
        pass


class GhostlineApp:
    def __init__(self, mutex=None):
        self._mutex = mutex
        setup_file_logging()
        self.sink_hwnd: Optional[int] = None
        self.is_running = True
        self.is_solving = False
        self.hotkey_thread: Optional[threading.Thread] = None
        self.hotkey_hwnd: Optional[int] = None
        self.hotkey_thread_id: Optional[int] = None
        self.hotkey_registered: bool = False
        self.registered_hotkey_ids: List[int] = []
        self.main_window: Optional[QtGhostlineMainWindow] = None

        # Initialize PyQt6 QApplication first on main thread
        self.qapp = QApplication.instance()
        if self.qapp is None:
            self.qapp = QApplication(sys.argv)
        from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
        self.qapp.setStyleSheet(QT_MAIN_STYLESHEET)

        # Initialize Centralized Thread-Safe Event Dispatcher Bridge
        self.bridge = QtEventBridge()
        self._connect_bridge_signals()

        # Set up single-instance sink window on main thread immediately
        self._setup_sink_window()

        self.config = load_config()
        logging.info("Configuration loaded: Model=%s, Endpoint=%s, Hotkey=%s, CapsLock=%s, Hover=%s",
                     self.config.model_name, self.config.ollama_url, self.config.hotkey,
                     getattr(self.config, "caps_lock_indicator", False),
                     getattr(self.config, "hover_to_answer_enabled", False))
        self.ollama = OllamaClient(
            base_url=self.config.ollama_url,
            default_model=self.config.model_name
        )
        self.pipeline = GhostlinePipeline(
            ollama_client=self.ollama,
            model_name=self.config.model_name,
            capture_mode=getattr(self.config, "capture_mode", "full_screen"),
            diagnostic_mode=getattr(self.config, "diagnostic_mode", False)
        )

        # Build Modern PyQt6 Main Window
        self.main_window = QtGhostlineMainWindow(
            config=self.config,
            on_trigger_solve=self.trigger_solve,
            on_settings_saved=self.on_settings_saved,
            on_toggle_hud=self.toggle_hud,
            on_test_caps=self.test_caps_lock,
            on_exit=self.shutdown,
            ollama_client=self.ollama,
            on_test_mic=self.test_mic_capture,
            on_test_loopback=self.test_system_loopback,
            on_test_transcription=self.test_transcription_engine,
            get_audio_diagnostics=self.get_audio_diagnostics,
            on_toggle_audio=self.toggle_audio_capture
        )
        root = self.main_window

        # Build floating HUD overlay (initially hidden)
        self.hud = QtGhostlineHudOverlay(
            on_close=self.on_hud_close,
            on_toggle_pause=self.toggle_hover_pause,
            on_position_changed=self.on_hud_position_changed,
            on_retry=lambda: self.trigger_solve(is_auto_hover=False),
            opacity=getattr(self.config, "hud_opacity", 0.95),
            width=getattr(self.config, "hud_width", 560),
            height=getattr(self.config, "hud_height", 520),
            is_pinned=getattr(self.config, "hud_pinned", False),
            always_on_top=getattr(self.config, "hud_always_on_top", True),
            exclude_from_capture=getattr(self.config, "exclude_from_capture", True),
            is_paused=getattr(self.config, "is_hover_paused", False),
            on_toggle_audio=self.toggle_audio_panel,
            on_ask_custom=self.on_hud_ask_custom,
            on_trigger_screenshot=lambda: self.trigger_solve(is_auto_hover=False)
        )
        self.hud.launch(parent=root, start_visible=False)

        # Initialize Video Call Audio Extraction & Live AI Assistant
        self.audio_capture = AudioCaptureManager(
            on_audio_chunk=self._on_audio_chunk,
            on_level_update=self._on_audio_level_update,
            system_device_index=getattr(self.config, "audio_system_device_index", None),
            mic_device_index=getattr(self.config, "audio_mic_device_index", None),
            system_enabled=getattr(self.config, "audio_source_system", True),
            mic_enabled=getattr(self.config, "audio_source_mic", True),
            system_volume=getattr(self.config, "audio_system_volume", 1.0),
            mic_volume=getattr(self.config, "audio_mic_volume", 1.0),
            chunk_duration_sec=getattr(self.config, "audio_chunk_sec", 2.0),
            save_recordings=getattr(self.config, "save_audio_recordings", False),
            recording_path=getattr(self.config, "audio_recording_path", None)
        )


        self.transcriber = LiveTranscriber(
            model_name=getattr(self.config, "audio_whisper_model", "tiny"),
            language=getattr(self.config, "audio_language", "auto"),
            on_partial=self._on_transcription_partial,
            on_segment=self._on_transcription_segment,
            max_history_items=getattr(self.config, "transcript_retention_max_items", 200)
        )

        self.audio_assistant = LiveAudioAssistant(
            ollama_client=self.ollama,
            model_name=self.config.model_name,
            max_context_turns=getattr(self.config, "audio_context_turns", 12),
            on_question_detected=self._on_audio_question_detected,
            on_answer=self._on_audio_answer,
            on_error=self._on_audio_error,
            auto_answer_questions=getattr(self.config, "audio_auto_answer_questions", True),
            debounce_sec=getattr(self.config, "audio_question_debounce_sec", 2.0)
        )

        # Dedicated Floating Live Audio & Transcription Panel
        self.audio_panel = QtLiveAudioPanel(
            on_start_capture=self.start_audio_capture,
            on_stop_capture=self.stop_audio_capture,
            on_toggle_pause=self.toggle_audio_pause,
            on_toggle_call_audio=self.set_call_audio_enabled,
            on_toggle_mic=self.set_mic_audio_enabled,
            on_ask_custom=self.ask_audio_custom,
            on_clear_transcript=self.clear_audio_transcript,
            on_export_transcript=self.export_audio_transcript,
            on_close=self.on_audio_panel_close,
            opacity=getattr(self.config, "hud_opacity", 0.95),
            always_on_top=getattr(self.config, "hud_always_on_top", True),
            exclude_from_capture=getattr(self.config, "exclude_from_capture", True),
            call_audio_enabled=getattr(self.config, "audio_source_system", True),
            mic_enabled=getattr(self.config, "audio_source_mic", True)
        )
        self.audio_panel.launch(parent=root, start_visible=False)

        # Build Automatic Hover-to-Answer Engine
        self.hover_detector = HoverDetector(
            on_trigger=lambda: self.trigger_solve(is_auto_hover=True),
            is_solving_fn=lambda: self.is_solving,
            get_excluded_rects=self.get_excluded_window_rects,
            enabled=getattr(self.config, "hover_to_answer_enabled", False),
            hover_delay_ms=getattr(self.config, "hover_delay_ms", 800),
            cooldown_sec=getattr(self.config, "hover_cooldown_sec", 3.0),
            movement_threshold_px=getattr(self.config, "hover_movement_threshold_px", 15),
            is_paused=getattr(self.config, "is_hover_paused", False)
        )

        # Build Tray Indicator with full navigation menu
        self.tray = TrayIndicator(
            on_trigger=self.trigger_solve,
            on_open_main=self.main_window.show_window,
            on_toggle_hud=self.toggle_hud,
            on_open_settings=self.open_settings,
            on_exit=self.shutdown,
            on_toggle_pause=self.toggle_hover_pause,
            on_toggle_audio=self.toggle_audio_capture,
            on_toggle_audio_panel=self.toggle_audio_panel
        )

        # Initialize Caps Lock Indicator with configured timing
        self.caps_indicator = CapsLockIndicator(
            enabled=getattr(self.config, "caps_lock_indicator", False),
            pulse_on_ms=getattr(self.config, "caps_pulse_on_ms", 300),
            pulse_off_ms=getattr(self.config, "caps_pulse_off_ms", 250),
            sequence_cooldown_ms=getattr(self.config, "caps_sequence_cooldown_ms", 700)
        )

    def _connect_bridge_signals(self):
        """Connects worker-thread signals to main-thread slots via Qt queued connections."""
        self.bridge.sig_trigger_solve.connect(self._main_thread_trigger_solve)
        self.bridge.sig_toggle_hud.connect(self._main_thread_toggle_hud)
        self.bridge.sig_toggle_audio_capture.connect(self._main_thread_toggle_audio_capture)
        self.bridge.sig_toggle_audio_panel.connect(self._main_thread_toggle_audio_panel)
        self.bridge.sig_show_main_window.connect(self._main_thread_show_main_window)
        self.bridge.sig_solve_started.connect(self._main_thread_solve_started)
        self.bridge.sig_solve_completed.connect(self._main_thread_solve_completed)
        self.bridge.sig_solve_error.connect(self._main_thread_solve_error)
        self.bridge.sig_stream_token.connect(self._main_thread_stream_token)
        self.bridge.sig_hud_state.connect(self._main_thread_hud_state)
        self.bridge.sig_audio_level.connect(self._main_thread_audio_level)
        self.bridge.sig_audio_partial.connect(self._main_thread_audio_partial)
        self.bridge.sig_audio_segment.connect(self._main_thread_audio_segment)
        self.bridge.sig_audio_thinking.connect(self._main_thread_audio_thinking)
        self.bridge.sig_audio_answer.connect(self._main_thread_audio_answer)
        self.bridge.sig_audio_error.connect(self._main_thread_audio_error)
        self.bridge.sig_audio_status.connect(self._main_thread_audio_status)

    def _main_thread_trigger_solve(self, is_auto_hover: bool):
        self.trigger_solve(is_auto_hover=is_auto_hover)

    def _main_thread_toggle_hud(self):
        if hasattr(self, "hud") and self.hud:
            self.hud.toggle_visibility()

    def _main_thread_toggle_audio_capture(self):
        self.toggle_audio_capture()

    def _main_thread_toggle_audio_panel(self):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.toggle_visibility()

    def _main_thread_show_main_window(self):
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.show_window()

    def _main_thread_solve_started(self):
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if show_hud and hasattr(self, "hud") and self.hud:
            self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
            self.hud.show_overlay()
            self.hud.set_state("capturing")
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.on_solve_started()
        if hasattr(self, "tray") and self.tray:
            self.tray.update_badge(badge="", status="thinking", tooltip="Ghostline — Thinking…")

    def _main_thread_solve_completed(self, res):
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.on_solve_completed(res)

        presentation = build_answer_presentation(res.parsed_question, res.answer_result)
        badge = presentation.badge
        is_mcq = (presentation.question_type == TYPE_MCQ)
        is_valid = presentation.is_validated
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)

        if not is_valid or presentation.question_type in [TYPE_UNCERTAIN, TYPE_ERROR]:
            if show_hud and hasattr(self, "hud") and self.hud:
                self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                self.hud.set_state("error", presentation=presentation)
            if hasattr(self, "tray") and self.tray:
                self.tray.update_badge(
                    badge="?",
                    status="error",
                    is_validated=False,
                    is_multiple_choice=is_mcq,
                    tooltip=f"Ghostline — {presentation.headline}"
                )
            if hasattr(self, "caps_indicator") and self.caps_indicator:
                self.caps_indicator.pulse("?")
        else:
            if show_hud and hasattr(self, "hud") and self.hud:
                self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                self.hud.set_state("answer", presentation=presentation)
            if hasattr(self, "tray") and self.tray:
                self.tray.update_badge(
                    badge=badge,
                    status="normal",
                    is_validated=True,
                    is_multiple_choice=is_mcq,
                    tooltip=f"Ghostline — {presentation.headline}"
                )
            if hasattr(self, "caps_indicator") and self.caps_indicator:
                self.caps_indicator.pulse(badge)

        if getattr(self.config, "auto_copy_answer", False):
            try:
                if hasattr(self, "hud") and self.hud:
                    self.hud.copy_answer_to_clipboard()
            except Exception:
                pass

    def _main_thread_solve_error(self, err_msg: str, raw_text: str, parsed_q: Optional[Any]):
        if hasattr(self, "main_window") and self.main_window:
            if hasattr(self.main_window, "on_solve_error"):
                try:
                    self.main_window.on_solve_error(err_msg, raw_text=raw_text)
                except TypeError:
                    self.main_window.on_solve_error(err_msg)

        is_extraction_uncertain = ("Unreliable question extraction" in err_msg or "does not contain question indicators" in err_msg)
        badge_char = "?" if is_extraction_uncertain else "!"

        err_ans = AnswerResult(
            answer_option=badge_char,
            proposed_option=badge_char,
            validation_status="uncertain" if is_extraction_uncertain else "error",
            is_validated=False,
            error=err_msg,
            tray_badge=badge_char
        )
        err_presentation = build_answer_presentation(parsed_q, err_ans)
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if show_hud and hasattr(self, "hud") and self.hud:
            self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
            self.hud.set_state("error", presentation=err_presentation)
        if hasattr(self, "tray") and self.tray:
            self.tray.update_badge(
                badge=badge_char,
                status="error",
                tooltip=f"Ghostline — {err_presentation.headline}"
            )
        if hasattr(self, "caps_indicator") and self.caps_indicator:
            self.caps_indicator.pulse(badge_char)

    def _main_thread_stream_token(self, token: str, solve_id: int):
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if show_hud and hasattr(self, "hud") and self.hud:
            self.hud.append_stream_token(token, solve_id=solve_id)

    def _main_thread_hud_state(self, stage: str, presentation: Optional[Any], solve_id: int):
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if show_hud and hasattr(self, "hud") and self.hud:
            self.hud.set_state(stage, presentation=presentation, solve_id=solve_id)

    def _main_thread_audio_level(self, source: str, rms: float, peak: float):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.update_level(source, rms, peak)
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.update_audio_level(source, rms, peak)

    def _main_thread_audio_partial(self, text: str, source: str):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.update_partial(text, source)

    def _main_thread_audio_segment(self, segment: Any):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.append_final_segment(segment)
        if hasattr(self, "hud") and self.hud:
            self.hud.append_transcript_segment(segment)
        if hasattr(self, "main_window") and self.main_window and hasattr(self.main_window, "on_audio_segment_received"):
            self.main_window.on_audio_segment_received(segment)

    def _main_thread_audio_thinking(self, question: str):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_thinking(question)

    def _main_thread_audio_answer(self, question: str, answer: str, code: Optional[str]):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_answer(question, answer, code)
        if hasattr(self, "hud") and self.hud:
            full_ans = f"Q: {question}\n{answer}" if question else answer
            self.hud.append_ai_answer(full_ans)

    def _main_thread_audio_error(self, err: str):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_error(err)

    def _main_thread_audio_status(self, is_capturing: bool, is_paused: bool):
        if hasattr(self, "hud") and self.hud:
            self.hud.update_audio_status(is_capturing=is_capturing, is_paused=is_paused)
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_capture_state(is_capturing)
            self.audio_panel.set_pause_state(is_paused)
            if is_capturing and not self.audio_panel.isVisible():
                self.audio_panel.show_panel()
        if hasattr(self, "main_window") and self.main_window and hasattr(self.main_window, "update_audio_status"):
            self.main_window.update_audio_status(is_capturing=is_capturing, is_paused=is_paused)

    def _setup_sink_window(self):
        """Creates hidden Win32 sink window on main thread for instant single-instance wakeup and solve IPC."""
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = SINGLE_INSTANCE_SINK_CLASS

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_GHOSTLINE_WAKEUP:
                logging.info("[Diagnostic %s] Received WakeUp message in sink wndproc. Restoring main window.", time.strftime("%H:%M:%S"))
                self.bridge.sig_show_main_window.emit()
                return 0
            elif msg == WM_GHOSTLINE_SOLVE:
                logging.info("[Diagnostic %s] Received Solve message in sink wndproc. Triggering solve.", time.strftime("%H:%M:%S"))
                self.bridge.sig_trigger_solve.emit(False)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc.lpfnWndProc = wndproc

        try:
            win32gui.RegisterClass(wc)
        except pywintypes.error as e:
            if e.winerror != 1410:
                logging.warning(f"Sink window class registration note: {e}")

        try:
            self.sink_hwnd = win32gui.CreateWindow(
                wc.lpszClassName, "GhostlineSinkWindow", 0, 0, 0, 0, 0, 0, 0, 0, None
            )
            try:
                for msg_id in (WM_GHOSTLINE_WAKEUP, WM_GHOSTLINE_SOLVE):
                    user32.ChangeWindowMessageFilter(msg_id, 1)  # MSGFLT_ADD
            except Exception:
                pass
            logging.info("Single-instance sink window created on main thread: HWND %s", self.sink_hwnd)
        except Exception as e:
            logging.exception(f"Failed to create sink window: {e}")
            self.sink_hwnd = None

    def toggle_hud(self):
        """Toggles floating mini-HUD visibility on demand."""
        self.hud.toggle_visibility()

    def open_settings(self):
        """Restores main window and switches to Settings screen."""
        self.main_window.show_window()
        self.main_window.show_screen("settings")

    def test_caps_lock(self):
        """Triggers a 2-pulse test signal on keyboard LED with hardware verification."""
        logging.info("[*] Manual Caps Lock test triggered from Settings/UI.")
        orig = self.caps_indicator.enabled
        self.caps_indicator.enabled = True
        try:
            # First verify toggle ability
            toggled = self.caps_indicator.test_toggle()
            logging.info("[*] Caps Lock hardware toggle verification result: %s", toggled)
            self.caps_indicator.pulse("B")
        finally:
            self.caps_indicator.enabled = orig

    def get_excluded_window_rects(self):
        """Returns bounding boxes of active Ghostline windows to avoid self-capture in hover detection."""
        rects = []
        if hasattr(self, "hud") and self.hud and getattr(self.hud, "is_visible", False):
            r = self.hud.get_window_rect()
            if r:
                rects.append(r)
        if hasattr(self, "main_window") and self.main_window:
            r = self.main_window.get_window_rect()
            if r:
                rects.append(r)
        if hasattr(self, "audio_panel") and self.audio_panel and getattr(self.audio_panel, "is_visible", False):
            r = self.audio_panel.get_window_rect()
            if r:
                rects.append(r)
        return rects

    def toggle_hover_pause(self) -> bool:
        """Toggles hover-to-answer pause state across hover detector, HUD, tray, and config."""
        if not hasattr(self, "hover_detector"):
            return False
        paused = self.hover_detector.toggle_pause()
        self.config.is_hover_paused = paused
        if hasattr(self, "hud") and self.hud:
            self.hud.is_paused = paused
            if hasattr(self.hud, "btn_pause") and self.hud.btn_pause:
                from ghostline.ui.hud_overlay import C_EMERALD, C_AMBER
                self.hud.btn_pause.config(
                    text="⏸" if not paused else "▶",
                    fg=C_EMERALD if not paused else C_AMBER
                )
        save_config(self.config)
        logging.info("[GhostlineApp] Hover detection toggled: paused=%s", paused)
        return paused

    def on_hud_position_changed(self, x: int, y: int):
        """Persists HUD position when moved."""
        self.config.hud_pos_x = x
        self.config.hud_pos_y = y
        if getattr(self.config, "hud_pinned", False):
            save_config(self.config)

    def on_settings_saved(self, new_config):
        """Called when user saves settings from the UI."""
        self.config = new_config
        self.caps_indicator.enabled = new_config.caps_lock_indicator
        self.caps_indicator.pulse_on_sec = max(0.04, new_config.caps_pulse_on_ms / 1000.0)
        self.caps_indicator.pulse_off_sec = max(0.04, new_config.caps_pulse_off_ms / 1000.0)
        self.pipeline.model_name = new_config.model_name
        self.pipeline.capture_mode = getattr(new_config, "capture_mode", "full_screen")
        self.pipeline.diagnostic_mode = getattr(new_config, "diagnostic_mode", False)
        self.ollama.default_model = new_config.model_name
        self.ollama.base_url = new_config.ollama_url

        if hasattr(self, "hover_detector"):
            self.hover_detector.update_config(
                enabled=new_config.hover_to_answer_enabled,
                hover_delay_ms=new_config.hover_delay_ms,
                cooldown_sec=new_config.hover_cooldown_sec,
                movement_threshold_px=new_config.hover_movement_threshold_px
            )
            if new_config.is_hover_paused != self.hover_detector.is_paused:
                if new_config.is_hover_paused:
                    self.hover_detector.pause()
                else:
                    self.hover_detector.resume()

        if hasattr(self, "hud") and self.hud and self.hud.root:
            try:
                self.hud.opacity = new_config.hud_opacity
                self.hud.root.attributes("-alpha", new_config.hud_opacity)
                self.hud.always_on_top = new_config.hud_always_on_top
                self.hud.root.attributes("-topmost", new_config.hud_always_on_top)
                self.hud.is_pinned = new_config.hud_pinned
                self.hud.exclude_from_capture = new_config.exclude_from_capture
                if self.hud.hwnd:
                    from ghostline.core.capture_exclusion import set_capture_exclusion
                    set_capture_exclusion(self.hud.hwnd, new_config.exclude_from_capture)
            except Exception as e:
                logging.warning("[HUD] Settings application warning: %s", e)

        # Update Live Audio settings
        if hasattr(self, "audio_capture"):
            self.audio_capture.system_enabled = getattr(new_config, "audio_source_system", True)
            self.audio_capture.mic_enabled = getattr(new_config, "audio_source_mic", True)
            self.audio_capture.system_volume = getattr(new_config, "audio_system_volume", 1.0)
            self.audio_capture.mic_volume = getattr(new_config, "audio_mic_volume", 1.0)
            self.audio_capture.chunk_duration_sec = getattr(new_config, "audio_chunk_sec", 2.0)
            self.audio_capture.save_recordings = getattr(new_config, "save_audio_recordings", False)
            self.audio_capture.recording_path = getattr(new_config, "audio_recording_path", None)

        if hasattr(self, "transcriber"):
            self.transcriber.language = getattr(new_config, "audio_language", "auto")

        if hasattr(self, "audio_assistant"):
            self.audio_assistant.auto_answer_questions = getattr(new_config, "audio_auto_answer_questions", True)
            self.audio_assistant.debounce_sec = getattr(new_config, "audio_question_debounce_sec", 2.0)
            self.audio_assistant.max_context_turns = getattr(new_config, "audio_context_turns", 12)
            self.audio_assistant.model_name = new_config.model_name

        if hasattr(self, "audio_panel") and self.audio_panel and self.audio_panel.root:
            try:
                self.audio_panel.exclude_from_capture = getattr(new_config, "exclude_from_capture", True)
                if self.audio_panel.hwnd:
                    from ghostline.core.capture_exclusion import set_capture_exclusion
                    set_capture_exclusion(self.audio_panel.hwnd, new_config.exclude_from_capture)
            except Exception as e:
                logging.warning("[AudioPanel] Capture exclusion warning: %s", e)

        logging.info("Settings updated and reloaded in active runtime.")

    # -------------------------------------------------------------
    # Live Audio & Transcription Methods
    # -------------------------------------------------------------
    def _on_audio_chunk(self, data, *args, **kwargs):
        source = kwargs.get("source")
        sample_rate = kwargs.get("sample_rate", 16000)
        if args:
            if len(args) == 1:
                source = args[0]
            elif len(args) >= 2:
                sample_rate = args[0]
                source = args[1]
        if source is None:
            source = "call"
        if hasattr(self, "transcriber") and self.transcriber:
            self.transcriber.push_audio_chunk(data, sample_rate, source)

    def _on_audio_level_update(self, source: str, rms: float, peak: float):
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_level.emit(source, float(rms), float(peak))
        else:
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.update_level(source, rms, peak)
            if hasattr(self, "main_window") and self.main_window:
                self.main_window.update_audio_level(source, rms, peak)

    def _on_transcription_partial(self, text, source):
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_partial.emit(str(text), str(source))
        elif hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.update_partial(text, source)

    def _on_transcription_segment(self, segment):
        if hasattr(self, "audio_assistant") and self.audio_assistant:
            self.audio_assistant.add_transcript_segment(segment)
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_segment.emit(segment)
        else:
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.append_final_segment(segment)
            if hasattr(self, "hud") and self.hud:
                self.hud.append_transcript_segment(segment)
            if hasattr(self, "main_window") and self.main_window and hasattr(self.main_window, "on_audio_segment_received"):
                self.main_window.on_audio_segment_received(segment)

    def _on_audio_question_detected(self, question):
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_thinking.emit(str(question))
        elif hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_thinking(question)

    def _on_audio_answer(self, question, answer, code):
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_answer.emit(str(question or ""), str(answer or ""), code)
        else:
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_ai_answer(question, answer, code)
            if hasattr(self, "hud") and self.hud:
                full_ans = f"Q: {question}\n{answer}" if question else answer
                self.hud.append_ai_answer(full_ans)

    def _on_audio_error(self, err):
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_error.emit(str(err))
        elif hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_error(err)

    def on_hud_ask_custom(self, query: str):
        """Dispatches manual question entered in HUD bottom query input."""
        logging.info("[HUD] Manual query submitted: %s", query[:50])
        if hasattr(self, "hud") and getattr(self.hud, "active_mode", "answer") == "audio":
            self.ask_audio_custom(query)
            return

        def _worker():
            solve_id = self.hud.start_solve() if hasattr(self.hud, "start_solve") else 0
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_hud_state.emit("thinking", None, solve_id)
            elif hasattr(self, "hud") and self.hud:
                self.hud.set_state("thinking", solve_id=solve_id)
            try:
                res = self.ollama.solve_question(
                    question_text=query,
                    options=None,
                    model=self.config.model_name
                )
                presentation = build_answer_presentation(None, res)
                if hasattr(self, "bridge") and self.bridge:
                    self.bridge.sig_hud_state.emit("answer", presentation, solve_id)
                elif hasattr(self, "hud") and self.hud:
                    self.hud.set_state("answer", presentation=presentation, solve_id=solve_id)
            except Exception as e:
                logging.exception(f"Manual query solve failed: {e}")
                err_ans = AnswerResult(
                    answer_option="!",
                    proposed_option="!",
                    validation_status="error",
                    is_validated=False,
                    error=str(e),
                    tray_badge="!"
                )
                presentation = build_answer_presentation(None, err_ans)
                if hasattr(self, "bridge") and self.bridge:
                    self.bridge.sig_hud_state.emit("error", presentation, solve_id)
                elif hasattr(self, "hud") and self.hud:
                    self.hud.set_state("error", presentation=presentation, solve_id=solve_id)

        threading.Thread(target=_worker, daemon=True).start()

    def get_audio_diagnostics(self) -> Dict[str, Any]:
        cap_tele = self.audio_capture.get_telemetry() if hasattr(self, "audio_capture") else {}
        trans_tele = self.transcriber.get_telemetry() if hasattr(self, "transcriber") else {}
        return {
            "capture": cap_tele,
            "transcription": trans_tele
        }

    def test_mic_capture(self, duration_sec: float = 3.0, update_fn=None) -> Dict[str, Any]:
        """Runs a 3-second live microphone capture test, measures RMS, and transcribes spoken speech."""
        import pyaudiowpatch as pyaudio
        p = None
        stream = None
        recorded_chunks = []
        stream_format = pyaudio.paInt16
        callback_stats = {"count": 0, "frames": 0, "peak": 0.0, "max_rms": 0.0}
        try:
            p = pyaudio.PyAudio()
            mic_dev = None

            # 1. Configured device if valid
            cfg_mic = getattr(self.config, "audio_mic_device_index", None)
            if cfg_mic is not None:
                try:
                    d = p.get_device_info_by_index(cfg_mic)
                    if d.get("maxInputChannels", 0) > 0 and not d.get("isLoopbackDevice", False):
                        mic_dev = d
                except Exception:
                    mic_dev = None

            # 2. WASAPI default input
            if mic_dev is None:
                try:
                    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    def_in = wasapi_info.get("defaultInputDevice")
                    if def_in is not None and def_in >= 0:
                        d = p.get_device_info_by_index(def_in)
                        if not d.get("isLoopbackDevice", False):
                            mic_dev = d
                except Exception:
                    pass

            # 3. System default input
            if mic_dev is None:
                try:
                    mic_dev = p.get_default_input_device_info()
                except Exception:
                    mic_dev = None

            if mic_dev is None:
                return {
                    "success": False,
                    "rms": 0.0,
                    "peak": 0.0,
                    "message": "FAILED: No microphone input device found on this system. Check physical connection and Windows Sound Settings."
                }

            rate = int(mic_dev.get("defaultSampleRate", 44100))
            channels = min(2, max(1, int(mic_dev.get("maxInputChannels", 1))))

            def _cb(in_data, frame_count, time_info, status):
                callback_stats["count"] += 1
                callback_stats["frames"] += frame_count
                if in_data:
                    recorded_chunks.append(in_data)
                return (None, pyaudio.paContinue)

            # Format negotiation: try paInt16 first, fallback to paFloat32
            for fmt in (pyaudio.paInt16, pyaudio.paFloat32):
                try:
                    stream = p.open(
                        format=fmt,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=mic_dev["index"],
                        stream_callback=_cb,
                        frames_per_buffer=1024
                    )
                    stream_format = fmt
                    break
                except Exception:
                    pass

            if stream is None:
                return {
                    "success": False,
                    "rms": 0.0,
                    "peak": 0.0,
                    "device": mic_dev["name"],
                    "message": f"ERROR: Could not open microphone stream on '{mic_dev['name']}'."
                }

            stream.start_stream()
            start_t = time.time()
            while time.time() - start_t < duration_sec:
                time.sleep(0.08)
                if recorded_chunks and update_fn:
                    last_pcm = recorded_chunks[-1]
                    if stream_format == pyaudio.paFloat32:
                        chunk_arr = np.frombuffer(last_pcm, dtype=np.float32)
                    else:
                        chunk_arr = np.frombuffer(last_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                    rms = float(np.sqrt(np.mean(chunk_arr**2))) if len(chunk_arr) > 0 else 0.0
                    peak = float(np.max(np.abs(chunk_arr))) if len(chunk_arr) > 0 else 0.0
                    callback_stats["peak"] = max(callback_stats["peak"], peak)
                    callback_stats["max_rms"] = max(callback_stats["max_rms"], rms)
                    try:
                        update_fn("mic", rms, peak)
                    except TypeError:
                        update_fn("mic", rms)

            stream.stop_stream()
            stream.close()
            stream = None

            if not recorded_chunks:
                return {
                    "success": False,
                    "rms": 0.0,
                    "peak": 0.0,
                    "device": mic_dev["name"],
                    "message": (
                        f"FAILED: No audio chunks received from '{mic_dev['name']}' (0 callbacks). "
                        "Please verify Windows Settings > Privacy & security > Microphone has desktop app permissions enabled and device is connected."
                    )
                }

            # Unpack audio
            all_pcm = b"".join(recorded_chunks)
            if stream_format == pyaudio.paFloat32:
                arr_float = np.frombuffer(all_pcm, dtype=np.float32)
                if channels > 1:
                    arr_float = arr_float.reshape(-1, channels).mean(axis=1)
            else:
                arr = np.frombuffer(all_pcm, dtype=np.int16)
                if channels > 1:
                    arr = arr.reshape(-1, channels).mean(axis=1)
                arr_float = arr.astype(np.float32) / 32768.0

            import math
            from scipy.signal import resample_poly
            gcd = math.gcd(rate, 16000)
            audio_16k = resample_poly(arr_float, 16000 // gcd, rate // gcd).astype(np.float32)

            avg_rms = float(np.sqrt(np.mean(audio_16k**2)))
            max_peak = float(np.max(np.abs(audio_16k))) if len(audio_16k) > 0 else 0.0

            if avg_rms < 0.0003:
                return {
                    "success": False,
                    "rms": avg_rms,
                    "peak": max_peak,
                    "device": mic_dev["name"],
                    "message": (
                        f"SILENT: Microphone stream opened on '{mic_dev['name']}', but signal is near zero "
                        f"(RMS: {avg_rms:.5f}, Peak: {max_peak:.4f}). Check hardware mute switch, boost volume in Windows Sound Settings, or speak closer to the mic."
                    )
                }

            trans_text = ""
            if hasattr(self, "transcriber") and self.transcriber:
                if self.transcriber.model is None:
                    self.transcriber.initialize_model()
                if self.transcriber.model:
                    segs, _ = self.transcriber.model.transcribe(audio_16k, beam_size=1, vad_filter=True)
                    trans_text = " ".join(s.text.strip() for s in segs)

            return {
                "success": True,
                "rms": avg_rms,
                "peak": max_peak,
                "device": mic_dev["name"],
                "transcription": trans_text,
                "message": (
                    f"SUCCESS: Captured {len(recorded_chunks)} chunks ({callback_stats['frames']} frames) from '{mic_dev['name']}'. "
                    f"RMS: {avg_rms:.4f}, Peak: {max_peak:.4f}. Transcribed: \"{trans_text}\""
                    if trans_text else
                    f"SUCCESS: Received microphone audio from '{mic_dev['name']}' (RMS: {avg_rms:.4f}, Peak: {max_peak:.4f}), but no clear speech was recognized."
                )
            }
        except Exception as ex:
            return {
                "success": False,
                "rms": 0.0,
                "peak": 0.0,
                "message": f"ERROR initializing microphone: {ex}"
            }
        finally:
            if stream:
                try: stream.close()
                except Exception: pass
            if p:
                try: p.terminate()
                except Exception: pass

    def test_system_loopback(self, duration_sec: float = 3.0, update_fn=None) -> Dict[str, Any]:
        """Runs a 3-second WASAPI Loopback test on the output device with live metrics."""
        import pyaudiowpatch as pyaudio
        p = None
        stream = None
        recorded_chunks = []
        stream_format = pyaudio.paInt16
        callback_stats = {"count": 0, "frames": 0, "peak": 0.0, "max_rms": 0.0}
        try:
            p = pyaudio.PyAudio()
            def_loop = None

            # 1. Configured system output device loopback analogue
            cfg_out = getattr(self.config, "audio_system_device_index", None)
            if cfg_out is not None:
                try:
                    d = p.get_device_info_by_index(cfg_out)
                    if d.get("isLoopbackDevice", False):
                        def_loop = d
                    elif hasattr(p, "get_wasapi_loopback_analogue_by_index"):
                        def_loop = p.get_wasapi_loopback_analogue_by_index(cfg_out)
                except Exception:
                    def_loop = None

            # 2. WASAPI default loopback
            if def_loop is None and hasattr(p, "get_default_wasapi_loopback"):
                try:
                    def_loop = p.get_default_wasapi_loopback()
                except Exception:
                    pass

            # 3. WASAPI default output device analogue
            if def_loop is None and hasattr(p, "get_wasapi_loopback_analogue_by_index"):
                try:
                    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    def_out = wasapi_info.get("defaultOutputDevice")
                    if def_out is not None and def_out >= 0:
                        def_loop = p.get_wasapi_loopback_analogue_by_index(def_out)
                except Exception:
                    pass

            # 4. Fallback search
            if def_loop is None:
                for i in range(p.get_device_count()):
                    d = p.get_device_info_by_index(i)
                    if "[loopback]" in d.get("name", "").lower():
                        def_loop = d
                        break

            if def_loop is None:
                return {
                    "success": False,
                    "rms": 0.0,
                    "peak": 0.0,
                    "message": "FAILED: No WASAPI loopback device found on this system. Check that Windows Audio service is running."
                }

            channels = int(def_loop.get("maxInputChannels", 2))
            rate = int(def_loop.get("defaultSampleRate", 48000))

            def _cb(in_data, frame_count, time_info, status):
                callback_stats["count"] += 1
                callback_stats["frames"] += frame_count
                if in_data:
                    recorded_chunks.append(in_data)
                return (None, pyaudio.paContinue)

            # Format negotiation
            for fmt in (pyaudio.paInt16, pyaudio.paFloat32):
                try:
                    stream = p.open(
                        format=fmt,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=def_loop["index"],
                        stream_callback=_cb,
                        frames_per_buffer=1024
                    )
                    stream_format = fmt
                    break
                except Exception:
                    pass

            if stream is None:
                return {
                    "success": False,
                    "rms": 0.0,
                    "peak": 0.0,
                    "device": def_loop["name"],
                    "message": f"ERROR: Could not open WASAPI loopback stream on '{def_loop['name']}'."
                }

            stream.start_stream()
            start_t = time.time()
            while time.time() - start_t < duration_sec:
                time.sleep(0.08)
                if recorded_chunks and update_fn:
                    last_pcm = recorded_chunks[-1]
                    if stream_format == pyaudio.paFloat32:
                        chunk_arr = np.frombuffer(last_pcm, dtype=np.float32)
                    else:
                        chunk_arr = np.frombuffer(last_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                    rms = float(np.sqrt(np.mean(chunk_arr**2))) if len(chunk_arr) > 0 else 0.0
                    peak = float(np.max(np.abs(chunk_arr))) if len(chunk_arr) > 0 else 0.0
                    callback_stats["peak"] = max(callback_stats["peak"], peak)
                    callback_stats["max_rms"] = max(callback_stats["max_rms"], rms)
                    try:
                        update_fn("call", rms, peak)
                    except TypeError:
                        update_fn("call", rms)

            stream.stop_stream()
            stream.close()
            stream = None

            if not recorded_chunks:
                return {
                    "success": False,
                    "rms": 0.0,
                    "peak": 0.0,
                    "device": def_loop["name"],
                    "message": (
                        f"STREAM IDLE: Loopback stream opened on '{def_loop['name']}', but 0 audio packets were delivered "
                        f"(Callbacks: {callback_stats['count']}).\n"
                        f"Root Cause: In Windows WASAPI, the loopback endpoint only receives audio frames when an application "
                        f"(such as YouTube in Chrome/Edge, Spotify, or a media player) is actively playing audible sound through '{def_loop['name']}'.\n"
                        f"Action: Start playing YouTube audio or speech out loud through '{def_loop['name']}' and click 'Test System Audio' again."
                    )
                }

            all_pcm = b"".join(recorded_chunks)
            if stream_format == pyaudio.paFloat32:
                arr_float = np.frombuffer(all_pcm, dtype=np.float32)
                if channels > 1:
                    arr_float = arr_float.reshape(-1, channels).mean(axis=1)
            else:
                arr = np.frombuffer(all_pcm, dtype=np.int16)
                if channels > 1:
                    arr = arr.reshape(-1, channels).mean(axis=1)
                arr_float = arr.astype(np.float32) / 32768.0

            import math
            from scipy.signal import resample_poly
            gcd = math.gcd(rate, 16000)
            audio_16k = resample_poly(arr_float, 16000 // gcd, rate // gcd).astype(np.float32)

            avg_rms = float(np.sqrt(np.mean(audio_16k**2)))
            max_peak = float(np.max(np.abs(audio_16k))) if len(audio_16k) > 0 else 0.0

            if avg_rms < 0.0003:
                return {
                    "success": True,
                    "rms": avg_rms,
                    "peak": max_peak,
                    "device": def_loop["name"],
                    "message": (
                        f"SILENT LOOPBACK: Captured {len(recorded_chunks)} chunks from '{def_loop['name']}', but audio energy is near zero "
                        f"(RMS: {avg_rms:.5f}, Peak: {max_peak:.4f}). Audio stream is working, but what is playing is silent or volume is very low."
                    )
                }

            trans_text = ""
            if hasattr(self, "transcriber") and self.transcriber:
                if self.transcriber.model is None:
                    self.transcriber.initialize_model()
                if self.transcriber.model:
                    segs, _ = self.transcriber.model.transcribe(audio_16k, beam_size=1, vad_filter=True)
                    trans_text = " ".join(s.text.strip() for s in segs)

            return {
                "success": True,
                "rms": avg_rms,
                "peak": max_peak,
                "device": def_loop["name"],
                "transcription": trans_text,
                "message": (
                    f"SUCCESS: Loopback captured {len(recorded_chunks)} chunks ({callback_stats['frames']} frames) from '{def_loop['name']}'. "
                    f"RMS: {avg_rms:.4f}, Peak: {max_peak:.4f}. Transcribed: \"{trans_text}\""
                    if trans_text else
                    f"SUCCESS: Loopback received audio frames from '{def_loop['name']}' (RMS: {avg_rms:.4f}, Peak: {max_peak:.4f}), but no clear speech was recognized."
                )
            }
        except Exception as ex:
            return {
                "success": False,
                "rms": 0.0,
                "peak": 0.0,
                "message": f"ERROR opening loopback stream: {ex}"
            }
        finally:
            if stream:
                try: stream.close()
                except Exception: pass
            if p:
                try: p.terminate()
                except Exception: pass

    def test_transcription_engine(self) -> Dict[str, Any]:
        """Tests local Whisper model using verified local speech audio."""
        if not hasattr(self, "transcriber") or not self.transcriber:
            return {"success": False, "message": "LiveTranscriber instance not initialized."}

        t0 = time.time()
        if self.transcriber.model is None:
            ok, msg = self.transcriber.initialize_model()
            if not ok:
                return {"success": False, "message": f"Failed to initialize model: {msg}"}

        # Portably resolve test audio fixture across source and packaged runtimes
        cand_fixtures = [
            Path(__file__).resolve().parent / "fixtures" / "test_speech.wav",
            Path(getattr(sys, "_MEIPASS", "")) / "ghostline" / "fixtures" / "test_speech.wav",
            Path(sys.executable).resolve().parent / "ghostline" / "fixtures" / "test_speech.wav",
            Path(sys.executable).resolve().parent / "_internal" / "ghostline" / "fixtures" / "test_speech.wav",
            get_app_dir() / "test_speech.wav"
        ]
        wav_path = None
        for p in cand_fixtures:
            if p and p.exists():
                wav_path = str(p)
                break

        if not wav_path:
            app_wav = get_app_dir() / "test_speech.wav"
            wav_path = str(app_wav)
            if not os.path.exists(wav_path):
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    filestream = win32com.client.Dispatch("SAPI.SpFileStream")
                    filestream.Open(wav_path, 3, False)
                    speaker.AudioOutputStream = filestream
                    speaker.Speak("Hello, this is a live audio test for Ghostline transcription.")
                    filestream.Close()
                except Exception as e:
                    return {"success": False, "message": f"Could not create speech test fixture: {e}"}

        try:
            import wave
            with wave.open(wav_path, "rb") as wf:
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)

            arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if framerate != 16000:
                import math
                from scipy.signal import resample_poly
                gcd = math.gcd(framerate, 16000)
                audio_16k = resample_poly(arr, 16000 // gcd, framerate // gcd).astype(np.float32)
            else:
                audio_16k = arr

            segments, info = self.transcriber.model.transcribe(
                audio_16k,
                beam_size=1,
                temperature=0.0,
                vad_filter=True
            )
            text = " ".join(s.text.strip() for s in segments)
            elapsed = time.time() - t0

            return {
                "success": bool(text),
                "model": self.transcriber.model_name,
                "device": self.transcriber.model_device,
                "elapsed_sec": elapsed,
                "language": info.language if info else "en",
                "text": text,
                "message": f"SUCCESS: Model '{self.transcriber.model_name}' ({self.transcriber.model_device.upper()}) transcribed in {elapsed:.2f}s: \"{text}\""
            }
        except Exception as ex:
            return {
                "success": False,
                "message": f"Transcription engine test failed: {ex}"
            }


    def start_audio_capture(self):
        logging.info("[Audio] Starting live audio capture and transcription...")
        if hasattr(self, "audio_capture"):
            self.audio_capture.start()
        if hasattr(self, "transcriber"):
            self.transcriber.start()
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_status.emit(True, False)
        else:
            if hasattr(self, "hud") and self.hud:
                self.hud.update_audio_status(is_capturing=True, is_paused=False)
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_capture_state(True)
                self.audio_panel.show_panel()

    def stop_audio_capture(self):
        logging.info("[Audio] Stopping live audio capture...")
        if hasattr(self, "audio_capture"):
            self.audio_capture.stop()
        if hasattr(self, "transcriber"):
            self.transcriber.stop()
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_status.emit(False, False)
        else:
            if hasattr(self, "hud") and self.hud:
                self.hud.update_audio_status(is_capturing=False, is_paused=False)
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_capture_state(False)

    def toggle_audio_capture(self):
        if hasattr(self, "audio_capture") and self.audio_capture.is_capturing:
            self.stop_audio_capture()
        else:
            self.start_audio_capture()

    def toggle_audio_pause(self) -> bool:
        if not hasattr(self, "audio_capture"):
            return False
        paused = self.audio_capture.toggle_pause()
        if hasattr(self, "transcriber"):
            self.transcriber.is_paused = paused
        is_capturing = getattr(self.audio_capture, "is_capturing", False)
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_status.emit(is_capturing, paused)
        else:
            if hasattr(self, "hud") and self.hud:
                self.hud.update_audio_status(is_capturing=is_capturing, is_paused=paused)
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_pause_state(paused)
        return paused

    def toggle_audio_panel(self):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.toggle_visibility()

    def set_call_audio_enabled(self, enabled: bool):
        if hasattr(self, "audio_capture"):
            self.audio_capture.system_enabled = enabled
        self.config.audio_source_system = enabled
        save_config(self.config)

    def set_mic_audio_enabled(self, enabled: bool):
        if hasattr(self, "audio_capture"):
            self.audio_capture.mic_enabled = enabled
        self.config.audio_source_mic = enabled
        save_config(self.config)

    def ask_audio_custom(self, query: str):
        if hasattr(self, "audio_assistant") and self.audio_assistant:
            self.audio_assistant.ask(query)

    def clear_audio_transcript(self):
        if hasattr(self, "transcriber"):
            self.transcriber.clear()
        if hasattr(self, "audio_assistant"):
            self.audio_assistant.clear_context()

    def export_audio_transcript(self, path: str):
        if hasattr(self, "transcriber"):
            self.transcriber.export_transcript(path)

    def on_audio_panel_close(self):
        logging.info("[AudioPanel] Panel hidden by user.")


    def start(self):
        config_path = get_config_path()
        config_exists = config_path.exists()
        caps_enabled = getattr(self.config, "caps_lock_indicator", False)

        print("=" * 60)
        print("  Ghostline: On-Device Question Recognition & Live Audio Assistant")
        print("=" * 60)
        print(f"[*] Version: {__version__}")
        print(f"[*] Process: PID={os.getpid()}, Executable={sys.executable}")
        print(f"[*] Config File: {config_path} (Exists: {config_exists})")
        print(f"[*] Caps Lock Indicator: {'ENABLED' if caps_enabled else 'DISABLED'}")
        print(f"[*] Indicator Mode: {self.config.indicator_mode}")
        print(f"[*] Local Model: {self.config.model_name}")
        print(f"[*] Ollama Endpoint: {self.config.ollama_url}")
        print(f"[*] Trigger Hotkey: {self.config.hotkey}")
        print(f"[*] Hover-to-Answer: {'ENABLED' if getattr(self.config, 'hover_to_answer_enabled', False) else 'DISABLED'}")

        logging.info("Starting runtime subsystems (PID=%d, Hotkey=%s, Model=%s)...",
                     os.getpid(), self.config.hotkey, self.config.model_name)

        # 1. Start Hotkey Listener & Single-Instance Sink immediately
        self.hotkey_thread = threading.Thread(target=self._hotkey_listener_loop, daemon=True)
        self.hotkey_thread.start()

        # 2. Start Tray Indicator immediately
        self.tray.start()

        # 3. Start Automatic Hover-to-Answer Engine
        if hasattr(self, "hover_detector"):
            self.hover_detector.start()

        # 4. Check Ollama daemon asynchronously so startup is instant (<20ms)
        def _async_check_ollama():
            try:
                if not self.ollama.is_available():
                    logging.warning("Ollama daemon is not responding at %s", self.config.ollama_url)
                    print(f"[!] Note: Ollama is not responding at {self.config.ollama_url}. Please ensure Ollama is running.")
                else:
                    logging.info("Local Ollama service confirmed reachable at %s", self.config.ollama_url)
            except Exception as e:
                logging.warning("Async Ollama check warning: %s", e)

        threading.Thread(target=_async_check_ollama, daemon=True).start()

        # 5. Run PyQt6 Main GUI Event Loop on main thread
        logging.info("Ghostline application starting PyQt6 main GUI loop.")
        try:
            if getattr(self.config, "start_minimized", False):
                self.main_window.hide_to_tray()
            else:
                self.main_window.show_window()
            sys.exit(self.qapp.exec())
        except KeyboardInterrupt:
            self.shutdown()
        except Exception as e:
            logging.exception(f"Unhandled exception in UI mainloop: {e}")
            self.shutdown()

    def trigger_solve(self, is_auto_hover: bool = False):
        """Called when hotkey is pressed, hover occurs, or triggered via tray or IPC."""
        logging.info("[Diagnostic %s] trigger_solve invoked (PID=%d, Thread=%s, is_solving=%s, is_auto_hover=%s)",
                     time.strftime("%H:%M:%S"), os.getpid(), threading.get_ident(), self.is_solving, is_auto_hover)
        if self.is_solving:
            logging.info("[Diagnostic %s] Solve already in progress; ignoring overlapping trigger.", time.strftime("%H:%M:%S"))
            return
        
        thread = threading.Thread(target=self._solve_worker, args=(is_auto_hover,), daemon=True)
        thread.start()

    def _solve_worker(self, is_auto_hover: bool = False):
        self.is_solving = True
        t_start = time.time()
        tracer = PipelineTracer()
        tracer.start_trace()
        logging.info("[Diagnostic %s] _solve_worker started (PID=%d, Thread=%s, is_auto_hover=%s)",
                     time.strftime("%H:%M:%S"), os.getpid(), threading.get_ident(), is_auto_hover)
        solve_id = self.hud.start_solve() if hasattr(self.hud, "start_solve") else 0
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_solve_started.emit()
        else:
            if show_hud:
                self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                self.hud.show_overlay()
                self.hud.set_state("capturing", solve_id=solve_id)
            if hasattr(self, "main_window") and self.main_window:
                self.main_window.on_solve_started()
            if hasattr(self, "tray") and self.tray:
                self.tray.update_badge(
                    badge="",
                    status="thinking",
                    tooltip="Ghostline — Thinking…"
                )

        def on_stream(token: str):
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_stream_token.emit(token, solve_id)
            elif show_hud and hasattr(self, "hud") and self.hud:
                self.hud.append_stream_token(token, solve_id=solve_id)

        def on_progress(stage: str):
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_hud_state.emit(stage, None, solve_id)
            elif show_hud and hasattr(self, "hud") and self.hud:
                self.hud.set_state(stage, solve_id=solve_id)

        try:
            dup_check = self.hover_detector.question_cache.contains if (is_auto_hover and hasattr(self, "hover_detector")) else None
            res = self.pipeline.process_from_cursor(
                capture_width=self.config.capture_width,
                capture_height=self.config.capture_height,
                capture_mode=getattr(self.config, "capture_mode", "full_screen"),
                stream_callback=on_stream,
                progress_callback=on_progress,
                is_duplicate_fn=dup_check,
                tracer=tracer
            )

            # Update cache and notify hover detector of completed solve
            if hasattr(self, "hover_detector"):
                self.hover_detector.notify_solve_completed()
                if res.parsed_question and res.parsed_question.question_text:
                    self.hover_detector.question_cache.add(res.parsed_question.question_text)

            # Dispatch result via bridge to main GUI thread
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_solve_completed.emit(res)
            else:
                if hasattr(self, "main_window") and self.main_window:
                    self.main_window.on_solve_completed(res)
                presentation = build_answer_presentation(res.parsed_question, res.answer_result)
                badge = presentation.badge
                is_mcq = (presentation.question_type == TYPE_MCQ)
                is_valid = presentation.is_validated
                if not is_valid or presentation.question_type in [TYPE_UNCERTAIN, TYPE_ERROR]:
                    if show_hud and hasattr(self, "hud") and self.hud:
                        self.hud.set_state("error", presentation=presentation, solve_id=solve_id)
                    if hasattr(self, "tray") and self.tray:
                        self.tray.update_badge(
                            badge="?",
                            status="error",
                            is_validated=False,
                            is_multiple_choice=is_mcq,
                            tooltip=f"Ghostline — {presentation.headline}"
                        )
                    if hasattr(self, "caps_indicator") and self.caps_indicator:
                        self.caps_indicator.pulse("?")
                else:
                    if show_hud and hasattr(self, "hud") and self.hud:
                        self.hud.set_state("answer", presentation=presentation, solve_id=solve_id)
                    if hasattr(self, "tray") and self.tray:
                        self.tray.update_badge(
                            badge=badge,
                            status="normal",
                            is_validated=True,
                            is_multiple_choice=is_mcq,
                            tooltip=f"Ghostline — {presentation.headline}"
                        )
                    if hasattr(self, "caps_indicator") and self.caps_indicator:
                        self.caps_indicator.pulse(badge)

            # Save local history with complete diagnostics
            if self.config.save_history_locally:
                self._save_history_entry(res)

        except DuplicateQuestionError as dup:
            logging.info("[Diagnostic %s] Duplicate question ignored in auto-hover: %s", time.strftime("%H:%M:%S"), dup)
            if hasattr(self, "hover_detector"):
                self.hover_detector.notify_solve_completed()

        except Exception as ex:
            if hasattr(self, "hover_detector"):
                self.hover_detector.notify_solve_completed()
            err_msg = str(ex)
            logging.exception(f"Error during solve worker execution: {err_msg}")
            raw_text = getattr(ex, "raw_text", "")
            parsed_q = getattr(ex, "parsed_question", None)
            
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_solve_error.emit(err_msg, raw_text, parsed_q)
            else:
                if hasattr(self.main_window, "on_solve_error"):
                    try:
                        self.main_window.on_solve_error(err_msg, raw_text=raw_text)
                    except TypeError:
                        self.main_window.on_solve_error(err_msg)
                
                is_extraction_uncertain = ("Unreliable question extraction" in err_msg or "does not contain question indicators" in err_msg)
                badge_char = "?" if is_extraction_uncertain else "!"
                
                err_ans = AnswerResult(
                    answer_option=badge_char,
                    proposed_option=badge_char,
                    validation_status="uncertain" if is_extraction_uncertain else "error",
                    is_validated=False,
                    error=err_msg,
                    tray_badge=badge_char
                )
                err_presentation = build_answer_presentation(parsed_q, err_ans)
                if show_hud and hasattr(self, "hud") and self.hud:
                    self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                    self.hud.set_state("error", presentation=err_presentation, solve_id=solve_id)
                if hasattr(self, "tray") and self.tray:
                    self.tray.update_badge(
                        badge=badge_char,
                        status="error",
                        tooltip=f"Ghostline — {err_presentation.headline}"
                    )
                if hasattr(self, "caps_indicator") and self.caps_indicator:
                    self.caps_indicator.pulse(badge_char)

        finally:
            self.is_solving = False
            logging.info("\n" + tracer.get_summary_report())
            logging.info("[Diagnostic %s] Solve worker finished. is_solving reset to False.", time.strftime("%H:%M:%S"))

    def _save_history_entry(self, res):
        try:
            history_file = get_app_dir() / "history.jsonl"
            entry = {
                "timestamp": time.time(),
                "cursor_pos": res.cursor_pos,
                "question": res.parsed_question.question_text,
                "options": res.parsed_question.options,
                "proposed_answer": res.answer_result.proposed_option,
                "answer": res.answer_result.answer_option,
                "is_validated": res.answer_result.is_validated,
                "confidence": res.answer_result.confidence,
                "explanation": res.answer_result.explanation,
                "code_snippet": getattr(res.answer_result, "code_snippet", None),
                "code_language": getattr(res.answer_result, "code_language", ""),
                "question_type": getattr(res.answer_result, "question_type", "mcq"),
                "direct_answer": getattr(res.answer_result, "direct_answer", ""),
                "timing_ms": {
                    "capture": res.capture_time_ms,
                    "ocr": res.ocr_time_ms,
                    "llm": res.llm_time_ms,
                    "total": res.total_time_ms
                }
            }
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


    def _hotkey_listener_loop(self):
        """Win32 RegisterHotKey loop and single-instance activation message sink."""
        HOTKEY_SOLVE = 1001         # Configurable (default Alt + /)
        HOTKEY_AUDIO_ASSIST = 1002  # Alt + A (Toggle Live Audio Assistant Panel)
        HOTKEY_AUDIO_TOGGLE = 1003  # Alt + L (Toggle Live Audio Listening/Capture)
        HOTKEY_HUD_TOGGLE = 1004    # Alt + T (Toggle Floating HUD Overlay)
        HOTKEY_AUDIO_ASK = 1005     # Alt + Q (Ask Ghostline on Call / Audio Assistant)

        MOD_NOREPEAT = 0x4000
        solve_mod, solve_vk = parse_hotkey_string(getattr(self.config, "hotkey", "Alt + /"))

        self.hotkey_thread_id = kernel32.GetCurrentThreadId()

        # Create hidden window for message pump and single-instance activation
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = SINGLE_INSTANCE_SINK_CLASS

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_GHOSTLINE_WAKEUP:
                logging.info("Received WakeUp message in sink window procedure. Restoring main window.")
                if hasattr(self, "bridge") and self.bridge:
                    self.bridge.sig_show_main_window.emit()
                elif hasattr(self, "main_window") and self.main_window:
                    self.main_window.show_window()
                return 0
            elif msg == WM_GHOSTLINE_SOLVE:
                logging.info("Received Solve message in sink window procedure. Triggering solve.")
                if hasattr(self, "bridge") and self.bridge:
                    self.bridge.sig_trigger_solve.emit(False)
                else:
                    self.trigger_solve()
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc.lpfnWndProc = wndproc

        try:
            win32gui.RegisterClass(wc)
        except pywintypes.error as e:
            # 1410: Class already exists across re-runs in same process
            if e.winerror != 1410:
                logging.warning(f"Sink window class registration note: {e}")

        hwnd = None
        try:
            hwnd = win32gui.CreateWindow(
                wc.lpszClassName, "GhostlineSinkWindow", 0, 0, 0, 0, 0, 0, 0, 0, None
            )
            self.hotkey_hwnd = hwnd

            # Enable UIPI message filter so non-elevated or background instances can signal
            try:
                for msg_id in (WM_GHOSTLINE_WAKEUP, WM_GHOSTLINE_SOLVE):
                    user32.ChangeWindowMessageFilter(msg_id, 1)  # MSGFLT_ADD
            except Exception:
                pass

            # Register All Global Shortcuts
            hotkeys = [
                (HOTKEY_SOLVE, solve_mod, solve_vk, f"Screen Solve ({getattr(self.config, 'hotkey', 'Alt + /')})"),
                (HOTKEY_AUDIO_ASSIST, win32con.MOD_ALT, ord('A'), "Live Audio Assistant (Alt + A)"),
                (HOTKEY_AUDIO_TOGGLE, win32con.MOD_ALT, ord('L'), "Live Audio Toggle (Alt + L)"),
                (HOTKEY_HUD_TOGGLE, win32con.MOD_ALT, ord('T'), "HUD Overlay Toggle (Alt + T)"),
                (HOTKEY_AUDIO_ASK, win32con.MOD_ALT, ord('Q'), "Audio Quick Ask (Alt + Q)"),
            ]

            registered_ids = []
            for hk_id, mod, vk, desc in hotkeys:
                if not user32.RegisterHotKey(hwnd, hk_id, mod | MOD_NOREPEAT, vk):
                    err = ctypes.GetLastError()
                    if err == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
                        logging.warning("[Hotkey] %s conflict: Win32 Error 1409 (already registered by another application).", desc)
                    else:
                        logging.warning("[Hotkey] Failed to register %s: Win32 Error %d.", desc, err)
                else:
                    registered_ids.append(hk_id)
                    logging.info("[Hotkey] Registered: %s", desc)

            self.registered_hotkey_ids = registered_ids
            self.hotkey_registered = (HOTKEY_SOLVE in registered_ids)

            while self.is_running:
                ret, msg = win32gui.GetMessage(0, 0, 0)
                if ret == 0:  # WM_QUIT
                    break
                msg_hwnd, msg_id, wparam, lparam, msg_time, pt = msg
                if msg_id == win32con.WM_HOTKEY:
                    if wparam == HOTKEY_SOLVE:
                        logging.info("[Diagnostic %s] WM_HOTKEY Solve (%s) received.", time.strftime("%H:%M:%S"), getattr(self.config, 'hotkey', 'Alt + /'))
                        if hasattr(self, "bridge") and self.bridge:
                            self.bridge.sig_trigger_solve.emit(False)
                        else:
                            self.trigger_solve()
                    elif wparam == HOTKEY_AUDIO_ASSIST:
                        logging.info("[Diagnostic %s] WM_HOTKEY Alt+A (Audio Assist) received.", time.strftime("%H:%M:%S"))
                        if hasattr(self, "bridge") and self.bridge:
                            self.bridge.sig_toggle_audio_panel.emit()
                        else:
                            self.toggle_audio_panel()
                    elif wparam == HOTKEY_AUDIO_TOGGLE:
                        logging.info("[Diagnostic %s] WM_HOTKEY Alt+L (Audio Toggle) received.", time.strftime("%H:%M:%S"))
                        if hasattr(self, "bridge") and self.bridge:
                            self.bridge.sig_toggle_audio_capture.emit()
                        else:
                            self.toggle_audio_capture()
                    elif wparam == HOTKEY_HUD_TOGGLE:
                        logging.info("[Diagnostic %s] WM_HOTKEY Alt+T (HUD Toggle) received.", time.strftime("%H:%M:%S"))
                        if hasattr(self, "bridge") and self.bridge:
                            self.bridge.sig_toggle_hud.emit()
                        else:
                            self.toggle_hud()
                    elif wparam == HOTKEY_AUDIO_ASK:
                        logging.info("[Diagnostic %s] WM_HOTKEY Alt+Q (Audio Ask) received.", time.strftime("%H:%M:%S"))
                        if hasattr(self, "bridge") and self.bridge:
                            self.bridge.sig_toggle_audio_panel.emit()
                        else:
                            self.toggle_audio_panel()
                elif msg_id == WM_GHOSTLINE_WAKEUP:
                    logging.info("[Diagnostic %s] Received WakeUp message in hotkey loop.", time.strftime("%H:%M:%S"))
                    if hasattr(self, "bridge") and self.bridge:
                        self.bridge.sig_show_main_window.emit()
                    elif hasattr(self, "main_window") and self.main_window:
                        self.main_window.show_window()
                elif msg_id == WM_GHOSTLINE_SOLVE:
                    logging.info("[Diagnostic %s] Received Solve message in hotkey loop.", time.strftime("%H:%M:%S"))
                    if hasattr(self, "bridge") and self.bridge:
                        self.bridge.sig_trigger_solve.emit(False)
                    else:
                        self.trigger_solve()
                win32gui.TranslateMessage(msg)
                win32gui.DispatchMessage(msg)
        except Exception as e:
            logging.exception(f"Hotkey/Sink message loop error: {e}")
        finally:
            if hwnd:
                for hk_id in (1001, 1002, 1003, 1004, 1005):
                    try:
                        user32.UnregisterHotKey(hwnd, hk_id)
                    except Exception:
                        pass
                self.hotkey_registered = False
                try:
                    win32gui.DestroyWindow(hwnd)
                except Exception:
                    pass
            self.hotkey_hwnd = None

    def on_hud_close(self):
        self.hud.set_state("ready")
        self.tray.update_badge("", "ready", tooltip="Ghostline: Ready (Alt+/)")

    def shutdown(self):
        logging.info("Shutting down Ghostline application...")
        self.is_running = False
        self.stop_audio_capture()
        if hasattr(self, "audio_panel"):
            try:
                self.audio_panel.destroy()
            except Exception:
                pass
        if hasattr(self, "caps_indicator"):
            try:
                self.caps_indicator.restore_safety_state()
            except Exception:
                pass
        if self.hotkey_hwnd:
            for hk_id in (1001, 1002, 1003, 1004, 1005):
                try:
                    user32.UnregisterHotKey(self.hotkey_hwnd, hk_id)
                except Exception:
                    pass
            self.hotkey_registered = False
        if self.hotkey_thread_id:
            try:
                user32.PostThreadMessageW(self.hotkey_thread_id, win32con.WM_QUIT, 0, 0)
            except Exception:
                pass
        if hasattr(self, "hover_detector"):
            try:
                self.hover_detector.stop()
            except Exception:
                pass
        if hasattr(self, "tray"):
            try:
                self.tray.stop()
            except Exception:
                pass
        if hasattr(self, "hud"):
            try:
                self.hud.destroy()
            except Exception:
                pass
        if hasattr(self, "main_window"):
            try:
                self.main_window.destroy()
            except Exception:
                pass
        if hasattr(self, "qapp") and self.qapp:
            try:
                self.qapp.quit()
            except Exception:
                pass
        if hasattr(self, "sink_hwnd") and self.sink_hwnd:
            try:
                win32gui.DestroyWindow(self.sink_hwnd)
            except Exception:
                pass
            self.sink_hwnd = None
        if hasattr(self, "_mutex") and self._mutex:
            try:
                win32api.CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None
        sys.exit(0)

def main():
    setup_file_logging()
    logging.info("=" * 65)
    logging.info("Starting Ghostline v%s (PID=%d)", __version__, os.getpid())
    logging.info("Python Executable: %s", sys.executable)
    logging.info("Working Directory: %s", os.getcwd())

    # Headless CLI Diagnostics & Smoke Test Check
    if any(arg in sys.argv for arg in ["--diagnostics", "--smoke-test", "-d"]):
        cfg = load_config()
        from ghostline.core.ocr_engine import get_win_ocr_binary_path
        ocr_path = get_win_ocr_binary_path()
        cand_fixtures = [
            Path(__file__).resolve().parent / "fixtures" / "test_speech.wav",
            Path(getattr(sys, "_MEIPASS", "")) / "ghostline" / "fixtures" / "test_speech.wav",
            Path(sys.executable).resolve().parent / "ghostline" / "fixtures" / "test_speech.wav",
            Path(sys.executable).resolve().parent / "_internal" / "ghostline" / "fixtures" / "test_speech.wav",
            get_app_dir() / "test_speech.wav"
        ]
        fixture_found = any(p and p.exists() for p in cand_fixtures)
        from ghostline.core.llm_client import OllamaClient
        client = OllamaClient(base_url=cfg.ollama_url, default_model=cfg.model_name)
        ollama_ok, models = client.check_health()
        res = {
            "status": "ok",
            "app": "Ghostline",
            "version": __version__,
            "frozen": getattr(sys, "frozen", False),
            "app_dir": str(get_app_dir()),
            "config_path": str(get_config_path()),
            "win_ocr_path": str(ocr_path),
            "win_ocr_exists": ocr_path.exists(),
            "fixture_exists": fixture_found,
            "ollama_running": ollama_ok,
            "models_available": models,
            "target_model_installed": any(cfg.model_name in m for m in models)
        }
        print(json.dumps(res, indent=2))
        sys.exit(0 if ocr_path.exists() else 1)

    # 1. Single-Instance Check BEFORE any GUI creation
    mutex_name = "Local\\GhostlineSingleInstanceMutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    last_err = win32api.GetLastError()
    if last_err == winerror.ERROR_ALREADY_EXISTS:
        is_solve_trigger = any(arg in sys.argv for arg in ["--solve", "-s", "/solve"])
        target_msg = WM_GHOSTLINE_SOLVE if is_solve_trigger else WM_GHOSTLINE_WAKEUP
        msg_name = "WM_GHOSTLINE_SOLVE" if is_solve_trigger else "WM_GHOSTLINE_WAKEUP"
        logging.info("[Diagnostic %s] Existing Ghostline instance detected via Mutex (PID=%d). Sending %s to primary instance.",
                     time.strftime("%H:%M:%S"), os.getpid(), msg_name)
        sink_hwnd = win32gui.FindWindow(SINGLE_INSTANCE_SINK_CLASS, None)
        if sink_hwnd:
            logging.info("[Diagnostic %s] Found active sink window (HWND %s). Posting %s.",
                         time.strftime("%H:%M:%S"), sink_hwnd, msg_name)
            win32gui.PostMessage(sink_hwnd, target_msg, 0, 0)
            if not is_solve_trigger:
                try:
                    win32gui.SetForegroundWindow(sink_hwnd)
                except Exception:
                    pass
            print(f"[*] Activated existing Ghostline instance (sent {msg_name}). Exiting secondary process (PID={os.getpid()}).")
            sys.exit(0)
        else:
            logging.warning("[Diagnostic %s] Mutex was held but sink window not found (possible orphaned process). Attempting broadcast %s.",
                            time.strftime("%H:%M:%S"), msg_name)
            win32gui.PostMessage(win32con.HWND_BROADCAST, target_msg, 0, 0)
            sys.exit(0)

    # 2. Main Application Lifecycle
    try:
        app = GhostlineApp(mutex=mutex)
        app.start()
    except Exception as ex:
        logging.exception("Fatal unhandled exception in Ghostline startup: %s", ex)
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Ghostline encountered a critical startup error:\n\n{ex}\n\nPlease check the diagnostic log at:\n{get_app_dir() / 'ghostline.log'}",
                "Ghostline Startup Error",
                0x10  # MB_ICONERROR
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()

