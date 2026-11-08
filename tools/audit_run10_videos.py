import subprocess
from pathlib import Path

OUT_DIR = Path("../ghostline_launch_video/run10").resolve()
videos = [v for v in OUT_DIR.glob("*.mp4") if not v.name.startswith("h1_test")]
print(f"=== AUDITING {len(videos)} MASTER VIDEOS ===\n")

total_sz = 0
for v in sorted(videos):
    sz_mb = v.stat().st_size / (1024 * 1024)
    total_sz += sz_mb
    with open(v, "rb") as fp:
        buf = fp.read(64)
    moov_pos = buf.find(b"moov")
    faststart = (moov_pos != -1)
    
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,pix_fmt,r_frame_rate,duration",
        "-of", "default=noprint_wrappers=1",
        str(v)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()
    info = dict(line.split("=") for line in res if "=" in line)
    
    # Check freezes
    fz_cmd = [
        "ffmpeg", "-i", str(v),
        "-vf", "freezedetect=noise=-60dB:duration=1.2",
        "-f", "null", "-"
    ]
    fz_out = subprocess.run(fz_cmd, capture_output=True, text=True).stderr
    freeze_count = fz_out.count("lavfi.freezedetect.freeze_start")
    
    print(f"{v.name}:")
    print(f"  Size: {sz_mb:.2f} MB | faststart (offset {moov_pos}): {faststart}")
    print(f"  Resolution: {info.get('width')}x{info.get('height')} | Codec: {info.get('codec_name')} ({info.get('pix_fmt')}) | FPS: {info.get('r_frame_rate')}")
    print(f"  Freezes > 1.2s: {freeze_count}")

print(f"\nTotal Web Video Size: {total_sz:.2f} MB (Budget <= 90MB: {total_sz <= 90.0})")
