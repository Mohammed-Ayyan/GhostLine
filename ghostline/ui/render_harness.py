"""
Ghostline UI Render Harness & Layout Audit Tool.
Renders all views, HUD states, dialogs, and menus offscreen at multiple window sizes and DPI scales.
Performs automated layout audits (geometry overflow, horizontal scrollbars, text clipping).
Dumps the widget inventory to JSON.
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QFontMetrics, QIcon, QAction, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QComboBox,
    QLineEdit, QScrollArea, QScrollBar, QMenu, QMessageBox
)

from ghostline.config import AppConfig, save_config
from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
from ghostline.ui.presentation import PresentedAnswer


def get_parent_chain(widget: QWidget) -> List[str]:
    chain = []
    curr = widget.parentWidget()
    while curr:
        name = curr.objectName() or curr.__class__.__name__
        chain.append(name)
        curr = curr.parentWidget()
    return chain


def audit_layout_of_widget(root: QWidget, page_name: str, width: int, height: int, scale: float) -> List[Dict[str, Any]]:
    issues = []

    # 1. Check for horizontal scrollbars
    for sb in root.findChildren(QScrollBar):
        if sb.orientation() == Qt.Orientation.Horizontal:
            if sb.isVisible() or sb.maximum() > 0:
                issues.append({
                    "page": page_name,
                    "type": "horizontal_scrollbar",
                    "widget": sb.objectName() or "QScrollBar",
                    "details": f"Horizontal scrollbar active (maximum={sb.maximum()}, visible={sb.isVisible()})",
                    "size": f"{width}x{height}",
                    "scale": scale
                })

    # 2. Check for clipped / elided text on labels and buttons
    for child in root.findChildren(QWidget):
        if not child.isVisible():
            continue
        text = ""
        if hasattr(child, "text") and callable(child.text):
            try:
                text = child.text()
            except Exception:
                text = ""

        if text and len(text.strip()) > 0:
            fm = child.fontMetrics()
            adv = fm.horizontalAdvance(text)
            w = child.width()
            # If advance is noticeably greater than widget width and widget isn't a word-wrapped label
            is_wrapped_label = isinstance(child, QLabel) and child.wordWrap()
            if not is_wrapped_label and w > 0 and adv > w:
                issues.append({
                    "page": page_name,
                    "type": "text_clipped",
                    "widget": child.objectName() or child.__class__.__name__,
                    "class": child.__class__.__name__,
                    "text": text[:60],
                    "advance_px": adv,
                    "width_px": w,
                    "overflow_px": adv - w,
                    "size": f"{width}x{height}",
                    "scale": scale
                })

    # 3. Check for child geometry overflow outside parent viewport
    for child in root.findChildren(QWidget):
        if not child.isVisible():
            continue
        parent = child.parentWidget()
        if not parent:
            continue
        # Skip scroll area container widget height overflow
        if isinstance(parent, QScrollArea) or (hasattr(parent, "parentWidget") and isinstance(parent.parentWidget(), QScrollArea)):
            # Only check horizontal overflow in scroll containers
            cw = child.geometry().x() + child.geometry().width()
            pw = parent.width()
            if pw > 0 and cw > pw + 4:
                issues.append({
                    "page": page_name,
                    "type": "horizontal_geometry_overflow",
                    "widget": child.objectName() or child.__class__.__name__,
                    "class": child.__class__.__name__,
                    "child_right": cw,
                    "parent_width": pw,
                    "overflow_px": cw - pw,
                    "size": f"{width}x{height}",
                    "scale": scale
                })

    return issues


def collect_widget_inventory(root: QWidget, page_name: str) -> List[Dict[str, Any]]:
    inv = []
    for w in root.findChildren(QWidget):
        text = ""
        if hasattr(w, "text") and callable(w.text):
            try:
                text = w.text()
            except Exception:
                text = ""
        tooltip = ""
        if hasattr(w, "toolTip") and callable(w.toolTip):
            try:
                tooltip = w.toolTip()
            except Exception:
                tooltip = ""

        inv.append({
            "page": page_name,
            "class": w.__class__.__name__,
            "objectName": w.objectName(),
            "text": text,
            "tooltip": tooltip,
            "enabled": w.isEnabled(),
            "visible": w.isVisible(),
            "parent_chain": get_parent_chain(w)
        })
    return inv


def create_realistic_sample_config(temp_dir: Path) -> AppConfig:
    cfg = AppConfig()
    cfg.ai_provider = "ollama"
    cfg.model_name = "qwen2.5:0.5b-instruct-q4_K_M-very-long-model-name-for-testing"
    cfg.ollama_url = "http://127.0.0.1:11434"
    cfg.hotkey = "Alt + /"
    cfg.hotkey_hud_toggle = "Alt + T"
    cfg.hotkey_quit = "Ctrl + Alt + Q"
    cfg.audio_hotkey_toggle = "Alt + A"
    cfg.show_hud_on_solve = False
    cfg.first_run_complete = True
    cfg.hud_opacity = 0.90
    cfg.caps_lock_indicator = True
    save_config(cfg, custom_path=temp_dir / "config.json")
    return cfg


def load_system_fonts_for_offscreen():
    win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for font_name in [
        "segoeui.ttf", "segoeuib.ttf", "segoeuisb.ttf", "segoeuisl.ttf",
        "seguiemj.ttf", "consola.ttf", "consolab.ttf", "CascadiaMono.ttf"
    ]:
        p = win_fonts / font_name
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))


def render_all_for_scale(scale: float, outdir: Path, sizes: List[tuple], dump_inventory: bool = False) -> Dict[str, Any]:
    os.environ["QT_SCALE_FACTOR"] = str(scale)
    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0], "-platform", "offscreen"])
    load_system_fonts_for_offscreen()
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        cfg = create_realistic_sample_config(temp_dir)

        from ghostline.ui.qt_main_window import QtGhostlineMainWindow, QtShortcutDialog
        from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay

        all_issues = []
        all_inventory = []
        rendered_images = []

        scale_tag = f"{int(scale * 100)}pct"
        scale_dir = outdir / scale_tag
        scale_dir.mkdir(parents=True, exist_ok=True)

        # -------------------------------------------------------------
        # 1. Render Main Window Pages
        # -------------------------------------------------------------
        pages = ["dashboard", "general", "model", "audio", "mode", "history", "security", "diagnostics"]

        for w, h in sizes:
            main_win = QtGhostlineMainWindow(config=cfg)
            main_win.resize(w, h)
            main_win.show()
            app.processEvents()

            for page_id in pages:
                main_win.show_screen(page_id)
                app.processEvents()
                time.sleep(0.02)
                app.processEvents()

                # Grab and save
                pix = main_win.grab()
                img_name = f"main_{page_id}_{w}x{h}_{scale_tag}.png"
                img_path = scale_dir / img_name
                pix.save(str(img_path))
                rendered_images.append(str(img_path))

                # Audit layout
                issues = audit_layout_of_widget(main_win, f"main_{page_id}", w, h, scale)
                all_issues.extend(issues)

                # Dump inventory once (at standard scale 1.0 and 1100x720)
                if dump_inventory and scale == 1.0 and w == 1100 and h == 720:
                    curr_inv = collect_widget_inventory(main_win.screen_frames[page_id], page_id)
                    all_inventory.extend(curr_inv)

            main_win.close()
            app.processEvents()

        # -------------------------------------------------------------
        # 2. Render HUD Overlay States
        # -------------------------------------------------------------
        hud = QtGhostlineHudOverlay()
        hud.resize(680, 580)
        hud.show()
        app.processEvents()

        # State A: Idle / Welcome
        hud._add_welcome_card()
        app.processEvents()
        img_idle = scale_dir / f"hud_idle_680x580_{scale_tag}.png"
        hud.grab().save(str(img_idle))
        rendered_images.append(str(img_idle))
        all_issues.extend(audit_layout_of_widget(hud, "hud_idle", 680, 580, scale))

        # State B: Answer State
        sample_answer = PresentedAnswer(
            badge="C",
            headline="Binary Heap",
            direct_answer="A Binary Heap provides O(log n) insertion and extraction of highest-priority elements.",
            explanation="A priority queue requires efficient retrieval of extreme elements. In a Binary Heap, elements can be inserted in O(log n) time and the minimum or maximum element can be extracted in O(log n) time, whereas an array or linked list would require O(n) for either insertion or extraction.",
            question_text="Which of the following data structures is most suitable for implementing an efficient priority queue with dynamic insertions?",
            options={
                "A": "Linked List (Unsorted)",
                "B": "Stack (LIFO)",
                "C": "Binary Heap (Min/Max Priority)",
                "D": "Binary Search Tree without balancing"
            },
            code="import heapq\n\nh = []\nheapq.heappush(h, (1, 'task_high'))\nheapq.heappush(h, (5, 'task_low'))\npriority, task = heapq.heappop(h)",
            code_language="python",
            is_validated=True,
            question_type="mcq"
        )
        hud.update_answer(sample_answer)
        app.processEvents()
        img_ans = scale_dir / f"hud_answer_680x580_{scale_tag}.png"
        hud.grab().save(str(img_ans))
        rendered_images.append(str(img_ans))
        all_issues.extend(audit_layout_of_widget(hud, "hud_answer", 680, 580, scale))

        # State C: Error State
        hud.show_notice_card("Inference Error Detected", "Failed to communicate with provider API endpoint: HTTP 429 Too Many Requests. Retrying in 4.5 seconds...")
        app.processEvents()
        img_err = scale_dir / f"hud_error_680x580_{scale_tag}.png"
        hud.grab().save(str(img_err))
        rendered_images.append(str(img_err))
        all_issues.extend(audit_layout_of_widget(hud, "hud_error", 680, 580, scale))

        # State D: Hardware Drawer Open
        hud.update_answer(sample_answer)
        if not hud.island_hardware.isVisible():
            hud.toggle_hardware_drawer()
        app.processEvents()
        img_hw = scale_dir / f"hud_hardware_680x580_{scale_tag}.png"
        hud.grab().save(str(img_hw))
        rendered_images.append(str(img_hw))
        all_issues.extend(audit_layout_of_widget(hud, "hud_hardware", 680, 580, scale))

        if dump_inventory and scale == 1.0:
            all_inventory.extend(collect_widget_inventory(hud, "hud_overlay"))

        hud.close()
        app.processEvents()

        # -------------------------------------------------------------
        # 3. Render Dialogs
        # -------------------------------------------------------------
        # Dialog A: Shortcut Dialog
        dlg = QtShortcutDialog(current_hotkey="Alt + /")
        dlg.resize(460, 240)
        dlg.show()
        app.processEvents()
        img_dlg = scale_dir / f"dialog_shortcut_460x240_{scale_tag}.png"
        dlg.grab().save(str(img_dlg))
        rendered_images.append(str(img_dlg))
        all_issues.extend(audit_layout_of_widget(dlg, "dialog_shortcut", 460, 240, scale))
        if dump_inventory and scale == 1.0:
            all_inventory.extend(collect_widget_inventory(dlg, "dialog_shortcut"))
        dlg.close()
        app.processEvents()

        # Dialog B: Sample QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("Settings Saved")
        msg.setText("All provider configuration options and DPAPI credentials have been saved.")
        msg.setInformativeText("Your changes will take effect immediately for all subsequent queries.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msg.show()
        app.processEvents()
        img_msg = scale_dir / f"dialog_messagebox_{scale_tag}.png"
        msg.grab().save(str(img_msg))
        rendered_images.append(str(img_msg))
        msg.close()
        app.processEvents()

        # -------------------------------------------------------------
        # 4. Render Tray Menu
        # -------------------------------------------------------------
        tray_menu = QMenu()
        tray_menu.setTitle("Ghostline")
        tray_menu.addAction("Open Ghostline")
        tray_menu.addAction("Show Last Answer")
        tray_menu.addAction("Solve Under Cursor (Alt+/)")
        tray_menu.addAction("Show/Hide Mini HUD (Alt+T)")
        tray_menu.addAction("Toggle Live Audio Capture (Alt+A)")
        tray_menu.addAction("Show/Hide Audio Panel")
        tray_menu.addAction("Pause/Resume Hover-to-Answer")
        tray_menu.addAction("Open Logs Folder")
        tray_menu.addAction("Settings")
        tray_menu.addSeparator()
        tray_menu.addAction("Quit Ghostline")
        tray_menu.show()
        app.processEvents()
        img_tray = scale_dir / f"tray_menu_{scale_tag}.png"
        tray_menu.grab().save(str(img_tray))
        rendered_images.append(str(img_tray))
        tray_menu.close()
        app.processEvents()

    return {
        "scale": scale,
        "images": rendered_images,
        "issues": all_issues,
        "inventory": all_inventory
    }
