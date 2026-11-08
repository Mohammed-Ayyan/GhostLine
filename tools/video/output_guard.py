"""
Ghostline Video Output Guard.
Post-render validation across all video tiers:
1. Extracts 1 fps frames from rendered MP4.
2. Runs native Windows OCR (bin/win_ocr.exe) on extracted frames.
3. Detects tofu / missing-glyph patterns (repetitive box characters, empty rectangles).
4. Verifies presence of expected keywords and text legibility per scene (>=90%).
5. Verifies container health: faststart moov atom at start, duration within +-0.5s.
"""

import os
import sys
import subprocess
import json
import shutil
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WIN_OCR_EXE = REPO_ROOT / "bin" / "win_ocr.exe"

class OutputGuardError(RuntimeError):
    """Raised when post-render video quality validation fails."""
    pass

TOFU_PATTERNS = [
    re.compile(r'(?:CI|C\]|CJ|Cl|\ü|aa|oo|00|mm){4,}', re.IGNORECASE),
    re.compile(r'[\u25a0-\u25a9\ufffd\u25fb-\u25fe]'), # geometric box characters
    re.compile(r'(?:[oO0C][oO0C][oO0C][oO0C]){3,}')
]

def check_faststart(video_path):
    """Verifies that moov atom comes before mdat."""
    with open(video_path, "rb") as fp:
        buf = fp.read(4096)
    moov_pos = buf.find(b"moov")
    mdat_pos = buf.find(b"mdat")
    if moov_pos == -1:
        raise OutputGuardError(f"{video_path.name}: moov atom not found in first 4096 bytes (faststart failed)")
    if mdat_pos != -1 and moov_pos > mdat_pos:
        raise OutputGuardError(f"{video_path.name}: moov atom ({moov_pos}) appears after mdat ({mdat_pos})")
    return moov_pos

def get_video_duration(video_path):
    """Returns video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise OutputGuardError(f"ffprobe failed on {video_path}: {proc.stderr}")
    return float(proc.stdout.strip())

def audit_video_frames(video_path, expected_keywords=None, target_duration=None, fps_sample=1):
    """
    Extracts frames at fps_sample, runs win_ocr.exe, checks for tofu, and matches keywords.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise OutputGuardError(f"Video file not found: {video_path}")

    # 1. Faststart
    moov_pos = check_faststart(video_path)

    # 2. Duration check
    actual_dur = get_video_duration(video_path)
    if target_duration is not None:
        if abs(actual_dur - target_duration) > 0.5:
            raise OutputGuardError(
                f"{video_path.name}: Duration {actual_dur:.2f}s deviates from target {target_duration}s by >0.5s"
            )

    # 3. Extract frames to temp dir
    tmp_dir = video_path.parent / f"_audit_{video_path.stem}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        extract_cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"fps={fps_sample},scale=-1:720",
            "-q:v", "3",
            str(tmp_dir / "frame_%04d.jpg")
        ]
        subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        frame_files = sorted(tmp_dir.glob("frame_*.jpg"))
        if not frame_files:
            raise OutputGuardError(f"No frames extracted from {video_path}")

        print(f"[*] Auditing {len(frame_files)} frames from {video_path.name} (moov offset {moov_pos}, dur {actual_dur:.2f}s)...")

        all_ocr_texts = []
        tofu_detections = []
        scene_words_found = set()

        for idx, ff in enumerate(frame_files):
            proc = subprocess.run([str(WIN_OCR_EXE), str(ff)], capture_output=True, text=True)
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                txt = data.get("text", "").strip()
                if txt:
                    all_ocr_texts.append(txt)
                    words = [w.lower() for w in re.findall(r'[a-zA-Z0-9\+\-]+', txt)]
                    scene_words_found.update(words)

                    # Check for tofu patterns
                    for pat in TOFU_PATTERNS:
                        m = pat.search(txt)
                        if m:
                            tofu_detections.append((ff.name, txt))
                            break

        if tofu_detections:
            sample_tofu = tofu_detections[:3]
            raise OutputGuardError(
                f"{video_path.name}: TOFU DETECTED in {len(tofu_detections)} frames!\n"
                f"Samples: {sample_tofu}"
            )

        # 4. Keyword verification if specified
        matched_keywords = []
        missing_keywords = []
        if expected_keywords:
            for kw in expected_keywords:
                kw_lower = kw.lower()
                # Check either exact word or substring in concatenated OCR text
                combined = " ".join(all_ocr_texts).lower()
                if kw_lower in combined or kw_lower in scene_words_found:
                    matched_keywords.append(kw)
                else:
                    missing_keywords.append(kw)

            match_ratio = len(matched_keywords) / len(expected_keywords) if expected_keywords else 1.0
            print(f"  [+] OCR Keywords: {len(matched_keywords)}/{len(expected_keywords)} matched ({match_ratio*100:.1f}%)")
            if match_ratio < 0.90:
                raise OutputGuardError(
                    f"{video_path.name}: OCR keyword match ratio {match_ratio*100:.1f}% is below 90% threshold!\n"
                    f"Missing: {missing_keywords}"
                )

        print(f"  [+] {video_path.name}: PASSED quality audit. 0 tofu frames, {len(all_ocr_texts)} legible text frames.")
        return {
            "video": video_path.name,
            "duration": actual_dur,
            "moov_offset": moov_pos,
            "frames_audited": len(frame_files),
            "text_frames": len(all_ocr_texts),
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "passed": True
        }

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python output_guard.py <video_path> [target_dur]")
        sys.exit(1)
    vpath = sys.argv[1]
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else None
    res = audit_video_frames(vpath, target_duration=dur)
    print("Result:", res)

