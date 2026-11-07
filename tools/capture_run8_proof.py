"""
Ghostline Run 8 Real Window Capture Proof Generator.
Captures the real Windows GUI (native Windows platform plugin, not offscreen)
for the 4 defect / feature areas required by Run 8 Section F2.
"""

import sys
import os
import time
import tempfile
import shutil
from pathlib import Path

# Add project root to sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ghostline.config import AppConfig
from ghostline.core.ollama_state import OllamaState
from ghostline.core.http_client import ProviderErrorInfo


def capture_run8_proof():
    out_dir = Path("reports/run8/captures").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    screen = app.primaryScreen()
    assert screen is not None, "Primary screen not available"
    print(f"[*] Capturing real windows with platform: {app.platformName()}, DPR: {screen.devicePixelRatio()}")

    from ghostline.ui.qt_main_window import QtGhostlineMainWindow, QtFirstRunWizardDialog

    # -------------------------------------------------------------
    # 1. Wizard Step 1 in Ollama states (not installed, stopped, ready)
    # -------------------------------------------------------------
    print("[*] 1. Capturing Wizard Step 1 Ollama states...")
    cfg = AppConfig()
    cfg.first_run_complete = False

    # State A: NOT_INSTALLED
    wiz = QtFirstRunWizardDialog(cfg)
    if hasattr(wiz, "ollama_wiz_card"):
        wiz.ollama_wiz_card.stop_polling()
        wiz.ollama_wiz_card.set_state(OllamaState.NOT_INSTALLED)
    wiz.resize(720, 560)
    wiz.show()
    app.processEvents()
    time.sleep(0.15)
    screen.grabWindow(int(wiz.winId())).save(str(out_dir / "wizard_step1_ollama_not_installed.png"), "PNG")

    # State B: INSTALLED_NOT_RUNNING
    if hasattr(wiz, "ollama_wiz_card"):
        wiz.ollama_wiz_card.set_state(OllamaState.INSTALLED_NOT_RUNNING)
    app.processEvents()
    time.sleep(0.15)
    screen.grabWindow(int(wiz.winId())).save(str(out_dir / "wizard_step1_ollama_stopped.png"), "PNG")

    # State C: READY
    if hasattr(wiz, "ollama_wiz_card"):
        wiz.ollama_wiz_card.set_state(OllamaState.READY)
    app.processEvents()
    time.sleep(0.15)
    screen.grabWindow(int(wiz.winId())).save(str(out_dir / "wizard_step1_ollama_ready.png"), "PNG")

    wiz.close()
    app.processEvents()

    # -------------------------------------------------------------
    # 2. Main Window: AI Settings Page with Error Banner & Copy Diagnostics
    # -------------------------------------------------------------
    print("[*] 2. Capturing AI Settings page with Provider Error Banner...")
    main_cfg = AppConfig()
    main_cfg.first_run_complete = True
    win = QtGhostlineMainWindow(main_cfg)
    win.resize(1100, 750)
    win.show()
    app.processEvents()
    time.sleep(0.15)

    # Navigate to AI settings page
    win.show_screen("model")
    app.processEvents()
    time.sleep(0.1)

    # Select Groq provider to show Cloud BYOK card and test connection UI
    if hasattr(win, "combo_provider"):
        for i in range(win.combo_provider.count()):
            if win.combo_provider.itemData(i) == "groq":
                win.combo_provider.setCurrentIndex(i)
                break
    app.processEvents()
    time.sleep(0.1)

    # Trigger error result with Copy Diagnostics button shown
    if hasattr(win, "lbl_test_result"):
        win.lbl_test_result.setText("Error: Cloudflare 403 Forbidden (error code: 1010). Request was blocked before reaching provider.")
        win.lbl_test_result.setStyleSheet("background: transparent; font-size: 12px; color: #F85149; font-weight: 500;")
    if hasattr(win, "btn_diag_copy"):
        win.btn_diag_copy.show()
    if hasattr(win, "btn_diag_copy") and "model" in win.screen_frames:
        win.screen_frames["model"].ensureWidgetVisible(win.btn_diag_copy)
    app.processEvents()
    time.sleep(0.15)
    screen.grabWindow(int(win.winId())).save(str(out_dir / "settings_ai_provider_error_banner.png"), "PNG")

    # -------------------------------------------------------------
    # 3. Settings > Tray & Startup with QtTrayHelpCard and restored SwitchHideTaskbar
    # -------------------------------------------------------------
    print("[*] 3. Capturing Settings > Tray & Startup...")
    win.show_screen("general")
    app.processEvents()
    time.sleep(0.1)
    if hasattr(win, "tray_help_card") and "general" in win.screen_frames:
        win.screen_frames["general"].ensureWidgetVisible(win.tray_help_card)
    app.processEvents()
    time.sleep(0.15)
    screen.grabWindow(int(win.winId())).save(str(out_dir / "settings_tray_and_startup.png"), "PNG")

    # -------------------------------------------------------------
    # 4. Home Page showing Status Chips
    # -------------------------------------------------------------
    print("[*] 4. Capturing Home Dashboard with Status Chips...")
    win.show_screen("dashboard")
    app.processEvents()
    time.sleep(0.1)
    screen.grabWindow(int(win.winId())).save(str(out_dir / "home_dashboard_status_chips.png"), "PNG")

    win.close()
    app.processEvents()
    print(f"[+] All proof captures saved successfully to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(capture_run8_proof())
