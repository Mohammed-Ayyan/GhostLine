"""
Test label background transparency inside cards in Fluent 2 dark theme.
Verifies that QLabels inside cards do not render opaque dark/grey strips
and that their background matches the card surface color (#292929).
"""

import os
import sys
import pytest
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QFrame, QLabel

from ghostline.ui.theme.builder import build_fluent_stylesheet
from ghostline.ui.theme.tokens import SURFACE_CARD, SURFACE_CANVAS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_label_background_transparency_in_card(qapp):
    """Verify that a QLabel inside a card inherits the card background without opaque bounding box strips."""
    qapp.setStyleSheet(build_fluent_stylesheet())

    # Parent container simulating page canvas
    page = QWidget()
    page.setObjectName("PageContainer")
    page.setFixedSize(400, 300)
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(20, 20, 20, 20)

    # Card
    card = QFrame()
    card.setObjectName("CardFrame")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(24, 24, 24, 24)

    # Label inside card
    label = QLabel("Card Description Text Inside Label")
    label.setObjectName("CardDesc")
    card_layout.addWidget(label)
    page_layout.addWidget(card)

    page.show()
    qapp.processEvents()

    # Grab pixel image
    pixmap = card.grab()
    image = pixmap.toImage()

    # Sample pixel inside the card padding (away from text and border)
    # Card is 360 wide, 260 high. Point (10, 10) is inside card padding.
    pad_pixel = image.pixelColor(10, 10)
    
    # Sample pixel at the corner of the label area (e.g. label top-left area where there is no glyph)
    lbl_pos = label.pos()
    lbl_bg_pixel = image.pixelColor(lbl_pos.x() + 2, lbl_pos.y() + 2)

    # Both must match the Fluent 2 dark card surface (#292929)
    # SURFACE_CARD is "#292929" -> RGB(41, 41, 41)
    expected_color = QColor(SURFACE_CARD)

    assert (pad_pixel.red(), pad_pixel.green(), pad_pixel.blue()) == (
        expected_color.red(),
        expected_color.green(),
        expected_color.blue()
    ), f"Card padding color {pad_pixel.name()} did not match expected {SURFACE_CARD}"

    assert (lbl_bg_pixel.red(), lbl_bg_pixel.green(), lbl_bg_pixel.blue()) == (
        expected_color.red(),
        expected_color.green(),
        expected_color.blue()
    ), f"Label background color {lbl_bg_pixel.name()} did not match card surface {SURFACE_CARD}"

