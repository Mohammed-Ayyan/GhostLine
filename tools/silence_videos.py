"""
Ghostline Video Audio Removal and Verification Tool.
Part B: Replaces all video audio tracks with silent AAC tracks without re-encoding video.
Verifies MD5 video stream checksum, duration, volumedetect silence, and faststart.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_MEDIA = REPO_ROOT / "website" / "media"
LAUNCH_VIDEO_DIR = Path("../ghostline_launch_video").resolve()
ARCHIVE_MUSIC_DIR = LAUNCH_VIDEO_DIR / "archive_with_music"
REPORTS_DIR = REPO_ROOT / "reports" / "run15"

def run_cmd(cmd):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=isinstance(cmd, str))
    return res.returncode, res.stdout, res.stderr

def get_video_metadata(filepath):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,pix_fmt,duration",
        "-of", "json",
        str(filepath)
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        raise RuntimeError(f"ffprobe failed for {filepath}: {stderr}")
    data = json.loads(stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    
    return {
        "duration": float(fmt.get("duration", 0.0)),
        "size": int(fmt.get("size", 0)),
        "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else 0,
        "video": {
            "codec": video_stream.get("codec_name") if video_stream else None,
            "width": video_stream.get("width") if video_stream else None,
            "height": video_stream.get("height") if video_stream else None,
            "pix_fmt": video_stream.get("pix_fmt") if video_stream else None,
            "duration": float(video_stream.get("duration", fmt.get("duration", 0.0))) if video_stream else 0.0
        } if video_stream else None,
        "audio": {
            "codec": audio_stream.get("codec_name") if audio_stream else None,
            "duration": float(audio_stream.get("duration", fmt.get("duration", 0.0))) if audio_stream else 0.0
        } if audio_stream else None
    }

def get_video_stream_md5(filepath):
    cmd = ["ffmpeg", "-v", "error", "-i", str(filepath), "-map", "0:v:0", "-f", "md5", "-"]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        raise RuntimeError(f"ffmpeg video md5 failed for {filepath}: {stderr}")
    out = stdout.strip()
    if "=" in out:
        out = out.split("=", 1)[1].strip()
    return out

def get_audio_volume_stats(filepath):
    cmd = ["ffmpeg", "-i", str(filepath), "-af", "volumedetect", "-f", "null", "-"]
    code, stdout, stderr = run_cmd(cmd)
    max_vol = None
    mean_vol = None
    for line in stderr.splitlines():
        if "max_volume:" in line:
            parts = line.split("max_volume:")
            max_vol = parts[1].strip()
        elif "mean_volume:" in line:
            parts = line.split("mean_volume:")
            mean_vol = parts[1].strip()
    return max_vol, mean_vol

def check_faststart(filepath):
    """Check if 'moov' atom appears before 'mdat' in an MP4 file."""
    with open(filepath, "rb") as f:
        data = f.read(1024 * 1024 * 8)
    pos_moov = data.find(b"moov")
    pos_mdat = data.find(b"mdat")
    if pos_moov == -1 or pos_mdat == -1:
        return False
    return pos_moov < pos_mdat

def process_file_to_silent(old_path, output_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", str(old_path),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "32k",
        "-shortest",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        str(output_path)
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        raise RuntimeError(f"ffmpeg conversion failed for {old_path}: {stderr}")

def main():
    print("=" * 80)
    print("GHOSTLINE VIDEO MUSIC REMOVAL PIPELINE (RUN 15 PART B)")
    print("=" * 80)
    
    ARCHIVE_MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Collect all shipped videos
    shipped_files = sorted(list(WEBSITE_MEDIA.glob("*.mp4")))
    print(f"Found {len(shipped_files)} shipped videos in {WEBSITE_MEDIA}")
    
    # 2. Collect master videos if any
    master_files = []
    if LAUNCH_VIDEO_DIR.exists():
        master_files = [f for f in LAUNCH_VIDEO_DIR.glob("*.mp4") if f.is_file() and "archive" not in str(f).lower() and "_temp" not in str(f)]
        run10_dir = LAUNCH_VIDEO_DIR / "run10"
        if run10_dir.exists():
            master_files.extend([f for f in run10_dir.glob("*.mp4") if f.is_file() and "archive" not in str(f).lower() and "_temp" not in str(f)])
    print(f"Found {len(master_files)} master videos in {LAUNCH_VIDEO_DIR}")

    all_targets = shipped_files + master_files
    seen = set()
    targets = []
    for f in all_targets:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            targets.append(f)
            
    results = []
    
    for video_path in targets:
        rel_name = video_path.name
        is_shipped = video_path.parent == WEBSITE_MEDIA.resolve()
        tag = "[SHIPPED]" if is_shipped else "[MASTER] "
        print(f"\n{tag} Processing: {rel_name}")
        
        # Pre-metadata
        old_meta = get_video_metadata(video_path)
        old_v_md5 = get_video_stream_md5(video_path)
        old_max_vol, old_mean_vol = get_audio_volume_stats(video_path)
        
        # Archive original with music before modifying
        archive_dest = ARCHIVE_MUSIC_DIR / f"{video_path.stem}_music_orig{video_path.suffix}"
        if not archive_dest.exists():
            shutil.copy2(video_path, archive_dest)
            print(f"  [x] Archived original to: {archive_dest.name}")
            
        # Create silent temp version
        temp_out = video_path.parent / f"{video_path.stem}_temp_silent.mp4"
        process_file_to_silent(video_path, temp_out)
        
        # Post-metadata
        new_meta = get_video_metadata(temp_out)
        new_v_md5 = get_video_stream_md5(temp_out)
        new_max_vol, new_mean_vol = get_audio_volume_stats(temp_out)
        has_faststart = check_faststart(temp_out)
        
        # Verification gates:
        # 1. Video stream MD5 identical
        v_md5_match = (old_v_md5 == new_v_md5)
        # 2. Duration match within 0.05s
        dur_diff = abs(new_meta["duration"] - old_meta["duration"])
        dur_match = dur_diff <= 0.05
        # 3. Resolution, codec, pix_fmt identical
        old_v = old_meta["video"] or {}
        new_v = new_meta["video"] or {}
        res_match = (old_v.get("width") == new_v.get("width") and 
                     old_v.get("height") == new_v.get("height") and
                     old_v.get("codec") == new_v.get("codec") and
                     old_v.get("pix_fmt") == new_v.get("pix_fmt"))
        # 4. Volume silence (max volume <= -90 dB or -inf)
        is_silent = False
        if new_max_vol is not None:
            if "-inf" in new_max_vol:
                is_silent = True
            else:
                try:
                    val = float(new_max_vol.replace("dB", "").strip())
                    is_silent = (val <= -90.0)
                except ValueError:
                    is_silent = False
        # 5. File size not larger than before (for files that already had audio; for video-only files, allow track header overhead)
        had_audio = old_meta["audio"] is not None
        if had_audio:
            size_ok = new_meta["size"] <= old_meta["size"]
        else:
            size_ok = new_meta["size"] <= (old_meta["size"] + 25000)
        
        print(f"  Old Size: {old_meta['size']:,} bytes -> New Size: {new_meta['size']:,} bytes ({new_meta['size'] / (1024*1024):.2f} MB)")
        print(f"  Duration: {old_meta['duration']:.2f}s -> {new_meta['duration']:.2f}s (diff: {dur_diff:.4f}s)")
        print(f"  Video MD5: {old_v_md5} -> {new_v_md5} (Match: {v_md5_match})")
        print(f"  Old Audio Volume: {old_max_vol} -> New Audio Volume: {new_max_vol} (Silent: {is_silent})")
        print(f"  Faststart: {has_faststart} | Res Match: {res_match} | Size OK: {size_ok}")
        
        all_passed = (v_md5_match and dur_match and res_match and is_silent and has_faststart and size_ok)
        if not all_passed:
            temp_out.unlink(missing_ok=True)
            raise RuntimeError(f"Verification gates failed for {rel_name}: "
                               f"v_md5={v_md5_match}, dur={dur_match}, res={res_match}, "
                               f"silent={is_silent}, faststart={has_faststart}, size={size_ok}")
        
        # Replace atomically
        temp_out.replace(video_path)
        print(f"  [SUCCESS] {rel_name} replaced with verified silent track.")
        
        results.append({
            "name": rel_name,
            "path": str(video_path),
            "is_shipped": is_shipped,
            "old_duration": old_meta["duration"],
            "new_duration": new_meta["duration"],
            "dur_diff": dur_diff,
            "old_size": old_meta["size"],
            "new_size": new_meta["size"],
            "old_video_md5": old_v_md5,
            "new_video_md5": new_v_md5,
            "video_md5_match": v_md5_match,
            "old_max_vol": old_max_vol,
            "new_max_vol": new_max_vol,
            "is_silent": is_silent,
            "faststart": has_faststart,
            "res_codec_match": res_match
        })
        
    # Write report JSON
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_json_path = REPORTS_DIR / "video_silence_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote verification results to {report_json_path}")
    
    # Print summary table
    print("\n" + "=" * 100)
    print(f"{'Filename':<42} | {'Old Size':<10} | {'New Size':<10} | {'Duration':<8} | {'Video MD5':<6} | {'Max Vol':<8}")
    print("-" * 100)
    for r in results:
        v_status = "PASS" if r["video_md5_match"] else "FAIL"
        print(f"{r['name']:<42} | {r['old_size'] / (1024*1024):6.2f} MB | {r['new_size'] / (1024*1024):6.2f} MB | {r['new_duration']:6.2f}s | {v_status:<6} | {r['new_max_vol']}")
    print("=" * 100)

if __name__ == "__main__":
    main()
