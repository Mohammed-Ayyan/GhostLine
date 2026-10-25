"""
Ghostline Floating Assistant HUD — Premium PyQt6 Overlay.
Directly implements Reference 2 design:
- Multi-island floating dark translucent acrylic architecture
- Island 1: Action toolbar (Answer ⌘↵, Screenshot ⌘⇧↵, Chat ⌘⇧⌫, Move, Expand, End)
- Island 2: Waveform visualizer & contextual question keyword chips
- Island 3: Main Q&A Answer Card with speech bubble question, star answer, bullet points,
  syntax-highlighted code blocks, copy controls, and bottom manual query bar.
- Win32 WS_EX_NOACTIVATE (focus-free) and WDA_EXCLUDEFROMCAPTURE (screen capture exclusion).
"""

import os
import sys
import time
import ctypes
from typing import Optional, Callable, Dict, Any, List

from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QTextEdit, QScrollArea,
    QSizePolicy
)

from ghostline.ui.qt_theme import (
    QtWaveformWidget, C_BG_CARD, C_BG_CARD_HOVER, C_BG_CARD_ACTIVE,
    C_BORDER, C_BORDER_LIGHT, C_BORDER_ACCENT, C_CYAN, C_EMERALD,
    C_AMBER, C_DANGER, C_GOLD, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_MUTED
)
from ghostline.core.capture_exclusion import set_capture_exclusion
from ghostline.ui.presentation import PresentedAnswer, TYPE_MCQ, TYPE_CODE, TYPE_THEORY

# Win32 Constants for non-activating window
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080


class QtGhostlineHudOverlay(QWidget):
    """
    Premium Floating Assistant HUD matching Reference 2.
    """

    def __init__(
        self,
        on_close: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], bool]] = None,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
        on_retry: Optional[Callable[[], None]] = None,
        opacity: float = 0.95,
        width: int = 560,
        height: int = 520,
        is_pinned: bool = True,
        always_on_top: bool = True,
        exclude_from_capture: bool = True,
        is_paused: bool = False,
        on_toggle_audio: Optional[Callable[[], None]] = None,
        on_ask_custom: Optional[Callable[[str], None]] = None,
        on_trigger_screenshot: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.on_close = on_close
        self.on_toggle_pause = on_toggle_pause
        self.on_position_changed = on_position_changed
        self.on_retry = on_retry
        self.opacity = opacity
        self.is_pinned = is_pinned
        self.always_on_top = always_on_top
        self.exclude_from_capture = exclude_from_capture
        self.is_paused = is_paused
        self.on_toggle_audio = on_toggle_audio
        self.on_ask_custom = on_ask_custom
        self.on_trigger_screenshot = on_trigger_screenshot

        self._drag_pos = QPoint()
        self._is_visible = False
        self.root = self
        self.timeout_sec = 0

        # Configure window flags: Frameless, Topmost, Tool window (no taskbar item)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(width)
        self.setMinimumHeight(380)

        self._init_ui()
        self._apply_win32_styles()

    def _apply_win32_styles(self):
        """Applies WS_EX_NOACTIVATE so clicking the HUD never steals focus from active exams or code editors."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
            if self.exclude_from_capture:
                set_capture_exclusion(hwnd, enable=True)
        except Exception:
            pass

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # =====================================================================
        # ISLAND 1: Top Action Toolbar (Reference 2)
        # =====================================================================
        self.island_toolbar = QFrame()
        self.island_toolbar.setObjectName("IslandFrame")
        self.island_toolbar.setStyleSheet(
            "QFrame#IslandFrame { background: rgba(26, 29, 38, 0.96); border: 1px solid #2d3345; border-radius: 12px; }"
        )
        tb_layout = QHBoxLayout(self.island_toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)
        tb_layout.setSpacing(8)

        # Screen & Mic Icons with Badge Dots
        icon_box = QHBoxLayout()
        icon_box.setSpacing(6)
        lbl_screen = QLabel("🖥️")
        lbl_screen.setStyleSheet("font-size: 14px;")
        lbl_mic = QLabel("🎙️")
        lbl_mic.setStyleSheet("font-size: 14px;")
        icon_box.addWidget(lbl_screen)
        icon_box.addWidget(lbl_mic)
        tb_layout.addLayout(icon_box)

        # Primary Action Buttons
        self.btn_ans = QPushButton("Answer ⌘↵")
        self.btn_ans.setStyleSheet(
            f"background: {C_BG_CARD_ACTIVE}; color: #ffffff; font-weight: 700; font-size: 12px; padding: 6px 14px; border-radius: 8px; border: 1px solid {C_BORDER_LIGHT};"
        )
        self.btn_ans.clicked.connect(self._trigger_retry)
        tb_layout.addWidget(self.btn_ans)

        self.btn_shot = QPushButton("Screenshot ⌘⇧↵")
        self.btn_shot.setStyleSheet(
            f"background: rgba(0,0,0,0.3); color: {C_TEXT_SECONDARY}; font-weight: 600; font-size: 12px; padding: 6px 12px; border-radius: 8px; border: 1px solid {C_BORDER};"
        )
        self.btn_shot.clicked.connect(self._trigger_screenshot)
        tb_layout.addWidget(self.btn_shot)

        self.btn_chat = QPushButton("Chat ⌘⇧⌫")
        self.btn_chat.setStyleSheet(
            f"background: rgba(0,0,0,0.3); color: {C_TEXT_SECONDARY}; font-weight: 600; font-size: 12px; padding: 6px 12px; border-radius: 8px; border: 1px solid {C_BORDER};"
        )
        self.btn_chat.clicked.connect(self._focus_input)
        tb_layout.addWidget(self.btn_chat)

        tb_layout.addStretch()

        # Utility Buttons
        btn_move = QLabel("✛")
        btn_move.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 14px; font-weight: 800; padding: 4px;")
        btn_move.setCursor(Qt.CursorShape.SizeAllCursor)
        tb_layout.addWidget(btn_move)

        btn_more = QPushButton("⋮")
        btn_more.setStyleSheet("background: transparent; color: #94a3b8; font-size: 16px; border: none;")
        tb_layout.addWidget(btn_more)

        btn_end = QPushButton("End")
        btn_end.setStyleSheet("background: #ef4444; color: #ffffff; font-weight: 700; font-size: 12px; padding: 5px 14px; border-radius: 8px; border: none;")
        btn_end.clicked.connect(self.hide_overlay)
        tb_layout.addWidget(btn_end)

        main_layout.addWidget(self.island_toolbar)

        # =====================================================================
        # ISLAND 2: Contextual Prompt Row & Waveform (Reference 2)
        # =====================================================================
        self.island_context = QFrame()
        self.island_context.setObjectName("IslandFrame")
        self.island_context.setStyleSheet(
            "QFrame#IslandFrame { background: rgba(22, 25, 33, 0.94); border: 1px solid #282e3e; border-radius: 10px; }"
        )
        ctx_layout = QHBoxLayout(self.island_context)
        ctx_layout.setContentsMargins(12, 6, 12, 6)
        ctx_layout.setSpacing(6)

        # Equalizer Waveform
        self.waveform = QtWaveformWidget()
        ctx_layout.addWidget(self.waveform)
        ctx_layout.addSpacing(6)

        # Keyword Chip Pills
        self.chip_container = QHBoxLayout()
        self.chip_container.setSpacing(6)
        sample_chips = ["How would you", "design a rate", "limiter for a", "public API?"]
        for chip_text in sample_chips:
            chip = QLabel(chip_text)
            chip.setStyleSheet(
                "background: rgba(40, 46, 61, 0.7); color: #cbd5e1; font-size: 11.5px; font-weight: 500; padding: 4px 10px; border-radius: 6px;"
            )
            self.chip_container.addWidget(chip)
        ctx_layout.addLayout(self.chip_container)
        ctx_layout.addStretch()

        btn_clear = QPushButton("Clear ⌘⇧⌫")
        btn_clear.setStyleSheet("background: transparent; color: #94a3b8; font-size: 11.5px; font-weight: 600; border: none;")
        btn_clear.clicked.connect(self._clear_question)
        ctx_layout.addWidget(btn_clear)

        main_layout.addWidget(self.island_context)

        # =====================================================================
        # ISLAND 3: Main Answer Card Surface (Reference 2)
        # =====================================================================
        self.island_answer = QFrame()
        self.island_answer.setObjectName("IslandFrame")
        self.island_answer.setStyleSheet(
            "QFrame#IslandFrame { background: rgba(22, 25, 33, 0.96); border: 1px solid #282e3e; border-radius: 14px; }"
        )
        ans_layout = QVBoxLayout(self.island_answer)
        ans_layout.setContentsMargins(18, 14, 18, 16)
        ans_layout.setSpacing(12)

        # Mini Top Nav Bar (<, >, Clear, Expand)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        btn_prev = QPushButton("←")
        btn_prev.setFixedSize(26, 22)
        btn_prev.setStyleSheet("background: rgba(255,255,255,0.06); color: #94a3b8; border-radius: 4px; border: none;")
        btn_next = QPushButton("→")
        btn_next.setFixedSize(26, 22)
        btn_next.setStyleSheet("background: rgba(255,255,255,0.06); color: #94a3b8; border-radius: 4px; border: none;")
        top_bar.addWidget(btn_prev)
        top_bar.addWidget(btn_next)
        top_bar.addStretch()

        btn_clear2 = QPushButton("Clear  ⌘⌫")
        btn_clear2.setStyleSheet("background: rgba(255,255,255,0.06); color: #94a3b8; font-size: 11.5px; padding: 3px 10px; border-radius: 4px; border: none;")
        btn_clear2.clicked.connect(self._clear_question)
        top_bar.addWidget(btn_clear2)

        ans_layout.addLayout(top_bar)

        # Question Row with Speech Bubble Icon and Copy
        q_row = QHBoxLayout()
        self.lbl_q_speech = QLabel("💬 Question:")
        self.lbl_q_speech.setStyleSheet(f"color: {C_CYAN}; font-size: 13.5px; font-weight: 700;")
        self.lbl_q_text = QLabel("How would you design a rate limiter for a public API?")
        self.lbl_q_text.setStyleSheet("color: #f8fafc; font-size: 13.5px; font-weight: 600;")
        self.lbl_q_text.setWordWrap(True)
        q_row.addWidget(self.lbl_q_speech)
        q_row.addWidget(self.lbl_q_text, 1)

        btn_copy_q = QPushButton("📋")
        btn_copy_q.setToolTip("Copy Question")
        btn_copy_q.setStyleSheet("background: transparent; color: #94a3b8; font-size: 14px; border: none;")
        btn_copy_q.clicked.connect(self._copy_question)
        q_row.addWidget(btn_copy_q)
        ans_layout.addLayout(q_row)

        # Answer Row with Gold Star Accent
        a_row = QHBoxLayout()
        self.lbl_a_star = QLabel("⭐ Answer:")
        self.lbl_a_star.setStyleSheet(f"color: {C_GOLD}; font-size: 14px; font-weight: 800;")
        self.lbl_a_text = QLabel("Token bucket per API key, stored in Redis.")
        self.lbl_a_text.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
        self.lbl_a_text.setWordWrap(True)
        a_row.addWidget(self.lbl_a_star)
        a_row.addWidget(self.lbl_a_text, 1)
        ans_layout.addLayout(a_row)

        # Bullet Points List
        self.bullets_box = QVBoxLayout()
        self.bullets_box.setSpacing(6)
        sample_bullets = [
            "• Refill logic: R tokens/sec up to a burst of B; each request decrements atomically with a Lua script.",
            "• On empty: reject with 429 and a Retry-After header.",
            "• Scaling: shard by key hash and keep hot counters in memory with an async flush."
        ]
        self.bullet_labels = []
        for b_text in sample_bullets:
            lbl_b = QLabel(b_text)
            lbl_b.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.45;")
            lbl_b.setWordWrap(True)
            self.bullets_box.addWidget(lbl_b)
            self.bullet_labels.append(lbl_b)
        ans_layout.addLayout(self.bullets_box)

        # Trade-off Paragraph
        self.lbl_tradeoff = QLabel("Trade-off: a sliding-window log is more precise but costs O(requests) memory.")
        self.lbl_tradeoff.setStyleSheet("color: #94a3b8; font-size: 12.5px; line-height: 1.4; margin-top: 4px;")
        self.lbl_tradeoff.setWordWrap(True)
        ans_layout.addWidget(self.lbl_tradeoff)

        # Code Container (collapsible/expandable if code exists)
        self.code_frame = QFrame()
        self.code_frame.setStyleSheet("background: #090c12; border: 1px solid #1e2433; border-radius: 8px; padding: 10px;")
        cf_layout = QVBoxLayout(self.code_frame)
        cf_layout.setContentsMargins(10, 8, 10, 8)
        cf_head = QHBoxLayout()
        lbl_code_lang = QLabel("REDIS LUA")
        lbl_code_lang.setStyleSheet(f"color: {C_CYAN}; font-size: 11px; font-weight: 700;")
        btn_copy_code = QPushButton("Copy Code")
        btn_copy_code.setStyleSheet("background: transparent; color: #94a3b8; font-size: 11px; font-weight: 600; border: none;")
        btn_copy_code.clicked.connect(self._copy_code)
        cf_head.addWidget(lbl_code_lang)
        cf_head.addStretch()
        cf_head.addWidget(btn_copy_code)
        cf_layout.addLayout(cf_head)

        self.txt_code = QLabel("local key = KEYS[1]\nlocal limit = tonumber(ARGV[1])\nlocal current = tonumber(redis.call('get', key) or '0')\nif current + 1 > limit then return 0 end\nredis.call('incrby', key, 1)\nreturn 1")
        self.txt_code.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11.5px; color: #38bdf8; line-height: 1.4;")
        cf_layout.addWidget(self.txt_code)
        ans_layout.addWidget(self.code_frame)

        # Footer Row (Answer · 19:01 👍 👎)
        foot_row = QHBoxLayout()
        self.lbl_foot = QLabel("Answer • 19:01")
        self.lbl_foot.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11.5px;")
        foot_row.addWidget(self.lbl_foot)
        foot_row.addStretch()
        btn_up = QPushButton("👍")
        btn_up.setStyleSheet("background: transparent; border: none; font-size: 13px;")
        btn_dn = QPushButton("👎")
        btn_dn.setStyleSheet("background: transparent; border: none; font-size: 13px;")
        foot_row.addWidget(btn_up)
        foot_row.addWidget(btn_dn)
        ans_layout.addLayout(foot_row)

        # Bottom Input Bar
        in_row = QHBoxLayout()
        self.input_custom = QLineEdit()
        self.input_custom.setPlaceholderText("Ask a follow-up or custom question...")
        self.input_custom.setStyleSheet(
            f"background: #11141c; color: #ffffff; border: 1px solid #282e3d; border-radius: 8px; padding: 7px 12px; font-size: 12.5px;"
        )
        self.input_custom.returnPressed.connect(self._send_custom_query)
        in_row.addWidget(self.input_custom, 1)

        btn_send = QPushButton("Ask")
        btn_send.setStyleSheet(
            f"background: {C_CYAN}; color: #0b0d11; font-weight: 700; font-size: 12px; padding: 7px 14px; border-radius: 8px; border: none;"
        )
        btn_send.clicked.connect(self._send_custom_query)
        in_row.addWidget(btn_send)
        ans_layout.addLayout(in_row)

        main_layout.addWidget(self.island_answer)

    # -------------------------------------------------------------------------
    # Dragging Window Behavior
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            if self.on_position_changed:
                self.on_position_changed(new_pos.x(), new_pos.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()

    # -------------------------------------------------------------------------
    # Public Controller API (Backward Compatible)
    # -------------------------------------------------------------------------
    def launch(self, parent=None, start_visible: bool = False):
        if start_visible:
            self.show_overlay()

    def show_overlay(self):
        self._is_visible = True
        self.show()
        self.raise_()
        self._apply_win32_styles()

    def hide_overlay(self):
        self._is_visible = False
        self.hide()
        if self.on_close:
            self.on_close()

    def toggle_visibility(self):
        if self._is_visible:
            self.hide_overlay()
        else:
            self.show_overlay()

    @property
    def is_visible(self) -> bool:
        return self.isVisible()

    def get_window_rect(self):
        if not self.isVisible():
            return None
        geo = self.geometry()
        return (geo.left(), geo.top(), geo.right(), geo.bottom())

    def set_state(self, state: str, presentation: Optional[Any] = None, solve_id: int = 0):
        if state == "capturing":
            self.lbl_a_text.setText("Capturing active screen region...")
        elif state == "ocr":
            self.lbl_a_text.setText("Running Windows OCR recognition...")
        elif state == "thinking":
            self.lbl_a_text.setText("Consulting local Ollama neural model...")
        elif state in ("answer", "ready"):
            if presentation:
                self.update_answer(presentation)
        elif state == "error":
            if presentation:
                self.update_answer(presentation)
            else:
                self.lbl_a_text.setText("Could not determine answer.")
        self.show_overlay()

    def append_stream_token(self, token: str, solve_id: int = 0):
        curr = self.lbl_a_text.text()
        if "Consulting" in curr or "Analyzing" in curr:
            self.lbl_a_text.setText(token)
        else:
            self.lbl_a_text.setText(curr + token)

    def append_transcript_segment(self, segment: Any):
        txt = getattr(segment, "text", str(segment))
        self.lbl_q_text.setText(f"[Audio]: {txt}")

    def append_ai_answer(self, full_ans: str):
        self.lbl_a_text.setText(full_ans)
        self.show_overlay()

    def copy_answer_to_clipboard(self):
        cb = QApplication.clipboard()
        if cb:
            ans = self.lbl_a_text.text()
            if self.code_frame.isVisible():
                ans += f"\n\n```\n{self.txt_code.text()}\n```"
            cb.setText(ans)

    def destroy(self):
        self.close()

    def update_audio_status(self, is_capturing: bool, is_paused: bool):
        """Updates HUD audio indicator and caption safely."""
        if is_capturing:
            if is_paused:
                self.lbl_q_text.setText("Live Audio Capture: Paused")
                self.lbl_a_text.setText("Audio capture is paused. Press Alt + L or click Resume.")
            else:
                self.lbl_q_text.setText("Live Audio Capture: Active (Listening...)")
                self.lbl_a_text.setText("Listening for conversation questions & speech...")
        else:
            self.lbl_q_text.setText("Ready for next question.")
            self.lbl_a_text.setText("Hover or press Alt + / over question.")

    def update_answer(self, presented_answer: Any):
        """Updates the HUD with structured answer data."""
        if hasattr(presented_answer, "question_text") and presented_answer.question_text:
            self.lbl_q_text.setText(presented_answer.question_text)
        elif hasattr(presented_answer, "raw_ocr_text") and presented_answer.raw_ocr_text:
            snippet = presented_answer.raw_ocr_text.strip()[:180]
            self.lbl_q_text.setText(f"Captured: {snippet}..." if snippet else "Captured screen text")

        q_type = getattr(presented_answer, "question_type", "")
        if q_type in ("uncertain", "error"):
            self.lbl_a_star.setText("⚠️ Notice:" if q_type == "uncertain" else "❗ Error:")
            self.lbl_a_star.setStyleSheet(f"color: {C_AMBER if q_type == 'uncertain' else C_DANGER}; font-size: 14px; font-weight: 800;")
        else:
            self.lbl_a_star.setText("⭐ Answer:")
            self.lbl_a_star.setStyleSheet(f"color: {C_GOLD}; font-size: 14px; font-weight: 800;")

        if hasattr(presented_answer, "headline") and presented_answer.headline:
            self.lbl_a_text.setText(presented_answer.headline)
        elif hasattr(presented_answer, "direct_answer") and presented_answer.direct_answer:
            self.lbl_a_text.setText(presented_answer.direct_answer)
        elif hasattr(presented_answer, "answer_text") and presented_answer.answer_text:
            self.lbl_a_text.setText(presented_answer.answer_text)

        if hasattr(presented_answer, "explanation") and presented_answer.explanation:
            self.lbl_tradeoff.setText(presented_answer.explanation)
        elif hasattr(presented_answer, "explanation_paragraphs") and presented_answer.explanation_paragraphs:
            self.lbl_tradeoff.setText("\n\n".join(presented_answer.explanation_paragraphs))

        if hasattr(presented_answer, "code_snippet") and presented_answer.code_snippet:
            self.txt_code.setText(presented_answer.code_snippet)
            self.code_frame.show()
        elif hasattr(presented_answer, "code") and presented_answer.code:
            self.txt_code.setText(presented_answer.code)
            self.code_frame.show()
        else:
            self.code_frame.hide()

        self.lbl_foot.setText(f"Answer • {time.strftime('%H:%M:%S')}")
        self.show_overlay()

    def start_solve(self) -> int:
        self.lbl_a_star.setText("⭐ Answer:")
        self.lbl_a_star.setStyleSheet(f"color: {C_GOLD}; font-size: 14px; font-weight: 800;")
        self.lbl_a_text.setText("Analyzing question with local AI...")
        self.show_overlay()
        return int(time.time())

    # -------------------------------------------------------------------------
    # Internal Action Handlers
    # -------------------------------------------------------------------------
    def _trigger_retry(self):
        if self.on_retry:
            self.on_retry()

    def _trigger_screenshot(self):
        if self.on_trigger_screenshot:
            self.on_trigger_screenshot()

    def _focus_input(self):
        self.input_custom.setFocus()

    def _clear_question(self):
        self.lbl_q_text.setText("Ready for next question.")
        self.lbl_a_text.setText("Hover or press Alt + / over question.")
        self.code_frame.hide()

    def _copy_question(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.lbl_q_text.text())

    def _copy_code(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.txt_code.text())

    def _send_custom_query(self):
        text = self.input_custom.text().strip()
        if text and self.on_ask_custom:
            self.on_ask_custom(text)
            self.input_custom.clear()

