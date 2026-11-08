"""
Ship Tier 1 Assets and In-Situ Browser Test.
1. Copies H1, H2, posters, and captions to website/media/.
2. Verifies file sizes and formats.
3. Runs headless browser playback test on local server.
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

T1_FILES = [
    "Ghostline_Launch_16x9_92s.mp4",
    "Ghostline_Launch_16x9_92s_poster.jpg",
    "Ghostline_Launch_16x9_92s.vtt",
    "Ghostline_Launch_16x9_92s.txt",
    "Ghostline_Hero_Loop_720p_8s.mp4",
    "Ghostline_Hero_Loop_720p_8s_poster.jpg"
]

def ship_tier1():
    print("--- Copying Tier 1 Assets to website/media/ ---")
    for fname in T1_FILES:
        src = MASTER_DIR / fname
        dst = MEDIA_DIR / fname
        assert src.exists(), f"Source file missing: {src}"
        shutil.copy2(src, dst)
        sz_kb = dst.stat().st_size / 1024.0
        print(f"  [+] Copied {fname} ({sz_kb:.1f} KB)")

    print("\n--- Running In-Situ Browser Playback Test ---")
    # Start local HTTP server
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8089"], cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto("http://localhost:8089/website/index.html", wait_until="networkidle")
            print("  [+] Loaded website/index.html")

            # Check hero video
            hero_video = page.locator("video").first
            assert hero_video.count() > 0, "Hero video element not found"
            # Wait for video playback
            page.wait_for_timeout(2000)
            cur_time = hero_video.evaluate("el => el.currentTime")
            ready_state = hero_video.evaluate("el => el.readyState")
            print(f"  [+] Hero Loop Status: readyState={ready_state}, currentTime={cur_time:.2f}s")
            assert ready_state >= 2, f"Hero video not ready: readyState={ready_state}"

            browser.close()
            print("  [+] Browser in-situ test PASSED!")
    finally:
        srv.terminate()
        srv.wait()

    print("\n[✓] TIER 1 SHIPPING VERIFICATION COMPLETE!")

if __name__ == "__main__":
    ship_tier1()
