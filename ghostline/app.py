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
import uuid
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

from ghostline import (
    __version__,
    BUILD_ID,
    GIT_COMMIT,
    GIT_COMMIT_SHORT,
    BUILD_TIMESTAMP,
    BUILD_IDENTIFIER,
    get_running_mode,
    get_build_summary
)

# Register custom Win32 messages for single-instance activation, IPC solve triggers, and runtime hotkey reload
WM_GHOSTLINE_WAKEUP = win32gui.RegisterWindowMessage("GhostlineWakeUpMsg")
WM_GHOSTLINE_SOLVE = win32gui.RegisterWindowMessage("GhostlineSolveMsg")
WM_GHOSTLINE_RELOAD_HOTKEYS = win32gui.RegisterWindowMessage("GhostlineReloadHotkeysMsg")
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
    sig_open_settings = pyqtSignal(str)        # screen_id
    sig_shutdown = pyqtSignal()

    # Screen Solve Lifecycle
    sig_solve_started = pyqtSignal()
    sig_solve_completed = pyqtSignal(object)   # res (PipelineExecutionResult)
    sig_solve_error = pyqtSignal(str, str, object)  # err_msg, raw_text, parsed_q
    sig_stream_token = pyqtSignal(str, int)    # token, solve_id
    sig_hud_state = pyqtSignal(str, object, int) # stage, presentation, solve_id

    # HUD Chat End-to-End Pipeline
    sig_hud_chat_loading = pyqtSignal(str)     # query
    sig_hud_chat_response = pyqtSignal(object, int) # presentation, chat_id
    sig_hud_chat_error = pyqtSignal(str, int)  # error_msg, chat_id

    # Audio & Transcription Streaming
    sig_audio_level = pyqtSignal(str, float, float) # source, rms, peak
    sig_audio_partial = pyqtSignal(str, str)        # text, source
    sig_audio_segment = pyqtSignal(object)          # segment (TranscriptSegment)
    sig_audio_thinking = pyqtSignal([str], [str, str])            # question [, entry_id]
    sig_audio_answer = pyqtSignal([str, str, object], [str, str, object, str]) # question, answer, code [, entry_id]
    sig_audio_error = pyqtSignal(str)               # err
    sig_audio_status = pyqtSignal(bool, bool)       # is_capturing, is_paused


VK_MAP = {
    "/": 0xBF, "?": 0xBF, "\\": 0xDC, "|": 0xDC,
    "[": 0xDB, "{": 0xDB, "]": 0xDD, "}": 0xDD,
    ";": 0xBA, ":": 0xBA, "'": 0xDE, "\"": 0xDE,
    ",": 0xBC, "<": 0xBC, ".": 0xBE, ">": 0xBE,
    "-": 0xBD, "_": 0xBD, "=": 0xBB, "+": 0xBB,
    "`": 0xC0, "~": 0xC0,
    "space": win32con.VK_SPACE,
    "tab": win32con.VK_TAB,
    "return": win32con.VK_RETURN, "enter": win32con.VK_RETURN,
    "escape": win32con.VK_ESCAPE, "esc": win32con.VK_ESCAPE,
    "backspace": win32con.VK_BACK, "back": win32con.VK_BACK,
    "insert": win32con.VK_INSERT, "delete": win32con.VK_DELETE, "del": win32con.VK_DELETE,
    "home": win32con.VK_HOME, "end": win32con.VK_END,
    "pageup": win32con.VK_PRIOR, "pagedown": win32con.VK_NEXT,
    "up": win32con.VK_UP, "down": win32con.VK_DOWN, "left": win32con.VK_LEFT, "right": win32con.VK_RIGHT
}


def parse_hotkey_string(hotkey_str: str) -> Tuple[int, int]:
    """Parses a hotkey string like 'alt+/', 'ctrl+alt+a', 'win+shift+f1' into (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in hotkey_str.replace("+", " ").split() if p.strip()]
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
        elif p in VK_MAP:
            vk = VK_MAP[p]
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


def validate_hotkey_string(hotkey_str: str) -> Tuple[bool, str, int, int, str]:
    """Validates user-entered hotkey string. Returns (is_valid, normalized_str, mod, vk, error_msg)."""
    clean_str = hotkey_str.strip()
    if not clean_str:
        return False, "", 0, 0, "Shortcut cannot be empty."

    parts = [p.strip().lower() for p in clean_str.replace("+", " ").split() if p.strip()]
    mod = 0
    vk = 0
    key_name = ""
    mod_names = []

    for p in parts:
        if p in ("alt", "menu"):
            if "Alt" not in mod_names:
                mod |= win32con.MOD_ALT
                mod_names.append("Alt")
        elif p in ("ctrl", "control"):
            if "Ctrl" not in mod_names:
                mod |= win32con.MOD_CONTROL
                mod_names.append("Ctrl")
        elif p in ("shift",):
            if "Shift" not in mod_names:
                mod |= win32con.MOD_SHIFT
                mod_names.append("Shift")
        elif p in ("win", "windows"):
            if "Win" not in mod_names:
                mod |= win32con.MOD_WIN
                mod_names.append("Win")
        elif p in VK_MAP:
            vk = VK_MAP[p]
            key_name = p.upper() if len(p) <= 2 else p.capitalize()
        elif len(p) == 1 and p.isalnum():
            vk = ord(p.upper())
            key_name = p.upper()
        elif p.startswith("f") and p[1:].isdigit():
            fn = int(p[1:])
            if 1 <= fn <= 24:
                vk = win32con.VK_F1 + (fn - 1)
                key_name = f"F{fn}"

    if not mod_names:
        return False, "", 0, 0, "Shortcut must include at least one modifier key (Ctrl, Alt, Shift, or Win)."
    if vk == 0 or not key_name:
        return False, "", 0, 0, "Shortcut must specify a valid key (e.g. /, A-Z, 0-9, F1-F12, Space)."

    normalized = " + ".join(mod_names + [key_name])
    return True, normalized, mod, vk, ""


def setup_file_logging():
    if sys.platform == "win32":
        try:
            # If launched from cmd or PowerShell, attach to parent console so prints and logs appear
            if ctypes.windll.kernel32.AttachConsole(-1):
                if sys.stdout is None or not hasattr(sys.stdout, "write"):
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                if sys.stderr is None or not hasattr(sys.stderr, "write"):
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8")
        except Exception:
            pass
    try:
        log_file = get_app_dir() / "ghostline.log"
        handlers = [
            logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
        ]
        if sys.stdout is not None and hasattr(sys.stdout, "write"):
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

        # Set Windows AppUserModelID so Windows taskbar groups and shows the custom icon properly
        if sys.platform == "win32":
            try:
                myappid = "Ghostline.AI.Desktop.v1"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                logging.warning("AppUserModelID note: %s", e)

        # Initialize PyQt6 QApplication first on main thread
        self.qapp = QApplication.instance()
        if self.qapp is None:
            self.qapp = QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
        self.qapp.setStyleSheet(QT_MAIN_STYLESHEET)

        self._cached_excluded_rects: List[Tuple[int, int, int, int]] = []
        self._audio_toggle_lock = threading.Lock()

        # Initialize Centralized Thread-Safe Event Dispatcher Bridge
        self.bridge = QtEventBridge()
        self._connect_bridge_signals()
        self._chat_seq = 0

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
            on_end=self.on_hud_end,
            on_toggle_pause=self.toggle_hover_pause,
            on_position_changed=self.on_hud_position_changed,
            on_retry=lambda: self.trigger_solve(is_auto_hover=False),
            opacity=getattr(self.config, "hud_opacity", 0.86),
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
            on_trigger=lambda: self.bridge.sig_trigger_solve.emit(False) if hasattr(self, "bridge") else self.trigger_solve(),
            on_open_main=lambda: self.bridge.sig_show_main_window.emit() if hasattr(self, "bridge") else self.main_window.show_window(),
            on_toggle_hud=lambda: self.bridge.sig_toggle_hud.emit() if hasattr(self, "bridge") else self.toggle_hud(),
            on_open_settings=lambda: self.bridge.sig_open_settings.emit("settings") if hasattr(self, "bridge") else self.open_settings(),
            on_exit=self.shutdown,
            on_toggle_pause=self.toggle_hover_pause,
            on_toggle_audio=lambda: self.bridge.sig_toggle_audio_capture.emit() if hasattr(self, "bridge") else self.toggle_audio_capture(),
            on_toggle_audio_panel=lambda: self.bridge.sig_toggle_audio_panel.emit() if hasattr(self, "bridge") else self.toggle_audio_panel()
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
        self.bridge.sig_open_settings.connect(self._main_thread_open_settings)
        self.bridge.sig_shutdown.connect(self._main_thread_shutdown)
        self.bridge.sig_solve_started.connect(self._main_thread_solve_started)
        self.bridge.sig_solve_completed.connect(self._main_thread_solve_completed)
        self.bridge.sig_solve_error.connect(self._main_thread_solve_error)
        self.bridge.sig_stream_token.connect(self._main_thread_stream_token)
        self.bridge.sig_hud_state.connect(self._main_thread_hud_state)
        self.bridge.sig_hud_chat_loading.connect(self._main_thread_hud_chat_loading)
        self.bridge.sig_hud_chat_response.connect(self._main_thread_hud_chat_response)
        self.bridge.sig_hud_chat_error.connect(self._main_thread_hud_chat_error)
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

    def _main_thread_open_settings(self, screen_id: str = "settings"):
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.show_window()
            self.main_window.show_screen(screen_id)

    def _main_thread_shutdown(self):
        self.shutdown()

    def _main_thread_hud_chat_loading(self, query: str):
        if hasattr(self, "hud") and self.hud:
            self.hud.set_chat_loading(query)

    def _main_thread_hud_chat_response(self, presentation: Any, chat_id: int):
        if chat_id != getattr(self, "_chat_seq", 0):
            logging.info("[HUD Chat] Ignoring stale chat response (chat_id %d vs current %d)", chat_id, self._chat_seq)
            return
        if hasattr(self, "hud") and self.hud:
            self.hud.set_chat_response(presentation)

    def _main_thread_hud_chat_error(self, err_msg: str, chat_id: int):
        if chat_id != getattr(self, "_chat_seq", 0):
            return
        if hasattr(self, "hud") and self.hud:
            self.hud.set_chat_error(err_msg)

    def _main_thread_solve_started(self):
        show_hud = getattr(self.config, "hud_enabled", True) and getattr(self.config, "show_hud_on_solve", True)
        if show_hud and hasattr(self, "hud") and self.hud:
            try:
                self.hud.timeout_sec = getattr(self.config, "answer_timeout_sec", 0)
                if hasattr(self.hud, "start_solve"):
                    self.hud.start_solve()
                elif hasattr(self.hud, "set_analyzing"):
                    self.hud.set_analyzing()
                elif hasattr(self.hud, "show_overlay"):
                    self.hud.show_overlay()
            except Exception as e:
                logging.exception("Error in HUD start_solve: %s", e)
        if hasattr(self, "main_window") and self.main_window:
            try:
                self.main_window.on_solve_started()
            except Exception as e:
                logging.exception("Error in main_window.on_solve_started: %s", e)
        if hasattr(self, "tray") and self.tray:
            try:
                self.tray.update_badge(badge="", status="thinking", tooltip="Ghostline — Thinking…")
            except Exception as e:
                logging.exception("Error in tray.update_badge: %s", e)

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

    def _main_thread_audio_thinking(self, question: str, entry_id: str = ""):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_thinking(question)
        if hasattr(self, "hud") and self.hud:
            self.hud.set_ai_thinking(question, entry_id=entry_id if entry_id else None)

    def _main_thread_audio_answer(self, question: str, answer: str, code: Optional[str] = None, entry_id: str = ""):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_answer(question, answer, code)
        if hasattr(self, "hud") and self.hud:
            self.hud.append_ai_answer(answer, question=question, code=code, entry_id=entry_id if entry_id else None)

    def _main_thread_audio_error(self, err: str):
        if hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_error(err)
        if hasattr(self, "hud") and self.hud:
            self.hud.set_chat_error(err)

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

    def open_settings(self, screen_id: str = "settings"):
        """Restores main window and switches to Settings screen."""
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_open_settings.emit(screen_id)
        elif hasattr(self, "main_window") and self.main_window:
            self.main_window.show_window()
            self.main_window.show_screen(screen_id)

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
        """Returns bounding boxes of active Ghostline windows to avoid self-capture in hover detection and screen OCR."""
        rects = []
        try:
            if hasattr(self, "hud") and self.hud:
                try:
                    is_vis = getattr(self.hud, "is_visible", False) or (hasattr(self.hud, "isVisible") and self.hud.isVisible())
                    if is_vis and hasattr(self.hud, "get_window_rect"):
                        r = self.hud.get_window_rect()
                        if r:
                            rects.append(r)
                except Exception:
                    pass
            if hasattr(self, "main_window") and self.main_window:
                try:
                    is_vis = getattr(self.main_window, "is_visible", False) or (hasattr(self.main_window, "isVisible") and self.main_window.isVisible())
                    if is_vis and hasattr(self.main_window, "get_window_rect"):
                        r = self.main_window.get_window_rect()
                        if r:
                            rects.append(r)
                except Exception:
                    pass
            if hasattr(self, "audio_panel") and self.audio_panel:
                try:
                    is_vis = getattr(self.audio_panel, "is_visible", False) or (hasattr(self.audio_panel, "isVisible") and self.audio_panel.isVisible())
                    if is_vis and hasattr(self.audio_panel, "get_window_rect"):
                        r = self.audio_panel.get_window_rect()
                        if r:
                            rects.append(r)
                except Exception:
                    pass
            if rects:
                self._cached_excluded_rects = rects
        except Exception as e:
            logging.debug("Error retrieving excluded window rects: %s", e)
            return getattr(self, "_cached_excluded_rects", [])
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
                self.hud.btn_pause.setText("⏸" if not paused else "▶")
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
        save_config(self.config)
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

        if hasattr(self, "hud") and self.hud:
            try:
                self.hud.opacity = new_config.hud_opacity
                self.hud.setWindowOpacity(new_config.hud_opacity)
                self.hud.always_on_top = new_config.hud_always_on_top
                self.hud.is_pinned = new_config.hud_pinned
                self.hud.exclude_from_capture = new_config.exclude_from_capture
                try:
                    hud_hwnd = int(self.hud.winId())
                    from ghostline.core.capture_exclusion import set_capture_exclusion
                    set_capture_exclusion(hud_hwnd, new_config.exclude_from_capture)
                except Exception:
                    pass
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

        if hasattr(self, "audio_panel") and self.audio_panel:
            try:
                self.audio_panel.exclude_from_capture = getattr(new_config, "exclude_from_capture", True)
                try:
                    ap_hwnd = int(self.audio_panel.winId())
                    from ghostline.core.capture_exclusion import set_capture_exclusion
                    set_capture_exclusion(ap_hwnd, new_config.exclude_from_capture)
                except Exception:
                    pass
            except Exception as e:
                logging.warning("[AudioPanel] Capture exclusion warning: %s", e)

        # Notify hotkey loop to re-register hotkey immediately
        if self.hotkey_hwnd:
            try:
                win32gui.PostMessage(self.hotkey_hwnd, WM_GHOSTLINE_RELOAD_HOTKEYS, 0, 0)
            except Exception as e:
                logging.warning("[Hotkey] Failed to post reload hotkey message: %s", e)

        # Apply Taskbar Visibility & Custom Icon
        if hasattr(self, "main_window") and self.main_window:
            try:
                self.main_window.apply_taskbar_visibility(getattr(new_config, "hide_from_taskbar", False))
                self.main_window.apply_icon()
            except Exception as e:
                logging.warning("[MainWindow] Taskbar/Icon update note: %s", e)

        if hasattr(self, "tray") and self.tray:
            try:
                self.tray.set_custom_icon(
                    getattr(new_config, "custom_icon_path", None),
                    getattr(new_config, "custom_icon_preset", "default")
                )
            except Exception as e:
                logging.warning("[Tray] Icon update note: %s", e)

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

    def _on_audio_question_detected(self, question, *args):
        eid = args[0] if args else ""
        if hasattr(self, "bridge") and self.bridge:
            try:
                self.bridge.sig_audio_thinking[str, str].emit(str(question), str(eid))
            except Exception:
                self.bridge.sig_audio_thinking[str].emit(str(question))
        elif hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_thinking(question)
        if hasattr(self, "hud") and self.hud and not hasattr(self, "bridge"):
            self.hud.set_ai_thinking(question, entry_id=eid if eid else None)

    def _on_audio_answer(self, question, answer, code=None, *args, **kwargs):
        eid = kwargs.get("entry_id") or (args[0] if args else "")
        if hasattr(self, "bridge") and self.bridge:
            try:
                self.bridge.sig_audio_answer[str, str, object, str].emit(str(question or ""), str(answer or ""), code, str(eid))
            except Exception:
                self.bridge.sig_audio_answer[str, str, object].emit(str(question or ""), str(answer or ""), code)
        else:
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_ai_answer(question, answer, code)
            if hasattr(self, "hud") and self.hud:
                self.hud.append_ai_answer(answer, question=question, code=code, entry_id=eid if eid else None)

    def _on_audio_error(self, err):
        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_error.emit(str(err))
        elif hasattr(self, "audio_panel") and self.audio_panel:
            self.audio_panel.set_ai_error(err)

    def on_hud_ask_custom(self, query: str):
        """Dispatches manual question entered in HUD bottom query input with conversation context."""
        clean_q = query.strip()
        if not clean_q:
            return
        logging.info("[HUD Chat] Query submitted: %s", clean_q[:60])
        if hasattr(self, "hud") and getattr(self.hud, "active_mode", "answer") in ("audio", "call"):
            self.ask_audio_custom(clean_q)
            return

        self._chat_seq = getattr(self, "_chat_seq", 0) + 1
        chat_id = self._chat_seq

        # Retrieve prior question and answer context on main GUI thread before dispatching worker
        prior_q = self.hud.get_current_question() if hasattr(self.hud, "get_current_question") else ""
        prior_a = self.hud.get_current_answer() if hasattr(self.hud, "get_current_answer") else ""

        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_hud_chat_loading.emit(clean_q)

        def _worker():
            try:
                # If there was a previous question & answer on screen, incorporate it as context
                context_prefix = ""
                if prior_q and "Ready for next question" not in prior_q:
                    context_prefix = f"Context from previous question on screen:\nQuestion: {prior_q}\n"
                    if prior_a and "Hover or press" not in prior_a:
                        context_prefix += f"Answer: {prior_a}\n"
                    context_prefix += "\nFollow-up Request:\n"

                full_prompt = f"{context_prefix}{clean_q}" if context_prefix else clean_q

                res = self.ollama.solve_question(
                    question_text=full_prompt,
                    options=None,
                    model=self.config.model_name
                )
                from ghostline.core.ocr_engine import ParsedQuestion
                sim_q = ParsedQuestion(question_text=clean_q, options={}, raw_text=clean_q)
                presentation = build_answer_presentation(sim_q, res)
                if hasattr(self, "bridge") and self.bridge:
                    self.bridge.sig_hud_chat_response.emit(presentation, chat_id)
            except Exception as e:
                logging.exception(f"HUD chat inference failed: {e}")
                if hasattr(self, "bridge") and self.bridge:
                    self.bridge.sig_hud_chat_error.emit(str(e), chat_id)

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


    def start_audio_capture(self) -> bool:
        """
        Starts live audio capture and transcription safely.
        Handles missing hardware/unsupported sample rates gracefully without crashing.
        Returns True if capture started, False if failed.
        """
        logging.info("[Audio] Starting live audio capture and transcription...")
        new_session_id = str(uuid.uuid4())[:8]
        if hasattr(self, "audio_assistant") and self.audio_assistant:
            self.audio_assistant.set_session(new_session_id)
        if hasattr(self, "hud") and self.hud and hasattr(self.hud, "session"):
            self.hud.session.session_id = new_session_id

        started = False
        status_msg = ""
        if hasattr(self, "audio_capture") and self.audio_capture:
            try:
                res = self.audio_capture.start()
                if isinstance(res, tuple):
                    started, status_msg = res
                else:
                    started = bool(res)
            except Exception as e:
                logging.exception("[Audio] Unexpected exception starting audio capture: %s", e)
                started = False
                status_msg = str(e)

        if not started:
            err = status_msg or "Audio capture could not be started. Check microphone / loopback audio devices."
            logging.warning("[Audio] Audio capture could not be started: %s", err)
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_audio_status.emit(False, False)
                self.bridge.sig_audio_error.emit(err)
            else:
                if hasattr(self, "hud") and self.hud:
                    self.hud.update_audio_status(is_capturing=False, is_paused=False)
                if hasattr(self, "audio_panel") and self.audio_panel:
                    self.audio_panel.set_capture_state(False)
                if hasattr(self, "main_window") and self.main_window:
                    self.main_window.update_audio_status(is_capturing=False, is_paused=False)
            return False

        if hasattr(self, "transcriber") and self.transcriber:
            try:
                self.transcriber.start()
            except Exception as e:
                logging.warning("[Audio] Transcriber start exception: %s", e)

        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_status.emit(True, False)
        else:
            if hasattr(self, "hud") and self.hud:
                self.hud.update_audio_status(is_capturing=True, is_paused=False)
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_capture_state(True)
                self.audio_panel.show_panel()
            if hasattr(self, "main_window") and self.main_window:
                self.main_window.update_audio_status(is_capturing=True, is_paused=False)
        return True

    def stop_audio_capture(self):
        """Stops live audio capture and transcription cleanly."""
        logging.info("[Audio] Stopping live audio capture...")
        if hasattr(self, "audio_capture") and self.audio_capture:
            try:
                self.audio_capture.stop()
            except Exception as e:
                logging.warning("[Audio] Error stopping audio capture: %s", e)
        if hasattr(self, "transcriber") and self.transcriber:
            try:
                self.transcriber.stop()
            except Exception as e:
                logging.warning("[Audio] Error stopping transcriber: %s", e)

        if hasattr(self, "bridge") and self.bridge:
            self.bridge.sig_audio_status.emit(False, False)
        else:
            if hasattr(self, "hud") and self.hud:
                self.hud.update_audio_status(is_capturing=False, is_paused=False)
            if hasattr(self, "audio_panel") and self.audio_panel:
                self.audio_panel.set_capture_state(False)
            if hasattr(self, "main_window") and self.main_window:
                self.main_window.update_audio_status(is_capturing=False, is_paused=False)

    def toggle_audio_capture(self) -> bool:
        """
        Toggles live audio capture with re-entrant debounce lock to prevent duplicate
        workers or simultaneous PyAudio initialization races when hotkey is pressed repeatedly.
        """
        if not hasattr(self, "_audio_toggle_lock"):
            self._audio_toggle_lock = threading.Lock()

        # Non-blocking lock to reject fast duplicate toggle presses while transition is in progress
        if not self._audio_toggle_lock.acquire(blocking=False):
            logging.info("[Audio] Audio toggle is currently transitioning; ignoring overlapping request.")
            return getattr(self.audio_capture, "is_capturing", False) if hasattr(self, "audio_capture") else False

        try:
            is_capturing = getattr(self.audio_capture, "is_capturing", False) if hasattr(self, "audio_capture") else False
            if is_capturing:
                self.stop_audio_capture()
                return False
            else:
                return self.start_audio_capture()
        finally:
            self._audio_toggle_lock.release()

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
        mode_str = get_running_mode()
        print(f"[*] Running Mode: [{mode_str}]")
        print(f"[*] Version & Build: v{__version__} ({BUILD_ID})")
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

        # Check cursor position relative to HUD overlay to prevent capturing own HUD
        try:
            import win32api
            cursor_pos = win32api.GetCursorPos()
            if cursor_pos and hasattr(self, "hud") and self.hud:
                if hasattr(self.hud, "is_inside_hud") and self.hud.is_inside_hud(cursor_pos[0], cursor_pos[1]):
                    logging.info("Cursor is positioned directly over Ghostline HUD; ignoring self-capture.")
                    if hasattr(self.hud, "show_toast"):
                        self.hud.show_toast("Move cursor over the question to solve")
                    return
        except Exception as e:
            logging.debug("HUD cursor check note: %s", e)

        # Retrieve excluded rects on GUI thread to avoid cross-thread QWidget access
        excluded_rects = self.get_excluded_window_rects()
        
        thread = threading.Thread(target=self._solve_worker, args=(is_auto_hover, excluded_rects), daemon=True)
        thread.start()

    def _solve_worker(self, is_auto_hover: bool = False, excluded_rects: Optional[List[Tuple[int, int, int, int]]] = None):
        self.is_solving = True
        t_start = time.time()
        tracer = PipelineTracer()
        tracer.start_trace()
        logging.info("[Diagnostic %s] _solve_worker started (PID=%d, Thread=%s, is_auto_hover=%s)",
                     time.strftime("%H:%M:%S"), os.getpid(), threading.get_ident(), is_auto_hover)
        solve_id = int(time.time() * 1000) & 0x7FFFFFFF
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
            if excluded_rects is None:
                excluded_rects = getattr(self, "_cached_excluded_rects", [])
            res = self.pipeline.process_from_cursor(
                capture_width=self.config.capture_width,
                capture_height=self.config.capture_height,
                capture_mode=getattr(self.config, "capture_mode", "full_screen"),
                stream_callback=on_stream,
                progress_callback=on_progress,
                is_duplicate_fn=dup_check,
                tracer=tracer,
                excluded_rects=excluded_rects
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
            elif msg == WM_GHOSTLINE_RELOAD_HOTKEYS:
                logging.info("[Hotkey] WM_GHOSTLINE_RELOAD_HOTKEYS received in wndproc. Reloading shortcut.")
                new_mod, new_vk = parse_hotkey_string(getattr(self.config, 'hotkey', 'Alt + /'))
                user32.UnregisterHotKey(hwnd, HOTKEY_SOLVE)
                if user32.RegisterHotKey(hwnd, HOTKEY_SOLVE, new_mod | MOD_NOREPEAT, new_vk):
                    logging.info("[Hotkey] Re-registered HOTKEY_SOLVE as %s", getattr(self.config, 'hotkey', 'Alt + /'))
                    self.hotkey_registered = True
                else:
                    err = ctypes.GetLastError()
                    logging.warning("[Hotkey] Failed to re-register HOTKEY_SOLVE (%s): Win32 Error %d", getattr(self.config, 'hotkey', 'Alt + /'), err)
                    self.hotkey_registered = False
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
                        logging.info("[Diagnostic %s] WM_HOTKEY Alt+A (Audio Assistance Toggle) received.", time.strftime("%H:%M:%S"))
                        if hasattr(self, "bridge") and self.bridge:
                            self.bridge.sig_toggle_audio_capture.emit()
                        else:
                            self.toggle_audio_capture()
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
                elif msg_id == WM_GHOSTLINE_RELOAD_HOTKEYS:
                    logging.info("[Hotkey] WM_GHOSTLINE_RELOAD_HOTKEYS received in message loop. Reloading shortcut.")
                    new_mod, new_vk = parse_hotkey_string(getattr(self.config, 'hotkey', 'Alt + /'))
                    user32.UnregisterHotKey(hwnd, HOTKEY_SOLVE)
                    if user32.RegisterHotKey(hwnd, HOTKEY_SOLVE, new_mod | MOD_NOREPEAT, new_vk):
                        logging.info("[Hotkey] Re-registered HOTKEY_SOLVE as %s", getattr(self.config, 'hotkey', 'Alt + /'))
                        self.hotkey_registered = True
                    else:
                        err = ctypes.GetLastError()
                        logging.warning("[Hotkey] Failed to re-register HOTKEY_SOLVE (%s): Win32 Error %d", getattr(self.config, 'hotkey', 'Alt + /'), err)
                        self.hotkey_registered = False
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
        logging.info("[HUD] Overlay closed by user; keeping in background.")
        if hasattr(self, "tray") and self.tray:
            self.tray.update_badge("", "ready", tooltip="Ghostline: Ready (Alt+/)")

    def on_hud_end(self):
        """Cleanly terminates active solve and live audio session across all controllers while preserving history."""
        logging.info("[HUD] End button clicked — terminating active session.")
        self.is_solving = False
        self._chat_seq = getattr(self, "_chat_seq", 0) + 1

        # 1. Stop audio capture and transcription background workers
        self.stop_audio_capture()

        # 2. End session in audio assistant (cancels debounces, in-flight Ollama calls)
        if hasattr(self, "audio_assistant") and self.audio_assistant:
            self.audio_assistant.end_session()

        # 3. Notify hover detector of completed solve
        if hasattr(self, "hover_detector"):
            self.hover_detector.notify_solve_completed()

        # 4. Update HUD state and controls without wiping conversation history
        if hasattr(self, "hud") and self.hud:
            self.hud.set_keyword_chips(["Session Ended", "Preserved"])
            if hasattr(self.hud, "btn_pause"):
                self.hud.btn_pause.setText("⏸ Pause")
            self.hud.update_audio_status(is_capturing=False, is_paused=False)

        # 5. Update tray & caps indicator
        if hasattr(self, "tray") and self.tray:
            self.tray.update_badge(badge="", status="ready", tooltip="Ghostline: Ready (Alt+/)")
        if hasattr(self, "caps_indicator") and self.caps_indicator:
            self.caps_indicator.restore_safety_state()

    def shutdown(self):
        if getattr(self, "_is_shutting_down", False):
            return
        self._is_shutting_down = True

        if threading.current_thread() is not threading.main_thread():
            if hasattr(self, "bridge") and self.bridge:
                self.bridge.sig_shutdown.emit()
                return
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
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            try:
                self.hotkey_thread.join(timeout=1.0)
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
        if hasattr(self, "qapp") and self.qapp:
            try:
                self.qapp.quit()
            except Exception:
                pass
        else:
            sys.exit(0)


def _cleanup_orphaned_ghostline_instances(current_pid: int):
    """Safely terminates dead/orphaned Ghostline processes holding mutexes without active windows."""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid == current_pid or pid == os.getpid():
                    continue
                pname = (proc.info['name'] or '').lower()
                cmd = ' '.join(proc.info['cmdline'] or []).lower()
                if 'ghostline.exe' in pname or ('python' in pname and ('ghostline.app' in cmd or 'ghostline\\app.py' in cmd or 'ghostline/app.py' in cmd)):
                    logging.info("Terminating orphaned Ghostline process PID=%d (%s)", pid, pname)
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        logging.warning("Orphaned process cleanup note: %s", e)


def main():
    setup_file_logging()
    mode_str = get_running_mode()
    logging.info("=" * 65)
    logging.info("Starting %s", BUILD_IDENTIFIER)
    logging.info("Running Mode: %s (PID=%d)", mode_str, os.getpid())
    logging.info("Executable: %s", sys.executable)
    logging.info("Working Directory: %s", os.getcwd())
    logging.info("Git Commit: %s", GIT_COMMIT)
    logging.info("Build Timestamp: %s", BUILD_TIMESTAMP)
    logging.info("=" * 65)

    # Check if explicit restart was requested
    is_restart = any(arg in sys.argv for arg in ["--restart", "-r", "/restart"])
    if is_restart:
        logging.info("[Restart] Explicit restart requested: closing any existing Ghostline processes...")
        _cleanup_orphaned_ghostline_instances(current_pid=os.getpid())
        time.sleep(0.5)

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
            "build_id": BUILD_ID,
            "git_commit": GIT_COMMIT,
            "git_commit_short": GIT_COMMIT_SHORT,
            "build_timestamp": BUILD_TIMESTAMP,
            "build_identifier": BUILD_IDENTIFIER,
            "running_mode": mode_str,
            "frozen": getattr(sys, "frozen", False),
            "executable": sys.executable,
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
        
        sink_hwnd = win32gui.FindWindow(SINGLE_INSTANCE_SINK_CLASS, None)
        if sink_hwnd and win32gui.IsWindow(sink_hwnd):
            logging.info("[Diagnostic %s] Existing Ghostline instance detected via Mutex (PID=%d). Found active sink window (HWND %s). Sending %s to primary instance.",
                         time.strftime("%H:%M:%S"), os.getpid(), sink_hwnd, msg_name)
            win32gui.PostMessage(sink_hwnd, target_msg, 0, 0)
            if not is_solve_trigger:
                try:
                    win32gui.SetForegroundWindow(sink_hwnd)
                except Exception:
                    pass
            print(f"[*] Activated existing Ghostline instance (sent {msg_name}). Exiting secondary process (PID={os.getpid()}).")
            sys.exit(0)
        else:
            # Mutex exists but NO active sink window exists (orphaned process or stale mutex).
            # Clean up orphaned processes, release mutex, and proceed with application startup.
            logging.warning("[Diagnostic %s] Mutex was held but active sink window was not found (orphaned/stale process). Cleaning up and taking over.",
                            time.strftime("%H:%M:%S"))
            _cleanup_orphaned_ghostline_instances(current_pid=os.getpid())
            try:
                win32api.CloseHandle(mutex)
            except Exception:
                pass
            time.sleep(0.3)
            mutex = win32event.CreateMutex(None, False, mutex_name)

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

