"""
Ghostline Run 10 Master Video Production Suite.
Renders all launch & documentation videos:
- H1: Launch Film (16:9, 1920x1080, 92s)
- H2: Homepage Hero Loop (16:9, 1280x720, 8s, seamless, <= 2MB)
- V1: Download & Setup Tutorial (16:9, 1920x1080, 140s)
- V2: How to Use Walkthrough (16:9, 1920x1080, 180s)
- S1: Instant Screen Solve Short (9:16, 1080x1920, 35s)
- S2: Dual-Stream Meeting Copilot Short (9:16, 1080x1920, 35s)
- S3: Grounded Identity Copilot Short (9:16, 1080x1920, 35s)
- S4: 100% Offline with Ollama Short (9:16, 1080x1920, 35s)
- S5: Stealth Hardware Signalling Short (9:16, 1080x1920, 35s)

Features:
- High-performance PyQt6 QPainter rendering piped directly to ffmpeg
- H.264 High profile, yuv420p, -movflags +faststart
- Original electronic soundtrack at -14.1 LUFS
- Kinetic typography, live waveforms, animated keycaps, UI captures
- Zero static freezes > 1.2s
- Automatic WebVTT subtitles, plain text transcripts, and <=60KB JPEG posters
"""

import os
import sys
import math
import subprocess
from pathlib import Path

# Ensure offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QImage, QPainter, QColor, QFont, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath, QPixmap
)
from PyQt6.QtWidgets import QApplication

# Initialize Qt Application
_app = QApplication.instance() or QApplication(sys.argv)

OUT_DIR = Path("../ghostline_launch_video/run10").resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_ASSETS = OUT_DIR / "raw_assets"
AUDIO_DIR = OUT_DIR / "audio"

# Brand Design Tokens (Fluent 2 Dark)
C_BG_DEEP = QColor("#0b0f19")
C_BG_SLATE = QColor("#0f172a")
C_CARD = QColor(30, 41, 59, 230)
C_BORDER = QColor(71, 85, 105, 180)
C_ACCENT = QColor("#6366f1")
C_ACCENT_GLOW = QColor(99, 102, 241, 50)
C_CYAN = QColor("#38bdf8")
C_EMERALD = QColor("#10b981")
C_AMBER = QColor("#f59e0b")
C_TEXT_WHITE = QColor("#f8fafc")
C_TEXT_MUTED = QColor("#94a3b8")
C_TEXT_DIM = QColor("#64748b")

def ease_out_cubic(x: float) -> float:
    return 1.0 - math.pow(1.0 - max(0.0, min(1.0, x)), 3)

def ease_in_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 4 * x * x * x if x < 0.5 else 1 - math.pow(-2 * x + 2, 3) / 2

def draw_background(p: QPainter, width: int, height: int, t: float):
    """Draws living background: moving grid, radial glow, floating particles (guarantees zero static frames)."""
    p.fillRect(0, 0, width, height, C_BG_DEEP)

    # Ambient moving radial glow
    glow_x = width * 0.5 + math.sin(t * 0.8) * (width * 0.2)
    glow_y = height * 0.4 + math.cos(t * 0.7) * (height * 0.15)
    rg = QRadialGradient(QPointF(glow_x, glow_y), max(width, height) * 0.6)
    rg.setColorAt(0.0, QColor(99, 102, 241, 65))
    rg.setColorAt(0.4, QColor(56, 189, 248, 25))
    rg.setColorAt(1.0, QColor(11, 15, 25, 0))
    p.fillRect(0, 0, width, height, QBrush(rg))

    # Moving coordinate grid
    grid_spacing = 60
    ox = (t * 36.0) % grid_spacing
    oy = (t * 24.0) % grid_spacing
    grid_pen = QPen(QColor(255, 255, 255, 18), 1.0)
    p.setPen(grid_pen)

    x = ox - grid_spacing
    while x < width + grid_spacing:
        p.drawLine(int(x), 0, int(x), height)
        x += grid_spacing

    y = oy - grid_spacing
    while y < height + grid_spacing:
        p.drawLine(0, int(y), width, int(y))
        y += grid_spacing

    # Floating kinetic ambient particles
    for i in range(16):
        px = ((i * 137.5 + t * 45.0 * (1 + (i % 3) * 0.5)) % (width + 40)) - 20
        py = ((i * 93.1 + math.sin(t * 1.5 + i) * 60.0 + i * 70.0) % (height + 40)) - 20
        rad = 3 + (i % 4) * 2
        p.setBrush(QColor(99, 102, 241, 70 if i % 2 == 0 else 50))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(px), int(py), rad * 2, rad * 2)

def draw_keycap(p: QPainter, x: int, y: int, text: str, is_pressed: bool = False, size: int = 56):
    """Draws mechanical 3D keycap."""
    w = max(size + 16, int(len(text) * 18 + 28))
    h = size
    y_off = 4 if is_pressed else 0

    if not is_pressed:
        p.setBrush(QColor(15, 23, 42, 220))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(x, y + 6, w, h, 10, 10)

    face_rect = QRect(x, y + y_off, w, h - 4)
    p.setBrush(QColor("#1e293b") if not is_pressed else QColor("#312e81"))
    border_col = C_ACCENT if is_pressed else QColor("#475569")
    p.setPen(QPen(border_col, 2.0))
    p.drawRoundedRect(face_rect, 10, 10)

    p.setFont(QFont("Consolas", int(size * 0.42), QFont.Weight.Bold))
    p.setPen(C_TEXT_WHITE if not is_pressed else QColor("#c7d2fe"))
    p.drawText(face_rect, Qt.AlignmentFlag.AlignCenter, text)

def draw_glass_card(p: QPainter, rect: QRect, border_color: QColor = C_BORDER):
    """Draws Fluent 2 Dark glassmorphism card."""
    shadow_rect = rect.adjusted(-4, 6, 4, 14)
    p.setBrush(QColor(0, 0, 0, 90))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(shadow_rect, 16, 16)

    p.setBrush(C_CARD)
    p.setPen(QPen(border_color, 1.5))
    p.drawRoundedRect(rect, 14, 14)

def draw_ethical_footer(p: QPainter, width: int, height: int, is_vertical: bool = False):
    """Draws mandatory ethical usage notice."""
    p.setFont(QFont("Segoe UI", 11 if is_vertical else 13, QFont.Weight.Medium))
    p.setPen(C_TEXT_DIM)
    text = "Follow the rules of your school, employer or interviewer."
    y = height - (60 if is_vertical else 44)
    p.drawText(QRect(0, y, width, 30), Qt.AlignmentFlag.AlignCenter, text)

# -------------------------------------------------------------------------
# H1: LAUNCH FILM RENDERER (1920x1080, 92s)
# -------------------------------------------------------------------------
def render_h1_launch_film():
    out_file = OUT_DIR / "Ghostline_Launch_16x9_92s.mp4"
    audio_file = AUDIO_DIR / "h1_audio_92s.wav"
    total_duration = 92.0
    fps = 30
    total_frames = int(total_duration * fps)

    print(f"\n[*] Rendering H1: Launch Film ({out_file.name}, 1920x1080, {total_duration}s)...")
    
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-i", str(audio_file),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(out_file)
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    canvas = QImage(1920, 1080, QImage.Format.Format_ARGB32)

    pm_profile = QPixmap(str(RAW_ASSETS / "app_profile_200.png"))
    pm_hud = QPixmap(str(RAW_ASSETS / "hud_answer_200.png"))

    for frame in range(total_frames):
        t = frame / float(fps)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_background(p, 1920, 1080, t)

        # SCENE 1: COLD OPEN - STUDY QUESTION (0.0s - 5.0s)
        if t < 5.0:
            st = t
            cam_drift = st * 6.0

            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(120, int(90 - cam_drift * 0.2), "SELF-STUDY & ASSESSMENT PRACTICE • SAMPLE DATA")
            
            p.setFont(QFont("Segoe UI Variable Display", 36, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, int(145 - cam_drift * 0.2), "Instant Screen Context Extraction")

            q_rect = QRect(120, int(200 - cam_drift * 0.3), 1680, 720)
            draw_glass_card(p, q_rect)

            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(160, int(250 - cam_drift * 0.3), "QUESTION 18 OF 40 // TIME COMPLEXITY")

            p.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.DemiBold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(160, int(285 - cam_drift * 0.3), 1600, 100),
                       Qt.TextFlag.TextWordWrap,
                       "Which data structure guarantees O(1) minimum element retrieval and O(log n) element insertion?")

            options = [
                ("A", "Singly Linked List with Tail Pointer", False),
                ("B", "Hash Table with Chaining", False),
                ("C", "Binary Min-Heap", st > 3.0),
                ("D", "Unsorted Dynamic Array", False)
            ]
            opt_coords = [(160, 420), (980, 420), (160, 560), (980, 560)]
            for idx, (letter, text, is_hover) in enumerate(options):
                ox, oy = opt_coords[idx]
                oy_adj = int(oy - cam_drift * 0.3)
                opt_rect = QRect(ox, oy_adj, 780, 105)
                b_color = C_ACCENT if is_hover else C_BORDER
                p.setBrush(QColor(15, 23, 42, 220) if not is_hover else QColor(99, 102, 241, 40))
                p.setPen(QPen(b_color, 1.5 if not is_hover else 2.5))
                p.drawRoundedRect(opt_rect, 10, 10)

                p.setFont(QFont("Segoe UI Variable Display", 22, QFont.Weight.Bold))
                p.setPen(C_ACCENT if is_hover else C_TEXT_MUTED)
                p.drawText(ox + 24, oy_adj + 62, f"{letter}.")

                p.setFont(QFont("Segoe UI", 20, QFont.Weight.Normal))
                p.setPen(C_TEXT_WHITE)
                p.drawText(ox + 70, oy_adj + 62, text)

            cur_p = min(1.0, st / 4.0)
            cx = 1500 - cur_p * 650
            cy = 750 - cur_p * 150
            p.setBrush(C_TEXT_WHITE)
            p.setPen(QPen(QColor(0,0,0,150), 2))
            p.drawEllipse(int(cx), int(cy), 14, 14)

        # SCENE 2: HOTKEY PRESS, SCAN SWEEP & ANSWER (5.0s - 14.0s)
        elif t < 14.0:
            st = t - 5.0
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(QRect(0, 70, 1920, 24), Qt.AlignmentFlag.AlignCenter, "INSTANT LOCAL OCR & SOLVE")

            p.setFont(QFont("Segoe UI Variable Display", 42, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(0, 105, 1920, 56), Qt.AlignmentFlag.AlignCenter, "Your AI. On Your PC.")

            is_down = st < 1.0
            draw_keycap(p, 880, 185, "Alt", is_pressed=is_down, size=62)
            draw_keycap(p, 980, 185, "/", is_pressed=is_down, size=62)

            scale_prog = ease_out_cubic(min(1.0, st / 1.2))
            hud_w = int(780 * scale_prog)
            hud_h = int(636 * scale_prog)
            hud_x = (1920 - hud_w) // 2
            hud_y = 290 + int((1.0 - scale_prog) * 40)

            if pm_hud and not pm_hud.isNull():
                p.drawPixmap(hud_x, hud_y, hud_w, hud_h, pm_hud)

            if st < 2.5:
                laser_y = 290 + int((st / 2.5) * hud_h)
                lg = QLinearGradient(0, laser_y, 1920, laser_y)
                lg.setColorAt(0.0, QColor(99, 102, 241, 0))
                lg.setColorAt(0.5, QColor(56, 189, 248, 255))
                lg.setColorAt(1.0, QColor(99, 102, 241, 0))
                p.fillRect(0, laser_y - 2, 1920, 5, QBrush(lg))

        # SCENE 3: LIVE MEETING DUAL-STREAM AUDIO (14.0s - 28.0s)
        elif t < 28.0:
            st = t - 14.0
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(120, 80, "LIVE MEETING & AUDIO COPILOT")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Dual-Stream Meeting Intelligence")

            c1_rect = QRect(120, 190, 800, 220)
            draw_glass_card(p, c1_rect)
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(155, 230, "[CALL AUDIO • WASAPI LOOPBACK]")
            p.setFont(QFont("Segoe UI", 21, QFont.Weight.Medium))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(155, 260, 730, 120), Qt.TextFlag.TextWordWrap,
                       "\"How do you optimize tail latency and guarantee cache coherence across distributed nodes?\"")

            for b in range(16):
                bh = 8 + int(abs(math.sin(t * 7.0 + b * 0.9)) * 42)
                p.fillRect(720 + b * 11, 230 - bh // 2, 6, bh, C_CYAN)

            c2_rect = QRect(120, 440, 800, 170)
            draw_glass_card(p, c2_rect)
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(155, 480, "[YOUR MICROPHONE • INPUT STREAM]")
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_MUTED)
            p.drawText(155, 530, "Listening... (Hardware loopback prevents self-echo)")

            hud_card = QRect(960, 190, 840, 680)
            draw_glass_card(p, hud_card, border_color=C_ACCENT)
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(1000, 240, "SUGGESTED FIRST-PERSON CANDIDATE REPLY")
            p.setFont(QFont("Segoe UI Variable Display", 22, QFont.Weight.Medium))
            p.setPen(C_TEXT_WHITE)

            resp_text = (
                "\"In my work leading distributed memory pipelines, I isolate tail latency using zero-copy "
                "socket buffers and hedged requests to bypass lagging nodes. For cache coherence, I deploy "
                "lease-based invalidation across our Redis cluster to prevent split-brain reads.\""
            )
            char_count = int(min(len(resp_text), st * 35))
            p.drawText(QRect(1000, 280, 760, 500), Qt.TextFlag.TextWordWrap, resp_text[:char_count])

        # SCENE 4: PERSONAL PROFILE GROUNDING (28.0s - 40.0s)
        elif t < 40.0:
            st = t - 28.0
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(120, 80, "CANDIDATE PROFILE GROUNDING")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Speaks Genuinely as You")

            if pm_profile and not pm_profile.isNull():
                p.drawPixmap(120, 190, 1100, 720, pm_profile)

            callout = QRect(1260, 220, 540, 480)
            draw_glass_card(p, callout, border_color=C_EMERALD)
            p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(1300, 270, "HONEST BOUNDARY ENFORCEMENT")
            
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1300, 310, 460, 300), Qt.TextFlag.TextWordWrap,
                       "Ghostline injects your actual education, career history, and tech stack into the copilot prompt.\n\n"
                       "✓ First-person responses\n"
                       "✓ Never claims fake degrees\n"
                       "✓ Acknowledges unknowns honestly")

        # SCENE 5: CHOOSE YOUR AI (LOCAL VS CLOUD) (40.0s - 54.0s)
        elif t < 54.0:
            st = t - 40.0
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(QRect(0, 70, 1920, 24), Qt.AlignmentFlag.AlignCenter, "ARCHITECTURE & PRIVACY SPLIT")

            p.setFont(QFont("Segoe UI Variable Display", 42, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(0, 105, 1920, 56), Qt.AlignmentFlag.AlignCenter, "Complete AI Freedom")

            c_local = QRect(180, 190, 740, 680)
            draw_glass_card(p, c_local, border_color=C_CYAN)
            p.setFont(QFont("Segoe UI Variable Display", 32, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(230, 260, "On This PC (Ollama)")
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(230, 300, 640, 200), Qt.TextFlag.TextWordWrap,
                       "100% offline local inference.\nScreen captures, voice audio, and answers never leave your machine.\nZero network packets.")

            loop_p = (t * 2.0) % 1.0
            p.setPen(QPen(C_CYAN, 3.0, Qt.PenStyle.DashLine))
            p.drawEllipse(450, 560, 200, 200)
            dot_ang = loop_p * 2 * math.pi
            dot_x = 550 + 100 * math.cos(dot_ang)
            dot_y = 660 + 100 * math.sin(dot_ang)
            p.setBrush(C_TEXT_WHITE)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(dot_x) - 8, int(dot_y) - 8, 16, 16)

            c_cloud = QRect(1000, 190, 740, 680)
            draw_glass_card(p, c_cloud, border_color=C_ACCENT)
            p.setFont(QFont("Segoe UI Variable Display", 32, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(1050, 260, "Cloud with Your Key")
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1050, 300, 640, 200), Qt.TextFlag.TextWordWrap,
                       "Groq • xAI • OpenAI • Gemini\nDirect TLS connection with your own API key.\nKeys encrypted locally using Windows DPAPI.")

        # SCENE 6: 3-STEP SETUP SPRINT (54.0s - 64.0s)
        elif t < 64.0:
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(QRect(0, 80, 1920, 24), Qt.AlignmentFlag.AlignCenter, "SETUP IN MINUTES")

            p.setFont(QFont("Segoe UI Variable Display", 42, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(0, 120, 1920, 56), Qt.AlignmentFlag.AlignCenter, "Fast, Clean Installation")

            steps = [
                ("1", "Download", "Installer or portable standalone zip archive for Windows 10 & 11."),
                ("2", "Configure AI", "Pick local Ollama 3B model or enter your cloud provider API key."),
                ("3", "Press Alt + /", "Instant screen solving and live call intelligence everywhere.")
            ]
            for idx, (num, title, desc) in enumerate(steps):
                sx = 140 + idx * 560
                sy = 240
                s_rect = QRect(sx, sy, 520, 560)
                draw_glass_card(p, s_rect)

                p.setFont(QFont("Segoe UI Variable Display", 54, QFont.Weight.ExtraBold))
                p.setPen(C_ACCENT)
                p.drawText(sx + 40, sy + 100, num)

                p.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.Bold))
                p.setPen(C_TEXT_WHITE)
                p.drawText(sx + 40, sy + 170, title)

                p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
                p.setPen(C_TEXT_MUTED)
                p.drawText(QRect(sx + 40, sy + 210, 440, 300), Qt.TextFlag.TextWordWrap, desc)

        # SCENE 7: HOTKEY & SYSTEM TRAY MATRIX (64.0s - 74.0s)
        elif t < 74.0:
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(120, 80, "SHORTCUTS & WORKFLOW")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Global Windows Hotkey Matrix")

            hk_items = [
                ("Alt + /", "Instant Screen Solve", "Scans question under cursor and displays HUD answer"),
                ("Alt + Q", "Live Meeting Copilot", "Toggles dual-stream microphone and loopback audio"),
                ("Alt + T", "Toggle HUD Overlay", "Shows or conceals floating HUD on demand"),
                ("Ctrl + Alt + Q", "Emergency Quit", "Immediately terminates all processes and background audio")
            ]
            for idx, (combo, name, desc) in enumerate(hk_items):
                hx = 120 + (idx % 2) * 860
                hy = 200 + (idx // 2) * 320
                h_rect = QRect(hx, hy, 820, 270)
                draw_glass_card(p, h_rect)

                p.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
                p.setPen(C_CYAN)
                p.drawText(hx + 40, hy + 70, combo)

                p.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Bold))
                p.setPen(C_TEXT_WHITE)
                p.drawText(hx + 40, hy + 130, name)

                p.setFont(QFont("Segoe UI", 17, QFont.Weight.Normal))
                p.setPen(C_TEXT_MUTED)
                p.drawText(QRect(hx + 40, hy + 160, 740, 80), Qt.TextFlag.TextWordWrap, desc)

        # SCENE 8: PRIVACY BASICS (74.0s - 82.0s)
        elif t < 82.0:
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(QRect(0, 80, 1920, 24), Qt.AlignmentFlag.AlignCenter, "SECURITY ARCHITECTURE")

            p.setFont(QFont("Segoe UI Variable Display", 42, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(0, 120, 1920, 56), Qt.AlignmentFlag.AlignCenter, "Your Data Stays Yours")

            cards = [
                ("Windows DPAPI", "Hardware-backed DPAPI encrypts API keys and local profile at rest."),
                ("Zero Telemetry", "No external analytics, tracking scripts, or remote metrics."),
                ("Local Native OCR", "Sub-millisecond Windows OCR library runs completely offline on CPU.")
            ]
            for idx, (title, desc) in enumerate(cards):
                cx = 140 + idx * 560
                cy = 240
                c_rect = QRect(cx, cy, 520, 540)
                draw_glass_card(p, c_rect, border_color=C_EMERALD)

                p.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.Bold))
                p.setPen(C_EMERALD)
                p.drawText(cx + 40, cy + 90, title)

                p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
                p.setPen(C_TEXT_WHITE)
                p.drawText(QRect(cx + 40, cy + 140, 440, 300), Qt.TextFlag.TextWordWrap, desc)

        # SCENE 9: CALL TO ACTION & ETHICAL NOTICE (82.0s - 92.0s)
        else:
            p.setBrush(C_ACCENT)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(900, 200, 120, 120, 28, 28)

            p.setFont(QFont("Segoe UI Variable Display", 72, QFont.Weight.ExtraBold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(900, 200, 120, 120), Qt.AlignmentFlag.AlignCenter, "G")

            p.setFont(QFont("Segoe UI Variable Display", 56, QFont.Weight.Bold))
            p.drawText(QRect(0, 360, 1920, 80), Qt.AlignmentFlag.AlignCenter, "Ghostline")

            p.setFont(QFont("Segoe UI", 24, QFont.Weight.Normal))
            p.setPen(C_TEXT_MUTED)
            p.drawText(QRect(0, 440, 1920, 40), Qt.AlignmentFlag.AlignCenter, "Native Windows Assistive AI & Meeting Copilot")

            pill = QRect(660, 540, 600, 72)
            draw_glass_card(p, pill, border_color=C_ACCENT)
            p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, "ghostline.app  •  github.com/Mohammed-Ayyan/GhostLine")

        draw_ethical_footer(p, 1920, 1080)
        p.end()

        raw_bytes = canvas.bits().asstring(1920 * 1080 * 4)
        proc.stdin.write(raw_bytes)

        if (frame + 1) % 400 == 0 or frame == total_frames - 1:
            pct = ((frame + 1) / total_frames) * 100.0
            print(f"  [+] H1 Frame {frame + 1}/{total_frames} ({pct:.1f}%)")

    proc.stdin.close()
    proc.wait()
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"[OK] H1 Master Render Finished: {out_file} ({size_mb:.2f} MB)")

# -------------------------------------------------------------------------
# H2: HOMEPAGE HERO LOOP (1280x720, 8s, seamless)
# -------------------------------------------------------------------------
def render_h2_hero_loop():
    out_file = OUT_DIR / "Ghostline_Hero_Loop_720p_8s.mp4"
    total_duration = 8.0
    fps = 30
    total_frames = int(total_duration * fps)

    print(f"\n[*] Rendering H2: Homepage Hero Loop ({out_file.name}, 1280x720, {total_duration}s)...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1280x720",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(out_file)
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    canvas = QImage(1280, 720, QImage.Format.Format_ARGB32)

    for frame in range(total_frames):
        t = frame / float(fps)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_background(p, 1280, 720, t)

        q_rect = QRect(80, 100, 1120, 520)
        draw_glass_card(p, q_rect)

        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.setPen(C_ACCENT)
        p.drawText(110, 140, "INSTANT SCREEN QUESTION SOLVE • ALT + /")

        p.setFont(QFont("Segoe UI Variable Display", 22, QFont.Weight.Bold))
        p.setPen(C_TEXT_WHITE)
        p.drawText(QRect(110, 165, 1060, 70), Qt.TextFlag.TextWordWrap,
                   "Which data structure guarantees O(1) minimum retrieval and O(log n) insertion?")

        is_solved = t > 3.0
        c_rect = QRect(110, 260, 1060, 90)
        p.setBrush(QColor(16, 185, 129, 40) if is_solved else QColor(15, 23, 42, 220))
        p.setPen(QPen(C_EMERALD if is_solved else C_BORDER, 2.0 if is_solved else 1.0))
        p.drawRoundedRect(c_rect, 10, 10)

        p.setFont(QFont("Segoe UI Variable Display", 20, QFont.Weight.Bold))
        p.setPen(C_EMERALD if is_solved else C_TEXT_MUTED)
        p.drawText(140, 315, "C. Binary Min-Heap  [✓ VERIFIED ANSWER]")

        if 1.5 <= t <= 3.5:
            lp = (t - 1.5) / 2.0
            ly = int(240 + lp * 220)
            p.fillRect(110, ly, 1060, 4, C_CYAN)

        draw_ethical_footer(p, 1280, 720)
        p.end()

        raw_bytes = canvas.bits().asstring(1280 * 720 * 4)
        proc.stdin.write(raw_bytes)

    proc.stdin.close()
    proc.wait()
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"[OK] H2 Hero Loop Finished: {out_file} ({size_mb:.2f} MB)")

# -------------------------------------------------------------------------
# V1: DOWNLOAD & SETUP TUTORIAL (1920x1080, 140s)
# -------------------------------------------------------------------------
def render_v1_setup():
    out_file = OUT_DIR / "Ghostline_Setup_Tutorial_16x9_140s.mp4"
    audio_file = AUDIO_DIR / "v1_audio_140s.wav"
    total_duration = 140.0
    fps = 30
    total_frames = int(total_duration * fps)

    print(f"\n[*] Rendering V1: Download & Setup Tutorial ({out_file.name}, 1920x1080, {total_duration}s)...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-i", str(audio_file),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(out_file)
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    canvas = QImage(1920, 1080, QImage.Format.Format_ARGB32)

    pm_model = QPixmap(str(RAW_ASSETS / "app_ai_provider_200.png"))
    pm_profile = QPixmap(str(RAW_ASSETS / "app_profile_200.png"))
    pm_gen = QPixmap(str(RAW_ASSETS / "app_general_200.png"))

    for frame in range(total_frames):
        t = frame / float(fps)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_background(p, 1920, 1080, t)

        # STAGE 1: DOWNLOAD & INTEGRITY CHECK (0s - 25s)
        if t < 25.0:
            st = t
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(120, 80, "STAGE 1 • DOWNLOAD & CRYPTOGRAPHIC VERIFICATION")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Download Ghostline for Windows 10 & 11")

            # Download Card
            c_down = QRect(120, 190, 800, 700)
            draw_glass_card(p, c_down)
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(160, 250, "Release Assets (GitHub / Website)")

            items = [
                ("Ghostline-Setup.exe", "Single-file NSIS installer • Installs to LocalAppData"),
                ("Ghostline-Portable.zip", "Zero-install standalone archive • Extract and run"),
                ("SHA256SUMS.txt", "Signed cryptographic hash manifest for integrity verification")
            ]
            for idx, (fn, desc) in enumerate(items):
                iy = 310 + idx * 110
                p.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
                p.setPen(C_TEXT_WHITE)
                p.drawText(160, iy, fn)
                p.setFont(QFont("Segoe UI", 15, QFont.Weight.Normal))
                p.setPen(C_TEXT_MUTED)
                p.drawText(160, iy + 30, desc)

            # PowerShell Hash Card
            c_hash = QRect(960, 190, 840, 700)
            draw_glass_card(p, c_hash, border_color=C_ACCENT)
            p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(1000, 240, "POWERSHELL VERIFICATION COMMAND")

            cmd_text = (
                "PS C:\\Downloads> Get-FileHash Ghostline-Setup.exe -Algorithm SHA256\n\n"
                "Algorithm  Hash\n"
                "---------  ----\n"
                "SHA256     A7B8C9...[Verified Match to SHA256SUMS.txt]\n\n"
                "Status: ✓ Binary integrity 100% verified authentic."
            )
            p.setFont(QFont("Consolas", 16, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1000, 290, 760, 400), Qt.TextFlag.TextWordWrap, cmd_text)

        # STAGE 2: INSTALLATION & SMARTSCREEN NOTE (25s - 60s)
        elif t < 60.0:
            st = t - 25.0
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_AMBER)
            p.drawText(120, 80, "STAGE 2 • INSTALLATION & DEFENDER SMART SCREEN")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Clean LocalAppData Installation")

            # SmartScreen Explanation Card
            c_ss = QRect(120, 190, 800, 700)
            draw_glass_card(p, c_ss, border_color=C_AMBER)
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_AMBER)
            p.drawText(160, 250, "Windows SmartScreen Advisory")

            ss_desc = (
                "Because Ghostline is a new open-source utility and not signed with an expensive "
                "enterprise EV certificate, Windows SmartScreen may show 'Windows protected your PC'.\n\n"
                "How to proceed safely:\n"
                "1. Click 'More info'\n"
                "2. Click 'Run anyway'\n\n"
                "Zero administrative or UAC driver privileges required. Ghostline installs exclusively "
                "to your user directory: %LOCALAPPDATA%\\Programs\\Ghostline."
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(160, 290, 720, 480), Qt.TextFlag.TextWordWrap, ss_desc)

            # Portable Alternative
            c_port = QRect(960, 190, 840, 700)
            draw_glass_card(p, c_port, border_color=C_CYAN)
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(1000, 250, "Zero-Install Portable Alternative")

            port_desc = (
                "Prefer not to run an installer at all?\n\n"
                "• Unzip Ghostline-Portable.zip anywhere on your disk.\n"
                "• Run Ghostline.exe directly.\n"
                "• All configuration is stored locally under %APPDATA%\\Ghostline.\n"
                "• Zero registry tampering, zero background services."
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1000, 290, 760, 400), Qt.TextFlag.TextWordWrap, port_desc)

        # STAGE 3: FIRST RUN WIZARD & AI SELECTION (60s - 95s)
        elif t < 95.0:
            st = t - 60.0
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(120, 80, "STAGE 3 • FIRST-RUN AI ENGINE SELECTION")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Choose Local Ollama or Cloud BYOK")

            if pm_model and not pm_model.isNull():
                p.drawPixmap(120, 190, 1000, 700, pm_model)

            c_guide = QRect(1160, 190, 640, 700)
            draw_glass_card(p, c_guide, border_color=C_CYAN)
            p.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(1200, 250, "Which Should You Pick?")

            guide_text = (
                "Path A: Local Ollama (Recommended for Privacy)\n"
                "• 100% offline inference\n"
                "• Requires 8GB RAM + 3B model\n"
                "• Ghostline auto-detects localhost:11434\n\n"
                "Path B: Cloud Providers (BYOK)\n"
                "• Groq (ultra-low latency)\n"
                "• xAI Grok\n"
                "• OpenAI & Google Gemini\n"
                "• Keys encrypted with Windows DPAPI"
            )
            p.setFont(QFont("Segoe UI", 17, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1200, 290, 560, 480), Qt.TextFlag.TextWordWrap, guide_text)

        # STAGE 4: PROFILE SETUP & IDENTITY (95s - 120s)
        elif t < 120.0:
            st = t - 95.0
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(120, 80, "STAGE 4 • CANDIDATE PROFILE GROUNDING")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Ensure AI Answers Grounded in Your Real History")

            if pm_profile and not pm_profile.isNull():
                p.drawPixmap(120, 190, 1000, 700, pm_profile)

            c_prof = QRect(1160, 190, 640, 700)
            draw_glass_card(p, c_prof, border_color=C_EMERALD)
            p.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(1200, 250, "Why Profile Grounding?")

            prof_text = (
                "In mock interviews and tests, Ghostline never introduces itself as an AI assistant.\n\n"
                "By entering your:\n"
                "• Education & Degree\n"
                "• Work Experience & Role\n"
                "• Core Tech Stack & Projects\n\n"
                "Ghostline formats all generated answers as first-person responses genuine to your real background."
            )
            p.setFont(QFont("Segoe UI", 17, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1200, 290, 560, 480), Qt.TextFlag.TextWordWrap, prof_text)

        # STAGE 5: VERIFY & TRAY TEST (120s - 140s)
        else:
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(120, 80, "STAGE 5 • SYSTEM TRAY & READY")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Ghostline Sits Silently in System Tray")

            c_tray = QRect(120, 190, 1680, 700)
            draw_glass_card(p, c_tray, border_color=C_ACCENT)

            p.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(160, 260, "Setup Complete • Global Hotkeys Active")

            keys = [
                ("Alt + /", "Instant Screen Question Solve"),
                ("Alt + Q", "Live Meeting Audio Copilot"),
                ("Alt + T", "Toggle HUD Overlay"),
                ("Ctrl + Alt + Q", "Emergency Quit")
            ]
            for idx, (hk, desc) in enumerate(keys):
                kx = 160 + (idx % 2) * 800
                ky = 330 + (idx // 2) * 160
                draw_keycap(p, kx, ky, hk.split()[0], False, 52)
                draw_keycap(p, kx + 85, ky, hk.split()[-1], False, 52)
                p.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))
                p.setPen(C_TEXT_WHITE)
                p.drawText(kx + 175, ky + 36, desc)

        draw_ethical_footer(p, 1920, 1080)
        p.end()

        raw_bytes = canvas.bits().asstring(1920 * 1080 * 4)
        proc.stdin.write(raw_bytes)

        if (frame + 1) % 600 == 0 or frame == total_frames - 1:
            pct = ((frame + 1) / total_frames) * 100.0
            print(f"  [+] V1 Frame {frame + 1}/{total_frames} ({pct:.1f}%)")

    proc.stdin.close()
    proc.wait()
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"[OK] V1 Setup Tutorial Master Finished: {out_file} ({size_mb:.2f} MB)")

# -------------------------------------------------------------------------
# V2: HOW TO USE WALKTHROUGH (1920x1080, 180s)
# -------------------------------------------------------------------------
def render_v2_walkthrough():
    out_file = OUT_DIR / "Ghostline_Walkthrough_16x9_180s.mp4"
    audio_file = AUDIO_DIR / "v2_audio_180s.wav"
    total_duration = 180.0
    fps = 30
    total_frames = int(total_duration * fps)

    print(f"\n[*] Rendering V2: How to Use Walkthrough ({out_file.name}, 1920x1080, {total_duration}s)...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-i", str(audio_file),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(out_file)
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    canvas = QImage(1920, 1080, QImage.Format.Format_ARGB32)

    pm_hud = QPixmap(str(RAW_ASSETS / "hud_answer_200.png"))
    pm_audio = QPixmap(str(RAW_ASSETS / "hud_audio_200.png"))

    for frame in range(total_frames):
        t = frame / float(fps)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_background(p, 1920, 1080, t)

        # PART 1: SYSTEM TRAY & STATUS (0s - 30s)
        if t < 30.0:
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(120, 80, "PART 1 • BACKGROUND OPERATION & SYSTEM TRAY")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Unobtrusive Windows Desktop Integration")

            c_tray = QRect(120, 190, 800, 700)
            draw_glass_card(p, c_tray)
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(160, 250, "Windows Notification Area (Tray)")

            tray_info = (
                "Ghostline operates cleanly from your Windows taskbar system tray.\n\n"
                "• Single-click: Opens Quick Action Menu\n"
                "• Right-click: Settings, Diagnostics, Clear Context, Quit\n"
                "• Minimal memory footprint (zero GPU polling when idle)\n"
                "• No intrusive persistent window borders"
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(160, 300, 720, 400), Qt.TextFlag.TextWordWrap, tray_info)

            # Simulated Taskbar
            tb_rect = QRect(960, 480, 840, 120)
            draw_glass_card(p, tb_rect, border_color=C_BORDER)
            p.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
            p.setPen(C_TEXT_MUTED)
            p.drawText(1000, 545, "Windows Taskbar")

            # Tray icon pill
            p.setBrush(C_ACCENT)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(1680, 510, 60, 60, 12, 12)
            p.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1680, 510, 60, 60), Qt.AlignmentFlag.AlignCenter, "G")

        # PART 2: INSTANT SCREEN QUESTION SOLVE (30s - 75s)
        elif t < 75.0:
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(120, 80, "PART 2 • INSTANT SCREEN SOLVE (ALT + /)")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Cursor-Targeted OCR & Markdown Solution")

            draw_keycap(p, 120, 190, "Alt", False, 52)
            draw_keycap(p, 205, 190, "/", False, 52)
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_MUTED)
            p.drawText(280, 226, "Press anywhere over an onscreen question")

            if pm_hud and not pm_hud.isNull():
                p.drawPixmap(120, 270, 780, 630, pm_hud)

            c_solve = QRect(940, 270, 860, 630)
            draw_glass_card(p, c_solve, border_color=C_ACCENT)
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(980, 330, "How Instant Screen Solve Works")

            solve_steps = (
                "1. Sub-Millisecond Windows OCR\n"
                "   Extracts raw text directly from display framebuffer.\n\n"
                "2. Context Parsing\n"
                "   Separates question stem, multiple-choice options, or code block.\n\n"
                "3. Verified Markdown Answer\n"
                "   Highlights optimal solution, time/space complexity, and concise rationale."
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(980, 380, 780, 450), Qt.TextFlag.TextWordWrap, solve_steps)

        # PART 3: LIVE MEETING DUAL-STREAM COPILOT (75s - 120s)
        elif t < 120.0:
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(120, 80, "PART 3 • LIVE MEETING COPILOT (ALT + Q)")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Dual-Stream Meeting Audio Intelligence")

            draw_keycap(p, 120, 190, "Alt", False, 52)
            draw_keycap(p, 205, 190, "Q", False, 52)
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_MUTED)
            p.drawText(280, 226, "Toggles dual audio capture stream")

            c_aud = QRect(120, 270, 800, 630)
            draw_glass_card(p, c_aud, border_color=C_CYAN)
            p.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Bold))
            p.setPen(C_CYAN)
            p.drawText(160, 330, "WASAPI Remote Audio + Microphone")

            for b in range(24):
                bh = 10 + int(abs(math.sin(t * 8.0 + b * 0.7)) * 55)
                p.fillRect(160 + b * 16, 420 - bh // 2, 8, bh, C_CYAN)

            aud_info = (
                "• WASAPI Loopback captures what interviewers say in Teams, Zoom, or Meet.\n"
                "• Dedicated microphone stream captures your speech.\n"
                "• Real-time transcription buffers conversational context.\n"
                "• Automatically generates candid first-person responses."
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(160, 480, 720, 380), Qt.TextFlag.TextWordWrap, aud_info)

            if pm_audio and not pm_audio.isNull():
                p.drawPixmap(960, 270, 840, 630, pm_audio)

        # PART 4: HARDWARE KEYBOARD SIGNALLING (120s - 155s)
        elif t < 155.0:
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(120, 80, "PART 4 • HARDWARE KEYBOARD SIGNALLING")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Invisible Tactile Output via Keyboard LEDs")

            c_led = QRect(120, 190, 1680, 700)
            draw_glass_card(p, c_led, border_color=C_EMERALD)

            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_EMERALD)
            p.drawText(160, 250, "Zero Popups • Screen-Share Invisible Signalling")

            led_desc = (
                "When taking remote assessments with mandatory screen sharing, on-screen notifications "
                "can compromise your screen. Ghostline blinks your physical keyboard LEDs instead:\n\n"
                "Supported Target Keys: Caps Lock • Num Lock • Scroll Lock"
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(160, 290, 1500, 120), Qt.TextFlag.TextWordWrap, led_desc)

            mappings = [
                ("1 Pulse", "Option A (or Choice 1 / True)"),
                ("2 Pulses", "Option B (or Choice 2 / False)"),
                ("3 Pulses", "Option C (or Choice 3)"),
                ("4 Pulses", "Option D (or Choice 4)")
            ]
            for idx, (pulse, meaning) in enumerate(mappings):
                px = 160 + idx * 400
                py = 460
                p_rect = QRect(px, py, 360, 200)
                draw_glass_card(p, p_rect)
                p.setFont(QFont("Segoe UI Variable Display", 28, QFont.Weight.Bold))
                p.setPen(C_EMERALD)
                p.drawText(px + 24, py + 60, pulse)
                p.setFont(QFont("Segoe UI", 17, QFont.Weight.Normal))
                p.setPen(C_TEXT_WHITE)
                p.drawText(QRect(px + 24, py + 95, 310, 80), Qt.TextFlag.TextWordWrap, meaning)

        # PART 5: EMERGENCY HOTKEYS & PRIVACY (155s - 180s)
        else:
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(120, 80, "PART 5 • EMERGENCY CONTROLS & COMPLIANCE")

            p.setFont(QFont("Segoe UI Variable Display", 38, QFont.Weight.Bold))
            p.setPen(C_TEXT_WHITE)
            p.drawText(120, 130, "Instant Killswitch & Privacy Safeguards")

            c_kill = QRect(120, 190, 800, 700)
            draw_glass_card(p, c_kill, border_color=QColor("#ef4444"))
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(QColor("#ef4444"))
            p.drawText(160, 250, "Ctrl + Alt + Q • Emergency Kill")

            kill_text = (
                "Instantly terminates all background threads, stops audio loopbacks, "
                "releases global hotkey hooks, and hides all windows immediately.\n\n"
                "Leaves zero trace in RAM."
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(160, 300, 720, 350), Qt.TextFlag.TextWordWrap, kill_text)

            c_sum = QRect(960, 190, 840, 700)
            draw_glass_card(p, c_sum, border_color=C_ACCENT)
            p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
            p.setPen(C_ACCENT)
            p.drawText(1000, 250, "Assistive AI Best Practices")

            sum_text = (
                "Ghostline is built for study, accessibility, and interview preparation.\n\n"
                "✓ Review suggested answers critically\n"
                "✓ Speak authentically in your own voice\n"
                "✓ Comply with all academic & institutional conduct policies"
            )
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
            p.setPen(C_TEXT_WHITE)
            p.drawText(QRect(1000, 300, 760, 350), Qt.TextFlag.TextWordWrap, sum_text)

        draw_ethical_footer(p, 1920, 1080)
        p.end()

        raw_bytes = canvas.bits().asstring(1920 * 1080 * 4)
        proc.stdin.write(raw_bytes)

        if (frame + 1) % 600 == 0 or frame == total_frames - 1:
            pct = ((frame + 1) / total_frames) * 100.0
            print(f"  [+] V2 Frame {frame + 1}/{total_frames} ({pct:.1f}%)")

    proc.stdin.close()
    proc.wait()
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"[OK] V2 Walkthrough Master Finished: {out_file} ({size_mb:.2f} MB)")

# -------------------------------------------------------------------------
# VERTICAL SHORTS S1 - S5 (1080x1920, 35s each)
# -------------------------------------------------------------------------
def render_vertical_short(
    short_id: str,
    title: str,
    badge: str,
    badge_color: QColor,
    audio_filename: str,
    render_content_fn
):
    out_file = OUT_DIR / f"Ghostline_Short_{short_id}_9x16_35s.mp4"
    audio_file = AUDIO_DIR / audio_filename
    total_duration = 35.0
    fps = 30
    total_frames = int(total_duration * fps)

    print(f"\n[*] Rendering {short_id}: {title} ({out_file.name}, 1080x1920, {total_duration}s)...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1080x1920",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-i", str(audio_file),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(out_file)
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    canvas = QImage(1080, 1920, QImage.Format.Format_ARGB32)

    for frame in range(total_frames):
        t = frame / float(fps)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_background(p, 1080, 1920, t)

        # Header Badge
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        p.setPen(badge_color)
        p.drawText(QRect(0, 140, 1080, 30), Qt.AlignmentFlag.AlignCenter, badge)

        # Title
        p.setFont(QFont("Segoe UI Variable Display", 36, QFont.Weight.Bold))
        p.setPen(C_TEXT_WHITE)
        p.drawText(QRect(60, 180, 960, 110), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, title)

        # Main Scene Content
        render_content_fn(p, t)

        # Ethical Footer
        draw_ethical_footer(p, 1080, 1920, is_vertical=True)
        p.end()

        raw_bytes = canvas.bits().asstring(1080 * 1920 * 4)
        proc.stdin.write(raw_bytes)

        if (frame + 1) % 300 == 0 or frame == total_frames - 1:
            pct = ((frame + 1) / total_frames) * 100.0
            print(f"  [+] {short_id} Frame {frame + 1}/{total_frames} ({pct:.1f}%)")

    proc.stdin.close()
    proc.wait()
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"[OK] {short_id} Master Render Finished: {out_file} ({size_mb:.2f} MB)")

def content_s1_screen(p: QPainter, t: float):
    # Hotkey indicator
    draw_keycap(p, 420, 310, "Alt", False, 60)
    draw_keycap(p, 540, 310, "/", False, 60)

    # Question Card
    q_rect = QRect(80, 420, 920, 520)
    draw_glass_card(p, q_rect)
    p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    p.setPen(C_CYAN)
    p.drawText(120, 480, "SAMPLE CODING ASSESSMENT")

    p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
    p.setPen(C_TEXT_WHITE)
    p.drawText(QRect(120, 510, 840, 100), Qt.TextFlag.TextWordWrap,
               "Which data structure guarantees O(1) minimum retrieval and O(log n) insertion?")

    options = [("A", "Linked List"), ("B", "Hash Table"), ("C", "Binary Min-Heap"), ("D", "Dynamic Array")]
    for idx, (let, txt) in enumerate(options):
        oy = 640 + idx * 70
        is_ans = (let == "C" and t > 2.0)
        p.setBrush(QColor(16, 185, 129, 50) if is_ans else QColor(15, 23, 42, 220))
        p.setPen(QPen(C_EMERALD if is_ans else C_BORDER, 2.0 if is_ans else 1.0))
        p.drawRoundedRect(120, oy, 840, 55, 8, 8)
        p.setFont(QFont("Segoe UI Variable Display", 20, QFont.Weight.Bold))
        p.setPen(C_EMERALD if is_ans else C_TEXT_WHITE)
        p.drawText(145, oy + 37, f"{let}. {txt}" + (" [✓ ANSWER]" if is_ans else ""))

    # Answer Card
    ans_card = QRect(80, 980, 920, 740)
    draw_glass_card(p, ans_card, border_color=C_ACCENT)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_ACCENT)
    p.drawText(120, 1040, "INSTANT HUD BREAKDOWN")

    expl = (
        "Correct Answer: C (Binary Min-Heap)\n\n"
        "• peek(): O(1) time complexity — minimum element sits at root node.\n\n"
        "• insert(): O(log n) time complexity — bubbles up the heap tree.\n\n"
        "• Extract Min: O(log n) time complexity.\n\n"
        "Hash tables offer O(1) lookup on key but O(n) to find minimum without sorting."
    )
    p.setFont(QFont("Segoe UI", 20, QFont.Weight.Normal))
    p.setPen(C_TEXT_WHITE)
    p.drawText(QRect(120, 1080, 840, 600), Qt.TextFlag.TextWordWrap, expl)

def content_s2_meeting(p: QPainter, t: float):
    # Call Audio Stream
    c1 = QRect(80, 340, 920, 360)
    draw_glass_card(p, c1, border_color=C_CYAN)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_CYAN)
    p.drawText(120, 400, "REMOTE CALL AUDIO • WASAPI LOOPBACK")

    for b in range(24):
        bh = 12 + int(abs(math.sin(t * 8.0 + b * 0.8)) * 60)
        p.fillRect(120 + b * 34, 480 - bh // 2, 16, bh, C_CYAN)

    p.setFont(QFont("Segoe UI", 22, QFont.Weight.Medium))
    p.setPen(C_TEXT_WHITE)
    p.drawText(QRect(120, 530, 840, 140), Qt.TextFlag.TextWordWrap,
               "\"How do you optimize tail latency across distributed Redis cache nodes?\"")

    # Copilot Response
    c2 = QRect(80, 740, 920, 980)
    draw_glass_card(p, c2, border_color=C_ACCENT)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_ACCENT)
    p.drawText(120, 800, "REAL-TIME FIRST-PERSON RESPONSE")

    p.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Medium))
    p.setPen(C_TEXT_WHITE)
    resp = (
        "\"In my distributed memory projects, I minimize tail latency by:\n\n"
        "1. Hedged Requests:\n"
        "Send backup requests after the 95th percentile timeout to bypass slow replicas.\n\n"
        "2. Connection Pooling:\n"
        "Reuse TCP connections to eliminate TLS handshake latency.\n\n"
        "3. Lease Invalidation:\n"
        "Prevent stampedes on cache misses using atomic setnx locks.\""
    )
    p.drawText(QRect(120, 840, 840, 840), Qt.TextFlag.TextWordWrap, resp)

def content_s3_grounding(p: QPainter, t: float):
    c_prof = QRect(80, 330, 920, 650)
    draw_glass_card(p, c_prof, border_color=C_EMERALD)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_EMERALD)
    p.drawText(120, 390, "ACTUAL CANDIDATE PROFILE")

    fields = [
        ("Candidate Name", "Ayyan (Software Engineer)"),
        ("Education", "B.S. in Computer Science"),
        ("Core Stack", "Python, C++, Qt, Distributed Systems, PyTorch"),
        ("Honest Boundaries", "Never claim unfamiliar tech; acknowledge gaps honestly")
    ]
    for idx, (k, v) in enumerate(fields):
        fy = 440 + idx * 125
        p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        p.setPen(C_TEXT_MUTED)
        p.drawText(120, fy, k)
        p.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))
        p.setPen(C_TEXT_WHITE)
        p.drawText(QRect(120, fy + 24, 840, 70), Qt.TextFlag.TextWordWrap, v)

    # Prompt injection card
    c_res = QRect(80, 1020, 920, 700)
    draw_glass_card(p, c_res, border_color=C_ACCENT)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_ACCENT)
    p.drawText(120, 1080, "COPILOT GROUNDING RESULT")

    p.setFont(QFont("Segoe UI", 21, QFont.Weight.Normal))
    p.setPen(C_TEXT_WHITE)
    res_text = (
        "Interviewer: \"Tell me about yourself.\"\n\n"
        "Ghostline Output:\n"
        "\"I'm a software engineer specializing in high-performance Python, C++, and Qt desktop systems. "
        "I graduated with a B.S. in Computer Science and focus on building low-latency, privacy-first tools.\"\n\n"
        "✓ Speaks genuinely as candidate\n"
        "✓ Zero AI self-introductions\n"
        "✓ 100% grounded facts"
    )
    p.drawText(QRect(120, 1120, 840, 560), Qt.TextFlag.TextWordWrap, res_text)

def content_s4_offline(p: QPainter, t: float):
    # Offline architecture diagram
    c_arch = QRect(80, 330, 920, 700)
    draw_glass_card(p, c_arch, border_color=C_CYAN)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_CYAN)
    p.drawText(120, 390, "100% AIR-GAPPED ON-DEVICE PIPELINE")

    loop_p = (t * 1.5) % 1.0
    p.setPen(QPen(C_CYAN, 4.0, Qt.PenStyle.DashLine))
    p.drawEllipse(340, 460, 400, 400)
    ang = loop_p * 2 * math.pi
    dot_x = 540 + 200 * math.cos(ang)
    dot_y = 660 + 200 * math.sin(ang)
    p.setBrush(C_TEXT_WHITE)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(int(dot_x) - 12, int(dot_y) - 12, 24, 24)

    p.setFont(QFont("Segoe UI Variable Display", 26, QFont.Weight.Bold))
    p.setPen(C_TEXT_WHITE)
    p.drawText(QRect(120, 620, 840, 80), Qt.AlignmentFlag.AlignCenter, "Localhost Ollama 3B")

    # Benefits
    c_ben = QRect(80, 1070, 920, 650)
    draw_glass_card(p, c_ben, border_color=C_EMERALD)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_EMERALD)
    p.drawText(120, 1130, "PRIVACY GUARANTEES")

    points = [
        "Zero Outbound Packets — Captures and audio never touch the internet.",
        "Local Windows OCR — Native sub-millisecond OCR on local CPU.",
        "Windows DPAPI — Cryptographic hardware key protection at rest.",
        "Zero Telemetry — No analytics, no phone-home, no trackers."
    ]
    for idx, pt in enumerate(points):
        py = 1180 + idx * 115
        p.setFont(QFont("Segoe UI", 19, QFont.Weight.Medium))
        p.setPen(C_TEXT_WHITE)
        p.drawText(QRect(120, py, 840, 95), Qt.TextFlag.TextWordWrap, f"✓ {pt}")

def content_s5_signalling(p: QPainter, t: float):
    # Keyboard diagram
    c_kb = QRect(80, 330, 920, 650)
    draw_glass_card(p, c_kb, border_color=C_EMERALD)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_EMERALD)
    p.drawText(120, 390, "MECHANICAL KEYBOARD LED SIGNALLING")

    # Draw Caps Lock Keycap with LED
    is_led_on = (math.sin(t * 10.0) > 0)
    draw_keycap(p, 360, 470, "Caps Lock", is_pressed=False, size=75)

    led_col = QColor(16, 185, 129, 255 if is_led_on else 60)
    p.setBrush(led_col)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(620, 495, 26, 26)

    p.setFont(QFont("Segoe UI Variable Display", 22, QFont.Weight.Bold))
    p.setPen(C_TEXT_WHITE)
    p.drawText(QRect(120, 590, 840, 60), Qt.AlignmentFlag.AlignCenter, "Tactile Screen-Share Invisible Output")

    p.setFont(QFont("Segoe UI", 18, QFont.Weight.Normal))
    p.setPen(C_TEXT_MUTED)
    p.drawText(QRect(120, 660, 840, 280), Qt.TextFlag.TextWordWrap,
               "Zero desktop notifications appear. Answers are signalled directly to your physical keyboard LED.")

    # Matrix Table
    c_mat = QRect(80, 1020, 920, 700)
    draw_glass_card(p, c_mat, border_color=C_ACCENT)
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.setPen(C_ACCENT)
    p.drawText(120, 1080, "PULSE COUNT TO OPTION MAPPING")

    pulses = [
        ("1 Blink", "Option A  /  Choice 1  /  True"),
        ("2 Blinks", "Option B  /  Choice 2  /  False"),
        ("3 Blinks", "Option C  /  Choice 3"),
        ("4 Blinks", "Option D  /  Choice 4")
    ]
    for idx, (pls, mean) in enumerate(pulses):
        py = 1140 + idx * 125
        p.setFont(QFont("Segoe UI Variable Display", 24, QFont.Weight.Bold))
        p.setPen(C_EMERALD)
        p.drawText(120, py, pls)
        p.setFont(QFont("Segoe UI", 19, QFont.Weight.Normal))
        p.setPen(C_TEXT_WHITE)
        p.drawText(120, py + 36, mean)

# -------------------------------------------------------------------------
# SUBTITLE & TRANSCRIPT GENERATORS
# -------------------------------------------------------------------------
SUBTITLES = {
    "Ghostline_Launch_16x9_92s": [
        ("00:00:00.500", "00:00:05.000", "Instant Screen Context Extraction for self-study and practice."),
        ("00:00:05.000", "00:00:14.000", "Press Alt + / to scan any question and solve locally with your AI."),
        ("00:00:14.000", "00:00:28.000", "Live meeting copilot: WASAPI loopback captures remote audio in real-time."),
        ("00:00:28.000", "00:00:40.000", "Candidate profile grounding: speaks genuinely as you with honest boundaries."),
        ("00:00:40.000", "00:00:54.000", "Complete AI freedom: run 100% offline with Ollama or bring your own cloud key."),
        ("00:00:54.000", "00:01:04.000", "Fast, clean installation in three minutes with zero driver requirements."),
        ("00:01:04.000", "00:01:14.000", "Global hotkeys: Alt + /, Alt + Q, Alt + T, and Ctrl + Alt + Q emergency quit."),
        ("00:01:14.000", "00:01:22.000", "Hardware DPAPI encryption and zero telemetry keep your private data safe."),
        ("00:01:22.000", "00:01:32.000", "Ghostline: Native Windows assistive AI. Follow the rules of your school or employer.")
    ],
    "Ghostline_Setup_Tutorial_16x9_140s": [
        ("00:00:00.500", "00:00:25.000", "Download Ghostline installer or portable zip and verify SHA256 integrity."),
        ("00:00:25.000", "00:01:00.000", "Install to LocalAppData. For SmartScreen, select More Info and Run Anyway."),
        ("00:01:00.000", "00:01:35.000", "Configure your AI: choose local Ollama for full privacy or cloud BYOK."),
        ("00:01:35.000", "00:02:00.000", "Fill out your candidate profile so Ghostline can answer on your behalf."),
        ("00:02:00.000", "00:02:20.000", "Ghostline sits quietly in your system tray. Press Alt + / to begin.")
    ],
    "Ghostline_Walkthrough_16x9_180s": [
        ("00:00:00.500", "00:00:30.000", "Ghostline background operation and Windows system tray overview."),
        ("00:00:30.000", "00:01:15.000", "Instant screen question solve: Alt + / captures question and provides verified answer."),
        ("00:01:15.000", "00:02:00.000", "Live meeting copilot: Alt + Q buffers remote audio and candidate speech."),
        ("00:02:00.000", "00:02:35.000", "Hardware keyboard signalling: blinks Caps, Num, or Scroll Lock LEDs invisibly."),
        ("00:02:35.000", "00:03:00.000", "Emergency killswitch Ctrl + Alt + Q and ethical usage guidelines.")
    ],
    "Ghostline_Short_S1_9x16_35s": [
        ("00:00:00.500", "00:00:12.000", "Instant screen question solve with Ghostline."),
        ("00:00:12.000", "00:00:25.000", "Press Alt + / to run sub-millisecond local OCR on any onscreen question."),
        ("00:00:25.000", "00:00:35.000", "Get verified answers and complexity breakdowns instantly.")
    ],
    "Ghostline_Short_S2_9x16_35s": [
        ("00:00:00.500", "00:00:12.000", "Dual-stream live meeting copilot."),
        ("00:00:12.000", "00:00:25.000", "WASAPI loopback captures remote call audio while your mic captures candidate speech."),
        ("00:00:25.000", "00:00:35.000", "Instant first-person suggested answers for technical discussions.")
    ],
    "Ghostline_Short_S3_9x16_35s": [
        ("00:00:00.500", "00:00:12.000", "Grounded candidate profile copilot."),
        ("00:00:12.000", "00:00:25.000", "Ghostline speaks genuinely as you, using your actual resume and degree."),
        ("00:00:25.000", "00:00:35.000", "Never generic AI answers, never fake claims.")
    ],
    "Ghostline_Short_S4_9x16_35s": [
        ("00:00:00.500", "00:00:12.000", "100% offline local AI on your PC with Ollama."),
        ("00:00:12.000", "00:00:25.000", "Zero network packets. Screen captures and audio never leave your machine."),
        ("00:00:25.000", "00:00:35.000", "Windows DPAPI hardware key security and zero telemetry.")
    ],
    "Ghostline_Short_S5_9x16_35s": [
        ("00:00:00.500", "00:00:12.000", "Stealth keyboard LED signalling."),
        ("00:00:12.000", "00:00:25.000", "Zero desktop popups on screen share. Answers blink your keyboard LEDs."),
        ("00:00:25.000", "00:00:35.000", "1 pulse for A, 2 for B, 3 for C, 4 for D.")
    ]
}

def generate_subtitles_and_posters():
    """Generates WebVTT (.vtt), transcript (.txt), and <=60KB JPEG posters."""
    print("\n[*] Generating WebVTT Subtitles, Text Transcripts, and JPEG Posters...")

    # Posters for all videos
    all_videos = [
        ("Ghostline_Launch_16x9_92s.mp4", 12.0),
        ("Ghostline_Hero_Loop_720p_8s.mp4", 4.0),
        ("Ghostline_Setup_Tutorial_16x9_140s.mp4", 45.0),
        ("Ghostline_Walkthrough_16x9_180s.mp4", 50.0),
        ("Ghostline_Short_S1_9x16_35s.mp4", 15.0),
        ("Ghostline_Short_S2_9x16_35s.mp4", 15.0),
        ("Ghostline_Short_S3_9x16_35s.mp4", 15.0),
        ("Ghostline_Short_S4_9x16_35s.mp4", 15.0),
        ("Ghostline_Short_S5_9x16_35s.mp4", 15.0)
    ]

    for v_name, timestamp in all_videos:
        v_path = OUT_DIR / v_name
        if not v_path.exists():
            continue
        base = v_path.stem
        poster_path = OUT_DIR / f"{base}_poster.jpg"

        # Extract frame as high-efficiency JPEG with quality control (target <= 60KB)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", str(v_path),
            "-vframes", "1",
            "-q:v", "5",  # High quality, compact
            str(poster_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sz_kb = poster_path.stat().st_size / 1024.0
        print(f"  [+] Poster {poster_path.name}: {sz_kb:.1f} KB")

    # Generate VTT and TXT
    for base, cues in SUBTITLES.items():
        vtt_path = OUT_DIR / f"{base}.vtt"
        txt_path = OUT_DIR / f"{base}.txt"

        # WebVTT
        vtt_content = ["WEBVTT", ""]
        txt_content = []
        for idx, (start, end, text) in enumerate(cues, 1):
            vtt_content.append(str(idx))
            vtt_content.append(f"{start} --> {end}")
            vtt_content.append(text)
            vtt_content.append("")
            txt_content.append(f"[{start}] {text}")

        vtt_path.write_text("\n".join(vtt_content), encoding="utf-8")
        txt_path.write_text("\n".join(txt_content), encoding="utf-8")
        print(f"  [+] Subtitles generated: {vtt_path.name} & {txt_path.name}")

# -------------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["h1", "h2", "v1", "v2", "shorts", "meta", "all"], default="all")
    args = parser.parse_args()

    if args.only in ["h1", "all"]:
        render_h1_launch_film()
    if args.only in ["h2", "all"]:
        render_h2_hero_loop()
    if args.only in ["v1", "all"]:
        render_v1_setup()
    if args.only in ["v2", "all"]:
        render_v2_walkthrough()
    if args.only in ["shorts", "all"]:
        render_vertical_short("S1", "Instant Screen Solve in 35s", "FEATURE SPOTLIGHT • ALT + /", C_ACCENT, "s1_audio_35s.wav", content_s1_screen)
        render_vertical_short("S2", "Live Meeting Copilot in 35s", "AUDIO INTELLIGENCE • ALT + Q", C_CYAN, "s2_audio_35s.wav", content_s2_meeting)
        render_vertical_short("S3", "Grounded Identity Copilot in 35s", "HONEST RESUME CONTEXT", C_EMERALD, "s3_audio_35s.wav", content_s3_grounding)
        render_vertical_short("S4", "100% Offline AI on Your PC", "OLLAMA LOCAL ARCHITECTURE", C_CYAN, "s4_audio_35s.wav", content_s4_offline)
        render_vertical_short("S5", "Stealth Keyboard Signalling", "PHYSICAL LED BLINKING", C_EMERALD, "s5_audio_35s.wav", content_s5_signalling)
    if args.only in ["meta", "all"]:
        generate_subtitles_and_posters()

    print("\n[✓] All Master Video Production Completed Successfully!")
