"""
Concatenates Segment 1, Segment 2, and Segment 3 into the 60-second Ghostline Product Demo Video.
Also extracts the official poster image and copies the deliverables to website_download and brag-output.
"""

import os
import sys
import subprocess
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent

SEG1 = root_dir / "recordings" / "segment_1" / "segment_1_product_and_scanning.mp4"
SEG2 = root_dir / "recordings" / "segment_2" / "segment_2_hud_tray_integration.mp4"
SEG3 = root_dir / "recordings" / "segment_3" / "segment_3_live_call_and_audio.mp4"

FINAL_DIR = root_dir / "recordings" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)
FINAL_VIDEO = FINAL_DIR / "ghostline_product_demo_60s.mp4"
CONCAT_FILE = FINAL_DIR / "concat_list.txt"

POSTER_IMAGE = FINAL_DIR / "ghostline_demo_poster.jpg"
WEBSITE_VIDEOS_DIR = root_dir / "website_download" / "videos"
WEBSITE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
WEBSITE_VIDEO = WEBSITE_VIDEOS_DIR / "ghostline_launch.mp4"
WEBSITE_POSTER = WEBSITE_VIDEOS_DIR / "ghostline_launch_poster.jpg"

BRAG_OUTPUT = root_dir / "brag-output-2026-10-26-021000" / "brag.mp4"
BRAG_POSTER = root_dir / "brag-output-2026-10-26-021000" / "brag.jpg"


def main():
    print("[*] Checking segment source files...")
    for seg in [SEG1, SEG2, SEG3]:
        if not seg.exists():
            raise FileNotFoundError(f"Missing required segment: {seg}")
        print(f"  [+] Found: {seg.name} ({seg.stat().st_size / (1024*1024):.2f} MB)")

    # Write concat list with forward slashes
    concat_content = f"file '{SEG1.as_posix()}'\nfile '{SEG2.as_posix()}'\nfile '{SEG3.as_posix()}'\n"
    CONCAT_FILE.write_text(concat_content, encoding="utf-8")
    print(f"[*] Wrote concat file: {CONCAT_FILE}")

    # Run ffmpeg filter_complex concat to normalize audio to 48kHz stereo and ensure seamless sync
    print("[*] Concatenating segments into 60s master video with audio normalization...")
    concat_cmd = [
        "ffmpeg", "-y",
        "-i", str(SEG1),
        "-i", str(SEG2),
        "-i", str(SEG3),
        "-filter_complex",
        "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        str(FINAL_VIDEO)
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"[+] Created master video: {FINAL_VIDEO} ({FINAL_VIDEO.stat().st_size / (1024*1024):.2f} MB)")

    # Verify duration with ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(FINAL_VIDEO)
    ]
    dur_str = subprocess.check_output(probe_cmd).decode().strip()
    print(f"[+] Master Video Duration: {dur_str}s (Expected: ~60.0s)")

    # Extract high-res poster frame at t=17.5s (mcq reticle + floating HUD settled)
    print("[*] Extracting master poster frame...")
    poster_cmd = [
        "ffmpeg", "-y",
        "-ss", "17.5",
        "-i", str(FINAL_VIDEO),
        "-frames:v", "1",
        "-q:v", "2",
        str(POSTER_IMAGE)
    ]
    subprocess.run(poster_cmd, check=True)
    print(f"[+] Generated poster image: {POSTER_IMAGE}")

    # Copy to website and brag directories
    import shutil
    shutil.copy2(FINAL_VIDEO, WEBSITE_VIDEO)
    shutil.copy2(POSTER_IMAGE, WEBSITE_POSTER)
    print(f"[+] Deployed to website: {WEBSITE_VIDEO} & {WEBSITE_POSTER}")

    if BRAG_OUTPUT.parent.exists():
        shutil.copy2(FINAL_VIDEO, BRAG_OUTPUT)
        shutil.copy2(POSTER_IMAGE, BRAG_POSTER)
        print(f"[+] Updated brag artifact: {BRAG_OUTPUT}")


if __name__ == "__main__":
    main()
