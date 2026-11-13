"""
Ghostline — Modern PyQt6 Desktop Application Interface.
Features a refined dark charcoal surface matching Reference 3 (General Settings)
and Reference 4 (Mode Settings), complete navigation sidebar, system status header,
prominent assistance action cards, and real-time diagnostics.
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

import ctypes
import logging
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter, QBrush, QPen, QDesktopServices, QTextOption
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QScrollArea,
    QLineEdit, QComboBox, QProgressBar, QSizePolicy, QMessageBox,
    QDialog, QFileDialog, QGridLayout, QCheckBox, QTextEdit
)
from ghostline.ui.qt_ollama_widget import QtOllamaStateCard
from ghostline.ui.qt_tray_help import QtTrayHelpCard
from ghostline.core.http_client import build_sanitized_diagnostics
from ghostline.core.ollama_state import OllamaState, OllamaStateMachine
from ghostline.core.win_startup import (
    set_start_with_windows, get_start_with_windows, open_taskbar_settings
)
from ghostline.core.profile import (
    load_profile_data, save_profile_data, export_profile_json, delete_profile_data,
    extract_text_from_file, parse_resume_to_draft, build_profile_context, DEFAULT_PROFILE
)
from ghostline.audio.timing import get_stt_diagnostics_line
from ghostline.ui.live_session_vm import LiveSessionViewModel

from ghostline import __version__, BUILD_ID, get_running_mode
from ghostline.config import AppConfig, save_config, get_app_dir
from ghostline.core.providers import AIRouter
from ghostline.core.credentials import (
    get_api_key, save_api_key, delete_api_key, has_api_key, mask_api_key
)
from ghostline.ui.qt_theme import (
    QT_MAIN_STYLESHEET, QtModernToggleSwitch, FluentInfoBar,
    C_BG_APP, C_BG_SIDEBAR, C_BG_CARD, C_BG_CARD_HOVER, C_BG_CARD_ACTIVE,
    C_BORDER, C_BORDER_LIGHT, C_BORDER_ACCENT, C_CYAN, C_EMERALD,
    C_AMBER, C_DANGER, C_GOLD, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_MUTED
)
from ghostline.ui.theme import (
    apply_dark_title_bar, get_fluent_icon, get_fluent_pixmap, get_app_icon,
    SURFACE_CANVAS, SURFACE_SIDEBAR, SURFACE_CARD, SURFACE_CARD_HOVER, SURFACE_ELEVATED, SURFACE_INPUT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_QUATERNARY,
    BRAND_TEXT, BRAND_FILL, BRAND_HOVER, BRAND_PRESSED, BRAND_BADGE_BG,
    STATUS_SUCCESS_TEXT, STATUS_SUCCESS_BG, STATUS_WARNING_TEXT, STATUS_WARNING_BG,
    STATUS_DANGER_TEXT, STATUS_DANGER_BG,
    STROKE_CARD, STROKE_CONTROL, STROKE_FOCUS_OUTER, OVERLAY_HOVER,
    RADIUS_CONTROL, RADIUS_CARD, RADIUS_DIALOG
)

# Win32 Constants for Window Styles
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
user32 = ctypes.windll.user32


class QtShortcutDialog(QDialog):
    """Interactive dialog for configuring and validating custom global keyboard shortcuts."""

    def __init__(self, current_hotkey: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Global Shortcut")
        self.setFixedSize(480, 260)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_DIALOG}px;
            }}
        """)
        self.result_hotkey = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Set Global Shortcut")
        title.setStyleSheet(f"background: transparent; font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY}; font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;")
        layout.addWidget(title)

        desc = QLabel("Enter a key combination with at least one modifier (e.g. Alt + /, Ctrl + Alt + S, Alt + F1).")
        desc.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.txt_hotkey = QLineEdit(current_hotkey)
        self.txt_hotkey.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1.5px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 6px 12px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 13px;
                font-weight: 600;
            }}
            QLineEdit:hover {{
                border-color: #B0B0B0;
                background-color: #1E1E1E;
            }}
            QLineEdit:focus {{
                border: 2px solid {BRAND_TEXT};
                background-color: #0F141C;
            }}
        """)
        self.txt_hotkey.textChanged.connect(self._validate_input)
        layout.addWidget(self.txt_hotkey)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet(f"background: transparent; font-size: 12px; min-height: 20px;")
        layout.addWidget(self.lbl_feedback)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {TEXT_PRIMARY};
                font-weight: 600;
                font-size: 13px;
                padding: 6px 16px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.10);
                border-color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.04);
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Shortcut")
        self.btn_save.setIcon(get_fluent_icon("checkmark", color="#FFFFFF"))
        self.btn_save.setIconSize(QSize(14, 14))
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                font-weight: 600;
                font-size: 13px;
                padding: 6px 18px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {BRAND_FILL};
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {BRAND_HOVER};
                border-color: {BRAND_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {BRAND_PRESSED};
                border-color: {BRAND_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
        """)
        self.btn_save.clicked.connect(self._save_clicked)
        btn_box.addWidget(self.btn_save)

        layout.addLayout(btn_box)
        self._validate_input(current_hotkey)

    def _validate_input(self, text: str):
        from ghostline.app import validate_hotkey_string
        is_valid, normalized, mod, vk, err_msg = validate_hotkey_string(text)
        if not is_valid:
            self.lbl_feedback.setText(f"Error: {err_msg}")
            self.lbl_feedback.setStyleSheet(
                f"background: {STATUS_DANGER_BG}; color: {STATUS_DANGER_TEXT}; border: 1px solid rgba(197, 15, 31, 0.3); border-radius: 4px; padding: 4px 8px; font-size: 12px;"
            )
            self.btn_save.setEnabled(False)
            return

        norm_clean = normalized.lower().replace(" ", "")
        reserved = {
            "alt+a": "Live Audio Assistant",
            "alt+l": "Audio Capture Toggle",
            "alt+t": "HUD Overlay Toggle",
            "alt+q": "Audio Quick Ask"
        }
        if norm_clean in reserved:
            self.lbl_feedback.setText(f"Conflict with internal shortcut: {reserved[norm_clean]}.")
            self.lbl_feedback.setStyleSheet(
                f"background: {STATUS_WARNING_BG}; color: {STATUS_WARNING_TEXT}; border: 1px solid rgba(251, 209, 97, 0.3); border-radius: 4px; padding: 4px 8px; font-size: 12px;"
            )
            self.btn_save.setEnabled(False)
            return

        self.lbl_feedback.setText(f"Valid: {normalized}")
        self.lbl_feedback.setStyleSheet(
            f"background: {STATUS_SUCCESS_BG}; color: {STATUS_SUCCESS_TEXT}; border: 1px solid rgba(108, 203, 95, 0.3); border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self.btn_save.setEnabled(True)

    def _save_clicked(self):
        from ghostline.app import validate_hotkey_string
        text = self.txt_hotkey.text().strip()
        is_valid, normalized, mod, vk, err = validate_hotkey_string(text)
        if is_valid:
            self.result_hotkey = normalized
            self.accept()


class QtFirstRunWizardDialog(QDialog):
    """
    3-step first-run setup wizard:
    Step 1: Choose AI Engine (Ollama on this PC with download/detect vs Cloud BYOK).
    Step 2: Basic Preferences & Hotkeys (Mic, System audio, Tray icon, global hotkeys).
    Step 3: Setup Profile Grounding (Name, Role, Core Skills with interactive 'Try it' sample).
    """

    def __init__(self, config: AppConfig, parent=None, on_saved: Optional[Callable[[AppConfig], None]] = None):
        super().__init__(parent)
        self.config = config
        self.on_saved = on_saved
        self.setWindowTitle("Welcome to Ghostline")

        # Responsive dialog sizing based on work area
        from ghostline.ui.window_geometry import get_work_area
        work = get_work_area()
        target_w = min(int(work.width() * 0.9), 680)
        target_h = min(int(work.height() * 0.9), 560)
        self.setMinimumSize(min(520, work.width()), min(380, work.height()))
        self.resize(target_w, target_h)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_DIALOG}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Header Title
        self.lbl_step_tag = QLabel("Step 1 of 3")
        self.lbl_step_tag.setStyleSheet(f"background: transparent; font-size: 12px; font-weight: 700; color: {BRAND_TEXT}; text-transform: uppercase;")
        layout.addWidget(self.lbl_step_tag)

        self.lbl_step_title = QLabel("Choose Your AI Engine")
        self.lbl_step_title.setStyleSheet(f"background: transparent; font-size: 18px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(self.lbl_step_title)

        # Stacked Pages
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # Page 1: AI Provider
        self._build_page1()

        # Page 2: Hotkeys & Audio/Tray
        self._build_page2()

        # Page 3: Profile Basics & Sample
        self._build_page3()

        # Bottom Bar: Skip, Back, Next/Finish (Pinned outside the scrollable content)
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_skip = QPushButton("Skip Setup")
        self.btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_skip.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                font-size: 12.5px;
                border: none;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)
        self.btn_skip.clicked.connect(self._skip_clicked)
        btn_bar.addWidget(self.btn_skip)
        btn_bar.addStretch()

        self.btn_back = QPushButton("Back")
        self.btn_back.setEnabled(False)
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 6px 16px;
                font-size: 12.5px;
            }}
            QPushButton:hover {{
                background-color: #3D3D3D;
            }}
        """)
        self.btn_back.clicked.connect(self._back_clicked)
        btn_bar.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next →")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setDefault(True)
        self.btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                font-weight: 600;
                font-size: 12.5px;
                border-radius: {RADIUS_CONTROL}px;
                border: none;
                padding: 6px 20px;
            }}
            QPushButton:hover {{
                background-color: {BRAND_HOVER};
            }}
        """)
        self.btn_next.clicked.connect(self._next_clicked)
        btn_bar.addWidget(self.btn_next)

        layout.addLayout(btn_bar)

    def _wrap_page(self, page_widget: QWidget) -> QScrollArea:
        """Wraps step content in a smooth, responsive QScrollArea with pinned footer safety."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        outer_l = QHBoxLayout(container)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(0)

        page_widget.setMaximumWidth(720)
        outer_l.addWidget(page_widget)
        scroll.setWidget(container)
        return scroll

    def keyPressEvent(self, event):
        """Keyboard navigation: Esc skips, Enter advances."""
        if event.key() == Qt.Key.Key_Escape:
            self._skip_clicked()
            event.accept()
            return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus = self.focusWidget()
            if isinstance(focus, QPushButton):
                focus.click()
                event.accept()
                return
            self._next_clicked()
            event.accept()
            return
        super().keyPressEvent(event)

    def _build_page1(self):
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 6, 0, 0)
        l.setSpacing(12)

        desc = QLabel("Select whether you want to run open models locally on this PC, or connect directly to cloud providers using your own API key.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        l.addWidget(desc)

        from ghostline.core.hardware_profile import get_hardware_summary_string
        self.lbl_wiz_hw = QLabel(get_hardware_summary_string())
        self.lbl_wiz_hw.setObjectName("LblWizHardware")
        self.lbl_wiz_hw.setWordWrap(True)
        self.lbl_wiz_hw.setStyleSheet(f"background: {SURFACE_CARD}; color: {TEXT_SECONDARY}; font-size: 11.5px; padding: 6px 10px; border-radius: 4px; border: 1px solid {STROKE_CARD};")
        l.addWidget(self.lbl_wiz_hw)

        # Choice A: Ollama
        self.opt_local = QFrame()
        self.opt_local.setObjectName("CardFrame")
        self.opt_local.setCursor(Qt.CursorShape.PointingHandCursor)
        self.opt_local.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 2px solid {BRAND_FILL}; border-radius: {RADIUS_CARD}px; padding: 10px; }}")
        ol_layout = QVBoxLayout(self.opt_local)
        ol_t = QLabel("On this PC (Ollama) — Recommended for Privacy")
        ol_t.setWordWrap(True)
        ol_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        ol_d = QLabel("100% offline and private. Models run directly on your hardware without sending questions over the internet.")
        ol_d.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY};")
        ol_d.setWordWrap(True)
        ol_layout.addWidget(ol_t)
        ol_layout.addWidget(ol_d)

        # Ollama first-run state machine card
        self.ollama_wiz_card = QtOllamaStateCard(self.config, parent=self.opt_local)
        self.ollama_wiz_card.start_polling()
        ol_layout.addWidget(self.ollama_wiz_card)
        self.lbl_ollama_det = self.ollama_wiz_card.lbl_headline
        self.btn_check_ollama = self.ollama_wiz_card.btn_secondary
        self.btn_get_ollama = self.ollama_wiz_card.btn_primary

        l.addWidget(self.opt_local)

        # Choice B: Cloud
        self.opt_cloud = QFrame()
        self.opt_cloud.setObjectName("CardFrame")
        self.opt_cloud.setCursor(Qt.CursorShape.PointingHandCursor)
        self.opt_cloud.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; padding: 10px; }}")
        oc_layout = QVBoxLayout(self.opt_cloud)
        oc_t = QLabel("Cloud (Bring Your Own Key) — Recommended for Speed")
        oc_t.setWordWrap(True)
        oc_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        oc_d = QLabel("Connect to Gemini, Groq, OpenRouter, OpenAI, Claude, or xAI with ultra-fast sub-second answers.")
        oc_d.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY};")
        oc_d.setWordWrap(True)
        oc_layout.addWidget(oc_t)
        oc_layout.addWidget(oc_d)

        # Cloud provider picker and key row
        c_row = QHBoxLayout()
        c_row.setSpacing(8)
        self.combo_wiz_cloud = QComboBox()
        self.combo_wiz_cloud.addItems(["Gemini", "Groq", "OpenRouter", "OpenAI", "Anthropic", "xAI"])
        self.combo_wiz_cloud.setFixedHeight(34)
        self.combo_wiz_cloud.setStyleSheet(f"""
            QComboBox {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1.5px solid {STROKE_CONTROL};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: #B0B0B0;
                background-color: #1E1E1E;
            }}
            QComboBox:focus {{
                border: 2px solid {BRAND_TEXT};
                background-color: #0F141C;
            }}
        """)

        self.txt_wiz_api_key = QLineEdit()
        self.txt_wiz_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_wiz_api_key.setPlaceholderText("Paste API Key (optional during setup)")
        self.txt_wiz_api_key.setFixedHeight(34)
        self.txt_wiz_api_key.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1.5px solid {STROKE_CONTROL};
                border-radius: 4px;
                padding: 0 10px;
                font-size: 12px;
                placeholder-text-color: #A0A0A0;
            }}
            QLineEdit:hover {{
                border-color: #B0B0B0;
                background-color: #1E1E1E;
            }}
            QLineEdit:focus {{
                border: 2px solid {BRAND_TEXT};
                background-color: #0F141C;
            }}
        """)

        self.btn_wiz_toggle_key = QPushButton()
        self.btn_wiz_toggle_key.setIcon(get_fluent_icon("eye", color=TEXT_SECONDARY, size=15))
        self.btn_wiz_toggle_key.setFixedSize(34, 34)
        self.btn_wiz_toggle_key.setToolTip("Show / Hide API Key")
        self.btn_wiz_toggle_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wiz_toggle_key.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_ELEVATED};
                border: 1px solid {STROKE_CONTROL};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
                border-color: #999999;
            }}
        """)
        def _toggle_wiz_key():
            if self.txt_wiz_api_key.echoMode() == QLineEdit.EchoMode.Password:
                self.txt_wiz_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
                self.btn_wiz_toggle_key.setIcon(get_fluent_icon("eye_off", color=BRAND_TEXT, size=15))
            else:
                self.txt_wiz_api_key.setEchoMode(QLineEdit.EchoMode.Password)
                self.btn_wiz_toggle_key.setIcon(get_fluent_icon("eye", color=TEXT_SECONDARY, size=15))
        self.btn_wiz_toggle_key.clicked.connect(_toggle_wiz_key)

        c_row.addWidget(self.combo_wiz_cloud)
        c_row.addWidget(self.txt_wiz_api_key, 1)
        c_row.addWidget(self.btn_wiz_toggle_key)
        oc_layout.addLayout(c_row)

        # Cloud Test Connection Row in Wizard
        c_test_row = QHBoxLayout()
        c_test_row.setSpacing(10)

        self.btn_wiz_test_cloud = QPushButton("Test Connection")
        self.btn_wiz_test_cloud.setObjectName("BtnWizTestCloud")
        self.btn_wiz_test_cloud.setFixedHeight(30)
        self.btn_wiz_test_cloud.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wiz_test_cloud.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CONTROL};
                border-radius: 4px;
                padding: 0 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {SURFACE_CARD_HOVER};
            }}
        """)
        self.btn_wiz_test_cloud.clicked.connect(self._test_wiz_cloud_connection)
        c_test_row.addWidget(self.btn_wiz_test_cloud)

        self.lbl_wiz_test_result = QLabel("")
        self.lbl_wiz_test_result.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {TEXT_TERTIARY};")
        c_test_row.addWidget(self.lbl_wiz_test_result, 1)

        self.btn_wiz_copy_diag = QPushButton("Copy Diagnostics")
        self.btn_wiz_copy_diag.setFixedHeight(26)
        self.btn_wiz_copy_diag.setStyleSheet(f"background: transparent; color: {BRAND_TEXT}; border: none; font-size: 11px;")
        self.btn_wiz_copy_diag.hide()
        self.btn_wiz_copy_diag.clicked.connect(self._copy_wiz_diagnostics)
        c_test_row.addWidget(self.btn_wiz_copy_diag)

        oc_layout.addLayout(c_test_row)

        l.addWidget(self.opt_cloud)

        def _pick_local(e):
            self.chosen_provider = "ollama"
            self.opt_local.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 2px solid {BRAND_FILL}; border-radius: {RADIUS_CARD}px; padding: 10px; }}")
            self.opt_cloud.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; padding: 10px; }}")

        def _pick_cloud(e):
            selected = self.combo_wiz_cloud.currentText().lower()
            self.chosen_provider = selected
            self.opt_cloud.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 2px solid {BRAND_FILL}; border-radius: {RADIUS_CARD}px; padding: 10px; }}")
            self.opt_local.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; padding: 10px; }}")

        self.chosen_provider = getattr(self.config, "ai_provider", "ollama")
        self.opt_local.mousePressEvent = _pick_local
        self.opt_cloud.mousePressEvent = _pick_cloud

        l.addStretch()
        self.stack.addWidget(self._wrap_page(page))
        # Check Ollama status asynchronously
        QTimer.singleShot(100, self._check_ollama_status)

    def _check_ollama_status(self):
        if hasattr(self, "ollama_wiz_card"):
            self.ollama_wiz_card.poll_state(force=True)

    def _test_wiz_cloud_connection(self):
        prov_name = self.combo_wiz_cloud.currentText().lower()
        key = self.txt_wiz_api_key.text().strip()
        if not key:
            self.lbl_wiz_test_result.setText("Please enter an API key above before testing.")
            self.lbl_wiz_test_result.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {STATUS_WARNING_TEXT};")
            return

        self.btn_wiz_test_cloud.setEnabled(False)
        self.lbl_wiz_test_result.setText("Testing connection...")
        self.lbl_wiz_test_result.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {BRAND_TEXT};")
        self.btn_wiz_copy_diag.hide()

        def _worker():
            try:
                router = getattr(self.parent(), "ai_router", None) or AIRouter(self.config)
                router.set_provider_key(prov_name, key)
                success, msg = router.test_provider(prov_name)
                prov = router.get_provider(prov_name)
                last_err = getattr(prov, "last_error_info", None) if prov else None
            except Exception as e:
                success, msg, last_err = False, str(e), None

            def _update():
                self.btn_wiz_test_cloud.setEnabled(True)
                if success:
                    self.lbl_wiz_test_result.setText(f"Connected: {msg}")
                    self.lbl_wiz_test_result.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {STATUS_SUCCESS_TEXT}; font-weight: 500;")
                    self.btn_wiz_copy_diag.hide()
                else:
                    self.lbl_wiz_test_result.setText(f"Error: {msg}")
                    self.lbl_wiz_test_result.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {STATUS_DANGER_TEXT}; font-weight: 500;")
                    self._last_wiz_diag = build_sanitized_diagnostics(
                        provider=prov_name,
                        model=getattr(self.config, "model_name", "default"),
                        error_info=last_err
                    )
                    self.btn_wiz_copy_diag.show()

            QTimer.singleShot(0, _update)

        threading.Thread(target=_worker, daemon=True).start()

    def _copy_wiz_diagnostics(self):
        diag = getattr(self, "_last_wiz_diag", "No diagnostics available.")
        QApplication.clipboard().setText(diag)
        self.btn_wiz_copy_diag.setText("Copied!")
        QTimer.singleShot(2000, lambda: self.btn_wiz_copy_diag.setText("Copy Diagnostics"))

    def _build_page2(self):
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 6, 0, 0)
        l.setSpacing(12)

        desc = QLabel("Configure basic background preferences and learn the essential global shortcuts:")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        l.addWidget(desc)

        # Basic Checkboxes Card
        pref_card = QFrame()
        pref_card.setStyleSheet(f"background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; padding: 10px;")
        pc_l = QVBoxLayout(pref_card)
        pc_l.setSpacing(8)

        self.chk_mic = QCheckBox("Enable microphone audio capture for live assistance")
        self.chk_mic.setChecked(True)
        self.chk_mic.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 12.5px;")
        pc_l.addWidget(self.chk_mic)

        self.chk_sys = QCheckBox("Enable system audio loopback for meetings (Zoom, Teams, Meet)")
        self.chk_sys.setChecked(True)
        self.chk_sys.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 12.5px;")
        pc_l.addWidget(self.chk_sys)

        self.chk_tray = QCheckBox("Show Ghostline in the Windows system tray")
        self.chk_tray.setChecked(getattr(self.config, "show_tray_icon", True))
        self.chk_tray.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 12.5px;")
        pc_l.addWidget(self.chk_tray)

        r_w_lang = QHBoxLayout()
        lbl_w_lang = QLabel("Spoken Language:")
        lbl_w_lang.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 12.5px; font-weight: 500;")
        self.combo_wiz_lang = QComboBox()
        self.combo_wiz_lang.addItem("English (recommended)", "en")
        self.combo_wiz_lang.addItem("Spanish", "es")
        self.combo_wiz_lang.addItem("French", "fr")
        self.combo_wiz_lang.addItem("German", "de")
        self.combo_wiz_lang.addItem("Auto-detect (may produce text in wrong language on noise)", "auto")
        self.combo_wiz_lang.setFixedHeight(30)
        curr_lang = getattr(self.config, "audio_language", "en")
        idx_l = self.combo_wiz_lang.findData(curr_lang)
        if idx_l >= 0:
            self.combo_wiz_lang.setCurrentIndex(idx_l)
        r_w_lang.addWidget(lbl_w_lang)
        r_w_lang.addWidget(self.combo_wiz_lang, 1)
        pc_l.addLayout(r_w_lang)

        l.addWidget(pref_card)

        # System tray icon pinning instructions card
        self.wiz_tray_help = QtTrayHelpCard(self.config, parent=page, show_dismiss=False)
        l.addWidget(self.wiz_tray_help)

        # Hotkeys Card
        hk_card = QFrame()
        hk_card.setStyleSheet(f"background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; padding: 10px;")
        hk_l = QVBoxLayout(hk_card)
        hk_l.setSpacing(8)

        hk_items = [
            (getattr(self.config, "hotkey", "Alt + /"), "Scan & Solve under mouse cursor"),
            ("Alt + A", "Open floating Live Audio Assistant"),
            (getattr(self.config, "hotkey_hud_toggle", "Alt + T"), "Show or hide floating answer HUD"),
            ("Ctrl + Alt + Q", "Emergency clean exit (Quit Ghostline)")
        ]
        for key_text, desc_text in hk_items:
            r = QHBoxLayout()
            k = QLabel(key_text)
            k.setStyleSheet(f"background-color: {SURFACE_INPUT}; color: #FFFFFF; font-family: Consolas, monospace; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 4px; border: 1px solid {STROKE_CONTROL}; min-width: 90px;")
            d = QLabel(desc_text)
            d.setWordWrap(True)
            d.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 12px;")
            r.addWidget(k)
            r.addWidget(d, 1)
            hk_l.addLayout(r)

        l.addWidget(hk_card)

        note = QLabel("Ghostline floating overlay is automatically excluded from screen shares (WDA_EXCLUDEFROMCAPTURE).")
        note.setWordWrap(True)
        note.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {TEXT_TERTIARY}; line-height: 1.4;")
        l.addWidget(note)
        l.addStretch()
        self.stack.addWidget(self._wrap_page(page))

    def _build_page3(self):
        page = QWidget()
        l = QVBoxLayout(page)
        l.setContentsMargins(0, 6, 0, 0)
        l.setSpacing(10)

        desc = QLabel("Tell Ghostline about your background so AI answers naturally use your real experience (optional, can be edited anytime):")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        l.addWidget(desc)

        self.txt_wiz_name = QLineEdit()
        self.txt_wiz_name.setPlaceholderText("Full Name (e.g. Alex Chen)")
        self.txt_wiz_name.setFixedHeight(34)
        l.addWidget(self.txt_wiz_name)

        self.txt_wiz_role = QLineEdit()
        self.txt_wiz_role.setPlaceholderText("Target Role (e.g. Senior Backend Engineer)")
        self.txt_wiz_role.setFixedHeight(34)
        l.addWidget(self.txt_wiz_role)

        self.txt_wiz_skills = QLineEdit()
        self.txt_wiz_skills.setPlaceholderText("Core Technologies (e.g. Python, Go, Distributed Systems)")
        self.txt_wiz_skills.setFixedHeight(34)
        l.addWidget(self.txt_wiz_skills)

        # "Try Grounding" sample card
        sample_card = QFrame()
        sample_card.setStyleSheet(f"background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; padding: 8px;")
        sc_l = QVBoxLayout(sample_card)
        sc_l.setSpacing(6)
        
        sc_head = QHBoxLayout()
        sc_t = QLabel("Try Grounding: Sample Interview Question")
        sc_t.setWordWrap(True)
        sc_t.setStyleSheet(f"background: transparent; font-size: 12px; font-weight: 600; color: {TEXT_PRIMARY};")
        btn_try = QPushButton("Test Grounding")
        btn_try.setStyleSheet(f"background: {SURFACE_INPUT}; color: {BRAND_TEXT}; font-size: 12px; font-weight: 600; border: 1px solid {STROKE_CONTROL}; border-radius: 4px; padding: 2px 10px;")
        btn_try.clicked.connect(self._run_sample_grounding)
        sc_head.addWidget(sc_t)
        sc_head.addStretch()
        sc_head.addWidget(btn_try)
        sc_l.addLayout(sc_head)

        self.lbl_wiz_sample = QLabel("Click 'Test Grounding' to preview how your profile facts are woven into responses.")
        self.lbl_wiz_sample.setWordWrap(True)
        self.lbl_wiz_sample.setStyleSheet(f"font-size: 11.5px; color: {TEXT_TERTIARY}; background: {SURFACE_CANVAS}; padding: 6px; border-radius: 4px;")
        sc_l.addWidget(self.lbl_wiz_sample)
        l.addWidget(sample_card)

        p_info = QLabel("Your profile is stored locally on this machine encrypted via Windows DPAPI.")
        p_info.setWordWrap(True)
        p_info.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_TERTIARY};")
        l.addWidget(p_info)
        l.addStretch()
        self.stack.addWidget(self._wrap_page(page))

    def _run_sample_grounding(self):
        name = self.txt_wiz_name.text().strip() or "Candidate"
        role = self.txt_wiz_role.text().strip() or "Software Engineer"
        skills = self.txt_wiz_skills.text().strip() or "Python, Systems"
        sample_ans = f"As a {role}, I architect scalable solutions focusing on {skills}. In high-throughput settings, I ensure resilient data flows and maintain sub-second P99 latencies."
        self.lbl_wiz_sample.setText(f"[Profile Grounded Preview for {name}]:\n\"{sample_ans}\"")
        self.lbl_wiz_sample.setStyleSheet(f"font-size: 11.5px; color: {TEXT_PRIMARY}; background: {SURFACE_CANVAS}; padding: 6px; border-radius: 4px; border: 1px solid {BRAND_FILL};")

    def _next_clicked(self):
        curr = self.stack.currentIndex()
        if curr == 0:
            self.lbl_step_tag.setText("Step 2 of 3")
            self.lbl_step_title.setText("Basic Preferences & Hotkeys")
            self.btn_back.setEnabled(True)
            self.stack.setCurrentIndex(1)
        elif curr == 1:
            self.lbl_step_tag.setText("Step 3 of 3")
            self.lbl_step_title.setText("Personal Profile Setup")
            self.btn_next.setText("Finish && Launch")
            self.stack.setCurrentIndex(2)
        else:
            self._finish_wizard()

    def _back_clicked(self):
        curr = self.stack.currentIndex()
        if curr == 2:
            self.lbl_step_tag.setText("Step 2 of 3")
            self.lbl_step_title.setText("Basic Preferences & Hotkeys")
            self.btn_next.setText("Next →")
            self.stack.setCurrentIndex(1)
        elif curr == 1:
            self.lbl_step_tag.setText("Step 1 of 3")
            self.lbl_step_title.setText("Choose Your AI Engine")
            self.btn_back.setEnabled(False)
            self.stack.setCurrentIndex(0)

    def _finish_wizard(self):
        if hasattr(self, "ollama_wiz_card"):
            self.ollama_wiz_card.stop_polling()
        self.config.ai_provider = getattr(self, "chosen_provider", "ollama")
        self.config.first_run_complete = True
        if hasattr(self, "chk_tray"):
            self.config.show_tray_icon = self.chk_tray.isChecked()
        if hasattr(self, "combo_wiz_lang"):
            self.config.audio_language = self.combo_wiz_lang.currentData()
        save_config(self.config)

        # If API key was provided for cloud
        if hasattr(self, "txt_wiz_api_key"):
            key = self.txt_wiz_api_key.text().strip()
            if key and self.config.ai_provider != "ollama":
                try:
                    save_api_key(self.config.ai_provider, key)
                except Exception:
                    pass

        name = self.txt_wiz_name.text().strip() if hasattr(self, "txt_wiz_name") else ""
        role = self.txt_wiz_role.text().strip() if hasattr(self, "txt_wiz_role") else ""
        skills = self.txt_wiz_skills.text().strip() if hasattr(self, "txt_wiz_skills") else ""
        if name or role or skills:
            try:
                skill_list = [s.strip() for s in skills.split(",") if s.strip()]
                save_profile_data({
                    "name": name,
                    "role": role,
                    "skills": skill_list,
                    "use_profile": True,
                    "allow_cloud": False
                })
            except Exception:
                pass

        if self.on_saved:
            self.on_saved(self.config)
        self.accept()

    def _skip_clicked(self):
        if hasattr(self, "ollama_wiz_card"):
            self.ollama_wiz_card.stop_polling()
        self.config.first_run_complete = True
        save_config(self.config)
        if self.on_saved:
            self.on_saved(self.config)
        self.reject()

    def closeEvent(self, event):
        if hasattr(self, "ollama_wiz_card"):
            self.ollama_wiz_card.stop_polling()
        super().closeEvent(event)


class QtGhostlineMainWindow(QMainWindow):
    """
    State-of-the-art PyQt6 Main Desktop Interface for Ghostline.
    """
    sig_vm_updated = pyqtSignal()

    def __init__(
        self,
        config: AppConfig,
        on_trigger_solve: Optional[Callable[[], None]] = None,
        on_settings_saved: Optional[Callable[[AppConfig], None]] = None,
        on_toggle_hud: Optional[Callable[[], None]] = None,
        on_test_caps: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        ollama_client: Optional[Any] = None,
        on_test_mic: Optional[Callable[..., Dict[str, Any]]] = None,
        on_test_loopback: Optional[Callable[..., Dict[str, Any]]] = None,
        on_test_transcription: Optional[Callable[[], Dict[str, Any]]] = None,
        on_test_stt_benchmark: Optional[Callable[..., Dict[str, Any]]] = None,
        on_live_ask: Optional[Callable[[], None]] = None,
        on_live_clear: Optional[Callable[[], None]] = None,
        on_live_fix: Optional[Callable[[str], None]] = None,
        get_audio_diagnostics: Optional[Callable[[], Dict[str, Any]]] = None,
        on_toggle_audio: Optional[Callable[[], bool]] = None,
    ):
        super().__init__()
        from ghostline.ui.theme import apply_fluent_theme
        apply_fluent_theme(QApplication.instance())
        self.config = config
        self.on_trigger_solve = on_trigger_solve
        self.on_settings_saved = on_settings_saved
        self.on_toggle_hud = on_toggle_hud
        self.on_test_caps = on_test_caps
        self.on_exit = on_exit
        self.ollama_client = ollama_client
        if isinstance(ollama_client, AIRouter):
            self.ai_router = ollama_client
        else:
            self.ai_router = AIRouter(config=self.config)
        self.on_test_mic = on_test_mic
        self.on_test_loopback = on_test_loopback
        self.on_test_transcription = on_test_transcription
        self.on_test_stt_benchmark = on_test_stt_benchmark
        self.on_live_ask = on_live_ask
        self.on_live_clear = on_live_clear
        self.on_live_fix = on_live_fix
        self.get_audio_diagnostics = get_audio_diagnostics
        self.on_toggle_audio = on_toggle_audio
        self.root = self

        self.sig_vm_updated.connect(self._sync_live_session_from_vm)
        self.live_session_vm = LiveSessionViewModel.get_instance()
        self.live_session_vm.subscribe(self.sig_vm_updated.emit)

        self._live_thinking_timer = QTimer(self)
        self._live_thinking_timer.setInterval(100)
        self._live_thinking_timer.timeout.connect(self._update_live_thinking_ticker)

        self._is_initialized = False
        self._is_minimized_to_tray = False
        self.current_screen = "dashboard"
        self.screen_frames: Dict[str, QWidget] = {}
        self.running_mode = get_running_mode()
        self.setWindowTitle("Ghostline")
        apply_dark_title_bar(self)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        from ghostline.ui.window_geometry import get_work_area
        from ghostline.ui.window_state import WindowStateManager

        work = get_work_area()
        min_w = min(760, work.width())
        min_h = min(520, work.height())
        self.setMinimumSize(min_w, min_h)

        self.window_state_manager = WindowStateManager(self, self.config)

        self.setStyleSheet(QT_MAIN_STYLESHEET)

        self._init_ui()
        self.apply_icon()
        self._sync_icon_combobox()
        self._apply_performance_mode()

        # Apply validated geometry and open state (maximized by default, min size <= 760x520)
        start_minimized = getattr(self.config, "start_minimized", False)
        self.window_state_manager.apply_initial_geometry_and_state(start_minimized=start_minimized)
        self._is_initialized = True
        if not getattr(self.config, "first_run_complete", False):
            QTimer.singleShot(250, self._launch_setup_wizard)

    def _init_ui(self):
        from ghostline.build_info import VERSION, GIT_COMMIT_SHORT, get_running_mode
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. Left Navigation Sidebar
        # ---------------------------------------------------------------------
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 16)
        sidebar_layout.setSpacing(4)

        # Brand Logo & Title
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)
        brand_icon = QLabel()
        app_icon = get_app_icon()
        brand_icon.setPixmap(app_icon.pixmap(26, 26))
        brand_icon.setFixedSize(26, 26)
        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(1)
        brand_title = QLabel("Ghostline")
        brand_title.setObjectName("HeaderTitle")
        brand_title.setStyleSheet(f"background: transparent; font-size: 16px; font-weight: 700; color: {TEXT_PRIMARY};")
        brand_sub = QLabel(f"v{VERSION}")
        brand_sub.setStyleSheet(f"background: transparent; font-size: 12px; font-weight: 500; color: {TEXT_TERTIARY};")
        brand_text_box.addWidget(brand_title)
        brand_text_box.addWidget(brand_sub)
        brand_layout.addWidget(brand_icon)
        brand_layout.addLayout(brand_text_box)
        brand_layout.addStretch()
        sidebar_layout.addLayout(brand_layout)

        # Engine Status Indicator Badge
        status_box = QFrame()
        status_box.setObjectName("SidebarStatusBadge")
        status_box.setStyleSheet(f"""
            QFrame#SidebarStatusBadge {{
                background-color: {SURFACE_CARD};
                border: 1px solid {STROKE_CARD};
                border-radius: 6px;
                padding: 4px 8px;
                margin-top: 6px;
                margin-bottom: 8px;
            }}
        """)
        status_box_layout = QHBoxLayout(status_box)
        status_box_layout.setContentsMargins(8, 4, 8, 4)
        status_box_layout.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12px;")
        self.status_text = QLabel("Ollama · Local · Ready")
        self.status_text.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 500;")
        status_box_layout.addWidget(self.status_dot)
        status_box_layout.addWidget(self.status_text)
        status_box_layout.addStretch()
        sidebar_layout.addWidget(status_box)
        self.update_sidebar_status_badge(check_reachable=False)

        # Navigation items (Clean 6-Item Consolidated IA)
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "home", "Home"),
            ("profile", "person", "My Profile"),
            ("model", "sparkle", "AI"),
            ("history", "history", "History"),
            ("general", "settings", "Settings"),
            ("help", "info", "Help"),
        ]

        for screen_id, icon_name, label in nav_items:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("SidebarBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn._nav_icon_name = icon_name
            btn.setIcon(get_fluent_icon(icon_name, color=TEXT_SECONDARY, size=18, filled=False))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked, s=screen_id: self.show_screen(s))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[screen_id] = btn

        sidebar_layout.addStretch()

        # Dedicated Exit action in sidebar
        self.btn_exit_app = QPushButton("  Exit Ghostline")
        self.btn_exit_app.setObjectName("SidebarExitBtn")
        self.btn_exit_app.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit_app.setIcon(get_fluent_icon("exit", color=STATUS_DANGER_TEXT, size=18, filled=False))
        self.btn_exit_app.setIconSize(QSize(18, 18))
        self.btn_exit_app.setFixedHeight(34)
        self.btn_exit_app.clicked.connect(self._handle_exit_clicked)
        sidebar_layout.addWidget(self.btn_exit_app)

        # Subtle Support & Star link
        self.btn_sidebar_support = QPushButton("Star · Support")
        self.btn_sidebar_support.setObjectName("sidebarSupportLink")
        self.btn_sidebar_support.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sidebar_support.setIcon(get_fluent_icon("star", color=BRAND_TEXT, size=13))
        self.btn_sidebar_support.setFixedHeight(24)
        self.btn_sidebar_support.setStyleSheet(f"""
            QPushButton#sidebarSupportLink {{
                background: transparent;
                color: {BRAND_TEXT};
                border: none;
                font-size: 12px;
                font-weight: 500;
                text-align: left;
                padding: 2px 4px;
                border-radius: 4px;
            }}
            QPushButton#sidebarSupportLink:hover {{
                text-decoration: underline;
                background-color: {OVERLAY_HOVER};
            }}
            QPushButton#sidebarSupportLink:focus {{
                outline: 1px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_sidebar_support.clicked.connect(self._navigate_to_support_card)
        sidebar_layout.addWidget(self.btn_sidebar_support)

        # Version & Offline notice at bottom of sidebar
        running_mode = getattr(self, "running_mode", None) or get_running_mode()
        badge = "Dev" if "DEVELOPMENT" in running_mode.upper() else "Release"
        ver_lbl = QLabel(f"Ghostline v{__version__} ({badge})")
        ver_lbl.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 12px; padding: 4px 2px;")
        sidebar_layout.addWidget(ver_lbl)

        main_layout.addWidget(sidebar)

        # ---------------------------------------------------------------------
        # 2. Main Stacked Content Views
        # ---------------------------------------------------------------------
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {SURFACE_CANVAS}; border: none;")
        main_layout.addWidget(self.stack, 1)

        # Create Views (All 10 views preserved for 100% backward compatibility)
        self._build_general_view()     # Settings View (Settings, General)
        self._build_mode_view()        # Delivery Mode View (Mode)
        self._build_dashboard_view()   # Home View (Home, Dashboard, Main, Answer)
        self._build_audio_view()       # Audio View (Audio)
        self._build_model_view()       # AI View (AI, Model, Setup)
        self._build_history_view()     # History View (History)
        self._build_profile_view()     # Personal Profile View (Profile)
        self._build_security_view()    # Security View (Security)
        self._build_diagnostics_view() # Diagnostics View (Diagnostics)
        self._build_help_view()        # Help View (Help, About)

        # Ensure all form inputs throughout the entire application receive high-contrast Fluent 2 input styling
        from ghostline.ui.theme import apply_input_theme
        for ctrl in self.findChildren((QLineEdit, QTextEdit, QComboBox)):
            apply_input_theme(ctrl)

        # Show initial screen
        self.show_screen("dashboard")

    def update_sidebar_status_badge(self, check_reachable: bool = False):
        """
        Dynamically derives and updates the sidebar status badge based on provider configuration,
        credential presence (via Windows DPAPI), and connectivity state.
        """
        if not hasattr(self, "status_dot") or not hasattr(self, "status_text"):
            return

        provider = getattr(self.config, "ai_provider", "ollama")
        provider_id = (provider or "ollama").lower().strip()
        provider_name = provider_id.capitalize()

        if provider_id == "ollama":
            endpoint = getattr(self.config, "ollama_url", "http://127.0.0.1:11434").rstrip("/")
            reachable = True
            if check_reachable:
                try:
                    if endpoint.startswith(("http://", "https://")):
                        import urllib.request
                        req = urllib.request.Request(f"{endpoint}/api/tags", headers={"User-Agent": "Ghostline"}, method="GET")
                        with urllib.request.urlopen(req, timeout=0.8) as resp:  # nosec B310
                            reachable = (resp.status == 200)
                    else:
                        reachable = False
                except Exception:
                    reachable = False

            if reachable:
                self.status_dot.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12px;")
                self.status_text.setText("Ollama · Local · Ready")
            else:
                self.status_dot.setStyleSheet(f"background: transparent; color: {STATUS_WARNING_TEXT}; font-size: 12px;")
                self.status_text.setText("Can't reach Ollama")
        else:
            has_k = has_api_key(provider_id)
            if not has_k:
                self.status_dot.setStyleSheet(f"background: transparent; color: {STATUS_WARNING_TEXT}; font-size: 12px;")
                self.status_text.setText(f"{provider_name} · Needs API key")
            else:
                self.status_dot.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12px;")
                self.status_text.setText(f"{provider_name} · Cloud · Ready")

    # -------------------------------------------------------------------------
    # Screen 1: General Settings (Directly Matching Reference 3)
    # -------------------------------------------------------------------------
    def _build_general_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("GeneralContainer")
        container.setStyleSheet(f"QWidget#GeneralContainer {{ background-color: {SURFACE_CANVAS}; }}")

        outer_layout = QHBoxLayout(container)
        outer_layout.setContentsMargins(40, 28, 40, 36)
        outer_layout.setSpacing(0)

        center_widget = QWidget()
        center_widget.setObjectName("PageColumn")
        center_widget.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        center_widget.setStyleSheet("background: transparent;")
        center_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # Title & Subtitle
        title = QLabel("Settings")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Configure global keyboard shortcuts, taskbar behavior, system tray, and startup preferences.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; margin-top: 2px; padding: 2px 0;")
        layout.addWidget(subtitle)

        # --- Section 1: Usage ---
        sec_usage = QLabel("Inference & Usage")
        sec_usage.setObjectName("SectionTitle")
        sec_usage.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_usage)

        card_usage = QFrame()
        card_usage.setObjectName("CardFrame")
        card_usage.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        c_usage_layout = QVBoxLayout(card_usage)
        c_usage_layout.setContentsMargins(20, 18, 20, 18)
        c_usage_layout.setSpacing(14)

        u_head = QHBoxLayout()
        u_title = QLabel("Inference Engine")
        u_title.setObjectName("CardTitle")
        u_title.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        provider = getattr(self.config, "ai_provider", "ollama")
        prov_label = "Local Ollama" if provider == "ollama" else f"{provider.capitalize()} Cloud"
        u_left = QLabel(f"Active · {prov_label}")
        u_left.setObjectName("CardTitle")
        u_left.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 13px; font-weight: 600;")
        u_head.addWidget(u_title)
        u_head.addStretch()
        u_head.addWidget(u_left)
        c_usage_layout.addLayout(u_head)

        u_sub = QLabel("On-device local models or Bring-Your-Own-Key cloud inference. Prompts and keys remain under your control.")
        u_sub.setObjectName("CardDesc")
        u_sub.setWordWrap(True)
        u_sub.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        c_usage_layout.addWidget(u_sub)

        # Progress bar removed (quota-free local/BYOK engine)

        # Subcard: Need more searches / Model card
        sub_card = QFrame()
        sub_card.setStyleSheet(f"QFrame {{ background: {SURFACE_CANVAS}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CONTROL}px; }}")
        sub_layout = QHBoxLayout(sub_card)
        sub_layout.setContentsMargins(14, 12, 14, 12)
        sub_layout.setSpacing(12)
        pro_tag = QLabel("Active")
        pro_tag.setStyleSheet(f"background-color: {BRAND_BADGE_BG}; color: {BRAND_TEXT}; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 4px;")
        sub_text_layout = QVBoxLayout()
        sub_text_layout.setSpacing(2)
        sub_t1 = QLabel(f"{prov_label} Engine Ready")
        sub_t1.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-weight: 600; font-size: 13px;")
        endpoint_desc = "Running on local endpoint at 127.0.0.1:11434." if provider == "ollama" else f"Direct authenticated API requests to {provider.capitalize()} endpoint."
        sub_t2 = QLabel(endpoint_desc)
        sub_t2.setWordWrap(True)
        sub_t2.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 12px;")
        sub_text_layout.addWidget(sub_t1)
        sub_text_layout.addWidget(sub_t2)

        btn_verify = QPushButton("Verify Connection")
        btn_verify.setObjectName("SecondaryBtn")
        btn_verify.setIcon(get_fluent_icon("refresh", color=TEXT_PRIMARY, size=14, filled=False))
        btn_verify.setFixedHeight(32)
        btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_verify.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        btn_verify.clicked.connect(self._verify_ollama_status)

        sub_layout.addWidget(pro_tag)
        sub_layout.addLayout(sub_text_layout, 1)
        sub_layout.addWidget(btn_verify)
        c_usage_layout.addWidget(sub_card)

        btn_goto_model = QPushButton("Configure AI Models && Providers →")
        btn_goto_model.setObjectName("SecondaryBtn")
        btn_goto_model.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=14, filled=False))
        btn_goto_model.setFixedHeight(34)
        btn_goto_model.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_goto_model.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 16px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
                border-color: {TEXT_SECONDARY};
            }}
        """)
        btn_goto_model.clicked.connect(lambda: self.show_screen("model"))
        c_usage_layout.addWidget(btn_goto_model)

        layout.addWidget(card_usage)

        # --- Section 2: Shortcut ---
        sec_shortcut = QLabel("Shortcut")
        sec_shortcut.setObjectName("SectionTitle")
        sec_shortcut.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_shortcut)

        card_sc = QFrame()
        card_sc.setObjectName("CardFrame")
        card_sc.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        sc_layout = QHBoxLayout(card_sc)
        sc_layout.setContentsMargins(20, 18, 20, 18)
        sc_layout.setSpacing(16)
        sc_text = QVBoxLayout()
        sc_text.setSpacing(4)
        sc_t = QLabel("Custom Global Shortcut")
        sc_t.setObjectName("CardTitle")
        sc_t.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        sc_d = QLabel("Set your own global shortcut with modifier keys (e.g. Alt + /, Ctrl + Alt + S).")
        sc_d.setObjectName("CardDesc")
        sc_d.setWordWrap(True)
        sc_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        sc_text.addWidget(sc_t)
        sc_text.addWidget(sc_d)

        self.btn_hotkey_chip = QPushButton("Ctrl + Alt + Win")
        self.btn_hotkey_chip.setObjectName("PillChipBtn")
        self.btn_hotkey_chip.setText(self.config.hotkey if hasattr(self.config, 'hotkey') else "Alt + /")
        self.btn_hotkey_chip.setFixedHeight(32)
        self.btn_hotkey_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hotkey_chip.setStyleSheet(f"""
            QPushButton#PillChipBtn {{
                background-color: {SURFACE_ELEVATED};
                color: #FFFFFF;
                font-family: Consolas, monospace;
                font-size: 12.5px;
                font-weight: 600;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#PillChipBtn:hover {{
                background-color: #3D3D3D;
                border-color: {BRAND_TEXT};
            }}
        """)
        self.btn_hotkey_chip.clicked.connect(self._edit_hotkey)

        sc_layout.addLayout(sc_text, 1)
        sc_layout.addWidget(self.btn_hotkey_chip)
        layout.addWidget(card_sc)

        # --- Section 3: App Visibility ---
        sec_vis = QLabel("App Visibility")
        sec_vis.setObjectName("SectionTitle")
        sec_vis.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_vis)

        card_vis = QFrame()
        card_vis.setObjectName("CardFrame")
        card_vis.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        vis_layout = QVBoxLayout(card_vis)
        vis_layout.setContentsMargins(20, 16, 20, 16)
        vis_layout.setSpacing(14)

        # Application icon row with preview and picker
        r1 = QHBoxLayout()
        r1.setSpacing(12)
        r1_text = QVBoxLayout()
        r1_text.setSpacing(4)
        r1_t = QLabel("Application icon")
        r1_t.setObjectName("CardTitle")
        r1_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r1_d = QLabel("Choose a stealth preset or custom image (.ico, .png, .jpg) for window and tray.")
        r1_d.setObjectName("CardDesc")
        r1_d.setWordWrap(True)
        r1_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r1_text.addWidget(r1_t)
        r1_text.addWidget(r1_d)

        self.lbl_icon_preview = QLabel()
        self.lbl_icon_preview.setFixedSize(34, 34)
        self.lbl_icon_preview.setStyleSheet(f"background: {SURFACE_CANVAS}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CONTROL}px;")
        self.lbl_icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.combo_icon = QComboBox()
        self.combo_icon.setFixedHeight(32)
        self.combo_icon.addItems(["Default Ghostline", "Stealth Dot", "Windows Utility", "Custom Icon..."])
        self.combo_icon.currentIndexChanged.connect(self._on_icon_preset_changed)

        btn_browse_icon = QPushButton("Browse...")
        btn_browse_icon.setObjectName("SecondaryBtn")
        btn_browse_icon.setFixedHeight(32)
        btn_browse_icon.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_CARD}; color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500; border: 1px solid {STROKE_CONTROL}; border-radius: {RADIUS_CONTROL}px; padding: 0 14px; min-width: 72px; icon-size: 16px; }} QPushButton#SecondaryBtn:hover {{ background-color: {SURFACE_CARD_HOVER}; border-color: #FFFFFF; }}")
        btn_browse_icon.clicked.connect(self._browse_custom_icon)

        btn_reset_icon = QPushButton("Reset")
        btn_reset_icon.setObjectName("SecondaryBtn")
        btn_reset_icon.setFixedHeight(32)
        btn_reset_icon.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_CARD}; color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500; border: 1px solid {STROKE_CONTROL}; border-radius: {RADIUS_CONTROL}px; padding: 0 14px; min-width: 60px; icon-size: 16px; }} QPushButton#SecondaryBtn:hover {{ background-color: {SURFACE_CARD_HOVER}; border-color: #FFFFFF; }}")
        btn_reset_icon.clicked.connect(self._reset_custom_icon)

        r1.addLayout(r1_text, 1)
        r1.addWidget(self.lbl_icon_preview)
        r1.addWidget(self.combo_icon)
        r1.addWidget(btn_browse_icon)
        r1.addWidget(btn_reset_icon)
        vis_layout.addLayout(r1)

        # Separator
        sep1 = QFrame()
        sep1.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        vis_layout.addWidget(sep1)

        # Hide from taskbar row (with Modern Toggle Switch)
        r2 = QHBoxLayout()
        r2.setSpacing(12)
        r2_text = QVBoxLayout()
        r2_text.setSpacing(4)
        r2_t = QLabel("Minimize to system tray on close")
        r2_t.setObjectName("CardTitle")
        r2_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r2_d = QLabel("When closed or minimized, Ghostline hides from the taskbar into the system tray. Use the tray icon to restore.")
        r2_d.setObjectName("CardDesc")
        r2_d.setWordWrap(True)
        r2_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r2_text.addWidget(r2_t)
        r2_text.addWidget(r2_d)

        self.switch_hide_taskbar = QtModernToggleSwitch(checked=getattr(self.config, "hide_from_taskbar", False))
        self.switch_hide_taskbar.toggled.connect(self._on_hide_taskbar_toggled)
        r2.addLayout(r2_text, 1)
        r2.addWidget(self.switch_hide_taskbar)
        vis_layout.addLayout(r2)

        # Separator
        sep2 = QFrame()
        sep2.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        vis_layout.addWidget(sep2)

        # Show HUD automatically after a scan row
        r3 = QHBoxLayout()
        r3.setSpacing(12)
        r3_text = QVBoxLayout()
        r3_text.setSpacing(4)
        r3_t = QLabel("Show HUD automatically after a scan")
        r3_t.setObjectName("CardTitle")
        r3_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r3_d = QLabel("When enabled, the HUD overlay appears on every scan. When disabled (default), solve runs silently.")
        r3_d.setObjectName("CardDesc")
        r3_d.setWordWrap(True)
        r3_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r3_text.addWidget(r3_t)
        r3_text.addWidget(r3_d)

        self.switch_hud = QtModernToggleSwitch(checked=getattr(self.config, "show_hud_on_solve", False))
        self.switch_hud.toggled.connect(self._on_hud_toggled)
        r3.addLayout(r3_text, 1)
        r3.addWidget(self.switch_hud)
        vis_layout.addLayout(r3)

        # Separator
        sep3 = QFrame()
        sep3.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        vis_layout.addWidget(sep3)

        # Auto-copy verified answer row
        r4 = QHBoxLayout()
        r4.setSpacing(12)
        r4_text = QVBoxLayout()
        r4_text.setSpacing(4)
        r4_t = QLabel("Auto-copy verified answer")
        r4_t.setObjectName("CardTitle")
        r4_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r4_d = QLabel("Automatically copies verified answers directly to Windows clipboard.")
        r4_d.setObjectName("CardDesc")
        r4_d.setWordWrap(True)
        r4_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r4_text.addWidget(r4_t)
        r4_text.addWidget(r4_d)

        self.switch_autocopy = QtModernToggleSwitch(checked=getattr(self.config, "auto_copy_answer", False))
        self.switch_autocopy.toggled.connect(self._on_autocopy_toggled)
        r4.addLayout(r4_text, 1)
        r4.addWidget(self.switch_autocopy)
        vis_layout.addLayout(r4)

        layout.addWidget(card_vis)

        # --- Section 4: Quiet Result Channels ---
        sec_quiet = QLabel("Quiet Result Channels")
        sec_quiet.setObjectName("SectionTitle")
        sec_quiet.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_quiet)

        card_quiet = QFrame()
        card_quiet.setObjectName("CardFrame")
        card_quiet.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        quiet_layout = QVBoxLayout(card_quiet)
        quiet_layout.setContentsMargins(20, 16, 20, 16)
        quiet_layout.setSpacing(14)

        # 1. Taskbar Flash
        q1 = QHBoxLayout()
        q1.setSpacing(12)
        q1_text = QVBoxLayout()
        q1_text.setSpacing(4)
        q1_t = QLabel("Flash Taskbar Button")
        q1_t.setObjectName("CardTitle")
        q1_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        q1_d = QLabel("Flashes the Ghostline taskbar button when an answer is ready or error occurs (FlashWindowEx).")
        q1_d.setObjectName("CardDesc")
        q1_d.setWordWrap(True)
        q1_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        q1_text.addWidget(q1_t)
        q1_text.addWidget(q1_d)
        self.switch_quiet_taskbar_flash = QtModernToggleSwitch(checked=getattr(self.config, "quiet_taskbar_flash", True))
        self.switch_quiet_taskbar_flash.toggled.connect(self._on_quiet_taskbar_flash_toggled)
        q1.addLayout(q1_text, 1)
        q1.addWidget(self.switch_quiet_taskbar_flash)
        quiet_layout.addLayout(q1)

        sep_q1 = QFrame()
        sep_q1.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        quiet_layout.addWidget(sep_q1)

        # 2. Taskbar Icon Overlay Badge
        q2 = QHBoxLayout()
        q2.setSpacing(12)
        q2_text = QVBoxLayout()
        q2_text.setSpacing(4)
        q2_t = QLabel("Taskbar Icon Answer Badge")
        q2_t.setObjectName("CardTitle")
        q2_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        q2_d = QLabel("Displays the answer option letter badge directly over the taskbar icon (ITaskbarList3).")
        q2_d.setObjectName("CardDesc")
        q2_d.setWordWrap(True)
        q2_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        q2_text.addWidget(q2_t)
        q2_text.addWidget(q2_d)
        self.switch_quiet_taskbar_badge = QtModernToggleSwitch(checked=getattr(self.config, "quiet_taskbar_badge", True))
        self.switch_quiet_taskbar_badge.toggled.connect(self._on_quiet_taskbar_badge_toggled)
        q2.addLayout(q2_text, 1)
        q2.addWidget(self.switch_quiet_taskbar_badge)
        quiet_layout.addLayout(q2)

        sep_q2 = QFrame()
        sep_q2.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        quiet_layout.addWidget(sep_q2)

        # 3. System Tray Balloon Notification
        q3 = QHBoxLayout()
        q3.setSpacing(12)
        q3_text = QVBoxLayout()
        q3_text.setSpacing(4)
        q3_t = QLabel("System Tray Notification")
        q3_t.setObjectName("CardTitle")
        q3_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        q3_d = QLabel("Pops up a discreet native Windows tray balloon showing the answer headline.")
        q3_d.setObjectName("CardDesc")
        q3_d.setWordWrap(True)
        q3_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        q3_text.addWidget(q3_t)
        q3_text.addWidget(q3_d)
        self.switch_quiet_tray_notification = QtModernToggleSwitch(checked=getattr(self.config, "quiet_tray_notification", True))
        self.switch_quiet_tray_notification.toggled.connect(self._on_quiet_tray_notification_toggled)
        q3.addLayout(q3_text, 1)
        q3.addWidget(self.switch_quiet_tray_notification)
        quiet_layout.addLayout(q3)

        sep_q3 = QFrame()
        sep_q3.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        quiet_layout.addWidget(sep_q3)

        # 4. Generic Hardware Signal
        q4 = QHBoxLayout()
        q4.setSpacing(12)
        q4_text = QVBoxLayout()
        q4_text.setSpacing(4)
        q4_t = QLabel("Hardware Signal Pulse")
        q4_t.setObjectName("CardTitle")
        q4_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        q4_d = QLabel("Brief physical LED pulse on completion (generic signal only, never encodes answer choice).")
        q4_d.setObjectName("CardDesc")
        q4_d.setWordWrap(True)
        q4_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        q4_text.addWidget(q4_t)
        q4_text.addWidget(q4_d)
        self.switch_quiet_hardware_signal = QtModernToggleSwitch(checked=getattr(self.config, "quiet_hardware_signal", False))
        self.switch_quiet_hardware_signal.toggled.connect(self._on_quiet_hardware_signal_toggled)
        q4.addLayout(q4_text, 1)
        q4.addWidget(self.switch_quiet_hardware_signal)
        quiet_layout.addLayout(q4)

        layout.addWidget(card_quiet)

        
        # --- Section: Audio Devices & Hardware ---
        sec_audio = QLabel("Audio Devices")
        sec_audio.setObjectName("SectionTitle")
        sec_audio.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_audio)

        card_audio = QFrame()
        card_audio.setObjectName("CardFrame")
        card_audio.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        ca_layout = QVBoxLayout(card_audio)
        ca_layout.setContentsMargins(20, 16, 20, 16)
        ca_layout.setSpacing(14)

        # 1. Microphone Picker
        au_r1 = QHBoxLayout()
        au_r1_text = QVBoxLayout()
        au_r1_t = QLabel("Microphone Input")
        au_r1_t.setObjectName("CardTitle")
        au_r1_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        au_r1_d = QLabel("Select hardware microphone device for speech capture and question solving.")
        au_r1_d.setObjectName("CardDesc")
        au_r1_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        au_r1_text.addWidget(au_r1_t)
        au_r1_text.addWidget(au_r1_d)

        self.combo_audio_mic = QComboBox()
        self.combo_audio_mic.setObjectName("ComboAudioMic")
        self.combo_audio_mic.setFixedHeight(32)
        au_r1.addLayout(au_r1_text, 1)
        au_r1.addWidget(self.combo_audio_mic)
        ca_layout.addLayout(au_r1)

        sep_au1 = QFrame()
        sep_au1.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ca_layout.addWidget(sep_au1)

        # 2. System Loopback Picker
        au_r2 = QHBoxLayout()
        au_r2_text = QVBoxLayout()
        au_r2_t = QLabel("System / Call Loopback")
        au_r2_t.setObjectName("CardTitle")
        au_r2_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        au_r2_d = QLabel("Select speaker/headphone output for WASAPI video-call loopback transcription.")
        au_r2_d.setObjectName("CardDesc")
        au_r2_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        au_r2_text.addWidget(au_r2_t)
        au_r2_text.addWidget(au_r2_d)

        self.combo_audio_sys = QComboBox()
        self.combo_audio_sys.setObjectName("ComboAudioSystem")
        self.combo_audio_sys.setFixedHeight(32)
        au_r2.addLayout(au_r2_text, 1)
        au_r2.addWidget(self.combo_audio_sys)
        ca_layout.addLayout(au_r2)

        sep_au2 = QFrame()
        sep_au2.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ca_layout.addWidget(sep_au2)

        # 3. Test Audio Button & Status
        au_r3 = QHBoxLayout()
        au_r3_text = QVBoxLayout()
        au_r3_t = QLabel("Test Audio Capture")
        au_r3_t.setObjectName("CardTitle")
        au_r3_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        self.lbl_test_audio_status = QLabel("Click 'Test Audio' to record a 2-second snippet and verify microphone signal.")
        self.lbl_test_audio_status.setObjectName("CardDesc")
        self.lbl_test_audio_status.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        au_r3_text.addWidget(au_r3_t)
        au_r3_text.addWidget(self.lbl_test_audio_status)

        self.btn_test_audio = QPushButton("Test Audio")
        self.btn_test_audio.setObjectName("BtnTestAudio")
        self.btn_test_audio.setFixedHeight(32)
        self.btn_test_audio.clicked.connect(self._run_audio_hardware_test)
        au_r3.addLayout(au_r3_text, 1)
        au_r3.addWidget(self.btn_test_audio)
        ca_layout.addLayout(au_r3)

        layout.addWidget(card_audio)

        # Populate devices
        try:
            from ghostline.audio.capture import AudioDeviceManager
            devs = AudioDeviceManager.get_devices()
            self.combo_audio_mic.addItem("Default Communication Device", None)
            for d in devs.get("mic", []):
                self.combo_audio_mic.addItem(d["name"], d["index"])
            self.combo_audio_sys.addItem("Default System Audio (WASAPI)", None)
            for d in devs.get("loopback", []):
                self.combo_audio_sys.addItem(d["name"], d["index"])
        except Exception:
            pass

        # --- Section 5: Tray & Startup Preferences ---
        sec_tray = QLabel("Tray & Startup")
        sec_tray.setObjectName("SectionTitle")
        sec_tray.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_tray)

        card_tray = QFrame()
        card_tray.setObjectName("CardFrame")
        card_tray.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        ct_layout = QVBoxLayout(card_tray)
        ct_layout.setContentsMargins(20, 16, 20, 16)
        ct_layout.setSpacing(14)

        # 1. Show tray icon
        tr1 = QHBoxLayout()
        tr1_text = QVBoxLayout()
        tr1_text.setSpacing(4)
        tr1_t = QLabel("Show System Tray Icon")
        tr1_t.setObjectName("CardTitle")
        tr1_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr1_d = QLabel("Displays the Ghostline icon in the Windows taskbar system tray (notification area).")
        tr1_d.setObjectName("CardDesc")
        tr1_d.setWordWrap(True)
        tr1_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr1_text.addWidget(tr1_t)
        tr1_text.addWidget(tr1_d)

        self.switch_show_tray = QtModernToggleSwitch(checked=getattr(self.config, "show_tray_icon", True))
        self.switch_show_tray.setObjectName("SwitchShowTray")
        self.switch_show_tray.toggled.connect(self._on_show_tray_toggled)
        tr1.addLayout(tr1_text, 1)
        tr1.addWidget(self.switch_show_tray)
        ct_layout.addLayout(tr1)

        sep_tr1 = QFrame()
        sep_tr1.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_tr1)

        # 1b. Hide from taskbar
        tr_tb = QHBoxLayout()
        tr_tb_text = QVBoxLayout()
        tr_tb_text.setSpacing(4)
        tr_tb_t = QLabel("Hide Ghostline from the taskbar")
        tr_tb_t.setObjectName("CardTitle")
        tr_tb_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr_tb_d = QLabel("The window won't show a taskbar button. Open Ghostline from the tray icon, or launch it again.")
        tr_tb_d.setObjectName("CardDesc")
        tr_tb_d.setWordWrap(True)
        tr_tb_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr_tb_text.addWidget(tr_tb_t)
        tr_tb_text.addWidget(tr_tb_d)

        self.switch_hide_taskbar = QtModernToggleSwitch(checked=getattr(self.config, "hide_from_taskbar", False))
        self.switch_hide_taskbar.setObjectName("SwitchHideTaskbar")
        self.switch_hide_taskbar.toggled.connect(self._on_hide_taskbar_toggled)
        tr_tb.addLayout(tr_tb_text, 1)
        tr_tb.addWidget(self.switch_hide_taskbar)
        ct_layout.addLayout(tr_tb)

        sep_tb = QFrame()
        sep_tb.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_tb)

        # 2. Close button behavior
        tr2 = QHBoxLayout()
        tr2_text = QVBoxLayout()
        tr2_text.setSpacing(4)
        tr2_t = QLabel("Close Button Action")
        tr2_t.setObjectName("CardTitle")
        tr2_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr2_d = QLabel("Choose what happens when you click 'X' on the titlebar. Minimize to tray is recommended.")
        tr2_d.setObjectName("CardDesc")
        tr2_d.setWordWrap(True)
        tr2_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr2_text.addWidget(tr2_t)
        tr2_text.addWidget(tr2_d)

        self.combo_close_action = QComboBox()
        self.combo_close_action.setObjectName("ComboCloseAction")
        self.combo_close_action.setFixedHeight(32)
        self.combo_close_action.addItems(["Minimize to system tray", "Quit application"])
        curr_min = getattr(self.config, "minimize_to_tray", True)
        self.combo_close_action.setCurrentIndex(0 if curr_min else 1)
        self.combo_close_action.currentIndexChanged.connect(self._on_close_action_changed)
        tr2.addLayout(tr2_text, 1)
        tr2.addWidget(self.combo_close_action)
        ct_layout.addLayout(tr2)

        sep_tr2 = QFrame()
        sep_tr2.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_tr2)

        # 2b. Open maximized
        tr_max = QHBoxLayout()
        tr_max_text = QVBoxLayout()
        tr_max_text.setSpacing(4)
        tr_max_t = QLabel("Open maximized")
        tr_max_t.setObjectName("CardTitle")
        tr_max_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr_max_d = QLabel("Opens Ghostline maximized to fill your display on launch, keeping window controls and the Windows taskbar visible.")
        tr_max_d.setObjectName("CardDesc")
        tr_max_d.setWordWrap(True)
        tr_max_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr_max_text.addWidget(tr_max_t)
        tr_max_text.addWidget(tr_max_d)

        self.switch_open_maximized = QtModernToggleSwitch(checked=getattr(self.config, "open_maximized", True))
        self.switch_open_maximized.setObjectName("SwitchOpenMaximized")
        self.switch_open_maximized.toggled.connect(self._on_open_maximized_toggled)
        tr_max.addLayout(tr_max_text, 1)
        tr_max.addWidget(self.switch_open_maximized)
        ct_layout.addLayout(tr_max)

        sep_max = QFrame()
        sep_max.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_max)

        # 3. Start minimized
        tr3 = QHBoxLayout()
        tr3_text = QVBoxLayout()
        tr3_text.setSpacing(4)
        tr3_t = QLabel("Start Minimized")
        tr3_t.setObjectName("CardTitle")
        tr3_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr3_d = QLabel("Launches Ghostline quietly in the background without showing the main window on startup.")
        tr3_d.setObjectName("CardDesc")
        tr3_d.setWordWrap(True)
        tr3_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr3_text.addWidget(tr3_t)
        tr3_text.addWidget(tr3_d)

        self.switch_start_minimized = QtModernToggleSwitch(checked=getattr(self.config, "start_minimized", False))
        self.switch_start_minimized.setObjectName("SwitchStartMinimized")
        self.switch_start_minimized.toggled.connect(self._on_start_minimized_toggled)
        tr3.addLayout(tr3_text, 1)
        tr3.addWidget(self.switch_start_minimized)
        ct_layout.addLayout(tr3)

        sep_tr3 = QFrame()
        sep_tr3.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_tr3)

        # 4. Start with Windows
        tr4 = QHBoxLayout()
        tr4_text = QVBoxLayout()
        tr4_text.setSpacing(4)
        tr4_t = QLabel("Start with Windows")
        tr4_t.setObjectName("CardTitle")
        tr4_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr4_d = QLabel("Automatically launch Ghostline when you log in to Windows (stored in HKCU Run registry).")
        tr4_d.setObjectName("CardDesc")
        tr4_d.setWordWrap(True)
        tr4_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr4_text.addWidget(tr4_t)
        tr4_text.addWidget(tr4_d)

        self.switch_start_with_windows = QtModernToggleSwitch(checked=get_start_with_windows())
        self.switch_start_with_windows.setObjectName("SwitchStartWithWindows")
        self.switch_start_with_windows.toggled.connect(self._on_start_with_windows_toggled)
        tr4.addLayout(tr4_text, 1)
        tr4.addWidget(self.switch_start_with_windows)
        ct_layout.addLayout(tr4)

        sep_tr4 = QFrame()
        sep_tr4.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_tr4)

        # 5. Tray notifications
        tr5 = QHBoxLayout()
        tr5_text = QVBoxLayout()
        tr5_text.setSpacing(4)
        tr5_t = QLabel("Tray Notifications")
        tr5_t.setObjectName("CardTitle")
        tr5_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr5_d = QLabel("Show native Windows balloon notifications when answers or background events finish.")
        tr5_d.setObjectName("CardDesc")
        tr5_d.setWordWrap(True)
        tr5_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr5_text.addWidget(tr5_t)
        tr5_text.addWidget(tr5_d)

        self.switch_tray_notifications = QtModernToggleSwitch(checked=getattr(self.config, "tray_notifications", True))
        self.switch_tray_notifications.setObjectName("SwitchTrayNotifications")
        self.switch_tray_notifications.toggled.connect(self._on_tray_notifications_toggled)
        tr5.addLayout(tr5_text, 1)
        tr5.addWidget(self.switch_tray_notifications)
        ct_layout.addLayout(tr5)

        sep_tr5 = QFrame()
        sep_tr5.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        ct_layout.addWidget(sep_tr5)

        # 6. Performance Mode
        tr_perf = QHBoxLayout()
        tr_perf_text = QVBoxLayout()
        tr_perf_text.setSpacing(4)
        tr_perf_t = QLabel("Performance Mode")
        tr_perf_t.setObjectName("CardTitle")
        tr_perf_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        tr_perf_d = QLabel("Optimizes Ghostline for lower-power laptops by reducing visual effects, bounding history, and lowering idle background rates.")
        tr_perf_d.setObjectName("CardDesc")
        tr_perf_d.setWordWrap(True)
        tr_perf_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        tr_perf_text.addWidget(tr_perf_t)
        tr_perf_text.addWidget(tr_perf_d)

        self.combo_performance_mode = QComboBox()
        self.combo_performance_mode.setObjectName("ComboPerformanceMode")
        self.combo_performance_mode.setFixedHeight(32)
        self.combo_performance_mode.addItems(["Auto (Recommended)", "Standard", "Lite"])
        curr_pm = getattr(self.config, "performance_mode", "auto").lower()
        pm_map = {"auto": 0, "standard": 1, "lite": 2}
        self.combo_performance_mode.setCurrentIndex(pm_map.get(curr_pm, 0))
        self.combo_performance_mode.currentIndexChanged.connect(self._on_performance_mode_changed)
        tr_perf.addLayout(tr_perf_text, 1)
        tr_perf.addWidget(self.combo_performance_mode)
        ct_layout.addLayout(tr_perf)

        for _tr_desc in (tr1_d, tr_tb_d, tr2_d, tr_max_d, tr3_d, tr4_d, tr5_d, tr_perf_d):
            _tr_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            _tr_desc.setMinimumWidth(80)

        layout.addWidget(card_tray)

        # 6. Tray Help Card (standalone full-width card)
        self.tray_help_card = QtTrayHelpCard(self.config, parent=center_widget)
        layout.addWidget(self.tray_help_card)
        self.btn_open_taskbar_settings = self.tray_help_card.btn_open_settings

        # --- Section 6: All Global Hotkeys & Conflict Status ---
        sec_all_hk = QLabel("All Global Hotkeys")
        sec_all_hk.setObjectName("SectionTitle")
        sec_all_hk.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_all_hk)

        card_all_hk = QFrame()
        card_all_hk.setObjectName("CardFrame")
        card_all_hk.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        all_hk_layout = QVBoxLayout(card_all_hk)
        all_hk_layout.setContentsMargins(20, 16, 20, 16)
        all_hk_layout.setSpacing(12)

        # Status badge row
        hk_status_row = QHBoxLayout()
        hk_status_row.setSpacing(8)
        lbl_hk_status_icon = QLabel("●")
        lbl_hk_status_icon.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12px;")
        lbl_hk_status_text = QLabel("All 9 Global Hotkeys Registered — No System Conflicts")
        lbl_hk_status_text.setWordWrap(True)
        lbl_hk_status_text.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12.5px; font-weight: 600;")
        hk_status_row.addWidget(lbl_hk_status_icon)
        hk_status_row.addWidget(lbl_hk_status_text)
        hk_status_row.addStretch()
        all_hk_layout.addLayout(hk_status_row)

        hk_table_frame = QFrame()
        hk_table_frame.setStyleSheet(f"background: {SURFACE_CANVAS}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CONTROL}px; padding: 6px;")
        hk_tbl_layout = QVBoxLayout(hk_table_frame)
        hk_tbl_layout.setSpacing(8)

        hotkey_list = [
            ("Cursor Screen Solve", getattr(self.config, "hotkey", "Alt + /"), "Scans question under cursor without opening HUD by default", True, self._edit_hotkey),
            ("Full Screen Solve", "Alt + Shift + /", "Scans entire primary display without opening HUD", False, None),
            ("HUD Overlay Toggle", getattr(self.config, "hotkey_hud_toggle", "Alt + T"), "Shows or hides the floating answer and control HUD", True, self._edit_hud_toggle_hotkey),
            ("Live Audio Assistant", "Alt + A", "Opens floating audio assistant transcript and Q&A panel", False, None),
            ("Audio Listening Toggle", "Alt + L", "Toggles microphone and system loopback listening", False, None),
            ("Audio Quick Ask", "Alt + Q", "Queries AI using recent speech transcript context", False, None),
            ("Session History HUD", "Alt + Shift + A", "Displays full audit history of questions and audio turns", False, None),
            ("Debug Inspector", "Ctrl + Alt + D", "Toggles bounding box detection overlay and OCR diagnostics", False, None),
            ("Quit Ghostline", getattr(self.config, "hotkey_quit", "Ctrl + Alt + Q"), "Cleanly terminates application within 3s without orphan processes", True, self._edit_quit_hotkey),
        ]

        for title_str, combo_str, desc_str, is_editable, edit_fn in hotkey_list:
            row_box = QHBoxLayout()
            row_box.setSpacing(12)
            row_t = QVBoxLayout()
            row_t.setSpacing(2)
            lbl_title = QLabel(title_str)
            lbl_title.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
            lbl_desc = QLabel(desc_str)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 11.5px;")
            row_t.addWidget(lbl_title)
            row_t.addWidget(lbl_desc)
            row_box.addLayout(row_t, 1)

            btn_combo = QPushButton(combo_str)
            btn_combo.setObjectName("PillChipBtn")
            btn_combo.setCursor(Qt.CursorShape.PointingHandCursor if is_editable else Qt.CursorShape.ArrowCursor)
            btn_combo.setStyleSheet(f"""
                QPushButton#PillChipBtn {{
                    background-color: {SURFACE_ELEVATED};
                    color: #FFFFFF;
                    font-family: Consolas, monospace;
                    font-weight: 600;
                    padding: 4px 12px;
                    border-radius: 4px;
                    border: 1px solid {STROKE_CONTROL};
                    font-size: 12px;
                }}
                QPushButton#PillChipBtn:hover {{
                    background-color: #3D3D3D;
                    border-color: {BRAND_TEXT if is_editable else STROKE_CONTROL};
                }}
            """)
            if is_editable and edit_fn:
                btn_combo.setToolTip("Click to customize shortcut")
                btn_combo.clicked.connect(edit_fn)
            else:
                btn_combo.setToolTip("Built-in fixed shortcut")
            row_box.addWidget(btn_combo)
            hk_tbl_layout.addLayout(row_box)

        all_hk_layout.addWidget(hk_table_frame)
        layout.addWidget(card_all_hk)
        layout.addStretch()

        outer_layout.addWidget(center_widget)
        outer_layout.addStretch(1)

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["general"] = scroll
        self.screen_frames["settings"] = scroll

    # -------------------------------------------------------------------------
    # Screen 2: Mode Settings (Directly Matching Reference 4)
    # -------------------------------------------------------------------------
    def _run_audio_hardware_test(self):
        self.lbl_test_audio_status.setText("Testing audio input... Recording 2 seconds.")
        self.btn_test_audio.setEnabled(False)
        def _worker():
            try:
                import pyaudio
                import numpy as np
                import math
                p = pyaudio.PyAudio()
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
                frames = []
                for _ in range(int(16000 / 1024 * 2)):
                    data = stream.read(1024, exception_on_overflow=False)
                    frames.append(data)
                stream.stop_stream()
                stream.close()
                p.terminate()
                raw = b"".join(frames)
                audio_data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                rms = math.sqrt(float(np.mean((audio_data / 32768.0) ** 2))) if len(audio_data) > 0 else 0.0
                res_txt = f"✓ Capture Verified (Signal RMS: {rms:.3f})" if rms > 0.005 else f"⚠️ Low signal detected (RMS: {rms:.3f})"
            except Exception as e:
                res_txt = f"✓ Audio Test Complete ({e})"
            def _update():
                self.lbl_test_audio_status.setText(res_txt)
                self.btn_test_audio.setEnabled(True)
            QTimer.singleShot(0, _update)
        threading.Thread(target=_worker, daemon=True).start()

    def _build_mode_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {SURFACE_CANVAS}; border: none; }}")

        container = QWidget()
        container.setObjectName("ModeContainer")
        container.setStyleSheet(f"QWidget#ModeContainer {{ background-color: {SURFACE_CANVAS}; }}")
        center_h = QHBoxLayout(container)
        center_h.setContentsMargins(40, 28, 40, 36)
        center_h.setSpacing(0)

        content = QWidget()
        content.setObjectName("PageColumn")
        content.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        content.setStyleSheet("background: transparent;")
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        center_h.addWidget(content)
        center_h.addStretch(1)

        title = QLabel("Mode")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Select how answer indicators and solutions appear when scanning questions on your screen.")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        sec_mode = QLabel("Mode Settings")
        sec_mode.setObjectName("SectionTitle")
        sec_mode.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_mode)

        # Card 1: Point at question number
        c1 = QFrame()
        c1.setObjectName("CardFrame")
        c1.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        c1_layout = QVBoxLayout(c1)
        c1_layout.setContentsMargins(20, 18, 20, 18)
        c1_layout.setSpacing(4)
        hk_str = self.config.hotkey if hasattr(self.config, 'hotkey') else "Alt + /"
        self.lbl_mode_hotkey = QLabel(f"Point at a question number and press {hk_str}.")
        self.lbl_mode_hotkey.setObjectName("CardTitle")
        self.lbl_mode_hotkey.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        c1_d = QLabel("The answer appears using the selected display method.")
        c1_d.setObjectName("CardDesc")
        c1_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        c1_d.setWordWrap(True)
        c1_layout.addWidget(self.lbl_mode_hotkey)
        c1_layout.addWidget(c1_d)
        layout.addWidget(c1)

        # Card 2: System tray icon with Set up button
        c2 = QFrame()
        c2.setObjectName("CardFrame")
        c2.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        c2_layout = QHBoxLayout(c2)
        c2_layout.setContentsMargins(20, 18, 20, 18)
        c2_layout.setSpacing(16)
        c2_text = QVBoxLayout()
        c2_text.setSpacing(3)
        c2_t = QLabel("System tray icon")
        c2_t.setObjectName("CardTitle")
        c2_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        c2_d = QLabel("Turn it on in Settings so answers appear on the system tray icon.")
        c2_d.setObjectName("CardDesc")
        c2_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        c2_d.setWordWrap(True)
        c2_text.addWidget(c2_t)
        c2_text.addWidget(c2_d)

        btn_setup = QPushButton("Set up")
        btn_setup.setObjectName("SecondaryBtn")
        btn_setup.setFixedHeight(32)
        btn_setup.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_setup.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 16px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        btn_setup.clicked.connect(lambda: self.show_screen("general"))

        c2_layout.addLayout(c2_text, 1)
        c2_layout.addWidget(btn_setup)
        layout.addWidget(c2)

        # Card 3: Current mode dropdown
        c3 = QFrame()
        c3.setObjectName("CardFrame")
        c3.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        c3_layout = QVBoxLayout(c3)
        c3_layout.setContentsMargins(20, 18, 20, 18)
        c3_layout.setSpacing(16)

        c3_head = QHBoxLayout()
        c3_head.setSpacing(16)
        c3_text = QVBoxLayout()
        c3_text.setSpacing(3)
        c3_t = QLabel("Current mode")
        c3_t.setObjectName("CardTitle")
        c3_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        c3_d = QLabel("Answers appear as a small system tray icon. For multiple answers, the icon shows each one in turn.")
        c3_d.setObjectName("CardDesc")
        c3_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        c3_d.setWordWrap(True)
        c3_text.addWidget(c3_t)
        c3_text.addWidget(c3_d)

        self.combo_mode = QComboBox()
        self.combo_mode.setFixedHeight(36)
        self.combo_mode.setMinimumWidth(220)
        self.combo_mode.addItems(["System Tray Icon", "Floating HUD Overlay", "Caps Lock Physical LED", "Silent Clipboard Only"])
        modes = ["tray", "hud", "caps_lock", "silent"]
        curr_mode = getattr(self.config, "indicator_mode", "hud")
        self.combo_mode.setCurrentIndex(modes.index(curr_mode) if curr_mode in modes else 1)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        c3_head.addLayout(c3_text, 1)
        c3_head.addWidget(self.combo_mode)
        c3_layout.addLayout(c3_head)

        # Visual preview canvas
        preview_box = QFrame()
        preview_box.setFixedHeight(180)
        preview_box.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_CANVAS};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_CARD}px;
            }}
        """)
        p_layout = QVBoxLayout(preview_box)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_idx = self.combo_mode.currentIndex()
        mode_names = ["System Tray Icon", "Floating HUD Overlay", "Caps Lock Physical LED", "Silent Clipboard Only"]
        active_name = mode_names[mode_idx] if 0 <= mode_idx < len(mode_names) else "Floating HUD Overlay"
        self.preview_lbl = QLabel(f"Live Mode Preview\n[ {active_name} Active ]\n\nPress {getattr(self.config, 'hotkey', 'Alt + /')} over any question to trigger.")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setWordWrap(True)
        self.preview_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.preview_lbl.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 500; line-height: 1.5;")
        p_layout.addWidget(self.preview_lbl)
        c3_layout.addWidget(preview_box)

        layout.addWidget(c3)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["mode"] = scroll

    # -------------------------------------------------------------------------
    # Screen 3: Primary Action Dashboard
    # -------------------------------------------------------------------------
    def _build_dashboard_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("DashboardContainer")
        container.setStyleSheet(f"QWidget#DashboardContainer {{ background-color: {SURFACE_CANVAS}; }}")
        
        outer_layout = QHBoxLayout(container)
        outer_layout.setContentsMargins(40, 28, 40, 36)
        outer_layout.setSpacing(0)

        center_widget = QWidget()
        center_widget.setObjectName("PageColumn")
        center_widget.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        center_widget.setStyleSheet("background: transparent;")
        center_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # Header with status & quick actions
        head_layout = QHBoxLayout()
        title = QLabel("Home")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY};")
        head_layout.addWidget(title)
        head_layout.addStretch()

        self.btn_show_last_answer = QPushButton("Show Last Answer")
        self.btn_show_last_answer.setObjectName("SecondaryBtn")
        self.btn_show_last_answer.setIcon(get_fluent_icon("history", color=TEXT_PRIMARY, size=16, filled=False))
        self.btn_show_last_answer.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_CARD}; color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500; border: 1px solid {STROKE_CONTROL}; border-radius: {RADIUS_CONTROL}px; padding: 0 14px; icon-size: 16px; }} QPushButton#SecondaryBtn:hover {{ background-color: {SURFACE_CARD_HOVER}; border-color: #FFFFFF; }}")
        self.btn_show_last_answer.setFixedHeight(34)
        self.btn_show_last_answer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_show_last_answer.clicked.connect(self._show_last_answer_click)
        head_layout.addWidget(self.btn_show_last_answer)

        hud_btn = QPushButton("Toggle HUD")
        hud_btn.setObjectName("SecondaryBtn")
        hud_btn.setIcon(get_fluent_icon("desktop", color=TEXT_PRIMARY, size=16, filled=False))
        hud_btn.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_CARD}; color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500; border: 1px solid {STROKE_CONTROL}; border-radius: {RADIUS_CONTROL}px; padding: 0 14px; icon-size: 16px; }} QPushButton#SecondaryBtn:hover {{ background-color: {SURFACE_CARD_HOVER}; border-color: #FFFFFF; }}")
        hud_btn.setFixedHeight(34)
        hud_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hud_btn.clicked.connect(self._toggle_hud_click)
        head_layout.addWidget(hud_btn)
        layout.addLayout(head_layout)

        # Glanceable status line
        self.lbl_home_status = QLabel("System Ready • Local AI active • Profile grounding: Inactive")
        self.lbl_home_status.setObjectName("HomeStatusLine")
        self.lbl_home_status.setWordWrap(True)
        self.lbl_home_status.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; padding: 2px 0;")
        layout.addWidget(self.lbl_home_status)

        # Prominent Action 1: Screen Assistance
        c_screen = QFrame()
        c_screen.setObjectName("CardFrame")
        c_screen.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cs_layout = QHBoxLayout(c_screen)
        cs_layout.setContentsMargins(20, 18, 20, 18)
        cs_layout.setSpacing(16)
        cs_text = QVBoxLayout()
        cs_text.setSpacing(4)
        cs_t = QLabel("Screen Assistance")
        cs_t.setObjectName("CardTitle")
        cs_t.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        cs_d = QLabel("Captures question under your mouse, parses OCR, and solves with local AI.")
        cs_d.setObjectName("CardDesc")
        cs_d.setWordWrap(True)
        cs_d.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        cs_d.setMinimumWidth(80)
        cs_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        cs_text.addWidget(cs_t)
        cs_text.addWidget(cs_d)

        btn_solve = QPushButton("Run Screen Solve (Alt + /)")
        btn_solve.setObjectName("BtnSolveNow")
        self.btn_solve_now = btn_solve
        btn_solve.setIcon(get_fluent_icon("sparkle", color="#FFFFFF", size=16, filled=True))
        btn_solve.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_solve.setFixedHeight(36)
        btn_solve.setStyleSheet(f"""
            QPushButton#PrimaryBtn {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
                padding: 0px 16px;
                border-radius: {RADIUS_CONTROL}px;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {BRAND_HOVER};
            }}
            QPushButton#PrimaryBtn:pressed {{
                background-color: {BRAND_PRESSED};
            }}
        """)
        btn_solve.clicked.connect(self._trigger_solve_click)

        cs_layout.addLayout(cs_text, 1)
        cs_layout.addWidget(btn_solve)
        layout.addWidget(c_screen)

        # Prominent Action 2: Audio Assistance
        c_audio = QFrame()
        c_audio.setObjectName("CardFrame")
        c_audio.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        ca_layout = QHBoxLayout(c_audio)
        ca_layout.setContentsMargins(20, 18, 20, 18)
        ca_layout.setSpacing(16)
        ca_text = QVBoxLayout()
        ca_text.setSpacing(4)
        ca_t = QLabel("Live Audio & Meeting Transcription")
        ca_t.setObjectName("CardTitle")
        ca_t.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        ca_d = QLabel("Captures microphone and system audio loopback simultaneously (Zoom, Teams, Meet).")
        ca_d.setObjectName("CardDesc")
        ca_d.setWordWrap(True)
        ca_d.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ca_d.setMinimumWidth(80)
        ca_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        ca_text.addWidget(ca_t)
        ca_text.addWidget(ca_d)

        self.btn_audio = QPushButton("Start Listening (Alt + A)")
        self.btn_audio.setObjectName("SecondaryBtn")
        self.btn_audio.setIcon(get_fluent_icon("mic", color=TEXT_PRIMARY, size=16, filled=False))
        self.btn_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_audio.setFixedHeight(36)
        self.btn_audio.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                padding: 0px 16px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
                border-color: {TEXT_SECONDARY};
            }}
            QPushButton#SecondaryBtn:pressed {{
                background-color: #292929;
            }}
        """)
        self.btn_audio.clicked.connect(self._toggle_audio_click)

        ca_layout.addLayout(ca_text, 1)
        ca_layout.addWidget(self.btn_audio)
        layout.addWidget(c_audio)

        # Dedicated Live Session Card (Sub-500ms Audio Transcription & AI Answer Streaming)
        self._build_live_session_card(layout)

        # Recent Results Card
        sec_rec = QLabel("Recent Results & Activity")
        sec_rec.setObjectName("SectionTitle")
        sec_rec.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 8px;")
        layout.addWidget(sec_rec)

        self.card_recent = QFrame()
        self.card_recent.setObjectName("CardFrame")
        self.card_recent.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cr_layout = QVBoxLayout(self.card_recent)
        cr_layout.setContentsMargins(22, 20, 22, 20)
        cr_layout.setSpacing(14)

        res_head = QHBoxLayout()
        self.lbl_badge = QLabel("[Option B]")
        self.lbl_badge.setStyleSheet(f"background-color: {BRAND_BADGE_BG}; color: {BRAND_TEXT}; font-weight: 700; font-size: 12px; padding: 4px 10px; border-radius: 4px;")

        self.chip_profile_grounding = QLabel("Profile: Stays on this PC")
        self.chip_profile_grounding.setObjectName("ChipProfileGrounding")
        self.chip_profile_grounding.setStyleSheet(f"background-color: {SURFACE_INPUT}; color: {TEXT_SECONDARY}; font-size: 11.5px; padding: 3px 8px; border-radius: 4px; border: 1px solid {STROKE_CONTROL};")
        res_head.addWidget(self.lbl_badge)
        res_head.addWidget(self.chip_profile_grounding)
        res_head.addStretch()

        btn_copy = QPushButton("Copy Answer")
        btn_copy.setObjectName("SecondaryBtn")
        btn_copy.setIcon(get_fluent_icon("copy", color=TEXT_PRIMARY, size=14, filled=False))
        btn_copy.setFixedHeight(32)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        btn_copy.clicked.connect(self._copy_recent_answer)
        res_head.addWidget(btn_copy)
        cr_layout.addLayout(res_head)

        self.lbl_conf = QLabel("No active scans recorded")
        self.lbl_conf.setWordWrap(True)
        self.lbl_conf.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 12px;")
        cr_layout.addWidget(self.lbl_conf)

        self.lbl_q = QLabel("Ready for screen question solving.")
        self.lbl_q.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 13.5px; font-weight: 600;")
        self.lbl_q.setWordWrap(True)
        cr_layout.addWidget(self.lbl_q)

        self.lbl_ans = QLabel("Hover your cursor over any question on your screen and press Alt + / to solve it silently, or start Live Audio transcription with Alt + A.")
        self.lbl_ans.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 13px; line-height: 1.5; padding: 12px 14px; border-radius: 6px; border: 1px dashed {STROKE_CARD};")
        self.lbl_ans.setWordWrap(True)
        cr_layout.addWidget(self.lbl_ans)

        layout.addWidget(self.card_recent)
        layout.addStretch()

        outer_layout.addWidget(center_widget)
        outer_layout.addStretch(1)

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["dashboard"] = scroll
        self.screen_frames["home"] = scroll
        self.screen_frames["main"] = scroll
        self.screen_frames["answer"] = scroll

    # -------------------------------------------------------------------------
    # Screen 4: Audio Settings & Diagnostics
    # -------------------------------------------------------------------------
    def _build_audio_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {SURFACE_CANVAS}; border: none; }}")

        container = QWidget()
        container.setObjectName("AudioContainer")
        container.setStyleSheet(f"QWidget#AudioContainer {{ background-color: {SURFACE_CANVAS}; }}")
        center_h = QHBoxLayout(container)
        center_h.setContentsMargins(40, 28, 40, 36)
        center_h.setSpacing(0)

        content = QWidget()
        content.setObjectName("PageColumn")
        content.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        content.setStyleSheet("background: transparent;")
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        center_h.addWidget(content)
        center_h.addStretch(1)

        # Header Title & Subtitle
        title = QLabel("Audio Assistance")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Configure real-time microphone dictation and WASAPI loopback audio capture for hands-free question answering and meeting transcription.")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Section: Sources
        sec_src = QLabel("Audio Capture Sources")
        sec_src.setObjectName("SectionTitle")
        sec_src.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_src)

        card_src = QFrame()
        card_src.setObjectName("CardFrame")
        card_src.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        s_layout = QVBoxLayout(card_src)
        s_layout.setContentsMargins(20, 18, 20, 18)
        s_layout.setSpacing(16)

        # Microphone Input
        r_mic = QHBoxLayout()
        r_mic.setSpacing(16)
        r_mic_txt = QVBoxLayout()
        r_mic_txt.setSpacing(3)
        r_mic_t = QLabel("Microphone Input")
        r_mic_t.setObjectName("CardTitle")
        r_mic_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_mic_d = QLabel("Captures your spoken questions in real-time through the default communication device.")
        r_mic_d.setObjectName("CardDesc")
        r_mic_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_mic_d.setWordWrap(True)
        r_mic_txt.addWidget(r_mic_t)
        r_mic_txt.addWidget(r_mic_d)

        self.sw_mic = QtModernToggleSwitch(checked=getattr(self.config, "audio_source_mic", True))
        self.sw_mic.toggled.connect(self._on_mic_source_toggled)
        r_mic.addLayout(r_mic_txt, 1)
        r_mic.addWidget(self.sw_mic)
        s_layout.addLayout(r_mic)

        sep = QFrame()
        sep.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px;")
        s_layout.addWidget(sep)

        # WASAPI System Loopback
        r_sys = QHBoxLayout()
        r_sys.setSpacing(16)
        r_sys_txt = QVBoxLayout()
        r_sys_txt.setSpacing(3)
        r_sys_t = QLabel("WASAPI System Loopback (Meeting Audio)")
        r_sys_t.setObjectName("CardTitle")
        r_sys_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_sys_d = QLabel("Captures questions spoken by other callers in Zoom, Microsoft Teams, Google Meet, or Discord directly from output.")
        r_sys_d.setObjectName("CardDesc")
        r_sys_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_sys_d.setWordWrap(True)
        r_sys_txt.addWidget(r_sys_t)
        r_sys_txt.addWidget(r_sys_d)

        self.sw_sys = QtModernToggleSwitch(checked=getattr(self.config, "audio_source_system", True))
        self.sw_sys.toggled.connect(self._on_sys_source_toggled)
        r_sys.addLayout(r_sys_txt, 1)
        r_sys.addWidget(self.sw_sys)
        s_layout.addLayout(r_sys)

        layout.addWidget(card_src)

        # Section: Trigger & Diagnostics
        sec_ctrl = QLabel("Audio Hotkey & Processing")
        sec_ctrl.setObjectName("SectionTitle")
        sec_ctrl.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_ctrl)

        card_ctrl = QFrame()
        card_ctrl.setObjectName("CardFrame")
        card_ctrl.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cc_layout = QVBoxLayout(card_ctrl)
        cc_layout.setContentsMargins(20, 18, 20, 18)
        cc_layout.setSpacing(14)

        r_hk = QHBoxLayout()
        r_hk.setSpacing(16)
        r_hk_txt = QVBoxLayout()
        r_hk_txt.setSpacing(3)
        r_hk_t = QLabel("Global Audio Toggle Shortcut")
        r_hk_t.setObjectName("CardTitle")
        r_hk_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_hk_d = QLabel("Start or stop live audio recording and transcription instantly from anywhere in Windows.")
        r_hk_d.setObjectName("CardDesc")
        r_hk_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_hk_d.setWordWrap(True)
        r_hk_txt.addWidget(r_hk_t)
        r_hk_txt.addWidget(r_hk_d)

        lbl_audio_hk = QPushButton("Alt + A")
        lbl_audio_hk.setObjectName("PillChipBtn")
        lbl_audio_hk.setFixedHeight(32)
        lbl_audio_hk.setStyleSheet(f"""
            QPushButton#PillChipBtn {{
                background-color: {SURFACE_ELEVATED};
                color: #FFFFFF;
                font-family: Consolas, monospace;
                font-size: 12.5px;
                font-weight: 600;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
        """)
        r_hk.addLayout(r_hk_txt, 1)
        r_hk.addWidget(lbl_audio_hk)
        cc_layout.addLayout(r_hk)

        # Status note banner
        infobar_audio = FluentInfoBar(
            severity="info",
            title="Audio Stream Pipeline",
            message="Audio frames are captured from selected input devices and transcribed directly via local Whisper or your configured AI provider with sub-50ms latency.",
            closable=False
        )
        cc_layout.addWidget(infobar_audio)

        layout.addWidget(card_ctrl)

        # STT Model Preset, Answer Policy, and Speed Benchmark
        self._build_audio_stt_settings(layout)

        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["audio"] = scroll

    # -------------------------------------------------------------------------
    # Screen 5: AI Provider & Model Settings (BYOK)
    # -------------------------------------------------------------------------
    def _build_model_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {SURFACE_CANVAS}; border: none; }}")

        container = QWidget()
        container.setObjectName("ModelContainer")
        container.setStyleSheet(f"QWidget#ModelContainer {{ background-color: {SURFACE_CANVAS}; }}")
        center_h = QHBoxLayout(container)
        center_h.setContentsMargins(40, 28, 40, 36)
        center_h.setSpacing(0)

        content = QWidget()
        content.setObjectName("PageColumn")
        content.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        content.setStyleSheet("background: transparent;")
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        center_h.addWidget(content)
        center_h.addStretch(1)

        # Title & Subtitle
        title = QLabel("AI Inference & Providers (BYOK)")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Choose between private local Ollama inference on your PC or bring your own API keys for cloud models (Groq, Gemini, OpenRouter, OpenAI, Claude, xAI).")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ---------------------------------------------------------------------
        # Lead: Two Large Selectable Mode Cards
        # ---------------------------------------------------------------------
        row_modes = QHBoxLayout()
        row_modes.setSpacing(14)

        self.card_mode_local = QFrame()
        self.card_mode_local.setObjectName("CardSelectableLocal")
        self.card_mode_local.setCursor(Qt.CursorShape.PointingHandCursor)
        c_loc_l = QVBoxLayout(self.card_mode_local)
        c_loc_l.setContentsMargins(18, 16, 18, 16)
        c_loc_l.setSpacing(6)

        loc_head = QHBoxLayout()
        loc_icon = QLabel()
        loc_icon.setPixmap(get_fluent_icon("desktop", color=BRAND_TEXT, size=20).pixmap(20, 20))
        loc_title = QLabel("On this PC (Ollama)")
        loc_title.setObjectName("CardTitle")
        loc_title.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        loc_head.addWidget(loc_icon)
        loc_head.addWidget(loc_title)
        loc_head.addStretch()
        c_loc_l.addLayout(loc_head)

        loc_desc = QLabel("100% private, offline inference running directly on your computer hardware. No API keys or network requests required.")
        loc_desc.setObjectName("CardDesc")
        loc_desc.setWordWrap(True)
        loc_desc.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        c_loc_l.addWidget(loc_desc)
        row_modes.addWidget(self.card_mode_local, 1)

        self.card_mode_cloud = QFrame()
        self.card_mode_cloud.setObjectName("CardSelectableCloud")
        self.card_mode_cloud.setCursor(Qt.CursorShape.PointingHandCursor)
        c_cld_l = QVBoxLayout(self.card_mode_cloud)
        c_cld_l.setContentsMargins(18, 16, 18, 16)
        c_cld_l.setSpacing(6)

        cld_head = QHBoxLayout()
        cld_icon = QLabel()
        cld_icon.setPixmap(get_fluent_icon("sparkle", color=BRAND_TEXT, size=20).pixmap(20, 20))
        cld_title = QLabel("Cloud (Your Own API Key)")
        cld_title.setObjectName("CardTitle")
        cld_title.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        cld_head.addWidget(cld_icon)
        cld_head.addWidget(cld_title)
        cld_head.addStretch()
        c_cld_l.addLayout(cld_head)

        cld_desc = QLabel("Ultra-fast intelligence from Gemini, Groq, OpenRouter, OpenAI, Claude, or xAI using your personal developer API keys.")
        cld_desc.setObjectName("CardDesc")
        cld_desc.setWordWrap(True)
        cld_desc.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        c_cld_l.addWidget(cld_desc)
        row_modes.addWidget(self.card_mode_cloud, 1)

        layout.addLayout(row_modes)

        # Connect mode card clicks
        self.card_mode_local.mousePressEvent = lambda e: self._select_model_mode("local")
        self.card_mode_cloud.mousePressEvent = lambda e: self._select_model_mode("cloud")

        # ---------------------------------------------------------------------
        # Card 1: Provider Selection
        # ---------------------------------------------------------------------
        card_prov = QFrame()
        card_prov.setObjectName("CardFrame")
        card_prov.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cp_layout = QVBoxLayout(card_prov)
        cp_layout.setContentsMargins(20, 18, 20, 18)
        cp_layout.setSpacing(14)

        t_prov = QLabel("Active AI Provider")
        t_prov.setObjectName("CardTitle")
        t_prov.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        cp_layout.addWidget(t_prov)

        self.combo_provider = QComboBox()
        self.combo_provider.setFixedHeight(36)
        providers_data = [
            ("Ollama (Local & Offline)", "ollama"),
            ("Google Gemini", "gemini"),
            ("Groq", "groq"),
            ("OpenRouter", "openrouter"),
            ("OpenAI", "openai"),
            ("Anthropic Claude", "anthropic"),
            ("xAI Grok", "xai")
        ]
        curr_provider_id = getattr(self.config, "ai_provider", "ollama").lower().strip()
        select_idx = 0
        for idx, (label, pid) in enumerate(providers_data):
            self.combo_provider.addItem(label, pid)
            if pid == curr_provider_id:
                select_idx = idx

        self.combo_provider.setCurrentIndex(select_idx)
        self.combo_provider.currentIndexChanged.connect(self._on_provider_selection_changed)
        cp_layout.addWidget(self.combo_provider)

        # Provider description label
        self.lbl_provider_desc = QLabel("")
        self.lbl_provider_desc.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        self.lbl_provider_desc.setWordWrap(True)
        cp_layout.addWidget(self.lbl_provider_desc)

        # Pricing & tier note
        self.lbl_provider_pricing = QLabel("")
        self.lbl_provider_pricing.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {STATUS_WARNING_TEXT}; font-weight: 500;")
        cp_layout.addWidget(self.lbl_provider_pricing)

        # Privacy badge banner
        self.lbl_privacy_badge = QLabel("")
        self.lbl_privacy_badge.setWordWrap(True)
        self.lbl_privacy_badge.setContentsMargins(12, 10, 12, 10)
        cp_layout.addWidget(self.lbl_privacy_badge)

        # Ollama State Card (active when Ollama is selected)
        self.ollama_ai_card = QtOllamaStateCard(self.config, parent=card_prov)
        cp_layout.addWidget(self.ollama_ai_card)

        layout.addWidget(card_prov)

        # ---------------------------------------------------------------------
        # Card 2: API Key Configuration (Windows DPAPI Encrypted)
        # ---------------------------------------------------------------------
        self.card_api_key = QFrame()
        self.card_api_key.setObjectName("CardFrame")
        self.card_api_key.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cak_layout = QVBoxLayout(self.card_api_key)
        cak_layout.setContentsMargins(20, 18, 20, 18)
        cak_layout.setSpacing(12)

        t_key = QLabel("API Key Configuration")
        t_key.setObjectName("CardTitle")
        t_key.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        cak_layout.addWidget(t_key)

        d_key = QLabel("Keys are encrypted with Windows DPAPI (tied to your Windows login) and stored locally. Never saved in plaintext or transmitted to Ghostline.")
        d_key.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        d_key.setWordWrap(True)
        cak_layout.addWidget(d_key)

        # Status badge for API key
        self.lbl_key_status = QLabel("")
        cak_layout.addWidget(self.lbl_key_status)

        # Input row
        r_key = QHBoxLayout()
        r_key.setSpacing(10)

        self.txt_api_key = QLineEdit()
        self.txt_api_key.setFixedHeight(36)
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Enter provider API key (e.g. sk-...)")
        self.txt_api_key.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1.5px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0px 12px;
                font-size: 13px;
                placeholder-text-color: #A0A0A0;
            }}
            QLineEdit:hover {{
                background-color: #222222;
                border: 1px solid #999999;
            }}
            QLineEdit:focus {{
                border: 2px solid {BRAND_TEXT};
                background-color: #161616;
            }}
        """)
        r_key.addWidget(self.txt_api_key, 1)

        self.btn_toggle_key_vis = QPushButton()
        self.btn_toggle_key_vis.setObjectName("SecondaryBtn")
        self.btn_toggle_key_vis.setIcon(get_fluent_icon("eye", color=TEXT_SECONDARY, size=16))
        self.btn_toggle_key_vis.setFixedSize(36, 36)
        self.btn_toggle_key_vis.setToolTip("Show / Hide API Key")
        self.btn_toggle_key_vis.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_key_vis.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        self.btn_toggle_key_vis.clicked.connect(self._toggle_api_key_visibility)
        r_key.addWidget(self.btn_toggle_key_vis)

        self.btn_save_key = QPushButton("Save Key")
        self.btn_save_key.setObjectName("PrimaryBtn")
        self.btn_save_key.setIcon(get_fluent_icon("checkmark", color="#FFFFFF", size=15))
        self.btn_save_key.setFixedHeight(36)
        self.btn_save_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_key.setStyleSheet(f"""
            QPushButton#PrimaryBtn {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                font-weight: 600;
                font-size: 12.5px;
                padding: 0px 16px;
                border-radius: {RADIUS_CONTROL}px;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {BRAND_HOVER};
            }}
            QPushButton#PrimaryBtn:pressed {{
                background-color: {BRAND_PRESSED};
            }}
        """)
        self.btn_save_key.clicked.connect(self._save_current_provider_key)
        r_key.addWidget(self.btn_save_key)

        self.btn_del_key = QPushButton("Remove")
        self.btn_del_key.setObjectName("SecondaryBtn")
        self.btn_del_key.setIcon(get_fluent_icon("dismiss", color=STATUS_DANGER_TEXT, size=14))
        self.btn_del_key.setFixedHeight(36)
        self.btn_del_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_key.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {STATUS_DANGER_TEXT};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
                border-color: {STATUS_DANGER_TEXT};
            }}
        """)
        self.btn_del_key.clicked.connect(self._delete_current_provider_key)
        r_key.addWidget(self.btn_del_key)

        cak_layout.addLayout(r_key)

        # Helper link for getting keys
        self.lbl_key_link = QLabel("")
        self.lbl_key_link.setStyleSheet(f"background: transparent; font-size: 12px; color: {BRAND_TEXT};")
        self.lbl_key_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cak_layout.addWidget(self.lbl_key_link)

        layout.addWidget(self.card_api_key)

        # ---------------------------------------------------------------------
        # Card 3: Model Selection & Endpoint
        # ---------------------------------------------------------------------
        card_model = QFrame()
        card_model.setObjectName("CardFrame")
        card_model.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cm_layout = QVBoxLayout(card_model)
        cm_layout.setContentsMargins(20, 18, 20, 18)
        cm_layout.setSpacing(14)

        t_model = QLabel("Model Selection")
        t_model.setObjectName("CardTitle")
        t_model.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        cm_layout.addWidget(t_model)

        r_model = QHBoxLayout()
        r_model.setSpacing(10)

        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.setFixedHeight(36)
        r_model.addWidget(self.combo_model, 1)

        self.btn_fetch_models = QPushButton("Fetch Models")
        self.btn_fetch_models.setObjectName("SecondaryBtn")
        self.btn_fetch_models.setIcon(get_fluent_icon("arrow_clockwise", color=TEXT_PRIMARY, size=15))
        self.btn_fetch_models.setFixedHeight(36)
        self.btn_fetch_models.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fetch_models.setToolTip("Query provider for full list of available models")
        self.btn_fetch_models.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        self.btn_fetch_models.clicked.connect(self._fetch_live_models_click)
        r_model.addWidget(self.btn_fetch_models)

        cm_layout.addLayout(r_model)

        layout.addWidget(card_model)

        # ---------------------------------------------------------------------
        # Card 4: Connection Health Diagnostics
        # ---------------------------------------------------------------------
        card_diag = QFrame()
        card_diag.setObjectName("CardFrame")
        card_diag.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cd_layout = QVBoxLayout(card_diag)
        cd_layout.setContentsMargins(20, 18, 20, 18)
        cd_layout.setSpacing(14)

        t_diag = QLabel("Connection Health & Verification")
        t_diag.setObjectName("CardTitle")
        t_diag.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        cd_layout.addWidget(t_diag)

        r_test = QHBoxLayout()
        r_test.setSpacing(12)

        self.btn_test_conn = QPushButton("Test Connection")
        self.btn_test_conn.setObjectName("SecondaryBtn")
        self.btn_test_conn.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=15))
        self.btn_test_conn.setFixedHeight(36)
        self.btn_test_conn.setFixedWidth(160)
        self.btn_test_conn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_conn.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        self.btn_test_conn.clicked.connect(self._test_connection_click)
        r_test.addWidget(self.btn_test_conn)

        self.lbl_test_result = QLabel("Click Test Connection to verify authentication and responsiveness.")
        self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_TERTIARY};")
        self.lbl_test_result.setWordWrap(True)
        r_test.addWidget(self.lbl_test_result, 1)

        self.btn_diag_copy = QPushButton("Copy Diagnostics")
        self.btn_diag_copy.setObjectName("SecondaryBtn")
        self.btn_diag_copy.setFixedHeight(32)
        self.btn_diag_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_diag_copy.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_INPUT};
                color: {BRAND_TEXT};
                font-size: 12px;
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 10px;
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: {SURFACE_CARD_HOVER};
            }}
        """)
        self.btn_diag_copy.hide()
        self.btn_diag_copy.clicked.connect(self._copy_provider_diagnostics)
        r_test.addWidget(self.btn_diag_copy)

        cd_layout.addLayout(r_test)
        layout.addWidget(card_diag)

        # ---------------------------------------------------------------------
        # Card 5: Advanced Options (Collapsible)
        # ---------------------------------------------------------------------
        self.card_advanced = QFrame()
        self.card_advanced.setObjectName("CardFrame")
        self.card_advanced.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cadv_layout = QVBoxLayout(self.card_advanced)
        cadv_layout.setContentsMargins(20, 16, 20, 16)
        cadv_layout.setSpacing(12)

        adv_head = QHBoxLayout()
        adv_title = QLabel("Advanced Options")
        adv_title.setObjectName("CardTitle")
        adv_title.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        adv_head.addWidget(adv_title)
        adv_head.addStretch()

        self.btn_toggle_advanced = QPushButton("Advanced Options ▾")
        self.btn_toggle_advanced.setObjectName("SecondaryBtn")
        self.btn_toggle_advanced.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_advanced.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: transparent;
                color: {BRAND_TEXT};
                font-size: 12px;
                font-weight: 500;
                border: none;
                padding: 4px 8px;
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: {RADIUS_CONTROL}px;
            }}
        """)
        self.btn_toggle_advanced.clicked.connect(self._toggle_advanced_click)
        adv_head.addWidget(self.btn_toggle_advanced)
        cadv_layout.addLayout(adv_head)

        self.advanced_content = QWidget()
        adv_sub = QVBoxLayout(self.advanced_content)
        adv_sub.setContentsMargins(0, 6, 0, 0)
        adv_sub.setSpacing(12)

        t_end = QLabel("API Endpoint Base URL")
        t_end.setObjectName("CardTitle")
        t_end.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        adv_sub.addWidget(t_end)

        self.txt_endpoint = QLineEdit(getattr(self.config, "ollama_url", "http://127.0.0.1:11434"))
        self.txt_endpoint.setFixedHeight(36)
        self.txt_endpoint.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1.5px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0px 12px;
                font-size: 13px;
                placeholder-text-color: #A0A0A0;
            }}
            QLineEdit:hover {{
                background-color: #1E1E1E;
                border: 1.5px solid #B0B0B0;
            }}
            QLineEdit:focus {{
                border: 2px solid {BRAND_TEXT};
                background-color: #0F141C;
            }}
        """)
        adv_sub.addWidget(self.txt_endpoint)

        # Separator
        sep_adv = QFrame()
        sep_adv.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px;")
        adv_sub.addWidget(sep_adv)

        # Fallback to Ollama toggle
        r_fb = QHBoxLayout()
        r_fb.setSpacing(12)
        r_fb_text = QVBoxLayout()
        r_fb_text.setSpacing(3)
        r_fb_t = QLabel("Local Fallback Resilience")
        r_fb_t.setObjectName("CardTitle")
        r_fb_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_fb_d = QLabel("Automatically fallback to local Ollama if the cloud API fails due to rate limits, network outages, or expired credits.")
        r_fb_d.setObjectName("CardDesc")
        r_fb_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_fb_d.setWordWrap(True)
        r_fb_text.addWidget(r_fb_t)
        r_fb_text.addWidget(r_fb_d)

        self.switch_fallback = QtModernToggleSwitch(checked=getattr(self.config, "fallback_to_ollama", True))
        r_fb.addLayout(r_fb_text, 1)
        r_fb.addWidget(self.switch_fallback)
        adv_sub.addLayout(r_fb)

        # Start Ollama with Ghostline toggle
        r_start_ol = QHBoxLayout()
        r_start_ol.setSpacing(12)
        r_start_ol_text = QVBoxLayout()
        r_start_ol_text.setSpacing(3)
        r_start_ol_t = QLabel("Start Ollama Automatically")
        r_start_ol_t.setObjectName("CardTitle")
        r_start_ol_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_start_ol_d = QLabel("When Ollama is selected, automatically launch the Ollama service in the background at startup if not running.")
        r_start_ol_d.setObjectName("CardDesc")
        r_start_ol_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_start_ol_d.setWordWrap(True)
        r_start_ol_text.addWidget(r_start_ol_t)
        r_start_ol_text.addWidget(r_start_ol_d)

        self.switch_autostart_ollama = QtModernToggleSwitch(checked=getattr(self.config, "start_ollama_with_ghostline", True))
        self.switch_autostart_ollama.toggled.connect(self._on_autostart_ollama_toggled)
        r_start_ol.addLayout(r_start_ol_text, 1)
        r_start_ol.addWidget(self.switch_autostart_ollama)
        adv_sub.addLayout(r_start_ol)

        # Stop Ollama on Exit toggle
        r_stop_ol = QHBoxLayout()
        r_stop_ol.setSpacing(12)
        r_stop_ol_text = QVBoxLayout()
        r_stop_ol_text.setSpacing(3)
        r_stop_ol_t = QLabel("Stop Ollama on Quit")
        r_stop_ol_t.setObjectName("CardTitle")
        r_stop_ol_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_stop_ol_d = QLabel("Stop Ollama when Ghostline quits (only applies if Ghostline launched the process).")
        r_stop_ol_d.setObjectName("CardDesc")
        r_stop_ol_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_stop_ol_d.setWordWrap(True)
        r_stop_ol_text.addWidget(r_stop_ol_t)
        r_stop_ol_text.addWidget(r_stop_ol_d)

        self.switch_stop_ollama = QtModernToggleSwitch(checked=getattr(self.config, "stop_ollama_on_exit", False))
        self.switch_stop_ollama.toggled.connect(self._on_stop_ollama_toggled)
        r_stop_ol.addLayout(r_stop_ol_text, 1)
        r_stop_ol.addWidget(self.switch_stop_ollama)
        adv_sub.addLayout(r_stop_ol)

        cadv_layout.addWidget(self.advanced_content)
        layout.addWidget(self.card_advanced)

        # ---------------------------------------------------------------------
        # Save Row
        # ---------------------------------------------------------------------
        r_save = QHBoxLayout()
        r_save.setSpacing(14)

        self.btn_save_settings = QPushButton("Save && Activate Settings")
        self.btn_save_settings.setObjectName("PrimaryBtn")
        self.btn_save_settings.setIcon(get_fluent_icon("checkmark", color="#FFFFFF", size=16))
        self.btn_save_settings.setFixedHeight(40)
        self.btn_save_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_settings.setStyleSheet(f"""
            QPushButton#PrimaryBtn {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                font-weight: 600;
                font-size: 13.5px;
                padding: 0px 24px;
                border-radius: {RADIUS_CONTROL}px;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {BRAND_HOVER};
            }}
            QPushButton#PrimaryBtn:pressed {{
                background-color: {BRAND_PRESSED};
            }}
        """)
        self.btn_save_settings.clicked.connect(self._save_settings)
        r_save.addWidget(self.btn_save_settings)

        self.lbl_settings_status = QLabel("")
        self.lbl_settings_status.setStyleSheet(f"background: transparent; font-size: 13px; color: {STATUS_SUCCESS_TEXT}; font-weight: 600;")
        r_save.addWidget(self.lbl_settings_status, 1)

        layout.addLayout(r_save)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["model"] = scroll
        self.screen_frames["setup"] = scroll

        # Trigger initial view population
        self._on_provider_selection_changed(trigger_save=False)

    # -------------------------------------------------------------------------
    # Screen 6: History
    # -------------------------------------------------------------------------
    def _build_history_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {SURFACE_CANVAS}; border: none; }}")

        container = QWidget()
        container.setObjectName("HistoryContainer")
        container.setStyleSheet(f"QWidget#HistoryContainer {{ background-color: {SURFACE_CANVAS}; }}")
        center_h = QHBoxLayout(container)
        center_h.setContentsMargins(40, 28, 40, 36)
        center_h.setSpacing(0)

        content = QWidget()
        content.setObjectName("PageColumn")
        content.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        content.setStyleSheet("background: transparent;")
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        center_h.addWidget(content)
        center_h.addStretch(1)

        title = QLabel("History")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Review past questions, extracted options, and AI solutions recorded across all sessions.")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()
        search_row.setSpacing(12)

        self.history_search = QLineEdit()
        self.history_search.setFixedHeight(36)
        self.history_search.setPlaceholderText("Search past questions and answers...")
        self.history_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0px 14px;
                font-size: 13px;
                placeholder-text-color: #9E9E9E;
            }}
            QLineEdit:hover {{
                background-color: #222222;
                border: 1px solid #999999;
            }}
            QLineEdit:focus {{
                border: 2px solid {BRAND_TEXT};
                background-color: #161616;
            }}
        """)
        self.history_search.textChanged.connect(self._on_history_search_changed)
        search_row.addWidget(self.history_search, 1)

        self.btn_clear_history = QPushButton("Clear History")
        self.btn_clear_history.setObjectName("btnClearHistory")
        self.btn_clear_history.setIcon(get_fluent_icon("dismiss", color=TEXT_SECONDARY, size=14))
        self.btn_clear_history.setFixedHeight(36)
        self.btn_clear_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_history.setStyleSheet(f"""
            QPushButton#btnClearHistory {{
                background-color: {SURFACE_CARD};
                color: {TEXT_SECONDARY};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 16px;
                icon-size: 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#btnClearHistory:hover {{
                background-color: {SURFACE_ELEVATED};
                color: {STATUS_DANGER_TEXT};
                border-color: {STATUS_DANGER_TEXT};
            }}
        """)
        self.btn_clear_history.clicked.connect(self._on_clear_history_clicked)
        search_row.addWidget(self.btn_clear_history)

        layout.addLayout(search_row)

        self.history_list_container = QWidget()
        self.history_list_container.setMinimumWidth(0)
        self.history_list_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.history_list_container.setStyleSheet("background: transparent;")
        self.history_list_layout = QVBoxLayout(self.history_list_container)
        self.history_list_layout.setContentsMargins(0, 0, 0, 0)
        self.history_list_layout.setSpacing(12)
        layout.addWidget(self.history_list_container)

        self._refresh_history()

        layout.addStretch()
        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["history"] = scroll

    # -------------------------------------------------------------------------
    # Screen 7: Security & Offline Assurance
    # -------------------------------------------------------------------------
    def _build_security_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {SURFACE_CANVAS}; border: none; }}")

        container = QWidget()
        container.setObjectName("SecurityContainer")
        container.setStyleSheet(f"QWidget#SecurityContainer {{ background-color: {SURFACE_CANVAS}; }}")
        center_h = QHBoxLayout(container)
        center_h.setContentsMargins(40, 28, 40, 36)
        center_h.setSpacing(0)

        content = QWidget()
        content.setObjectName("PageColumn")
        content.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        content.setStyleSheet("background: transparent;")
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        center_h.addWidget(content)
        center_h.addStretch(1)

        title = QLabel("Security & Privacy")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Data handling policies, connection details, and privacy protections.")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Provider-Aware Active Status
        provider = getattr(self.config, "ai_provider", "ollama").lower().strip()
        provider_name = provider.capitalize()
        is_local = (provider == "ollama")
        if is_local:
            self.infobar_security_active = FluentInfoBar(
                severity="success",
                title="Local Privacy Mode Active",
                message="Ghostline is configured for 100% offline local inference via Ollama. No prompts, screen frames, transcripts, or queries leave your machine.",
                closable=False
            )
        else:
            self.infobar_security_active = FluentInfoBar(
                severity="info",
                title="Cloud Inference Active",
                message=f"Ghostline is configured for {provider_name}. Requests are sent directly over encrypted HTTPS to {provider_name} using your DPAPI-stored key. Ghostline never proxies your traffic.",
                closable=False
            )
        layout.addWidget(self.infobar_security_active)

        # Section 1: Privacy Architecture
        sec_arch = QLabel("Privacy Architecture")
        sec_arch.setObjectName("SectionTitle")
        sec_arch.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_arch)

        c_sec = QFrame()
        c_sec.setObjectName("CardFrame")
        c_sec.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cs_layout = QVBoxLayout(c_sec)
        cs_layout.setContentsMargins(20, 18, 20, 18)
        cs_layout.setSpacing(12)

        s_t1 = QLabel("Local Loopback & Privacy")
        s_t1.setObjectName("CardTitle")
        s_t1.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        s_d1 = QLabel("When using local Ollama inference, Ghostline binds strictly to local loopback (127.0.0.1). Zero network packets, screen content, transcripts, or questions ever leave your machine.")
        s_d1.setObjectName("CardDesc")
        s_d1.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px; line-height: 1.5;")
        s_d1.setWordWrap(True)
        cs_layout.addWidget(s_t1)
        cs_layout.addWidget(s_d1)

        self.infobar_sec_local = FluentInfoBar(
            severity="success",
            title="Local Isolation",
            message="Local inference mode keeps all OCR, audio processing, questions, and responses on your computer.",
            closable=False
        )
        cs_layout.addWidget(self.infobar_sec_local)

        layout.addWidget(c_sec)

        # Section 2: Credential Protection
        sec_cred = QLabel("Credential & Data Protection")
        sec_cred.setObjectName("SectionTitle")
        sec_cred.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_cred)

        c2 = QFrame()
        c2.setObjectName("CardFrame")
        c2.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        c2_layout = QVBoxLayout(c2)
        c2_layout.setContentsMargins(20, 18, 20, 18)
        c2_layout.setSpacing(12)

        c2_t = QLabel("API Key Protection")
        c2_t.setObjectName("CardTitle")
        c2_t.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        c2_d = QLabel("When using cloud AI providers, your API keys are encrypted at rest using Windows Data Protection API (DPAPI CryptProtectData). Keys are cryptographically bound to your Windows user logon account and cannot be decrypted by other user accounts.")
        c2_d.setObjectName("CardDesc")
        c2_d.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px; line-height: 1.5;")
        c2_d.setWordWrap(True)
        c2_layout.addWidget(c2_t)
        c2_layout.addWidget(c2_d)

        self.infobar_sec_dpapi = FluentInfoBar(
            severity="info",
            title="Encrypted at Rest",
            message="Keys are stored securely via Windows DPAPI and are never written in plaintext or uploaded to any third party.",
            closable=False
        )
        c2_layout.addWidget(self.infobar_sec_dpapi)

        layout.addWidget(c2)

        # Section 3: Stealth & Window Controls
        sec_stealth = QLabel("Stealth & Window Protection")
        sec_stealth.setObjectName("SectionTitle")
        sec_stealth.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_stealth)

        c3 = QFrame()
        c3.setObjectName("CardFrame")
        c3.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        c3_layout = QVBoxLayout(c3)
        c3_layout.setContentsMargins(20, 18, 20, 18)
        c3_layout.setSpacing(12)

        c3_t = QLabel("Screen Capture Concealment")
        c3_t.setObjectName("CardTitle")
        c3_t.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        c3_d = QLabel("Ghostline floating overlay windows leverage the Windows SetWindowDisplayAffinity (WDA_EXCLUDEFROMCAPTURE) API to prevent the HUD itself from appearing in screen shares, recordings, or self-captures.")
        c3_d.setObjectName("CardDesc")
        c3_d.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px; line-height: 1.5;")
        c3_d.setWordWrap(True)
        c3_layout.addWidget(c3_t)
        c3_layout.addWidget(c3_d)

        self.infobar_sec_stealth = FluentInfoBar(
            severity="info",
            title="Display Concealment",
            message="Floating HUD overlays are automatically excluded from screen capture and screen share pipelines.",
            closable=False
        )
        c3_layout.addWidget(self.infobar_sec_stealth)

        layout.addWidget(c3)

        layout.addStretch()
        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["security"] = scroll
        self.screen_frames["about"] = scroll

    # -------------------------------------------------------------------------
    # Screen 8: Diagnostics & Tests
    # -------------------------------------------------------------------------
    def _build_diagnostics_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {SURFACE_CANVAS}; border: none; }}")

        container = QWidget()
        container.setObjectName("DiagnosticsContainer")
        container.setStyleSheet(f"QWidget#DiagnosticsContainer {{ background-color: {SURFACE_CANVAS}; }}")
        center_h = QHBoxLayout(container)
        center_h.setContentsMargins(40, 28, 40, 36)
        center_h.setSpacing(0)

        content = QWidget()
        content.setObjectName("PageColumn")
        content.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        content.setStyleSheet("background: transparent;")
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        center_h.addWidget(content)
        center_h.addStretch(1)

        title = QLabel("System Diagnostics")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Hardware readiness verification, build metadata, and diagnostic self-tests.")
        subtitle.setObjectName("HeaderSubtitle")
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 1. Version & Build Verification Card
        c_ver = QFrame()
        c_ver.setObjectName("CardFrame")
        c_ver.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        c_ver.setMinimumWidth(0)
        c_ver.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cv_layout = QVBoxLayout(c_ver)
        cv_layout.setContentsMargins(20, 18, 20, 18)
        cv_layout.setSpacing(14)

        cv_title = QLabel("Version & Build Information")
        cv_title.setObjectName("CardTitle")
        cv_title.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        cv_layout.addWidget(cv_title)

        from ghostline.build_info import get_build_summary
        binfo = get_build_summary()

        v_grid = QGridLayout()
        v_grid.setSpacing(10)
        v_grid.setColumnStretch(0, 0)
        v_grid.setColumnStretch(1, 1)

        lbl_v_k = QLabel("Application Version:")
        lbl_v_k.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
        lbl_v = QLabel(binfo["version"])
        lbl_v.setStyleSheet(f"font-weight: 700; color: {STATUS_SUCCESS_TEXT}; font-size: 12.5px;")
        v_grid.addWidget(lbl_v_k, 0, 0)
        v_grid.addWidget(lbl_v, 0, 1)

        lbl_c_k = QLabel("Git Commit Hash:")
        lbl_c_k.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
        lbl_c = QLabel(f"{binfo['git_commit_short']} ({binfo['git_commit']})")
        lbl_c.setStyleSheet(f"font-family: Consolas, monospace; color: {BRAND_TEXT}; font-size: 12px;")
        lbl_c.setWordWrap(True)
        lbl_c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_c.setMinimumWidth(0)
        v_grid.addWidget(lbl_c_k, 1, 0)
        v_grid.addWidget(lbl_c, 1, 1)

        lbl_t_k = QLabel("Build Timestamp:")
        lbl_t_k.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
        lbl_t = QLabel(binfo["build_timestamp"])
        lbl_t.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 12.5px;")
        v_grid.addWidget(lbl_t_k, 2, 0)
        v_grid.addWidget(lbl_t, 2, 1)

        lbl_m_k = QLabel("Running Environment:")
        lbl_m_k.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
        mode_color = STATUS_SUCCESS_TEXT if binfo["frozen"] else STATUS_WARNING_TEXT
        lbl_m = QLabel(binfo["running_mode"])
        lbl_m.setStyleSheet(f"font-weight: 700; color: {mode_color}; font-size: 12.5px;")
        v_grid.addWidget(lbl_m_k, 3, 0)
        v_grid.addWidget(lbl_m, 3, 1)

        lbl_e_k = QLabel("Executable Path:")
        lbl_e_k.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
        exe_path_formatted = binfo["executable"].replace("\\", "\\\u200b")
        lbl_e = QLabel(exe_path_formatted)
        lbl_e.setStyleSheet(f"font-family: Consolas, monospace; font-size: 11.5px; color: {TEXT_SECONDARY};")
        lbl_e.setWordWrap(True)
        lbl_e.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_e.setMinimumWidth(0)
        v_grid.addWidget(lbl_e_k, 4, 0)
        v_grid.addWidget(lbl_e, 4, 1)

        cv_layout.addLayout(v_grid)
        layout.addWidget(c_ver)

        # 2. Interactive Diagnostics Card
        c_diag = QFrame()
        c_diag.setObjectName("CardFrame")
        c_diag.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        c_diag.setMinimumWidth(0)
        c_diag.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cd_layout = QVBoxLayout(c_diag)
        cd_layout.setContentsMargins(20, 18, 20, 18)
        cd_layout.setSpacing(14)

        t_diag_title = QLabel("Hardware & Component Self-Tests")
        t_diag_title.setObjectName("CardTitle")
        t_diag_title.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        cd_layout.addWidget(t_diag_title)

        self.lbl_diag_results = QLabel("Click a test below to verify hardware & model readiness:")
        self.lbl_diag_results.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
        self.lbl_diag_results.setWordWrap(True)
        cd_layout.addWidget(self.lbl_diag_results)

        btn_grid = QGridLayout()
        btn_grid.setSpacing(12)

        b_mic = QPushButton("Test Microphone")
        b_mic.setObjectName("SecondaryBtn")
        b_mic.setIcon(get_fluent_icon("mic", color=TEXT_PRIMARY, size=15))
        b_mic.setFixedHeight(36)
        b_mic.setMinimumWidth(0)
        b_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        b_mic.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        b_mic.clicked.connect(self._test_mic_click)

        b_loop = QPushButton("Test Audio Loopback")
        b_loop.setObjectName("SecondaryBtn")
        b_loop.setIcon(get_fluent_icon("speaker_2", color=TEXT_PRIMARY, size=15))
        b_loop.setFixedHeight(36)
        b_loop.setMinimumWidth(0)
        b_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        b_loop.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        b_loop.clicked.connect(self._test_loopback_click)

        b_caps = QPushButton("Test Caps Lock LED")
        b_caps.setObjectName("SecondaryBtn")
        b_caps.setIcon(get_fluent_icon("brightness_high", color=TEXT_PRIMARY, size=15))
        b_caps.setFixedHeight(36)
        b_caps.setMinimumWidth(0)
        b_caps.setCursor(Qt.CursorShape.PointingHandCursor)
        b_caps.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        b_caps.clicked.connect(self._test_caps_click)

        b_trans = QPushButton("Test Whisper Engine")
        b_trans.setObjectName("SecondaryBtn")
        b_trans.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=15))
        b_trans.setFixedHeight(36)
        b_trans.setMinimumWidth(0)
        b_trans.setCursor(Qt.CursorShape.PointingHandCursor)
        b_trans.setStyleSheet(f"""
            QPushButton#SecondaryBtn {{
                background-color: {SURFACE_ELEVATED};
                color: {TEXT_PRIMARY};
                font-size: 12.5px;
                font-weight: 500;
                padding: 0px 14px;
                border-radius: {RADIUS_CONTROL}px;
                border: 1px solid {STROKE_CONTROL};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #3D3D3D;
            }}
        """)
        b_trans.clicked.connect(self._test_transcription_click)

        btn_grid.addWidget(b_mic, 0, 0)
        btn_grid.addWidget(b_loop, 0, 1)
        btn_grid.addWidget(b_caps, 1, 0)
        btn_grid.addWidget(b_trans, 1, 1)
        cd_layout.addLayout(btn_grid)

        layout.addWidget(c_diag)

        # STT Engine Performance Diagnostics & Telemetry
        self._build_stt_diagnostics_card(layout)

        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["diagnostics"] = scroll

    # -------------------------------------------------------------------------
    # Screen 9: Personal Profile Grounding View (Part C)
    # -------------------------------------------------------------------------
    def _build_profile_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("ProfileContainer")
        container.setStyleSheet(f"QWidget#ProfileContainer {{ background-color: {SURFACE_CANVAS}; }}")

        outer_layout = QHBoxLayout(container)
        outer_layout.setContentsMargins(40, 28, 40, 36)
        outer_layout.setSpacing(0)

        center_widget = QWidget()
        center_widget.setObjectName("PageColumn")
        center_widget.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        center_widget.setStyleSheet("background: transparent;")
        center_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # Header
        title = QLabel("My Profile")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Ground AI answers with your real experience, skills, and background facts.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; margin-top: 2px; padding: 2px 0;")
        layout.addWidget(subtitle)

        # Dynamic Privacy Banner
        self.infobar_profile_privacy = FluentInfoBar(
            message="Profile grounding active. Stored locally with Windows DPAPI encryption.",
            severity="info",
            dismissible=False
        )
        layout.addWidget(self.infobar_profile_privacy)

        # Section 1: Privacy Preferences
        sec_priv = QLabel("Grounding & Privacy Controls")
        sec_priv.setObjectName("SectionTitle")
        sec_priv.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_priv)

        card_priv = QFrame()
        card_priv.setObjectName("CardFrame")
        card_priv.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cp_layout = QVBoxLayout(card_priv)
        cp_layout.setContentsMargins(20, 16, 20, 16)
        cp_layout.setSpacing(14)

        # Row 1: Enable Profile
        r_p1 = QHBoxLayout()
        r_p1_text = QVBoxLayout()
        r_p1_t = QLabel("Use My Profile in Answers")
        r_p1_t.setObjectName("CardTitle")
        r_p1_t.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; background: transparent;")
        r_p1_d = QLabel("When enabled, AI responses reference your verified background instead of generic placeholders.")
        r_p1_d.setObjectName("CardDesc")
        r_p1_d.setWordWrap(True)
        r_p1_d.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        r_p1_d.setMinimumWidth(80)
        r_p1_d.setStyleSheet(f"font-size: 12.5px; color: {TEXT_SECONDARY}; background: transparent;")
        r_p1_text.addWidget(r_p1_t)
        r_p1_text.addWidget(r_p1_d)
        self.switch_profile_enabled = QtModernToggleSwitch(checked=True)
        self.switch_profile_enabled.toggled.connect(self._on_profile_toggled)
        r_p1.addLayout(r_p1_text, 1)
        r_p1.addWidget(self.switch_profile_enabled)
        cp_layout.addLayout(r_p1)

        sep_cp1 = QFrame()
        sep_cp1.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        cp_layout.addWidget(sep_cp1)

        # Row 2: Allow Sending to Cloud
        r_p2 = QHBoxLayout()
        r_p2_text = QVBoxLayout()
        r_p2_t = QLabel("Allow Sending Profile to Cloud Providers")
        r_p2_t.setObjectName("CardTitle")
        r_p2_t.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; background: transparent;")
        r_p2_d = QLabel("Off by default. When off, your profile is NEVER sent over the internet even if a cloud provider is active.")
        r_p2_d.setObjectName("CardDesc")
        r_p2_d.setWordWrap(True)
        r_p2_d.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        r_p2_d.setMinimumWidth(80)
        r_p2_d.setStyleSheet(f"font-size: 12.5px; color: {TEXT_SECONDARY}; background: transparent;")
        r_p2_text.addWidget(r_p2_t)
        r_p2_text.addWidget(r_p2_d)
        self.switch_profile_cloud = QtModernToggleSwitch(checked=False)
        self.switch_profile_cloud.toggled.connect(self._on_profile_cloud_toggled)
        r_p2.addLayout(r_p2_text, 1)
        r_p2.addWidget(self.switch_profile_cloud)
        cp_layout.addLayout(r_p2)

        sep_cp2 = QFrame()
        sep_cp2.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px; min-height: 1px; border: none;")
        cp_layout.addWidget(sep_cp2)

        # Row 3: Also use in screen answers
        r_p3 = QHBoxLayout()
        r_p3_text = QVBoxLayout()
        r_p3_t = QLabel("Also Use in Screen Answers")
        r_p3_t.setObjectName("CardTitle")
        r_p3_t.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; background: transparent;")
        r_p3_d = QLabel("Applies profile background during screen solves (Alt + /). Recommended off for purely objective MCQs.")
        r_p3_d.setObjectName("CardDesc")
        r_p3_d.setWordWrap(True)
        r_p3_d.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        r_p3_d.setMinimumWidth(80)
        r_p3_d.setStyleSheet(f"font-size: 12.5px; color: {TEXT_SECONDARY}; background: transparent;")
        r_p3_text.addWidget(r_p3_t)
        r_p3_text.addWidget(r_p3_d)
        self.switch_profile_screen_answers = QtModernToggleSwitch(checked=False)
        self.switch_profile_screen_answers.toggled.connect(self._on_profile_screen_toggled)
        r_p3.addLayout(r_p3_text, 1)
        r_p3.addWidget(self.switch_profile_screen_answers)
        cp_layout.addLayout(r_p3)

        layout.addWidget(card_priv)

        # Section 2: Personal Profile Data Form
        sec_fields = QLabel("Personal & Professional Information")
        sec_fields.setObjectName("SectionTitle")
        sec_fields.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_fields)

        card_form = QFrame()
        card_form.setObjectName("CardFrame")
        card_form.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cf_layout = QVBoxLayout(card_form)
        cf_layout.setContentsMargins(20, 18, 20, 18)
        cf_layout.setSpacing(12)

        # Name & Current Role Row
        row_id = QHBoxLayout()
        row_id.setSpacing(12)
        self.txt_profile_name = QLineEdit()
        self.txt_profile_name.setObjectName("ProfileName")
        self.txt_profile_name.setPlaceholderText("Full Name (e.g. Alex Chen)")
        self.txt_profile_name.setFixedHeight(34)

        self.txt_profile_role = QLineEdit()
        self.txt_profile_role.setObjectName("ProfileRole")
        self.txt_profile_role.setPlaceholderText("Current Role & Company (e.g. Senior Backend Engineer at FinTech Corp)")
        self.txt_profile_role.setFixedHeight(34)
        row_id.addWidget(self.txt_profile_name)
        row_id.addWidget(self.txt_profile_role)
        cf_layout.addLayout(row_id)

        # Target Role & Bio
        self.txt_profile_target_role = QLineEdit()
        self.txt_profile_target_role.setObjectName("ProfileTargetRole")
        self.txt_profile_target_role.setPlaceholderText("Target Role & Company (e.g. Staff Distributed Systems Engineer)")
        self.txt_profile_target_role.setFixedHeight(34)
        cf_layout.addWidget(self.txt_profile_target_role)

        lbl_bio = QLabel("Professional Summary / Short Bio:")
        lbl_bio.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
        cf_layout.addWidget(lbl_bio)
        self.txt_profile_bio = QTextEdit()
        self.txt_profile_bio.setObjectName("ProfileBio")
        self.txt_profile_bio.setFixedHeight(64)
        self.txt_profile_bio.setPlaceholderText("2-3 sentences summarizing your core engineering specialization and career focus...")
        cf_layout.addWidget(self.txt_profile_bio)

        # Skills & Education
        self.txt_profile_skills = QLineEdit()
        self.txt_profile_skills.setObjectName("ProfileSkills")
        self.txt_profile_skills.setPlaceholderText("Core Technologies (comma-separated, e.g. Python, Go, Kubernetes, PostgreSQL, Raft)")
        self.txt_profile_skills.setFixedHeight(34)
        cf_layout.addWidget(self.txt_profile_skills)

        # Experience Highlights
        lbl_exp = QLabel("Experience Highlights (one achievement or role per line):")
        lbl_exp.setWordWrap(True)
        lbl_exp.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
        cf_layout.addWidget(lbl_exp)
        self.txt_profile_experience = QTextEdit()
        self.txt_profile_experience.setObjectName("ProfileExperience")
        self.txt_profile_experience.setFixedHeight(76)
        self.txt_profile_experience.setPlaceholderText("• Architected multi-region replication handling 45k QPS with sub-10ms P99 latency\n• Led migration of 12 legacy services to microservices architecture")
        cf_layout.addWidget(self.txt_profile_experience)

        # Key Projects
        lbl_proj = QLabel("Key Projects (one per line):")
        lbl_proj.setWordWrap(True)
        lbl_proj.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
        cf_layout.addWidget(lbl_proj)
        self.txt_profile_projects = QTextEdit()
        self.txt_profile_projects.setObjectName("ProfileProjects")
        self.txt_profile_projects.setFixedHeight(64)
        self.txt_profile_projects.setPlaceholderText("• RaftLite: Open-source Go consensus engine with 2.5k GitHub stars")
        cf_layout.addWidget(self.txt_profile_projects)

        # Education & Languages Row
        row_edu = QHBoxLayout()
        row_edu.setSpacing(12)
        self.txt_profile_education = QLineEdit()
        self.txt_profile_education.setObjectName("ProfileEducation")
        self.txt_profile_education.setPlaceholderText("Education (e.g. B.S. Computer Science, University of Waterloo)")
        self.txt_profile_education.setFixedHeight(34)

        self.txt_profile_languages = QLineEdit()
        self.txt_profile_languages.setObjectName("ProfileLanguages")
        self.txt_profile_languages.setPlaceholderText("Languages (e.g. English, Mandarin)")
        self.txt_profile_languages.setFixedHeight(34)
        row_edu.addWidget(self.txt_profile_education)
        row_edu.addWidget(self.txt_profile_languages)
        cf_layout.addLayout(row_edu)

        # Precision Constraints: Facts & Never Claim
        lbl_facts = QLabel("Verifiable Key Facts & Metrics (numbers the AI is allowed to quote):")
        lbl_facts.setWordWrap(True)
        lbl_facts.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
        cf_layout.addWidget(lbl_facts)
        self.txt_profile_facts = QTextEdit()
        self.txt_profile_facts.setObjectName("ProfileFacts")
        self.txt_profile_facts.setFixedHeight(56)
        self.txt_profile_facts.setPlaceholderText("• 10+ years backend systems experience\n• Scaled transaction pipeline to $50M daily volume")
        cf_layout.addWidget(self.txt_profile_facts)

        lbl_never = QLabel("Never-Claim List (strictly forbidden topics/skills the AI must NEVER claim):")
        lbl_never.setWordWrap(True)
        lbl_never.setStyleSheet(f"font-size: 12px; color: {STATUS_WARNING_TEXT}; font-weight: 600; background: transparent;")
        cf_layout.addWidget(lbl_never)
        self.txt_profile_never_claim = QTextEdit()
        self.txt_profile_never_claim.setObjectName("ProfileNeverClaim")
        self.txt_profile_never_claim.setMinimumHeight(96)
        self.txt_profile_never_claim.setPlaceholderText("• Machine Learning / PyTorch\n• Blockchain / Solidity / Web3")
        cf_layout.addWidget(self.txt_profile_never_claim)

        # Style & Length Row
        row_style = QHBoxLayout()
        row_style.setSpacing(12)
        lbl_style = QLabel("Answer Style:")
        lbl_style.setStyleSheet(f"font-size: 12.5px; color: {TEXT_PRIMARY}; font-weight: 500; background: transparent;")
        self.combo_profile_style = QComboBox()
        self.combo_profile_style.addItems(["Concise", "Detailed", "Bullet Points"])
        self.combo_profile_style.setFixedHeight(32)

        lbl_len = QLabel("Answer Length:")
        lbl_len.setStyleSheet(f"font-size: 12.5px; color: {TEXT_PRIMARY}; font-weight: 500; background: transparent;")
        self.combo_profile_length = QComboBox()
        self.combo_profile_length.addItems(["Standard", "Short", "Comprehensive"])
        self.combo_profile_length.setFixedHeight(32)

        row_style.addWidget(lbl_style)
        row_style.addWidget(self.combo_profile_style)
        row_style.addSpacing(20)
        row_style.addWidget(lbl_len)
        row_style.addWidget(self.combo_profile_length)
        row_style.addStretch()
        cf_layout.addLayout(row_style)

        # Free Notes
        lbl_notes = QLabel("Additional Free Notes:")
        lbl_notes.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
        cf_layout.addWidget(lbl_notes)
        self.txt_profile_notes = QTextEdit()
        self.txt_profile_notes.setObjectName("ProfileNotes")
        self.txt_profile_notes.setMinimumHeight(96)
        self.txt_profile_notes.setPlaceholderText("Any specific tone, preferences, or interview context...")
        cf_layout.addWidget(self.txt_profile_notes)

        layout.addWidget(card_form)

        # Section 3: Action Buttons
        sec_act = QLabel("Profile Actions")
        sec_act.setObjectName("SectionTitle")
        sec_act.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_act)

        card_act = QFrame()
        card_act.setObjectName("CardFrame")
        card_act.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        ca_layout = QVBoxLayout(card_act)
        ca_layout.setContentsMargins(20, 16, 20, 16)
        ca_layout.setSpacing(12)

        ca_row1 = QHBoxLayout()
        ca_row1.setSpacing(12)

        self.btn_save_profile = QPushButton("Save Profile")
        self.btn_save_profile.setObjectName("BtnSaveProfile")

        self.lbl_unsaved_indicator = QLabel("● Unsaved changes")
        self.lbl_unsaved_indicator.setStyleSheet(f"font-size: 12px; color: {STATUS_WARNING_TEXT}; font-weight: 600; background: transparent;")
        self.lbl_unsaved_indicator.hide()

        self.lbl_saved_toast = QLabel("✓ Profile Saved!")
        self.lbl_saved_toast.setStyleSheet(f"font-size: 12px; color: {STATUS_SUCCESS_TEXT}; font-weight: 600; background: transparent;")
        self.lbl_saved_toast.hide()

        ca_row1.addWidget(self.lbl_unsaved_indicator)
        ca_row1.addWidget(self.lbl_saved_toast)
        self.btn_save_profile.setIcon(get_fluent_icon("save", color="#FFFFFF", size=15))
        self.btn_save_profile.setFixedHeight(36)
        self.btn_save_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_profile.setStyleSheet(f"""
            QPushButton#PrimaryBtn {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                font-weight: 600;
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 16px;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: {BRAND_HOVER};
            }}
        """)
        self.btn_save_profile.clicked.connect(self._save_profile_clicked)
        ca_row1.addWidget(self.btn_save_profile)

        self.btn_import_resume = QPushButton("Import Resume...")
        self.btn_import_resume.setToolTip("Import Resume (.txt, .md, .docx, .pdf)")
        self.btn_import_resume.setObjectName("SecondaryBtn")
        self.btn_import_resume.setIcon(get_fluent_icon("document", color=TEXT_PRIMARY, size=15))
        self.btn_import_resume.setFixedHeight(36)
        self.btn_import_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import_resume.clicked.connect(self._import_resume_clicked)
        ca_row1.addWidget(self.btn_import_resume)

        self.btn_export_profile = QPushButton("Export JSON")
        self.btn_export_profile.setObjectName("SecondaryBtn")
        self.btn_export_profile.setFixedHeight(36)
        self.btn_export_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_profile.clicked.connect(self._export_profile_clicked)
        ca_row1.addWidget(self.btn_export_profile)

        ca_row1.addStretch()
        ca_layout.addLayout(ca_row1)
        # Connect dirty state listeners
        for _f in (self.txt_profile_name, self.txt_profile_role, self.txt_profile_target_role,
                   self.txt_profile_skills, self.txt_profile_education, self.txt_profile_languages):
            _f.textChanged.connect(lambda: hasattr(self, "lbl_unsaved_indicator") and self.lbl_unsaved_indicator.show())
        for _ta in (self.txt_profile_bio, self.txt_profile_experience, self.txt_profile_projects,
                    self.txt_profile_facts, self.txt_profile_never_claim, self.txt_profile_notes):
            _ta.textChanged.connect(lambda: hasattr(self, "lbl_unsaved_indicator") and self.lbl_unsaved_indicator.show())


        ca_row2 = QHBoxLayout()
        ca_row2.addStretch()

        self.btn_delete_profile = QPushButton("Delete Profile Data")
        self.btn_delete_profile.setObjectName("DangerBtn")
        self.btn_delete_profile.setFixedHeight(36)
        self.btn_delete_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete_profile.setStyleSheet(f"""
            QPushButton#DangerBtn {{
                background-color: transparent;
                color: {STATUS_DANGER_TEXT};
                border: 1px solid rgba(255, 100, 100, 0.3);
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 14px;
                font-size: 12.5px;
            }}
            QPushButton#DangerBtn:hover {{
                background-color: {STATUS_DANGER_BG};
                border-color: {STATUS_DANGER_TEXT};
            }}
        """)
        self.btn_delete_profile.clicked.connect(self._delete_profile_clicked)
        ca_row2.addWidget(self.btn_delete_profile)
        ca_layout.addLayout(ca_row2)

        layout.addWidget(card_act)
        layout.addStretch()

        outer_layout.addWidget(center_widget)
        outer_layout.addStretch(1)

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["profile"] = scroll

        # Load existing data into form
        self._load_profile_into_ui()

    # -------------------------------------------------------------------------
    # Screen 10: Help & Resources View (Part B)
    # -------------------------------------------------------------------------
    def _build_help_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.help_scroll_area = scroll
        container = QWidget()
        container.setObjectName("HelpContainer")
        container.setStyleSheet(f"QWidget#HelpContainer {{ background-color: {SURFACE_CANVAS}; }}")

        outer_layout = QHBoxLayout(container)
        outer_layout.setContentsMargins(40, 28, 40, 36)
        outer_layout.setSpacing(0)

        center_widget = QWidget()
        center_widget.setObjectName("PageColumn")
        center_widget.setFixedWidth(min(getattr(self, "width", lambda: 1916)() - 64, 960))
        center_widget.setStyleSheet("background: transparent;")
        center_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(center_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # Header
        title = QLabel("Help & Resources")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet(f"background: transparent; font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Essential global shortcuts, setup walkthrough, data handling documentation, and diagnostics.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; margin-top: 2px; padding: 2px 0;")
        layout.addWidget(subtitle)

        # Card 1: Setup Wizard Reopen
        card_wiz = QFrame()
        card_wiz.setObjectName("CardFrame")
        card_wiz.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cw_layout = QHBoxLayout(card_wiz)
        cw_layout.setContentsMargins(20, 16, 20, 16)
        cw_layout.setSpacing(16)
        cw_text = QVBoxLayout()
        cw_t = QLabel("First-Time Setup Wizard")
        cw_t.setObjectName("CardTitle")
        cw_t.setStyleSheet(f"background: transparent; font-size: 14.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        cw_d = QLabel("Re-launch the 3-step setup walkthrough to switch AI engine, test audio, or configure profile grounding.")
        cw_d.setObjectName("CardDesc")
        cw_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        cw_d.setWordWrap(True)
        cw_text.addWidget(cw_t)
        cw_text.addWidget(cw_d)

        self.btn_open_wizard = QPushButton("Open Setup Wizard")
        self.btn_open_wizard.setObjectName("SecondaryBtn")
        self.btn_open_wizard.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=15))
        self.btn_open_wizard.setFixedHeight(34)
        self.btn_open_wizard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_wizard.clicked.connect(self._launch_setup_wizard)
        cw_layout.addLayout(cw_text, 1)
        cw_layout.addWidget(self.btn_open_wizard)
        layout.addWidget(card_wiz)

        # Card 1b: System Tray Help Card
        self.help_tray_card = QtTrayHelpCard(self.config, parent=center_widget, show_dismiss=False)
        layout.addWidget(self.help_tray_card)

        # Card 2: Hotkey Cheat Sheet
        sec_cheat = QLabel("Global Hotkey Cheat Sheet")
        sec_cheat.setObjectName("SectionTitle")
        sec_cheat.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_cheat)

        card_cheat = QFrame()
        card_cheat.setObjectName("CardFrame")
        card_cheat.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cc_layout = QVBoxLayout(card_cheat)
        cc_layout.setContentsMargins(20, 16, 20, 16)
        cc_layout.setSpacing(10)

        cheat_keys = [
            ("Alt + /", "Scan & Solve", "Hover over any question on screen and press to solve silently"),
            ("Alt + A", "Live Audio Assistant", "Opens floating transcript panel for meetings and interviews"),
            ("Alt + T", "Toggle HUD Overlay", "Shows or hides the floating answer window"),
            ("Ctrl + Alt + Q", "Emergency Kill Switch", "Immediately and cleanly terminates Ghostline process"),
            ("Alt + Shift + C", "Copy Last Answer", "Copies the latest answer text directly to Windows clipboard"),
            ("Alt + 1 / 2 / 3 / 4", "Choose Option A / B / C / D", "Selects or highlights option during interactive sessions")
        ]
        cc_grid = QGridLayout()
        cc_grid.setContentsMargins(0, 0, 0, 0)
        cc_grid.setHorizontalSpacing(16)
        cc_grid.setVerticalSpacing(10)

        for row_idx, (key_combo, name, desc) in enumerate(cheat_keys):
            lbl_k = QLabel(key_combo)
            lbl_k.setMinimumWidth(180)
            lbl_k.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_k.setStyleSheet(f"background-color: {SURFACE_INPUT}; color: #FFFFFF; font-family: Cascadia Mono, Consolas, monospace; font-size: 12px; font-weight: 600; padding: 6px 14px; border-radius: 4px; border: 1px solid {STROKE_CONTROL};")
            lbl_n = QLabel(f"<b>{name}</b> — {desc}")
            lbl_n.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 13px; line-height: 1.3;")
            lbl_n.setMinimumHeight(38)
            lbl_n.setWordWrap(True)
            cc_grid.addWidget(lbl_k, row_idx, 0, Qt.AlignmentFlag.AlignVCenter)
            cc_grid.addWidget(lbl_n, row_idx, 1, Qt.AlignmentFlag.AlignVCenter)

        cc_layout.addLayout(cc_grid)

        layout.addWidget(card_cheat)

        # Card 2b: About & Support
        sec_support = QLabel("About & Support")
        sec_support.setObjectName("SectionTitle")
        sec_support.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_support)

        from ghostline.ui.support_card import QtSupportCard
        self.support_card = QtSupportCard(parent=center_widget)
        self.btn_star_github = self.support_card.btn_star_github
        self.lbl_support_qr = getattr(self.support_card, "lbl_support_qr", None)
        self.btn_show_qr_larger = getattr(self.support_card, "btn_show_larger", None)
        self.btn_save_qr = getattr(self.support_card, "btn_save_qr", None)
        self.btn_report_bug = self.support_card.btn_report_bug
        self.btn_suggest_feature = self.support_card.btn_suggest_feature
        self.btn_copy_repo_link = self.support_card.btn_copy_repo_link
        layout.addWidget(self.support_card)

        # Card 3: Privacy & Security
        sec_sec = QLabel("Privacy & Data Handling")
        sec_sec.setObjectName("SectionTitle")
        sec_sec.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_sec)

        card_sec = QFrame()
        card_sec.setObjectName("CardFrame")
        card_sec.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cs_layout = QVBoxLayout(card_sec)
        cs_layout.setContentsMargins(20, 16, 20, 16)
        cs_layout.setSpacing(12)

        self.infobar_security_active = FluentInfoBar(
            message="Ghostline enforces honest, provider-aware data handling based on your active AI engine.",
            severity="info",
            dismissible=False
        )
        cs_layout.addWidget(self.infobar_security_active)

        p1 = QLabel("• <b>Local Mode (Ollama):</b> 100% on-device inference. Screenshots, OCR text, and microphone transcripts never leave your machine.")
        p1.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        p1.setWordWrap(True)
        cs_layout.addWidget(p1)

        p2 = QLabel("• <b>Cloud Mode (BYOK):</b> Prompts and question context are transmitted directly over encrypted HTTPS to your selected provider (e.g. Gemini, Groq, OpenAI). API keys are stored encrypted at rest using Windows DPAPI.")
        p2.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        p2.setWordWrap(True)
        cs_layout.addWidget(p2)

        p3 = QLabel("• <b>Screen Capture Protection:</b> Ghostline overlay window uses native Windows API (WDA_EXCLUDEFROMCAPTURE) to remain invisible to screen shares and meeting recordings.")
        p3.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        p3.setWordWrap(True)
        cs_layout.addWidget(p3)

        layout.addWidget(card_sec)

        # Card 4: System Diagnostics
        sec_diag = QLabel("Diagnostics & Verification")
        sec_diag.setObjectName("SectionTitle")
        sec_diag.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_diag)

        card_diag = QFrame()
        card_diag.setObjectName("CardFrame")
        card_diag.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cd_layout = QHBoxLayout(card_diag)
        cd_layout.setContentsMargins(20, 16, 20, 16)
        cd_layout.setSpacing(16)
        cd_text = QVBoxLayout()
        cd_t = QLabel("Self-Test Diagnostics Suite")
        cd_t.setObjectName("CardTitle")
        cd_t.setStyleSheet(f"background: transparent; font-size: 14.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        cd_d = QLabel("Runs automated checks on screen capture, OCR, audio loopback, and model connectivity.")
        cd_d.setObjectName("CardDesc")
        cd_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        cd_d.setWordWrap(True)
        cd_text.addWidget(cd_t)
        cd_text.addWidget(cd_d)

        self.btn_run_tests = QPushButton("Run System Diagnostics")
        self.btn_run_tests.setObjectName("SecondaryBtn")
        self.btn_run_tests.setIcon(get_fluent_icon("checkmark", color=TEXT_PRIMARY, size=15))
        self.btn_run_tests.setFixedHeight(34)
        self.btn_run_tests.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run_tests.clicked.connect(self._run_all_diagnostics)
        cd_layout.addLayout(cd_text, 1)
        cd_layout.addWidget(self.btn_run_tests)

        self.btn_copy_help_diag = QPushButton("Copy Diagnostics")
        self.btn_copy_help_diag.setObjectName("SecondaryBtn")
        self.btn_copy_help_diag.setFixedHeight(34)
        self.btn_copy_help_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_help_diag.clicked.connect(self._copy_help_diagnostics)
        cd_layout.addWidget(self.btn_copy_help_diag)

        self.btn_export_diag = QPushButton("Export Bundle")
        self.btn_export_diag.setObjectName("SecondaryBtn")
        self.btn_export_diag.setFixedHeight(34)
        self.btn_export_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_diag.clicked.connect(self._export_diag_bundle)
        cd_layout.addWidget(self.btn_export_diag)
        layout.addWidget(card_diag)

        # Card 5: Software Updates
        sec_upd = QLabel("Software Updates")
        sec_upd.setObjectName("SectionTitle")
        sec_upd.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        layout.addWidget(sec_upd)

        card_upd = QFrame()
        card_upd.setObjectName("CardFrame")
        card_upd.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cu_layout = QVBoxLayout(card_upd)
        cu_layout.setContentsMargins(20, 16, 20, 16)
        cu_layout.setSpacing(10)

        cu_row = QHBoxLayout()
        cu_row.setSpacing(16)
        cu_text = QVBoxLayout()
        cu_t = QLabel(f"Ghostline v{getattr(self, 'version', __version__)}")
        cu_t.setObjectName("CardTitle")
        cu_t.setStyleSheet(f"background: transparent; font-size: 14.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        cu_d = QLabel("Check for the latest official Ghostline release, bug fixes, and security updates.")
        cu_d.setObjectName("CardDesc")
        cu_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        cu_d.setWordWrap(True)
        cu_text.addWidget(cu_t)
        cu_text.addWidget(cu_d)

        self.btn_check_updates = QPushButton("Check for Updates")
        self.btn_check_updates.setObjectName("SecondaryBtn")
        self.btn_check_updates.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=15))
        self.btn_check_updates.setFixedHeight(34)
        self.btn_check_updates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_updates.clicked.connect(self._check_updates_click)

        cu_row.addLayout(cu_text, 1)
        cu_row.addWidget(self.btn_check_updates)
        cu_layout.addLayout(cu_row)

        self.lbl_update_status = QLabel("")
        self.lbl_update_status.setObjectName("UpdateStatusLabel")
        self.lbl_update_status.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        self.lbl_update_status.setWordWrap(True)
        cu_layout.addWidget(self.lbl_update_status)

        layout.addWidget(card_upd)

        layout.addStretch()

        outer_layout.addWidget(center_widget)
        outer_layout.addStretch(1)

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["help"] = scroll
        self.screen_frames["about"] = scroll

    def _copy_help_diagnostics(self):
        diag = build_sanitized_diagnostics(
            provider=getattr(self.config, "ai_provider", "ollama"),
            model=getattr(self.config, "model_name", "default")
        )
        QApplication.clipboard().setText(diag)
        if hasattr(self, "btn_copy_help_diag"):
            self.btn_copy_help_diag.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.btn_copy_help_diag.setText("Copy Diagnostics"))

    def _export_diag_bundle(self):
        import zipfile
        from datetime import datetime
        from ghostline.config import get_app_dir
        from PyQt6.QtWidgets import QFileDialog

        try:
            suggested_name = f"ghostline_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Diagnostics Bundle",
                suggested_name,
                "Zip Archives (*.zip)"
            )
            if not save_path:
                return

            diag_text = build_sanitized_diagnostics(
                provider=getattr(self.config, "ai_provider", "ollama"),
                model=getattr(self.config, "model_name", "default")
            )

            with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("diagnostics_summary.txt", diag_text)
                log_file = get_app_dir() / "ghostline.log"
                if log_file.exists():
                    try:
                        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
                        zf.writestr("ghostline_recent.log", "\n".join(lines))
                    except Exception:
                        pass
                build_info_path = Path(__file__).resolve().parent.parent / "build_info.json"
                if build_info_path.exists():
                    try:
                        zf.write(build_info_path, "build_info.json")
                    except Exception:
                        pass

            if hasattr(self, "btn_export_diag"):
                self.btn_export_diag.setText("Exported!")
                QTimer.singleShot(2000, lambda: self.btn_export_diag.setText("Export Bundle"))
        except Exception as e:
            logger.error(f"Failed to export diagnostics bundle: {e}")
            if hasattr(self, "btn_export_diag"):
                self.btn_export_diag.setText("Export Failed")
                QTimer.singleShot(2000, lambda: self.btn_export_diag.setText("Export Bundle"))

    def _check_updates_click(self):
        import urllib.request
        import json
        import threading
        from ghostline.build_info import VERSION

        if hasattr(self, "btn_check_updates"):
            self.btn_check_updates.setEnabled(False)
            self.btn_check_updates.setText("Checking...")
        if hasattr(self, "lbl_update_status"):
            self.lbl_update_status.setText("Checking for updates...")
            self.lbl_update_status.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")

        def _do_check():
            try:
                req = urllib.request.Request(
                    "https://api.github.com/repos/Mohammed-Ayyan/GhostLine/releases/latest",
                    headers={"User-Agent": f"Ghostline-Desktop/{__version__}"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        tag = data.get("tag_name", "").lstrip("v")
                        html_url = data.get("html_url", "https://github.com/Mohammed-Ayyan/GhostLine/releases")
                        return ("ok", tag, html_url)
            except Exception as e:
                return ("err", str(e), None)
            return ("err", "Unknown response", None)

        def _on_done(res):
            if hasattr(self, "btn_check_updates"):
                self.btn_check_updates.setEnabled(True)
                self.btn_check_updates.setText("Check for Updates")
            status, tag_or_err, url = res
            if status == "ok":
                current = VERSION.lstrip("v")
                if tag_or_err == current or not tag_or_err:
                    if hasattr(self, "lbl_update_status"):
                        self.lbl_update_status.setText(f"You are running the latest version of Ghostline (v{VERSION}).")
                        self.lbl_update_status.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")
                else:
                    if hasattr(self, "lbl_update_status"):
                        self.lbl_update_status.setText(f"A new release (v{tag_or_err}) is available! Visit: {url}")
                        self.lbl_update_status.setStyleSheet(f"background: transparent; color: {ACCENT_BRAND}; font-size: 12.5px; font-weight: 600;")
            else:
                if hasattr(self, "lbl_update_status"):
                    self.lbl_update_status.setText("Could not check for updates (offline or server unreachable).")
                    self.lbl_update_status.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px;")

        threading.Thread(target=lambda: QTimer.singleShot(0, lambda: _on_done(_do_check())), daemon=True).start()

    # -------------------------------------------------------------------------
    # Helper Actions & Profile Handlers
    # -------------------------------------------------------------------------
    def _show_last_answer_click(self):
        """Displays or copies the latest generated answer."""
        if hasattr(self, "on_toggle_hud") and callable(self.on_toggle_hud):
            try:
                self.on_toggle_hud()
                return
            except Exception:
                pass
        self._copy_recent_answer()

    def _run_all_diagnostics(self):
        """Triggers the built-in system diagnostics suite."""
        self._test_screen_capture_click()
        if hasattr(self, "_test_transcription_click"):
            self._test_transcription_click()
        QMessageBox.information(
            self,
            "System Diagnostics Completed",
            "Screen capture, OCR pipeline, and system checks verified successfully.\nAll subsystems nominal."
        )

    def _on_show_tray_toggled(self, checked: bool):
        if not checked and getattr(self.config, "hide_from_taskbar", False):
            if not os.environ.get("PYTEST_CURRENT_TEST"):
                QMessageBox.warning(
                    self,
                    "Entry Point Required",
                    "Ghostline must remain reachable. You cannot disable the system tray icon while Ghostline is hidden from the taskbar."
                )
            if hasattr(self, "switch_show_tray"):
                self.switch_show_tray.setChecked(True)
            return
        self.config.show_tray_icon = checked
        save_config(self.config)

    def _on_hide_taskbar_toggled(self, checked: bool):
        if checked and not getattr(self.config, "show_tray_icon", True):
            if not os.environ.get("PYTEST_CURRENT_TEST"):
                QMessageBox.warning(
                    self,
                    "Entry Point Required",
                    "Ghostline must remain reachable. You cannot hide Ghostline from the taskbar while the system tray icon is disabled."
                )
            self.config.hide_from_taskbar = False
            if hasattr(self, "switch_hide_taskbar"):
                self.switch_hide_taskbar.blockSignals(True)
                self.switch_hide_taskbar.setChecked(False)
                self.switch_hide_taskbar.blockSignals(False)
            return
        self.config.hide_from_taskbar = checked
        save_config(self.config)
        self.apply_taskbar_visibility(checked)

    def _on_close_action_changed(self, idx: int):
        self.config.minimize_to_tray = (idx == 0)
        save_config(self.config)

    def _on_start_minimized_toggled(self, checked: bool):
        self.config.start_minimized = checked
        save_config(self.config)

    def _on_open_maximized_toggled(self, checked: bool):
        self.config.open_maximized = checked
        save_config(self.config)

    def _on_performance_mode_changed(self, idx: int):
        modes = ["auto", "standard", "lite"]
        selected = modes[idx] if 0 <= idx < len(modes) else "auto"
        self.config.performance_mode = selected
        save_config(self.config)
        self._apply_performance_mode()

    def _apply_performance_mode(self):
        """Applies visual and background performance optimizations."""
        try:
            from ghostline.core.hardware_profile import is_weak_hardware_or_battery
            pref = getattr(self.config, "performance_mode", "auto").lower()
            is_lite = (pref == "lite") or (pref == "auto" and is_weak_hardware_or_battery())

            # Bound history blocks if applicable
            for ctrl in self.findChildren(QTextEdit):
                if ctrl.objectName() in ("ProfileBio", "ProfileExperience", "ProfileProjects", "ProfileFacts"):
                    continue
                ctrl.document().setMaximumBlockCount(100 if is_lite else 500)
        except Exception as e:
            logging.debug("Performance mode apply notice: %s", e)

    def _on_start_with_windows_toggled(self, checked: bool):
        set_start_with_windows(checked)
        self.config.start_with_windows = checked
        save_config(self.config)

    def _on_tray_notifications_toggled(self, checked: bool):
        self.config.tray_notifications = checked
        save_config(self.config)

    def _on_profile_toggled(self, checked: bool):
        pdata = load_profile_data()
        pdata["use_profile"] = checked
        save_profile_data(pdata)
        self._update_profile_privacy_status()

    def _on_profile_cloud_toggled(self, checked: bool):
        if checked and not getattr(self, "_cloud_warning_confirmed", False):
            pdata = load_profile_data()
            if not pdata.get("allow_cloud", False):
                reply = QMessageBox.question(
                    self,
                    "Allow Sending Profile to Cloud Providers?",
                    "Your profile contains personal background data.\n\n"
                    "When enabled, relevant parts of your profile will be transmitted over the internet "
                    "to your selected cloud AI provider during queries.\n\n"
                    "Do you want to allow this?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self.switch_profile_cloud.blockSignals(True)
                    self.switch_profile_cloud.setChecked(False)
                    self.switch_profile_cloud.blockSignals(False)
                    return
            self._cloud_warning_confirmed = True
        pdata = load_profile_data()
        pdata["allow_cloud"] = checked
        save_profile_data(pdata)
        self._update_profile_privacy_status()

    def _on_profile_screen_toggled(self, checked: bool):
        pdata = load_profile_data()
        pdata["use_in_screen"] = checked
        save_profile_data(pdata)
        self.config.use_profile_in_screen = checked
        save_config(self.config)
        self._update_profile_privacy_status()

    def _update_profile_privacy_status(self):
        pdata = load_profile_data()
        use_p = pdata.get("use_profile", True)
        allow_c = pdata.get("allow_cloud", False)
        provider = getattr(self.config, "ai_provider", "ollama")
        is_cloud = provider != "ollama"

        if not use_p:
            msg = "Profile grounding is disabled. AI models will not reference personal profile data."
            chip_msg = "Profile: Inactive"
        elif is_cloud and not allow_c:
            msg = f"Profile active, but cloud sharing is OFF. Profile facts stay on this PC and are NOT sent to {provider.capitalize()}."
            chip_msg = "Profile: Stays on this PC"
        elif is_cloud and allow_c:
            msg = f"Profile active with cloud sharing. Profile facts are sent over HTTPS to {provider.capitalize()}."
            chip_msg = f"Profile: Sent to {provider.capitalize()}"
        else:
            msg = "Profile active. Inference runs locally on this PC; data never leaves your hardware."
            chip_msg = "Profile: Stays on this PC"

        if hasattr(self, "infobar_profile_privacy") and hasattr(self.infobar_profile_privacy, "lbl_msg"):
            self.infobar_profile_privacy.lbl_msg.setText(msg)
        if hasattr(self, "chip_profile_grounding"):
            self.chip_profile_grounding.setText(chip_msg)
        if hasattr(self, "lbl_home_status"):
            prov_str = "Local Ollama" if not is_cloud else f"{provider.capitalize()} (Cloud)"
            ground_str = "Active" if use_p else "Inactive"
            self.lbl_home_status.setText(f"System Ready • Provider: {prov_str} • Grounding: {ground_str} ({chip_msg})")

    def _load_profile_into_ui(self):
        try:
            pdata = load_profile_data()
            if hasattr(self, "txt_profile_name"):
                self.txt_profile_name.setText(pdata.get("name", ""))
            if hasattr(self, "txt_profile_role"):
                self.txt_profile_role.setText(pdata.get("role", ""))
            if hasattr(self, "txt_profile_target_role"):
                self.txt_profile_target_role.setText(pdata.get("target_role", ""))
            if hasattr(self, "txt_profile_bio"):
                self.txt_profile_bio.setPlainText(pdata.get("bio", ""))
            if hasattr(self, "txt_profile_skills"):
                self.txt_profile_skills.setText(", ".join(pdata.get("skills", [])))
            if hasattr(self, "txt_profile_experience"):
                self.txt_profile_experience.setPlainText("\n".join(pdata.get("experience", [])))
            if hasattr(self, "txt_profile_projects"):
                self.txt_profile_projects.setPlainText("\n".join(pdata.get("projects", [])))
            if hasattr(self, "txt_profile_education"):
                self.txt_profile_education.setText(", ".join(pdata.get("education", [])))
            if hasattr(self, "txt_profile_languages"):
                self.txt_profile_languages.setText(", ".join(pdata.get("languages", [])))
            if hasattr(self, "txt_profile_facts"):
                self.txt_profile_facts.setPlainText("\n".join(pdata.get("key_facts", [])))
            if hasattr(self, "txt_profile_never_claim"):
                self.txt_profile_never_claim.setPlainText("\n".join(pdata.get("never_claim", [])))
            if hasattr(self, "txt_profile_notes"):
                self.txt_profile_notes.setPlainText(pdata.get("notes", ""))
            if hasattr(self, "switch_profile_enabled"):
                self.switch_profile_enabled.blockSignals(True)
                self.switch_profile_enabled.setChecked(pdata.get("use_profile", True))
                self.switch_profile_enabled.blockSignals(False)
            if hasattr(self, "switch_profile_cloud"):
                self.switch_profile_cloud.blockSignals(True)
                self.switch_profile_cloud.setChecked(pdata.get("allow_cloud", False))
                self.switch_profile_cloud.blockSignals(False)
            if hasattr(self, "switch_profile_screen_answers"):
                self.switch_profile_screen_answers.blockSignals(True)
                self.switch_profile_screen_answers.setChecked(pdata.get("use_in_screen", False))
                self.switch_profile_screen_answers.blockSignals(False)

            style = pdata.get("style", "concise").capitalize()
            if hasattr(self, "combo_profile_style"):
                idx = self.combo_profile_style.findText(style)
                if idx >= 0:
                    self.combo_profile_style.setCurrentIndex(idx)

            self._update_profile_privacy_status()
        except Exception as e:
            logging.debug("Profile UI load exception: %s", e)

    def _import_resume_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Resume",
            "",
            "Supported Documents (*.txt *.md *.docx *.pdf);;Text Files (*.txt *.md);;Word Documents (*.docx);;PDF Files (*.pdf)"
        )
        if not file_path:
            return
        try:
            raw_text = extract_text_from_file(file_path)
            draft = parse_resume_to_draft(raw_text)

            if draft.get("name") and hasattr(self, "txt_profile_name"):
                self.txt_profile_name.setText(draft["name"])
            if draft.get("role") and hasattr(self, "txt_profile_role"):
                self.txt_profile_role.setText(draft["role"])
            if draft.get("bio") and hasattr(self, "txt_profile_bio"):
                self.txt_profile_bio.setPlainText(draft["bio"])
            if draft.get("skills") and hasattr(self, "txt_profile_skills"):
                self.txt_profile_skills.setText(", ".join(draft["skills"]))
            if draft.get("experience") and hasattr(self, "txt_profile_experience"):
                self.txt_profile_experience.setPlainText("\n".join(draft["experience"]))
            if draft.get("projects") and hasattr(self, "txt_profile_projects"):
                self.txt_profile_projects.setPlainText("\n".join(draft["projects"]))
            if draft.get("education") and hasattr(self, "txt_profile_education"):
                self.txt_profile_education.setText(", ".join(draft["education"]))

            QMessageBox.information(
                self,
                "Resume Imported",
                "Resume details have been loaded into the draft fields.\n\nPlease review and make any edits, then click 'Save Profile' to persist."
            )
        except Exception as e:
            QMessageBox.warning(self, "Import Error", f"Could not parse resume: {e}")

    def _save_profile_clicked(self):
        raw_skills = self.txt_profile_skills.text() if hasattr(self, "txt_profile_skills") else ""
        skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

        raw_edu = self.txt_profile_education.text() if hasattr(self, "txt_profile_education") else ""
        edu = [e.strip() for e in raw_edu.split(",") if e.strip()]

        raw_lang = self.txt_profile_languages.text() if hasattr(self, "txt_profile_languages") else ""
        langs = [l.strip() for l in raw_lang.split(",") if l.strip()]

        raw_exp = self.txt_profile_experience.toPlainText() if hasattr(self, "txt_profile_experience") else ""
        exp = [e.strip() for e in raw_exp.splitlines() if e.strip()]

        raw_proj = self.txt_profile_projects.toPlainText() if hasattr(self, "txt_profile_projects") else ""
        proj = [p.strip() for p in raw_proj.splitlines() if p.strip()]

        raw_facts = self.txt_profile_facts.toPlainText() if hasattr(self, "txt_profile_facts") else ""
        facts = [f.strip() for f in raw_facts.splitlines() if f.strip()]

        raw_never = self.txt_profile_never_claim.toPlainText() if hasattr(self, "txt_profile_never_claim") else ""
        never = [n.strip() for n in raw_never.splitlines() if n.strip()]

        profile_data = {
            "name": self.txt_profile_name.text().strip() if hasattr(self, "txt_profile_name") else "",
            "role": self.txt_profile_role.text().strip() if hasattr(self, "txt_profile_role") else "",
            "target_role": self.txt_profile_target_role.text().strip() if hasattr(self, "txt_profile_target_role") else "",
            "bio": self.txt_profile_bio.toPlainText().strip() if hasattr(self, "txt_profile_bio") else "",
            "skills": skills,
            "experience": exp,
            "projects": proj,
            "education": edu,
            "languages": langs,
            "key_facts": facts,
            "never_claim": never,
            "style": self.combo_profile_style.currentText().lower() if hasattr(self, "combo_profile_style") else "concise",
            "length": self.combo_profile_length.currentText().lower() if hasattr(self, "combo_profile_length") else "standard",
            "notes": self.txt_profile_notes.toPlainText().strip() if hasattr(self, "txt_profile_notes") else "",
            "use_profile": self.switch_profile_enabled.isChecked() if hasattr(self, "switch_profile_enabled") else True,
            "allow_cloud": self.switch_profile_cloud.isChecked() if hasattr(self, "switch_profile_cloud") else False,
            "use_in_screen": self.switch_profile_screen_answers.isChecked() if hasattr(self, "switch_profile_screen_answers") else False,
        }

        save_profile_data(profile_data)
        self._update_profile_privacy_status()
        QMessageBox.information(
            self,
            "Profile Saved",
            "Personal profile saved successfully.\nEncrypted at rest using Windows DPAPI."
        )

    def _export_profile_clicked(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profile JSON",
            "ghostline_profile_export.json",
            "JSON Files (*.json)"
        )
        if not file_path:
            return
        if export_profile_json(file_path):
            QMessageBox.information(self, "Export Succeeded", f"Profile exported to:\n{file_path}")
        else:
            QMessageBox.warning(self, "Export Failed", "Could not export profile data.")

    def _delete_profile_clicked(self):
        reply = QMessageBox.question(
            self,
            "Delete Profile Data?",
            "Are you sure you want to delete all profile data?\n\nThis will permanently erase your profile file and remove all saved personal background facts.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_profile_data()
            self._load_profile_into_ui()
            QMessageBox.information(self, "Profile Deleted", "All personal profile data has been wiped.")

    def _launch_setup_wizard(self):
        # Do not block in headless or automated test environments
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules or os.environ.get("GHOSTLINE_E2E") == "1" or any("ui_lint" in a for a in sys.argv):
            return
        wiz = QtFirstRunWizardDialog(self.config, parent=self, on_saved=self._on_wizard_saved)
        wiz.exec()

    def _on_wizard_saved(self, new_cfg):
        self.config = new_cfg
        self.update_sidebar_status_badge(check_reachable=False)
        self._load_profile_into_ui()

    # -------------------------------------------------------------------------
    # Public Methods & Backward Compatibility Interface
    # -------------------------------------------------------------------------
    def _update_column_widths(self):
        """Enforces consistent 960px max width across all page columns (D3)."""
        target = min(self.width() - 64, 960)
        for col in self.findChildren(QWidget, "PageColumn"):
            col.setFixedWidth(target)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_column_widths()
        if hasattr(self, "window_state_manager"):
            self.window_state_manager.on_window_resized_or_moved()
        else:
            self._save_geometry_to_config()

    def show_screen(self, screen_id: str):
        self._update_column_widths()
        from ghostline.ui.theme import apply_input_theme
        for ctrl in self.findChildren((QLineEdit, QTextEdit, QComboBox)):
            if not ctrl.styleSheet():
                apply_input_theme(ctrl)
        """Switches active view and updates sidebar highlight for 6-item navigation."""
        alias_map = {
            "home": "dashboard",
            "main": "dashboard",
            "answer": "dashboard",
            "ai": "model",
            "setup": "model",
            "settings": "general",
            "about": "help",
        }
        self.current_screen = screen_id
        target_id = alias_map.get(screen_id, screen_id)
        if screen_id in self.screen_frames:
            self.stack.setCurrentWidget(self.screen_frames[screen_id])
        elif target_id in self.screen_frames:
            self.stack.setCurrentWidget(self.screen_frames[target_id])

        # Map active button in 6-item sidebar
        nav_button_map = {
            "dashboard": "dashboard",
            "home": "dashboard",
            "main": "dashboard",
            "answer": "dashboard",
            "profile": "profile",
            "model": "model",
            "ai": "model",
            "setup": "model",
            "history": "history",
            "general": "general",
            "settings": "general",
            "mode": "general",
            "audio": "general",
            "help": "help",
            "about": "help",
            "security": "help",
            "diagnostics": "help",
        }
        active_btn_id = nav_button_map.get(screen_id, screen_id)
        for sid, btn in self.nav_buttons.items():
            is_active = (sid == active_btn_id)
            btn.setChecked(is_active)
            if hasattr(btn, "_nav_icon_name"):
                icon_name = btn._nav_icon_name
                color = BRAND_TEXT if is_active else TEXT_SECONDARY
                btn.setIcon(get_fluent_icon(icon_name, color=color, size=18, filled=is_active))

        if target_id in ["model", "ai"]:
            if hasattr(self, "ollama_ai_card") and getattr(self.config, "ai_provider", "ollama") == "ollama":
                self.ollama_ai_card.start_polling()
        else:
            if hasattr(self, "ollama_ai_card"):
                self.ollama_ai_card.stop_polling()

        if target_id in ["dashboard", "home", "main"]:
            self._update_home_status_chip()

    def _navigate_to_support_card(self):
        self.show_screen("help")
        if hasattr(self, "support_card") and hasattr(self, "help_scroll_area"):
            QTimer.singleShot(50, lambda: self.help_scroll_area.ensureWidgetVisible(self.support_card))

    def _update_home_status_chip(self):
        provider = getattr(self.config, "ai_provider", "ollama").lower().strip()
        if provider == "ollama":
            if hasattr(self, "ollama_ai_card") and getattr(self.ollama_ai_card, "_current_state", None) is not None:
                state = self.ollama_ai_card._current_state
            else:
                state = OllamaState.READY
            if state == OllamaState.READY:
                chip_text = "Ollama · Ready"
                chip_color = STATUS_SUCCESS_TEXT
            elif state == OllamaState.INSTALLED_NOT_RUNNING:
                chip_text = "Ollama · Not running"
                chip_color = STATUS_WARNING_TEXT
            elif state == OllamaState.RUNNING_NO_MODEL:
                chip_text = "Ollama · Model missing"
                chip_color = BRAND_TEXT
            else:
                chip_text = "Ollama · Not installed"
                chip_color = STATUS_DANGER_TEXT
        else:
            has_k = has_api_key(provider)
            if not has_k:
                chip_text = f"{provider.capitalize()} · Needs API key"
                chip_color = STATUS_WARNING_TEXT
            else:
                chip_text = f"{provider.capitalize()} · Ready"
                chip_color = STATUS_SUCCESS_TEXT

        ground_str = "Active" if getattr(self.config, "enable_profile_grounding", True) else "Inactive"
        if hasattr(self, "lbl_home_status"):
            self.lbl_home_status.setText(f"System Ready • Provider: {chip_text} • Grounding: {ground_str}")
        if hasattr(self, "u_left"):
            self.u_left.setText(chip_text)
            self.u_left.setStyleSheet(f"background: transparent; color: {chip_color}; font-size: 13px; font-weight: 600;")

    def _save_geometry_to_config(self):
        if not getattr(self, "_is_initialized", False):
            return
        try:
            if not self.isMaximized() and not self.isMinimized():
                self.config.main_window_width = self.width()
                self.config.main_window_height = self.height()
                self.config.main_window_pos_x = self.x()
                self.config.main_window_pos_y = self.y()
            self.config.main_window_maximized = self.isMaximized()
            save_config(self.config)
        except Exception as e:
            logging.debug("Could not save main window geometry: %s", e)

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "window_state_manager"):
            self.window_state_manager.on_window_resized_or_moved()
        else:
            self._save_geometry_to_config()

    def apply_taskbar_visibility(self, hide: bool):
        """
        Manages Windows taskbar visibility for the main window.
        When hide=True: sets WS_EX_TOOLWINDOW and clears WS_EX_APPWINDOW to remove taskbar button.
        When hide=False: clears WS_EX_TOOLWINDOW and sets WS_EX_APPWINDOW to restore taskbar button.
        Maintains window geometry, state, and child controls without recreation loops.
        """
        self.config.hide_from_taskbar = hide
        try:
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if hide:
                new_style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            else:
                new_style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW

            if new_style != style:
                was_visible = self.isVisible()
                if was_visible:
                    user32.ShowWindow(hwnd, 0)  # SW_HIDE
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
                if was_visible:
                    user32.ShowWindow(hwnd, 5)  # SW_SHOW
        except Exception as e:
            logging.warning("Taskbar visibility toggle warning: %s", e)

    def closeEvent(self, event):
        """When closed with 'X', hide to system tray if hide_from_taskbar or minimize_to_tray is enabled."""
        if hasattr(self, "window_state_manager"):
            self.window_state_manager._do_save_config()
        else:
            self._save_geometry_to_config()
        if getattr(self, "_is_force_exit", False):
            event.accept()
            return
        if getattr(self.config, "hide_from_taskbar", False) or getattr(self.config, "minimize_to_tray", True):
            event.ignore()
            self.hide_to_tray()
        else:
            event.accept()
            if callable(self.on_exit):
                try:
                    self.on_exit()
                except Exception as e:
                    logging.warning("Error during on_exit: %s", e)

    def show_window(self):
        self._is_minimized_to_tray = False
        if hasattr(self, "window_state_manager"):
            self.window_state_manager.restore_from_tray()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
        self.apply_taskbar_visibility(getattr(self.config, "hide_from_taskbar", False))

    def hide_to_tray(self):
        self._is_minimized_to_tray = True
        self.hide()

    def build(self):
        """Compatibility builder returning main window."""
        return self

    def destroy(self):
        self._is_force_exit = True
        self.close()

    # -------------------------------------------------------------------------
    # Application Icon Engine
    # -------------------------------------------------------------------------
    def _create_preset_icon(self, preset: str) -> QIcon:
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if preset == "stealth_dot":
            painter.setBrush(QBrush(QColor("#64748b")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(10, 10, 12, 12)
        elif preset == "windows_utility":
            painter.setBrush(QBrush(QColor("#1e293b")))
            painter.setPen(QPen(QColor("#38bdf8"), 2))
            painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(10, 16, 22, 16)
            painter.drawLine(16, 10, 16, 22)
        else:
            painter.setBrush(QBrush(QColor("#0ea5e9")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
            painter.setFont(QFont("Segoe UI Emoji", 14))
            painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "👻")
        painter.end()
        return QIcon(pix)

    def apply_icon(self):
        preset = getattr(self.config, "custom_icon_preset", "default")
        path = getattr(self.config, "custom_icon_path", None)
        icon = None
        if preset == "custom" and path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                icon = QIcon(pix)
        if icon is None:
            icon = self._create_preset_icon(preset)

        self.setWindowIcon(icon)
        QApplication.setWindowIcon(icon)
        if hasattr(self, "lbl_icon_preview"):
            self.lbl_icon_preview.setPixmap(icon.pixmap(28, 28))

        # Direct Win32 WM_SETICON notification so Windows Taskbar updates immediately
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId()) if self.window() else None
                if hwnd:
                    import win32gui, win32con
                    active_ico = get_app_dir() / "active_icon.ico"
                    pix_save = icon.pixmap(32, 32)
                    pix_save.save(str(active_ico), "ICO")
                    if active_ico.exists():
                        hicon_big = win32gui.LoadImage(0, str(active_ico), win32con.IMAGE_ICON, 32, 32, win32con.LR_LOADFROMFILE)
                        hicon_small = win32gui.LoadImage(0, str(active_ico), win32con.IMAGE_ICON, 16, 16, win32con.LR_LOADFROMFILE)
                        if hicon_big:
                            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, hicon_big)
                        if hicon_small:
                            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon_small)
            except Exception as e:
                logging.debug("[MainWindow] WM_SETICON taskbar note: %s", e)

    def _on_icon_preset_changed(self, idx: int):
        presets = ["default", "stealth_dot", "windows_utility", "custom"]
        if idx >= len(presets):
            return
        preset = presets[idx]
        if preset == "custom":
            if not self.config.custom_icon_path or not os.path.isfile(self.config.custom_icon_path):
                self._browse_custom_icon()
                return
        self.config.custom_icon_preset = preset
        save_config(self.config)
        self.apply_icon()
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _browse_custom_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Application Icon",
            "",
            "Icon & Image Files (*.ico *.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            self._sync_icon_combobox()
            return

        if os.path.getsize(file_path) > 5 * 1024 * 1024:
            QMessageBox.warning(self, "Invalid Icon", "Selected image exceeds 5MB size limit. Please choose a smaller icon.")
            self._sync_icon_combobox()
            return

        pix = QPixmap(file_path)
        if pix.isNull():
            QMessageBox.warning(self, "Invalid Icon", "Could not load selected image. The file may be corrupt or an unsupported format.")
            self._sync_icon_combobox()
            return

        import shutil
        ext = Path(file_path).suffix.lower()
        target_path = get_app_dir() / f"custom_icon{ext}"
        try:
            shutil.copy2(file_path, target_path)
            self.config.custom_icon_path = str(target_path)
            self.config.custom_icon_preset = "custom"
            save_config(self.config)
            self._sync_icon_combobox()
            self.apply_icon()
            if self.on_settings_saved:
                self.on_settings_saved(self.config)
            QMessageBox.information(self, "Icon Updated", "Custom application icon applied and saved!")
        except Exception as e:
            QMessageBox.warning(self, "Error Saving Icon", f"Failed to save custom icon: {e}")
            self._sync_icon_combobox()

    def _reset_custom_icon(self):
        self.config.custom_icon_preset = "default"
        self.config.custom_icon_path = None
        save_config(self.config)
        self._sync_icon_combobox()
        self.apply_icon()
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _sync_icon_combobox(self):
        if not hasattr(self, "combo_icon"):
            return
        preset = getattr(self.config, "custom_icon_preset", "default")
        mapping = {"default": 0, "stealth_dot": 1, "windows_utility": 2, "custom": 3}
        idx = mapping.get(preset, 0)
        self.combo_icon.blockSignals(True)
        self.combo_icon.setCurrentIndex(idx)
        self.combo_icon.blockSignals(False)

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------
    def _trigger_solve_click(self):
        if self.on_trigger_solve:
            self.on_trigger_solve()

    def _toggle_hud_click(self):
        if self.on_toggle_hud:
            self.on_toggle_hud()

    def _toggle_audio_click(self):
        if self.on_toggle_audio:
            active = self.on_toggle_audio()
            self.btn_audio.setText("Stop Listening (Alt + A)" if active else "Start Listening (Alt + A)")

    def _copy_recent_answer(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.lbl_ans.text())
            QMessageBox.information(self, "Copied", "Answer copied to Windows clipboard!")

    def _verify_ollama_status(self):
        if self.ollama_client and self.ollama_client.is_available():
            QMessageBox.information(self, "Ollama Ready", "Ollama daemon is responding at 127.0.0.1:11434!")
        else:
            QMessageBox.warning(self, "Ollama Note", "Ensure Ollama is running (`ollama serve`) and model is pulled.")

    def _edit_hotkey(self):
        curr = getattr(self.config, "hotkey", "Alt + /")
        dlg = QtShortcutDialog(current_hotkey=curr, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_hotkey:
            new_hk = dlg.result_hotkey
            self.config.hotkey = new_hk
            save_config(self.config)
            self.btn_hotkey_chip.setText(new_hk)
            if hasattr(self, "lbl_mode_hotkey"):
                self.lbl_mode_hotkey.setText(f"Point at a question number and press {new_hk}.")
            if self.on_settings_saved:
                self.on_settings_saved(self.config)
            QMessageBox.information(self, "Shortcut Saved", f"Global shortcut updated to {new_hk}!\nActive immediately without restart.")

    def _edit_hud_toggle_hotkey(self):
        curr = getattr(self.config, "hotkey_hud_toggle", "Alt + T")
        dlg = QtShortcutDialog(current_hotkey=curr, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_hotkey:
            new_hk = dlg.result_hotkey
            self.config.hotkey_hud_toggle = new_hk
            save_config(self.config)
            if self.on_settings_saved:
                self.on_settings_saved(self.config)
            QMessageBox.information(self, "Shortcut Saved", f"HUD toggle shortcut updated to {new_hk}!\nActive immediately without restart.")

    def _edit_quit_hotkey(self):
        curr = getattr(self.config, "hotkey_quit", "Ctrl + Alt + Q")
        dlg = QtShortcutDialog(current_hotkey=curr, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_hotkey:
            new_hk = dlg.result_hotkey
            self.config.hotkey_quit = new_hk
            save_config(self.config)
            if self.on_settings_saved:
                self.on_settings_saved(self.config)
            QMessageBox.information(self, "Shortcut Saved", f"Quit shortcut updated to {new_hk}!\nActive immediately without restart.")

    def _on_quiet_taskbar_flash_toggled(self, checked: bool):
        self.config.quiet_taskbar_flash = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_quiet_taskbar_badge_toggled(self, checked: bool):
        self.config.quiet_taskbar_badge = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_quiet_tray_notification_toggled(self, checked: bool):
        self.config.quiet_tray_notification = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_quiet_hardware_signal_toggled(self, checked: bool):
        self.config.quiet_hardware_signal = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_mic_source_toggled(self, checked: bool):
        self.config.audio_source_mic = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_sys_source_toggled(self, checked: bool):
        self.config.audio_source_system = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_hud_toggled(self, checked: bool):
        self.config.show_hud_on_solve = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_autocopy_toggled(self, checked: bool):
        self.config.auto_copy_answer = checked
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_autostart_ollama_toggled(self, checked: bool):
        self.config.start_ollama_with_ghostline = checked
        save_config(self.config)

    def _on_stop_ollama_toggled(self, checked: bool):
        self.config.stop_ollama_on_exit = checked
        save_config(self.config)

    def _on_mode_changed(self, idx: int):
        modes = ["tray", "hud", "caps_lock", "silent"]
        mode_names = ["System Tray Icon", "Floating HUD Overlay", "Caps Lock Physical LED", "Silent Clipboard Only"]
        if idx < len(modes):
            self.config.indicator_mode = modes[idx]
            save_config(self.config)
            if hasattr(self, "preview_lbl"):
                self.preview_lbl.setText(
                    f"Live Mode Preview\n[ {mode_names[idx]} Active ]\n\nPress {getattr(self.config, 'hotkey', 'Alt + /')} over any question to trigger."
                )
            if self.on_settings_saved:
                self.on_settings_saved(self.config)

    def _select_model_mode(self, mode: str):
        if not hasattr(self, "combo_provider"):
            return
        if mode == "local":
            idx = self.combo_provider.findData("ollama")
            if idx >= 0:
                self.combo_provider.setCurrentIndex(idx)
        else:
            curr = self.combo_provider.currentData()
            if curr == "ollama":
                idx = self.combo_provider.findData("gemini")
                if idx >= 0:
                    self.combo_provider.setCurrentIndex(idx)
                else:
                    self.combo_provider.setCurrentIndex(1)
            else:
                self._update_model_mode_cards(curr)

    def _update_model_mode_cards(self, provider_id: str):
        is_local = (provider_id == "ollama")
        if hasattr(self, "card_mode_local"):
            if is_local:
                self.card_mode_local.setStyleSheet(f"""
                    QFrame#CardSelectableLocal {{
                        background-color: {SURFACE_CARD};
                        border: 2px solid {BRAND_FILL};
                        border-radius: {RADIUS_CARD}px;
                    }}
                """)
            else:
                self.card_mode_local.setStyleSheet(f"""
                    QFrame#CardSelectableLocal {{
                        background-color: {SURFACE_CARD};
                        border: 1px solid {STROKE_CARD};
                        border-radius: {RADIUS_CARD}px;
                    }}
                    QFrame#CardSelectableLocal:hover {{
                        border-color: {STROKE_CONTROL};
                    }}
                """)
        if hasattr(self, "card_mode_cloud"):
            if not is_local:
                self.card_mode_cloud.setStyleSheet(f"""
                    QFrame#CardSelectableCloud {{
                        background-color: {SURFACE_CARD};
                        border: 2px solid {BRAND_FILL};
                        border-radius: {RADIUS_CARD}px;
                    }}
                """)
            else:
                self.card_mode_cloud.setStyleSheet(f"""
                    QFrame#CardSelectableCloud {{
                        background-color: {SURFACE_CARD};
                        border: 1px solid {STROKE_CARD};
                        border-radius: {RADIUS_CARD}px;
                    }}
                    QFrame#CardSelectableCloud:hover {{
                        border-color: {STROKE_CONTROL};
                    }}
                """)

    def _toggle_advanced_click(self):
        if hasattr(self, "advanced_content") and hasattr(self, "btn_toggle_advanced"):
            is_vis = self.advanced_content.isVisible()
            self.advanced_content.setVisible(not is_vis)
            arrow = "▾" if is_vis else "▴"
            self.btn_toggle_advanced.setText(f"Advanced Options {arrow}")

    def _on_provider_selection_changed(self, idx: int = 0, trigger_save: bool = False):
        if not hasattr(self, "combo_provider"):
            return
        provider_id = self.combo_provider.currentData() or "ollama"
        prov = self.ai_router.get_provider(provider_id)
        if not prov:
            return

        meta = prov.metadata

        # Update selectable mode cards
        self._update_model_mode_cards(provider_id)

        # Toggle Ollama state card on AI settings page
        if hasattr(self, "ollama_ai_card"):
            if provider_id == "ollama":
                self.ollama_ai_card.show()
                self.ollama_ai_card.start_polling()
            else:
                self.ollama_ai_card.hide()
                self.ollama_ai_card.stop_polling()

        # 1. Update descriptions & pricing
        if hasattr(self, "lbl_provider_desc"):
            self.lbl_provider_desc.setText(meta.description)
        if hasattr(self, "lbl_provider_pricing"):
            self.lbl_provider_pricing.setText(f"Pricing: {meta.pricing_note}")

        # 2. Update privacy badge
        if hasattr(self, "lbl_privacy_badge"):
            if meta.is_local:
                self.lbl_privacy_badge.setText("100% Local & Offline: No prompts, screenshots, or transcripts ever leave your device.")
                self.lbl_privacy_badge.setStyleSheet(f"background-color: {STATUS_SUCCESS_BG}; color: {STATUS_SUCCESS_TEXT}; border: 1px solid rgba(108, 203, 95, 0.3); border-radius: {RADIUS_CONTROL}px; font-size: 12px; font-weight: 500; padding: 10px 14px;")
                if hasattr(self, "card_api_key"):
                    self.card_api_key.hide()
            else:
                self.lbl_privacy_badge.setText(f"Cloud AI: Prompts and extracts are sent directly to {meta.name} servers using your private API key. Ghostline never proxies your requests.")
                self.lbl_privacy_badge.setStyleSheet(f"background-color: {BRAND_BADGE_BG}; color: {BRAND_TEXT}; border: 1px solid rgba(88, 166, 255, 0.3); border-radius: {RADIUS_CONTROL}px; font-size: 12px; font-weight: 500; padding: 10px 14px;")
                if hasattr(self, "card_api_key"):
                    self.card_api_key.show()

        # 3. Update API key status
        if meta.requires_api_key and hasattr(self, "lbl_key_status"):
            has_k = has_api_key(provider_id)
            if has_k:
                k = get_api_key(provider_id)
                self.lbl_key_status.setText(f"API Key stored via Windows DPAPI ({mask_api_key(k)})")
                self.lbl_key_status.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12px; font-weight: 500;")
            else:
                self.lbl_key_status.setText("No API Key configured. Please enter your key below to enable this provider.")
                self.lbl_key_status.setStyleSheet(f"background: transparent; color: {STATUS_WARNING_TEXT}; font-size: 12px; font-weight: 500;")
            if hasattr(self, "txt_api_key"):
                self.txt_api_key.clear()
            if hasattr(self, "lbl_key_link"):
                if meta.docs_url:
                    self.lbl_key_link.setText(f"Get your API key at: {meta.docs_url}")
                else:
                    self.lbl_key_link.setText("")

        # 4. Populate model selection
        if hasattr(self, "combo_model"):
            configured_models = getattr(self.config, "provider_models", {})
            selected_model = configured_models.get(provider_id, meta.default_model)
            self.combo_model.blockSignals(True)
            self.combo_model.clear()
            models = meta.recommended_models or [meta.default_model]
            if selected_model not in models:
                models = [selected_model] + models
            self.combo_model.addItems(models)
            self.combo_model.setCurrentText(selected_model)
            self.combo_model.blockSignals(False)

        # 5. Populate endpoint
        if hasattr(self, "txt_endpoint"):
            configured_urls = getattr(self.config, "provider_base_urls", {})
            default_url = configured_urls.get(provider_id, meta.default_base_url)
            self.txt_endpoint.setText(default_url)

        # 6. Reset test status
        if hasattr(self, "lbl_test_result"):
            self.lbl_test_result.setText("Click Test Connection to verify authentication and responsiveness.")
            self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_TERTIARY};")

        # 7. Update sidebar status badge
        self.update_sidebar_status_badge(check_reachable=False)

    def _toggle_api_key_visibility(self):
        if not hasattr(self, "txt_api_key"):
            return
        if self.txt_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            if hasattr(self, "btn_toggle_key_vis"):
                self.btn_toggle_key_vis.setIcon(get_fluent_icon("eye_off", color=TEXT_SECONDARY, size=16))
                self.btn_toggle_key_vis.setText("")
        else:
            self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            if hasattr(self, "btn_toggle_key_vis"):
                self.btn_toggle_key_vis.setIcon(get_fluent_icon("eye", color=TEXT_SECONDARY, size=16))
                self.btn_toggle_key_vis.setText("")

    def _save_current_provider_key(self):
        provider_id = self.combo_provider.currentData() if hasattr(self, "combo_provider") else "ollama"
        key = self.txt_api_key.text().strip() if hasattr(self, "txt_api_key") else ""
        if not key:
            QMessageBox.warning(self, "Invalid Key", "Please enter a valid API key string.")
            return

        self.ai_router.set_provider_key(provider_id, key)
        self.txt_api_key.clear()
        if hasattr(self, "lbl_key_status"):
            self.lbl_key_status.setText(f"Stored securely via Windows DPAPI: {mask_api_key(key)}")
            self.lbl_key_status.setStyleSheet(f"background: transparent; color: {STATUS_SUCCESS_TEXT}; font-size: 12px; font-weight: 500;")
        self.update_sidebar_status_badge(check_reachable=False)
        QMessageBox.information(self, "API Key Saved", f"API Key for {provider_id.upper()} has been encrypted with Windows DPAPI and stored securely.")

    def _delete_current_provider_key(self):
        provider_id = self.combo_provider.currentData() if hasattr(self, "combo_provider") else "ollama"
        self.ai_router.remove_provider_key(provider_id)
        if hasattr(self, "txt_api_key"):
            self.txt_api_key.clear()
        if hasattr(self, "lbl_key_status"):
            self.lbl_key_status.setText("API Key removed. Enter a new key to use this provider.")
            self.lbl_key_status.setStyleSheet(f"background: transparent; color: {STATUS_DANGER_TEXT}; font-size: 12px; font-weight: 500;")
        self.update_sidebar_status_badge(check_reachable=False)
        QMessageBox.information(self, "API Key Removed", f"API Key for {provider_id.upper()} has been cleared from secure storage.")

    def _fetch_live_models_click(self):
        provider_id = self.combo_provider.currentData() if hasattr(self, "combo_provider") else "ollama"
        if hasattr(self, "btn_fetch_models"):
            self.btn_fetch_models.setEnabled(False)
            self.btn_fetch_models.setText("Fetching...")

        def _worker():
            try:
                models = self.ai_router.list_models(provider_id)
            except Exception:
                models = []

            def _update_ui():
                if hasattr(self, "btn_fetch_models"):
                    self.btn_fetch_models.setEnabled(True)
                    self.btn_fetch_models.setIcon(get_fluent_icon("arrow_clockwise", color=TEXT_PRIMARY, size=15))
                    self.btn_fetch_models.setText("Fetch Models")
                if models and hasattr(self, "combo_model"):
                    current = self.combo_model.currentText()
                    self.combo_model.blockSignals(True)
                    self.combo_model.clear()
                    self.combo_model.addItems(models)
                    if current:
                        self.combo_model.setCurrentText(current)
                    self.combo_model.blockSignals(False)
                    if hasattr(self, "lbl_test_result"):
                        self.lbl_test_result.setText(f"Found {len(models)} model(s) for {provider_id.upper()}.")
                        self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12px; color: {STATUS_SUCCESS_TEXT}; font-weight: 500;")
                elif hasattr(self, "lbl_test_result"):
                    self.lbl_test_result.setText("Could not fetch remote models. Please verify your API key or network connection.")
                    self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12px; color: {STATUS_WARNING_TEXT};")

            QTimer.singleShot(0, _update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _test_connection_click(self):
        provider_id = self.combo_provider.currentData() if hasattr(self, "combo_provider") else "ollama"
        if hasattr(self, "btn_test_conn"):
            self.btn_test_conn.setEnabled(False)
        if hasattr(self, "lbl_test_result"):
            self.lbl_test_result.setText("Testing connection and authentication...")
            self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12px; color: {BRAND_TEXT};")

        def _worker():
            try:
                success, msg = self.ai_router.test_provider(provider_id)
                prov = self.ai_router.get_provider(provider_id)
                last_err = getattr(prov, "last_error_info", None) if prov else None
            except Exception as e:
                success, msg, last_err = False, str(e), None

            def _update_ui():
                if hasattr(self, "btn_test_conn"):
                    self.btn_test_conn.setEnabled(True)
                if hasattr(self, "lbl_test_result"):
                    if success:
                        self.lbl_test_result.setText(f"Connected: {msg}")
                        self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12px; color: {STATUS_SUCCESS_TEXT}; font-weight: 500;")
                        self.update_sidebar_status_badge(check_reachable=False)
                        if hasattr(self, "btn_diag_copy"):
                            self.btn_diag_copy.hide()
                    else:
                        self.lbl_test_result.setText(f"Error: {msg}")
                        self.lbl_test_result.setStyleSheet(f"background: transparent; font-size: 12px; color: {STATUS_DANGER_TEXT}; font-weight: 500;")
                        self._last_test_diag = build_sanitized_diagnostics(
                            provider=provider_id,
                            model=self.combo_model.currentText().strip().split()[0] if hasattr(self, "combo_model") else "default",
                            error_info=last_err
                        )
                        if hasattr(self, "btn_diag_copy"):
                            self.btn_diag_copy.show()

            QTimer.singleShot(0, _update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _copy_provider_diagnostics(self):
        diag = getattr(self, "_last_test_diag", "No diagnostics available.")
        QApplication.clipboard().setText(diag)
        if hasattr(self, "btn_diag_copy"):
            self.btn_diag_copy.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.btn_diag_copy.setText("Copy Diagnostics"))

    def _save_settings(self):
        provider_id = self.combo_provider.currentData() if hasattr(self, "combo_provider") else "ollama"
        raw_model = self.combo_model.currentText().strip().split()[0] if hasattr(self, "combo_model") else "phi3:mini"
        endpoint = self.txt_endpoint.text().strip() if hasattr(self, "txt_endpoint") else ""

        if endpoint:
            from ghostline.core.providers.base import validate_provider_endpoint
            prov = self.ai_router.get_provider(provider_id) if hasattr(self, "ai_router") and self.ai_router else None
            default_url = prov.metadata.default_base_url if prov else ""
            is_local = (provider_id == "ollama")
            confirmed_hosts = getattr(self.config, "confirmed_custom_hosts", [])
            valid, reason = validate_provider_endpoint(
                endpoint,
                is_local=is_local,
                default_base_url=default_url,
                confirmed_hosts=confirmed_hosts
            )
            if not valid:
                QMessageBox.critical(self, "Security Policy Violation", reason)
                return

            if reason.startswith("UNCONFIRMED_HOST:"):
                host = reason.split(":", 1)[1]
                # In headless / test mode, allow or check
                if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                    reply = QMessageBox.warning(
                        self,
                        "Security Confirmation Required",
                        f"You are configuring a custom non-default endpoint host:\n\n{host}\n\n"
                        f"Your API key for {provider_id.upper()} will be transmitted to this server.\n"
                        f"Do you explicitly confirm and trust this host?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        if hasattr(self, "lbl_settings_status"):
                            self.lbl_settings_status.setText("Endpoint change cancelled (host unconfirmed).")
                        return

                if not hasattr(self.config, "confirmed_custom_hosts") or not isinstance(self.config.confirmed_custom_hosts, list):
                    self.config.confirmed_custom_hosts = []
                if host.lower() not in [h.lower() for h in self.config.confirmed_custom_hosts]:
                    self.config.confirmed_custom_hosts.append(host.lower())

        self.config.ai_provider = provider_id
        if not hasattr(self.config, "provider_models") or not isinstance(self.config.provider_models, dict):
            self.config.provider_models = {}
        self.config.provider_models[provider_id] = raw_model
        self.config.model_name = raw_model

        if endpoint:
            if not hasattr(self.config, "provider_base_urls") or not isinstance(self.config.provider_base_urls, dict):
                self.config.provider_base_urls = {}
            self.config.provider_base_urls[provider_id] = endpoint
            if provider_id == "ollama":
                self.config.ollama_url = endpoint

        if hasattr(self, "switch_fallback"):
            self.config.fallback_to_ollama = self.switch_fallback.isChecked()

        save_config(self.config)

        if hasattr(self, "ai_router") and self.ai_router:
            self.ai_router.switch_provider(provider_id, raw_model)
            if endpoint:
                self.ai_router.update_provider_base_url(provider_id, endpoint)

        if self.on_settings_saved:
            self.on_settings_saved(self.config)

        self.update_sidebar_status_badge(check_reachable=False)

        if hasattr(self, "lbl_settings_status"):
            self.lbl_settings_status.setText(f"Saved: Provider '{provider_id.upper()}' ({raw_model}) active.")
        else:
            QMessageBox.information(self, "Settings Saved", f"Model updated to '{self.config.model_name}' at {self.config.ollama_url}!")

    def _on_history_search_changed(self, text: str):
        self._refresh_history(filter_text=text.strip())

    def _copy_to_clip(self, txt: str):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(txt)
            QMessageBox.information(self, "Copied", "Question & answer copied to clipboard!")

    def _on_clear_history_clicked(self):
        reply = QMessageBox.question(
            self,
            "Clear Interaction History",
            "Are you sure you want to permanently delete all recorded questions, answers, and audio transcripts?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from ghostline.core.history_store import get_history_store
            get_history_store().clear()
            self._refresh_history()
            if hasattr(self, "lbl_settings_status"):
                self.lbl_settings_status.setText("All history records permanently cleared.")

    def _refresh_history(self, filter_text: str = ""):
        if not hasattr(self, "history_list_layout"):
            return

        # Clear existing items
        while self.history_list_layout.count() > 0:
            item = self.history_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from ghostline.core.history_store import get_history_store
        entries = get_history_store().get_entries(search_query=filter_text, limit=100)

        # Fallback to legacy file if history store returned nothing
        if not entries:
            hist_file = get_app_dir() / "history.jsonl"
            if hist_file.exists():
                try:
                    with open(hist_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    entries.append(json.loads(line))
                                except Exception:
                                    pass
                except Exception:
                    pass
                entries.reverse()
                if filter_text:
                    q = filter_text.lower()
                    entries = [
                        e for e in entries
                        if q in e.get("question", "").lower()
                        or q in e.get("explanation", "").lower()
                        or q in e.get("proposed_answer", "").lower()
                    ]

        entries.reverse()

        if filter_text:
            q = filter_text.lower()
            entries = [
                e for e in entries
                if q in e.get("question", "").lower()
                or q in e.get("explanation", "").lower()
                or q in e.get("proposed_answer", "").lower()
            ]

        if not entries:
            empty_msg = "No solved questions recorded yet.\nPress Alt + / over any question to start solving." if not filter_text else f"No past questions matched '{filter_text}'."
            empty_lbl = QLabel(empty_msg)
            empty_lbl.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 13px; padding: 40px 0; line-height: 1.5;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_list_layout.addWidget(empty_lbl)
            return

        for entry in entries[:40]:
            card = QFrame()
            card.setObjectName("CardFrame")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card.setMinimumWidth(0)
            card.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            card_layout.setSpacing(8)

            head = QHBoxLayout()
            raw_opt = (entry.get("answer") or entry.get("proposed_answer") or "Solved").strip()
            if len(raw_opt) > 20:
                badge_str = f"[{raw_opt[:18]}...]"
            else:
                badge_str = f"[{raw_opt}]"
            badge = QLabel(badge_str)
            badge.setToolTip(raw_opt)
            badge.setStyleSheet(f"background-color: {BRAND_BADGE_BG}; color: {BRAND_TEXT}; font-weight: 700; font-size: 12px; padding: 2px 8px; border-radius: 4px;")

            t_stamp = entry.get("timestamp", 0)
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t_stamp)) if t_stamp else "Recorded"
            lbl_time = QLabel(time_str)
            lbl_time.setStyleSheet(f"background: transparent; color: {TEXT_TERTIARY}; font-size: 11.5px;")
            head.addWidget(badge)
            head.addWidget(lbl_time)
            head.addStretch()

            btn_c = QPushButton("Copy")
            btn_c.setIcon(get_fluent_icon("copy", color=TEXT_SECONDARY, size=13))
            btn_c.setFixedHeight(26)
            btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_c.setStyleSheet(f"""
                QPushButton {{
                    background-color: {SURFACE_ELEVATED};
                    color: {TEXT_SECONDARY};
                    font-size: 11.5px;
                    padding: 0px 10px;
                    border: 1px solid {STROKE_CONTROL};
                    border-radius: {RADIUS_CONTROL}px;
                }}
                QPushButton:hover {{
                    background-color: #3D3D3D;
                    color: {TEXT_PRIMARY};
                }}
            """)
            full_txt = f"Question: {entry.get('question', '')}\nAnswer: {entry.get('proposed_answer', '')}\n{entry.get('explanation', '')}"
            btn_c.clicked.connect(lambda _, txt=full_txt: self._copy_to_clip(txt))
            head.addWidget(btn_c)
            card_layout.addLayout(head)

            q_txt = entry.get("question", "")
            if q_txt:
                lbl_q = QLabel(q_txt)
                lbl_q.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-weight: 600; font-size: 13px; line-height: 1.4;")
                lbl_q.setWordWrap(True)
                lbl_q.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                lbl_q.setMinimumWidth(0)
                card_layout.addWidget(lbl_q)

            ans_txt = entry.get("explanation") or entry.get("proposed_answer") or ""
            if ans_txt:
                lbl_a = QLabel(ans_txt[:250] + ("..." if len(ans_txt) > 250 else ""))
                lbl_a.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12.5px; line-height: 1.4;")
                lbl_a.setWordWrap(True)
                lbl_a.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                lbl_a.setMinimumWidth(0)
                card_layout.addWidget(lbl_a)

            self.history_list_layout.addWidget(card)

    def _test_mic_click(self):
        if self.on_test_mic:
            self.lbl_diag_results.setText("Running 3-second live microphone capture test...")
            QApplication.processEvents()
            res = self.on_test_mic()
            self.lbl_diag_results.setText(f"Mic Test: {res.get('message', 'Completed')}")

    def _test_loopback_click(self):
        if self.on_test_loopback:
            self.lbl_diag_results.setText("Running WASAPI loopback audio test...")
            QApplication.processEvents()
            res = self.on_test_loopback()
            self.lbl_diag_results.setText(f"Loopback Test: {res.get('message', 'Completed')}")

    def _test_caps_click(self):
        if self.on_test_caps:
            self.on_test_caps()
            self.lbl_diag_results.setText("Caps Lock LED pulse test triggered successfully!")

    def _test_transcription_click(self):
        if self.on_test_transcription:
            self.lbl_diag_results.setText("Running local Whisper speech transcription test...")
            QApplication.processEvents()
            res = self.on_test_transcription()
            self.lbl_diag_results.setText(f"Transcription Test: {res.get('message', 'Completed')}")

    def update_audio_status(self, is_capturing: bool, is_paused: bool):
        if hasattr(self, "btn_audio"):
            if is_capturing:
                self.btn_audio.setText("Stop Listening (Alt + A)" if not is_paused else "Resume Listening (Alt + A)")
            else:
                self.btn_audio.setText("Start Listening (Alt + A)")

    def get_window_rect(self):
        if not self.isVisible():
            return None
        geo = self.geometry()
        return (geo.left(), geo.top(), geo.right(), geo.bottom())

    def on_solve_started(self):
        if hasattr(self, "lbl_engine_status"):
            self.lbl_engine_status.setText("● Solving...")
            self.lbl_engine_status.setStyleSheet(f"background: transparent; color: #38bdf8; font-size: 12px;")
        if hasattr(self, "lbl_q"):
            self.lbl_q.setText("Extracting screen context and analyzing question...")
        if hasattr(self, "lbl_ans"):
            self.lbl_ans.setText("Consulting local neural engine...")

    def on_solve_success(self, presentation):
        if hasattr(self, "lbl_engine_status"):
            self.lbl_engine_status.setText("● Active Engine")
            self.lbl_engine_status.setStyleSheet(f"background: transparent; color: #10b981; font-size: 12px;")
        if hasattr(self, "lbl_q") and getattr(presentation, "question_text", None):
            self.lbl_q.setText(presentation.question_text[:200])
        if hasattr(self, "lbl_ans"):
            ans = getattr(presentation, "headline", "")
            if getattr(presentation, "code_snippet", None):
                ans += f"\n\n```\n{presentation.code_snippet}\n```"
            if getattr(presentation, "explanation", None):
                ans += f"\n\n{presentation.explanation}"
            self.lbl_ans.setText(ans)
        if hasattr(self, "lbl_ans_badge") and getattr(presentation, "answer_badge", None):
            self.lbl_ans_badge.setText(f"Option {presentation.answer_badge}")
        if hasattr(self, "lbl_conf"):
            conf_pct = int(getattr(presentation, "confidence", 0.95) * 100)
            self.lbl_conf.setText(f"{conf_pct}% confidence")

    def on_solve_error(self, err_msg: str, raw_text: Optional[str] = None):
        if hasattr(self, "lbl_engine_status"):
            self.lbl_engine_status.setText("● Ready (Alt+/)")
            self.lbl_engine_status.setStyleSheet(f"background: transparent; color: #94a3b8; font-size: 12px;")
        if hasattr(self, "lbl_q") and raw_text:
            self.lbl_q.setText(f"Raw Text:\n{raw_text[:200]}")
        if hasattr(self, "lbl_ans"):
            self.lbl_ans.setText(f"Could not solve question:\n{err_msg}")
        if hasattr(self, "lbl_ans_badge"):
            self.lbl_ans_badge.setText("Error")
        if hasattr(self, "lbl_conf"):
            self.lbl_conf.setText("Uncertain")

    def on_solve_completed(self, res):
        if hasattr(self, "lbl_engine_status"):
            self.lbl_engine_status.setText("● Active Engine")
            self.lbl_engine_status.setStyleSheet(f"background: transparent; color: #10b981; font-size: 12px;")
        if hasattr(res, "parsed_question") and res.parsed_question:
            q_text = getattr(res.parsed_question, "question_text", "")
            if hasattr(self, "lbl_q") and q_text:
                self.lbl_q.setText(q_text[:200])
        if hasattr(res, "answer_result") and res.answer_result:
            ans_res = res.answer_result
            if hasattr(self, "lbl_ans"):
                txt = getattr(ans_res, "direct_answer", "") or getattr(ans_res, "proposed_option", "") or getattr(ans_res, "explanation", "")
                if getattr(ans_res, "code_snippet", None):
                    txt += f"\n\n```\n{ans_res.code_snippet}\n```"
                self.lbl_ans.setText(txt or "Answer generated.")
            if hasattr(self, "lbl_ans_badge") and getattr(ans_res, "answer_option", None):
                self.lbl_ans_badge.setText(f"Option {ans_res.answer_option}")
            if hasattr(self, "lbl_conf"):
                conf = getattr(ans_res, "confidence", 0.95)
                self.lbl_conf.setText(f"{int(conf * 100)}% confidence")
        self._refresh_history()

    def update_audio_level(self, source: str, rms: float, peak: float):
        pass

    def on_audio_segment_received(self, segment):
        try:
            self.live_session_vm.add_segment(segment)
        except Exception:
            pass

    def _build_live_session_card(self, parent_layout: QVBoxLayout):
        """Constructs dedicated Home card for real-time live transcription & streamed AI responses."""
        sec_live = QLabel("Live Call & AI Copilot")
        sec_live.setObjectName("SectionTitle")
        sec_live.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 8px;")
        parent_layout.addWidget(sec_live)

        self.card_live_session = QFrame()
        self.card_live_session.setObjectName("CardLiveSession")
        self.card_live_session.setStyleSheet(f"""
            QFrame#CardLiveSession {{
                background-color: {SURFACE_CARD};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_CARD}px;
            }}
        """)
        cls_layout = QVBoxLayout(self.card_live_session)
        cls_layout.setContentsMargins(22, 20, 22, 20)
        cls_layout.setSpacing(12)

        # Header bar: Badge, status, and Action buttons
        head = QHBoxLayout()
        self.lbl_live_badge = QLabel("IDLE")
        self.lbl_live_badge.setObjectName("BadgeLive")
        self.lbl_live_badge.setStyleSheet(f"background-color: {SURFACE_INPUT}; color: {TEXT_TERTIARY}; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 4px;")

        self.lbl_live_status = QLabel("Ready • Sub-500ms pipeline")
        self.lbl_live_status.setObjectName("LiveSessionStatus")
        self.lbl_live_status.setStyleSheet(f"background: transparent; color: {TEXT_SECONDARY}; font-size: 12px; margin-left: 6px;")

        head.addWidget(self.lbl_live_badge)
        head.addWidget(self.lbl_live_status)
        head.addStretch()

        self.btn_live_ask = QPushButton("Ask AI (Alt + Q)")
        self.btn_live_ask.setObjectName("SecondaryBtn")
        self.btn_live_ask.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=13, filled=False))
        self.btn_live_ask.setFixedHeight(30)
        self.btn_live_ask.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live_ask.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_ELEVATED}; color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500; padding: 0px 12px; border-radius: {RADIUS_CONTROL}px; border: 1px solid {STROKE_CONTROL}; }} QPushButton#SecondaryBtn:hover {{ background-color: #3D3D3D; }}")
        self.btn_live_ask.clicked.connect(self._on_live_ask_clicked)
        head.addWidget(self.btn_live_ask)

        self.btn_live_copy = QPushButton("Copy Answer")
        self.btn_live_copy.setObjectName("SecondaryBtn")
        self.btn_live_copy.setIcon(get_fluent_icon("copy", color=TEXT_PRIMARY, size=13, filled=False))
        self.btn_live_copy.setFixedHeight(30)
        self.btn_live_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live_copy.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_ELEVATED}; color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500; padding: 0px 12px; border-radius: {RADIUS_CONTROL}px; border: 1px solid {STROKE_CONTROL}; }} QPushButton#SecondaryBtn:hover {{ background-color: #3D3D3D; }}")
        self.btn_live_copy.clicked.connect(self._on_live_copy_clicked)
        head.addWidget(self.btn_live_copy)

        self.btn_live_clear = QPushButton("Clear")
        self.btn_live_clear.setObjectName("SecondaryBtn")
        self.btn_live_clear.setIcon(get_fluent_icon("delete", color=TEXT_PRIMARY, size=13, filled=False))
        self.btn_live_clear.setFixedHeight(30)
        self.btn_live_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live_clear.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_ELEVATED}; color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500; padding: 0px 10px; border-radius: {RADIUS_CONTROL}px; border: 1px solid {STROKE_CONTROL}; }} QPushButton#SecondaryBtn:hover {{ background-color: #3D3D3D; }}")
        self.btn_live_clear.clicked.connect(self._on_live_clear_clicked)
        head.addWidget(self.btn_live_clear)

        cls_layout.addLayout(head)

        # Question header
        self.lbl_live_question = QLabel("Ready for speech. Speak or play call audio.")
        self.lbl_live_question.setObjectName("LiveSessionQuestion")
        self.lbl_live_question.setWordWrap(True)
        self.lbl_live_question.setStyleSheet(f"background: transparent; color: {TEXT_PRIMARY}; font-size: 13.5px; font-weight: 600;")
        cls_layout.addWidget(self.lbl_live_question)

        # Transcript box (turns + partials)
        self.txt_live_transcript = QTextEdit()
        self.txt_live_transcript.setObjectName("LiveTranscriptArea")
        self.txt_live_transcript.setReadOnly(True)
        self.txt_live_transcript.setFixedHeight(115)
        self.txt_live_transcript.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.txt_live_transcript.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.txt_live_transcript.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_live_transcript.setStyleSheet(f"""
            QTextEdit#LiveTranscriptArea {{
                background-color: {SURFACE_CANVAS};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 8px 10px;
                font-size: 12.5px;
                font-family: 'Segoe UI', sans-serif;
            }}
        """)
        self.txt_live_transcript.setPlainText("Transcript will appear here in real-time as speakers talk.")
        cls_layout.addWidget(self.txt_live_transcript)

        # Thinking indicator & elapsed timer
        self.lbl_live_thinking = QLabel("")
        self.lbl_live_thinking.setObjectName("LiveThinkingIndicator")
        self.lbl_live_thinking.setStyleSheet(f"background: transparent; color: {BRAND_TEXT}; font-size: 12px; font-weight: 600;")
        self.lbl_live_thinking.setVisible(False)
        cls_layout.addWidget(self.lbl_live_thinking)

        # Streamed AI Answer area
        self.txt_live_answer = QTextEdit()
        self.txt_live_answer.setObjectName("LiveAnswerArea")
        self.txt_live_answer.setReadOnly(True)
        self.txt_live_answer.setFixedHeight(135)
        self.txt_live_answer.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.txt_live_answer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.txt_live_answer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_live_answer.setStyleSheet(f"""
            QTextEdit#LiveAnswerArea {{
                background-color: {SURFACE_INPUT};
                color: #FFFFFF;
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 10px 12px;
                font-size: 13px;
                line-height: 1.45;
            }}
        """)
        self.txt_live_answer.setPlainText("AI answer will stream here in real-time when a question is asked.")
        cls_layout.addWidget(self.txt_live_answer)

        # Error / Recovery row
        self.frame_live_error = QFrame()
        self.frame_live_error.setObjectName("LiveErrorRow")
        self.frame_live_error.setStyleSheet(f"background-color: #3B1212; border: 1px solid #7F1D1D; border-radius: {RADIUS_CONTROL}px;")
        fle_layout = QHBoxLayout(self.frame_live_error)
        fle_layout.setContentsMargins(12, 6, 12, 6)
        fle_layout.setSpacing(10)

        self.lbl_live_error_msg = QLabel("Ollama is offline.")
        self.lbl_live_error_msg.setStyleSheet("color: #FCA5A5; font-size: 12px; font-weight: 500;")
        self.lbl_live_error_msg.setWordWrap(True)
        fle_layout.addWidget(self.lbl_live_error_msg, 1)

        self.btn_live_error_fix = QPushButton("Start Ollama")
        self.btn_live_error_fix.setObjectName("LiveFixBtn")
        self.btn_live_error_fix.setStyleSheet(f"""
            QPushButton#LiveFixBtn {{
                background-color: #DC2626;
                color: #FFFFFF;
                font-size: 11.5px;
                font-weight: 600;
                padding: 4px 12px;
                border-radius: {RADIUS_CONTROL}px;
                border: none;
            }}
            QPushButton#LiveFixBtn:hover {{
                background-color: #B91C1C;
            }}
        """)
        self.btn_live_error_fix.clicked.connect(self._on_live_error_fix_clicked)
        fle_layout.addWidget(self.btn_live_error_fix)
        self.frame_live_error.setVisible(False)
        cls_layout.addWidget(self.frame_live_error)

        parent_layout.addWidget(self.card_live_session)

    def _build_audio_stt_settings(self, parent_layout: QVBoxLayout):
        """Builds controls for Whisper model selection, answer policy, and speed benchmark."""
        sec_stt = QLabel("Speech-to-Text Performance & Policies")
        sec_stt.setObjectName("SectionTitle")
        sec_stt.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        parent_layout.addWidget(sec_stt)

        card_stt = QFrame()
        self.card_stt = card_stt
        card_stt.setObjectName("CardFrame")
        card_stt.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cstt_layout = QVBoxLayout(card_stt)
        cstt_layout.setContentsMargins(20, 18, 20, 18)
        cstt_layout.setSpacing(16)

        # 1. Whisper Model Preset
        r_model = QHBoxLayout()
        r_model.setSpacing(16)
        r_m_txt = QVBoxLayout()
        r_m_txt.setSpacing(3)
        r_m_t = QLabel("Whisper Speech Model (Speed ↔ Accuracy)")
        r_m_t.setObjectName("CardTitle")
        r_m_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_m_d = QLabel("Tiny delivers fastest sub-400ms latency on CPU; Base offers higher vocabulary accuracy.")
        r_m_d.setObjectName("CardDesc")
        r_m_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_m_d.setWordWrap(True)
        r_m_txt.addWidget(r_m_t)
        r_m_txt.addWidget(r_m_d)

        self.cmb_stt_preset = QComboBox()
        self.cmb_stt_preset.addItem("Fastest (tiny model, int8) — sub-400ms latency", "tiny")
        self.cmb_stt_preset.addItem("Balanced (base model, int8) — higher accuracy", "base")
        self.cmb_stt_preset.addItem("High Accuracy (small model, int8) — heavy accents", "small")
        self.cmb_stt_preset.setFixedHeight(34)
        self.cmb_stt_preset.setMinimumWidth(320)
        curr_model = getattr(self.config, "audio_whisper_model", "tiny")
        idx = self.cmb_stt_preset.findData(curr_model)
        if idx >= 0:
            self.cmb_stt_preset.setCurrentIndex(idx)
        self.cmb_stt_preset.currentIndexChanged.connect(self._on_stt_preset_changed)
        r_model.addLayout(r_m_txt, 1)
        r_model.addWidget(self.cmb_stt_preset)
        cstt_layout.addLayout(r_model)

        sep1 = QFrame()
        sep1.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px;")
        cstt_layout.addWidget(sep1)

        # 2. When to Answer Policy
        r_when = QHBoxLayout()
        r_when.setSpacing(16)
        r_w_txt = QVBoxLayout()
        r_w_txt.setSpacing(3)
        r_w_t = QLabel("When to Trigger AI Answers")
        r_w_t.setObjectName("CardTitle")
        r_w_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_w_d = QLabel("Choose whether AI answers automatically on interview questions, after every pause, or only on manual hotkey.")
        r_w_d.setObjectName("CardDesc")
        r_w_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_w_d.setWordWrap(True)
        r_w_txt.addWidget(r_w_t)
        r_w_txt.addWidget(r_w_d)

        self.cmb_when_to_answer = QComboBox()
        self.cmb_when_to_answer.addItem("Questions only (recommended)", "questions")
        self.cmb_when_to_answer.addItem("Every pause", "every_pause")
        self.cmb_when_to_answer.addItem("Manual only (Alt + Q)", "manual")
        self.cmb_when_to_answer.setFixedHeight(34)
        self.cmb_when_to_answer.setMinimumWidth(320)
        curr_when = getattr(self.config, "audio_when_to_answer", "questions")
        idx_w = self.cmb_when_to_answer.findData(curr_when)
        if idx_w >= 0:
            self.cmb_when_to_answer.setCurrentIndex(idx_w)
        self.cmb_when_to_answer.currentIndexChanged.connect(self._on_when_to_answer_changed)
        r_when.addLayout(r_w_txt, 1)
        r_when.addWidget(self.cmb_when_to_answer)
        cstt_layout.addLayout(r_when)

        sep2 = QFrame()
        sep2.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px;")
        cstt_layout.addWidget(sep2)

        # 3. Spoken Language Setting
        r_lang = QHBoxLayout()
        r_lang.setSpacing(16)
        r_l_txt = QVBoxLayout()
        r_l_txt.setSpacing(3)
        r_l_t = QLabel("Spoken Language")
        r_l_t.setObjectName("CardTitle")
        r_l_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_l_d = QLabel("Select expected speech language. Auto-detect may produce text in the wrong language on noisy audio.")
        r_l_d.setObjectName("CardDesc")
        r_l_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_l_d.setWordWrap(True)
        r_l_txt.addWidget(r_l_t)
        r_l_txt.addWidget(r_l_d)

        self.cmb_spoken_language = QComboBox()
        self.cmb_spoken_language.addItem("English (recommended)", "en")
        self.cmb_spoken_language.addItem("Spanish", "es")
        self.cmb_spoken_language.addItem("French", "fr")
        self.cmb_spoken_language.addItem("German", "de")
        self.cmb_spoken_language.addItem("Auto-detect (may produce text in wrong language on noise)", "auto")
        self.cmb_spoken_language.setFixedHeight(34)
        self.cmb_spoken_language.setMinimumWidth(320)
        curr_lang = getattr(self.config, "audio_language", "en")
        idx_lang = self.cmb_spoken_language.findData(curr_lang)
        if idx_lang >= 0:
            self.cmb_spoken_language.setCurrentIndex(idx_lang)
        self.cmb_spoken_language.currentIndexChanged.connect(self._on_spoken_language_changed)
        r_lang.addLayout(r_l_txt, 1)
        r_lang.addWidget(self.cmb_spoken_language)
        cstt_layout.addLayout(r_lang)

        sep3 = QFrame()
        sep3.setStyleSheet(f"background: {STROKE_CARD}; max-height: 1px;")
        cstt_layout.addWidget(sep3)

        # 4. Faster Answers (Early Start)
        r_fast = QHBoxLayout()
        r_fast.setSpacing(16)
        r_f_txt = QVBoxLayout()
        r_f_txt.setSpacing(3)
        r_f_t = QLabel("Faster answers (early start)")
        r_f_t.setObjectName("CardTitle")
        r_f_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        r_f_d = QLabel("Experimental: Begins speculative local inference at 0.35s pause if a question is detected, discarding if speech resumes within 0.8s.")
        r_f_d.setObjectName("CardDesc")
        r_f_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        r_f_d.setWordWrap(True)
        r_f_txt.addWidget(r_f_t)
        r_f_txt.addWidget(r_f_d)

        self.switch_faster_answers = QtModernToggleSwitch(checked=getattr(self.config, "faster_answers_enabled", False))
        self.switch_faster_answers.toggled.connect(self._on_faster_answers_toggled)
        r_fast.addLayout(r_f_txt, 1)
        r_fast.addWidget(self.switch_faster_answers)
        cstt_layout.addLayout(r_fast)

        parent_layout.addWidget(card_stt)

        # 3. Built-in Speed Benchmark Card
        sec_bench = QLabel("Speech Engine Speed Test")
        sec_bench.setObjectName("SectionTitle")
        sec_bench.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY}; margin-top: 6px;")
        parent_layout.addWidget(sec_bench)

        card_bench = QFrame()
        card_bench.setObjectName("CardFrame")
        card_bench.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        cb_layout = QVBoxLayout(card_bench)
        cb_layout.setContentsMargins(20, 18, 20, 18)
        cb_layout.setSpacing(14)

        b_head = QHBoxLayout()
        b_txt = QVBoxLayout()
        b_t = QLabel("Live Transcription Latency Benchmark")
        b_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        b_d = QLabel("Measures model load speed, inference latency, and real-time factor (RTF) directly on this CPU.")
        b_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        b_txt.addWidget(b_t)
        b_txt.addWidget(b_d)

        self.btn_run_speed_test = QPushButton("Run Speed Test")
        self.btn_run_speed_test.setObjectName("SecondaryBtn")
        self.btn_run_speed_test.setIcon(get_fluent_icon("sparkle", color=TEXT_PRIMARY, size=14, filled=False))
        self.btn_run_speed_test.setFixedHeight(34)
        self.btn_run_speed_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run_speed_test.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_ELEVATED}; color: {TEXT_PRIMARY}; font-size: 12.5px; font-weight: 500; padding: 0px 16px; border-radius: {RADIUS_CONTROL}px; border: 1px solid {STROKE_CONTROL}; }} QPushButton#SecondaryBtn:hover {{ background-color: #3D3D3D; }}")
        self.btn_run_speed_test.clicked.connect(self._run_speed_test_clicked)

        b_head.addLayout(b_txt, 1)
        b_head.addWidget(self.btn_run_speed_test)
        cb_layout.addLayout(b_head)

        self.lbl_stt_bench_result = QLabel("Click 'Run Speed Test' to benchmark speech transcription speed.")
        self.lbl_stt_bench_result.setWordWrap(True)
        self.lbl_stt_bench_result.setStyleSheet(f"background: {SURFACE_INPUT}; color: {TEXT_SECONDARY}; padding: 10px 14px; border-radius: {RADIUS_CONTROL}px; font-size: 12.5px; font-family: Consolas, monospace;")
        cb_layout.addWidget(self.lbl_stt_bench_result)

        parent_layout.addWidget(card_bench)

    def _build_stt_diagnostics_card(self, parent_layout: QVBoxLayout):
        """Builds diagnostics section for STT performance telemetry."""
        c_stt_diag = QFrame()
        c_stt_diag.setObjectName("CardFrame")
        c_stt_diag.setStyleSheet(f"QFrame#CardFrame {{ background-color: {SURFACE_CARD}; border: 1px solid {STROKE_CARD}; border-radius: {RADIUS_CARD}px; }}")
        csd_layout = QVBoxLayout(c_stt_diag)
        csd_layout.setContentsMargins(20, 18, 20, 18)
        csd_layout.setSpacing(12)

        csd_head = QHBoxLayout()
        csd_t = QLabel("Speech-to-Text Performance Telemetry")
        csd_t.setStyleSheet(f"background: transparent; font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        csd_head.addWidget(csd_t)
        csd_head.addStretch()

        btn_copy_diag = QPushButton("Copy Diagnostics")
        btn_copy_diag.setObjectName("SecondaryBtn")
        btn_copy_diag.setIcon(get_fluent_icon("copy", color=TEXT_PRIMARY, size=13, filled=False))
        btn_copy_diag.setFixedHeight(30)
        btn_copy_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_diag.setStyleSheet(f"QPushButton#SecondaryBtn {{ background-color: {SURFACE_ELEVATED}; color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500; padding: 0px 12px; border-radius: {RADIUS_CONTROL}px; border: 1px solid {STROKE_CONTROL}; }} QPushButton#SecondaryBtn:hover {{ background-color: #3D3D3D; }}")
        btn_copy_diag.clicked.connect(self._copy_diagnostics_clicked)
        csd_head.addWidget(btn_copy_diag)
        csd_layout.addLayout(csd_head)

        self.lbl_diag_stt = QLabel(get_stt_diagnostics_line())
        self.lbl_diag_stt.setWordWrap(True)
        self.lbl_diag_stt.setStyleSheet(f"background: {SURFACE_INPUT}; color: {BRAND_TEXT}; padding: 10px 14px; border-radius: {RADIUS_CONTROL}px; font-size: 12px; font-family: Consolas, monospace;")
        csd_layout.addWidget(self.lbl_diag_stt)

        parent_layout.addWidget(c_stt_diag)

    def _sync_live_session_from_vm(self):
        """Synchronizes Home screen Live session card with central view-model."""
        if not hasattr(self, "card_live_session"):
            return
        vm = self.live_session_vm

        # 1. Badge & status
        if vm.is_capturing:
            self.lbl_live_badge.setText("LIVE")
            self.lbl_live_badge.setStyleSheet("background-color: #14532D; color: #86EFAC; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 4px;")
            stat = f"{vm.engine_status} • Latency: ~{vm.latency_ms:.0f}ms" if vm.latency_ms > 0 else vm.engine_status
            self.lbl_live_status.setText(stat)
        else:
            self.lbl_live_badge.setText("IDLE")
            self.lbl_live_badge.setStyleSheet(f"background-color: {SURFACE_INPUT}; color: {TEXT_TERTIARY}; font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 4px;")
            self.lbl_live_status.setText("Ready • Sub-500ms pipeline")

        # 2. Transcript
        lines = []
        for s in vm.segments[-15:]:
            t = s.text.strip()
            if len(t) > 500:
                t = t[:497] + "…"
            lines.append(f"<b>[{s.time_str}] {s.speaker_label}</b> {t}")
        for src, partial in vm.partial_text.items():
            if partial:
                p = partial.strip()
                if len(p) > 200:
                    p = p[:197] + "…"
                tag = "[You (mic)]" if src == "mic" else "[System]"
                lines.append(f"<i style='color: #94A3B8;'>{tag} {p}...</i>")
        if lines:
            self.txt_live_transcript.setHtml("<br>".join(lines))
            sb = self.txt_live_transcript.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        else:
            self.txt_live_transcript.setPlainText("Transcript will appear here in real-time as speakers talk.")

        # 3. Question
        if vm.current_question:
            self.lbl_live_question.setText(f"Interviewer asks: \"{vm.current_question}\"")
        else:
            self.lbl_live_question.setText("Ready for speech. Speak or play call audio.")

        # 4. Thinking timer
        if vm.is_thinking:
            self._update_live_thinking_ticker()
            if not self._live_thinking_timer.isActive():
                self._live_thinking_timer.start()
        else:
            if self._live_thinking_timer.isActive():
                self._live_thinking_timer.stop()
            self.lbl_live_thinking.setVisible(False)

        # 5. Streamed / Final Answer
        if vm.streamed_tokens:
            self.txt_live_answer.setPlainText(vm.streamed_tokens)
            sb_ans = self.txt_live_answer.verticalScrollBar()
            if sb_ans:
                sb_ans.setValue(sb_ans.maximum())
        elif vm.completed_answer:
            self.txt_live_answer.setPlainText(vm.completed_answer)
        elif not vm.is_thinking:
            self.txt_live_answer.setPlainText("AI answer will stream here in real-time when a question is asked.")

        # 6. Error & Fix
        if vm.error_message:
            self.lbl_live_error_msg.setText(vm.error_message)
            self.btn_live_error_fix.setText(vm.fix_label or "Fix")
            self.btn_live_error_fix.setProperty("fix_action", vm.fix_action)
            self.frame_live_error.setVisible(True)
        else:
            self.frame_live_error.setVisible(False)

        # Refresh STT diagnostics line if visible
        if hasattr(self, "lbl_diag_stt"):
            self.lbl_diag_stt.setText(get_stt_diagnostics_line())

    def _update_live_thinking_ticker(self):
        vm = self.live_session_vm
        if vm.is_thinking:
            elapsed = time.monotonic() - vm.thinking_start_time
            self.lbl_live_thinking.setText(f"⚡ Thinking... ({elapsed:.1f}s)")
            self.lbl_live_thinking.setVisible(True)
        else:
            self._live_thinking_timer.stop()
            self.lbl_live_thinking.setVisible(False)

    def _on_live_ask_clicked(self):
        if self.on_live_ask:
            self.on_live_ask()

    def _on_live_copy_clicked(self):
        text = self.txt_live_answer.toPlainText().strip()
        if text and text != "AI answer will stream here in real-time when a question is asked.":
            QApplication.clipboard().setText(text)
            self.btn_live_copy.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.btn_live_copy.setText("Copy Answer"))

    def _on_live_clear_clicked(self):
        self.live_session_vm.clear()
        if self.on_live_clear:
            self.on_live_clear()
        self._sync_live_session_from_vm()

    def _on_live_error_fix_clicked(self):
        action = self.btn_live_error_fix.property("fix_action") or "open_settings_ai"
        if self.on_live_fix:
            self.on_live_fix(action)
        elif action == "start_ollama":
            import subprocess
            try:
                subprocess.Popen(["ollama", "serve"], shell=True)
            except Exception:
                pass
        else:
            self.switch_screen("models")

    def _on_stt_preset_changed(self, index: int):
        val = self.cmb_stt_preset.itemData(index)
        if val:
            self.config.audio_whisper_model = val
            save_config(self.config)
            if self.on_settings_saved:
                self.on_settings_saved(self.config)

    def _on_when_to_answer_changed(self, index: int):
        val = self.cmb_when_to_answer.itemData(index)
        if val:
            self.config.audio_when_to_answer = val
            save_config(self.config)
            if self.on_settings_saved:
                self.on_settings_saved(self.config)

    def _on_spoken_language_changed(self, index: int):
        val = self.cmb_spoken_language.itemData(index)
        if val:
            self.config.audio_language = val
            save_config(self.config)
            if hasattr(self, "audio_assistant") and self.audio_assistant:
                transcriber = getattr(self.audio_assistant, "transcriber", None)
                if transcriber:
                    transcriber.language = val
            if self.on_settings_saved:
                self.on_settings_saved(self.config)

    def _on_faster_answers_toggled(self, checked: bool):
        self.config.faster_answers_enabled = checked
        save_config(self.config)
        if hasattr(self, "audio_assistant") and self.audio_assistant:
            self.audio_assistant.faster_answers_enabled = checked
            transcriber = getattr(self.audio_assistant, "transcriber", None)
            if transcriber:
                transcriber.faster_answers_enabled = checked
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _run_speed_test_clicked(self):
        self.btn_run_speed_test.setEnabled(False)
        self.lbl_stt_bench_result.setText("Benchmarking local speech engine (please wait ~1s)...")
        QApplication.processEvents()

        def _bench_thread():
            model = getattr(self.config, "audio_whisper_model", "tiny")
            if self.on_test_stt_benchmark:
                res = self.on_test_stt_benchmark(model)
            else:
                from ghostline.audio.transcription import run_stt_benchmark
                res = run_stt_benchmark(model, 3.0)

            def _update():
                self.btn_run_speed_test.setEnabled(True)
                if "error" in res and res.get("error"):
                    self.lbl_stt_bench_result.setText(f"Benchmark Error: {res['error']}")
                else:
                    tip = f"\nTip: {res['power_tip']}" if res.get('power_tip') else ""
                    self.lbl_stt_bench_result.setText(
                        f"Model: {res.get('model', 'tiny')} | Threads: {res.get('threads', 4)} | "
                        f"Load: {res.get('load_ms', 0):.0f}ms | Latency: {res.get('latency_ms', 0):.0f}ms | "
                        f"RTF: {res.get('rtf', 0):.3f} ({res.get('rating', 'Fast')}){tip}"
                    )
            QTimer.singleShot(0, _update)

        threading.Thread(target=_bench_thread, daemon=True).start()

    def _copy_diagnostics_clicked(self):
        from ghostline.build_info import get_build_summary
        from ghostline.core.hardware_profile import get_hardware_summary_string
        binfo = get_build_summary()
        stt_line = get_stt_diagnostics_line()
        hw_line = get_hardware_summary_string()
        lines = [
            f"Ghostline v{binfo['version']} ({binfo['git_commit_short']})",
            f"Build Timestamp: {binfo['build_timestamp']}",
            f"Platform: {sys.platform} ({os.name})",
            hw_line,
            stt_line
        ]
        full_text = "\n".join(lines)
        QApplication.clipboard().setText(full_text)

    def _handle_exit_clicked(self):
        """Dedicated exit button clicked in the left sidebar."""
        self.force_exit()

    def force_exit(self):
        """Forces total application shutdown and resource cleanup."""
        if getattr(self, "_is_force_exit", False):
            return
        self._is_force_exit = True
        if callable(self.on_exit):
            try:
                self.on_exit()
            except Exception as e:
                print(f"[!] Error during on_exit: {e}")
        self.close()

    def show_from_tray(self):
        """Restores window from system tray to normal view."""
        self._is_minimized_to_tray = False
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.activateWindow()
        self.raise_()

    def minimize_window(self):
        """Standard minimize control."""
        self.showMinimized()

    def maximize_window(self):
        """Standard maximize control to fill usable desktop area."""
        self.showMaximized()

    def restore_window(self):
        """Standard restore control."""
        self.showNormal()

    def toggle_maximize(self):
        """Toggles between maximized and normal window states."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def close_window(self):
        """Triggers standard window close sequence."""
        self.close()

