"""
Segment 2 Generator: Floating HUD, Tray, and Desktop Integration (20-40 seconds)
Produces broadcast-quality 1080p 30fps H.264 video with real PyQt6 UI and Tray rendering.
Sequence:
- 20-25s: Floating HUD Q&A interaction and Copy Answer action.
- 25-32.5s: Windows notification overflow menu, Ghostline tray icon with dynamic badge B, and context menu.
- 32.5-40s: Desktop Settings window, Caps Lock LED indicator mode, and hardware test.
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
from ghostline.ui.tray_indicator import TrayIndicator

OUTPUT_DIR = root_dir / "recordings" / "segment_2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_VIDEO = OUTPUT_DIR / "segment_2_hud_tray_integration.mp4"
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

    # Cursor Body
    painter.setBrush(QColor(255, 255, 255))
    painter.setPen(QPen(QColor(15, 23, 42), 1.5))
    poly = [QPoint(int(x), int(y)), QPoint(int(x), int(y+16)), QPoint(int(x+4), int(y+12)), QPoint(int(x+10), int(y+20)), QPoint(int(x+13), int(y+18)), QPoint(int(x+7), int(y+10)), QPoint(int(x+13), int(y+10))]
    painter.drawPolygon(poly)

    if is_clicking:
        painter.setPen(QPen(QColor(56, 189, 248, 180), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(x-10), int(y-10), 20, 20)

    painter.restore()


def draw_windows_taskbar(painter, tray_highlight=False):
    tb_rect = QRect(0, HEIGHT - 48, WIDTH, 48)
    painter.fillRect(tb_rect, QColor("#10141d"))
    painter.setPen(QPen(QColor("#1e293b"), 1))
    painter.drawLine(0, HEIGHT - 48, WIDTH, HEIGHT - 48)

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
    # Ghostline Taskbar App Icon
    painter.setBrush(QColor("#38bdf8"))
    painter.drawRoundedRect(cx + 116, HEIGHT - 38, 26, 26, 6, 6)
    painter.fillRect(cx + 124, HEIGHT - 6, 10, 3, QColor("#38bdf8"))

    # System Tray Area (bottom right)
    painter.setFont(QFont("Segoe UI", 10))
    painter.setPen(QColor("#f8fafc"))
    painter.drawText(WIDTH - 140, HEIGHT - 28, "10:45 AM")
    painter.setFont(QFont("Segoe UI", 9))
    painter.setPen(QColor("#94a3b8"))
    painter.drawText(WIDTH - 140, HEIGHT - 14, "10/26/2026")
    
    # Chevron button
    chev_rect = QRect(WIDTH - 186, HEIGHT - 38, 26, 28)
    if tray_highlight:
        painter.fillRect(chev_rect, QColor("#1e293b"))
    painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    painter.setPen(QColor("#f8fafc" if tray_highlight else "#94a3b8"))
    painter.drawText(chev_rect, Qt.AlignmentFlag.AlignCenter, "⌃")

    # Volume & Wi-Fi
    painter.setFont(QFont("Segoe UI Symbol", 10))
    painter.setPen(QColor("#94a3b8"))
    painter.drawText(WIDTH - 225, HEIGHT - 20, "🛈  🔊")


def draw_tray_overflow_menu(painter, badge_img_pix, x, y, show_context_menu=False):
    # Authentic Windows 11 Notification Area Overflow Flyout
    fw, fh = 160, 100
    f_rect = QRect(x, y, fw, fh)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Flyout Background & Border
    painter.fillRect(f_rect, QColor("#161a24"))
    painter.setPen(QPen(QColor("#334155"), 1))
    painter.drawRoundedRect(f_rect, 8, 8)

    # Grid of notification icons
    # Icon 1: Windows Defender
    painter.setBrush(QColor("#1e293b"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(x + 16, y + 16, 32, 32, 6, 6)
    painter.setPen(QColor("#38bdf8"))
    painter.setFont(QFont("Segoe UI Symbol", 12))
    painter.drawText(x + 24, y + 38, "🛡️")

    # Icon 2: Bluetooth
    painter.setBrush(QColor("#1e293b"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(x + 64, y + 16, 32, 32, 6, 6)
    painter.setPen(QColor("#94a3b8"))
    painter.drawText(x + 72, y + 38, "ᛒ")

    # Icon 3: Ghostline Tray Icon (with dynamic badge B!)
    tray_box = QRect(x + 112, y + 16, 32, 32)
    painter.drawPixmap(tray_box, badge_img_pix)
    # Subtle cyan glow ring around Ghostline icon
    painter.setPen(QPen(QColor(56, 189, 248, 160), 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(tray_box, 6, 6)

    # Tooltip pill if not showing context menu
    if not show_context_menu:
        tt_rect = QRect(x - 90, y - 34, 250, 26)
        painter.fillRect(tt_rect, QColor("#0f172a"))
        painter.setPen(QPen(QColor("#38bdf8"), 1))
        painter.drawRoundedRect(tt_rect, 4, 4)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.drawText(tt_rect, Qt.AlignmentFlag.AlignCenter, "Ghostline — Answer B: End-to-end...")

    # Context Menu if right-clicked
    if show_context_menu:
        cm_w, cm_h = 220, 160
        cm_x, cm_y = x - 70, y - cm_h - 10
        cm_rect = QRect(cm_x, cm_y, cm_w, cm_h)
        painter.fillRect(cm_rect, QColor("#111827"))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(cm_rect, 8, 8)

        items = [
            ("● Show Answer Window", True),
            ("⚡ Solve Under Cursor (Alt + /)", False),
            ("👁 Toggle HUD Overlay", False),
            ("⚙ Settings...", False),
            ("🚪 Exit", False)
        ]
        iy = cm_y + 8
        for title, is_bold in items:
            if "Settings" in title:
                # Hover highlight on Settings
                painter.fillRect(QRect(cm_x + 6, iy - 2, cm_w - 12, 28), QColor("#1e293b"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if is_bold else QFont.Weight.Normal))
            painter.setPen(QColor("#38bdf8" if is_bold else "#f8fafc"))
            painter.drawText(cm_x + 18, iy + 16, title)
            iy += 30

    painter.restore()


def draw_desktop_wallpaper(painter):
    painter.fillRect(0, 0, WIDTH, HEIGHT, QColor("#090d16"))
    from PyQt6.QtGui import QRadialGradient
    rad = QRadialGradient(WIDTH / 2, HEIGHT / 2 - 50, 850)
    rad.setColorAt(0.0, QColor(20, 35, 60, 160))
    rad.setColorAt(0.6, QColor(12, 18, 30, 80))
    rad.setColorAt(1.0, QColor(9, 13, 22, 0))
    painter.fillRect(0, 0, WIDTH, HEIGHT, rad)


def draw_caption(painter, text, subtext=""):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    cap_w = 840
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


def create_caps_lock_keyboard_graphic(is_blinking=False, pulse_count=0):
    # Renders an authentic keyboard indicator module showing Caps Lock LED
    w, h = 340, 180
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#111827"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    p.fillRect(0, 0, w, h, QColor("#1e293b"))
    p.setPen(QPen(QColor("#334155"), 1.5))
    p.drawRoundedRect(0, 0, w, h, 10, 10)

    p.setPen(QColor("#38bdf8"))
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.drawText(20, 32, "PHYSICAL HARDWARE SIGNALING")

    # Keyboard Key Representation (Caps Lock Keycap)
    key_rect = QRect(25, 55, 120, 95)
    p.fillRect(key_rect, QColor("#0f172a"))
    p.setPen(QPen(QColor("#475569"), 1.5))
    p.drawRoundedRect(key_rect, 8, 8)

    p.setPen(QColor("#f8fafc"))
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
    p.drawText(40, 85, "Caps Lock")

    # LED Indicator Light on Keycap
    led_x, led_y = 42, 110
    if is_blinking:
        # Bright Glowing Green LED
        p.setBrush(QColor("#10b981"))
        p.setPen(QPen(QColor("#34d399"), 2))
        p.drawEllipse(led_x, led_y, 14, 14)
        # Glow halo
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(16, 185, 129, 120), 4))
        p.drawEllipse(led_x - 3, led_y - 3, 20, 20)
    else:
        # Dim off LED
        p.setBrush(QColor("#1e293b"))
        p.setPen(QPen(QColor("#475569"), 1))
        p.drawEllipse(led_x, led_y, 14, 14)

    # Explanation on right side
    p.setPen(QColor("#e2e8f0"))
    p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    p.drawText(160, 75, "LED Output: 2 Pulses")
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(160, 98, "Verified Option B")
    p.drawText(160, 118, "Restores typing state")
    p.drawText(160, 138, "Zero on-screen trace")

    p.end()
    return QPixmap.fromImage(img)


def main():
    print("[*] Launching PyQt6 Engine for Segment 2 (Floating HUD, Tray, and Desktop Integration)...")
    app = QApplication.instance() or QApplication(sys.argv)
    from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    cfg = AppConfig()

    # 1. Real Floating HUD Window
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

    # 2. Real Ghostline Settings Window (Hardware & Stealth tab)
    main_win = QtGhostlineMainWindow(config=cfg)
    main_win.resize(960, 680)
    main_win.show_screen("general")
    app.processEvents()
    pix_settings = main_win.grab()

    # 3. Dynamic Tray Icon Badge Image (real output of TrayIndicator)
    tray = TrayIndicator()
    badge_img_pil = tray.create_image("B", "normal")
    badge_img_bytes = badge_img_pil.convert("RGBA").tobytes("raw", "RGBA")
    qimg_badge = QImage(badge_img_bytes, badge_img_pil.width, badge_img_pil.height, QImage.Format.Format_RGBA8888)
    pix_tray_badge = QPixmap.fromImage(qimg_badge)

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

    canvas = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)

    # Coordinates
    hud_center_x, hud_center_y = (WIDTH - pix_hud.width()) // 2, 100
    tray_flyout_x, tray_flyout_y = WIDTH - 200, HEIGHT - 165
    settings_x, settings_y = (WIDTH - 960) // 2, 90

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS # 0.0s to 20.0s (representing 20s to 40s in total film)

        canvas.fill(QColor("#090d16"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_desktop_wallpaper(painter)

        # -------------------------------------------------------------
        # 0.0s - 5.0s (Film: 20s - 25s): Floating HUD & Copy Answer Action
        # -------------------------------------------------------------
        if t < 5.0:
            # Floating HUD prominently centered
            painter.drawPixmap(hud_center_x, hud_center_y, pix_hud)

            # Cursor moves to Copy Answer button on the card
            copy_btn_x = hud_center_x + pix_hud.width() - 85
            copy_btn_y = hud_center_y + 115

            prog = min(1.0, t / 2.5)
            cur_x = 450 + (copy_btn_x - 450) * ease_in_out(prog)
            cur_y = 350 + (copy_btn_y - 350) * ease_in_out(prog)

            is_click = (2.4 <= t <= 2.6)
            has_copied = (t >= 2.5)

            # Draw Toast when copied
            if has_copied:
                toast_rect = QRect((WIDTH - 360) // 2, hud_center_y + pix_hud.height() + 15, 360, 38)
                painter.fillRect(toast_rect, QColor(16, 185, 129, 230))
                painter.setPen(QPen(QColor(52, 211, 153), 1.5))
                painter.drawRoundedRect(toast_rect, 8, 8)
                painter.setPen(QColor("#090d16"))
                painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                painter.drawText(toast_rect, Qt.AlignmentFlag.AlignCenter, "✓ Answer & rationale copied to clipboard")

            render_cursor(painter, cur_x, cur_y, is_clicking=is_click)
            draw_windows_taskbar(painter)
            draw_caption(painter, "Persistent Multi-Card HUD & One-Click Export", "Verified direct answers, structured explanations, and instant clipboard export")

        # -------------------------------------------------------------
        # 5.0s - 12.5s (Film: 25s - 32.5s): System Tray Integration & Context Menu
        # -------------------------------------------------------------
        elif t < 12.5:
            # HUD remains visible on top left
            painter.drawPixmap(80, 80, pix_hud)

            # Taskbar with tray highlight
            show_flyout = (t >= 7.0)
            show_context = (t >= 9.5)
            draw_windows_taskbar(painter, tray_highlight=show_flyout)

            # Cursor moves to notification chevron
            chev_x = WIDTH - 173
            chev_y = HEIGHT - 24

            if t < 7.0:
                prog = (t - 5.0) / 2.0
                cur_x = (hud_center_x + pix_hud.width() - 85) + (chev_x - (hud_center_x + pix_hud.width() - 85)) * ease_in_out(prog)
                cur_y = (hud_center_y + 115) + (chev_y - (hud_center_y + 115)) * ease_in_out(prog)
                is_click = (6.8 <= t <= 7.0)
            elif t < 9.5:
                # Move cursor to Ghostline icon in flyout
                ghost_icon_x = tray_flyout_x + 128
                ghost_icon_y = tray_flyout_y + 32
                prog = (t - 7.0) / 2.0
                cur_x = chev_x + (ghost_icon_x - chev_x) * ease_in_out(prog)
                cur_y = chev_y + (ghost_icon_y - chev_y) * ease_in_out(prog)
                is_click = (9.3 <= t <= 9.5)
            else:
                # Move cursor to 'Settings...' in context menu
                settings_item_x = tray_flyout_x - 70 + 80
                settings_item_y = tray_flyout_y - 160 - 10 + 110
                prog = min(1.0, (t - 9.5) / 1.5)
                cur_x = (tray_flyout_x + 128) + (settings_item_x - (tray_flyout_x + 128)) * ease_in_out(prog)
                cur_y = (tray_flyout_y + 32) + (settings_item_y - (tray_flyout_y + 32)) * ease_in_out(prog)
                is_click = (11.8 <= t <= 12.0)

            if show_flyout:
                draw_tray_overflow_menu(painter, pix_tray_badge, tray_flyout_x, tray_flyout_y, show_context_menu=show_context)

            render_cursor(painter, cur_x, cur_y, is_clicking=is_click)
            draw_caption(painter, "Stealth Windows Notification Area Integration", "Dynamic 32x32 taskbar badges show verified answers • Full native context menu")

        # -------------------------------------------------------------
        # 12.5s - 20.0s (Film: 32.5s - 40s): Settings Window & Caps Lock Signaling
        # -------------------------------------------------------------
        else:
            # Settings Window
            painter.drawPixmap(settings_x, settings_y, pix_settings)

            # Draw Caps Lock Hardware Graphic in top right overlay
            kb_x = settings_x + 960 - 360
            kb_y = settings_y + 180

            # Blink simulation at 16.0s - 18.0s (2 clean pulses)
            blink_state = False
            if 16.0 <= t <= 16.4 or 16.8 <= t <= 17.2:
                blink_state = True

            pix_kb = create_caps_lock_keyboard_graphic(is_blinking=blink_state)
            painter.drawPixmap(kb_x, kb_y, pix_kb)

            # Move cursor to "Test Caps Lock LED" button in Settings
            btn_test_x = settings_x + 480
            btn_test_y = settings_y + 440

            prog = min(1.0, (t - 12.5) / 2.0)
            cur_x = 750 + (btn_test_x - 750) * ease_in_out(prog)
            cur_y = 600 + (btn_test_y - 600) * ease_in_out(prog)
            is_click = (15.5 <= t <= 15.7)

            # Highlight test button if clicked
            if t >= 15.6:
                diag_rect = QRect(settings_x + 220, settings_y + 490, 520, 36)
                painter.fillRect(diag_rect, QColor(16, 185, 129, 220))
                painter.setPen(QPen(QColor(52, 211, 153), 1))
                painter.drawRoundedRect(diag_rect, 6, 6)
                painter.setPen(QColor("#090d16"))
                painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                painter.drawText(diag_rect, Qt.AlignmentFlag.AlignCenter, "Caps Lock LED pulse test triggered successfully! (2 pulses for Option B)")

            render_cursor(painter, cur_x, cur_y, is_clicking=is_click)
            draw_windows_taskbar(painter)
            draw_caption(painter, "Physical Hardware Signaling — Zero On-Screen Traces", "Pulsing keyboard LED communicates answer (B = 2 pulses) without altering typing state")

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

    # Now Mix Audio & Music for Segment 2
    print("[*] Mixing authentic audio cues and music for Segment 2...")
    final_video = OUTPUT_DIR / "segment_2_final.mp4"
    
    # Audio filters:
    # 0: Video
    # 1: Music (volume=0.16)
    # 2: click1.ogg at 2.5s (Copy button click)
    # 3: click1.ogg at 7.0s (Tray chevron click)
    # 4: switch10.ogg at 9.4s (Right click context menu)
    # 5: click1.ogg at 11.9s (Settings click)
    # 6: click1.ogg at 15.6s (Test Caps Lock click)
    # 7: switch30.ogg at 16.0s (Caps lock pulse 1)
    # 8: switch30.ogg at 16.8s (Caps lock pulse 2)
    audio_cmd = [
        "ffmpeg", "-y",
        "-i", str(OUTPUT_VIDEO),
        "-ss", "20.0", "-i", str(AUDIO_MUSIC), # Music continuation from 20s
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "switch10.ogg"),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "switch30.ogg"),
        "-i", str(SFX_DIR / "switch30.ogg"),
        "-filter_complex",
        "[1:a]volume=0.16[mus];"
        "[2:a]adelay=2500|2500,volume=0.8[s1];"
        "[3:a]adelay=7000|7000,volume=0.8[s2];"
        "[4:a]adelay=9400|9400,volume=0.9[s3];"
        "[5:a]adelay=11900|11900,volume=0.8[s4];"
        "[6:a]adelay=15600|15600,volume=0.8[s5];"
        "[7:a]adelay=16000|16000,volume=0.7[s6];"
        "[8:a]adelay=16800|16800,volume=0.7[s7];"
        "[mus][s1][s2][s3][s4][s5][s6][s7]amix=inputs=8:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", "20.0",
        str(final_video)
    ]
    subprocess.run(audio_cmd, check=True)
    if final_video.exists():
        final_video.replace(OUTPUT_VIDEO)
        print(f"[✓] Segment 2 successfully completed: {OUTPUT_VIDEO} (Duration: 20.0s)")


if __name__ == "__main__":
    main()
