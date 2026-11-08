import os
import sys

print("--- Testing Qt Font Availability ---")
# 1. Default offscreen
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QImage, QPainter, QColor, QFont
from PyQt6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)
fams = QFontDatabase.families()
print(f"QFontDatabase.families() count under raw offscreen: {len(fams)}")

# Let's see if Segoe UI or Arial exist in C:\Windows\Fonts
win_fonts = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf"
]
for wf in win_fonts:
    if os.path.exists(wf):
        font_id = QFontDatabase.addApplicationFont(wf)
        print(f"Loaded {wf} -> font_id={font_id}")

fams_after = QFontDatabase.families()
print(f"QFontDatabase.families() count after addApplicationFont: {len(fams_after)} -> {fams_after}")

# Now render a test image with QPainter
img = QImage(800, 200, QImage.Format.Format_ARGB32)
img.fill(QColor("#000000"))
p = QPainter(img)
p.setPen(QColor("#ffffff"))
test_font = QFont("Segoe UI", 32)
p.setFont(test_font)
p.drawText(50, 100, "Ghostline High Efficiency Local OCR Engine")
p.end()
img.save("reports/run11/test_segoe_render.png")

# Now OCR it
import subprocess, json
proc = subprocess.run(["bin/win_ocr.exe", "reports/run11/test_segoe_render.png"], capture_output=True, text=True)
if proc.returncode == 0:
    data = json.loads(proc.stdout)
    print("OCR Result on rendered text:", data.get("text"))
else:
    print("OCR Error:", proc.stderr)

