"""
Ghostline Real Window Capture Engine
Captures pixel-perfect screenshots of the running GUI using the native Windows platform plugin.
Grabs exclusively the application's native HWND via QScreen.grabWindow().
"""

import sys
import os
import time
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from ghostline.config import AppConfig


def run_real_capture(
    outdir: str,
    sizes: Optional[List[Tuple[int, int]]] = None,
    scale: Optional[float] = None
) -> int:
    """
    Runs the real GUI on the default Windows platform plugin (native DWM),
    visits every screen, dialog, and HUD state, and captures the exact native HWND client.
    """
    out_path = Path(outdir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting Ghostline Real Window Capture Engine...")
    print(f"[*] Output directory: {out_path}")

    # 1. Isolate temporary test profile
    temp_dir = Path(tempfile.mkdtemp(prefix="ghostline_capture_"))
    dummy_cfg = AppConfig()
    dummy_cfg.first_run_complete = True

    # Default target sizes per specification:
    # maximized, 1920x1080, 1536x864, 1366x768, 1280x720, 900x600
    target_sizes = sizes or [
        (1920, 1080),
        (1536, 864),
        (1366, 768),
        (1280, 720),
        (900, 600),
        ("maximized", None)
    ]

    # Ensure QApplication exists
    app = QApplication.instance()
    if not app:
        # DO NOT force offscreen; run on native Windows platform plugin
        app = QApplication(sys.argv)

    screen = app.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    print(f"[*] Native display plugin: {app.platformName()}, Primary Screen DPR: {dpr}")
    print(f"[*] Capture method: QScreen.grabWindow(HWND) via Windows DWM surface")

    from ghostline.ui.qt_main_window import QtGhostlineMainWindow, QtFirstRunWizardDialog
    from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
    from ghostline.ui.presentation import PresentedAnswer

    captured_count = 0

    for sz in target_sizes:
        win = QtGhostlineMainWindow(config=dummy_cfg)
        
        is_max = (isinstance(sz, tuple) and sz[0] == "maximized") or sz == "maximized"
        if is_max:
            win.showMaximized()
            app.processEvents()
            time.sleep(0.15)
            w, h = win.width(), win.height()
            size_label = f"maximized_{w}x{h}"
        else:
            w, h = sz
            win.resize(w, h)
            win.show()
            app.processEvents()
            time.sleep(0.15)
            size_label = f"{w}x{h}"

        scale_subfolder = out_path / f"scale_{int(dpr*100)}pct"
        scale_subfolder.mkdir(parents=True, exist_ok=True)

        screens = [
            "dashboard", "general", "help", "mode", "model",
            "profile", "history", "security", "diagnostics", "audio"
        ]

        for s_id in screens:
            win.show_screen(s_id)
            app.processEvents()
            time.sleep(0.08)

            hwnd = int(win.winId())
            # Grab native HWND surface
            pixmap = screen.grabWindow(hwnd)
            shot_file = scale_subfolder / f"main_{s_id}_{size_label}.png"
            pixmap.save(str(shot_file), "PNG")
            captured_count += 1

        win.close()
        app.processEvents()

    # Capture HUD Overlay States (fixed overlay size ~680x580)
    print("[*] Capturing Floating HUD Overlay states...")
    hud = QtGhostlineHudOverlay(width=680, height=580)
    hud.resize(680, 580)
    hud.show()
    app.processEvents()
    time.sleep(0.1)

    hud_subfolder = out_path / f"scale_{int(dpr*100)}pct"
    hud_subfolder.mkdir(parents=True, exist_ok=True)

    # 1. Idle HUD
    hud.show()
    app.processEvents()
    time.sleep(0.08)
    hud_hwnd = int(hud.winId())
    screen.grabWindow(hud_hwnd).save(str(hud_subfolder / "hud_idle_680x580.png"), "PNG")
    captured_count += 1

    # 2. Answer HUD
    mock_ans = PresentedAnswer(
        question_type="mcq",
        badge="B",
        headline="Option B: Transport Layer",
        direct_answer="Transport Layer",
        explanation="The Transport Layer (Layer 4) is responsible for end-to-end communication, segment sequencing, and flow control.",
        confidence=98.5,
        options={"A": "Network Layer", "B": "Transport Layer", "C": "Session Layer", "D": "Data Link Layer"},
        selected_option_key="B",
        question_text="Which layer of the OSI model handles TCP segment sequencing and flow control?"
    )
    hud.update_answer(mock_ans)
    app.processEvents()
    time.sleep(0.08)
    screen.grabWindow(hud_hwnd).save(str(hud_subfolder / "hud_answer_680x580.png"), "PNG")
    captured_count += 1

    # 3. Notice / Error HUD
    hud.show_notice_card("Notice", "Unable to detect question region under cursor. Please hover and press Alt + /.")
    app.processEvents()
    time.sleep(0.08)
    screen.grabWindow(hud_hwnd).save(str(hud_subfolder / "hud_error_680x580.png"), "PNG")
    captured_count += 1

    # 4. Hardware Drawer HUD
    hud.toggle_hardware_drawer()
    app.processEvents()
    time.sleep(0.08)
    screen.grabWindow(hud_hwnd).save(str(hud_subfolder / "hud_hardware_680x580.png"), "PNG")
    captured_count += 1

    hud.close()
    app.processEvents()

    # Capture Setup Wizard Dialog
    print("[*] Capturing Setup Wizard Dialog...")
    wiz = QtFirstRunWizardDialog(config=dummy_cfg)
    wiz.show()
    app.processEvents()
    time.sleep(0.1)
    wiz_hwnd = int(wiz.winId())
    screen.grabWindow(wiz_hwnd).save(str(hud_subfolder / "dialog_wizard_640x520.png"), "PNG")
    captured_count += 1
    wiz.close()
    app.processEvents()

    # Clean up temp test profile
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    print(f"[+] Real-window capture complete! Captured {captured_count} images into {out_path}")
    return 0
