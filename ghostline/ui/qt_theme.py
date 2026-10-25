"""
Ghostline Qt Design System — Modern Dark Charcoal Aesthetic for PyQt6.
Tokens, custom painter widgets, and comprehensive QSS stylesheets matching reference designs.
"""

from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient
from PyQt6.QtWidgets import QWidget

# -----------------------------------------------------------------------------
# Color Palette Tokens
# -----------------------------------------------------------------------------
C_BG_APP = "#111318"          # Deep canvas background
C_BG_SIDEBAR = "#161922"      # Clean navigation sidebar
C_BG_CARD = "#1c202a"         # Primary card surface
C_BG_CARD_HOVER = "#242a38"   # Interactive card hover
C_BG_CARD_ACTIVE = "#2c3446"  # Active / selected card container
C_BG_CODE = "#0a0d14"         # Deep code surface
C_BG_INPUT = "#151821"        # Input box surface

C_BORDER = "#282e3d"          # Subtle border
C_BORDER_LIGHT = "#353d52"    # Inner border
C_BORDER_ACCENT = "#38bdf8"   # Cyan accent border

C_CYAN = "#38bdf8"            # Primary brand accent
C_CYAN_HOVER = "#0284c7"
C_EMERALD = "#10b981"         # Success / Active green
C_AMBER = "#f59e0b"           # Warning / Thinking gold
C_DANGER = "#ef4444"          # Danger / Error coral
C_GOLD = "#facc15"            # Answer star accent

C_TEXT_PRIMARY = "#f8fafc"    # Bright white text
C_TEXT_SECONDARY = "#94a3b8"  # Slate secondary text
C_TEXT_MUTED = "#64748b"      # Muted metadata
C_TEXT_DIM = "#475569"

# -----------------------------------------------------------------------------
# Master QSS Stylesheet
# -----------------------------------------------------------------------------
QT_MAIN_STYLESHEET = f"""
QMainWindow, QDialog, QWidget#CentralWidget {{
    background-color: {C_BG_APP};
    color: {C_TEXT_PRIMARY};
    font-family: 'Segoe UI', -apple-system, sans-serif;
}}

/* Sidebar Styling */
QWidget#Sidebar {{
    background-color: {C_BG_SIDEBAR};
    border-right: 1px solid {C_BORDER};
}}

QPushButton#SidebarBtn {{
    background-color: transparent;
    color: {C_TEXT_SECONDARY};
    text-align: left;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    border: none;
}}

QPushButton#SidebarBtn:hover {{
    background-color: {C_BG_CARD_HOVER};
    color: {C_TEXT_PRIMARY};
}}

QPushButton#SidebarBtn:checked, QPushButton#SidebarBtn[active="true"] {{
    background-color: {C_BG_CARD_ACTIVE};
    color: {C_TEXT_PRIMARY};
    font-weight: 600;
}}

/* Cards and Panels */
QFrame#CardFrame {{
    background-color: {C_BG_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
}}

QFrame#CardFrame:hover {{
    border-color: {C_BORDER_LIGHT};
}}

QFrame#IslandFrame {{
    background-color: rgba(22, 25, 34, 0.95);
    border: 1px solid {C_BORDER};
    border-radius: 12px;
}}

/* Typography */
QLabel#HeaderTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {C_TEXT_PRIMARY};
}}

QLabel#SectionTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {C_TEXT_PRIMARY};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QLabel#CardTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {C_TEXT_PRIMARY};
}}

QLabel#CardDesc {{
    font-size: 13px;
    color: {C_TEXT_SECONDARY};
    line-height: 1.4;
}}

QLabel#BadgeText {{
    font-size: 12px;
    font-weight: 700;
    color: {C_CYAN};
}}

/* Buttons */
QPushButton#PrimaryBtn {{
    background-color: {C_CYAN};
    color: #0b0d11;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 18px;
    border-radius: 8px;
    border: none;
}}

QPushButton#PrimaryBtn:hover {{
    background-color: #7dd3fc;
}}

QPushButton#SecondaryBtn {{
    background-color: {C_BG_CARD_HOVER};
    color: {C_TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 500;
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid {C_BORDER};
}}

QPushButton#SecondaryBtn:hover {{
    background-color: {C_BG_CARD_ACTIVE};
    border-color: {C_BORDER_LIGHT};
}}

QPushButton#WhitePillBtn {{
    background-color: #ffffff;
    color: #0f1117;
    font-size: 12px;
    font-weight: 700;
    padding: 6px 16px;
    border-radius: 14px;
    border: none;
}}

QPushButton#WhitePillBtn:hover {{
    background-color: #e2e8f0;
}}

QPushButton#PillChipBtn {{
    background-color: rgba(0, 0, 0, 0.3);
    color: {C_TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 8px;
    border: 1px solid {C_BORDER};
}}

QPushButton#PillChipBtn:hover {{
    border-color: {C_CYAN};
    color: {C_CYAN};
}}

/* Dropdowns / ComboBox */
QComboBox {{
    background-color: {C_BG_CARD_HOVER};
    color: {C_TEXT_PRIMARY};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
}}

QComboBox:hover {{
    border-color: {C_BORDER_LIGHT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {C_BG_CARD};
    color: {C_TEXT_PRIMARY};
    border: 1px solid {C_BORDER};
    selection-background-color: {C_BG_CARD_ACTIVE};
    selection-color: {C_TEXT_PRIMARY};
    border-radius: 8px;
    padding: 4px;
}}

/* Text Inputs */
QLineEdit, QTextEdit {{
    background-color: {C_BG_INPUT};
    color: {C_TEXT_PRIMARY};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}}

QLineEdit:focus, QTextEdit:focus {{
    border-color: {C_CYAN};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {C_BORDER_LIGHT};
    min-height: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {C_TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

# -----------------------------------------------------------------------------
# Modern Animated Toggle Switch Widget (Matching Reference 3)
# -----------------------------------------------------------------------------
class QtModernToggleSwitch(QWidget):
    """
    Smooth, anti-aliased, modern iOS/macOS toggle switch.
    """
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(44, 24)
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

        w, h = self.width(), self.height()
        r = h / 2.0

        # Background track
        track_color = QColor(C_EMERALD) if self._checked else QColor("#2d3342")
        p.setBrush(QBrush(track_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # Knob
        knob_radius = (h - 4) / 2.0
        knob_x = (w - knob_radius - 3) if self._checked else (knob_radius + 3)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QRectF(knob_x - knob_radius, 2, knob_radius * 2, knob_radius * 2))
        p.end()

# -----------------------------------------------------------------------------
# Animated Audio Waveform Equalizer (Matching Reference 2)
# -----------------------------------------------------------------------------
class QtWaveformWidget(QWidget):
    """
    Mini green waveform audio equalizer bars matching Reference 2.
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
        p.setBrush(QBrush(QColor(C_EMERALD)))

        w, h = self.width(), self.height()
        bar_w = 3.0
        spacing = 3.0

        for i, val in enumerate(self.bars):
            bar_h = max(3.0, h * float(val))
            x = i * (bar_w + spacing) + 1.0
            y = (h - bar_h) / 2.0
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)
        p.end()
