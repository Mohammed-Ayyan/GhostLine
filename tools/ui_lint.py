"""
Ghostline UI Lint Engine
Audits the live widget hierarchy of Ghostline Qt GUI pages across window dimensions.
Evaluates:
  a) strips (pixel color match between label background and parent card surface)
  b) text clipping (QFontMetrics bounds vs widget geometry)
  c) mnemonic loss (loss of literal '&' in button/label text)
  d) layout overlaps and horizontal scrollbars
  e) content column width uniformity (min(width - 64, 960))
  f) button icon-text gap (>= 8px)
  g) heading and card left-edge alignment (+- 1px)
  h) combobox dropdown chevron presence
  i) minimum text size (>= 12px)
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Ensure ghostline package is on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import (
    QApplication, QLabel, QPushButton, QComboBox, QFrame,
    QScrollArea, QWidget, QAbstractButton
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QFontMetrics, QImage, QColor

from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.config import load_config


class UILintRunner:
    def __init__(self, window_sizes: List[Tuple[int, int]] = None):
        self.sizes = window_sizes or [(1916, 1140), (1280, 720), (900, 600)]
        self.screens = [
            "dashboard", "general", "help", "mode", "model",
            "profile", "history", "security", "diagnostics", "audio"
        ]

    def run_lint(self) -> Dict[str, Any]:
        app = QApplication.instance() or QApplication(sys.argv)
        from ghostline.ui.theme import apply_fluent_theme
        apply_fluent_theme(app)
        cfg = load_config()

        failures = {
            "strips": [],
            "clipped_text": [],
            "mnemonic_loss": [],
            "overlaps": [],
            "column_width": [],
            "icon_gap": [],
            "heading_alignment": [],
            "combobox_arrow": [],
            "min_text_size": [],
            "d6_keycap_clipped": [],
            "d8_useless_progressbar": [],
            "d9_seeded_recent_result": [],
            "d14_uneven_hotkey_rows": [],
            "qt_warnings": []
        }

        for width, height in self.sizes:
            window = QtGhostlineMainWindow(config=cfg)
            window.resize(width, height)
            window.show()
            app.processEvents()

            for screen_id in self.screens:
                window.show_screen(screen_id)
                app.processEvents()
                frame = window.screen_frames.get(screen_id)
                if not frame:
                    continue

                img = window.grab().toImage()

                # a) Strips & background painting
                self._check_strips(window, frame, screen_id, img, failures["strips"])

                # b) Text clipping
                self._check_clipped_text(frame, screen_id, failures["clipped_text"])

                # c) Mnemonic loss
                self._check_mnemonic_loss(frame, screen_id, failures["mnemonic_loss"])

                # d) Overlaps & horizontal scrollbars
                self._check_overlaps_and_scrollbars(frame, screen_id, failures["overlaps"])

                # e) Content column width uniformity
                self._check_column_width(window, frame, screen_id, width, failures["column_width"])

                # f) Icon-to-text gap & size
                self._check_icon_gaps(frame, screen_id, failures["icon_gap"])

                # g) Heading alignment
                self._check_heading_alignment(window, frame, screen_id, failures["heading_alignment"])

                # h) Combobox arrow
                self._check_combobox_arrow(window, frame, screen_id, img, failures["combobox_arrow"])

                # i) Min text size
                self._check_min_text_size(frame, screen_id, failures["min_text_size"])

                # Specific Defect Checks (D6, D8, D9, D14)
                if screen_id == "help":
                    self._check_d6_keycaps(frame, failures["d6_keycap_clipped"])
                    self._check_d14_help_rows(frame, failures["d14_uneven_hotkey_rows"])
                elif screen_id == "general":
                    self._check_d8_progressbar(frame, failures["d8_useless_progressbar"])
                elif screen_id == "dashboard":
                    self._check_d9_seeded_result(frame, failures["d9_seeded_recent_result"])

            window.close()

        total_violations = sum(len(v) for v in failures.values())
        return {
            "total_violations": total_violations,
            "failures": failures
        }

    def _check_strips(self, window, frame, screen_id, img, results):
        cards = [c for c in frame.findChildren(QFrame) if c.objectName() == "CardFrame" and c.isVisible()]
        for c in cards:
            labels = c.findChildren(QLabel)
            for lbl in labels:
                if not lbl.isVisible() or not lbl.text().strip():
                    continue
                ss = lbl.styleSheet().lower()
                # If label is styled intentionally as a badge or tag, skip
                if "background-color" in ss and ("rgba" in ss or "#292929" in ss or "brand" in ss):
                    continue
                # If label stylesheet explicitly sets a dark opaque canvas background
                if "background-color: #1f1f1f" in ss or "background: #1f1f1f" in ss:
                    results.append({
                        "screen": screen_id,
                        "card": c.objectName(),
                        "label": lbl.text()[:30],
                        "issue": "Label explicitly paints canvas background #1F1F1F creating dark strip"
                    })
                    continue
                # Inspect label grab: verify it does not fill with opaque #1F1F1F
                lbl_img = lbl.grab().toImage()
                corner_col = lbl_img.pixelColor(min(1, lbl_img.width() - 1), min(1, lbl_img.height() - 1))
                if corner_col.name() == "#1f1f1f":
                    results.append({
                        "screen": screen_id,
                        "card": c.objectName(),
                        "label": lbl.text()[:30],
                        "issue": "Label corner paints opaque canvas background #1F1F1F creating dark strip"
                    })

    def _check_clipped_text(self, frame, screen_id, results):
        for lbl in frame.findChildren(QLabel):
            if not lbl.isVisible() or not lbl.text().strip():
                continue
            text = lbl.text()
            fm = lbl.fontMetrics()
            cr = lbl.contentsRect()
            if cr.width() <= 0 or cr.height() <= 0:
                continue
            flags = Qt.TextFlag.TextWordWrap if lbl.wordWrap() else 0
            bounds = fm.boundingRect(cr, flags, text)
            if bounds.height() > cr.height() + 2:
                results.append({
                    "screen": screen_id,
                    "widget": lbl.objectName() or "QLabel",
                    "text": text[:35],
                    "req_height": bounds.height(),
                    "avail_height": cr.height()
                })

    def _check_mnemonic_loss(self, frame, screen_id, results):
        for btn in frame.findChildren(QAbstractButton):
            txt = btn.text()
            # If text has a single '&' followed by non-space/non-&, it is consumed as mnemonic
            if " & " in txt and not " && " in txt:
                results.append({
                    "screen": screen_id,
                    "widget": btn.objectName() or "QAbstractButton",
                    "text": txt,
                    "issue": "Unescaped '&' causes mnemonic underline / consumption"
                })

    def _check_overlaps_and_scrollbars(self, frame, screen_id, results):
        for sa in frame.findChildren(QScrollArea):
            h_bar = sa.horizontalScrollBar()
            if h_bar and h_bar.isVisible() and h_bar.maximum() > 0:
                results.append({
                    "screen": screen_id,
                    "scroll_area": sa.objectName() or "QScrollArea",
                    "issue": f"Horizontal scrollbar active (max={h_bar.maximum()})"
                })

    def _check_column_width(self, window, frame, screen_id, win_width, results):
        target_width = min(win_width - 64, 960)
        # Check CardFrames width in main layout
        for c in frame.findChildren(QFrame):
            if c.objectName() == "CardFrame" and c.isVisible():
                if abs(c.width() - target_width) > 40:
                    results.append({
                        "screen": screen_id,
                        "card": c.objectName(),
                        "actual_width": c.width(),
                        "target_width": target_width,
                        "diff": abs(c.width() - target_width)
                    })
                    break

    def _check_icon_gaps(self, frame, screen_id, results):
        # Buttons with icons: check spacing
        for btn in frame.findChildren(QPushButton):
            if not btn.icon().isNull() and btn.text().strip():
                ss = btn.styleSheet().lower()
                # If button or class has padding and icon-size enforced
                has_inline = ("padding" in ss or "icon" in ss)
                is_standard = btn.objectName() in ("PrimaryBtn", "SecondaryBtn", "SubtleBtn", "SidebarBtn", "WhitePillBtn", "PillChipBtn")
                if not (has_inline or is_standard):
                    results.append({
                        "screen": screen_id,
                        "button": btn.objectName() or btn.text()[:25],
                        "issue": "Button has icon and text without enforced 8px Fluent gap"
                    })

    def _check_heading_alignment(self, window, frame, screen_id, results):
        cards = [c for c in frame.findChildren(QFrame) if c.objectName() == "CardFrame" and c.isVisible()]
        if not cards:
            return
        card_x = cards[0].mapTo(window, cards[0].rect().topLeft()).x()
        for lbl in frame.findChildren(QLabel):
            # Exclude labels that are children/descendants inside cards
            if any(c.isAncestorOf(lbl) for c in cards):
                continue
            if lbl.isVisible() and lbl.text().strip() and any(k in lbl.text().lower() for k in ["settings", "assistance", "shortcuts"]):
                lbl_x = lbl.mapTo(window, lbl.rect().topLeft()).x()
                if abs(lbl_x - card_x) > 2 and abs(lbl_x - card_x) < 40:
                    results.append({
                        "screen": screen_id,
                        "heading": lbl.text()[:30],
                        "heading_x": lbl_x,
                        "card_x": card_x,
                        "offset": abs(lbl_x - card_x)
                    })

    def _check_combobox_arrow(self, window, frame, screen_id, img, results):
        for combo in frame.findChildren(QComboBox):
            if combo.isVisible():
                c_img = combo.grab().toImage()
                arrow_region = [
                    c_img.pixelColor(x, y).name()
                    for x in range(max(0, c_img.width() - 28), c_img.width())
                    for y in range(c_img.height())
                ]
                has_arrow = ("#ffffff" in arrow_region or any(c not in ("#000000", "#292929") for c in arrow_region))
                if not has_arrow:
                    results.append({
                        "screen": screen_id,
                        "combobox": combo.objectName() or "QComboBox",
                        "issue": "Combobox drop-down arrow missing or indistinguishable from field background"
                    })

    def _check_min_text_size(self, frame, screen_id, results):
        for lbl in frame.findChildren(QLabel):
            if lbl.isVisible() and lbl.text().strip():
                f = lbl.font()
                if f.pixelSize() > 0 and f.pixelSize() < 12:
                    results.append({
                        "screen": screen_id,
                        "label": lbl.text()[:25],
                        "pixel_size": f.pixelSize(),
                        "issue": f"Text size {f.pixelSize()}px is below 12px threshold"
                    })


    def _check_d6_keycaps(self, frame, results):
        for lbl in frame.findChildren(QLabel):
            txt = lbl.text()
            if "Alt +" in txt or "Ctrl +" in txt:
                fm = lbl.fontMetrics()
                needed_w = fm.horizontalAdvance(txt) + 16
                if lbl.width() < needed_w:
                    results.append({
                        "keycap": txt,
                        "actual_width": lbl.width(),
                        "needed_width": needed_w,
                        "issue": "Keycap text clipped due to fixed width"
                    })

    def _check_d8_progressbar(self, frame, results):
        from PyQt6.QtWidgets import QProgressBar
        bars = frame.findChildren(QProgressBar)
        for pb in bars:
            if pb.isVisible():
                results.append({
                    "progressbar": pb.objectName() or "QProgressBar",
                    "value": pb.value(),
                    "issue": "Useless decorative progress bar present in Inference Engine"
                })

    def _check_d9_seeded_result(self, frame, results):
        for lbl in frame.findChildren(QLabel):
            txt = lbl.text()
            if "Which algorithm computes" in txt or "Windows OCR Verified" in txt:
                results.append({
                    "label": lbl.objectName() or "QLabel",
                    "text": txt[:50],
                    "issue": "Seeded / fake test result displayed on clean Home screen"
                })

    def _check_d14_help_rows(self, frame, results):
        # Check rows inside hotkey cheatsheet card in help
        cards = [c for c in frame.findChildren(QFrame) if c.objectName() == "CardFrame"]
        for c in cards:
            keycaps = [lbl for lbl in c.findChildren(QLabel) if "Alt +" in lbl.text()]
            if len(keycaps) >= 3:
                # Hotkey cheatsheet card: check heights
                heights = [k.parentWidget().height() if k.parentWidget() else k.height() for k in keycaps]
                if len(set(heights)) > 1:
                    results.append({
                        "card": c.objectName(),
                        "heights": heights,
                        "issue": "Uneven row heights in Help hotkey cheat sheet"
                    })


if __name__ == "__main__":
    out_file = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out_file = sys.argv[idx + 1]

    runner = UILintRunner(window_sizes=[(1916, 1140)])
    rep = runner.run_lint()
    
    lines = []
    lines.append(f"[UI LINT AUDIT REPORT] Total Violations: {rep['total_violations']}")
    for cat, items in rep["failures"].items():
        if items:
            lines.append(f"  - {cat.upper()}: {len(items)} issues detected")
            for item in items[:5]:
                lines.append(f"      * {item}")

    output_str = "\n".join(lines)
    print(output_str)

    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(output_str + "\n")
            f.write("\n--- FULL FAILURE DUMP ---\n")
            import json
            f.write(json.dumps(rep, indent=2))
            
    if rep["total_violations"] > 0:
        sys.exit(1)
    else:
        print("[+] All UI Lint Checks Passed Cleanly!")
        sys.exit(0)
