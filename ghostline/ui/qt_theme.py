"""
Ghostline Qt Design System — Microsoft Fluent 2 Dark Design Language.
Provides backward-compatible tokens, painter widgets, and QSS stylesheets.
"""

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy
from typing import Optional

from ghostline.ui.theme.tokens import *
from ghostline.ui.theme.builder import build_fluent_stylesheet
from ghostline.ui.theme.icons import get_fluent_icon, get_fluent_pixmap, get_app_icon

# Master QSS Stylesheet conforming to Microsoft Fluent 2
QT_MAIN_STYLESHEET = build_fluent_stylesheet()


# -----------------------------------------------------------------------------
# Microsoft Fluent 2 Toggle Switch Widget
# -----------------------------------------------------------------------------
class QtModernToggleSwitch(QWidget):
    """
    Smooth, anti-aliased Microsoft Fluent 2 toggle switch.
    Dimensions: 40x20px with pill radius (10px).
    Checked: Brand Fill (#115EA3) with white circular knob.
    Unchecked: Subtle surface (#292929) with border (#666666).
    """
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(40, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        r = h / 2.0

        if self._checked:
            track_color = QColor(BRAND_FILL)
            p.setBrush(QBrush(track_color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

            knob_radius = (h - 4.0) / 2.0
            knob_x = w - knob_radius - 2.5
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.drawEllipse(QRectF(knob_x - knob_radius, 2.0, knob_radius * 2.0, knob_radius * 2.0))
        else:
            track_color = QColor(SURFACE_INPUT)
            p.setBrush(QBrush(track_color))
            p.setPen(QColor(STROKE_CONTROL))
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

            knob_radius = (h - 6.0) / 2.0
            knob_x = knob_radius + 3.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(TEXT_SECONDARY)))
            p.drawEllipse(QRectF(knob_x - knob_radius, 3.0, knob_radius * 2.0, knob_radius * 2.0))

        p.end()


# -----------------------------------------------------------------------------
# Animated Audio Waveform Equalizer (Fluent Tone)
# -----------------------------------------------------------------------------
class QtWaveformWidget(QWidget):
    """
    Mini Fluent audio equalizer bars.
    """
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedSize(24, 16)
        self.bars = [0.4, 0.8, 1.0, 0.5]

    def set_levels(self, levels: list):
        self.bars = levels[:4]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(BRAND_TEXT)))

        w, h = self.width(), self.height()
        bar_w = 3.0
        spacing = 3.0

        for i, val in enumerate(self.bars):
            bar_h = max(3.0, h * float(val))
            x = i * (bar_w + spacing) + 1.0
            y = (h - bar_h) / 2.0
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)
        p.end()


# -----------------------------------------------------------------------------
# Microsoft Fluent 2 InfoBar Notification & Callout Widget
# -----------------------------------------------------------------------------
class FluentInfoBar(QFrame):
    """
    Microsoft Fluent 2 InfoBar notification / callout widget.
    Features:
    - 4px corner radius (RADIUS_CONTROL)
    - Status color fill at ~12% alpha
    - Subtle 1px border with status color at ~30% alpha
    - Fluent vector icon (info, checkmark, warning, dismiss)
    - Text in TEXT_PRIMARY (#FFFFFF)
    - Optional dismiss button with dismiss vector icon
    """
    closed = pyqtSignal()

    def __init__(
        self,
        severity: str = "info",
        title: str = "",
        message: str = "",
        closable: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("FluentInfoBar")
        self._severity = severity
        self._closable = closable

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Text container
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_PRIMARY}; background: transparent; border: none;")
        self.title_label.setWordWrap(True)
        if not title:
            self.title_label.hide()
        text_layout.addWidget(self.title_label)

        self.msg_label = QLabel(message)
        self.msg_label.setStyleSheet(f"font-size: 12.5px; font-weight: 400; color: {TEXT_PRIMARY}; background: transparent; border: none; line-height: 1.4;")
        self.msg_label.setWordWrap(True)
        self.msg_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(self.msg_label)

        layout.addLayout(text_layout, 1)

        # Close button
        if closable:
            self.btn_close = QPushButton()
            self.btn_close.setIcon(get_fluent_icon("dismiss", color=TEXT_SECONDARY, size=14))
            self.btn_close.setFixedSize(24, 24)
            self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_close.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.08);
                }
            """)
            self.btn_close.clicked.connect(self._on_close)
            layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)

        self.set_severity(severity, title, message)

    def set_severity(self, severity: str, title: Optional[str] = None, message: Optional[str] = None):
        self._severity = severity
        if title is not None:
            self.title_label.setText(title)
            self.title_label.setVisible(bool(title))
        if message is not None:
            self.msg_label.setText(message)

        if severity == "success":
            bg = "rgba(108, 203, 95, 0.12)"
            border = "rgba(108, 203, 95, 0.30)"
            icon = get_fluent_icon("checkmark", color=STATUS_SUCCESS_TEXT, size=16, filled=True)
        elif severity == "warning":
            bg = "rgba(251, 209, 97, 0.12)"
            border = "rgba(251, 209, 97, 0.30)"
            icon = get_fluent_icon("warning", color=STATUS_WARNING_TEXT, size=16, filled=False)
        elif severity in ("error", "danger"):
            bg = "rgba(197, 15, 31, 0.12)"
            border = "rgba(197, 15, 31, 0.30)"
            icon = get_fluent_icon("dismiss", color=STATUS_DANGER_TEXT, size=16, filled=True)
        else:  # info
            bg = "rgba(17, 94, 163, 0.14)"
            border = "rgba(88, 166, 255, 0.30)"
            icon = get_fluent_icon("info", color=BRAND_TEXT, size=16, filled=False)

        self.icon_label.setPixmap(icon.pixmap(18, 18))
        self.setStyleSheet(f"""
            QFrame#FluentInfoBar {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
        """)

    def _on_close(self):
        self.hide()
        self.closed.emit()

