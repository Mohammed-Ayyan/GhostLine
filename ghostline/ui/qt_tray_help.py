"""
Ghostline — System Tray Icon Instructions & Taskbar Pinning Card.
Supports Windows 11 and Windows 10 specific instruction text,
direct URI navigation to Windows Taskbar Settings (ms-settings:taskbar),
and dismissal persistence.
"""

import sys
from typing import Optional, Callable, Any, Tuple

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from ghostline.config import save_config
from ghostline.ui.theme.tokens import (
    SURFACE_CARD, SURFACE_INPUT, SURFACE_CARD_HOVER, STROKE_CARD,
    STROKE_CONTROL, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BRAND_TEXT, BRAND_FILL, RADIUS_CARD, RADIUS_CONTROL
)
from ghostline.ui.theme.icons import get_fluent_icon


def open_taskbar_settings():
    """
    Opens Windows Taskbar Settings using the documented ms-settings:taskbar URI.
    Falls back to ms-settings:personalization if taskbar URI is unsupported.
    """
    url_taskbar = QUrl("ms-settings:taskbar")
    ok = QDesktopServices.openUrl(url_taskbar)
    if not ok:
        QDesktopServices.openUrl(QUrl("ms-settings:personalization"))


def get_windows_tray_instructions() -> Tuple[str, str]:
    """
    Detects Windows version (Win 11 build >= 22000 vs Win 10)
    and returns official instructions per Microsoft documentation.
    """
    is_win11 = False
    try:
        build_num = sys.getwindowsversion().build
        is_win11 = (build_num >= 22000)
    except Exception:
        pass

    if is_win11:
        headline = "Show Ghostline's tray icon on Windows 11"
        text = (
            "Open Settings → Personalization → Taskbar → Other system tray icons → turn Ghostline ON. "
            "Or click the ^ arrow near the clock and drag Ghostline's icon onto the taskbar."
        )
    else:
        headline = "Show Ghostline's tray icon on Windows 10"
        text = (
            "Settings → Personalization → Taskbar → Select which icons appear on the taskbar → turn Ghostline ON, "
            "or drag it from the ^ overflow."
        )
    return headline, text


class QtTrayHelpCard(QFrame):
    """
    Self-contained help card explaining how to make Ghostline's tray icon always visible.
    """
    def __init__(
        self,
        config: Any,
        parent: Optional[QWidget] = None,
        show_dismiss: bool = True,
        on_dismiss: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.config = config
        self.on_dismiss = on_dismiss
        self.setObjectName("CardFrame")
        self.setStyleSheet(f"""
            QFrame#CardFrame {{
                background-color: {SURFACE_CARD};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_CARD}px;
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header with icon and title
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(get_fluent_icon("info", color=BRAND_TEXT, size=18).pixmap(18, 18))
        header_row.addWidget(self.icon_lbl)

        headline, instructions = get_windows_tray_instructions()
        self.title_lbl = QLabel(headline)
        self.title_lbl.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        header_row.addWidget(self.title_lbl, 1)
        layout.addLayout(header_row)

        # Body text
        self.desc_lbl = QLabel(instructions)
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        layout.addWidget(self.desc_lbl)

        # Action row
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self.btn_open_settings = QPushButton("Open taskbar settings")
        self.btn_open_settings.setObjectName("BtnOpenTaskbarSettings")
        self.btn_open_settings.setFixedHeight(32)
        self.btn_open_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_settings.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border-color: {BRAND_TEXT};
                background-color: {SURFACE_CARD_HOVER};
            }}
        """)
        self.btn_open_settings.clicked.connect(open_taskbar_settings)
        action_row.addWidget(self.btn_open_settings)

        if show_dismiss:
            self.chk_dismiss = QCheckBox("Don't show again")
            self.chk_dismiss.setChecked(getattr(self.config, "tray_help_card_dismissed", False))
            self.chk_dismiss.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 12px;")
            self.chk_dismiss.toggled.connect(self._on_dismiss_toggled)
            action_row.addWidget(self.chk_dismiss)

        action_row.addStretch()
        layout.addLayout(action_row)

    def _on_dismiss_toggled(self, checked: bool):
        if self.config:
            self.config.tray_help_card_dismissed = checked
            save_config(self.config)
        if checked and self.on_dismiss:
            self.on_dismiss()
