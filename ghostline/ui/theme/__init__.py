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
