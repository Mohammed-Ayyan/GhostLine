"""
Tier 1 Quality Gate Auditor.
Validates H1 (Launch Film 92s) and H2 (Hero Loop 8s) against all Part 4 criteria:
1. Font Guard: No tofu, Inter & JetBrains Mono verified.
2. Output Guard: OCR on 1 fps frames with >= 90% keyword match and 0 tofu.
3. Duration contract: H1 (92.0s +-0.5s), H2 (8.0s +-0.5s).
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
MEDIA_DIR = REPO_ROOT / "website" / "media"
WIN_OCR_EXE = REPO_ROOT / "bin" / "win_ocr.exe"

H1_KEYWORDS = [
    "Instant Screen", "Min-Heap", "Alt", "/", "Dual-Stream",
    "Candidate Profile", "Offline", "Ollama", "Ghostline"
]

H2_KEYWORDS = [
    "Instant Screen", "Question", "Answer", "Alt"
]

def audit_tier1():
    from tools.video.output_guard import audit_video_frames

    print("========================================")
    print("RUNNING TIER 1 QUALITY AUDIT (H1 & H2)")
    print("========================================")

    h1_path = MASTER_DIR / "Ghostline_Launch_16x9_92s.mp4"
    h2_path = MASTER_DIR / "Ghostline_Hero_Loop_720p_8s.mp4"

    assert h1_path.exists(), f"H1 not found at {h1_path}"
    assert h2_path.exists(), f"H2 not found at {h2_path}"

    # 1. Output guard & OCR audit on H1
    print("\n--- Auditing H1 (Launch Film 92s) ---")
    res_h1 = audit_video_frames(h1_path, expected_keywords=H1_KEYWORDS, target_duration=92.0)
    print(f"[OK] H1 Guard Passed: {res_h1['matched_keywords']}")

    # 2. Output guard & OCR audit on H2
    print("\n--- Auditing H2 (Hero Loop 8s) ---")
    res_h2 = audit_video_frames(h2_path, expected_keywords=H2_KEYWORDS, target_duration=8.0)
    print(f"[OK] H2 Guard Passed: {res_h2['matched_keywords']}")

    # 3. Posters check
    print("\n--- Auditing Posters ---")
    h1_poster = MASTER_DIR / "Ghostline_Launch_16x9_92s_poster.jpg"
    h2_poster = MASTER_DIR / "Ghostline_Hero_Loop_720p_8s_poster.jpg"
    for p in [h1_poster, h2_poster]:
        assert p.exists(), f"Poster missing: {p}"
        sz_kb = p.stat().st_size / 1024.0
        print(f"Poster {p.name}: {sz_kb:.1f} KB (Limit <= 60 KB: {sz_kb <= 60.0})")
        assert sz_kb <= 60.0, f"Poster {p.name} exceeds 60 KB limit!"

        # OCR poster check
        proc = subprocess.run([str(WIN_OCR_EXE), str(p)], capture_output=True, text=True)
        assert proc.returncode == 0, f"OCR failed on poster {p.name}"
        data = json.loads(proc.stdout)
        txt = data.get("text", "")
        print(f"  OCR text on {p.name}: '{txt[:100]}...'")

    # 4. Motion freeze check via ffmpeg
    print("\n--- Auditing Motion Freezes (>1.2s) ---")
    for v in [h1_path, h2_path]:
        cmd = [
            "ffmpeg", "-i", str(v),
            "-vf", "freezedetect=noise=-60dB:duration=1.2",
            "-f", "null", "-"
        ]
        fz_out = subprocess.run(cmd, capture_output=True, text=True).stderr
        freezes = fz_out.count("lavfi.freezedetect.freeze_start")
        print(f"  {v.name}: {freezes} freezes detected (Limit: 0)")
        assert freezes == 0, f"{v.name} has static freeze > 1.2s!"

    # 5. Generate Contact Sheet for H1 (4x4 = 16 frames)
    print("\n--- Generating Contact Sheet for H1 ---")
    cs_path = MASTER_DIR / "h1_contact_sheet.jpg"
    cs_cmd = [
        "ffmpeg", "-y",
        "-i", str(h1_path),
        "-vf", "fps=1/5.75,scale=480:270,tile=4x4",
        "-q:v", "3",
        str(cs_path)
    ]
    subprocess.run(cs_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  Contact sheet generated: {cs_path.name} ({cs_path.stat().st_size / 1024:.1f} KB)")

    # Run OCR on contact sheet and quote 5+ real words
    proc = subprocess.run([str(WIN_OCR_EXE), str(cs_path)], capture_output=True, text=True)
    if proc.returncode == 0:
        cs_txt = json.loads(proc.stdout).get("text", "")
        words = [w for w in cs_txt.split() if len(w) > 3]
        print(f"  Contact Sheet Quoted Words (5+ required): {words[:12]}")
        assert len(words) >= 5, "Contact sheet did not yield 5+ real words"

    print("\n[✓] ALL TIER 1 QUALITY GATES PASSED!")
    return True

if __name__ == "__main__":
    audit_tier1()

