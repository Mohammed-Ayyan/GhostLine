"""
Ghostline Microsoft Fluent 2 Design System Package.
Exposes design tokens, icon providers, stylesheet builders, theme application routines,
and maintains full backward-compatibility for legacy theme consumers.
"""

import sys
import ctypes
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QFont, QFontDatabase

# Legacy tokens and Tkinter helpers for backward compatibility
try:
    from ghostline.ui.legacy_theme import *
except Exception:
    pass

# Fluent 2 Design System tokens, icons, and stylesheet builder
from ghostline.ui.theme.tokens import *
from ghostline.ui.theme.icons import get_fluent_icon, get_fluent_pixmap, get_app_icon
from ghostline.ui.theme.builder import build_fluent_stylesheet


def resolve_system_font() -> str:
    """Detects available Fluent fonts, preferring Segoe UI Variable Text with Segoe UI fallback."""
    families = set(QFontDatabase.families())
    if "Segoe UI Variable Text" in families:
        return "Segoe UI Variable Text"
    if "Segoe UI" in families:
        return "Segoe UI"
    return "Arial"


def apply_dark_title_bar(window: QWidget) -> bool:
    """Enables Windows 11 immersive dark mode on standard window title chrome via DWM."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(window.winId())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
        if res != 0:
            # Fallback for Windows 10 build 1809+
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        return res == 0
    except Exception:
        return False


def apply_fluent_theme(app: Optional[QApplication] = None) -> None:
    """Applies the master Fluent 2 Dark theme and resolved typography to the QApplication."""
    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    # 1. Force predictable cross-platform Fusion style
    app.setStyle("Fusion")

    # 2. Apply comprehensive dark QPalette matching Fluent 2 Dark tokens
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1F1F1F"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#292929"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1F1F1F"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#333333"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#292929"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#115EA3"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    # 3. Resolve and apply primary font family
    font_name = resolve_system_font()
    font = QFont(font_name, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # 4. Apply master Fluent 2 stylesheet
    stylesheet = build_fluent_stylesheet()
    app.setStyleSheet(stylesheet)


# =============================================================================
# High-Visibility Fluent 2 Form Controls Styling Helper
# =============================================================================
STYLE_LINE_EDIT = f"""
    QLineEdit {{
        background-color: {SURFACE_INPUT};
        color: #FFFFFF;
        border: 1.5px solid {STROKE_CONTROL};
        border-radius: {RADIUS_CONTROL}px;
        padding: 5px 10px;
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 13px;
        placeholder-text-color: {TEXT_PLACEHOLDER};
        selection-background-color: {BRAND_FILL};
        selection-color: #FFFFFF;
    }}
    QLineEdit:hover {{
        background-color: {SURFACE_INPUT_HOVER};
        border: 1.5px solid #B0B0B0;
    }}
    QLineEdit:focus {{
        border: 2px solid {BRAND_TEXT};
        background-color: #0F141C;
    }}
    QLineEdit:disabled {{
        background-color: #181818;
        color: {TEXT_DISABLED};
        border: 1px solid #3D3D3D;
    }}
    QLineEdit:read-only {{
        background-color: #181818;
        color: {TEXT_SECONDARY};
        border: 1.5px solid #555555;
    }}
"""

STYLE_TEXT_EDIT = f"""
    QTextEdit, QPlainTextEdit {{
        background-color: {SURFACE_INPUT};
        color: #FFFFFF;
        border: 1.5px solid {STROKE_CONTROL};
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 10px;
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 13px;
        placeholder-text-color: {TEXT_PLACEHOLDER};
        selection-background-color: {BRAND_FILL};
        selection-color: #FFFFFF;
    }}
    QTextEdit:hover, QPlainTextEdit:hover {{
        background-color: {SURFACE_INPUT_HOVER};
        border: 1.5px solid #B0B0B0;
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {BRAND_TEXT};
        background-color: #0F141C;
    }}
    QTextEdit:disabled, QPlainTextEdit:disabled {{
        background-color: #181818;
        color: {TEXT_DISABLED};
        border: 1px solid #3D3D3D;
    }}
    QTextEdit:read-only, QPlainTextEdit:read-only {{
        background-color: #181818;
        color: {TEXT_SECONDARY};
        border: 1.5px solid #555555;
    }}
"""

STYLE_COMBO_BOX = f"""
    QComboBox {{
        background-color: {SURFACE_INPUT};
        color: #FFFFFF;
        border: 1.5px solid {STROKE_CONTROL};
        border-radius: {RADIUS_CONTROL}px;
        padding: 4px 10px;
        font-family: {FONT_FAMILY_PRIMARY};
        font-size: 13px;
        min-height: 24px;
    }}
    QComboBox:hover {{
        background-color: {SURFACE_INPUT_HOVER};
        border: 1.5px solid #B0B0B0;
    }}
    QComboBox:focus {{
        border: 2px solid {BRAND_TEXT};
        background-color: #0F141C;
    }}
    QComboBox:disabled {{
        background-color: #181818;
        color: {TEXT_DISABLED};
        border: 1px solid #3D3D3D;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 26px;
        border-left: 1px solid {STROKE_CARD};
    }}
    QComboBox QAbstractItemView {{
        background-color: {SURFACE_CARD};
        color: #FFFFFF;
        border: 1.5px solid {STROKE_CONTROL};
        border-radius: {RADIUS_CONTROL}px;
        padding: 4px;
        selection-background-color: {BRAND_FILL};
        selection-color: #FFFFFF;
    }}
"""


def apply_input_theme(widget: QWidget) -> None:
    """Applies high-visibility Microsoft Fluent 2 Dark form styling to an input widget."""
    from PyQt6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QComboBox
    if isinstance(widget, QLineEdit):
        widget.setStyleSheet(STYLE_LINE_EDIT)
    elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
        widget.setStyleSheet(STYLE_TEXT_EDIT)
    elif isinstance(widget, QComboBox):
        widget.setStyleSheet(STYLE_COMBO_BOX)
