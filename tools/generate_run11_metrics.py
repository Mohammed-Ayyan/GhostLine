import os
import hashlib
import json
import subprocess
from pathlib import Path

MEDIA_DIR = Path("website/media").resolve()

VIDEOS = [
    ("Ghostline_Launch_16x9_92s.mp4", "1920x1080", 92.0),
    ("Ghostline_Hero_Loop_720p_8s.mp4", "1280x720", 8.0),
    ("Ghostline_Setup_Tutorial_16x9_140s.mp4", "1920x1080", 140.0),
    ("Ghostline_Walkthrough_16x9_180s.mp4", "1920x1080", 180.0),
    ("Ghostline_Short_S1_9x16_35s.mp4", "1080x1920", 35.0),
    ("Ghostline_Short_S2_9x16_35s.mp4", "1080x1920", 35.0),
    ("Ghostline_Short_S3_9x16_35s.mp4", "1080x1920", 35.0),
    ("Ghostline_Short_S4_9x16_35s.mp4", "1080x1920", 35.0),
    ("Ghostline_Short_S5_9x16_35s.mp4", "1080x1920", 35.0),
]

POSTERS = [
    "Ghostline_Launch_16x9_92s_poster.jpg",
    "Ghostline_Hero_Loop_720p_8s_poster.jpg",
    "Ghostline_Setup_Tutorial_16x9_140s_poster.jpg",
    "Ghostline_Walkthrough_16x9_180s_poster.jpg",
    "Ghostline_Short_S1_9x16_35s_poster.jpg",
    "Ghostline_Short_S2_9x16_35s_poster.jpg",
    "Ghostline_Short_S3_9x16_35s_poster.jpg",
    "Ghostline_Short_S4_9x16_35s_poster.jpg",
    "Ghostline_Short_S5_9x16_35s_poster.jpg",
]

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_moov_offset(p):
    with open(p, "rb") as f:
        data = f.read(1024)
        moov_idx = data.find(b"moov")
        if moov_idx != -1:
            return moov_idx - 4
    return -1

def get_duration(p):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except:
        return 0.0

def get_poster_ocr(p):
    cmd = ["bin/win_ocr.exe", str(p)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    text = res.stdout.strip()
    words = text.split()
    return " ".join(words[:12]) + ("..." if len(words) > 12 else "")

print("=== VIDEO METRICS ===")
for vname, res, exp_dur in VIDEOS:
    vpath = MEDIA_DIR / vname
    sz_mb = vpath.stat().st_size / (1024 * 1024)
    sha = sha256_file(vpath)
    moov = get_moov_offset(vpath)
    act_dur = get_duration(vpath)
    print(f"{vname} | {res} | {act_dur:.2f}s | {sz_mb:.2f} MB | moov:{moov} | SHA256:{sha[:16]}...")

print("\n=== POSTER METRICS ===")
for pname in POSTERS:
    ppath = MEDIA_DIR / pname
    sz_kb = ppath.stat().st_size / 1024.0
    sha = sha256_file(ppath)
    ocr_sample = get_poster_ocr(ppath)
    print(f"{pname} | {sz_kb:.1f} KB (<=60KB: {sz_kb<=60.0}) | SHA256:{sha[:16]}... | OCR: '{ocr_sample}'")

total_mb = sum(f.stat().st_size for f in MEDIA_DIR.glob("*")) / (1024 * 1024)
print(f"\nTOTAL MEDIA DIR SIZE: {total_mb:.2f} MB (Budget <=90.0MB: {total_mb <= 90.0})")

