import os
import subprocess
import time
from pathlib import Path

MEDIA_DIR = Path("website/media").resolve()

for s in ["S1", "S2", "S3", "S4", "S5"]:
    fname = f"Ghostline_Short_{s}_9x16_35s.mp4"
    vpath = MEDIA_DIR / fname
    tmp_out = MEDIA_DIR / f"_tmp_{fname}"
    cmd = [
        "ffmpeg", "-y", "-i", str(vpath),
        "-c:v", "libx264", "-preset", "fast",
        "-b:v", "900k", "-maxrate", "1800k", "-bufsize", "3600k",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(tmp_out)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    if tmp_out.exists() and tmp_out.stat().st_size > 1000:
        if vpath.exists():
            vpath.unlink()
        tmp_out.rename(vpath)
        print(f"  [+] Optimized {fname}: {vpath.stat().st_size / (1024*1024):.2f} MB")

total_mb = sum(f.stat().st_size for f in MEDIA_DIR.glob("*")) / (1024 * 1024)
print(f"\nFinal Total website/media/ size: {total_mb:.2f} MB (Budget <= 90MB: {total_mb <= 90.0})")

