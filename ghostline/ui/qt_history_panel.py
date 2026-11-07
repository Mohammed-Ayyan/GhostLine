"""
Ghostline — On-Demand History HUD Overlay (PyQt6)
Provides dedicated, searchable, filterable history review across both Screen and Audio sessions.
Opened exclusively on-demand via Alt + Shift + A (configurable).
"""

import time
from typing import Optional, Callable, Dict, Any, List

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea, QSizePolicy
)

from ghostline.ui.qt_theme import (
    QT_MAIN_STYLESHEET,
    C_BG_APP, C_BG_SIDEBAR, C_BG_CARD, C_BG_CARD_HOVER, C_BG_CARD_ACTIVE,
    C_BORDER, C_BORDER_LIGHT, C_BORDER_ACCENT, C_CYAN, C_EMERALD,
    C_AMBER, C_DANGER, C_GOLD, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_MUTED
)
from ghostline.core.capture_exclusion import set_capture_exclusion
from ghostline.core.history_store import get_history_store


class HistoryCardWidget(QFrame):
    """Visual interaction card for past screen solves or audio transcripts."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("HistoryCard")
        is_screen = (self.entry.get("source") == "screen")
        self.setStyleSheet(f"""
            QFrame#HistoryCard {{
                background: {C_BG_CARD};
                border: 1px solid {C_BORDER};
                border-left: 3px solid {'#10b981' if is_screen else '#38bdf8'};
                border-radius: 8px;
                padding: 10px;
            }}
            QFrame#HistoryCard:hover {{
                border-color: {C_BORDER_LIGHT};
                background: {C_BG_CARD_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header: Source Badge + Time + Copy Button
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        src_badge = QLabel("SCREEN SOLVE" if is_screen else "AUDIO / CALL")
        src_badge.setStyleSheet(f"""
            background: {'rgba(16, 185, 129, 0.15)' if is_screen else 'rgba(56, 189, 248, 0.15)'};
            color: {'#10b981' if is_screen else '#38bdf8'};
            font-size: 10px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 4px;
        """)
        header_row.addWidget(src_badge)

        time_lbl = QLabel(self.entry.get("time_str", ""))
        time_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        header_row.addWidget(time_lbl)

        if self.entry.get("badge") and is_screen:
            badge_lbl = QLabel(f"Option {self.entry['badge']}")
            badge_lbl.setStyleSheet("background: #10b981; color: #090d16; font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 4px;")
            header_row.addWidget(badge_lbl)

        header_row.addStretch()

        self.btn_copy = QPushButton("📋 Copy")
        self.btn_copy.setFixedSize(64, 22)
        self.btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                color: {C_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.12);
                color: {C_TEXT_PRIMARY};
            }}
        """)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        header_row.addWidget(self.btn_copy)
        layout.addLayout(header_row)

        # Content: Question / Utterance
        q_text = self.entry.get("question") or self.entry.get("original_text", "")
        if q_text:
            lbl_q = QLabel(q_text)
            lbl_q.setWordWrap(True)
            lbl_q.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 12.5px; font-weight: 600;")
            lbl_q.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(lbl_q)

        # Supporting passage if present
        passage = self.entry.get("supporting_passage", "")
        if passage:
            lbl_pass = QLabel(passage)
            lbl_pass.setWordWrap(True)
            lbl_pass.setStyleSheet("background: #090c12; border: 1px solid #1e2433; border-radius: 4px; padding: 4px; font-family: Consolas; font-size: 11px; color: #38bdf8;")
            lbl_pass.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(lbl_pass)

        # Answer / Explanation
        ans_text = self.entry.get("answer", "")
        if ans_text:
            ans_box = QFrame()
            ans_box.setStyleSheet(f"background: rgba(0, 0, 0, 0.25); border: 1px solid {C_BORDER}; border-radius: 6px; padding: 6px;")
            ab_layout = QVBoxLayout(ans_box)
            ab_layout.setContentsMargins(4, 4, 4, 4)
            lbl_ans = QLabel(ans_text)
            lbl_ans.setWordWrap(True)
            lbl_ans.setStyleSheet(f"color: {'#34d399' if is_screen else '#7dd3fc'}; font-size: 12px; font-weight: 500;")
            lbl_ans.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            ab_layout.addWidget(lbl_ans)

            # Code snippet if present
            code = self.entry.get("code_snippet")
            if code:
                lbl_code = QLabel(code)
                lbl_code.setWordWrap(True)
                lbl_code.setStyleSheet("font-family: Consolas; font-size: 11.5px; color: #f8fafc; background: #030712; padding: 6px; border-radius: 4px;")
                lbl_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                ab_layout.addWidget(lbl_code)

            layout.addWidget(ans_box)

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        parts = []
        if self.entry.get("question"):
            parts.append(f"Question: {self.entry['question']}")
        if self.entry.get("answer"):
            parts.append(f"Answer: {self.entry['answer']}")
        if self.entry.get("code_snippet"):
            parts.append(f"Code:\n{self.entry['code_snippet']}")
        if self.entry.get("original_text"):
            parts.append(f"Transcript: {self.entry['original_text']}")
        full_text = "\n\n".join(parts)
        if full_text:
            clipboard.setText(full_text)
            self.btn_copy.setText("✓ Copied")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Copy"))


class QtHistoryHudOverlay(QWidget):
    """
    On-Demand Floating History HUD Window.
    Mutual exclusivity managed by HudManager.
    """

    def __init__(
        self,
        on_close: Optional[Callable[[], None]] = None,
        opacity: float = 0.94,
        width: int = 580,
        height: int = 680,
        always_on_top: bool = True,
        exclude_from_capture: bool = True,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.on_close_cb = on_close
        self.opacity_val = opacity
        self.always_on_top = always_on_top
        self.exclude_from_capture = exclude_from_capture
        self.active_filter = "all"
        self._drag_pos = QPoint()

        self._setup_window_flags(width, height)
        self._build_ui()
        self.refresh_history()

    def _setup_window_flags(self, width: int, height: int):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(self.opacity_val)
        self.resize(width, height)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("HistoryContainer")
        container.setStyleSheet(f"""
            QFrame#HistoryContainer {{
                background: {C_BG_APP};
                border: 1px solid {C_BORDER_ACCENT};
                border-radius: 12px;
            }}
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        # Title Bar / Drag Header
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)

        lbl_icon = QLabel("📜")
        lbl_icon.setStyleSheet("font-size: 16px;")
        title_bar.addWidget(lbl_icon)

        lbl_title = QLabel("Ghostline Interaction History")
        lbl_title.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 14px; font-weight: 700;")
        title_bar.addWidget(lbl_title)

        title_bar.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                color: {C_TEXT_SECONDARY};
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C_DANGER};
                color: #ffffff;
                border-color: {C_DANGER};
            }}
        """)
        btn_close.clicked.connect(self.hide_panel)
        title_bar.addWidget(btn_close)
        c_layout.addLayout(title_bar)

        # Filter Tabs & Search Bar
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.btn_filter_all = QPushButton("All")
        self.btn_filter_screen = QPushButton("🖥 Screen")
        self.btn_filter_audio = QPushButton("🎙 Audio")

        for b, f in [(self.btn_filter_all, "all"), (self.btn_filter_screen, "screen"), (self.btn_filter_audio, "audio")]:
            b.setCheckable(True)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.clicked.connect(lambda checked, mode=f: self._set_filter(mode))
            controls_row.addWidget(b)

        self.btn_filter_all.setChecked(True)
        self._update_filter_button_styles()

        controls_row.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search history...")
        self.txt_search.setFixedWidth(180)
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background: #181818;
                border: 1px solid #6E6E6E;
                border-radius: 6px;
                padding: 5px 8px;
                color: #FFFFFF;
                font-size: 11px;
                placeholder-text-color: #9E9E9E;
            }}
            QLineEdit:hover {{
                border-color: #999999;
                background: #222222;
            }}
            QLineEdit:focus {{
                border: 2px solid #58A6FF;
                background: #161616;
            }}
        """)
        self.txt_search.textChanged.connect(self._on_search_changed)
        controls_row.addWidget(self.txt_search)

        c_layout.addLayout(controls_row)

        # Scroll Area for Interaction Cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255, 255, 255, 0.3);
            }}
        """)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_container)
        c_layout.addWidget(self.scroll)

        # Footer Actions
        footer = QHBoxLayout()
        self.lbl_count = QLabel("0 entries")
        self.lbl_count.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
        footer.addWidget(self.lbl_count)

        footer.addStretch()

        btn_clear = QPushButton("🗑 Clear History")
        btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                color: {C_TEXT_MUTED};
                font-size: 11px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: rgba(239, 68, 68, 0.1);
                border-color: {C_DANGER};
                color: {C_DANGER};
            }}
        """)
        btn_clear.clicked.connect(self._clear_history)
        footer.addWidget(btn_clear)

        c_layout.addLayout(footer)
        root.addWidget(container)

    def _update_filter_button_styles(self):
        for b, mode in [(self.btn_filter_all, "all"), (self.btn_filter_screen, "screen"), (self.btn_filter_audio, "audio")]:
            is_active = (self.active_filter == mode)
            b.setChecked(is_active)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(56, 189, 248, 0.2)' if is_active else 'rgba(255, 255, 255, 0.05)'};
                    border: 1px solid {'#38bdf8' if is_active else C_BORDER};
                    border-radius: 6px;
                    color: {'#38bdf8' if is_active else C_TEXT_SECONDARY};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{
                    border-color: {'#38bdf8' if is_active else C_BORDER_LIGHT};
                }}
            """)

    def _set_filter(self, mode: str):
        self.active_filter = mode
        self._update_filter_button_styles()
        self.refresh_history()

    def _on_search_changed(self, text: str):
        self.refresh_history()

    def refresh_history(self):
        """Clears and re-populates history cards from SessionHistoryStore."""
        # Remove old cards
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        store = get_history_store()
        query = self.txt_search.text()
        entries = store.get_entries(mode_filter=self.active_filter, search_query=query, limit=100)

        self.lbl_count.setText(f"{len(entries)} entries")

        if not entries:
            empty_lbl = QLabel("No interaction history found.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 12px; padding: 40px;")
            self.cards_layout.insertWidget(0, empty_lbl)
            return

        for idx, entry in enumerate(entries):
            card = HistoryCardWidget(entry)
            self.cards_layout.insertWidget(idx, card)

    def _clear_history(self):
        get_history_store().clear()
        self.refresh_history()

    def launch(self, parent=None, start_visible: bool = False):
        if parent:
            self.setParent(parent)
        if start_visible:
            self.show_panel()

    def show_panel(self):
        self.refresh_history()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_panel(self):
        self.hide()
        if self.on_close_cb:
            self.on_close_cb()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide_panel()
        else:
            self.show_panel()

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
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_panel()
            event.accept()
        else:
            super().keyPressEvent(event)
