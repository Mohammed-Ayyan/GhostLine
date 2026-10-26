"""
Segment 3 Generator: Live Call, Audio Transcription, and Final Result (40-60 seconds)
Produces broadcast-quality 1080p 30fps H.264 video with real PyQt6 UI, Audio HUD, and Meeting window.
Sequence:
- 40-46s: Active interview meeting window on desktop, live audio waveform & WASAPI loopback capture.
- 46-52s: Interviewer speaks question; candidate says "Okay, got it." (classified as acknowledgement, no false answer).
- 52-56s: AI reasoning reveals Live Call Q&A card; previous entries preserved in history stream.
- 56-60s: Click End button (stops capture, preserves history), smooth transition to official closing title lock.
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
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.presentation import PresentedAnswer, TYPE_THEORY
from ghostline.audio.assistant import LiveAudioAssistant

OUTPUT_DIR = root_dir / "recordings" / "segment_3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_VIDEO = OUTPUT_DIR / "segment_3_live_call_and_audio.mp4"
AUDIO_MUSIC = root_dir / ".agents" / "skills" / "brag" / "assets" / "music" / "happy-beats-business-moves-vol-12-by-ende-dot-app.mp3"
SFX_DIR = root_dir / "brag-output-2026-10-26-021000" / "composition" / "assets" / "sfx"
SPEECH_WAV = root_dir / "ghostline" / "fixtures" / "test_speech.wav"

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


def draw_windows_taskbar(painter):
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
    
    # Chevron
    painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    painter.setPen(QColor("#94a3b8"))
    painter.drawText(WIDTH - 175, HEIGHT - 20, "⌃")

    # Volume & Wi-Fi
    painter.setFont(QFont("Segoe UI Symbol", 10))
    painter.drawText(WIDTH - 210, HEIGHT - 20, "🛈  🔊")


def draw_desktop_wallpaper(painter):
    painter.fillRect(0, 0, WIDTH, HEIGHT, QColor("#090d16"))
    from PyQt6.QtGui import QRadialGradient
    rad = QRadialGradient(WIDTH / 2, HEIGHT / 2 - 50, 850)
    rad.setColorAt(0.0, QColor(20, 35, 60, 160))
    rad.setColorAt(0.6, QColor(12, 18, 30, 80))
    rad.setColorAt(1.0, QColor(9, 13, 22, 0))
    painter.fillRect(0, 0, WIDTH, HEIGHT, rad)


def create_meeting_window_pixmap(interviewer_speaking=False, waveform_phase=0.0):
    w, h = 980, 680
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#111827"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Window Title Bar
    p.fillRect(0, 0, w, 44, QColor("#1e293b"))
    p.setPen(QColor("#334155"))
    p.drawLine(0, 44, w, 44)

    # Window title
    p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    p.setPen(QColor("#f8fafc"))
    p.drawText(20, 28, "🔴 Video Meeting — Senior Systems Architect Interview")

    # Window controls
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(w - 75, 28, "—  □  ✕")

    # Sub-bar
    p.fillRect(0, 45, w, 40, QColor("#0f172a"))
    p.setPen(QColor("#10b981"))
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    p.drawText(24, 70, "● WASAPI Loopback Audio Active (48kHz)")
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(w - 200, 70, "Call Duration: 14:22")

    # Video Cards Container
    # 1. Interviewer Card (Top Half)
    card1 = QRect(24, 100, w - 48, 320)
    p.fillRect(card1, QColor("#1e293b"))
    p.setPen(QPen(QColor("#38bdf8" if interviewer_speaking else "#334155"), 2.0 if interviewer_speaking else 1.0))
    p.drawRoundedRect(card1, 10, 10)

    # Avatar Circle
    p.setBrush(QColor("#0284c7"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(card1.center().x() - 40, card1.center().y() - 50, 80, 80)
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
    p.drawText(QRect(card1.center().x() - 40, card1.center().y() - 50, 80, 80), Qt.AlignmentFlag.AlignCenter, "JS")

    # Name Tag
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.setPen(QColor("#f8fafc"))
    p.drawText(40, 130, "Johnathan Sterling (Lead Distributed Systems Interviewer)")

    # Speaking indicator wave on interviewer card
    if interviewer_speaking:
        p.setPen(QColor("#10b981"))
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.drawText(w - 180, 130, "🎙 Speaking...")
        
        # Audio wave bars
        wx = card1.center().x() - 60
        wy = card1.center().y() + 50
        for i in range(12):
            h_bar = int(10 + 25 * np.abs(np.sin(waveform_phase + i * 0.5)))
            p.fillRect(wx + i * 10, wy - h_bar // 2, 6, h_bar, QColor("#38bdf8"))

    # 2. Candidate Card (Bottom Half)
    card2 = QRect(24, 435, w - 48, 220)
    p.fillRect(card2, QColor("#182030"))
    p.setPen(QPen(QColor("#334155"), 1.0))
    p.drawRoundedRect(card2, 10, 10)

    # Candidate Name Tag
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.setPen(QColor("#f8fafc"))
    p.drawText(40, 465, "Candidate (You) — Microphone Connected")

    p.setBrush(QColor("#334155"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(card2.center().x() - 30, card2.center().y() - 20, 60, 60)
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
    p.drawText(QRect(card2.center().x() - 30, card2.center().y() - 20, 60, 60), Qt.AlignmentFlag.AlignCenter, "YOU")

    p.end()
    return QPixmap.fromImage(img)


def draw_caption(painter, text, subtext=""):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    cap_w = 860
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


def draw_closing_brand_card(painter, alpha):
    # Official Ghostline Closing Title Lock
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    overlay_col = QColor(9, 13, 22, int(255 * alpha))
    painter.fillRect(0, 0, WIDTH, HEIGHT, overlay_col)

    cx = WIDTH // 2
    cy = HEIGHT // 2 - 20

    # Glowing Brand Emblem Box
    emblem_w, emblem_h = 90, 90
    emblem_rect = QRect(cx - emblem_w // 2, cy - 140, emblem_w, emblem_h)
    painter.setBrush(QColor("#161a24"))
    painter.setPen(QPen(QColor(56, 189, 248, int(220 * alpha)), 2.5))
    painter.drawRoundedRect(emblem_rect, 20, 20)
    
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI Symbol", 36))
    painter.drawText(emblem_rect, Qt.AlignmentFlag.AlignCenter, "👻")

    # Title
    painter.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
    painter.setPen(QColor(255, 255, 255, int(255 * alpha)))
    painter.drawText(QRect(0, cy - 20, WIDTH, 50), Qt.AlignmentFlag.AlignCenter, "GHOSTLINE")

    # Subtitle
    painter.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
    painter.setPen(QColor(56, 189, 248, int(230 * alpha)))
    painter.drawText(QRect(0, cy + 36, WIDTH, 30), Qt.AlignmentFlag.AlignCenter, "100% Offline AI Assistant for Windows")

    # Pill tags
    tags = "Zero Cloud Packets • Local Ollama phi3:mini • MIT Open Source"
    painter.setFont(QFont("Segoe UI", 13))
    painter.setPen(QColor(148, 163, 184, int(220 * alpha)))
    painter.drawText(QRect(0, cy + 76, WIDTH, 30), Qt.AlignmentFlag.AlignCenter, tags)

    # Call to action badge
    cta_rect = QRect(cx - 180, cy + 125, 360, 48)
    painter.setBrush(QColor(56, 189, 248, int(240 * alpha)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(cta_rect, 24, 24)
    painter.setPen(QColor(11, 13, 17, int(255 * alpha)))
    painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
    painter.drawText(cta_rect, Qt.AlignmentFlag.AlignCenter, "Download v1.0.0 at ghostline.dev")

    painter.restore()


def main():
    print("[*] Launching PyQt6 Engine for Segment 3 (Live Call, Audio Transcription, and Final Result)...")
    app = QApplication.instance() or QApplication(sys.argv)
    from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    # 1. State A: Live Call with Transcripts (before AI answer)
    hud_state_a = QtGhostlineHudOverlay(width=580, height=580, opacity=0.98, is_pinned=True, always_on_top=True)
    hud_state_a.resize(580, 580)
    hud_state_a.set_active_mode("call")
    hud_state_a.set_keyword_chips(["Live Call", "Listening..."])

    hud_state_a.append_transcript("10:45:02", "call", "Interviewer: What are the key trade-offs between B-Tree and LSM-Tree storage architectures?")
    # Acknowledgement turn:
    assistant = LiveAudioAssistant(model_name="phi3:mini")
    is_q, category, conf = assistant.classify_utterance("Okay, got it.")
    hud_state_a.append_transcript("10:45:06", "mic", "You: Okay, got it.")
    hud_state_a.show()
    app.processEvents()
    pix_hud_a = hud_state_a.grab()

    # 2. State B: Substantive Question Answered
    hud_state_b = QtGhostlineHudOverlay(width=580, height=580, opacity=0.98, is_pinned=True, always_on_top=True)
    hud_state_b.resize(580, 580)
    hud_state_b.set_active_mode("call")
    hud_state_b.set_keyword_chips(["Call", "Answered ✓"])

    hud_state_b.append_transcript("10:45:02", "call", "Interviewer: What are the key trade-offs between B-Tree and LSM-Tree storage architectures?")
    hud_state_b.append_transcript("10:45:06", "mic", "You: Okay, got it.")

    entry_ans = hud_state_b.session.create_entry(
        source="call",
        original_text="What are the key trade-offs between B-Tree and LSM-Tree storage engines?",
        detected_question="What are the key trade-offs between B-Tree and LSM-Tree storage engines?",
        question_type=TYPE_THEORY
    )
    pres_ans = PresentedAnswer(
        question_type=TYPE_THEORY,
        badge="Call",
        headline="Storage Engine Trade-offs: B-Tree vs LSM-Tree",
        direct_answer="B-Tree: Optimal Read Latency | LSM-Tree: Optimal Write Throughput",
        explanation="• B-Trees perform in-place page updates; deterministic O(log N) point reads without compaction lag.\n• LSM-Trees append to MemTable/WAL and flush SSTables sequentially; maximizes write IOPS.\n• LSM trade-off: Read and space amplification due to multi-level compaction (Leveled/Size-Tiered).",
        is_validated=True,
        confidence=0.982,
        question_text="What are the key trade-offs between B-Tree and LSM-Tree storage engines?"
    )
    hud_state_b.session.complete_entry(entry_ans.id, pres_ans)
    hud_state_b.add_or_update_card(entry_ans)
    hud_state_b.show()
    app.processEvents()
    pix_hud_b = hud_state_b.grab()

    # 3. State C: Session Ended cleanly
    hud_state_c = QtGhostlineHudOverlay(width=580, height=580, opacity=0.98, is_pinned=True, always_on_top=True)
    hud_state_c.resize(580, 580)
    hud_state_c.set_active_mode("call")
    hud_state_c.set_keyword_chips(["Session Ended", "Preserved"])
    hud_state_c.add_or_update_card(entry_ans)
    hud_state_c.show()
    app.processEvents()
    pix_hud_c = hud_state_c.grab()

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
    meet_x, meet_y = 60, 70
    hud_x, hud_y = WIDTH - 580 - 50, 70

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS # 0.0s to 20.0s (representing 40s to 60s in total film)

        canvas.fill(QColor("#090d16"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_desktop_wallpaper(painter)

        # Draw Video Meeting Window
        is_speaking = (1.0 <= t <= 7.0)
        pix_meet = create_meeting_window_pixmap(interviewer_speaking=is_speaking, waveform_phase=t * 8.0)
        painter.drawPixmap(meet_x, meet_y, pix_meet)

        # -------------------------------------------------------------
        # 0.0s - 6.0s (Film: 40s - 46s): Live Audio Capture & Transcripts
        # -------------------------------------------------------------
        if t < 6.0:
            painter.drawPixmap(hud_x, hud_y, pix_hud_a)
            cur_x = meet_x + 400 + 40 * np.sin(t)
            cur_y = meet_y + 300 + 20 * np.cos(t)
            render_cursor(painter, cur_x, cur_y)
            draw_caption(painter, "Live Call & Interview Audio Capture", "Independent WASAPI loopback and microphone transcription with zero acoustic echo")

        # -------------------------------------------------------------
        # 6.0s - 11.5s (Film: 46s - 51.5s): Question Detection & Filtering
        # -------------------------------------------------------------
        elif t < 11.5:
            painter.drawPixmap(hud_x, hud_y, pix_hud_a)

            # Highlight acknowledgement filter box
            ack_rect = QRect(hud_x + 20, hud_y + 195, 540, 48)
            painter.setPen(QPen(QColor(56, 189, 248, 160), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(ack_rect, 6, 6)

            cur_x = hud_x + 180
            cur_y = hud_y + 215
            render_cursor(painter, cur_x, cur_y)

            draw_caption(painter, "Smart Utterance Classifier Filters Acknowledgements", "'Okay, got it' preserved in transcript • Suppresses redundant AI inference triggers")

        # -------------------------------------------------------------
        # 11.5s - 16.0s (Film: 51.5s - 56s): Verified Q&A Answer Card
        # -------------------------------------------------------------
        elif t < 16.0:
            painter.drawPixmap(hud_x, hud_y, pix_hud_b)
            
            # Cursor hovers over the generated answer card
            cur_x = hud_x + 280
            cur_y = hud_y + 360
            render_cursor(painter, cur_x, cur_y)

            draw_caption(painter, "Instant Technical Synthesis & Explanation", "Structured trade-offs delivered in real time • Previous utterances preserved above")

        # -------------------------------------------------------------
        # 16.0s - 17.5s (Film: 56s - 57.5s): Click End Button Cleanly
        # -------------------------------------------------------------
        elif t < 17.5:
            # Move cursor to End button
            end_btn_x = hud_x + 580 - 45
            end_btn_y = hud_y + 25

            prog = min(1.0, (t - 16.0) / 0.8)
            cur_x = (hud_x + 280) + (end_btn_x - (hud_x + 280)) * ease_in_out(prog)
            cur_y = (hud_y + 360) + (end_btn_y - (hud_y + 360)) * ease_in_out(prog)
            is_click = (16.6 <= t <= 16.8)

            painter.drawPixmap(hud_x, hud_y, pix_hud_b if t < 16.7 else pix_hud_c)
            render_cursor(painter, cur_x, cur_y, is_clicking=is_click)

            draw_caption(painter, "Clean Session Lifecycle & Instant Termination", "End halts all audio captures & workers immediately • Preserves full conversation history")

        # -------------------------------------------------------------
        # 17.5s - 20.0s (Film: 57.5s - 60s): Official Closing Brand Lock
        # -------------------------------------------------------------
        else:
            fade = min(1.0, (t - 17.5) / 0.5)
            draw_closing_brand_card(painter, fade)

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

    # Mix Audio & Speech for Segment 3
    print("[*] Mixing authentic speech, tactile cues, and music for Segment 3...")
    final_video = OUTPUT_DIR / "segment_3_final.mp4"

    # Audio filters:
    # 0: Video
    # 1: Music (volume=0.12)
    # 2: test_speech.wav at 1.0s (Interviewer speaking)
    # 3: click1.ogg at 6.0s (Transcript arrival tick)
    # 4: impactBell_heavy_000.ogg at 11.5s (Answer card reveal)
    # 5: switch10.ogg at 16.7s (End button click)
    # 6: impactBell_heavy_000.ogg at 17.5s (Final brand resolve)
    audio_cmd = [
        "ffmpeg", "-y",
        "-i", str(OUTPUT_VIDEO),
        "-ss", "40.0", "-i", str(AUDIO_MUSIC), # Music continuation from 40s
        "-i", str(SPEECH_WAV),
        "-i", str(SFX_DIR / "click1.ogg"),
        "-i", str(SFX_DIR / "impactBell_heavy_000.ogg"),
        "-i", str(SFX_DIR / "switch10.ogg"),
        "-i", str(SFX_DIR / "impactBell_heavy_000.ogg"),
        "-filter_complex",
        "[1:a]volume=0.12[mus];"
        "[2:a]adelay=1000|1000,volume=1.0[speech];"
        "[3:a]adelay=6000|6000,volume=0.7[s1];"
        "[4:a]adelay=11500|11500,volume=0.85[s2];"
        "[5:a]adelay=16700|16700,volume=0.9[s3];"
        "[6:a]adelay=17500|17500,volume=0.85[s4];"
        "[mus][speech][s1][s2][s3][s4]amix=inputs=6:duration=first:dropout_transition=2[aout]",
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
        print(f"[✓] Segment 3 successfully completed: {OUTPUT_VIDEO} (Duration: 20.0s)")


if __name__ == "__main__":
    main()
