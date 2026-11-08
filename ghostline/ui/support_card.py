"""
Ghostline Support & Community Card (Fluent 2)
Provides an in-app "About and support" card on the Help page:
- Star on GitHub CTA with primary button (QDesktopServices.openUrl)
- Optional Buy Me a Coffee UPI QR tile (crisp dark-on-light, never inverted)
- Show larger QR modal (420px) and Save QR image action (QFileDialog)
- Subtle links row (Report a bug, Suggest a feature, Copy repo link)
- Zero network requests: strictly local, no telemetry, no reminders, no popups.
"""

import sys
import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialog, QFileDialog, QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, QUrl, QTimer, QSize
from PyQt6.QtGui import (
    QDesktopServices, QPixmap, QPainter, QImage,
    QGuiApplication, QColor, QFont
)
from PyQt6.QtSvg import QSvgRenderer

from ghostline.build_info import __version__, REPO_URL, REPO_ISSUES_URL
from ghostline.ui.theme.tokens import (
    SURFACE_CARD, SURFACE_INPUT, SURFACE_ELEVATED,
    STROKE_CARD, STROKE_CONTROL, STROKE_FOCUS_OUTER,
    RADIUS_CARD, RADIUS_CONTROL,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BRAND_FILL, BRAND_HOVER, BRAND_PRESSED, BRAND_TEXT,
    OVERLAY_HOVER
)
from ghostline.ui.theme.icons import get_fluent_icon, get_fluent_pixmap


def get_support_dir() -> Path:
    """Resolves assets/support across development and PyInstaller frozen builds."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "assets" / "support",
        Path(getattr(sys, "_MEIPASS", "")) / "assets" / "support",
        Path(sys.executable).resolve().parent / "assets" / "support",
        Path(sys.executable).resolve().parent / "_internal" / "assets" / "support",
        Path("assets/support"),
    ]
    for c in candidates:
        if c and c.exists() and c.is_dir():
            return c
    return Path("assets/support")


def get_support_asset_path(filename: str) -> Optional[Path]:
    """Finds a specific file in the support assets directory or dev fallbacks."""
    sdir = get_support_dir()
    p = sdir / filename
    if p.exists():
        return p
    dev_fallback = Path(__file__).resolve().parent.parent.parent / "website" / "assets" / "support" / filename
    if dev_fallback.exists():
        return dev_fallback
    return None


def render_qr_pixmap(logical_size: int = 200, dpr: float = 1.0) -> QPixmap:
    """
    Renders the bundled support QR SVG onto a crisp QPixmap scaled to devicePixelRatio.
    Falls back to bundled high-res PNG with smooth scaling if SVG is missing.
    """
    px_size = max(1, int(round(logical_size * dpr)))
    svg_path = get_support_asset_path("Ghostline-support-qr.svg")
    if svg_path and svg_path.exists():
        try:
            renderer = QSvgRenderer(str(svg_path))
            if renderer.isValid():
                pixmap = QPixmap(px_size, px_size)
                pixmap.fill(Qt.GlobalColor.white)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                pixmap.setDevicePixelRatio(dpr)
                return pixmap
        except Exception:
            pass

    png_path = get_support_asset_path("Ghostline-support-qr.png")
    if png_path and png_path.exists():
        try:
            src = QPixmap(str(png_path))
            if not src.isNull():
                scaled = src.scaled(
                    px_size, px_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                scaled.setDevicePixelRatio(dpr)
                return scaled
        except Exception:
            pass

    return QPixmap()


class QtSupportQrDialog(QDialog):
    """Accessible modal dialog showing the enlarged (420px) support QR code."""

    def __init__(self, parent: Optional[QWidget] = None, repo_url: str = REPO_URL):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.repo_url = repo_url
        self.setObjectName("supportQrDialog")
        self.setWindowTitle("Support Ghostline")
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog#supportQrDialog {{
                background-color: {SURFACE_ELEVATED};
                border: 1px solid {STROKE_CARD};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Header Title
        lbl_title = QLabel("Support Ghostline (UPI QR)")
        lbl_title.setObjectName("DialogTitle")
        lbl_title.setStyleSheet(f"background: transparent; font-size: 18px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("Scan with any UPI app (Google Pay, PhonePe, Paytm, BHIM, or your bank app). Supporting is entirely optional.")
        lbl_desc.setObjectName("DialogDesc")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"background: transparent; font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        layout.addWidget(lbl_desc)

        # QR Container (Solid White Rounded Tile, Dark on Light)
        tile = QFrame()
        tile.setObjectName("DialogQrTile")
        tile.setStyleSheet("""
            QFrame#DialogQrTile {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E0E0E0;
            }
        """)
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(12, 12, 12, 12)
        tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_large_qr = QLabel()
        self.lbl_large_qr.setObjectName("largeQrLabel")
        self.lbl_large_qr.setAccessibleName("Large QR code to support Ghostline")
        self.lbl_large_qr.setFixedSize(420, 420)
        self.lbl_large_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_large_qr.setStyleSheet("background-color: #FFFFFF; border: none;")

        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        pm = render_qr_pixmap(420, dpr)
        if not pm.isNull():
            self.lbl_large_qr.setPixmap(pm)

        tile_layout.addWidget(self.lbl_large_qr)
        layout.addWidget(tile, alignment=Qt.AlignmentFlag.AlignCenter)

        # Bank Account & Fraud Safety Disclosures
        note1 = QLabel("Scanning shows the payee name from my bank account.")
        note1.setObjectName("DialogNoteBank")
        note1.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY};")
        note1.setWordWrap(True)
        layout.addWidget(note1)

        note2 = QLabel("Only pay through this app or the official GitHub repository.")
        note2.setObjectName("DialogNoteFraud")
        note2.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_TERTIARY};")
        note2.setWordWrap(True)
        layout.addWidget(note2)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)
        actions_row.addStretch(1)

        self.btn_save_large_qr = QPushButton("Save QR image")
        self.btn_save_large_qr.setObjectName("dialogSaveQrButton")
        self.btn_save_large_qr.setIcon(get_fluent_icon("copy", color=TEXT_PRIMARY, size=14))
        self.btn_save_large_qr.setFixedHeight(34)
        self.btn_save_large_qr.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_large_qr.setStyleSheet(f"""
            QPushButton#dialogSaveQrButton {{
                background-color: {SURFACE_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#dialogSaveQrButton:hover {{
                background-color: {OVERLAY_HOVER};
                border-color: {TEXT_PRIMARY};
            }}
            QPushButton#dialogSaveQrButton:focus {{
                outline: 2px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_save_large_qr.clicked.connect(self._save_qr_clicked)
        actions_row.addWidget(self.btn_save_large_qr)

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("dialogCloseButton")
        self.btn_close.setFixedHeight(34)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(f"""
            QPushButton#dialogCloseButton {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                border: none;
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#dialogCloseButton:hover {{
                background-color: {BRAND_HOVER};
            }}
            QPushButton#dialogCloseButton:pressed {{
                background-color: {BRAND_PRESSED};
            }}
            QPushButton#dialogCloseButton:focus {{
                outline: 2px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_close.clicked.connect(self.accept)
        actions_row.addWidget(self.btn_close)

        layout.addLayout(actions_row)

    def _save_qr_clicked(self):
        png_src = get_support_asset_path("Ghostline-support-qr.png")
        if not png_src or not png_src.exists():
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Support QR",
            "Ghostline-support-qr.png",
            "PNG Image (*.png)"
        )
        if dest:
            shutil.copyfile(str(png_src), dest)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


class QtSupportCard(QFrame):
    """
    The 'About and support' card embedded on the Help page.
    Includes Star on GitHub, optional Buy Me a Coffee UPI QR, and subtle project links.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        repo_url: str = REPO_URL,
        issues_url: str = REPO_ISSUES_URL
    ):
        super().__init__(parent)
        self.repo_url = repo_url
        self.issues_url = issues_url
        self.setObjectName("supportCard")
        self.setStyleSheet(f"""
            QFrame#supportCard {{
                background-color: {SURFACE_CARD};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_CARD}px;
            }}
        """)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(16)

        # -------------------------------------------------------------
        # 1. Card Header: Title & App Version
        # -------------------------------------------------------------
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_lbl = QLabel(f"Ghostline v{__version__} — About & Support")
        title_lbl.setObjectName("supportCardTitle")
        title_lbl.setStyleSheet(f"background: transparent; font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};")
        header_layout.addWidget(title_lbl)

        desc_lbl = QLabel("Ghostline is free, open source, and built by one developer. Supporting it is entirely optional.")
        desc_lbl.setObjectName("supportCardDesc")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        header_layout.addWidget(desc_lbl)
        card_layout.addLayout(header_layout)

        # Divider
        div1 = QFrame()
        div1.setFixedHeight(1)
        div1.setStyleSheet(f"background-color: {STROKE_CARD}; border: none;")
        card_layout.addWidget(div1)

        # -------------------------------------------------------------
        # 2. Block A: Star on GitHub
        # -------------------------------------------------------------
        star_block = QHBoxLayout()
        star_block.setSpacing(16)

        star_text_layout = QVBoxLayout()
        star_text_layout.setSpacing(2)
        star_t = QLabel("Star Ghostline on GitHub")
        star_t.setObjectName("starTitle")
        star_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
        star_d = QLabel("A star helps other people find the project and supports continued open-source development.")
        star_d.setObjectName("starDesc")
        star_d.setWordWrap(True)
        star_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
        star_text_layout.addWidget(star_t)
        star_text_layout.addWidget(star_d)
        star_block.addLayout(star_text_layout, 1)

        self.btn_star_github = QPushButton("Star on GitHub")
        self.btn_star_github.setObjectName("starOnGithubButton")
        self.btn_star_github.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_star_github.setIcon(get_fluent_icon("star", color="#FFFFFF", size=15, filled=True))
        self.btn_star_github.setFixedHeight(34)
        self.btn_star_github.setStyleSheet(f"""
            QPushButton#starOnGithubButton {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                border: none;
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#starOnGithubButton:hover {{
                background-color: {BRAND_HOVER};
            }}
            QPushButton#starOnGithubButton:pressed {{
                background-color: {BRAND_PRESSED};
            }}
            QPushButton#starOnGithubButton:focus {{
                outline: 2px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_star_github.clicked.connect(self._open_repo_url)
        star_block.addWidget(self.btn_star_github)
        card_layout.addLayout(star_block)

        # -------------------------------------------------------------
        # 3. Block B: Buy Me a Coffee (Only if QR asset exists)
        # -------------------------------------------------------------
        self.has_qr_asset = bool(get_support_asset_path("Ghostline-support-qr.svg") or get_support_asset_path("Ghostline-support-qr.png"))

        if self.has_qr_asset:
            div2 = QFrame()
            div2.setFixedHeight(1)
            div2.setStyleSheet(f"background-color: {STROKE_CARD}; border: none;")
            card_layout.addWidget(div2)

            coffee_block = QVBoxLayout()
            coffee_block.setSpacing(12)

            coffee_header = QVBoxLayout()
            coffee_header.setSpacing(2)
            coffee_t = QLabel("Buy me a coffee")
            coffee_t.setObjectName("coffeeTitle")
            coffee_t.setStyleSheet(f"background: transparent; font-size: 13.5px; font-weight: 600; color: {TEXT_PRIMARY};")
            coffee_d = QLabel("Ghostline is built by one developer. Supporting it is entirely optional.")
            coffee_d.setObjectName("coffeeDesc")
            coffee_d.setWordWrap(True)
            coffee_d.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_SECONDARY};")
            coffee_header.addWidget(coffee_t)
            coffee_header.addWidget(coffee_d)
            coffee_block.addLayout(coffee_header)

            # QR Presentation Row: White Tile + Info & Actions
            qr_row = QHBoxLayout()
            qr_row.setSpacing(20)
            qr_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

            # Solid White Tile (Always Dark-on-Light, Crisp Quiet Zone)
            self.qr_tile = QFrame()
            self.qr_tile.setObjectName("supportQrTileFrame")
            self.qr_tile.setStyleSheet("""
                QFrame#supportQrTileFrame {
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    border: 1px solid #E0E0E0;
                }
            """)
            qr_tile_layout = QVBoxLayout(self.qr_tile)
            qr_tile_layout.setContentsMargins(10, 10, 10, 10)
            qr_tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.lbl_support_qr = QLabel()
            self.lbl_support_qr.setObjectName("supportQrLabel")
            self.lbl_support_qr.setAccessibleName("QR code to support Ghostline")
            self.lbl_support_qr.setFixedSize(200, 200)
            self.lbl_support_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_support_qr.setStyleSheet("background-color: #FFFFFF; border: none;")

            self._update_qr_pixmap()
            qr_tile_layout.addWidget(self.lbl_support_qr)
            qr_row.addWidget(self.qr_tile)

            # Next to QR: Instructions, Notes & Action Buttons
            qr_side = QVBoxLayout()
            qr_side.setSpacing(10)
            qr_side.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            note_scan = QLabel("Scan with any UPI app (Google Pay, PhonePe, Paytm, BHIM, or your bank app).")
            note_scan.setObjectName("qrScanNote")
            note_scan.setWordWrap(True)
            note_scan.setStyleSheet(f"background: transparent; font-size: 12.5px; color: {TEXT_PRIMARY}; font-weight: 500;")
            qr_side.addWidget(note_scan)

            self.lbl_note_bank = QLabel("Scanning shows the payee name from my bank account.")
            self.lbl_note_bank.setObjectName("qrBankNote")
            self.lbl_note_bank.setWordWrap(True)
            self.lbl_note_bank.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY};")
            qr_side.addWidget(self.lbl_note_bank)

            self.lbl_note_fraud = QLabel("Only pay through this app or the official GitHub repository.")
            self.lbl_note_fraud.setObjectName("qrFraudNote")
            self.lbl_note_fraud.setWordWrap(True)
            self.lbl_note_fraud.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_TERTIARY};")
            qr_side.addWidget(self.lbl_note_fraud)

            # Actions Row
            qr_btn_row = QHBoxLayout()
            qr_btn_row.setSpacing(10)

            self.btn_show_larger = QPushButton("Show larger")
            self.btn_show_larger.setObjectName("showQrLargerButton")
            self.btn_show_larger.setIcon(get_fluent_icon("open", color=TEXT_PRIMARY, size=14))
            self.btn_show_larger.setFixedHeight(32)
            self.btn_show_larger.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_show_larger.setStyleSheet(f"""
                QPushButton#showQrLargerButton {{
                    background-color: {SURFACE_INPUT};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {STROKE_CONTROL};
                    border-radius: {RADIUS_CONTROL}px;
                    padding: 0 14px;
                    font-size: 12.5px;
                    font-weight: 500;
                }}
                QPushButton#showQrLargerButton:hover {{
                    background-color: {OVERLAY_HOVER};
                    border-color: {TEXT_PRIMARY};
                }}
                QPushButton#showQrLargerButton:focus {{
                    outline: 2px solid {STROKE_FOCUS_OUTER};
                }}
            """)
            self.btn_show_larger.clicked.connect(self._show_larger_clicked)
            qr_btn_row.addWidget(self.btn_show_larger)

            self.btn_save_qr = QPushButton("Save QR image")
            self.btn_save_qr.setObjectName("saveQrButton")
            self.btn_save_qr.setIcon(get_fluent_icon("copy", color=TEXT_PRIMARY, size=14))
            self.btn_save_qr.setFixedHeight(32)
            self.btn_save_qr.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_save_qr.setStyleSheet(f"""
                QPushButton#saveQrButton {{
                    background-color: {SURFACE_INPUT};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {STROKE_CONTROL};
                    border-radius: {RADIUS_CONTROL}px;
                    padding: 0 14px;
                    font-size: 12.5px;
                    font-weight: 500;
                }}
                QPushButton#saveQrButton:hover {{
                    background-color: {OVERLAY_HOVER};
                    border-color: {TEXT_PRIMARY};
                }}
                QPushButton#saveQrButton:focus {{
                    outline: 2px solid {STROKE_FOCUS_OUTER};
                }}
            """)
            self.btn_save_qr.clicked.connect(self._save_qr_clicked)
            qr_btn_row.addWidget(self.btn_save_qr)
            qr_btn_row.addStretch(1)

            qr_side.addLayout(qr_btn_row)
            qr_row.addLayout(qr_side, 1)
            coffee_block.addLayout(qr_row)

            card_layout.addLayout(coffee_block)
        else:
            self.lbl_support_qr = None
            self.btn_show_larger = None
            self.btn_save_qr = None

        # -------------------------------------------------------------
        # 4. Subtle Links Row: Report a bug, Suggest feature, Copy link
        # -------------------------------------------------------------
        div3 = QFrame()
        div3.setFixedHeight(1)
        div3.setStyleSheet(f"background-color: {STROKE_CARD}; border: none;")
        card_layout.addWidget(div3)

        links_row = QHBoxLayout()
        links_row.setSpacing(16)

        self.btn_report_bug = QPushButton("Report a bug")
        self.btn_report_bug.setObjectName("reportBugButton")
        self.btn_report_bug.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_report_bug.setIcon(get_fluent_icon("open", color=BRAND_TEXT, size=13))
        self.btn_report_bug.setStyleSheet(f"""
            QPushButton#reportBugButton {{
                background: transparent;
                color: {BRAND_TEXT};
                border: none;
                font-size: 12.5px;
                font-weight: 500;
                padding: 4px 6px;
                border-radius: 4px;
            }}
            QPushButton#reportBugButton:hover {{
                text-decoration: underline;
                background-color: {OVERLAY_HOVER};
            }}
            QPushButton#reportBugButton:focus {{
                outline: 1px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_report_bug.clicked.connect(self._open_issues_url)
        links_row.addWidget(self.btn_report_bug)

        self.btn_suggest_feature = QPushButton("Suggest a feature")
        self.btn_suggest_feature.setObjectName("suggestFeatureButton")
        self.btn_suggest_feature.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_suggest_feature.setIcon(get_fluent_icon("sparkle", color=BRAND_TEXT, size=13))
        self.btn_suggest_feature.setStyleSheet(f"""
            QPushButton#suggestFeatureButton {{
                background: transparent;
                color: {BRAND_TEXT};
                border: none;
                font-size: 12.5px;
                font-weight: 500;
                padding: 4px 6px;
                border-radius: 4px;
            }}
            QPushButton#suggestFeatureButton:hover {{
                text-decoration: underline;
                background-color: {OVERLAY_HOVER};
            }}
            QPushButton#suggestFeatureButton:focus {{
                outline: 1px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_suggest_feature.clicked.connect(self._open_issues_url)
        links_row.addWidget(self.btn_suggest_feature)

        self.btn_copy_repo_link = QPushButton("Copy repo link")
        self.btn_copy_repo_link.setObjectName("copyRepoLinkButton")
        self.btn_copy_repo_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_repo_link.setIcon(get_fluent_icon("copy", color=BRAND_TEXT, size=13))
        self.btn_copy_repo_link.setStyleSheet(f"""
            QPushButton#copyRepoLinkButton {{
                background: transparent;
                color: {BRAND_TEXT};
                border: none;
                font-size: 12.5px;
                font-weight: 500;
                padding: 4px 6px;
                border-radius: 4px;
            }}
            QPushButton#copyRepoLinkButton:hover {{
                text-decoration: underline;
                background-color: {OVERLAY_HOVER};
            }}
            QPushButton#copyRepoLinkButton:focus {{
                outline: 1px solid {STROKE_FOCUS_OUTER};
            }}
        """)
        self.btn_copy_repo_link.clicked.connect(self._copy_repo_link_clicked)
        links_row.addWidget(self.btn_copy_repo_link)

        links_row.addStretch(1)
        card_layout.addLayout(links_row)

    def _update_qr_pixmap(self):
        if not self.lbl_support_qr:
            return
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        pm = render_qr_pixmap(200, dpr)
        if not pm.isNull():
            self.lbl_support_qr.setPixmap(pm)

    def _open_repo_url(self):
        QDesktopServices.openUrl(QUrl(self.repo_url))

    def _open_issues_url(self):
        QDesktopServices.openUrl(QUrl(self.issues_url))

    def _copy_repo_link_clicked(self):
        cb = QGuiApplication.clipboard()
        if cb:
            cb.setText(self.repo_url)
            orig_text = self.btn_copy_repo_link.text()
            self.btn_copy_repo_link.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.btn_copy_repo_link.setText(orig_text))

    def _show_larger_clicked(self):
        dlg = QtSupportQrDialog(self, repo_url=self.repo_url)
        dlg.exec()

    def _save_qr_clicked(self):
        png_src = get_support_asset_path("Ghostline-support-qr.png")
        if not png_src or not png_src.exists():
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Support QR",
            "Ghostline-support-qr.png",
            "PNG Image (*.png)"
        )
        if dest:
            shutil.copyfile(str(png_src), dest)
