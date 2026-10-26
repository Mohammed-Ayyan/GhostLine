"""
Ghostline Step-by-Step Installation & Usage Tutorial Video Generator.
Produces a crisp 1080p 60-80s tutorial video with verified UI captures,
instructive step callouts, progress bar, chapter titles, and audio bed.
"""

import os
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 30

OUTPUT_DIR = os.path.join("website_download", "videos")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TEMP_FRAMES_DIR = os.path.join("scratch_tutorial_frames")
os.makedirs(TEMP_FRAMES_DIR, exist_ok=True)

# Colors
C_BG = (11, 13, 17)
C_SURFACE = (18, 21, 28)
C_CARD = (24, 29, 40)
C_BORDER = (46, 54, 73)
C_ACCENT = (56, 189, 248)
C_EMERALD = (16, 185, 129)
C_GOLD = (250, 204, 21)
C_WHITE = (248, 250, 252)
C_MUTED = (148, 163, 184)
C_DARK = (15, 18, 24)

# Paths to verified artifacts
ARTIFACT_DIR = r"C:\Users\sumiy\.gemini\antigravity-ide\brain\2b1b3398-9e18-420f-a8e4-008427a2b9a7"
IMG_DASHBOARD = os.path.join(ARTIFACT_DIR, "main_dashboard.png")
IMG_SETTINGS = os.path.join(ARTIFACT_DIR, "main_settings.png")
IMG_HUD_ANSWER = os.path.join(ARTIFACT_DIR, "hud_standard_answer.png")
IMG_HUD_AUDIO = os.path.join(ARTIFACT_DIR, "hud_live_audio.png")
IMG_SMARTSCREEN = os.path.join(ARTIFACT_DIR, "smartscreen_expanded_1792941635100.png")
IMG_TASKBAR = os.path.join(ARTIFACT_DIR, "taskbar_tab_1792941655975.png")
IMG_SETUP_GUIDE = os.path.join(ARTIFACT_DIR, "windows_setup_section_1792941612576.png")

MUSIC_TRACK = os.path.join(
    ".agents", "skills", "brag", "assets", "music",
    "happy-beats-business-moves-vol-1-by-ende-dot-app.mp3"
)

# Chapter Definitions
CHAPTERS = [
    {
        "num": "01",
        "title": "Downloading Ghostline for Windows",
        "subtitle": "Choose between the Zero-Setup Portable ZIP and Standard Setup Installer",
        "steps": [
            "Visit the official Ghostline release website.",
            "Portable ZIP (387 MB): Extract anywhere and run without administrative privileges.",
            "Standard Installer (395 MB): Auto-installs to %LOCALAPPDATA% with Start Menu shortcuts.",
            "Optional: Download Setup-Offline-AI.bat for 1-click local model configuration."
        ],
        "image": IMG_SETUP_GUIDE,
        "duration_sec": 8.0
    },
    {
        "num": "02",
        "title": "Verifying Authenticity (SHA-256 Checksum)",
        "subtitle": "Ensure your download is untampered and cryptographically authentic",
        "steps": [
            "Open Windows PowerShell in your Downloads directory.",
            "Run: Get-FileHash -Algorithm SHA256 .\\Ghostline-Setup.exe",
            "Verify the output matches: 1552017645d5c6305dc2a7c3ca9658ecd85c01651f000103d57f02f66b74b51c",
            "For Portable ZIP, confirm: ec40ee74e129683f71f204ca86f98592d72917094f75a2338c6c2d7274775484"
        ],
        "image": IMG_SETUP_GUIDE,
        "duration_sec": 8.0
    },
    {
        "num": "03",
        "title": "Windows Defender SmartScreen Handling",
        "subtitle": "Understanding unknown publisher warnings on open-source software",
        "steps": [
            "Ghostline is an open-source project without a costly enterprise EV signing certificate.",
            "When 'Windows protected your PC' appears, click 'More info'.",
            "Verify the application name: Ghostline-Setup.exe or Ghostline.exe.",
            "Click 'Run anyway' to launch securely without disabling any antivirus shields."
        ],
        "image": IMG_SMARTSCREEN,
        "duration_sec": 8.0
    },
    {
        "num": "04",
        "title": "Installing and Launching Ghostline",
        "subtitle": "First-time desktop launch and Start Menu / Taskbar pinning",
        "steps": [
            "Setup Installer installs cleanly into: %LOCALAPPDATA%\\Programs\\Ghostline.",
            "Double-click Ghostline desktop icon or search 'Ghostline' in Start Menu.",
            "Right-click the Ghostline taskbar ghost icon and select 'Pin to taskbar'.",
            "The app operates 100% locally with zero cloud network traffic."
        ],
        "image": IMG_DASHBOARD,
        "duration_sec": 8.0
    },
    {
        "num": "05",
        "title": "Setting Up Ollama & Local AI Models",
        "subtitle": "Configure your on-device neural reasoning engine",
        "steps": [
            "Install Ollama from https://ollama.com if not already present.",
            "Open Windows Terminal / CMD and pull the verified model: ollama pull phi3:mini",
            "Ollama runs on http://127.0.0.1:11434 with direct hardware acceleration.",
            "Ghostline connects automatically to your local Ollama instance on launch."
        ],
        "image": IMG_SETTINGS,
        "duration_sec": 8.0
    },
    {
        "num": "06",
        "title": "Configuring Global Keyboard Shortcuts",
        "subtitle": "Instant screen capture and HUD control across any application",
        "steps": [
            "Alt + / : Hover over any on-screen question to trigger instant local OCR solve.",
            "Alt + C : Toggle the Ghostline Floating HUD overlay visibility anytime.",
            "Alt + H : Minimize or restore the main dashboard.",
            "All shortcuts can be customized under Settings -> Shortcut Preferences."
        ],
        "image": IMG_SETTINGS,
        "duration_sec": 8.0
    },
    {
        "num": "07",
        "title": "Using Screen Assistance & Floating HUD",
        "subtitle": "On-device OCR question parsing and step-by-step reasoning",
        "steps": [
            "Hover your mouse cursor over an exam question or technical problem.",
            "Press Alt + / : Ghostline captures the bounding region and parses text locally.",
            "The Floating HUD slides in with gold star verified answer badge.",
            "Inspect full rationale, confidence rating (98%+), and local latency (<1s)."
        ],
        "image": IMG_HUD_ANSWER,
        "duration_sec": 9.0
    },
    {
        "num": "08",
        "title": "Audio Panel & Live Transcription",
        "subtitle": "Capture system audio loopback and microphone in real time",
        "steps": [
            "Switch to the Audio Panel tab on the Floating HUD.",
            "Select your audio input device: Microphone or WASAPI System Audio Loopback.",
            "Live speech recognition transcribes technical dialogue directly on-device.",
            "Press 'Solve Active Context' to analyze speech transcripts with your local LLM."
        ],
        "image": IMG_HUD_AUDIO,
        "duration_sec": 9.0
    },
    {
        "num": "09",
        "title": "Troubleshooting & Security Guidelines",
        "subtitle": "Resolving port conflicts, model availability, and antivirus flags",
        "steps": [
            "Port 11434 Error: Run 'ollama serve' or restart the Ollama Windows tray app.",
            "Model Not Found: Verify model presence via 'ollama list'.",
            "Antivirus Quarantine: If false-positive occurs, restore only the single executable path.",
            "Strict Security Rule: NEVER exclude whole folders or disable Real-Time Protection."
        ],
        "image": IMG_SETTINGS,
        "duration_sec": 8.0
    },
    {
        "num": "10",
        "title": "Updating & Clean Uninstallation",
        "subtitle": "Managing updates and removing Ghostline with zero residual traces",
        "steps": [
            "Updates: Download new releases from GitHub or website and run over previous install.",
            "Uninstallation: Open Windows Settings -> Apps -> Installed Apps -> Ghostline -> Uninstall.",
            "Portable ZIP: Simply delete the extracted folder. Zero registry remnants.",
            "Thank you for using Ghostline — 100% Private, On-Device Windows AI!"
        ],
        "image": IMG_DASHBOARD,
        "duration_sec": 8.0
    }
]

def load_font(size, bold=False):
    # Try common Windows fonts
    font_names = ["segoeui.ttf", "segoeuib.ttf", "arial.ttf", "arialbd.ttf"]
    if bold:
        font_names = ["segoeuib.ttf", "arialbd.ttf", "segoeui.ttf"]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_title = load_font(34, bold=True)
font_subtitle = load_font(20, bold=False)
font_step = load_font(20, bold=False)
font_step_bold = load_font(22, bold=True)
font_badge = load_font(18, bold=True)
font_footer = load_font(16, bold=False)

def render_chapter_slide(chapter, chapter_idx, total_chapters, progress_frac):
    im = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(im)

    # Top Header Bar
    draw.rectangle([0, 0, WIDTH, 100], fill=C_SURFACE)
    draw.line([0, 100, WIDTH, 100], fill=C_BORDER, width=2)

    # Brand tag on left
    draw.rounded_rectangle([40, 24, 200, 76], radius=8, fill=C_CARD, outline=C_BORDER, width=1)
    draw.text((56, 36), "GHOSTLINE", font=font_badge, fill=C_ACCENT)
    draw.text((158, 38), "v1.0.0", font=font_footer, fill=C_MUTED)

    # Chapter Number Badge
    badge_text = f"CHAPTER {chapter['num']} OF {total_chapters:02d}"
    draw.rounded_rectangle([220, 24, 430, 76], radius=8, fill=(16, 30, 48), outline=C_ACCENT, width=1)
    draw.text((236, 37), badge_text, font=font_badge, fill=C_ACCENT)

    # Main Chapter Title in Header
    draw.text((450, 26), chapter["title"], font=font_title, fill=C_WHITE)
    draw.text((452, 68), chapter["subtitle"], font=font_subtitle, fill=C_MUTED)

    # Overall Progress Bar
    bar_w = int(WIDTH * progress_frac)
    draw.rectangle([0, 98, bar_w, 102], fill=C_ACCENT)

    # Content Layout: Left Column (Steps Callouts, width 780), Right Column (Image Preview, width 1020)
    # Left Steps Card
    left_x = 40
    left_y = 124
    left_w = 780
    left_h = 916

    draw.rounded_rectangle([left_x, left_y, left_x + left_w, left_y + left_h], radius=16, fill=C_SURFACE, outline=C_BORDER, width=2)

    # Section Heading inside Steps Card
    draw.text((left_x + 32, left_y + 28), "Step-by-Step Instructions", font=load_font(24, bold=True), fill=C_ACCENT)
    draw.line([left_x + 32, left_y + 68, left_x + left_w - 32, left_y + 68], fill=C_BORDER, width=1)

    step_y = left_y + 90
    for i, step_text in enumerate(chapter["steps"]):
        # Step Number Pill
        draw.rounded_rectangle([left_x + 32, step_y, left_x + 72, step_y + 40], radius=8, fill=C_CARD, outline=C_ACCENT, width=1)
        draw.text((left_x + 42, step_y + 8), f"{i+1:02d}", font=load_font(18, bold=True), fill=C_WHITE)

        # Word wrap step text
        words = step_text.split()
        lines = []
        cur_line = []
        for w in words:
            test_line = " ".join(cur_line + [w])
            if draw.textlength(test_line, font=font_step) < 660:
                cur_line.append(w)
            else:
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        line_y = step_y + 6
        for line in lines:
            draw.text((left_x + 90, line_y), line, font=font_step, fill=C_WHITE)
            line_y += 30

        step_y += max(80, len(lines) * 32 + 35)

    # Pro-tip Box at bottom of left column
    tip_y = left_y + left_h - 130
    draw.rounded_rectangle([left_x + 24, tip_y, left_x + left_w - 24, tip_y + 106], radius=12, fill=(16, 25, 36), outline=(32, 60, 90), width=1)
    draw.text((left_x + 40, tip_y + 16), "PRO TIP / SECURITY ASSURANCE:", font=load_font(16, bold=True), fill=C_GOLD)
    draw.text((left_x + 40, tip_y + 44), "Ghostline never sends OCR screen data or speech audio to cloud endpoints.", font=font_footer, fill=C_MUTED)
    draw.text((left_x + 40, tip_y + 68), "All neural processing executes strictly on your local machine.", font=font_footer, fill=C_MUTED)

    # Right Image Preview Card
    right_x = 844
    right_y = 124
    right_w = 1036
    right_h = 916

    draw.rounded_rectangle([right_x, right_y, right_x + right_w, right_y + right_h], radius=16, fill=C_SURFACE, outline=C_BORDER, width=2)
    draw.text((right_x + 32, right_y + 24), "Live Desktop Demonstration", font=load_font(22, bold=True), fill=C_WHITE)
    draw.text((right_x + right_w - 220, right_y + 26), "Windows 11 / 10 Build", font=font_footer, fill=C_MUTED)

    # Load and fit artifact image
    img_path = chapter.get("image")
    if img_path and os.path.exists(img_path):
        try:
            art = Image.open(img_path)
            # Box to fit inside:
            inner_w = right_w - 48
            inner_h = right_h - 80
            art.thumbnail((inner_w, inner_h), Image.Resampling.LANCZOS)
            paste_x = right_x + 24 + (inner_w - art.width) // 2
            paste_y = right_y + 64 + (inner_h - art.height) // 2
            # Draw subtle border behind image
            draw.rectangle([paste_x - 2, paste_y - 2, paste_x + art.width + 1, paste_y + art.height + 1], outline=C_BORDER, width=2)
            im.paste(art, (paste_x, paste_y))
        except Exception as e:
            draw.text((right_x + 40, right_y + 100), f"Preview rendering error: {e}", font=font_subtitle, fill=C_MUTED)
    else:
        draw.text((right_x + 40, right_y + 100), "Demonstration capture available in build.", font=font_subtitle, fill=C_MUTED)

    return im

def build_all_frames():
    print("[*] Generating tutorial video frames...")
    frame_index = 0
    total_duration = sum(ch["duration_sec"] for ch in CHAPTERS)
    cur_time = 0.0

    for ch_idx, chapter in enumerate(CHAPTERS):
        num_frames = int(chapter["duration_sec"] * FPS)
        print(f"    - Chapter {chapter['num']}: {chapter['title']} ({num_frames} frames)")
        base_img = render_chapter_slide(chapter, ch_idx + 1, len(CHAPTERS), cur_time / total_duration)

        # Save base frame
        base_frame_path = os.path.join(TEMP_FRAMES_DIR, f"ch_{ch_idx:02d}_base.png")
        base_img.save(base_frame_path)

        for f in range(num_frames):
            # Write sequential symlink/copy or write directly
            frame_filename = os.path.join(TEMP_FRAMES_DIR, f"frame_{frame_index:05d}.png")
            # For efficiency, if not first frame, copy base frame
            if f == 0:
                base_img.save(frame_filename)
            else:
                # Small micro-transition progress bar update on base image
                frame_progress = (cur_time + (f / FPS)) / total_duration
                # clone and update progress bar only
                f_img = base_img.copy()
                d = ImageDraw.Draw(f_img)
                d.rectangle([0, 98, int(WIDTH * frame_progress), 102], fill=C_ACCENT)
                f_img.save(frame_filename)

            frame_index += 1

        cur_time += chapter["duration_sec"]

    print(f"[OK] Generated {frame_index} frames ({total_duration:.1f} seconds total).")
    return frame_index, total_duration

def assemble_video(total_duration=82.0):
    output_video = os.path.join(OUTPUT_DIR, "ghostline_tutorial.mp4")
    print(f"[*] Assembling video into {output_video} via FFmpeg...")

    input_pattern = os.path.join(TEMP_FRAMES_DIR, "frame_%05d.png")

    # FFmpeg command combining PNG sequence and music bed
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", input_pattern,
        "-i", MUSIC_TRACK,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", f"volume=0.35,afade=t=in:st=0:d=1,afade=t=out:st={total_duration-2}:d=2",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        output_video
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print("[!] FFmpeg compilation failed:")
        print(res.stderr[-500:])
        sys.exit(1)

    print(f"[OK] Successfully compiled tutorial video: {output_video}")
    print(f"    Size: {os.path.getsize(output_video):,} bytes")

    # Generate tutorial poster
    poster_path = os.path.join(OUTPUT_DIR, "ghostline_tutorial_poster.jpg")
    cmd_poster = [
        "ffmpeg", "-y",
        "-ss", "4.0",
        "-i", output_video,
        "-frames:v", "1",
        "-q:v", "2",
        poster_path
    ]
    subprocess.run(cmd_poster, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[OK] Generated poster: {poster_path}")

if __name__ == "__main__":
    assemble_video(82.0)
