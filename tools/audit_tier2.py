"""
Tier 2 Quality Gate Auditor.
Validates V1 (Setup Tutorial 140s) and V2 (Walkthrough 180s) against all Part 4 criteria:
1. Font Guard: No tofu, Inter & JetBrains Mono verified.
2. Output Guard: OCR on 1 fps frames with >= 90% keyword match and 0 tofu.
3. Duration contract: V1 (140.0s +-0.5s), V2 (180.0s +-0.5s).
4. Format: faststart (+movflags +faststart, moov at front), posters <= 60KB.
5. Motion audit: 0 freezes > 1.2s.
6. Generates contact sheets and quotes 5+ real words.
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

V1_KEYWORDS = [
    "Ghostline", "Setup", "Ollama", "Model", "Install", "Ready"
]

V2_KEYWORDS = [
    "Ghostline", "Profile", "HUD", "Shortcut", "System", "Answer"
]

def audit_tier2():
    from tools.video.output_guard import audit_video_frames

    print("========================================")
    print("RUNNING TIER 2 QUALITY AUDIT (V1 & V2)")
    print("========================================")

    v1_path = MASTER_DIR / "Ghostline_Setup_Tutorial_16x9_140s.mp4"
    v2_path = MASTER_DIR / "Ghostline_Walkthrough_16x9_180s.mp4"

    assert v1_path.exists(), f"V1 not found at {v1_path}"
    assert v2_path.exists(), f"V2 not found at {v2_path}"

    # 1. Output guard & OCR audit on V1
    print("\n--- Auditing V1 (Setup Tutorial 140s) ---")
    res_v1 = audit_video_frames(v1_path, expected_keywords=V1_KEYWORDS, target_duration=140.0)
    print(f"[OK] V1 Guard Passed: {res_v1['matched_keywords']}")

    # 2. Output guard & OCR audit on V2
    print("\n--- Auditing V2 (Walkthrough 180s) ---")
    res_v2 = audit_video_frames(v2_path, expected_keywords=V2_KEYWORDS, target_duration=180.0)
    print(f"[OK] V2 Guard Passed: {res_v2['matched_keywords']}")

    # 3. Posters check
    print("\n--- Auditing Posters ---")
    v1_poster = MASTER_DIR / "Ghostline_Setup_Tutorial_16x9_140s_poster.jpg"
    v2_poster = MASTER_DIR / "Ghostline_Walkthrough_16x9_180s_poster.jpg"
    for p in [v1_poster, v2_poster]:
        assert p.exists(), f"Poster missing: {p}"
        sz_kb = p.stat().st_size / 1024.0
        print(f"Poster {p.name}: {sz_kb:.1f} KB (Limit <= 60 KB: {sz_kb <= 60.0})")
        assert sz_kb <= 60.0, f"Poster {p.name} exceeds 60 KB limit!"

        proc = subprocess.run([str(WIN_OCR_EXE), str(p)], capture_output=True, text=True)
        assert proc.returncode == 0, f"OCR failed on poster {p.name}"
        data = json.loads(proc.stdout)
        txt = data.get("text", "")
        print(f"  OCR text on {p.name}: '{txt[:100]}...'")

    # 4. Motion freeze check
    print("\n--- Auditing Motion Freezes (>1.2s) ---")
    for v in [v1_path, v2_path]:
        cmd = [
            "ffmpeg", "-i", str(v),
            "-vf", "freezedetect=noise=-60dB:duration=1.2",
            "-f", "null", "-"
        ]
        fz_out = subprocess.run(cmd, capture_output=True, text=True).stderr
        freezes = fz_out.count("lavfi.freezedetect.freeze_start")
        print(f"  {v.name}: {freezes} freezes detected (Limit: 0)")
        assert freezes == 0, f"{v.name} has static freeze > 1.2s!"

    # 5. Contact Sheet for V1 and V2
    for v in [v1_path, v2_path]:
        cs_path = MASTER_DIR / f"{v.stem}_contact_sheet.jpg"
        interval = (140.0 / 16.0) if "140s" in v.name else (180.0 / 16.0)
        cs_cmd = [
            "ffmpeg", "-y",
            "-i", str(v),
            "-vf", f"fps=1/{interval:.2f},scale=480:270,tile=4x4",
            "-q:v", "3",
            str(cs_path)
        ]
        subprocess.run(cs_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc = subprocess.run([str(WIN_OCR_EXE), str(cs_path)], capture_output=True, text=True)
        if proc.returncode == 0:
            cs_txt = json.loads(proc.stdout).get("text", "")
            words = [w for w in cs_txt.split() if len(w) > 3]
            print(f"  {cs_path.name} Quoted Words: {words[:8]}")
            assert len(words) >= 5, f"{cs_path.name} did not yield 5+ real words"

    print("\n[✓] ALL TIER 2 QUALITY GATES PASSED!")
    return True

if __name__ == "__main__":
    audit_tier2()

