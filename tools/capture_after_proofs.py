"""
Capture after visual proofs for Run 19 in reports/run19/captures/after/
"""

import os
import sys
from pathlib import Path

os.environ["GHOSTLINE_TEST_MODE"] = "1"
os.environ["GHOSTLINE_E2E"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow, QtFirstRunWizardDialog
from ghostline.ui.window_geometry import get_work_area


def capture_all():
    app = QApplication.instance() or QApplication(sys.argv)
    out_dir = ROOT / "reports" / "run19" / "captures" / "after"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Home Maximized (1920x1080@100)
    os.environ["GHOSTLINE_E2E_FAKE_SCREEN"] = "1920x1080@100"
    cfg = AppConfig()
    cfg.first_run_complete = True
    cfg.open_maximized = True
    win = QtGhostlineMainWindow(cfg)
    win.show()
    app.processEvents()

    img1 = QImage(win.size(), QImage.Format.Format_ARGB32)
    img1.fill(Qt.GlobalColor.transparent)
    win.render(img1)
    p1 = out_dir / "home_maximized.png"
    img1.save(str(p1))
    print(f"[+] Saved {p1} ({win.width()}x{win.height()}, maximized={win.isMaximized()})")
    win.close()

    # 2. Wizard on 1366x768@150
    os.environ["GHOSTLINE_E2E_FAKE_SCREEN"] = "1366x768@150"
    cfg_wiz = AppConfig()
    cfg_wiz.first_run_complete = False
    wiz = QtFirstRunWizardDialog(cfg_wiz)
    wiz.show()
    app.processEvents()

    img2 = QImage(wiz.size(), QImage.Format.Format_ARGB32)
    img2.fill(Qt.GlobalColor.transparent)
    wiz.render(img2)
    p2 = out_dir / "wizard_1366x768_scale150_step1.png"
    img2.save(str(p2))
    print(f"[+] Saved {p2} ({wiz.width()}x{wiz.height()})")
    wiz.close()

    # 3. Settings / Lite Mode Home (1920x1080@100)
    os.environ["GHOSTLINE_E2E_FAKE_SCREEN"] = "1920x1080@100"
    cfg_lite = AppConfig()
    cfg_lite.first_run_complete = True
    cfg_lite.performance_mode = "lite"
    win_lite = QtGhostlineMainWindow(cfg_lite)
    win_lite.show()
    win_lite.show_screen("general")
    app.processEvents()

    img3 = QImage(win_lite.size(), QImage.Format.Format_ARGB32)
    img3.fill(Qt.GlobalColor.transparent)
    win_lite.render(img3)
    p3 = out_dir / "lite_mode_general_settings.png"
    img3.save(str(p3))
    print(f"[+] Saved {p3} ({win_lite.width()}x{win_lite.height()})")
    win_lite.close()


if __name__ == "__main__":
    capture_all()
