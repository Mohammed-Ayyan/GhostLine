import os
import glob
import subprocess
import json

FORENSIC_DIR = "reports/run11/forensic_frames"
os.makedirs(FORENSIC_DIR, exist_ok=True)

media_files = sorted(glob.glob("website/media/*.mp4"))
print(f"Found {len(media_files)} video files.")

# 1. Extract frames
for vf in media_files:
    base = os.path.splitext(os.path.basename(vf))[0]
    out_pattern = os.path.join(FORENSIC_DIR, f"{base}_f%03d.jpg")
    # Extract 1 frame every 5 seconds or 1 fps for short videos to keep count reasonable
    # For full coverage, let's extract 1 fps
    cmd = [
        "ffmpeg", "-y", "-i", vf,
        "-vf", "fps=1/5,scale=-1:360",
        "-q:v", "4",
        out_pattern
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    extracted = glob.glob(os.path.join(FORENSIC_DIR, f"{base}_f*.jpg"))
    print(f"Extracted {len(extracted)} forensic frames for {base}")

# Also extract poster frames
for pf in sorted(glob.glob("website/media/*_poster.jpg")):
    base = os.path.splitext(os.path.basename(pf))[0]
    out_file = os.path.join(FORENSIC_DIR, f"{base}_forensic.jpg")
    # Copy or scale
    cmd = ["ffmpeg", "-y", "-i", pf, "-vf", "scale=-1:360", "-q:v", "4", out_file]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 2. Run OCR on sample frames of each video and poster
print("\nRunning OCR analysis on posters and sample frames...")
results = {}
for pf in sorted(glob.glob("website/media/*_poster.jpg")):
    name = os.path.basename(pf)
    proc = subprocess.run(["bin/win_ocr.exe", pf], capture_output=True, text=True)
    if proc.returncode == 0:
        data = json.loads(proc.stdout)
        results[name] = data.get("text", "")
    else:
        results[name] = "ERROR"

for vf in media_files:
    base = os.path.splitext(os.path.basename(vf))[0]
    frames = sorted(glob.glob(os.path.join(FORENSIC_DIR, f"{base}_f*.jpg")))
    sample_text = []
    for f in frames[::max(1, len(frames)//3)]:
        proc = subprocess.run(["bin/win_ocr.exe", f], capture_output=True, text=True)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            txt = data.get("text", "").strip()
            if txt:
                sample_text.append(f"{os.path.basename(f)}: '{txt}'")
    results[base] = sample_text

with open("reports/run11/ocr_forensic_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Forensic OCR analysis completed. Results written to reports/run11/ocr_forensic_results.json")

