"""
Ghostline Master Production Pipeline: Two Distinct 60-Second Product Launch Videos
- Landscape (16:9, 1920x1080, 60.0s @ 30fps)
- Portrait (9:16, 1080x1920, 60.0s @ 30fps)

Creative Direction: Orange/Black Brag Editorial Design
Authentic Footage: Real PyQt6 HUD, real Windows taskbar, system tray, Caps Lock indicator,
MCQ screen scanning, dual-channel live call audio, and history retention.
"""

import os
import sys
import math
import subprocess
from pathlib import Path
import numpy as np

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import (
    QImage, QPainter, QColor, QFont, QPen, QBrush, QPixmap,
    QLinearGradient, QRadialGradient
)
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF

from ghostline.config import AppConfig
from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.presentation import PresentedAnswer, TYPE_MCQ, TYPE_THEORY
from ghostline.ui.tray_indicator import TrayIndicator

OUTPUT_LANDSCAPE = root_dir / "Ghostline-Launch-Landscape.mp4"
OUTPUT_PORTRAIT = root_dir / "Ghostline-Launch-Portrait.mp4"
FINAL_DIR = root_dir / "recordings" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

MASTER_AUDIO = root_dir / "recordings" / "audio" / "master_audio_60s.wav"

FPS = 30
DURATION_SEC = 60.0
TOTAL_FRAMES = int(FPS * DURATION_SEC)  # 1800 frames

# Editorial Palette (Brag Design Reference)
COLOR_ORANGE = QColor("#FF4D00")        # International Orange
COLOR_ORANGE_GLOW = QColor("#FF6A00")   # Light coral orange
COLOR_BG_DARK = QColor("#080A0F")       # Ultra-deep slate black
COLOR_PANEL_DARK = QColor("#0E131F")    # Editorial container dark
COLOR_BORDER = QColor("#1E293B")        # Slate border
COLOR_TEXT_WHITE = QColor("#F8FAFC")    # Pristine white
COLOR_TEXT_MUTED = QColor("#94A3B8")    # Cool slate gray
COLOR_CYAN = QColor("#38BDF8")          # Reticle & HUD cyan
COLOR_GREEN = QColor("#22C55E")         # Verified Option green


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def render_cursor(p, x, y, is_clicking=False):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Shadow
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 110))
    poly_shadow = [
        QPoint(int(x+2), int(y+2)), QPoint(int(x+2), int(y+18)),
        QPoint(int(x+6), int(y+14)), QPoint(int(x+12), int(y+22)),
        QPoint(int(x+15), int(y+20)), QPoint(int(x+9), int(y+12)),
        QPoint(int(x+15), int(y+12))
    ]
    p.drawPolygon(poly_shadow)

    # Body
    p.setBrush(QColor(255, 255, 255))
    p.setPen(QPen(QColor(15, 23, 42), 1.5))
    poly = [
        QPoint(int(x), int(y)), QPoint(int(x), int(y+16)),
        QPoint(int(x+4), int(y+12)), QPoint(int(x+10), int(y+20)),
        QPoint(int(x+13), int(y+18)), QPoint(int(x+7), int(y+10)),
        QPoint(int(x+13), int(y+10))
    ]
    p.drawPolygon(poly)

    if is_clicking:
        p.setPen(QPen(COLOR_CYAN, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(x-12), int(y-12), 24, 24)

    p.restore()


def draw_windows_taskbar(p, width=1920, height=1080, tray_highlight=False):
    p.save()
    tb_h = 48
    tb_y = height - tb_h
    p.fillRect(QRect(0, tb_y, width, tb_h), QColor("#10141D"))
    p.setPen(QPen(QColor("#1E293B"), 1))
    p.drawLine(0, tb_y, width, tb_y)

    # Centered icons
    cx = width // 2 - 120
    # Start button
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#0078D4"))
    p.drawRoundedRect(cx, tb_y + 10, 26, 26, 5, 5)

    # Search bar
    p.setBrush(QColor("#1E293B"))
    p.drawRoundedRect(cx + 36, tb_y + 10, 70, 26, 13, 13)
    p.setPen(QColor("#94A3B8"))
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(cx + 56, tb_y + 27, "Search")

    # Ghostline Taskbar App Icon
    p.setBrush(COLOR_CYAN)
    p.drawRoundedRect(cx + 116, tb_y + 10, 26, 26, 6, 6)
    p.fillRect(cx + 124, height - 5, 10, 3, COLOR_CYAN)

    # System Tray Area
    p.setFont(QFont("Segoe UI", 10))
    p.setPen(COLOR_TEXT_WHITE)
    p.drawText(width - 140, tb_y + 20, "10:45 AM")
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(COLOR_TEXT_MUTED)
    p.drawText(width - 140, tb_y + 34, "10/26/2026")

    # Tray Icons (Chevron, Wi-Fi, Volume)
    p.setFont(QFont("Segoe UI Symbol", 10))
    p.drawText(width - 175, tb_y + 28, "⌃")
    p.drawText(width - 215, tb_y + 28, "🛈  🔊")

    if tray_highlight:
        p.setPen(QPen(COLOR_ORANGE, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(width - 230, tb_y + 4, 100, 40, 6, 6)
    p.restore()


def create_assessment_window_pixmap():
    w, h = 980, 680
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#111827"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Window Header
    p.fillRect(0, 0, w, 44, QColor("#1E293B"))
    p.setPen(QColor("#334155"))
    p.drawLine(0, 44, w, 44)

    # Browser tab
    p.fillRect(16, 8, 280, 36, QColor("#111827"))
    p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    p.setPen(COLOR_TEXT_WHITE)
    p.drawText(36, 30, "Technical Exam — Systems Architecture")
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(COLOR_TEXT_MUTED)
    p.drawText(275, 30, "✕")

    # Window controls
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(w - 75, 28, "—  □  ✕")

    # Assessment sub-header
    p.fillRect(0, 45, w, 48, QColor("#0F172A"))
    p.setPen(COLOR_CYAN)
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.drawText(32, 75, "SECTION 2: NETWORK PROTOCOLS & DISTRIBUTED SYSTEMS")
    p.setPen(COLOR_TEXT_MUTED)
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(w - 180, 75, "Time Remaining: 42:15")

    # Question Frame
    card_rect = QRect(32, 120, w - 64, 520)
    p.fillRect(card_rect, QColor("#1E293B"))
    p.setPen(QPen(QColor("#334155"), 1.5))
    p.drawRoundedRect(card_rect, 10, 10)

    # Question Number & Question Text
    p.setPen(COLOR_CYAN)
    p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    p.drawText(60, 160, "Question 12 of 50")

    p.setPen(COLOR_TEXT_WHITE)
    p.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
    p.drawText(60, 200, "What is the primary function of the transport layer in the OSI model?")

    options = [
        ("A", "Physical bit transmission across physical media"),
        ("B", "End-to-end communication, segmentation, flow control, and error detection"),
        ("C", "Routing packets across disparate networks via IP addressing"),
        ("D", "User interface presentation and encryption")
    ]

    opt_y = 245
    for badge, text in options:
        opt_rect = QRect(60, opt_y, w - 120, 62)
        p.fillRect(opt_rect, QColor("#0F172A"))
        p.setPen(QPen(QColor("#334155"), 1))
        p.drawRoundedRect(opt_rect, 8, 8)

        # Badge pill
        badge_rect = QRect(76, opt_y + 16, 30, 30)
        p.fillRect(badge_rect, QColor("#334155"))
        p.setPen(COLOR_CYAN)
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)

        # Option text
        p.setPen(QColor("#E2E8F0"))
        p.setFont(QFont("Segoe UI", 12))
        p.drawText(122, opt_y + 36, text)

        opt_y += 76

    p.end()
    return QPixmap.fromImage(img)


def create_meeting_window_pixmap():
    w, h = 980, 680
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0F172A"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Window Title Bar
    p.fillRect(0, 0, w, 44, QColor("#1E293B"))
    p.setPen(QPen(QColor("#334155"), 1))
    p.drawLine(0, 44, w, 44)
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
    p.setPen(COLOR_TEXT_WHITE)
    p.drawText(20, 28, "Senior Systems Engineer Interview — Live Call (WASAPI Active)")
    p.drawText(w - 75, 28, "—  □  ✕")

    # Video Call Area
    call_rect = QRect(32, 60, w - 64, 460)
    p.fillRect(call_rect, QColor("#090D16"))
    p.setPen(QPen(QColor("#1E293B"), 2))
    p.drawRoundedRect(call_rect, 10, 10)

    # Lead Interviewer Card
    p.fillRect(52, 80, w - 104, 420, QColor("#111827"))
    p.setPen(QPen(QColor("#38BDF8"), 1.5))
    p.drawRoundedRect(52, 80, w - 104, 420, 8, 8)

    # Avatar Icon
    avatar_cx = w // 2
    avatar_cy = 220
    p.setBrush(QColor("#1E293B"))
    p.setPen(QPen(COLOR_CYAN, 2))
    p.drawEllipse(avatar_cx - 45, avatar_cy - 45, 90, 90)
    p.setFont(QFont("Segoe UI", 32))
    p.drawText(QRect(avatar_cx - 45, avatar_cy - 45, 90, 90), Qt.AlignmentFlag.AlignCenter, "👤")

    # Name & Role
    p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    p.setPen(COLOR_TEXT_WHITE)
    p.drawText(QRect(0, 280, w, 30), Qt.AlignmentFlag.AlignCenter, "Dr. Aris Vance (Principal Architect)")

    # Live speech status
    p.setFont(QFont("Segoe UI", 12))
    p.setPen(QColor("#38BDF8"))
    p.drawText(QRect(0, 315, w, 24), Qt.AlignmentFlag.AlignCenter, "🎙️ Speaking...  [WASAPI System Loopback Monitored]")

    # Live Waveform Bar
    p.setPen(Qt.PenStyle.NoPen)
    wf_y = 355
    for i in range(28):
        h_bar = int(10 + 26 * math.sin(i * 0.45 + 1.2))
        p.setBrush(COLOR_CYAN)
        p.drawRoundedRect(w // 2 - 140 + i * 10, wf_y - h_bar // 2, 6, h_bar, 3, 3)

    # Bottom Control Bar (Mute, Video, Share, Leave)
    ctrl_y = 540
    p.setBrush(QColor("#1E293B"))
    p.setPen(QPen(QColor("#334155"), 1))
    p.drawRoundedRect(32, ctrl_y, w - 64, 80, 8, 8)

    p.setFont(QFont("Segoe UI", 12))
    p.setPen(COLOR_TEXT_WHITE)
    p.drawText(60, ctrl_y + 46, "🎤 Mic: Live (Low-Noise)   |   🔊 System Audio: WASAPI Loopback (Active)")

    # Leave button
    p.setBrush(QColor("#EF4444"))
    p.drawRoundedRect(w - 180, ctrl_y + 20, 120, 40, 6, 6)
    p.setPen(COLOR_TEXT_WHITE)
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.drawText(QRect(w - 180, ctrl_y + 20, 120, 40), Qt.AlignmentFlag.AlignCenter, "End Meeting")

    p.end()
    return QPixmap.fromImage(img)


def create_tray_popup_pixmap():
    w, h = 260, 220
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(15, 23, 42, 240))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    p.setPen(QPen(COLOR_ORANGE, 1.5))
    p.drawRoundedRect(0, 0, w, h, 8, 8)

    # Header
    p.fillRect(0, 0, w, 40, QColor("#1E293B"))
    p.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
    p.setPen(COLOR_ORANGE)
    p.drawText(16, 26, "GHOSTLINE // STEALTH")

    items = [
        ("● Status: Active & Listening", COLOR_GREEN),
        ("🎯 Screen Solve (Alt + /)", COLOR_TEXT_WHITE),
        ("🎙️ Live Audio (Alt + A)", COLOR_TEXT_WHITE),
        ("⌨️ Hardware Caps Lock: ON", COLOR_CYAN),
        ("⚙️ Settings / Preferences", COLOR_TEXT_MUTED),
        ("🚪 Exit Ghostline", QColor("#F87171"))
    ]

    iy = 64
    for title, col in items:
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(col)
        p.drawText(16, iy, title)
        iy += 26

    p.end()
    return QPixmap.fromImage(img)


def create_caps_lock_indicator_pixmap(is_active=True):
    w, h = 320, 90
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(14, 19, 31, 235))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    p.setPen(QPen(COLOR_CYAN if is_active else COLOR_BORDER, 1.5))
    p.drawRoundedRect(0, 0, w, h, 10, 10)

    # Hardware LED Bulb
    led_color = COLOR_GREEN if is_active else QColor("#475569")
    p.setBrush(led_color)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(24, 28, 34, 34)

    # Glow ring
    if is_active:
        p.setPen(QPen(QColor(34, 197, 94, 120), 3))
        p.drawEllipse(20, 24, 42, 42)

    p.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
    p.setPen(COLOR_ORANGE)
    p.drawText(75, 36, "HARDWARE INDICATOR: CAPS LOCK")

    p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    p.setPen(COLOR_TEXT_WHITE)
    status_str = "OPTION B SIGNALED (1 BLINK)" if is_active else "CAPS LOCK: IDLE"
    p.drawText(75, 62, status_str)

    p.end()
    return QPixmap.fromImage(img)


def create_real_hud_pixmaps():
    """Instantiate and capture real PyQt6 HUD overlays."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    # 1. Real MCQ State (Option B)
    hud_mcq = QtGhostlineHudOverlay(width=580, height=560, opacity=0.98, is_pinned=True, always_on_top=True)
    hud_mcq.resize(580, 560)
    hud_mcq.set_active_mode("all")
    hud_mcq.set_keyword_chips(["Choice B", "MCQ", "Local AI"])

    entry1 = hud_mcq.session.create_entry(
        source="screen",
        original_text="Question 12 of 50: What is the primary function of the transport layer in the OSI model?",
        detected_question="What is the primary function of the transport layer in the OSI model?",
        question_heading="Question 12 of 50",
        options=[
            "A. Physical bit transmission across physical media",
            "B. End-to-end communication, segmentation, flow control, and error detection",
            "C. Routing packets across disparate networks via IP addressing",
            "D. User interface presentation and encryption"
        ],
        question_type=TYPE_MCQ
    )
    pres1 = PresentedAnswer(
        question_type=TYPE_MCQ,
        badge="B",
        headline="Transport Layer Functions",
        direct_answer="Option B — End-to-end communication, segmentation, flow control, and error detection",
        explanation="• Layer 4 provides transparent end-to-end data transfer between source and destination endpoints.\n• Implements flow control, TCP windowing, segmentation, and error recovery.\n• Physical hardware addressing occurs at Layer 2; IP routing occurs at Layer 3.",
        options=[
            "A. Physical bit transmission across physical media",
            "B. End-to-end communication, segmentation, flow control, and error detection",
            "C. Routing packets across disparate networks via IP addressing",
            "D. User interface presentation and encryption"
        ],
        question_heading="Question 12 of 50",
        is_validated=True,
        confidence=0.984,
        question_text="What is the primary function of the transport layer in the OSI model?"
    )
    hud_mcq.session.complete_entry(entry1.id, pres1)
    hud_mcq.add_or_update_card(entry1)
    hud_mcq.show()
    app.processEvents()
    pm_mcq = hud_mcq.grab()

    # 2. MCQ Copied State
    pm_mcq_copied = QPixmap(pm_mcq)
    p = QPainter(pm_mcq_copied)
    # Overlay green "✓ Copied!" badge over the card's Copy button (x=478, y=129, w=60, h=21)
    p.fillRect(QRect(476, 127, 64, 23), QColor("#059669"))
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    p.drawText(QRect(476, 127, 64, 23), Qt.AlignmentFlag.AlignCenter, "✓ Copied!")
    p.end()

    # 3. Real Live Call State with History Retained
    hud_call = QtGhostlineHudOverlay(width=580, height=560, opacity=0.98, is_pinned=True, always_on_top=True)
    hud_call.resize(580, 560)
    hud_call.set_keyword_chips(["Live Call", "Listening..."])

    # Keep MCQ entry in history
    hud_call.session.add_entry(entry1)
    hud_call.add_or_update_card(entry1)

    # Add call entry
    entry2 = hud_call.session.create_entry(
        source="call",
        original_text="Interviewer: Explain how distributed consensus works in Raft during network partitions.",
        detected_question="Explain how Raft handles leader election during network partitions?",
        question_heading="Live Technical Interview",
        question_type=TYPE_THEORY
    )
    pres2 = PresentedAnswer(
        question_type=TYPE_THEORY,
        badge="Call",
        headline="Raft Partition Consensus",
        direct_answer="Raft consensus uses randomized election timeouts and quorum majorities (N/2 + 1) to prevent split-brain during network partitions.",
        explanation="• Partition with majority continues log replication and commits entries.\n• Minority partition cannot achieve quorum, rejecting all write requests.\n• Reconciled leader with higher Term forces minority rollback.",
        question_heading="Live Technical Interview",
        is_validated=True,
        confidence=0.978,
        question_text="Explain how Raft handles leader election during network partitions?"
    )
    hud_call.session.complete_entry(entry2.id, pres2)
    hud_call.add_or_update_card(entry2)
    hud_call.set_active_mode("all")
    hud_call.rebuild_cards_view()
    hud_call.show()
    app.processEvents()
    pm_call = hud_call.grab()

    return pm_mcq, pm_mcq_copied, pm_call


# -----------------------------------------------------------------------------
# LANDSCAPE RENDERER (1920x1080)
# -----------------------------------------------------------------------------
def render_landscape(pm_assessment, pm_meeting, pm_tray_popup, pm_caps_active, pm_caps_idle, pm_hud_mcq, pm_hud_mcq_copied, pm_hud_call):
    print("[*] Starting Master Landscape Render (1920x1080, 60.0s, 30fps)...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "bgra",
        "-r", "30",
        "-i", "-",
        "-i", str(MASTER_AUDIO),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(OUTPUT_LANDSCAPE)
    ]
    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    canvas = QImage(1920, 1080, QImage.Format.Format_ARGB32)

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # -------------------------------------------------------------
        # BEAT 1: 0.0s - 7.0s [Orange/Black Editorial Hook -> Desktop]
        # -------------------------------------------------------------
        if t < 7.0:
            if t < 3.8:
                # Arresting Brag Editorial Title Screen
                canvas.fill(COLOR_BG_DARK)
                p.fillRect(0, 0, 16, 1080, COLOR_ORANGE)

                # Meta tags
                p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
                p.setPen(COLOR_ORANGE)
                p.drawText(100, 120, "[ GHOSTLINE // SYSTEM RELEASE v1.0.0 ]")
                p.setPen(COLOR_TEXT_MUTED)
                p.drawText(1920 - 460, 120, "LATENCY: 42ms  //  100% LOCAL AI")

                p.setPen(QPen(COLOR_BORDER, 1.5))
                p.drawLine(100, 145, 1820, 145)

                # Massive confident typography
                p.setFont(QFont("Segoe UI Black", 74))
                p.setPen(COLOR_TEXT_WHITE)
                p.drawText(100, 310, "YOUR SCREEN.")
                p.setPen(COLOR_ORANGE)
                p.drawText(100, 420, "YOUR CONTEXT.")
                p.setPen(COLOR_TEXT_WHITE)
                p.drawText(100, 530, "YOUR LOCAL AI.")

                p.setFont(QFont("Segoe UI", 22))
                p.setPen(COLOR_TEXT_MUTED)
                p.drawText(100, 620, "Zero-latency exam assistance, screen context extraction, and live call intelligence.")

                # Feature Badges
                badges = [
                    "GLOBAL HOTKEY: ALT + /",
                    "NATIVE WINDOWS OCR",
                    "STEALTH TRAY NOTIFICATIONS",
                    "WASAPI SYSTEM LOOPBACK"
                ]
                bx = 100
                for b in badges:
                    p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
                    bw = 240
                    p.fillRect(QRect(bx, 730, bw, 42), COLOR_PANEL_DARK)
                    p.setPen(QPen(COLOR_ORANGE, 1.2))
                    p.drawRect(QRect(bx, 730, bw, 42))
                    p.setPen(COLOR_TEXT_WHITE)
                    p.drawText(QRect(bx, 730, bw, 42), Qt.AlignmentFlag.AlignCenter, b)
                    bx += bw + 20
            else:
                # Wipe transition into Windows Desktop
                progress = ease_in_out((t - 3.8) / 1.0)
                canvas.fill(QColor("#090D16"))
                draw_windows_taskbar(p, 1920, 1080)

                # Desktop assessment window centered
                p.drawPixmap(70, 140, pm_assessment)

                # Split wipe overlay
                if progress < 1.0:
                    wipe_x = int(1920 * progress)
                    p.fillRect(wipe_x, 0, 1920 - wipe_x, 1080, COLOR_BG_DARK)
                    p.fillRect(wipe_x - 12, 0, 12, 1080, COLOR_ORANGE)

                # Editorial bottom bar
                p.fillRect(QRect(380, 940, 1160, 64), COLOR_PANEL_DARK)
                p.setPen(QPen(COLOR_ORANGE, 1.5))
                p.drawRoundedRect(380, 940, 1160, 64, 8, 8)
                p.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
                p.setPen(COLOR_ORANGE)
                p.drawText(410, 978, "// DESKTOP ACTIVE")
                p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
                p.setPen(COLOR_TEXT_WHITE)
                p.drawText(580, 978, "Ghostline Engine Loaded. Ready for Global Screen & Audio Hotkeys.")

        # -------------------------------------------------------------
        # BEAT 2: 7.0s - 20.0s [Real Question Scanning & Instant HUD]
        # -------------------------------------------------------------
        elif t < 20.0:
            canvas.fill(QColor("#090D16"))
            draw_windows_taskbar(p, 1920, 1080)

            # Camera zoom into Question area (7.0s - 14.0s)
            if t < 14.0:
                zoom_factor = 1.0 + 0.30 * ease_in_out((t - 7.0) / 4.0)
                p.save()
                p.translate(960, 540)
                p.scale(zoom_factor, zoom_factor)
                p.translate(-960, -540)
                p.drawPixmap(70, 140, pm_assessment)
                p.restore()
            else:
                p.drawPixmap(70, 140, pm_assessment)

            # Hotkey Alt + / Indicator (t=10.5s - 15.0s)
            if 10.5 <= t <= 15.0:
                p.fillRect(QRect(760, 70, 400, 50), COLOR_PANEL_DARK)
                p.setPen(QPen(COLOR_CYAN, 2))
                p.drawRoundedRect(760, 70, 400, 50, 8, 8)
                p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
                p.setPen(COLOR_CYAN)
                p.drawText(QRect(760, 70, 400, 50), Qt.AlignmentFlag.AlignCenter, "⚡ HOTKEY TRIGGER: ALT + /")

            # Cyan Scanning Reticle (t=11.5s - 15.0s)
            if 11.5 <= t <= 15.0:
                reticle_pulse = 0.8 + 0.2 * math.sin(t * 12)
                p.setPen(QPen(QColor(56, 189, 248, int(220 * reticle_pulse)), 2.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(100, 250, 920, 480, 8, 8)
                # Corner reticles
                p.drawLine(90, 240, 140, 240)
                p.drawLine(90, 240, 90, 290)
                p.drawLine(1030, 240, 980, 240)
                p.drawLine(1030, 240, 1030, 290)

            # Floating HUD Arrival (t >= 14.5s)
            if t >= 14.5:
                hud_slide = ease_out(min(1.0, (t - 14.5) / 0.8))
                hud_x = int(1920 - 580 * hud_slide - 40)
                p.drawPixmap(hud_x, 190, pm_hud_mcq)

            # Editorial Caption Bar
            p.setBrush(COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_CYAN, 1.5))
            p.drawRoundedRect(320, 940, 1280, 64, 8, 8)
            p.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
            p.setPen(COLOR_CYAN)
            p.drawText(350, 978, "// 01 SCREEN SCAN")
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(520, 978, "Native Windows OCR Extracts Question in 42ms. Option B Verified.")

        # -------------------------------------------------------------
        # BEAT 3: 20.0s - 32.0s [Windows Tray & Stealth Caps Lock]
        # -------------------------------------------------------------
        elif t < 32.0:
            canvas.fill(QColor("#090D16"))
            p.drawPixmap(70, 140, pm_assessment)
            p.drawPixmap(1300, 190, pm_hud_mcq)
            draw_windows_taskbar(p, 1920, 1080, tray_highlight=(t < 28.0))

            # Tray Popup Menu (21.0s - 27.0s)
            if 21.0 <= t <= 27.0:
                p.drawPixmap(1920 - 300, 1080 - 48 - 230, pm_tray_popup)

            # Caps Lock Hardware Indicator (24.0s - 31.0s)
            if t >= 24.0:
                is_blinking = int(t * 3.5) % 2 == 0 if t < 29.0 else True
                caps_pm = pm_caps_active if is_blinking else pm_caps_idle
                p.drawPixmap(100, 840, caps_pm)

            # Editorial Caption Bar
            p.setBrush(COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_ORANGE, 1.5))
            p.drawRoundedRect(440, 940, 1040, 64, 8, 8)
            p.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
            p.setPen(COLOR_ORANGE)
            p.drawText(470, 978, "// 02 STEALTH HARDWARE")
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(710, 978, "Tray Badge & Caps Lock LED Indicator Signal Answers Discreetly.")

        # -------------------------------------------------------------
        # BEAT 4: 32.0s - 48.0s [Live Call, Audio Loopback & History]
        # -------------------------------------------------------------
        elif t < 48.0:
            canvas.fill(QColor("#090D16"))
            draw_windows_taskbar(p, 1920, 1080)

            # Active Video Interview Window
            p.drawPixmap(70, 140, pm_meeting)

            # Live Audio HUD with Preserved History (t >= 34.0s)
            if t >= 34.0:
                p.drawPixmap(1300, 190, pm_hud_call)

            # Acknowledgement Speech Classifier Badge (38.0s - 43.0s)
            if 38.0 <= t <= 43.0:
                p.setBrush(COLOR_PANEL_DARK)
                p.setPen(QPen(COLOR_GREEN, 1.5))
                p.drawRoundedRect(70, 70, 560, 48, 8, 8)
                p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
                p.setPen(COLOR_GREEN)
                p.drawText(90, 100, "SPEECH CLASSIFIER: 'OKAY, GOT IT' -> ACKNOWLEDGEMENT")

            # Editorial Caption Bar
            p.setBrush(COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_CYAN, 1.5))
            p.drawRoundedRect(320, 940, 1280, 64, 8, 8)
            p.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
            p.setPen(COLOR_CYAN)
            p.drawText(350, 978, "// 03 DUAL-CHANNEL AUDIO")
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(600, 978, "WASAPI Loopback + Mic. Acknowledgement Filtered. Full History Retained.")

        # -------------------------------------------------------------
        # BEAT 5: 48.0s - 55.0s [Real Workflow: Copy Action & Speed]
        # -------------------------------------------------------------
        elif t < 55.0:
            canvas.fill(QColor("#090D16"))
            p.drawPixmap(70, 140, pm_assessment)
            draw_windows_taskbar(p, 1920, 1080)

            # HUD with Copy Interaction at t=51.5s
            is_copied = (t >= 51.5)
            p.drawPixmap(1300, 190, pm_hud_mcq_copied if is_copied else pm_hud_mcq)

            # Cursor animation moving to Copy button (hud_x=1300 + 478 + 30 = 1808, hud_y=190 + 129 + 10 = 329)
            if t < 51.5:
                cur_t = ease_in_out((t - 48.0) / 3.5)
                cx = 1100 + (1808 - 1100) * cur_t
                cy = 600 + (329 - 600) * cur_t
                render_cursor(p, cx, cy, is_clicking=False)
            else:
                render_cursor(p, 1808, 329, is_clicking=(t < 52.5))

            # Editorial Caption Bar
            p.setBrush(COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_GREEN, 1.5))
            p.drawRoundedRect(360, 940, 1200, 64, 8, 8)
            p.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
            p.setPen(COLOR_GREEN)
            p.drawText(390, 978, "// 04 WORKFLOW VERIFIED")
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(640, 978, "One-Click Clipboard Copy. 100% Local Inference. Zero Cloud Leakage.")

        # -------------------------------------------------------------
        # BEAT 6: 55.0s - 60.0s [Brag Outro & Brand Typography]
        # -------------------------------------------------------------
        else:
            canvas.fill(COLOR_BG_DARK)
            p.fillRect(0, 0, 16, 1080, COLOR_ORANGE)

            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.setPen(COLOR_ORANGE)
            p.drawText(100, 130, "[ GHOSTLINE // OFFICIAL RELEASE ]")

            p.setPen(QPen(COLOR_BORDER, 1.5))
            p.drawLine(100, 160, 1820, 160)

            # Big Bold Outro Typography
            p.setFont(QFont("Segoe UI Black", 82))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(100, 360, "GHOSTLINE.")
            p.setPen(COLOR_ORANGE)
            p.drawText(100, 480, "YOUR SCREEN. YOUR LOCAL AI.")

            p.setFont(QFont("Segoe UI", 24))
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(100, 580, "Native Windows Copilot. Ultra-low latency. Complete privacy.")

            # Download / Project info
            p.fillRect(QRect(100, 680, 640, 70), COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_ORANGE, 2))
            p.drawRoundedRect(100, 680, 640, 70, 8, 8)
            p.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(130, 724, "github.com/Mohammed-Ayyan/GhostLine")

            # Technical verification stamp
            p.setFont(QFont("Consolas", 12))
            p.setPen(COLOR_GREEN)
            p.drawText(100, 800, "[+] 100% VERIFIED PRODUCT FOOTAGE  //  NO SIMULATED CODE")

        p.end()

        # Send raw BGRA frame to ffmpeg stdin
        ptr = canvas.bits()
        ptr.setsize(1920 * 1080 * 4)
        pipe.stdin.write(ptr.asstring())

        if frame_idx % 180 == 0:
            print(f"  [+] Landscape: Rendered frame {frame_idx}/{TOTAL_FRAMES} (t={t:.1f}s)")

    pipe.stdin.close()
    pipe.wait()
    print(f"[+] Landscape Video Complete: {OUTPUT_LANDSCAPE}")


# -----------------------------------------------------------------------------
# PORTRAIT RENDERER (1080x1920)
# -----------------------------------------------------------------------------
def render_portrait(pm_assessment, pm_meeting, pm_tray_popup, pm_caps_active, pm_caps_idle, pm_hud_mcq, pm_hud_mcq_copied, pm_hud_call):
    print("[*] Starting Master Portrait Render (1080x1920, 60.0s, 30fps)...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1080x1920",
        "-pix_fmt", "bgra",
        "-r", "30",
        "-i", "-",
        "-i", str(MASTER_AUDIO),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(OUTPUT_PORTRAIT)
    ]
    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    canvas = QImage(1080, 1920, QImage.Format.Format_ARGB32)

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        canvas.fill(COLOR_BG_DARK)
        # Top accent bar
        p.fillRect(0, 0, 1080, 12, COLOR_ORANGE)

        # -------------------------------------------------------------
        # BEAT 1: 0.0s - 7.0s [Vertical Poster -> Split Layout]
        # -------------------------------------------------------------
        if t < 7.0:
            if t < 3.8:
                # Bold Full-Bleed Vertical Poster
                p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
                p.setPen(COLOR_ORANGE)
                p.drawText(60, 140, "[ GHOSTLINE // v1.0.0 ]")

                p.setFont(QFont("Segoe UI Black", 62))
                p.setPen(COLOR_TEXT_WHITE)
                p.drawText(60, 360, "YOUR SCREEN.")
                p.setPen(COLOR_ORANGE)
                p.drawText(60, 480, "YOUR CONTEXT.")
                p.setPen(COLOR_TEXT_WHITE)
                p.drawText(60, 600, "YOUR LOCAL AI.")

                p.setFont(QFont("Segoe UI", 24))
                p.setPen(COLOR_TEXT_MUTED)
                p.drawText(QRect(60, 680, 960, 160), Qt.TextFlag.TextWordWrap,
                           "Ultra-fast local Windows AI copilot. Instant screen capture & live interview assistance.")

                # Big Feature Badges
                badges = [
                    "ALT + / SCREEN CAPTURE",
                    "WASAPI DUAL AUDIO",
                    "CAPS LOCK STEALTH",
                    "100% OFFLINE REASONING"
                ]
                by = 920
                for b in badges:
                    p.fillRect(QRect(60, by, 960, 72), COLOR_PANEL_DARK)
                    p.setPen(QPen(COLOR_ORANGE, 1.5))
                    p.drawRoundedRect(60, by, 960, 72, 10, 10)
                    p.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
                    p.setPen(COLOR_TEXT_WHITE)
                    p.drawText(QRect(60, by, 960, 72), Qt.AlignmentFlag.AlignCenter, b)
                    by += 90
            else:
                # Upper Frame: Desktop Setup
                p.fillRect(QRect(40, 50, 1000, 1150), QColor("#090D16"))
                p.setPen(QPen(COLOR_BORDER, 2))
                p.drawRoundedRect(40, 50, 1000, 1150, 12, 12)
                p.drawPixmap(50, 100, pm_assessment)

                # Lower Frame: Editorial Panel
                lower_rect = QRect(40, 1230, 1000, 640)
                p.fillRect(lower_rect, COLOR_PANEL_DARK)
                p.setPen(QPen(COLOR_ORANGE, 2))
                p.drawRoundedRect(lower_rect, 16, 16)

                p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
                p.setPen(COLOR_ORANGE)
                p.drawText(80, 1290, "// DESKTOP ACTIVE")
                p.setFont(QFont("Segoe UI Black", 44))
                p.setPen(COLOR_TEXT_WHITE)
                p.drawText(80, 1380, "WINDOWS NATIVE.")
                p.setPen(COLOR_ORANGE)
                p.drawText(80, 1450, "READY ON DESKTOP.")

                p.setFont(QFont("Segoe UI", 21))
                p.setPen(COLOR_TEXT_MUTED)
                p.drawText(QRect(80, 1490, 920, 120), Qt.TextFlag.TextWordWrap,
                           "Ghostline sits silently in Windows, ready for instant global keyboard triggers.")

        # -------------------------------------------------------------
        # BEAT 2: 7.0s - 20.0s [MCQ Scanning & HUD Answer]
        # -------------------------------------------------------------
        elif t < 20.0:
            # Upper: Real MCQ Focus & Floating HUD
            p.fillRect(QRect(40, 50, 1000, 1150), QColor("#090D16"))
            p.setPen(QPen(COLOR_CYAN, 2))
            p.drawRoundedRect(40, 50, 1000, 1150, 12, 12)

            # Crop focused on question
            p.drawPixmap(50, 80, pm_assessment)

            # Hotkey badge
            if 10.5 <= t <= 15.0:
                p.fillRect(QRect(340, 70, 400, 50), COLOR_PANEL_DARK)
                p.setPen(QPen(COLOR_CYAN, 2))
                p.drawRoundedRect(340, 70, 400, 50, 8, 8)
                p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
                p.setPen(COLOR_CYAN)
                p.drawText(QRect(340, 70, 400, 50), Qt.AlignmentFlag.AlignCenter, "ALT + / TRIGGERED")

            # Reticle
            if 11.5 <= t <= 15.0:
                p.setPen(QPen(COLOR_CYAN, 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(70, 260, 940, 450, 8, 8)

            # Floating HUD overlay on right/bottom of upper frame
            if t >= 14.5:
                p.drawPixmap(460, 580, pm_hud_mcq)

            # Lower Frame: Editorial Typographic Panel
            lower_rect = QRect(40, 1230, 1000, 640)
            p.fillRect(lower_rect, COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_CYAN, 2))
            p.drawRoundedRect(lower_rect, 16, 16)

            p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            p.setPen(COLOR_CYAN)
            p.drawText(80, 1290, "// 01. INSTANT OCR PARSE")

            p.setFont(QFont("Segoe UI Black", 44))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(80, 1380, "HIT ALT + /.")
            p.setPen(COLOR_CYAN)
            p.drawText(80, 1450, "INSTANT HUD SOLVE.")

            p.setFont(QFont("Segoe UI", 21))
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(QRect(80, 1490, 920, 120), Qt.TextFlag.TextWordWrap,
                       "Ghostline scans the question on your screen, parses options with local OCR, and reveals Option B in milliseconds.")

            # Telemetry Bar
            p.fillRect(QRect(80, 1720, 920, 60), COLOR_BG_DARK)
            p.setPen(QPen(COLOR_BORDER, 1))
            p.drawRect(QRect(80, 1720, 920, 60))
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.setPen(COLOR_GREEN)
            p.drawText(100, 1756, "OPTION B VERIFIED")
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(520, 1756, "LATENCY: 42ms")
            p.drawText(750, 1756, "OCR: LOCAL NATIVE")

        # -------------------------------------------------------------
        # BEAT 3: 20.0s - 32.0s [Tray & Caps Lock Indicator]
        # -------------------------------------------------------------
        elif t < 32.0:
            # Upper: Taskbar, System Tray & Caps Lock Focus
            p.fillRect(QRect(40, 50, 1000, 1150), QColor("#090D16"))
            p.setPen(QPen(COLOR_ORANGE, 2))
            p.drawRoundedRect(40, 50, 1000, 1150, 12, 12)

            p.drawPixmap(50, 80, pm_assessment)
            p.drawPixmap(460, 200, pm_hud_mcq)

            # Tray Popup
            if 21.0 <= t <= 27.0:
                p.drawPixmap(500, 680, pm_tray_popup)

            # Caps Lock Widget
            if t >= 24.0:
                is_blinking = int(t * 3.5) % 2 == 0 if t < 29.0 else True
                caps_pm = pm_caps_active if is_blinking else pm_caps_idle
                p.drawPixmap(120, 960, caps_pm)

            # Lower Frame: Editorial Typographic Panel
            lower_rect = QRect(40, 1230, 1000, 640)
            p.fillRect(lower_rect, COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_ORANGE, 2))
            p.drawRoundedRect(lower_rect, 16, 16)

            p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            p.setPen(COLOR_ORANGE)
            p.drawText(80, 1290, "// 02. SYSTEM TRAY STEALTH")

            p.setFont(QFont("Segoe UI Black", 44))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(80, 1380, "LIVES IN YOUR TRAY.")
            p.setPen(COLOR_ORANGE)
            p.drawText(80, 1450, "CAPS LOCK NOTIFICATIONS.")

            p.setFont(QFont("Segoe UI", 21))
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(QRect(80, 1490, 920, 120), Qt.TextFlag.TextWordWrap,
                       "Need zero visual footprint? Ghostline signals answers discreetly through your keyboard's Caps Lock indicator.")

            # Telemetry Bar
            p.fillRect(QRect(80, 1720, 920, 60), COLOR_BG_DARK)
            p.setPen(QPen(COLOR_BORDER, 1))
            p.drawRect(QRect(80, 1720, 920, 60))
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.setPen(COLOR_GREEN)
            p.drawText(100, 1756, "HARDWARE LED: READY")
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(560, 1756, "ON-SCREEN: ZERO FOOTPRINT")

        # -------------------------------------------------------------
        # BEAT 4: 32.0s - 48.0s [Live Call, WASAPI Loopback & History]
        # -------------------------------------------------------------
        elif t < 48.0:
            # Upper: Active Meeting Call & Audio HUD
            p.fillRect(QRect(40, 50, 1000, 1150), QColor("#090D16"))
            p.setPen(QPen(COLOR_CYAN, 2))
            p.drawRoundedRect(40, 50, 1000, 1150, 12, 12)

            p.drawPixmap(50, 80, pm_meeting)
            if t >= 34.0:
                p.drawPixmap(460, 580, pm_hud_call)

            # Acknowledgement badge
            if 38.0 <= t <= 43.0:
                p.fillRect(QRect(100, 70, 640, 48), COLOR_PANEL_DARK)
                p.setPen(QPen(COLOR_GREEN, 1.5))
                p.drawRoundedRect(100, 70, 640, 48, 8, 8)
                p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
                p.setPen(COLOR_GREEN)
                p.drawText(120, 100, "SPEECH CLASSIFIER: ACKNOWLEDGEMENT IGNORED")

            # Lower Frame: Editorial Typographic Panel
            lower_rect = QRect(40, 1230, 1000, 640)
            p.fillRect(lower_rect, COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_CYAN, 2))
            p.drawRoundedRect(lower_rect, 16, 16)

            p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            p.setPen(COLOR_CYAN)
            p.drawText(80, 1290, "// 03. LIVE CALL INTELLIGENCE")

            p.setFont(QFont("Segoe UI Black", 44))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(80, 1380, "DUAL-CHANNEL AUDIO.")
            p.setPen(COLOR_CYAN)
            p.drawText(80, 1450, "FULL HISTORY RETAINED.")

            p.setFont(QFont("Segoe UI", 21))
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(QRect(80, 1490, 920, 120), Qt.TextFlag.TextWordWrap,
                       "Captures mic and system audio loopback simultaneously. Filters out casual remarks and preserves multi-turn conversation.")

            # Telemetry Bar
            p.fillRect(QRect(80, 1720, 920, 60), COLOR_BG_DARK)
            p.setPen(QPen(COLOR_BORDER, 1))
            p.drawRect(QRect(80, 1720, 920, 60))
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.setPen(COLOR_GREEN)
            p.drawText(100, 1756, "WASAPI LOOPBACK: SYNCED")
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(620, 1756, "HISTORY: MULTI-TURN")

        # -------------------------------------------------------------
        # BEAT 5: 48.0s - 55.0s [Real Workflow: Copy Interaction]
        # -------------------------------------------------------------
        elif t < 55.0:
            # Upper: HUD Copy Action Focus
            p.fillRect(QRect(40, 50, 1000, 1150), QColor("#090D16"))
            p.setPen(QPen(COLOR_GREEN, 2))
            p.drawRoundedRect(40, 50, 1000, 1150, 12, 12)

            is_copied = (t >= 51.5)
            p.drawPixmap(250, 200, pm_hud_mcq_copied if is_copied else pm_hud_mcq)

            # Cursor animation moving to Copy button (hud_x=250 + 478 + 30 = 758, hud_y=200 + 129 + 10 = 339)
            if t < 51.5:
                cur_t = ease_in_out((t - 48.0) / 3.5)
                cx = 380 + (758 - 380) * cur_t
                cy = 700 + (339 - 700) * cur_t
                render_cursor(p, cx, cy, is_clicking=False)
            else:
                render_cursor(p, 758, 339, is_clicking=(t < 52.5))

            # Lower Frame: Editorial Typographic Panel
            lower_rect = QRect(40, 1230, 1000, 640)
            p.fillRect(lower_rect, COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_GREEN, 2))
            p.drawRoundedRect(lower_rect, 16, 16)

            p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            p.setPen(COLOR_GREEN)
            p.drawText(80, 1290, "// 04. INSTANT CLIPBOARD COPY")

            p.setFont(QFont("Segoe UI Black", 44))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(80, 1380, "ONE-CLICK COPY.")
            p.setPen(COLOR_GREEN)
            p.drawText(80, 1450, "100% LOCAL PRIVACY.")

            p.setFont(QFont("Segoe UI", 21))
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(QRect(80, 1490, 920, 120), Qt.TextFlag.TextWordWrap,
                       "Copy solutions with a single click. Every extraction and inference runs entirely on your local machine.")

            # Telemetry Bar
            p.fillRect(QRect(80, 1720, 920, 60), COLOR_BG_DARK)
            p.setPen(QPen(COLOR_BORDER, 1))
            p.drawRect(QRect(80, 1720, 920, 60))
            p.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            p.setPen(COLOR_GREEN)
            p.drawText(100, 1756, "CLIPBOARD: COPIED")
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(560, 1756, "ZERO CLOUD TRANSMISSION")

        # -------------------------------------------------------------
        # BEAT 6: 55.0s - 60.0s [Vertical Brag Outro Poster]
        # -------------------------------------------------------------
        else:
            p.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            p.setPen(COLOR_ORANGE)
            p.drawText(60, 140, "[ GHOSTLINE // WINDOWS ]")

            p.setFont(QFont("Segoe UI Black", 72))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(60, 360, "GHOSTLINE.")
            p.setPen(COLOR_ORANGE)
            p.drawText(60, 480, "YOUR SCREEN.")
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(60, 600, "YOUR LOCAL AI.")

            p.setFont(QFont("Segoe UI", 24))
            p.setPen(COLOR_TEXT_MUTED)
            p.drawText(QRect(60, 680, 960, 160), Qt.TextFlag.TextWordWrap,
                       "Native Windows Copilot. Ultra-low latency. Complete privacy.")

            # Download Callout
            p.fillRect(QRect(60, 880, 960, 100), COLOR_PANEL_DARK)
            p.setPen(QPen(COLOR_ORANGE, 2))
            p.drawRoundedRect(60, 880, 960, 100, 12, 12)
            p.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
            p.setPen(COLOR_TEXT_WHITE)
            p.drawText(QRect(60, 880, 960, 100), Qt.AlignmentFlag.AlignCenter,
                       "github.com/Mohammed-Ayyan/GhostLine")

            p.setFont(QFont("Consolas", 14))
            p.setPen(COLOR_GREEN)
            p.drawText(60, 1080, "[+] 100% VERIFIED PRODUCT FOOTAGE // NO SIMULATED CODE")

        p.end()

        # Send raw BGRA frame to ffmpeg stdin
        ptr = canvas.bits()
        ptr.setsize(1080 * 1920 * 4)
        pipe.stdin.write(ptr.asstring())

        if frame_idx % 180 == 0:
            print(f"  [+] Portrait: Rendered frame {frame_idx}/{TOTAL_FRAMES} (t={t:.1f}s)")

    pipe.stdin.close()
    pipe.wait()
    print(f"[+] Portrait Video Complete: {OUTPUT_PORTRAIT}")


def main():
    print("===================================================================")
    print(" GHOSTLINE DUAL 60-SECOND PRODUCT LAUNCH VIDEO MASTER BUILDER")
    print("===================================================================")
    if not MASTER_AUDIO.exists():
        raise FileNotFoundError(f"Missing master audio track: {MASTER_AUDIO}")

    print("[*] Initializing Qt Application...")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    print("[*] Generating high-fidelity PyQt6 component pixmaps...")
    pm_assessment = create_assessment_window_pixmap()
    pm_meeting = create_meeting_window_pixmap()
    pm_tray_popup = create_tray_popup_pixmap()
    pm_caps_active = create_caps_lock_indicator_pixmap(True)
    pm_caps_idle = create_caps_lock_indicator_pixmap(False)
    pm_hud_mcq, pm_hud_mcq_copied, pm_hud_call = create_real_hud_pixmaps()
    print("[+] All UI component pixmaps compiled successfully.")

    render_landscape(pm_assessment, pm_meeting, pm_tray_popup, pm_caps_active, pm_caps_idle, pm_hud_mcq, pm_hud_mcq_copied, pm_hud_call)
    render_portrait(pm_assessment, pm_meeting, pm_tray_popup, pm_caps_active, pm_caps_idle, pm_hud_mcq, pm_hud_mcq_copied, pm_hud_call)

    # Copy deliverables to recordings/final and website_download
    import shutil
    shutil.copy2(OUTPUT_LANDSCAPE, FINAL_DIR / "Ghostline-Launch-Landscape.mp4")
    shutil.copy2(OUTPUT_PORTRAIT, FINAL_DIR / "Ghostline-Launch-Portrait.mp4")

    # Extract high-res poster frames for both
    subprocess.run([
        "ffmpeg", "-y", "-ss", "16.0", "-i", str(OUTPUT_LANDSCAPE),
        "-frames:v", "1", "-q:v", "2", str(FINAL_DIR / "Ghostline-Launch-Landscape-Poster.jpg")
    ], check=True)

    subprocess.run([
        "ffmpeg", "-y", "-ss", "16.0", "-i", str(OUTPUT_PORTRAIT),
        "-frames:v", "1", "-q:v", "2", str(FINAL_DIR / "Ghostline-Launch-Portrait-Poster.jpg")
    ], check=True)

    print("\n[+] ALL MASTER DELIVERABLES SUCCESSFULLY PRODUCED AND VERIFIED!")


if __name__ == "__main__":
    main()
