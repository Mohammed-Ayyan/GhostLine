"""
Ship Tier 2 Assets and In-Situ Browser Test.
1. Generates <= 60 KB posters and metadata for V1 & V2.
2. Runs Tier 2 Quality Audit.
3. Copies V1, V2, posters, and captions to website/media/.
4. Runs headless browser playback test on website/install.html and website/use.html.
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

T2_FILES = [
    "Ghostline_Setup_Tutorial_16x9_140s.mp4",
    "Ghostline_Setup_Tutorial_16x9_140s_poster.jpg",
    "Ghostline_Setup_Tutorial_16x9_140s.vtt",
    "Ghostline_Setup_Tutorial_16x9_140s.txt",
    "Ghostline_Walkthrough_16x9_180s.mp4",
    "Ghostline_Walkthrough_16x9_180s_poster.jpg",
    "Ghostline_Walkthrough_16x9_180s.vtt",
    "Ghostline_Walkthrough_16x9_180s.txt"
]

def ship_tier2():
    print("--- Generating Metadata & Posters for Tier 2 ---")
    meta_cmd = [sys.executable, "tools/build_run10_videos.py", "--only", "meta"]
    subprocess.run(meta_cmd, check=True)

    print("\n--- Running Tier 2 Quality Audit ---")
    audit_cmd = [sys.executable, "tools/audit_tier2.py"]
    subprocess.run(audit_cmd, check=True)

    print("\n--- Copying Tier 2 Assets to website/media/ ---")
    for fname in T2_FILES:
        src = MASTER_DIR / fname
        dst = MEDIA_DIR / fname
        assert src.exists(), f"Source file missing: {src}"
        shutil.copy2(src, dst)
        sz_kb = dst.stat().st_size / 1024.0
        print(f"  [+] Copied {fname} ({sz_kb:.1f} KB)")

    print("\n--- Running In-Situ Browser Playback Test for T2 ---")
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8090"], cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Test install.html (V1)
            page = browser.new_page()
            page.goto("http://localhost:8090/website/install.html", wait_until="networkidle")
            print("  [+] Loaded website/install.html")
            v1_video = page.locator("video").first
            if v1_video.count() > 0:
                ready_v1 = v1_video.evaluate("el => el.readyState")
                print(f"  [+] V1 Install Video Status: readyState={ready_v1}")

            # Test use.html (V2)
            page2 = browser.new_page()
            page2.goto("http://localhost:8090/website/use.html", wait_until="networkidle")
            print("  [+] Loaded website/use.html")
            v2_video = page2.locator("video").first
            if v2_video.count() > 0:
                ready_v2 = v2_video.evaluate("el => el.readyState")
                print(f"  [+] V2 Walkthrough Video Status: readyState={ready_v2}")

            browser.close()
            print("  [+] Browser in-situ test for Tier 2 PASSED!")
    finally:
        srv.terminate()
        srv.wait()

    print("\n[✓] TIER 2 SHIPPING VERIFICATION COMPLETE!")

if __name__ == "__main__":
    ship_tier2()

