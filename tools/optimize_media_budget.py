import os
import subprocess
from pathlib import Path

MEDIA_DIR = Path("website/media").resolve()

# Target bitrates to hit ~80 MB total (well under 90MB budget)
TARGETS = {
    "Ghostline_Walkthrough_16x9_180s.mp4": "1100k", # 180s -> ~25MB
    "Ghostline_Setup_Tutorial_16x9_140s.mp4": "1000k", # 140s -> ~18MB
    "Ghostline_Launch_16x9_92s.mp4": "1200k", # 92s -> ~14MB
    "Ghostline_Short_S1_9x16_35s.mp4": "950k", # 35s -> ~4.2MB
    "Ghostline_Short_S2_9x16_35s.mp4": "950k",
    "Ghostline_Short_S3_9x16_35s.mp4": "950k",
    "Ghostline_Short_S4_9x16_35s.mp4": "950k",
    "Ghostline_Short_S5_9x16_35s.mp4": "950k",
}

print("Optimizing video bitrates to fit comfortably within the 90MB total budget...")
for fname, b_rate in TARGETS.items():
    vpath = MEDIA_DIR / fname
    if not vpath.exists():
        continue
    tmp_out = MEDIA_DIR / f"_opt_{fname}"
    cmd = [
        "ffmpeg", "-y", "-i", str(vpath),
        "-c:v", "libx264", "-preset", "fast",
        "-b:v", b_rate, "-maxrate", str(int(b_rate[:-1])*2)+"k",
        "-bufsize", str(int(b_rate[:-1])*4)+"k",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(tmp_out)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if tmp_out.exists() and tmp_out.stat().st_size > 1000:
        tmp_out.replace(vpath)
        print(f"  [+] Optimized {fname}: {vpath.stat().st_size / (1024*1024):.2f} MB")

total_mb = sum(f.stat().st_size for f in MEDIA_DIR.glob("*")) / (1024 * 1024)
print(f"\nFinal Total website/media/ size: {total_mb:.2f} MB (Budget <= 90MB: {total_mb <= 90.0})")

