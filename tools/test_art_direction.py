"""
Test Art Direction for Ghostline Launch Videos.
Renders sample frames for Landscape and Portrait formats matching the Brag creative direction.
"""

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, QRect

root_dir = Path(__file__).resolve().parent.parent

app = QApplication.instance() or QApplication(sys.argv)

def render_sample_landscape_intro():
    img = QImage(1920, 1080, QImage.Format.Format_RGB32)
    img.fill(QColor("#080a0f"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Left accent bar (International Orange)
    p.fillRect(0, 0, 16, 1080, QColor("#FF4D00"))
    
    # Top technical tag
    p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
    p.setPen(QColor("#FF4D00"))
    p.drawText(100, 120, "[ GHOSTLINE // SYSTEM RELEASE v1.0.0 ]")
    
    p.setPen(QColor("#64748b"))
    p.drawText(1920 - 420, 120, "LATENCY: 42ms  //  100% OFFLINE")
    
    # Thin divider rule
    p.setPen(QPen(QColor("#1e293b"), 1.5))
    p.drawLine(100, 145, 1820, 145)
    
    # Bold Oversized Editorial Typography
    p.setFont(QFont("Segoe UI Black", 74))
    p.setPen(QColor("#ffffff"))
    p.drawText(100, 310, "YOUR SCREEN.")
    
    p.setPen(QColor("#FF4D00"))
    p.drawText(100, 420, "YOUR CONTEXT.")
    
    p.setPen(QColor("#ffffff"))
    p.drawText(100, 530, "YOUR LOCAL AI.")
    
    # Subhead
    p.setFont(QFont("Segoe UI", 22))
    p.setPen(QColor("#94a3b8"))
    p.drawText(100, 620, "Zero-latency exam assistance, screen context extraction, and live call intelligence.")
    
    # Technical Badges
    badges = [
        "GLOBAL HOTKEY: ALT + /",
        "NATIVE WINDOWS OCR",
        "STEALTH TRAY NOTIFICATIONS",
        "WASAPI SYSTEM LOOPBACK"
    ]
    bx = 100
    by = 720
    for b in badges:
        p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        bw = 240
        p.fillRect(QRect(bx, by, bw, 42), QColor("#111827"))
        p.setPen(QPen(QColor("#FF4D00"), 1.2))
        p.drawRect(QRect(bx, by, bw, 42))
        p.setPen(QColor("#f8fafc"))
        p.drawText(QRect(bx, by, bw, 42), Qt.AlignmentFlag.AlignCenter, b)
        bx += bw + 20
        
    p.end()
    img.save(str(root_dir / "recordings" / "test_landscape_intro.png"))
    print("[+] Saved test_landscape_intro.png")

def render_sample_portrait_frame():
    img = QImage(1080, 1920, QImage.Format.Format_RGB32)
    img.fill(QColor("#080a0f"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Top border accent
    p.fillRect(0, 0, 1080, 12, QColor("#FF4D00"))
    
    # Upper Section: Real product frame placeholder
    p.fillRect(40, 60, 1000, 1140, QColor("#111827"))
    p.setPen(QPen(QColor("#1e293b"), 2))
    p.drawRoundedRect(40, 60, 1000, 1140, 12, 12)
    
    p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
    p.setPen(QColor("#FF4D00"))
    p.drawText(60, 100, "[ REAL WINDOWS DESKTOP // QUESTION SCAN ]")
    
    # Lower Section: Brag Editorial Typographic Block
    lower_rect = QRect(40, 1240, 1000, 620)
    p.fillRect(lower_rect, QColor("#0e131f"))
    p.setPen(QPen(QColor("#FF4D00"), 2))
    p.drawRoundedRect(lower_rect, 16, 16)
    
    # Tag
    p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
    p.setPen(QColor("#FF4D00"))
    p.drawText(80, 1310, "// 01. INSTANT OCR PARSE")
    
    # Oversized Headline
    p.setFont(QFont("Segoe UI Black", 46))
    p.setPen(QColor("#ffffff"))
    p.drawText(80, 1400, "HIT ALT + /.")
    p.setPen(QColor("#FF4D00"))
    p.drawText(80, 1470, "INSTANT HUD SOLVE.")
    
    # Editorial Caption
    p.setFont(QFont("Segoe UI", 20))
    p.setPen(QColor("#cbd5e1"))
    p.drawText(QRect(80, 1510, 920, 120), Qt.TextFlag.TextWordWrap, 
               "Ghostline scans the question on your screen, parses options with local OCR, and reveals Option B in milliseconds.")
    
    # Telemetry Bar
    p.fillRect(QRect(80, 1720, 920, 60), QColor("#080a0f"))
    p.setPen(QPen(QColor("#1e293b"), 1))
    p.drawRect(QRect(80, 1720, 920, 60))
    
    p.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
    p.setPen(QColor("#22c55e"))
    p.drawText(100, 1756, "● OPTION B VERIFIED")
    p.setPen(QColor("#94a3b8"))
    p.drawText(500, 1756, "LATENCY: 42ms")
    p.drawText(750, 1756, "OCR: LOCAL NATIVE")
    
    p.end()
    img.save(str(root_dir / "recordings" / "test_portrait_frame.png"))
    print("[+] Saved test_portrait_frame.png")

if __name__ == "__main__":
    render_sample_landscape_intro()
    render_sample_portrait_frame()
