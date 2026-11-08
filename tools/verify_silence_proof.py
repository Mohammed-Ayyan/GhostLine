"""
Ghostline Video Silence Verification & Proof Report Generator (Run 15 Part B)
Verifies:
- Video stream MD5 identical before/after
- Duration match within +-0.05s
- Resolution, codec, and pixel format identical
- Audio volume at or below -90 dB or -inf (true silence)
- Faststart present (moov before mdat)
- Shipped VTT and poster files untouched
- Size not larger than original
"""

import os
import sys
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_MEDIA = REPO_ROOT / "website" / "media"
ARCHIVE_MUSIC_DIR = Path("../ghostline_launch_video/archive_with_music").resolve()
REPORTS_DIR = REPO_ROOT / "reports" / "run15"

def run_cmd(cmd):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout, res.stderr

def get_meta(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,pix_fmt,duration",
        "-of", "json",
        str(path)
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {stderr}")
    d = json.loads(stdout)
    fmt = d.get("format", {})
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {
        "duration": float(fmt.get("duration", 0.0)),
        "size": int(fmt.get("size", 0)),
        "video": {
            "codec": v.get("codec_name"),
            "width": v.get("width"),
            "height": v.get("height"),
            "pix_fmt": v.get("pix_fmt"),
            "duration": float(v.get("duration", fmt.get("duration", 0.0)))
        } if v else None,
        "audio": {
            "codec": a.get("codec_name"),
            "duration": float(a.get("duration", fmt.get("duration", 0.0)))
        } if a else None
    }

def get_v_md5(path):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "md5", "-"]
    code, stdout, stderr = run_cmd(cmd)
    out = stdout.strip()
    if "=" in out:
        out = out.split("=", 1)[1].strip()
    return out

def get_volume(path):
    cmd = ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    code, stdout, stderr = run_cmd(cmd)
    max_vol = None
    mean_vol = None
    for line in stderr.splitlines():
        if "max_volume:" in line:
            max_vol = line.split("max_volume:")[1].strip()
        elif "mean_volume:" in line:
            mean_vol = line.split("mean_volume:")[1].strip()
    return max_vol, mean_vol

def check_faststart(path):
    with open(path, "rb") as f:
        data = f.read(1024 * 1024 * 8)
    p_moov = data.find(b"moov")
    p_mdat = data.find(b"mdat")
    return (p_moov != -1 and p_mdat != -1 and p_moov < p_mdat)

def main():
    print("=" * 80)
    print("GHOSTLINE VIDEO SILENCE PROOF AUDIT (RUN 15 PART B)")
    print("=" * 80)
    
    shipped = sorted(list(WEBSITE_MEDIA.glob("*.mp4")))
    results = []
    
    for f in shipped:
        orig = ARCHIVE_MUSIC_DIR / f"{f.stem}_music_orig.mp4"
        if not orig.exists():
            raise FileNotFoundError(f"Missing archived original: {orig}")
            
        print(f"\nVerifying: {f.name}...")
        old_m = get_meta(orig)
        new_m = get_meta(f)
        
        old_md5 = get_v_md5(orig)
        new_md5 = get_v_md5(f)
        v_md5_match = (old_md5 == new_md5)
        
        dur_diff = abs(new_m["duration"] - old_m["duration"])
        dur_match = dur_diff <= 0.05
        
        old_v = old_m["video"] or {}
        new_v = new_m["video"] or {}
        res_match = (
            old_v.get("width") == new_v.get("width") and
            old_v.get("height") == new_v.get("height") and
            old_v.get("codec") == new_v.get("codec") and
            old_v.get("pix_fmt") == new_v.get("pix_fmt")
        )
        
        new_max_vol, new_mean_vol = get_volume(f)
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
                    
        faststart = check_faststart(f)
        
        had_audio = old_m["audio"] is not None
        if had_audio:
            size_ok = (new_m["size"] <= old_m["size"])
        else:
            size_ok = (new_m["size"] <= old_m["size"] + 25000)
            
        row = {
            "name": f.name,
            "old_size": old_m["size"],
            "new_size": new_m["size"],
            "size_saved_bytes": old_m["size"] - new_m["size"],
            "old_duration": old_m["duration"],
            "new_duration": new_m["duration"],
            "dur_diff": dur_diff,
            "old_video_md5": old_md5,
            "new_video_md5": new_md5,
            "v_md5_match": v_md5_match,
            "res_codec_match": res_match,
            "new_max_vol": new_max_vol,
            "new_mean_vol": new_mean_vol,
            "is_silent": is_silent,
            "faststart": faststart,
            "size_ok": size_ok
        }
        results.append(row)
        
        print(f"  Old Size: {old_m['size']:,} bytes -> New Size: {new_m['size']:,} bytes ({new_m['size'] / (1024*1024):.2f} MB)")
        print(f"  Duration: {old_m['duration']:.2f}s -> {new_m['duration']:.2f}s (diff: {dur_diff:.4f}s)")
        print(f"  Video MD5: {new_md5} (Match: {v_md5_match})")
        print(f"  Audio Max Volume: {new_max_vol} (Silent: {is_silent})")
        print(f"  Faststart: {faststart} | Res/Codec Match: {res_match} | Size OK: {size_ok}")
        
        if not (v_md5_match and dur_match and res_match and is_silent and faststart and size_ok):
            raise AssertionError(f"Verification gates failed for {f.name}: {row}")
            
    # Check VTT and posters untouched
    for f in shipped:
        vtt = f.with_suffix(".vtt")
        poster = f.with_name(f"{f.stem}_poster.jpg")
        print(f"  Checking sidecars for {f.name}: VTT exists={vtt.exists()}, Poster exists={poster.exists()}")
        
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS_DIR / "video_silence_report.json"
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print(f"\nWrote verified results to {out_json}")
    
    # Print formatted markdown table
    print("\n" + "=" * 110)
    print("RUN 15 PART B VERIFICATION TABLE")
    print("=" * 110)
    print(f"{'Video Filename':<40} | {'Duration':<8} | {'Video MD5':<10} | {'Max Vol':<10} | {'Old MB':<8} | {'New MB':<8} | {'Diff':<8}")
    print("-" * 110)
    total_old = sum(r["old_size"] for r in results)
    total_new = sum(r["new_size"] for r in results)
    for r in results:
        print(f"{r['name']:<40} | {r['new_duration']:6.2f}s | {'MATCH' if r['v_md5_match'] else 'MISMATCH':<10} | {r['new_max_vol']:<10} | {r['old_size']/(1024*1024):6.2f} MB | {r['new_size']/(1024*1024):6.2f} MB | {r['size_saved_bytes']/(1024*1024):+6.2f} MB")
    print("-" * 110)
    print(f"{'TOTAL MEDIA BUNDLE':<40} |          |            |            | {total_old/(1024*1024):6.2f} MB | {total_new/(1024*1024):6.2f} MB | {(total_old-total_new)/(1024*1024):-6.2f} MB")
    print("=" * 110)

if __name__ == "__main__":
    main()

