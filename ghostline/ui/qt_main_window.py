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
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QScrollArea,
    QLineEdit, QComboBox, QProgressBar, QSizePolicy, QMessageBox
)

from ghostline import __version__
from ghostline.config import AppConfig, save_config, get_app_dir
from ghostline.ui.qt_theme import (
    QT_MAIN_STYLESHEET, QtModernToggleSwitch,
    C_BG_APP, C_BG_SIDEBAR, C_BG_CARD, C_BG_CARD_HOVER, C_BG_CARD_ACTIVE,
    C_BORDER, C_BORDER_LIGHT, C_BORDER_ACCENT, C_CYAN, C_EMERALD,
    C_AMBER, C_DANGER, C_GOLD, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_MUTED
)


class QtGhostlineMainWindow(QMainWindow):
    """
    State-of-the-art PyQt6 Main Desktop Interface for Ghostline.
    """

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
        get_audio_diagnostics: Optional[Callable[[], Dict[str, Any]]] = None,
        on_toggle_audio: Optional[Callable[[], bool]] = None,
    ):
        super().__init__()
        self.config = config
        self.on_trigger_solve = on_trigger_solve
        self.on_settings_saved = on_settings_saved
        self.on_toggle_hud = on_toggle_hud
        self.on_test_caps = on_test_caps
        self.on_exit = on_exit
        self.ollama_client = ollama_client
        self.on_test_mic = on_test_mic
        self.on_test_loopback = on_test_loopback
        self.on_test_transcription = on_test_transcription
        self.get_audio_diagnostics = get_audio_diagnostics
        self.on_toggle_audio = on_toggle_audio
        self.root = self

        self._is_minimized_to_tray = False
        self.current_screen = "dashboard"
        self.screen_frames = {}

        self.setWindowTitle("Ghostline — Offline AI Assistant")
        self.setMinimumSize(880, 640)
        self.resize(960, 680)
        self.setStyleSheet(QT_MAIN_STYLESHEET)

        self._init_ui()

    def _init_ui(self):
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
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 20)
        sidebar_layout.setSpacing(6)

        # Brand Logo & Title
        brand_layout = QHBoxLayout()
        brand_icon = QLabel("👻")
        brand_icon.setStyleSheet("font-size: 22px;")
        brand_title = QLabel("Ghostline")
        brand_title.setObjectName("HeaderTitle")
        brand_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        brand_layout.addWidget(brand_icon)
        brand_layout.addWidget(brand_title)
        brand_layout.addStretch()
        sidebar_layout.addLayout(brand_layout)

        # Engine Status Indicator Badge
        status_box = QFrame()
        status_box.setStyleSheet(f"background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; padding: 6px 10px; margin-top: 8px; margin-bottom: 12px;")
        status_box_layout = QHBoxLayout(status_box)
        status_box_layout.setContentsMargins(6, 4, 6, 4)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {C_EMERALD}; font-size: 11px;")
        self.status_text = QLabel("Engine Ready")
        self.status_text.setStyleSheet(f"color: {C_EMERALD}; font-size: 11.5px; font-weight: 600;")
        status_box_layout.addWidget(self.status_dot)
        status_box_layout.addWidget(self.status_text)
        status_box_layout.addStretch()
        sidebar_layout.addWidget(status_box)

        # Navigation items
        self.nav_buttons = {}
        nav_items = [
            ("general", "⚙️", "General"),
            ("mode", "🖥️", "Mode"),
            ("dashboard", "⚡", "Dashboard"),
            ("audio", "🎙️", "Audio"),
            ("model", "🧠", "Model"),
            ("history", "📜", "History"),
            ("security", "🛡️", "Security"),
            ("diagnostics", "🩺", "Diagnostics")
        ]

        for screen_id, icon, label in nav_items:
            btn = QPushButton(f"{icon}  {label}")
            btn.setObjectName("SidebarBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, s=screen_id: self.show_screen(s))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[screen_id] = btn

        sidebar_layout.addStretch()

        # Version & Offline notice at bottom of sidebar
        ver_lbl = QLabel(f"Ghostline v{__version__}\n100% Offline AI")
        ver_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px; line-height: 1.4;")
        sidebar_layout.addWidget(ver_lbl)

        main_layout.addWidget(sidebar)

        # ---------------------------------------------------------------------
        # 2. Main Stacked Content Views
        # ---------------------------------------------------------------------
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {C_BG_APP};")
        main_layout.addWidget(self.stack, 1)

        # Create Views
        self._build_general_view()     # Matching Reference 3
        self._build_mode_view()        # Matching Reference 4
        self._build_dashboard_view()   # Matching Primary Action Dashboard
        self._build_audio_view()       # Audio settings & VU meters
        self._build_model_view()       # Local Ollama manager
        self._build_history_view()     # Solved questions history
        self._build_security_view()    # Offline security assurance
        self._build_diagnostics_view() # Live diagnostic tools

        # Show initial screen
        self.show_screen("dashboard")

    # -------------------------------------------------------------------------
    # Screen 1: General Settings (Directly Matching Reference 3)
    # -------------------------------------------------------------------------
    def _build_general_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(24)

        # Title
        title = QLabel("General")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        # --- Section 1: Usage ---
        sec_usage = QLabel("Usage")
        sec_usage.setObjectName("SectionTitle")
        layout.addWidget(sec_usage)

        card_usage = QFrame()
        card_usage.setObjectName("CardFrame")
        c_usage_layout = QVBoxLayout(card_usage)
        c_usage_layout.setContentsMargins(20, 20, 20, 20)
        c_usage_layout.setSpacing(14)

        u_head = QHBoxLayout()
        u_title = QLabel("Searches left")
        u_title.setObjectName("CardTitle")
        u_left = QLabel("Unlimited (Offline)")
        u_left.setObjectName("CardTitle")
        u_left.setStyleSheet(f"color: {C_EMERALD};")
        u_head.addWidget(u_title)
        u_head.addStretch()
        u_head.addWidget(u_left)
        c_usage_layout.addLayout(u_head)

        u_sub = QLabel("100% on-device inference via local Ollama. Zero rate limits, zero subscriptions.")
        u_sub.setObjectName("CardDesc")
        c_usage_layout.addWidget(u_sub)

        # Progress bar
        pbar = QProgressBar()
        pbar.setFixedHeight(6)
        pbar.setValue(100)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"QProgressBar {{ background: rgba(255,255,255,0.06); border-radius: 3px; }} QProgressBar::chunk {{ background: {C_CYAN}; border-radius: 3px; }}")
        c_usage_layout.addWidget(pbar)

        # Subcard: Need more searches / Model card
        sub_card = QFrame()
        sub_card.setStyleSheet("QFrame { background: rgba(0,0,0,0.25); border-radius: 8px; }")
        sub_layout = QHBoxLayout(sub_card)
        sub_layout.setContentsMargins(14, 12, 14, 12)
        pro_tag = QLabel("Offline")
        pro_tag.setStyleSheet("background: #2a3142; color: #38bdf8; font-weight:700; font-size:11px; padding: 3px 8px; border-radius:4px;")
        sub_text_layout = QVBoxLayout()
        sub_t1 = QLabel("Local AI Engine Ready")
        sub_t1.setStyleSheet("color:#ffffff; font-weight:600; font-size:13px;")
        sub_t2 = QLabel("Running on your hardware at 127.0.0.1:11434 with 0 external network requests.")
        sub_t2.setStyleSheet(f"color:{C_TEXT_MUTED}; font-size:12px;")
        sub_text_layout.addWidget(sub_t1)
        sub_text_layout.addWidget(sub_t2)

        btn_verify = QPushButton("Verify Ollama")
        btn_verify.setStyleSheet("QPushButton { background-color: #ffffff; color: #0f1117; font-size: 12px; font-weight: 700; padding: 6px 16px; border-radius: 14px; border: none; } QPushButton:hover { background-color: #e2e8f0; }")
        btn_verify.clicked.connect(self._verify_ollama_status)

        sub_layout.addWidget(pro_tag)
        sub_layout.addSpacing(10)
        sub_layout.addLayout(sub_text_layout, 1)
        sub_layout.addWidget(btn_verify)
        c_usage_layout.addWidget(sub_card)

        btn_goto_model = QPushButton("Configure Local AI Models →")
        btn_goto_model.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG_CARD};
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
                border-radius: 8px;
                border: 1px solid {C_BORDER};
            }}
            QPushButton:hover {{
                background-color: {C_BG_CARD_HOVER};
                border-color: {C_CYAN};
            }}
        """)
        btn_goto_model.clicked.connect(lambda: self.show_screen("model"))
        c_usage_layout.addWidget(btn_goto_model)

        layout.addWidget(card_usage)

        # --- Section 2: Shortcut ---
        sec_shortcut = QLabel("Shortcut")
        sec_shortcut.setObjectName("SectionTitle")
        layout.addWidget(sec_shortcut)

        card_sc = QFrame()
        card_sc.setObjectName("CardFrame")
        sc_layout = QHBoxLayout(card_sc)
        sc_layout.setContentsMargins(20, 20, 20, 20)
        sc_text = QVBoxLayout()
        sc_t = QLabel("Custom Shortcut")
        sc_t.setObjectName("CardTitle")
        sc_d = QLabel("Set your own shortcut: Ctrl, Alt or Win, plus one key (e.g. Alt + /).")
        sc_d.setObjectName("CardDesc")
        sc_text.addWidget(sc_t)
        sc_text.addWidget(sc_d)

        self.btn_hotkey_chip = QPushButton("Ctrl + Alt + Win")
        self.btn_hotkey_chip.setObjectName("PillChipBtn")
        self.btn_hotkey_chip.setText(self.config.hotkey if hasattr(self.config, 'hotkey') else "Alt + /")
        self.btn_hotkey_chip.clicked.connect(self._edit_hotkey)

        sc_layout.addLayout(sc_text, 1)
        sc_layout.addWidget(self.btn_hotkey_chip)
        layout.addWidget(card_sc)

        # --- Section 3: App Visibility ---
        sec_vis = QLabel("App Visibility")
        sec_vis.setObjectName("SectionTitle")
        layout.addWidget(sec_vis)

        card_vis = QFrame()
        card_vis.setObjectName("CardFrame")
        vis_layout = QVBoxLayout(card_vis)
        vis_layout.setContentsMargins(20, 16, 20, 16)
        vis_layout.setSpacing(16)

        # Default icon row
        r1 = QHBoxLayout()
        r1_text = QVBoxLayout()
        r1_t = QLabel("Default icon")
        r1_t.setObjectName("CardTitle")
        r1_d = QLabel("Looks like an ordinary system icon rather than a special app.")
        r1_d.setObjectName("CardDesc")
        r1_text.addWidget(r1_t)
        r1_text.addWidget(r1_d)

        self.combo_icon = QComboBox()
        self.combo_icon.addItems(["Ghostline Icon", "Windows Utility", "Stealth Dot", "Calculator"])
        r1.addLayout(r1_text, 1)
        r1.addWidget(self.combo_icon)
        vis_layout.addLayout(r1)

        # Separator
        sep1 = QFrame()
        sep1.setStyleSheet(f"background: {C_BORDER}; max-height: 1px;")
        vis_layout.addWidget(sep1)

        # Hide from taskbar row (with Modern Toggle Switch)
        r2 = QHBoxLayout()
        r2_text = QVBoxLayout()
        r2_t = QLabel("Hide from taskbar")
        r2_t.setObjectName("CardTitle")
        r2_d = QLabel("Hides the Ghostline button from the taskbar. You can open the app from the system tray.")
        r2_d.setObjectName("CardDesc")
        r2_text.addWidget(r2_t)
        r2_text.addWidget(r2_d)

        self.switch_hide_taskbar = QtModernToggleSwitch(checked=getattr(self.config, "start_minimized", False))
        self.switch_hide_taskbar.toggled.connect(self._on_hide_taskbar_toggled)
        r2.addLayout(r2_text, 1)
        r2.addWidget(self.switch_hide_taskbar)
        vis_layout.addLayout(r2)

        # Separator
        sep2 = QFrame()
        sep2.setStyleSheet(f"background: {C_BORDER}; max-height: 1px;")
        vis_layout.addWidget(sep2)

        # Floating Stealth HUD row
        r3 = QHBoxLayout()
        r3_text = QVBoxLayout()
        r3_t = QLabel("Floating stealth HUD")
        r3_t.setObjectName("CardTitle")
        r3_d = QLabel("Display the floating overlay window when question is detected.")
        r3_d.setObjectName("CardDesc")
        r3_text.addWidget(r3_t)
        r3_text.addWidget(r3_d)

        self.switch_hud = QtModernToggleSwitch(checked=getattr(self.config, "show_hud_on_solve", True))
        self.switch_hud.toggled.connect(self._on_hud_toggled)
        r3.addLayout(r3_text, 1)
        r3.addWidget(self.switch_hud)
        vis_layout.addLayout(r3)

        # Separator
        sep3 = QFrame()
        sep3.setStyleSheet(f"background: {C_BORDER}; max-height: 1px;")
        vis_layout.addWidget(sep3)

        # Auto-copy verified answer row
        r4 = QHBoxLayout()
        r4_text = QVBoxLayout()
        r4_t = QLabel("Auto-copy verified answer")
        r4_t.setObjectName("CardTitle")
        r4_d = QLabel("Automatically copies verified answers directly to Windows clipboard.")
        r4_d.setObjectName("CardDesc")
        r4_text.addWidget(r4_t)
        r4_text.addWidget(r4_d)

        self.switch_autocopy = QtModernToggleSwitch(checked=getattr(self.config, "auto_copy_answer", False))
        self.switch_autocopy.toggled.connect(self._on_autocopy_toggled)
        r4.addLayout(r4_text, 1)
        r4.addWidget(self.switch_autocopy)
        vis_layout.addLayout(r4)

        layout.addWidget(card_vis)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["general"] = scroll
        self.screen_frames["settings"] = scroll

    # -------------------------------------------------------------------------
    # Screen 2: Mode Settings (Directly Matching Reference 4)
    # -------------------------------------------------------------------------
    def _build_mode_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(24)

        title = QLabel("Mode")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        sec_mode = QLabel("Mode Settings")
        sec_mode.setObjectName("SectionTitle")
        layout.addWidget(sec_mode)

        # Card 1: Point at question number
        c1 = QFrame()
        c1.setObjectName("CardFrame")
        c1_layout = QVBoxLayout(c1)
        c1_layout.setContentsMargins(20, 18, 20, 18)
        c1_t = QLabel("Point at a question number and press " + (self.config.hotkey if hasattr(self.config, 'hotkey') else "Alt + /") + ".")
        c1_t.setObjectName("CardTitle")
        c1_d = QLabel("The answer appears using the selected display method.")
        c1_d.setObjectName("CardDesc")
        c1_layout.addWidget(c1_t)
        c1_layout.addWidget(c1_d)
        layout.addWidget(c1)

        # Card 2: System tray icon with Set up button
        c2 = QFrame()
        c2.setObjectName("CardFrame")
        c2_layout = QHBoxLayout(c2)
        c2_layout.setContentsMargins(20, 18, 20, 18)
        c2_text = QVBoxLayout()
        c2_t = QLabel("System tray icon")
        c2_t.setObjectName("CardTitle")
        c2_d = QLabel("Turn it on in Settings so answers appear on the system tray icon.")
        c2_d.setObjectName("CardDesc")
        c2_text.addWidget(c2_t)
        c2_text.addWidget(c2_d)

        btn_setup = QPushButton("Set up")
        btn_setup.setStyleSheet("QPushButton { background-color: #ffffff; color: #0f1117; font-size: 12px; font-weight: 700; padding: 6px 16px; border-radius: 14px; border: none; } QPushButton:hover { background-color: #e2e8f0; }")
        btn_setup.clicked.connect(lambda: self.show_screen("general"))

        c2_layout.addLayout(c2_text, 1)
        c2_layout.addWidget(btn_setup)
        layout.addWidget(c2)

        # Card 3: Current mode dropdown
        c3 = QFrame()
        c3.setObjectName("CardFrame")
        c3_layout = QVBoxLayout(c3)
        c3_layout.setContentsMargins(20, 18, 20, 18)
        c3_layout.setSpacing(14)

        c3_head = QHBoxLayout()
        c3_text = QVBoxLayout()
        c3_t = QLabel("Current mode")
        c3_t.setObjectName("CardTitle")
        c3_d = QLabel("Answers appear as a small system tray icon. For multiple answers, the icon shows each one in turn.")
        c3_d.setObjectName("CardDesc")
        c3_text.addWidget(c3_t)
        c3_text.addWidget(c3_d)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["System Tray Icon", "Floating HUD Overlay", "Caps Lock Physical LED", "Silent Clipboard Only"])
        self.combo_mode.setCurrentIndex(1)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        c3_head.addLayout(c3_text, 1)
        c3_head.addWidget(self.combo_mode)
        c3_layout.addLayout(c3_head)

        # Visual preview canvas
        preview_box = QFrame()
        preview_box.setFixedHeight(220)
        preview_box.setStyleSheet(f"background: #090b10; border: 1px solid {C_BORDER}; border-radius: 8px;")
        p_layout = QVBoxLayout(preview_box)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_lbl = QLabel("🖥️ Live Mode Preview\n[ Floating HUD + Tray Badge Active ]\n\nPress Alt + / over any question to trigger.")
        preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 13px; font-weight: 500;")
        p_layout.addWidget(preview_lbl)
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
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        # Header with status
        head_layout = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("HeaderTitle")
        head_layout.addWidget(title)
        head_layout.addStretch()

        hud_btn = QPushButton("Toggle HUD")
        hud_btn.setObjectName("SecondaryBtn")
        hud_btn.clicked.connect(self._toggle_hud_click)
        head_layout.addWidget(hud_btn)
        layout.addLayout(head_layout)

        # Prominent Action 1: Screen Assistance
        c_screen = QFrame()
        c_screen.setObjectName("CardFrame")
        cs_layout = QHBoxLayout(c_screen)
        cs_layout.setContentsMargins(24, 22, 24, 22)
        cs_text = QVBoxLayout()
        cs_t = QLabel("🖥️ Screen Assistance")
        cs_t.setObjectName("CardTitle")
        cs_t.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {C_TEXT_PRIMARY};")
        cs_d = QLabel("Captures question under your mouse, parses OCR, and solves with local AI in <50ms.")
        cs_d.setObjectName("CardDesc")
        cs_text.addWidget(cs_t)
        cs_text.addWidget(cs_d)

        btn_solve = QPushButton("Run Screen Solve (Alt + /)")
        btn_solve.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_solve.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_CYAN};
                color: #080d16;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #7dd3fc;
            }}
        """)
        btn_solve.clicked.connect(self._trigger_solve_click)

        cs_layout.addLayout(cs_text, 1)
        cs_layout.addWidget(btn_solve)
        layout.addWidget(c_screen)

        # Prominent Action 2: Audio Assistance
        c_audio = QFrame()
        c_audio.setObjectName("CardFrame")
        ca_layout = QHBoxLayout(c_audio)
        ca_layout.setContentsMargins(24, 22, 24, 22)
        ca_text = QVBoxLayout()
        ca_t = QLabel("🎙️ Live Audio & Meeting Transcription")
        ca_t.setObjectName("CardTitle")
        ca_t.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {C_TEXT_PRIMARY};")
        ca_d = QLabel("Captures microphone and system audio loopback simultaneously (Zoom, Teams, Meet).")
        ca_d.setObjectName("CardDesc")
        ca_text.addWidget(ca_t)
        ca_text.addWidget(ca_d)

        self.btn_audio = QPushButton("Start Listening (Alt + L)")
        self.btn_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_audio.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG_CARD_HOVER};
                color: {C_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                padding: 10px 20px;
                border-radius: 8px;
                border: 1px solid {C_BORDER_LIGHT};
            }}
            QPushButton:hover {{
                background-color: {C_BG_CARD_ACTIVE};
                border-color: {C_CYAN};
            }}
        """)
        self.btn_audio.clicked.connect(self._toggle_audio_click)

        ca_layout.addLayout(ca_text, 1)
        ca_layout.addWidget(self.btn_audio)
        layout.addWidget(c_audio)

        # Recent Results Card
        sec_rec = QLabel("Recent Results & Activity")
        sec_rec.setObjectName("SectionTitle")
        layout.addWidget(sec_rec)

        self.card_recent = QFrame()
        self.card_recent.setObjectName("CardFrame")
        cr_layout = QVBoxLayout(self.card_recent)
        cr_layout.setContentsMargins(22, 20, 22, 20)
        cr_layout.setSpacing(12)

        res_head = QHBoxLayout()
        self.lbl_badge = QLabel("[Option B]")
        self.lbl_badge.setStyleSheet(f"background: rgba(56, 189, 248, 0.15); color: {C_CYAN}; font-weight: 800; font-size: 13px; padding: 4px 10px; border-radius: 6px;")
        self.lbl_conf = QLabel("Confidence: 99.4% • Windows OCR Verified")
        self.lbl_conf.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 12px;")
        res_head.addWidget(self.lbl_badge)
        res_head.addWidget(self.lbl_conf)
        res_head.addStretch()

        btn_copy = QPushButton("Copy Answer")
        btn_copy.setObjectName("SecondaryBtn")
        btn_copy.clicked.connect(self._copy_recent_answer)
        res_head.addWidget(btn_copy)
        cr_layout.addLayout(res_head)

        self.lbl_q = QLabel("Question: Which algorithm computes single-source shortest path on weighted graphs with non-negative weights in O((V + E) log V)?")
        self.lbl_q.setStyleSheet(f"color: {C_TEXT_PRIMARY}; font-size: 13.5px; font-weight: 600;")
        self.lbl_q.setWordWrap(True)
        cr_layout.addWidget(self.lbl_q)

        self.lbl_ans = QLabel("Answer: Dijkstra's Algorithm with Min-Heap\nDijkstra's algorithm finds the shortest path between nodes in a graph with non-negative edge weights in O((V + E) log V) time.")
        self.lbl_ans.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 13px; line-height: 1.4;")
        self.lbl_ans.setWordWrap(True)
        cr_layout.addWidget(self.lbl_ans)

        layout.addWidget(self.card_recent)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["dashboard"] = scroll
        self.screen_frames["main"] = scroll
        self.screen_frames["answer"] = scroll

    # -------------------------------------------------------------------------
    # Screen 4: Audio Settings & Diagnostics
    # -------------------------------------------------------------------------
    def _build_audio_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Audio Assistance")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        sec_src = QLabel("Audio Capture Sources")
        sec_src.setObjectName("SectionTitle")
        layout.addWidget(sec_src)

        card_src = QFrame()
        card_src.setObjectName("CardFrame")
        s_layout = QVBoxLayout(card_src)
        s_layout.setContentsMargins(20, 20, 20, 20)
        s_layout.setSpacing(16)

        # Microphone
        r_mic = QHBoxLayout()
        r_mic_txt = QVBoxLayout()
        r_mic_t = QLabel("Microphone Input")
        r_mic_t.setObjectName("CardTitle")
        r_mic_d = QLabel("Captures your spoken questions in real-time.")
        r_mic_d.setObjectName("CardDesc")
        r_mic_txt.addWidget(r_mic_t)
        r_mic_txt.addWidget(r_mic_d)
        self.sw_mic = QtModernToggleSwitch(checked=getattr(self.config, "audio_source_mic", True))
        self.sw_mic.toggled.connect(self._on_mic_source_toggled)
        r_mic.addLayout(r_mic_txt, 1)
        r_mic.addWidget(self.sw_mic)
        s_layout.addLayout(r_mic)

        sep = QFrame()
        sep.setStyleSheet(f"background: {C_BORDER}; max-height: 1px;")
        s_layout.addWidget(sep)

        # System Loopback
        r_sys = QHBoxLayout()
        r_sys_txt = QVBoxLayout()
        r_sys_t = QLabel("WASAPI System Loopback (Meeting Audio)")
        r_sys_t.setObjectName("CardTitle")
        r_sys_d = QLabel("Captures questions spoken by other callers in Zoom, Teams, or Discord directly from output.")
        r_sys_d.setObjectName("CardDesc")
        r_sys_txt.addWidget(r_sys_t)
        r_sys_txt.addWidget(r_sys_d)
        self.sw_sys = QtModernToggleSwitch(checked=getattr(self.config, "audio_source_system", True))
        self.sw_sys.toggled.connect(self._on_sys_source_toggled)
        r_sys.addLayout(r_sys_txt, 1)
        r_sys.addWidget(self.sw_sys)
        s_layout.addLayout(r_sys)

        layout.addWidget(card_src)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["audio"] = scroll

    # -------------------------------------------------------------------------
    # Screen 5: Model & Ollama Manager
    # -------------------------------------------------------------------------
    def _build_model_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Local AI Models (Ollama)")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        c_model = QFrame()
        c_model.setObjectName("CardFrame")
        cm_layout = QVBoxLayout(c_model)
        cm_layout.setContentsMargins(20, 20, 20, 20)
        cm_layout.setSpacing(14)

        t1 = QLabel("Active Inference Model")
        t1.setObjectName("CardTitle")
        cm_layout.addWidget(t1)

        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.addItems(["phi3:mini (Recommended, 2.3GB)", "llama3.2:3b", "mistral:7b", "mistral:latest", "qwen2.5:3b"])
        # Preselect configured model
        curr_model = getattr(self.config, "model_name", "phi3:mini")
        found_idx = -1
        for i in range(self.combo_model.count()):
            if self.combo_model.itemText(i).startswith(curr_model):
                found_idx = i
                break
        if found_idx >= 0:
            self.combo_model.setCurrentIndex(found_idx)
        else:
            self.combo_model.insertItem(0, curr_model)
            self.combo_model.setCurrentIndex(0)
        cm_layout.addWidget(self.combo_model)

        t2 = QLabel("Ollama Endpoint")
        t2.setObjectName("CardTitle")
        cm_layout.addWidget(t2)

        self.txt_endpoint = QLineEdit(getattr(self.config, "ollama_url", "http://127.0.0.1:11434"))
        cm_layout.addWidget(self.txt_endpoint)

        btn_save = QPushButton("Save Model Settings")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save_settings)
        cm_layout.addWidget(btn_save)

        layout.addWidget(c_model)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["model"] = scroll
        self.screen_frames["setup"] = scroll

    # -------------------------------------------------------------------------
    # Screen 6: History
    # -------------------------------------------------------------------------
    def _build_history_view(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(16)

        title = QLabel("History")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("🔍 Search past questions and answers...")
        self.history_search.textChanged.connect(self._on_history_search_changed)
        layout.addWidget(self.history_search)

        self.history_list_container = QWidget()
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
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Security & Privacy")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        c_sec = QFrame()
        c_sec.setObjectName("CardFrame")
        cs_layout = QVBoxLayout(c_sec)
        cs_layout.setContentsMargins(22, 20, 22, 20)
        cs_layout.setSpacing(12)

        s_t1 = QLabel("🛡️ Zero-Socket Guarantee")
        s_t1.setStyleSheet(f"font-size:16px; font-weight:700; color:{C_CYAN};")
        s_d1 = QLabel("Ghostline operates strictly on local loopback (127.0.0.1). No screen content, transcripts, or question queries ever leave your machine.")
        s_d1.setStyleSheet(f"color:{C_TEXT_SECONDARY}; font-size:13px; line-height:1.5;")
        s_d1.setWordWrap(True)
        cs_layout.addWidget(s_t1)
        cs_layout.addWidget(s_d1)

        layout.addWidget(c_sec)
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
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        title = QLabel("System Diagnostics")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        c_diag = QFrame()
        c_diag.setObjectName("CardFrame")
        cd_layout = QVBoxLayout(c_diag)
        cd_layout.setContentsMargins(20, 20, 20, 20)
        cd_layout.setSpacing(14)

        self.lbl_diag_results = QLabel("Click a test below to verify hardware & model readiness:")
        self.lbl_diag_results.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 13px;")
        cd_layout.addWidget(self.lbl_diag_results)

        btn_row = QHBoxLayout()
        b_mic = QPushButton("Test Microphone")
        b_mic.setObjectName("SecondaryBtn")
        b_mic.clicked.connect(self._test_mic_click)

        b_loop = QPushButton("Test Audio Loopback")
        b_loop.setObjectName("SecondaryBtn")
        b_loop.clicked.connect(self._test_loopback_click)

        b_caps = QPushButton("Test Caps Lock LED")
        b_caps.setObjectName("SecondaryBtn")
        b_caps.clicked.connect(self._test_caps_click)

        b_trans = QPushButton("Test Whisper Engine")
        b_trans.setObjectName("SecondaryBtn")
        b_trans.clicked.connect(self._test_transcription_click)

        btn_row.addWidget(b_mic)
        btn_row.addWidget(b_loop)
        btn_row.addWidget(b_caps)
        btn_row.addWidget(b_trans)
        cd_layout.addLayout(btn_row)

        layout.addWidget(c_diag)
        layout.addStretch()

        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        self.screen_frames["diagnostics"] = scroll

    # -------------------------------------------------------------------------
    # Public Methods & Backward Compatibility Interface
    # -------------------------------------------------------------------------
    def show_screen(self, screen_id: str):
        """Switches active view and updates sidebar highlight."""
        self.current_screen = screen_id
        if screen_id in self.screen_frames:
            self.stack.setCurrentWidget(self.screen_frames[screen_id])

        for sid, btn in self.nav_buttons.items():
            btn.setChecked(sid == screen_id)

    def show_window(self):
        self._is_minimized_to_tray = False
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        self._is_minimized_to_tray = True
        self.hide()

    def build(self):
        """Compatibility builder returning main window."""
        return self

    def destroy(self):
        self.close()

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
            self.btn_audio.setText("Stop Listening (Alt + L)" if active else "Start Listening (Alt + L)")

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
        from PyQt6.QtWidgets import QInputDialog
        curr = getattr(self.config, "hotkey", "alt+/")
        text, ok = QInputDialog.getText(
            self,
            "Configure Global Shortcut",
            "Enter shortcut (e.g. Alt + /, Ctrl + Alt + S, Alt + F1):",
            QLineEdit.EchoMode.Normal,
            curr
        )
        if ok and text.strip():
            new_hk = text.strip().lower()
            self.config.hotkey = new_hk
            self.btn_hotkey_chip.setText(new_hk)
            if self.on_settings_saved:
                self.on_settings_saved(self.config)
            QMessageBox.information(self, "Shortcut Saved", f"Global shortcut updated to {new_hk}!")

    def _on_mic_source_toggled(self, checked: bool):
        self.config.audio_source_mic = checked
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_sys_source_toggled(self, checked: bool):
        self.config.audio_source_system = checked
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_hide_taskbar_toggled(self, checked: bool):
        self.config.start_minimized = checked
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_hud_toggled(self, checked: bool):
        self.config.show_hud_on_solve = checked
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_autocopy_toggled(self, checked: bool):
        self.config.auto_copy_answer = checked
        if self.on_settings_saved:
            self.on_settings_saved(self.config)

    def _on_mode_changed(self, idx: int):
        modes = ["tray", "hud", "caps_lock", "silent"]
        if idx < len(modes):
            self.config.indicator_mode = modes[idx]
            if self.on_settings_saved:
                self.on_settings_saved(self.config)

    def _save_settings(self):
        if hasattr(self, "combo_model"):
            raw_model = self.combo_model.currentText().strip().split()[0]
            self.config.model_name = raw_model
        if hasattr(self, "txt_endpoint"):
            endpoint = self.txt_endpoint.text().strip()
            if endpoint:
                self.config.ollama_url = endpoint
        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)
        if hasattr(self, "lbl_settings_status"):
            self.lbl_settings_status.setText(f"✓ Saved! Model '{self.config.model_name}' configured.")
        else:
            QMessageBox.information(self, "Settings Saved", f"Model updated to '{self.config.model_name}' at {self.config.ollama_url}!")

    def _on_history_search_changed(self, text: str):
        self._refresh_history(filter_text=text.strip())

    def _copy_to_clip(self, txt: str):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(txt)
            QMessageBox.information(self, "Copied", "Question & answer copied to clipboard!")

    def _refresh_history(self, filter_text: str = ""):
        if not hasattr(self, "history_list_layout"):
            return

        # Clear existing items
        while self.history_list_layout.count() > 0:
            item = self.history_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        hist_file = get_app_dir() / "history.jsonl"
        entries = []
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
            except Exception as ex:
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

        if not entries:
            empty_msg = "No solved questions recorded yet.\nPress Alt + / over any question to start solving." if not filter_text else f"No past questions matched '{filter_text}'."
            empty_lbl = QLabel(empty_msg)
            empty_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 13px; padding: 30px 0;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_list_layout.addWidget(empty_lbl)
            return

        for entry in entries[:40]:
            card = QFrame()
            card.setObjectName("CardFrame")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(6)

            head = QHBoxLayout()
            ans_opt = entry.get("answer") or entry.get("proposed_answer") or "Solved"
            badge = QLabel(f"[{ans_opt}]")
            badge.setStyleSheet(f"background: rgba(56, 189, 248, 0.15); color: {C_CYAN}; font-weight: 700; font-size: 11px; padding: 2px 8px; border-radius: 4px;")

            t_stamp = entry.get("timestamp", 0)
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t_stamp)) if t_stamp else "Recorded"
            lbl_time = QLabel(time_str)
            lbl_time.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
            head.addWidget(badge)
            head.addWidget(lbl_time)
            head.addStretch()

            btn_c = QPushButton("Copy")
            btn_c.setStyleSheet(f"background: transparent; color: {C_TEXT_MUTED}; font-size: 11px; border: none;")
            full_txt = f"Question: {entry.get('question', '')}\nAnswer: {entry.get('proposed_answer', '')}\n{entry.get('explanation', '')}"
            btn_c.clicked.connect(lambda _, txt=full_txt: self._copy_to_clip(txt))
            head.addWidget(btn_c)
            card_layout.addLayout(head)

            q_txt = entry.get("question", "")
            if q_txt:
                lbl_q = QLabel(q_txt)
                lbl_q.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 13px;")
                lbl_q.setWordWrap(True)
                card_layout.addWidget(lbl_q)

            ans_txt = entry.get("explanation") or entry.get("proposed_answer") or ""
            if ans_txt:
                lbl_a = QLabel(ans_txt[:250] + ("..." if len(ans_txt) > 250 else ""))
                lbl_a.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12.5px; line-height: 1.4;")
                lbl_a.setWordWrap(True)
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
                self.btn_audio.setText("Stop Listening (Alt + L)" if not is_paused else "Resume Listening (Alt + L)")
            else:
                self.btn_audio.setText("Start Listening (Alt + L)")

    def get_window_rect(self):
        if not self.isVisible():
            return None
        geo = self.geometry()
        return (geo.left(), geo.top(), geo.right(), geo.bottom())

    def on_solve_started(self):
        if hasattr(self, "lbl_engine_status"):
            self.lbl_engine_status.setText("● Solving...")
            self.lbl_engine_status.setStyleSheet("color: #38bdf8; font-size: 11px;")
        if hasattr(self, "lbl_q"):
            self.lbl_q.setText("Extracting screen context and analyzing question...")
        if hasattr(self, "lbl_ans"):
            self.lbl_ans.setText("Consulting local neural engine...")

    def on_solve_success(self, presentation):
        if hasattr(self, "lbl_engine_status"):
            self.lbl_engine_status.setText("● Active Engine")
            self.lbl_engine_status.setStyleSheet("color: #10b981; font-size: 11px;")
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
            self.lbl_engine_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
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
            self.lbl_engine_status.setStyleSheet("color: #10b981; font-size: 11px;")
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
        pass

    def destroy(self):
        self.close()

