"""
Segment 1 Generator: The Product and Question Scanning (0-20 seconds)
Produces broadcast-quality 1080p 30fps H.264 video with real PyQt6 UI rendering.
Sequence:
- 0-4s: Introduce Ghostline over real Dashboard UI footage.
- 4-9s: Show main Ghostline application, readiness state, mode settings, and minimizing.
- 9-15s: Display clearly readable MCQ question on desktop.
- 15-20s: Trigger Alt + /, cyan reticle lock, instant HUD answer reveal with Option B.
"""

import os
import sys
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QImage, QPainter, QColor, QFont, QPen, QBrush, QPixmap
from PyQt6.QtCore import Qt, QPoint, QRect

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.presentation import PresentedAnswer, TYPE_MCQ

OUTPUT_DIR = root_dir / "recordings" / "segment_1"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_VIDEO = OUTPUT_DIR / "segment_1_product_and_scanning.mp4"
AUDIO_MUSIC = root_dir / ".agents" / "skills" / "brag" / "assets" / "music" / "happy-beats-business-moves-vol-12-by-ende-dot-app.mp3"
SFX_DIR = root_dir / "brag-output-2026-10-26-021000" / "composition" / "assets" / "sfx"

FPS = 30
DURATION_SEC = 20.0
TOTAL_FRAMES = int(FPS * DURATION_SEC) # 600 frames
WIDTH = 1920
HEIGHT = 1080


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def ease_out(t):
    return 1 - (1 - t) ** 3


def render_cursor(painter, x, y, is_clicking=False):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Cursor Shadow
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 100))
    poly_shadow = [QPoint(int(x+2), int(y+2)), QPoint(int(x+2), int(y+18)), QPoint(int(x+6), int(y+14)), QPoint(int(x+12), int(y+22)), QPoint(int(x+15), int(y+20)), QPoint(int(x+9), int(y+12)), QPoint(int(x+15), int(y+12))]
    painter.drawPolygon(poly_shadow)

    # Cursor Body (Standard Windows Arrow)
    painter.setBrush(QColor(255, 255, 255))
    painter.setPen(QPen(QColor(15, 23, 42), 1.5))
    poly = [QPoint(int(x), int(y)), QPoint(int(x), int(y+16)), QPoint(int(x+4), int(y+12)), QPoint(int(x+10), int(y+20)), QPoint(int(x+13), int(y+18)), QPoint(int(x+7), int(y+10)), QPoint(int(x+13), int(y+10))]
    painter.drawPolygon(poly)

    if is_clicking:
        painter.setPen(QPen(QColor(56, 189, 248, 180), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(x-10), int(y-10), 20, 20)

    painter.restore()


def draw_windows_taskbar(painter):
    # Windows 11 Taskbar at bottom
    tb_rect = QRect(0, HEIGHT - 48, WIDTH, 48)
    painter.fillRect(tb_rect, QColor("#10141d"))
    painter.setPen(QPen(QColor("#1e293b"), 1))
    painter.drawLine(0, HEIGHT - 48, WIDTH, HEIGHT - 48)

    # Centered taskbar icons
    cx = WIDTH // 2 - 120
    # Start button
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0078d4"))
    painter.drawRoundedRect(cx, HEIGHT - 38, 26, 26, 5, 5)
    # Search pill
    painter.setBrush(QColor("#1e293b"))
    painter.drawRoundedRect(cx + 36, HEIGHT - 38, 70, 26, 13, 13)
    painter.setPen(QColor("#94a3b8"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(cx + 56, HEIGHT - 21, "Search")
    # App Icons
    painter.setBrush(QColor("#38bdf8"))
    painter.drawRoundedRect(cx + 116, HEIGHT - 38, 26, 26, 6, 6) # Ghostline Icon
    # Active indicator under Ghostline icon
    painter.fillRect(cx + 124, HEIGHT - 6, 10, 3, QColor("#38bdf8"))

    # System Tray Area (bottom right)
    painter.setFont(QFont("Segoe UI", 10))
    painter.setPen(QColor("#f8fafc"))
    painter.drawText(WIDTH - 140, HEIGHT - 28, "10:45 AM")
    painter.setFont(QFont("Segoe UI", 9))
    painter.setPen(QColor("#94a3b8"))
    painter.drawText(WIDTH - 140, HEIGHT - 14, "10/26/2026")
    # Tray Icons (Chevron, Wi-Fi, Volume)
    painter.setFont(QFont("Segoe UI Symbol", 10))
    painter.drawText(WIDTH - 175, HEIGHT - 20, "⌃")
    painter.drawText(WIDTH - 210, HEIGHT - 20, "🛈  🔊")


def draw_desktop_wallpaper(painter):
    # Deep slate navy Windows desktop wallpaper with radial ambient glow
    painter.fillRect(0, 0, WIDTH, HEIGHT, QColor("#090d16"))
    # Ambient radial gradient in center
    from PyQt6.QtGui import QRadialGradient
    rad = QRadialGradient(WIDTH / 2, HEIGHT / 2 - 50, 850)
    rad.setColorAt(0.0, QColor(20, 35, 60, 160))
    rad.setColorAt(0.6, QColor(12, 18, 30, 80))
    rad.setColorAt(1.0, QColor(9, 13, 22, 0))
    painter.fillRect(0, 0, WIDTH, HEIGHT, rad)


def create_assessment_window_pixmap():
    # Renders a pristine browser/assessment window containing Question 12 of 50
    w, h = 980, 680
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#111827"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Window Frame & Title Bar
    p.fillRect(0, 0, w, 44, QColor("#1e293b"))
    p.setPen(QColor("#334155"))
    p.drawLine(0, 44, w, 44)

    # Tab
    p.fillRect(16, 8, 280, 36, QColor("#111827"))
    p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    p.setPen(QColor("#f8fafc"))
    p.drawText(36, 30, "Technical Exam — Systems Architecture")
    # Close tab x
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(QColor("#94a3b8"))
    p.drawText(275, 30, "✕")

    # Window controls (min, max, close)
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(w - 75, 28, "—  □  ✕")

    # Sub-header / Assessment Status
    p.fillRect(0, 45, w, 48, QColor("#0f172a"))
    p.setPen(QColor("#38bdf8"))
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.drawText(32, 75, "SECTION 2: NETWORK PROTOCOLS & DISTRIBUTED SYSTEMS")
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(w - 180, 75, "Time Remaining: 42:15")

    # Main Question Card Frame
    card_rect = QRect(32, 120, w - 64, 520)
    p.fillRect(card_rect, QColor("#1e293b"))
    p.setPen(QPen(QColor("#334155"), 1.5))
    p.drawRoundedRect(card_rect, 10, 10)

    # Question Header & Stem
    p.setPen(QColor("#38bdf8"))
    p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    p.drawText(60, 160, "Question 12 of 50")

    p.setPen(QColor("#f8fafc"))
    p.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
    p.drawText(60, 200, "What is the primary function of the transport layer in the OSI model?")

    # Options
    options = [
        ("A", "Physical bit transmission across physical media"),
        ("B", "End-to-end communication, segmentation, flow control, and error detection"),
        ("C", "Routing packets across disparate networks via IP addressing"),
        ("D", "User interface presentation and encryption")
    ]

    opt_y = 245
    for badge, text in options:
        opt_rect = QRect(60, opt_y, w - 120, 62)
        p.fillRect(opt_rect, QColor("#0f172a"))
        p.setPen(QPen(QColor("#334155"), 1))
        p.drawRoundedRect(opt_rect, 8, 8)

        # Badge pill
        badge_rect = QRect(76, opt_y + 16, 30, 30)
        p.fillRect(badge_rect, QColor("#334155"))
        p.setPen(QColor("#38bdf8"))
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)

        # Option text
        p.setPen(QColor("#e2e8f0"))
        p.setFont(QFont("Segoe UI", 12))
        p.drawText(122, opt_y + 36, text)

        opt_y += 76

    p.end()
    return QPixmap.fromImage(img)


def draw_caption(painter, text, subtext=""):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Bottom banner backdrop
    cap_w = 820
    cap_h = 64 if not subtext else 78
    cap_x = (WIDTH - cap_w) // 2
    cap_y = HEIGHT - 145
    
    painter.fillRect(QRect(cap_x, cap_y, cap_w, cap_h), QColor(15, 23, 42, 220))
    painter.setPen(QPen(QColor(56, 189, 248, 120), 1.5))
    painter.drawRoundedRect(cap_x, cap_y, cap_w, cap_h, 10, 10)

    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    painter.drawText(QRect(cap_x + 20, cap_y + 12, cap_w - 40, 30), Qt.AlignmentFlag.AlignCenter, text)

    if subtext:
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(QRect(cap_x + 20, cap_y + 44, cap_w - 40, 24), Qt.AlignmentFlag.AlignCenter, subtext)

    painter.restore()


def main():
    print("[*] Launching PyQt6 Engine for Segment 1 (The Product and Question Scanning)...")
    app = QApplication.instance() or QApplication(sys.argv)
    from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    cfg = AppConfig()

    # 1. Real Main Desktop Window
    main_win = QtGhostlineMainWindow(config=cfg)
    main_win.resize(960, 680)
    main_win.show()
    app.processEvents()

    # Populate Sample Results in Main Window
    class MockRes:
        class parsed_question:
            question_text = "What is the primary function of the transport layer in the OSI model?"
        class answer_result:
            answer_option = "B"
            proposed_option = "B"
            direct_answer = "Option B — End-to-end communication, segmentation, flow control, and error detection"
            explanation = "The OSI Transport Layer (Layer 4) provides transparent transfer of data between end users, handling segmentation, flow control, and error recovery (e.g. TCP/UDP)."
            code_snippet = ""
            confidence = 0.984

    main_win.on_solve_completed(MockRes())
    main_win.show_screen("dashboard")
    app.processEvents()
    pix_dashboard = main_win.grab()

    main_win.show_screen("mode")
    app.processEvents()
    pix_mode = main_win.grab()

    # 2. Real Floating HUD Window
    hud = QtGhostlineHudOverlay(width=580, height=560, opacity=0.98, is_pinned=True, always_on_top=True)
    hud.resize(580, 560)
    hud.set_active_mode("all")
    hud.set_keyword_chips(["Choice B", "MCQ", "Local AI"])

    entry = hud.session.create_entry(
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
    pres = PresentedAnswer(
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
    hud.session.complete_entry(entry.id, pres)
    hud.add_or_update_card(entry)
    hud.show()
    app.processEvents()
    pix_hud = hud.grab()

    # 3. Assessment Window Pixmap
    pix_exam = create_assessment_window_pixmap()

    # Prepare FFMPEG Video Pipe
    print(f"[*] Starting raw video encoding to {OUTPUT_VIDEO} ({TOTAL_FRAMES} frames @ {FPS} fps)...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "bgra",
        "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "18",
        str(OUTPUT_VIDEO)
    ]
    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    # Animate 600 Frames (0.0s to 20.0s)
    # Positions
    exam_x, exam_y = (WIDTH - pix_exam.width()) // 2, 70
    main_x, main_y = (WIDTH - 960) // 2, 90
    hud_x, hud_y = WIDTH - pix_hud.width() - 50, 90

    # Cursor trajectories
    cur_x, cur_y = 400.0, 300.0

    canvas = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS # Current time in seconds

        canvas.fill(QColor("#090d16"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_desktop_wallpaper(painter)

        # -------------------------------------------------------------
        # 0.0s - 4.0s: Intro Ghostline Dashboard
        # -------------------------------------------------------------
        if t < 4.0:
            # Draw Main Window
            painter.drawPixmap(main_x, main_y, pix_dashboard)
            # Gentle cursor motion
            t_norm = t / 4.0
            cur_x = 550 + 60 * np.sin(t_norm * 3.14)
            cur_y = 280 + 30 * np.cos(t_norm * 3.14)
            render_cursor(painter, cur_x, cur_y)
            draw_caption(painter, "GHOSTLINE — 100% Offline AI Assistant for Windows", "Zero cloud packets • On-device Ollama phi3:mini • Privacy-first")

        # -------------------------------------------------------------
        # 4.0s - 9.0s: Switch Mode & Minimize Window
        # -------------------------------------------------------------
        elif t < 9.0:
            if t < 6.8:
                # Cursor moves to Mode button in sidebar
                prog = min(1.0, (t - 4.0) / 1.5)
                cur_x = 550 + (main_x + 90 - 550) * ease_in_out(prog)
                cur_y = 280 + (main_y + 295 - 280) * ease_in_out(prog)
                is_click = (5.5 <= t <= 5.7)
                painter.drawPixmap(main_x, main_y, pix_dashboard if t < 5.6 else pix_mode)
                render_cursor(painter, cur_x, cur_y, is_clicking=is_click)
                draw_caption(painter, "Instant Question Capture & Assistance Settings", "Global hotkey Alt + / • Active window targeting • Local inference")
            else:
                # Cursor moves to minimize button in title bar
                prog = min(1.0, (t - 6.8) / 1.0)
                cur_x = (main_x + 90) + (main_x + 960 - 70 - (main_x + 90)) * ease_in_out(prog)
                cur_y = (main_y + 295) + (main_y + 22 - (main_y + 295)) * ease_in_out(prog)
                is_click = (7.8 <= t <= 8.0)
                
                # Minimizing animation (scale down to taskbar)
                if t < 7.9:
                    painter.drawPixmap(main_x, main_y, pix_mode)
                else:
                    min_prog = (t - 7.9) / 1.1
                    scale = max(0.01, 1.0 - min_prog)
                    mw = int(960 * scale)
                    mh = int(680 * scale)
                    mx = int(main_x + (WIDTH // 2 - main_x) * min_prog)
                    my = int(main_y + (HEIGHT - 48 - main_y) * min_prog)
                    scaled_pix = pix_mode.scaled(mw, mh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    painter.drawPixmap(mx, my, scaled_pix)

                render_cursor(painter, cur_x, cur_y, is_clicking=is_click)
                draw_caption(painter, "Stealth Background Operation", "Minimizes directly to background readiness • No telemetry")

        # -------------------------------------------------------------
        # 9.0s - 15.0s: Display Real MCQ Assessment Screen
        # -------------------------------------------------------------
        elif t < 15.0:
            # Draw Assessment Portal
            painter.drawPixmap(exam_x, exam_y, pix_exam)

            # Cursor floats naturally across the question stem and options
            cur_prog = (t - 9.0) / 6.0
            cur_x = exam_x + 180 + 350 * ease_in_out(min(1.0, cur_prog * 1.5))
            cur_y = exam_y + 200 + 120 * np.sin(cur_prog * 3.14)
            render_cursor(painter, cur_x, cur_y)

            draw_caption(painter, "Point Cursor Over Any Question on Your Screen", "Hover cursor and press Alt + / over technical questions, MCQs, or code")

        # -------------------------------------------------------------
        # 15.0s - 20.0s: Trigger Alt + /, Reticle Lock, Floating HUD Answer
        # -------------------------------------------------------------
        else:
            # Shift assessment window slightly left to accommodate floating HUD
            shift_prog = ease_out(min(1.0, (t - 15.0) / 0.8))
            cur_exam_x = int(exam_x - 220 * shift_prog)
            painter.drawPixmap(cur_exam_x, exam_y, pix_exam)

            # Draw Cyan Scanning Reticle around Question Stem & Options
            ret_x = cur_exam_x + 40
            ret_y = exam_y + 130
            ret_w = pix_exam.width() - 80
            ret_h = 490

            pulse = 0.5 + 0.5 * np.sin((t - 15.0) * 12.0)
            painter.setPen(QPen(QColor(56, 189, 248, int(160 + 80 * pulse)), 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(ret_x, ret_y, ret_w, ret_h, 8, 8)

            # Reticle Corner Crosshairs
            cs = 16
            painter.setPen(QPen(QColor(56, 189, 248), 3.5))
            painter.drawLine(ret_x - 4, ret_y - 4, ret_x + cs, ret_y - 4)
            painter.drawLine(ret_x - 4, ret_y - 4, ret_x - 4, ret_y + cs)
            painter.drawLine(ret_x + ret_w + 4, ret_y - 4, ret_x + ret_w - cs, ret_y - 4)
            painter.drawLine(ret_x + ret_w + 4, ret_y - 4, ret_x + ret_w + 4, ret_y + cs)
            painter.drawLine(ret_x - 4, ret_y + ret_h + 4, ret_x + cs, ret_y + ret_h + 4)
            painter.drawLine(ret_x - 4, ret_y + ret_h + 4, ret_x - 4, ret_y + ret_h - cs)
            painter.drawLine(ret_x + ret_w + 4, ret_y + ret_h + 4, ret_x + ret_w - cs, ret_y + ret_h + 4)
            painter.drawLine(ret_x + ret_w + 4, ret_y + ret_h + 4, ret_x + ret_w + 4, ret_y + ret_h - cs)

            # Hotkey Badge Pill (Top Center)
            hk_rect = QRect(cur_exam_x + (pix_exam.width() - 200) // 2, exam_y + 80, 200, 36)
            painter.fillRect(hk_rect, QColor("#1e293b"))
            painter.setPen(QPen(QColor("#38bdf8"), 2))
            painter.drawRoundedRect(hk_rect, 18, 18)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            painter.drawText(hk_rect, Qt.AlignmentFlag.AlignCenter, "⚡ Hotkey: Alt + /")

            # Status Badge Pill
            stat_w = 230
            stat_rect = QRect(cur_exam_x + (pix_exam.width() - stat_w) // 2, exam_y + 140, stat_w, 32)
            painter.fillRect(stat_rect, QColor(15, 23, 42, 230))
            painter.setPen(QPen(QColor(16, 185, 129), 1.5))
            painter.drawRoundedRect(stat_rect, 6, 6)
            painter.setPen(QColor("#10b981"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            status_txt = "OCR: 42ms • Neural Solved" if t >= 16.2 else "Native Screen OCR Scanning..."
            painter.drawText(stat_rect, Qt.AlignmentFlag.AlignCenter, status_txt)

            # Reveal Floating HUD (Slides in smoothly from right at 16.2s)
            if t >= 16.2:
                hud_slide = ease_out(min(1.0, (t - 16.2) / 0.6))
                cur_hud_x = int(WIDTH - (WIDTH - hud_x) * hud_slide)
                painter.drawPixmap(cur_hud_x, hud_y, pix_hud)

            # Cursor resting near option B
            cur_x = cur_exam_x + 240
            cur_y = exam_y + 340
            render_cursor(painter, cur_x, cur_y)

            draw_caption(painter, "Instant Local OCR & Neural Reasoning in 642ms", "Verified Option B highlighted • Full explanatory breakdown • 100% Offline")

        # Draw Windows 11 Taskbar
        draw_windows_taskbar(painter)
        painter.end()

        # Pipe raw BGRA frame to ffmpeg
        ptr = canvas.bits()
        ptr.setsize(WIDTH * HEIGHT * 4)
        pipe.stdin.write(ptr.asstring())

        if frame_idx % 60 == 0:
            print(f"[*] Rendered {frame_idx}/{TOTAL_FRAMES} frames ({t:.1f}s / {DURATION_SEC:.1f}s)...")

    pipe.stdin.close()
    pipe.wait()
    print(f"[+] Raw video rendered to: {OUTPUT_VIDEO}")

    # Now Mix Tactile Audio & Music using ffmpeg
    print("[*] Mixing authentic audio cues and music for Segment 1...")
    final_video = OUTPUT_DIR / "segment_1_final.mp4"
    
    # Audio filters:
    # 0: Video
    # 1: Music (volume=0.18)
    # 2: click1.ogg at 0.8s (intro click)
    # 3: click1.ogg at 5.5s (mode click)
    # 4: switch10.ogg at 15.0s (Alt + / hotkey)
    # 5: click1.ogg at 16.2s (OCR lock)
    # 6: impactBell_heavy_000.ogg at 17.5s (Answer reveal bell)
    audio_cmd = [
        "ffmpeg", "-y",
        "-i", str(OUTPUT_VIDEO),
        "-i", str(AUDIO_MUSIC),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "switch10.ogg"),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "impactBell_heavy_000.ogg"),
        "-filter_complex",
        "[1:a]volume=0.16[mus];"
        "[2:a]adelay=800|800,volume=0.8[s1];"
        "[3:a]adelay=5500|5500,volume=0.8[s2];"
        "[4:a]adelay=15000|15000,volume=1.0[s3];"
        "[5:a]adelay=16200|16200,volume=0.9[s4];"
        "[6:a]adelay=17500|17500,volume=0.85[s5];"
        "[mus][s1][s2][s3][s4][s5]amix=inputs=6:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", "20.0",
        str(final_video)
    ]
    subprocess.run(audio_cmd, check=True)
    # Replace raw with final
    if final_video.exists():
        final_video.replace(OUTPUT_VIDEO)
        print(f"[✓] Segment 1 successfully completed: {OUTPUT_VIDEO} (Duration: 20.0s)")


if __name__ == "__main__":
    main()
