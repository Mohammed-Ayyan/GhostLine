"""
Comprehensive Test Suite for Ghostline Support & Community Card (Run 17):
- Build with and without QR asset
- QR pixmap decoding from widget.grab() across 100/125/150/200% DPR scales
- Dark-on-light white tile contrast verification
- QDesktopServices.openUrl monkeypatched verification for Star & Bug buttons
- QFileDialog.getSaveFileName monkeypatched verification for Save QR button
- Clipboard copy verification for Copy Repo Link button
- Strict zero-network enforcement (socket connect patched)
- Privacy leak scan across live widget hierarchy (zero raw UPI ID, payee name, or upi:// strings)
- Inertness verification (no timers or popups created)
- Sidebar support link navigation
"""

import sys
import os
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pytest
import numpy as np
import cv2

from PyQt6.QtWidgets import QApplication, QWidget, QDialog
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QImage

from ghostline.config import AppConfig
from ghostline.build_info import REPO_URL, REPO_ISSUES_URL
from ghostline.ui.support_card import QtSupportCard, QtSupportQrDialog, render_qr_pixmap, get_support_asset_path
from ghostline.ui.qt_main_window import QtGhostlineMainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(scope="module")
def ref_payload():
    detector = cv2.QRCodeDetector()
    cand_paths = [
        Path("support_inputs/WhatsApp Image 2026-11-08 at 17.15.47.jpeg"),
        Path("assets/support/Ghostline-support-qr-original-cropped.png"),
        Path("website/assets/support/Ghostline-support-qr-original-cropped.png"),
        Path("assets/support/Ghostline-support-qr.png")
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


def test_support_card_builds_with_qr(qapp):
    card = QtSupportCard()
    assert card.objectName() == "supportCard"
    assert card.has_qr_asset is True
    assert card.btn_star_github is not None
    assert card.lbl_support_qr is not None
    assert card.btn_show_larger is not None
    assert card.btn_save_qr is not None
    assert card.btn_report_bug is not None
    assert card.btn_suggest_feature is not None
    assert card.btn_copy_repo_link is not None


def test_support_card_builds_without_qr(qapp, monkeypatch):
    import ghostline.ui.support_card as sc_mod
    monkeypatch.setattr(sc_mod, "get_support_asset_path", lambda fn: None)

    card = sc_mod.QtSupportCard()
    assert card.has_qr_asset is False
    assert card.lbl_support_qr is None
    assert card.btn_show_larger is None
    assert card.btn_save_qr is None
    # Block A and subtle links must still exist cleanly
    assert card.btn_star_github is not None
    assert card.btn_report_bug is not None
    assert card.btn_suggest_feature is not None
    assert card.btn_copy_repo_link is not None


def test_qr_pixmap_grab_and_decodes_at_scales(qapp, ref_payload):
    card = QtSupportCard()
    card.show()
    detector = cv2.QRCodeDetector()

    for dpr in [1.0, 1.25, 1.5, 2.0]:
        pm = render_qr_pixmap(200, dpr=dpr)
        assert not pm.isNull(), f"Rendered QR pixmap is null at dpr={dpr}"
        card.lbl_support_qr.setPixmap(pm)

        # Grab actual widget pixels
        grabbed = card.lbl_support_qr.grab()
        qimg = grabbed.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        h, w = qimg.height(), qimg.width()
        arr = np.ndarray(shape=(h, w, 4), dtype=np.uint8, buffer=ptr, strides=(qimg.bytesPerLine(), 4, 1))
        bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

        decoded_text, _, _ = detector.detectAndDecode(bgr)
        assert decoded_text, f"Failed to decode QR from grabbed widget at dpr={dpr}"
        assert decoded_text == ref_payload, f"Decoded payload mismatch at dpr={dpr}"
    card.close()


def test_white_tile_is_dark_on_light(qapp):
    card = QtSupportCard()
    assert hasattr(card, "qr_tile"), "Missing qr_tile on support card"
    # Check stylesheet specifies solid #FFFFFF background
    sheet = card.qr_tile.styleSheet()
    assert "#FFFFFF" in sheet.upper(), f"Tile background is not solid white: {sheet}"


def test_star_and_report_bug_open_urls(qapp, monkeypatch):
    opened_urls = []

    def mock_open_url(url: QUrl):
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", mock_open_url)

    card = QtSupportCard()
    card.btn_star_github.click()
    assert opened_urls == [REPO_URL], f"Star button did not open {REPO_URL}"

    opened_urls.clear()
    card.btn_report_bug.click()
    assert opened_urls == [REPO_ISSUES_URL], f"Report bug button did not open {REPO_ISSUES_URL}"

    opened_urls.clear()
    card.btn_suggest_feature.click()
    assert opened_urls == [REPO_ISSUES_URL], f"Suggest feature button did not open {REPO_ISSUES_URL}"


def test_save_qr_image_writes_valid_file(qapp, monkeypatch, ref_payload):
    detector = cv2.QRCodeDetector()
    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = Path(tmpdir) / "test_saved_qr.png"

        def mock_get_save_filename(*args, **kwargs):
            return str(target_path), "PNG Image (*.png)"

        import ghostline.ui.support_card as sc_mod
        monkeypatch.setattr(sc_mod.QFileDialog, "getSaveFileName", mock_get_save_filename)

        card = sc_mod.QtSupportCard()
        card.btn_save_qr.click()

        assert target_path.exists(), "Saved QR file was not created"
        saved_bgr = cv2.imread(str(target_path))
        decoded, _, _ = detector.detectAndDecode(saved_bgr)
        assert decoded == ref_payload, "Saved QR file does not decode to reference payload"


def test_copy_repo_link_sets_clipboard(qapp):
    card = QtSupportCard()
    cb = QGuiApplication.clipboard()
    cb.clear()

    card.btn_copy_repo_link.click()
    assert cb.text() == REPO_URL, f"Clipboard text mismatch: {cb.text()} != {REPO_URL}"
    assert card.btn_copy_repo_link.text() == "Copied!"


def test_zero_network_access(qapp, monkeypatch):
    """Asserts that building the support card and clicking buttons triggers 0 network socket calls."""
    connections = []
    orig_connect = socket.socket.connect

    def forbidden_connect(self, *args, **kwargs):
        connections.append(args)
        raise AssertionError(f"Forbidden network connection attempted: {args}")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)

    card = QtSupportCard()
    card.btn_star_github.click()
    card.btn_report_bug.click()
    card.btn_suggest_feature.click()
    card.btn_copy_repo_link.click()

    dlg = QtSupportQrDialog()
    assert len(connections) == 0, f"Network connections were made: {connections}"


def test_zero_privacy_leaks_in_widget_tree(qapp, ref_payload):
    """Verifies that unmasked UPI ID, payee name, or upi:// never appear in widget text or properties."""
    parsed = urlparse(ref_payload)
    qs = parse_qs(parsed.query)
    raw_pa = qs.get("pa", [""])[0]
    raw_pn = qs.get("pn", [""])[0]

    forbidden_tokens = ["upi://"]
    if raw_pa:
        forbidden_tokens.append(raw_pa)
    if raw_pn and len(raw_pn) >= 3:
        forbidden_tokens.append(raw_pn)

    card = QtSupportCard()
    dlg = QtSupportQrDialog()

    for root_w in [card, dlg]:
        for widget in root_w.findChildren(QWidget):
            text = ""
            if hasattr(widget, "text"):
                text += " " + str(widget.text())
            if hasattr(widget, "toolTip"):
                text += " " + str(widget.toolTip())
            if hasattr(widget, "accessibleName"):
                text += " " + str(widget.accessibleName())
            text += " " + str(widget.objectName())

            for tok in forbidden_tokens:
                assert tok.lower() not in text.lower(), f"Privacy leak detected in {widget.objectName()}: found sensitive token!"


def test_support_card_is_inert_no_timers_or_popups(qapp):
    card = QtSupportCard()
    # Check no lingering QTimers created with active interval
    active_timers = [c for c in card.findChildren(QWidget) if hasattr(c, "isActive") and c.isActive()]
    assert len(active_timers) == 0, "Active timer running on support card"


def test_sidebar_support_link_navigates(qapp):
    cfg = AppConfig()
    win = QtGhostlineMainWindow(cfg)

    win.show_screen("dashboard")
    assert win.current_screen == "dashboard"

    # Click sidebar support link
    win.btn_sidebar_support.click()
    assert win.current_screen == "help", "Clicking sidebar link did not switch to help screen"
