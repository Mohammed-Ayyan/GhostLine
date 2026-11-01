"""
Ghostline Qt Design System — Microsoft Fluent 2 Dark Design Language.
Provides backward-compatible tokens, painter widgets, and QSS stylesheets.
"""

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import QWidget

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
