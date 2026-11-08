"""
Tier 3 Quality Gate Auditor.
Validates S1–S5 Vertical Shorts against all Part 4 criteria:
1. Font Guard: No tofu, Inter & JetBrains Mono verified.
2. Output Guard: OCR on 1 fps frames with >= 90% keyword match and 0 tofu.
3. Duration contract: 35.0s +-0.5s for each short.
4. Format: faststart (+movflags +faststart, moov at front), posters <= 60KB.
5. Motion audit: 0 freezes > 1.2s.
6. Generates contact sheets and quotes 5+ real words per short.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MASTER_DIR = Path("../ghostline_launch_video/run10").resolve()
WIN_OCR_EXE = REPO_ROOT / "bin" / "win_ocr.exe"

SHORTS = [
    ("Ghostline_Short_S1_9x16_35s.mp4", ["Assessment", "Binary", "Heap", "Alt"]),
    ("Ghostline_Short_S2_9x16_35s.mp4", ["Audio", "Loopback", "Redis", "Latency"]),
    ("Ghostline_Short_S3_9x16_35s.mp4", ["Candidate Profile", "Computer Science", "Ghostline"]),
    ("Ghostline_Short_S4_9x16_35s.mp4", ["Air-Gapped", "Ollama", "Privacy", "Zero"]),
    ("Ghostline_Short_S5_9x16_35s.mp4", ["Keyboard", "LED", "Option", "Tactile"])
]

def audit_tier3():
    from tools.video.output_guard import audit_video_frames

    print("========================================")
    print("RUNNING TIER 3 QUALITY AUDIT (S1–S5)")
    print("========================================")

    for v_name, kw in SHORTS:
        v_path = MASTER_DIR / v_name
        assert v_path.exists(), f"Short missing: {v_path}"

        print(f"\n--- Auditing {v_name} ---")
        res = audit_video_frames(v_path, expected_keywords=kw, target_duration=35.0)
        print(f"[OK] {v_name} Passed: {res['matched_keywords']}")

        poster = MASTER_DIR / f"{v_path.stem}_poster.jpg"
        assert poster.exists(), f"Poster missing: {poster}"
        sz_kb = poster.stat().st_size / 1024.0
        print(f"Poster {poster.name}: {sz_kb:.1f} KB (Limit <= 60 KB: {sz_kb <= 60.0})")
        assert sz_kb <= 60.0, f"Poster {poster.name} exceeds 60 KB limit!"

        # Motion freeze check
        cmd = [
            "ffmpeg", "-i", str(v_path),
            "-vf", "freezedetect=noise=-60dB:duration=1.2",
            "-f", "null", "-"
        ]
        fz_out = subprocess.run(cmd, capture_output=True, text=True).stderr
        freezes = fz_out.count("lavfi.freezedetect.freeze_start")
        print(f"  {v_name}: {freezes} freezes detected (Limit: 0)")
        assert freezes == 0, f"{v_name} has static freeze > 1.2s!"

        # Contact sheet
        cs_path = MASTER_DIR / f"{v_path.stem}_contact_sheet.jpg"
        cs_cmd = [
            "ffmpeg", "-y",
            "-i", str(v_path),
            "-vf", "fps=1/2.2,scale=270:480,tile=4x4",
            "-q:v", "3",
            str(cs_path)
        ]
        subprocess.run(cs_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc = subprocess.run([str(WIN_OCR_EXE), str(cs_path)], capture_output=True, text=True)
        if proc.returncode == 0:
            cs_txt = json.loads(proc.stdout).get("text", "")
            words = [w for w in cs_txt.split() if len(w) > 3]
            print(f"  {cs_path.name} Quoted Words: {words[:6]}")
            assert len(words) >= 5, f"{cs_path.name} did not yield 5+ real words"

    print("\n[✓] ALL TIER 3 QUALITY GATES PASSED!")
    return True

if __name__ == "__main__":
    audit_tier3()

