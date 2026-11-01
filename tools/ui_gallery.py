"""
Ghostline Microsoft Fluent 2 Dark — Component Gallery.
Provides a comprehensive showcase of primitive shared components:
- Primary, Secondary, Subtle, Danger buttons (normal, hover, disabled)
- LineEdit and ComboBox inputs
- QtModernToggleSwitch (checked and unchecked)
- Card frames and settings rows
- Thin 8px scrollbars
- Themed QMenu
- Interactive Shortcut & Modal Dialogs
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure repo root is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QLineEdit, QComboBox,
    QProgressBar, QMenu, QGridLayout
)

from ghostline.ui.theme import (
    apply_fluent_theme, get_fluent_icon,
    SURFACE_CANVAS, SURFACE_SIDEBAR, SURFACE_CARD, SURFACE_ELEVATED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BRAND_FILL, BRAND_TEXT, STATUS_SUCCESS_TEXT, STATUS_WARNING_TEXT, STATUS_DANGER_TEXT
)
from ghostline.ui.qt_theme import QtModernToggleSwitch


class FluentComponentGallery(QMainWindow):
    """Component Gallery showcase window for Microsoft Fluent 2 Dark components."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ghostline Fluent 2 Dark — Component Gallery")
        self.resize(1000, 840)
        self.setMinimumSize(900, 700)

        central = QWidget(self)
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header_bar = QFrame()
        header_bar.setFixedHeight(64)
        header_bar.setStyleSheet(f"background-color: {SURFACE_SIDEBAR}; border-bottom: 1px solid #2E2E2E;")
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(28, 0, 28, 0)
        
        lbl_head = QLabel("Microsoft Fluent 2 Dark — Component Gallery")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {TEXT_PRIMARY};")
        lbl_sub = QLabel("Primitives, Controls, Surfaces & Accessibility Verification")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {TEXT_TERTIARY};")
        hb_layout.addWidget(lbl_head)
        hb_layout.addSpacing(16)
        hb_layout.addWidget(lbl_sub)
        hb_layout.addStretch()
        main_layout.addWidget(header_bar)

        # Scrollable Gallery Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        content.setStyleSheet(f"background-color: {SURFACE_CANVAS};")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(36, 28, 36, 36)
        c_layout.setSpacing(24)

        # --- Section 1: Buttons ---
        sec1 = QLabel("1. Standard Button Variants")
        sec1.setObjectName("SectionTitle")
        c_layout.addWidget(sec1)

        card_btns = QFrame()
        card_btns.setObjectName("CardFrame")
        cb_layout = QVBoxLayout(card_btns)
        cb_layout.setContentsMargins(20, 20, 20, 20)
        cb_layout.setSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_primary = QPushButton("Primary Action")
        btn_primary.setObjectName("PrimaryBtn")
        btn_primary.setIcon(get_fluent_icon("sparkle", color="#FFFFFF", size=16, filled=True))
        btn_primary.setFixedSize(140, 36)
        btn_row.addWidget(btn_primary)

        btn_secondary = QPushButton("Secondary Action")
        btn_secondary.setObjectName("SecondaryBtn")
        btn_secondary.setIcon(get_fluent_icon("settings", color=TEXT_PRIMARY, size=16, filled=False))
        btn_secondary.setFixedSize(150, 36)
        btn_row.addWidget(btn_secondary)

        btn_subtle = QPushButton("Subtle Action")
        btn_subtle.setObjectName("SubtleBtn")
        btn_subtle.setIcon(get_fluent_icon("history", color=TEXT_SECONDARY, size=16, filled=False))
        btn_subtle.setFixedSize(130, 36)
        btn_row.addWidget(btn_subtle)

        btn_danger = QPushButton("Danger Action")
        btn_danger.setObjectName("DangerBtn")
        btn_danger.setIcon(get_fluent_icon("exit", color=STATUS_DANGER_TEXT, size=16, filled=False))
        btn_danger.setFixedSize(130, 36)
        btn_row.addWidget(btn_danger)

        btn_disabled = QPushButton("Disabled Action")
        btn_disabled.setEnabled(False)
        btn_disabled.setFixedSize(130, 36)
        btn_row.addWidget(btn_disabled)

        btn_row.addStretch()
        cb_layout.addLayout(btn_row)
        c_layout.addWidget(card_btns)

        # --- Section 2: Form Controls (LineEdit, ComboBox, Toggle) ---
        sec2 = QLabel("2. Inputs & Interactive Controls")
        sec2.setObjectName("SectionTitle")
        c_layout.addWidget(sec2)

        card_inputs = QFrame()
        card_inputs.setObjectName("CardFrame")
        ci_layout = QGridLayout(card_inputs)
        ci_layout.setContentsMargins(20, 20, 20, 20)
        ci_layout.setSpacing(16)

        # LineEdit
        lbl_le = QLabel("Standard Text Input:")
        lbl_le.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        txt_input = QLineEdit("Default input value")
        txt_input.setFixedHeight(34)
        ci_layout.addWidget(lbl_le, 0, 0)
        ci_layout.addWidget(txt_input, 0, 1)

        # ComboBox
        lbl_cb = QLabel("Standard Dropdown:")
        lbl_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        combo = QComboBox()
        combo.setFixedHeight(34)
        combo.addItems(["Ollama (Local Inference)", "OpenAI (GPT-4o)", "Groq (Llama 3 70B)", "Anthropic (Claude 3.5)"])
        ci_layout.addWidget(lbl_cb, 1, 0)
        ci_layout.addWidget(combo, 1, 1)

        # Toggle Switch
        lbl_sw = QLabel("Fluent 2 Toggle Switch:")
        lbl_sw.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        sw_row = QHBoxLayout()
        sw_row.setSpacing(16)
        sw_on = QtModernToggleSwitch(checked=True)
        lbl_on = QLabel("Active (On)")
        lbl_on.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        sw_off = QtModernToggleSwitch(checked=False)
        lbl_off = QLabel("Inactive (Off)")
        lbl_off.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        sw_row.addWidget(sw_on)
        sw_row.addWidget(lbl_on)
        sw_row.addSpacing(20)
        sw_row.addWidget(sw_off)
        sw_row.addWidget(lbl_off)
        sw_row.addStretch()
        ci_layout.addWidget(lbl_sw, 2, 0)
        ci_layout.addLayout(sw_row, 2, 1)

        c_layout.addWidget(card_inputs)

        # --- Section 3: Status & Feedback ---
        sec3 = QLabel("3. Badges, Progress & Feedback Indicators")
        sec3.setObjectName("SectionTitle")
        c_layout.addWidget(sec3)

        card_status = QFrame()
        card_status.setObjectName("CardFrame")
        cs_layout = QVBoxLayout(card_status)
        cs_layout.setContentsMargins(20, 20, 20, 20)
        cs_layout.setSpacing(14)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(12)

        def make_badge(dot_color, text, text_color):
            b = QFrame()
            b.setStyleSheet(f"background-color: {SURFACE_ELEVATED}; border: 1px solid #383838; border-radius: 6px; padding: 4px 10px;")
            l = QHBoxLayout(b)
            l.setContentsMargins(6, 4, 6, 4)
            l.setSpacing(6)
            d = QLabel("●")
            d.setStyleSheet(f"color: {dot_color}; font-size: 9px;")
            t = QLabel(text)
            t.setStyleSheet(f"color: {text_color}; font-size: 12px; font-weight: 500;")
            l.addWidget(d)
            l.addWidget(t)
            return b

        badge_row.addWidget(make_badge(STATUS_SUCCESS_TEXT, "Online · Connected", TEXT_PRIMARY))
        badge_row.addWidget(make_badge(STATUS_WARNING_TEXT, "Warning · Retrying", TEXT_PRIMARY))
        badge_row.addWidget(make_badge(STATUS_DANGER_TEXT, "Error · Service Offline", TEXT_PRIMARY))
        badge_row.addStretch()
        cs_layout.addLayout(badge_row)

        # Progress bar
        pbar = QProgressBar()
        pbar.setFixedHeight(6)
        pbar.setValue(68)
        pbar.setTextVisible(False)
        cs_layout.addWidget(pbar)

        c_layout.addWidget(card_status)

        # --- Section 4: Menus & Dialogs ---
        sec4 = QLabel("4. Menus & Modal Dialogs")
        sec4.setObjectName("SectionTitle")
        c_layout.addWidget(sec4)

        card_dialogs = QFrame()
        card_dialogs.setObjectName("CardFrame")
        cd_layout = QHBoxLayout(card_dialogs)
        cd_layout.setContentsMargins(20, 20, 20, 20)
        cd_layout.setSpacing(16)

        btn_menu = QPushButton("Open Context Menu ▾")
        btn_menu.setObjectName("SecondaryBtn")
        btn_menu.setFixedHeight(34)
        
        # Menu with items
        menu = QMenu(self)
        menu.addAction("Solve Question (Alt + /)")
        menu.addAction("Toggle Audio Assistant (Alt + A)")
        menu.addSeparator()
        menu.addAction("Open Settings")
        btn_menu.setMenu(menu)
        cd_layout.addWidget(btn_menu)

        btn_show_dialog = QPushButton("Open Shortcut Configuration Dialog")
        btn_show_dialog.setObjectName("SecondaryBtn")
        btn_show_dialog.setFixedHeight(34)
        btn_show_dialog.clicked.connect(self._show_shortcut_dialog)
        cd_layout.addWidget(btn_show_dialog)
        cd_layout.addStretch()

        c_layout.addWidget(card_dialogs)
        c_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

    def _show_shortcut_dialog(self):
        from ghostline.ui.qt_main_window import QtShortcutDialog
        dlg = QtShortcutDialog(current_hotkey="alt+/", parent=self)
        dlg.exec()


def render_gallery(outdir: str = "ui_shots/slice3", scales: list = None):
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    if scales is None:
        scales = [1.0, 1.5, 2.0]

    from ghostline.ui.render_harness import load_system_fonts_for_offscreen
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    load_system_fonts_for_offscreen()
    apply_fluent_theme(app)

    gallery = FluentComponentGallery()
    gallery.resize(1000, 840)
    gallery.show()

    rendered = []
    for scale in scales:
        pct = int(scale * 100)
        img_name = f"gallery_{pct}pct.png"
        img_path = out_path / img_name
        
        pixmap = QPixmap(int(1000 * scale), int(840 * scale))
        pixmap.setDevicePixelRatio(scale)
        gallery.render(pixmap)
        pixmap.save(str(img_path), "PNG")
        rendered.append(str(img_path))
        print(f"[+] Rendered Gallery at {pct}%: {img_path} ({pixmap.width()}x{pixmap.height()})")

    gallery.close()
    return rendered


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghostline Fluent 2 Component Gallery")
    parser.add_argument("--render", action="store_true", help="Render offscreen gallery images")
    parser.add_argument("--outdir", default="ui_shots/slice3", help="Output directory for rendered PNGs")
    args = parser.parse_args()

    if args.render:
        render_gallery(outdir=args.outdir)
    else:
        app = QApplication(sys.argv)
        apply_fluent_theme(app)
        win = FluentComponentGallery()
        win.show()
        sys.exit(app.exec())

