"""
Ghostline Launch Video Production & Encoding Pipeline
Orchestrates high-resolution rendering, Playwright screen capture,
SFX cue audio composition, and FFmpeg H.264/AAC encoding.
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = (ROOT.parent / "ghostline_launch_video").resolve()
ASSETS_DIR = OUT_DIR / "assets"
THUMBNAILS_DIR = OUT_DIR / "thumbnails"
TEMP_DIR = OUT_DIR / "_render_temp"

SFX_DIR = (ROOT / ".agents" / "skills" / "brag" / "assets" / "sfx").resolve()

def ensure_dirs():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

def render_thumbnails(browser):
    print("\n--- 1. Rendering Thumbnails ---")
    thumb_specs = [
        ("thumbnail_1280x720.html", {"width": 1280, "height": 720}, "thumbnail_1280x720.png"),
        ("thumbnail_1080x1350.html", {"width": 1080, "height": 1350}, "thumbnail_1080x1350.png"),
        ("thumbnail_1080x1920.html", {"width": 1080, "height": 1920}, "thumbnail_1080x1920.png"),
    ]

    for html_name, vp, out_name in thumb_specs:
        html_file = ROOT / "video_engine" / html_name
        dest = THUMBNAILS_DIR / out_name
        page = browser.new_page(viewport=vp)
        page.goto(html_file.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(dest))
        page.close()
        print(f"[+] Rendered thumbnail: {dest.name} ({dest.stat().st_size} bytes)")

def build_audio_track(duration_sec, cues, out_aac_path):
    """
    cues is a list of tuples: (time_ms, sfx_relative_path)
    Uses FFmpeg to build a mixed stereo AAC audio track.
    """
    print(f"[*] Assembling audio track ({duration_sec}s, {len(cues)} cues) -> {out_aac_path.name}")
    # Validate SFX files exist
    valid_cues = []
    for t_ms, rel_path in cues:
        p = SFX_DIR / rel_path
        if p.exists():
            valid_cues.append((t_ms, p))
        else:
            print(f"    [!] Warning: SFX not found: {p}")

    if not valid_cues:
        # Generate silent audio track
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration_sec),
            "-c:a", "aac", "-b:a", "192k",
            str(out_aac_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return

    # Build FFmpeg command with inputs and filtergraph
    # Input 0: base silence of full duration
    inputs = [
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration_sec}"
    ]
    filter_chains = []
    mix_labels = ["[0:a]"]

    for idx, (t_ms, sfx_p) in enumerate(valid_cues, start=1):
        inputs.extend(["-i", str(sfx_p)])
        filter_chains.append(f"[{idx}:a]adelay={t_ms}|{t_ms}[d{idx}]")
        mix_labels.append(f"[d{idx}]")

    num_inputs = len(valid_cues) + 1
    filter_chains.append(f"{''.join(mix_labels)}amix=inputs={num_inputs}:duration=first:dropout_transition=0[outa]")

    filter_str = ";".join(filter_chains)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[outa]",
        "-t", str(duration_sec),
        "-c:a", "aac", "-b:a", "192k",
        str(out_aac_path)
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"    [!] Audio filtergraph error: {res.stderr.decode('utf-8', errors='ignore')[:300]}")
        # Fallback to pure silence
        cmd_fb = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration_sec),
            "-c:a", "aac", "-b:a", "192k",
            str(out_aac_path)
        ]
        subprocess.run(cmd_fb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print(f"[+] Audio track ready: {out_aac_path.name}")

def record_html(browser, html_path, width, height, duration_sec, out_webm):
    print(f"[*] Recording browser {width}x{height} for {duration_sec}s -> {out_webm.name}...")
    context = browser.new_context(
        viewport={"width": width, "height": height},
        record_video_dir=str(TEMP_DIR),
        record_video_size={"width": width, "height": height}
    )
    page = context.new_page()
    page.goto(html_path.as_uri(), wait_until="networkidle")

    # Wait for exact duration
    page.wait_for_timeout(int(duration_sec * 1000) + 1000)

    raw_video_path = page.video.path()
    context.close()

    if out_webm.exists():
        out_webm.unlink()
    Path(raw_video_path).rename(out_webm)
    print(f"[+] Browser recording complete: {out_webm.name} ({out_webm.stat().st_size} bytes)")

def mux_final_video(webm_path, audio_path, output_mp4, duration_sec, poster_path=None):
    print(f"[*] Encoding final video -> {output_mp4.name}...")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(webm_path),
        "-i", str(audio_path),
        "-t", str(duration_sec),
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_mp4)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"    [!] Error muxing video: {res.stderr.decode('utf-8', errors='ignore')}")
        raise RuntimeError("FFmpeg encode failed")

    print(f"[+] Output ready: {output_mp4.name} ({output_mp4.stat().st_size} bytes)")

    if poster_path:
        # Extract frame at 2.0s as poster
        cmd_p = [
            "ffmpeg", "-y",
            "-ss", "00:00:02.000",
            "-i", str(output_mp4),
            "-vframes", "1",
            "-q:v", "2",
            str(poster_path)
        ]
        subprocess.run(cmd_p, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if poster_path.exists():
            print(f"[+] Extracted poster frame: {poster_path.name}")

def main():
    ensure_dirs()
    print("=== Ghostline Video Production Pipeline Starting ===")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # Step 1: Render Thumbnails
        render_thumbnails(browser)

        # -------------------------------------------------------------
        # VIDEO A: Main 16:9 Tour (104 seconds)
        # -------------------------------------------------------------
        print("\n--- 2. Producing Video A (16:9 Main Tour) ---")
        html_16x9 = ROOT / "video_engine" / "presentation_16x9.html"
        cues_16x9 = [
            (0, "impact/impactSoft_medium_001.ogg"),
            (8000, "ui/click2.ogg"),
            (18000, "casino/card-slide-1.ogg"),
            (28000, "interface/click_003.ogg"),
            (40000, "interface/switch_007.ogg"),
            (52000, "casino/card-place-1.ogg"),
            (64000, "impact/impactSoft_medium_002.ogg"),
            (76000, "interface/click_002.ogg"),
            (86000, "ui/rollover2.ogg"),
            (96000, "impact/impactBell_heavy_000.ogg"),
        ]
        audio_16x9 = TEMP_DIR / "audio_16x9.aac"
        build_audio_track(104, cues_16x9, audio_16x9)

        webm_16x9 = TEMP_DIR / "raw_16x9.webm"
        record_html(browser, html_16x9, 1920, 1080, 104, webm_16x9)

        out_mp4_16x9 = OUT_DIR / "Ghostline_Launch_16x9_104s.mp4"
        poster_16x9 = OUT_DIR / "Ghostline_Launch_16x9_poster.jpg"
        mux_final_video(webm_16x9, audio_16x9, out_mp4_16x9, 104, poster_16x9)

        # -------------------------------------------------------------
        # VIDEO B: Vertical Cut 9:16 (48 seconds)
        # -------------------------------------------------------------
        print("\n--- 3. Producing Video B (9:16 Vertical Cut) ---")
        html_9x16 = ROOT / "video_engine" / "presentation_9x16.html"
        cues_9x16 = [
            (0, "impact/impactSoft_medium_001.ogg"),
            (6000, "interface/click_003.ogg"),
            (14000, "interface/switch_007.ogg"),
            (22000, "casino/card-slide-1.ogg"),
            (30000, "impact/impactSoft_medium_002.ogg"),
            (38000, "impact/impactBell_heavy_000.ogg"),
        ]
        audio_9x16 = TEMP_DIR / "audio_9x16.aac"
        build_audio_track(48, cues_9x16, audio_9x16)

        webm_9x16 = TEMP_DIR / "raw_9x16.webm"
        record_html(browser, html_9x16, 1080, 1920, 48, webm_9x16)

        out_mp4_9x16 = OUT_DIR / "Ghostline_Launch_9x16_48s.mp4"
        poster_9x16 = OUT_DIR / "Ghostline_Launch_9x16_poster.jpg"
        mux_final_video(webm_9x16, audio_9x16, out_mp4_9x16, 48, poster_9x16)

        # -------------------------------------------------------------
        # VIDEO C: Teaser 9:16 (16 seconds)
        # -------------------------------------------------------------
        print("\n--- 4. Producing Video C (9:16 Teaser) ---")
        html_teaser = ROOT / "video_engine" / "presentation_teaser.html"
        cues_teaser = [
            (0, "impact/impactSoft_medium_001.ogg"),
            (4000, "interface/click_003.ogg"),
            (8000, "interface/switch_007.ogg"),
            (12000, "impact/impactBell_heavy_000.ogg"),
        ]
        audio_teaser = TEMP_DIR / "audio_teaser.aac"
        build_audio_track(16, cues_teaser, audio_teaser)

        webm_teaser = TEMP_DIR / "raw_teaser.webm"
        record_html(browser, html_teaser, 1080, 1920, 16, webm_teaser)

        out_mp4_teaser = OUT_DIR / "Ghostline_Teaser_9x16_16s.mp4"
        poster_teaser = OUT_DIR / "Ghostline_Teaser_9x16_poster.jpg"
        mux_final_video(webm_teaser, audio_teaser, out_mp4_teaser, 16, poster_teaser)

        browser.close()

    # Clean up temp
    try:
        shutil.rmtree(TEMP_DIR)
    except Exception:
        pass

    print("\n[SUCCESS] All video deliverables rendered successfully!")

if __name__ == "__main__":
    main()

