"""
Ghostline — Modern PyQt6 Live Audio & Transcript Assistant HUD.
Features:
- Distinct visual areas for live transcript and AI response
- Independent scrollable areas for both transcript history and AI analysis
- Readable timestamps, speaker source labels ([Call] vs [Mic])
- Live microphone & system loopback VU audio level meters
- Functional Start / Stop / Pause controls with visible recording indicator
- Win32 WS_EX_NOACTIVATE (focus-free) and WDA_EXCLUDEFROMCAPTURE (stealth overlay)
"""

import os
import sys
import time
import ctypes
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QColor, QFont, QCursor, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QTextEdit, QScrollArea,
    QProgressBar, QSizePolicy, QFileDialog, QMessageBox
)

from ghostline.ui.qt_theme import (
    QT_MAIN_STYLESHEET, QtModernToggleSwitch, QtWaveformWidget,
    C_BG_APP, C_BG_SIDEBAR, C_BG_CARD, C_BG_CARD_HOVER, C_BG_CARD_ACTIVE,
    C_BORDER, C_BORDER_LIGHT, C_BORDER_ACCENT, C_CYAN, C_EMERALD,
    C_AMBER, C_DANGER, C_GOLD, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_MUTED
)
from ghostline.core.capture_exclusion import set_capture_exclusion
from ghostline.audio.transcription import TranscriptSegment

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080


class QtLiveAudioPanel(QWidget):
    """
    State-of-the-art Live Audio HUD Overlay for Ghostline.
    """

    def __init__(
        self,
        on_start_capture: Optional[Callable[[], None]] = None,
        on_stop_capture: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], bool]] = None,
        on_toggle_call_audio: Optional[Callable[[bool], None]] = None,
        on_toggle_mic: Optional[Callable[[bool], None]] = None,
        on_ask_custom: Optional[Callable[[str], None]] = None,
        on_clear_transcript: Optional[Callable[[], None]] = None,
        on_export_transcript: Optional[Callable[[str], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        opacity: float = 0.95,
        width: int = 560,
        height: int = 680,
        always_on_top: bool = True,
        exclude_from_capture: bool = True,
        call_audio_enabled: bool = True,
        mic_enabled: bool = True,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.on_start_capture = on_start_capture
        self.on_stop_capture = on_stop_capture
        self.on_toggle_pause = on_toggle_pause
        self.on_toggle_call_audio = on_toggle_call_audio
        self.on_toggle_mic = on_toggle_mic
        self.on_ask_custom = on_ask_custom
        self.on_clear_transcript = on_clear_transcript
        self.on_export_transcript = on_export_transcript
        self.on_close = on_close

        self.opacity = opacity
        self.always_on_top = always_on_top
        self.exclude_from_capture = exclude_from_capture
        self.call_audio_enabled = call_audio_enabled
        self.mic_enabled = mic_enabled

        self.is_recording = False
        self.is_paused = False
        self._drag_pos = QPoint()
        self._is_visible = False
        self.root = self

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(self.opacity)
        self.resize(width, height)

        self._build_ui()
        self._apply_win32_styles()

    def _apply_win32_styles(self):
        hwnd = int(self.winId())
        if sys.platform == "win32" and hwnd:
            try:
                user32 = ctypes.windll.user32
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
                if self.exclude_from_capture:
                    set_capture_exclusion(hwnd, True)
            except Exception:
                pass

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Main Glass Container
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(17, 19, 24, 0.94);
                border: 1px solid {C_BORDER};
                border-radius: 14px;
            }}
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(12)

        # -------------------------------------------------------------
        # Header: Title, Recording Indicator, Controls
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(10)

        # Recording pulse dot
        self.lbl_rec_dot = QLabel("●")
        self.lbl_rec_dot.setStyleSheet(f"color: {C_DANGER}; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        self.lbl_rec_text = QLabel("LIVE AUDIO HUD")
        self.lbl_rec_text.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 13px; font-weight: 700; background: transparent; border: none; letter-spacing: 0.5px;")

        header.addWidget(self.lbl_rec_dot)
        header.addWidget(self.lbl_rec_text)
        header.addStretch()

        # Mini Waveform
        self.waveform = QtWaveformWidget()
        self.waveform.setFixedSize(60, 20)
        self.waveform.setStyleSheet("background: transparent; border: none;")
        header.addWidget(self.waveform)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TEXT_MUTED};
                border: 1px solid {C_BORDER};
                border-radius: 13px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(239, 68, 68, 0.2);
                color: #ef4444;
                border-color: #ef4444;
            }}
        """)
        btn_close.clicked.connect(self.hide_panel)
        header.addWidget(btn_close)
        c_layout.addLayout(header)

        # -------------------------------------------------------------
        # Status & Control Action Bar
        # -------------------------------------------------------------
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        self.btn_capture = QPushButton("Start Listening")
        self.btn_capture.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_capture.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background: #10b981;
            }}
        """)
        self.btn_capture.clicked.connect(self._toggle_capture_click)
        ctrl_bar.addWidget(self.btn_capture)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_pause.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG_CARD};
                color: {C_TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 600;
                padding: 6px 12px;
                border-radius: 6px;
                border: 1px solid {C_BORDER};
            }}
            QPushButton:hover {{
                background-color: {C_BG_CARD_HOVER};
                border-color: {C_BORDER_LIGHT};
            }}
        """)
        self.btn_pause.clicked.connect(self._toggle_pause_click)
        ctrl_bar.addWidget(self.btn_pause)

        # Audio VU meters: Mic & System
        lbl_mic = QLabel("Mic:")
        lbl_mic.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
        self.vu_mic = QProgressBar()
        self.vu_mic.setFixedSize(50, 8)
        self.vu_mic.setTextVisible(False)
        self.vu_mic.setRange(0, 100)
        self.vu_mic.setValue(0)
        self.vu_mic.setStyleSheet(f"""
            QProgressBar {{
                background: #1c202a;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C_EMERALD};
                border-radius: 4px;
            }}
        """)

        lbl_sys = QLabel("Call:")
        lbl_sys.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
        self.vu_sys = QProgressBar()
        self.vu_sys.setFixedSize(50, 8)
        self.vu_sys.setTextVisible(False)
        self.vu_sys.setRange(0, 100)
        self.vu_sys.setValue(0)
        self.vu_sys.setStyleSheet(f"""
            QProgressBar {{
                background: #1c202a;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C_CYAN};
                border-radius: 4px;
            }}
        """)

        ctrl_bar.addWidget(lbl_mic)
        ctrl_bar.addWidget(self.vu_mic)
        ctrl_bar.addWidget(lbl_sys)
        ctrl_bar.addWidget(self.vu_sys)
        ctrl_bar.addStretch()

        c_layout.addLayout(ctrl_bar)

        # -------------------------------------------------------------
        # Section 1: Live Audio Transcript (Scrollable)
        # -------------------------------------------------------------
        sec1_header = QHBoxLayout()
        lbl_trans_title = QLabel("LIVE TRANSCRIPTION")
        lbl_trans_title.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; background: transparent; border: none;")
        sec1_header.addWidget(lbl_trans_title)
        sec1_header.addStretch()

        btn_export = QPushButton("Export")
        btn_export.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_export.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent; border: none; margin-right: 6px;")
        btn_export.clicked.connect(self._export_transcript_click)
        sec1_header.addWidget(btn_export)

        btn_clear = QPushButton("Clear")
        btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_clear.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
        btn_clear.clicked.connect(self._clear_transcript_click)
        sec1_header.addWidget(btn_clear)
        c_layout.addLayout(sec1_header)

        # Transcript Scroll Area
        self.transcript_scroll = QScrollArea()
        self.transcript_scroll.setWidgetResizable(True)
        self.transcript_scroll.setFixedHeight(180)
        self.transcript_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: #0c0d11;
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        self.transcript_container = QWidget()
        self.transcript_container.setStyleSheet("background: transparent;")
        self.transcript_layout = QVBoxLayout(self.transcript_container)
        self.transcript_layout.setContentsMargins(10, 10, 10, 10)
        self.transcript_layout.setSpacing(6)
        self.transcript_layout.addStretch()
        self.transcript_scroll.setWidget(self.transcript_container)
        c_layout.addWidget(self.transcript_scroll)

        # Partial speech row
        self.lbl_partial = QLabel("Listening for speech...")
        self.lbl_partial.setStyleSheet(f"color: {C_TEXT_MUTED}; font-style: italic; font-size: 11px; background: transparent; border: none; padding-left: 4px;")
        c_layout.addWidget(self.lbl_partial)

        # -------------------------------------------------------------
        # Section 2: AI Response & Analysis Area (Scrollable)
        # -------------------------------------------------------------
        sec2_header = QHBoxLayout()
        lbl_ai_title = QLabel("REAL-TIME AI ANALYSIS & ANSWERS")
        lbl_ai_title.setStyleSheet(f"color: {C_CYAN}; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; background: transparent; border: none;")
        sec2_header.addWidget(lbl_ai_title)
        sec2_header.addStretch()

        self.btn_copy_ai = QPushButton("Copy Answer")
        self.btn_copy_ai.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy_ai.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_TEXT_SECONDARY};
                font-size: 11px;
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                background: {C_BG_CARD_HOVER};
                color: {C_CYAN};
            }}
        """)
        self.btn_copy_ai.clicked.connect(self._copy_ai_response)
        sec2_header.addWidget(self.btn_copy_ai)
        c_layout.addLayout(sec2_header)

        # AI Response Card & Scroll Area
        self.ai_scroll = QScrollArea()
        self.ai_scroll.setWidgetResizable(True)
        self.ai_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: #14171f;
                border: 1px solid {C_BORDER_ACCENT};
                border-radius: 8px;
            }}
        """)
        self.ai_container = QWidget()
        self.ai_container.setStyleSheet("background: transparent;")
        self.ai_layout = QVBoxLayout(self.ai_container)
        self.ai_layout.setContentsMargins(12, 12, 12, 12)
        self.ai_layout.setSpacing(8)

        self.lbl_ai_q = QLabel("Question detected from call will appear here.")
        self.lbl_ai_q.setWordWrap(True)
        self.lbl_ai_q.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px; font-weight: 600; background: transparent; border: none;")
        self.ai_layout.addWidget(self.lbl_ai_q)

        self.lbl_ai_ans = QLabel("AI guidance and validated solutions will generate automatically.")
        self.lbl_ai_ans.setWordWrap(True)
        self.lbl_ai_ans.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 13px; line-height: 1.4; background: transparent; border: none;")
        self.ai_layout.addWidget(self.lbl_ai_ans)

        self.ai_code_frame = QFrame()
        self.ai_code_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #0b0d13;
                border: 1px solid {C_BORDER};
                border-radius: 6px;
            }}
        """)
        code_vbox = QVBoxLayout(self.ai_code_frame)
        code_vbox.setContentsMargins(8, 8, 8, 8)
        self.lbl_ai_code = QLabel()
        self.lbl_ai_code.setWordWrap(True)
        self.lbl_ai_code.setStyleSheet(f"color: {C_EMERALD}; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; background: transparent; border: none;")
        code_vbox.addWidget(self.lbl_ai_code)
        self.ai_code_frame.hide()
        self.ai_layout.addWidget(self.ai_code_frame)

        self.ai_layout.addStretch()
        self.ai_scroll.setWidget(self.ai_container)
        c_layout.addWidget(self.ai_scroll)

        # -------------------------------------------------------------
        # Footer: Manual Query Input
        # -------------------------------------------------------------
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.input_custom = QLineEdit()
        self.input_custom.setPlaceholderText("Ask AI about this call / interview...")
        self.input_custom.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0c0d11;
                color: {C_TEXT_PRIMARY};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C_CYAN};
            }}
        """)
        self.input_custom.returnPressed.connect(self._send_custom_query)
        footer.addWidget(self.input_custom)

        btn_send = QPushButton("Ask")
        btn_send.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_CYAN};
                color: #090d16;
                font-size: 12px;
                font-weight: 700;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #7dd3fc;
            }}
        """)
        btn_send.clicked.connect(self._send_custom_query)
        footer.addWidget(btn_send)

        c_layout.addLayout(footer)

        main_layout.addWidget(container)

    # -------------------------------------------------------------------------
    # Drag Behavior
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()

    # -------------------------------------------------------------------------
    # Public Controller API
    # -------------------------------------------------------------------------
    def launch(self, parent=None, start_visible: bool = False):
        if start_visible:
            self.show_panel()

    def show_panel(self):
        self._is_visible = True
        self.show()
        self.raise_()
        self._apply_win32_styles()

    def hide_panel(self):
        self._is_visible = False
        self.hide()
        if self.on_close:
            self.on_close()

    def toggle_visibility(self):
        if self._is_visible:
            self.hide_panel()
        else:
            self.show_panel()

    @property
    def is_visible(self) -> bool:
        return self.isVisible()

    def get_window_rect(self):
        if not self.isVisible():
            return None
        geo = self.geometry()
        return (geo.left(), geo.top(), geo.right(), geo.bottom())

    def update_level(self, source: str, rms: float, peak: float):
        val = min(100, int(rms * 250))
        if source == "mic":
            self.vu_mic.setValue(val)
        else:
            self.vu_sys.setValue(val)

    def update_partial(self, text: str, source: str):
        if text.strip():
            src_lbl = "[Mic]" if source == "mic" else "[Call]"
            self.lbl_partial.setText(f"{src_lbl}: {text}...")
        else:
            self.lbl_partial.setText("Listening for speech...")

    def append_final_segment(self, segment: TranscriptSegment):
        time_str = time.strftime("%H:%M:%S")
        is_mic = getattr(segment, "source", "call") == "mic"
        src_tag = "[You]" if is_mic else "[Call]"
        tag_color = C_EMERALD if is_mic else C_CYAN

        row = QLabel()
        row.setWordWrap(True)
        row.setStyleSheet("background: transparent; border: none; font-size: 12px;")
        row.setText(f"<span style='color: {C_TEXT_MUTED}; font-size: 10px;'>[{time_str}]</span> "
                    f"<b style='color: {tag_color};'>{src_tag}</b> "
                    f"<span style='color: {C_TEXT_PRIMARY};'>{segment.text}</span>")

        # Insert before stretch
        cnt = self.transcript_layout.count()
        self.transcript_layout.insertWidget(max(0, cnt - 1), row)

        # Scroll to bottom
        QTimer.singleShot(50, lambda: self.transcript_scroll.verticalScrollBar().setValue(
            self.transcript_scroll.verticalScrollBar().maximum()
        ))
        self.lbl_partial.setText("Listening for speech...")

    def set_ai_thinking(self, question: str):
        self.lbl_ai_q.setText(f"Q: {question}")
        self.lbl_ai_ans.setText("Analyzing call query with local Ollama AI...")
        self.ai_code_frame.hide()

    def set_ai_answer(self, question: str, answer: str, code: Optional[str] = None):
        if question:
            self.lbl_ai_q.setText(f"Q: {question}")
        self.lbl_ai_ans.setText(answer)
        if code:
            self.lbl_ai_code.setText(code)
            self.ai_code_frame.show()
        else:
            self.ai_code_frame.hide()

        # Auto show panel if hidden when an answer is ready
        if not self.isVisible():
            self.show_panel()

    def set_capture_state(self, is_capturing: bool):
        """Safely updates capture state and toggle button appearance."""
        self.is_recording = is_capturing
        if self.is_recording:
            self.btn_capture.setText("Stop Listening")
            self.btn_capture.setStyleSheet("""
                QPushButton {
                    background: #ef4444;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover {
                    background: #dc2626;
                }
            """)
        else:
            self.btn_capture.setText("Start Listening")
            self.btn_capture.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover {
                    background: #10b981;
                }
            """)

    def set_pause_state(self, is_paused: bool):
        """Safely updates pause state and button caption."""
        self.is_paused = is_paused
        self.btn_pause.setText("Resume" if self.is_paused else "Pause")

    def _export_transcript_click(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Conversation Transcript",
            str(Path.home() / "ghostline_transcript.txt"),
            "Text Files (*.txt);;JSON Lines (*.jsonl);;All Files (*.*)"
        )
        if file_path and self.on_export_transcript:
            self.on_export_transcript(file_path)

    def destroy(self):
        self.close()

    # -------------------------------------------------------------------------
    # Internal Handlers
    # -------------------------------------------------------------------------
    def _toggle_capture_click(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.btn_capture.setText("Stop Listening")
            self.btn_capture.setStyleSheet(f"""
                QPushButton {{
                    background: #ef4444;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: none;
                }}
            """)
            if self.on_start_capture:
                self.on_start_capture()
        else:
            self.btn_capture.setText("Start Listening")
            self.btn_capture.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: none;
                }}
            """)
            if self.on_stop_capture:
                self.on_stop_capture()

    def _toggle_pause_click(self):
        self.is_paused = not self.is_paused
        self.btn_pause.setText("Resume" if self.is_paused else "Pause")
        if self.on_toggle_pause:
            self.on_toggle_pause()

    def _clear_transcript_click(self):
        # Remove items in transcript_layout except stretch
        while self.transcript_layout.count() > 1:
            item = self.transcript_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if self.on_clear_transcript:
            self.on_clear_transcript()

    def _copy_ai_response(self):
        cb = QApplication.clipboard()
        if cb:
            txt = self.lbl_ai_ans.text()
            if self.ai_code_frame.isVisible():
                txt += f"\n\n```\n{self.lbl_ai_code.text()}\n```"
            cb.setText(txt)

    def _send_custom_query(self):
        q = self.input_custom.text().strip()
        if q and self.on_ask_custom:
            self.on_ask_custom(q)
            self.input_custom.clear()
