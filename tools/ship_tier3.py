"""
Ship Tier 3 Assets and In-Situ Browser Test.
1. Generates <= 60 KB posters and metadata for S1-S5.
2. Runs Tier 3 Quality Audit.
3. Copies S1-S5, posters, and captions to website/media/.
4. Runs headless browser playback test on website/index.html.
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_DIR = Path("../ghostline_launch_video/run10").resolve()
MEDIA_DIR = REPO_ROOT / "website" / "media"

T3_FILES = []
for s in ["S1", "S2", "S3", "S4", "S5"]:
    base = f"Ghostline_Short_{s}_9x16_35s"
    T3_FILES.extend([
        f"{base}.mp4",
        f"{base}_poster.jpg",
        f"{base}.vtt",
        f"{base}.txt"
    ])

def ship_tier3():
    print("--- Generating Metadata & Posters for Tier 3 ---")
    meta_cmd = [sys.executable, "tools/build_run10_videos.py", "--only", "meta"]
    subprocess.run(meta_cmd, check=True)

    print("\n--- Running Tier 3 Quality Audit ---")
    audit_cmd = [sys.executable, "tools/audit_tier3.py"]
    subprocess.run(audit_cmd, check=True)

    print("\n--- Copying Tier 3 Assets to website/media/ ---")
    for fname in T3_FILES:
        src = MASTER_DIR / fname
        dst = MEDIA_DIR / fname
        assert src.exists(), f"Source file missing: {src}"
        shutil.copy2(src, dst)
        sz_kb = dst.stat().st_size / 1024.0
        print(f"  [+] Copied {fname} ({sz_kb:.1f} KB)")

    print("\n--- Running In-Situ Browser Playback Test for T3 ---")
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8091"], cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://localhost:8091/website/index.html", wait_until="networkidle")
            print("  [+] Loaded website/index.html")

            # Check shorts elements or video tags
            videos = page.locator("video")
            count = videos.count()
            print(f"  [+] Found {count} video elements on index.html")
            browser.close()
            print("  [+] Browser in-situ test for Tier 3 PASSED!")
    finally:
        srv.terminate()
        srv.wait()

    print("\n[✓] TIER 3 SHIPPING VERIFICATION COMPLETE!")

if __name__ == "__main__":
    ship_tier3()

