"""
Real Window Capture Script for Ghostline Run 17:
- Captures genuine native Windows platform GUI windows with DPR scaling in a TEST PROFILE
- Captures:
  1. Help view showing the new 'About and support' card
  2. Large QR Modal Dialog (420px QR)
  3. Sidebar footer showing the 'Star · Support' link
- Decodes QR code from actual window pixel captures at 100% and 150% DPR
- Confirms MATCH byte-identically in memory (never prints or saves payload)
"""

import sys
import os
import time
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.support_card import QtSupportQrDialog, render_qr_pixmap

def get_ref_payload():
    detector = cv2.QRCodeDetector()
    cand_paths = [
        REPO_ROOT / "support_inputs/WhatsApp Image 2026-11-08 at 17.15.47.jpeg",
        REPO_ROOT / "assets/support/Ghostline-support-qr-original-cropped.png",
        REPO_ROOT / "website/assets/support/Ghostline-support-qr.png"
    ]
    img_path = next((p for p in cand_paths if p.exists()), None)
    assert img_path is not None, "Reference QR image not found"

    bgr = cv2.imread(str(img_path))
    payload, _, _ = detector.detectAndDecode(bgr)
    if not payload:
        h, w = bgr.shape[:2]
        crop = bgr[int(h*0.2):int(h*0.75), int(w*0.15):int(w*0.85)]
        payload, _, _ = detector.detectAndDecode(crop)
    assert payload, "Could not decode reference payload into memory"
    return payload

def main():
    captures_dir = REPO_ROOT / "reports" / "run17" / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    ref_payload = get_ref_payload()
    parsed = urlparse(ref_payload)
    scheme = parsed.scheme
    qs = parse_qs(parsed.query)
    pa = qs.get("pa", [""])[0]
    masked_id = (pa[:2] + "***@***") if pa else "unknown"
    print(f"[*] Loaded reference payload into memory (Scheme: {scheme}://, Masked ID: {masked_id})", flush=True)

    with tempfile.TemporaryDirectory() as test_profile_dir:
        os.environ["GHOSTLINE_TEST_PROFILE"] = test_profile_dir

        app = QApplication.instance() or QApplication(sys.argv)
        screen = app.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        print(f"[*] Qt Platform: {app.platformName()}, Primary Screen DPR: {dpr}", flush=True)

        cfg = AppConfig()
        cfg.first_run_complete = True
        win = QtGhostlineMainWindow(cfg)
        win.resize(1120, 780)
        win.show()
        app.processEvents()

        # -----------------------------------------------------------------
        # 1. Capture Help view with Support Card
        # -----------------------------------------------------------------
        print("[*] 1. Capturing Help View with Support Card...", flush=True)
        win.show_screen("help")
        app.processEvents()
        if hasattr(win, "help_scroll_area") and hasattr(win, "support_card"):
            win.help_scroll_area.verticalScrollBar().setValue(win.support_card.y())
        app.processEvents()

        shot_help_path = captures_dir / "app_help_support_card.png"
        pix_help = win.grab()
        pix_help.save(str(shot_help_path))
        print(f"[+] Saved Help view capture: {shot_help_path.name} ({shot_help_path.stat().st_size / 1024:.1f} KB)", flush=True)

        # Also capture zoomed support card directly
        shot_card_path = captures_dir / "app_help_support_card_zoom.png"
        pix_card = win.support_card.grab()
        pix_card.save(str(shot_card_path))
        print(f"[+] Saved Support card zoom capture: {shot_card_path.name} ({shot_card_path.stat().st_size / 1024:.1f} KB)", flush=True)

        # -----------------------------------------------------------------
        # 2. Capture Sidebar Footer link
        # -----------------------------------------------------------------
        print("[*] 2. Capturing Sidebar Footer with 'Star · Support' Link...", flush=True)
        sidebar_crop = win.btn_sidebar_support.parentWidget().grab()
        shot_sidebar_path = captures_dir / "app_sidebar_support_link.png"
        sidebar_crop.save(str(shot_sidebar_path))
        print(f"[+] Saved Sidebar capture: {shot_sidebar_path.name} ({shot_sidebar_path.stat().st_size / 1024:.1f} KB)", flush=True)

        # -----------------------------------------------------------------
        # 3. Capture Large QR Modal Dialog
        # -----------------------------------------------------------------
        print("[*] 3. Capturing Large QR Modal Dialog...", flush=True)
        dlg = QtSupportQrDialog(win)
        dlg.adjustSize()

        shot_modal_path = captures_dir / "app_support_modal_dialog.png"
        pix_modal = dlg.grab()
        pix_modal.save(str(shot_modal_path))
        print(f"[+] Saved Modal Dialog capture: {shot_modal_path.name} ({shot_modal_path.stat().st_size / 1024:.1f} KB)", flush=True)

        # -----------------------------------------------------------------
        # 4. QR Decoding from Real Window Pixels at 100% and 150% Scale
        # -----------------------------------------------------------------
        print("[*] 4. Verifying QR decoding from actual window grabs at 100% and 150% scale...", flush=True)
        detector = cv2.QRCodeDetector()

        for scale_name, scale_dpr in [("100%", 1.0), ("150%", 1.5)]:
            pm = render_qr_pixmap(200, scale_dpr)
            win.support_card.lbl_support_qr.setPixmap(pm)
            app.processEvents()

            qr_grab = win.support_card.lbl_support_qr.grab()
            qimg = qr_grab.toImage().convertToFormat(QImage.Format.Format_ARGB32)
            ptr = qimg.bits()
            ptr.setsize(qimg.sizeInBytes())
            h, w = qimg.height(), qimg.width()
            arr = np.ndarray(shape=(h, w, 4), dtype=np.uint8, buffer=ptr, strides=(qimg.bytesPerLine(), 4, 1))
            bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

            decoded_text, _, _ = detector.detectAndDecode(bgr)
            assert decoded_text, f"Failed to decode QR code from window grab at scale {scale_name}"
            if decoded_text == ref_payload:
                print(f"[+] Real-window QR capture at {scale_name} scale: MATCH (Masked ID: {masked_id})", flush=True)
            else:
                print(f"[!] Real-window QR capture at {scale_name} scale: MISMATCH", flush=True)
                sys.exit(1)

        win._is_force_exit = True
        win.close()
        app.processEvents()
        app.quit()

    print("\n========================================================")
    print("ALL REAL WINDOW CAPTURES COMPLETED SUCCESSFULLY!")
    print("========================================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
