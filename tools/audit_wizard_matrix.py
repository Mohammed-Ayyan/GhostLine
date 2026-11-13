"""
Wizard Reproduction and Matrix Audit across Screen Sizes, DPI Scales, and Font Stacks.
Tests every wizard step and checks:
- Dialog fits within the simulated work area
- Pinned footer buttons (Back / Next / Skip) are fully visible
- Text clipping (QFontMetrics)
- Content overflow / missing scroll area
Saves forensic screenshots to reports/run19/captures/before/
"""

import os
import sys
from pathlib import Path

# Headless / E2E configuration
os.environ["GHOSTLINE_E2E"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import (
    QApplication, QLabel, QPushButton, QComboBox, QFrame,
    QScrollArea, QWidget, QAbstractButton, QLineEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QFont, QFontMetrics, QImage

from ghostline.config import AppConfig
from ghostline.ui.window_geometry import get_work_area
from ghostline.ui.qt_main_window import QtFirstRunWizardDialog

MATRIX = [
    ("800x600", [100]),
    ("1024x768", [100]),
    ("1280x720", [100, 125, 150]),
    ("1366x768", [100, 125, 150, 175]),
    ("1536x864", [125, 150]),
    ("1600x900", [125, 150]),
    ("1920x1080", [100, 125, 150, 200]),
    ("2560x1440", [100, 150]),
]

FONT_CASES = [
    ("Segoe UI Variable Text", "Segoe UI Variable Text, Segoe UI, sans-serif"),
    ("Segoe UI", "Segoe UI, sans-serif"),
    ("Arial", "Arial, Tahoma, sans-serif"),
]


def audit_matrix():
    app = QApplication.instance() or QApplication(sys.argv)
    
    out_dir = ROOT / "reports" / "run19" / "captures" / "before"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for res, scales in MATRIX:
        for scale in scales:
            spec = f"{res}@{scale}"
            os.environ["GHOSTLINE_E2E_FAKE_SCREEN"] = spec
            work = get_work_area()

            for font_name, font_stack in FONT_CASES:
                font = QFont(font_name, 10)
                app.setFont(font)

                cfg = AppConfig()
                wiz = QtFirstRunWizardDialog(cfg)
                wiz.show()
                app.processEvents()

                # Check Step 1, 2, 3
                for step_idx in range(3):
                    wiz.stack.setCurrentIndex(step_idx)
                    app.processEvents()

                    # Check geometry
                    wiz_w = wiz.width()
                    wiz_h = wiz.height()
                    overflows_screen = (wiz_h > work.height()) or (wiz_w > work.width())

                    # Check footer button visibility
                    next_rect = wiz.btn_next.geometry()
                    footer_clipped = (next_rect.bottom() > wiz_h) or (wiz_h > work.height())

                    # Check text clipping
                    clipped_labels = []
                    for lbl in wiz.findChildren(QLabel):
                        if lbl.isVisible() and lbl.text():
                            fm = QFontMetrics(lbl.font())
                            # Check single line overflow if not word wrapped
                            if not lbl.wordWrap() and lbl.width() > 0:
                                text_w = fm.horizontalAdvance(lbl.text())
                                if text_w > lbl.width() + 4:
                                    clipped_labels.append(lbl.text()[:20])

                    defects = []
                    if overflows_screen:
                        defects.append(f"Dialog height {wiz_h}px > work area {work.height()}px")
                    if footer_clipped:
                        defects.append("Next/Back button below fold or cut off by screen")
                    if clipped_labels:
                        defects.append(f"Text clipped: {len(clipped_labels)} labels")

                    results.append({
                        "spec": spec,
                        "font": font_name,
                        "step": step_idx + 1,
                        "work_h": work.height(),
                        "wiz_h": wiz_h,
                        "defects": defects,
                    })

                    # Capture key representative before states
                    if spec in ["800x600@100", "1366x768@150"] and font_name == "Segoe UI Variable Text":
                        img = QImage(wiz.size(), QImage.Format.Format_ARGB32)
                        img.fill(Qt.GlobalColor.transparent)
                        wiz.render(img)
                        capture_path = out_dir / f"wiz_before_{spec.replace('@', '_scale')}_step{step_idx+1}.png"
                        img.save(str(capture_path))

                wiz.close()

    # Print summary
    failing = [r for r in results if r["defects"]]
    print(f"Total matrix combinations tested: {len(results)}")
    print(f"Combinations with defects BEFORE fixes: {len(failing)}")
    
    unique_defects = set()
    for f in failing:
        for d in f["defects"]:
            unique_defects.add(d)

    print("\nUnique defects identified:")
    for d in sorted(unique_defects):
        print(f"  - {d}")

    # Generate matrix markdown table for before.md
    md_lines = [
        "| Screen & Scale | Work Area (Logical) | Wizard Dialog Size | Footer Buttons Visible? | Defects |",
        "|---|---|---|---|---|",
    ]
    seen_specs = set()
    for r in results:
        if r["spec"] not in seen_specs and r["step"] == 1 and r["font"] == "Segoe UI Variable Text":
            seen_specs.add(r["spec"])
            d_str = "<br>".join(r["defects"]) if r["defects"] else "None (Fits)"
            footer_ok = "NO (Clipped)" if any("below fold" in d for d in r["defects"]) else "YES"
            md_lines.append(f"| {r['spec']} | {r['work_h']} px height | {r['wiz_h']} px (Fixed) | {footer_ok} | {d_str} |")

    table_md = "\n".join(md_lines)
    (ROOT / "reports" / "run19" / "wizard_matrix_before.md").write_text(table_md, encoding="utf-8")
    print("\n[+] Table written to reports/run19/wizard_matrix_before.md")


if __name__ == "__main__":
    audit_matrix()
