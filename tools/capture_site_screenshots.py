"""
Captures screenshots of website pages at 1440, 768, and 390 viewports.
Usage: python tools/capture_site_screenshots.py --out-dir ../ghostline_launch_video/run10/site_before
"""

import sys
import argparse
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = REPO_ROOT / "website"

def capture_all(out_dir_path: str):
    out_dir = Path(out_dir_path).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    handler = partial(SimpleHTTPRequestHandler, directory=str(WEBSITE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    viewports = [
        ("desktop_1440", {"width": 1440, "height": 900}),
        ("tablet_768", {"width": 768, "height": 1024}),
        ("mobile_390", {"width": 390, "height": 844})
    ]

    pages = [
        "index.html",
        "install.html",
        "use.html",
        "models.html",
        "privacy.html",
        "responsible-use.html",
        "faq.html",
        "changelog.html",
        "404.html"
    ]

    print(f"[*] Capturing screenshots to {out_dir}...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, vp_dims in viewports:
            ctx = browser.new_context(viewport=vp_dims)
            page = ctx.new_page()
            for pg in pages:
                url = f"http://127.0.0.1:{port}/{pg}"
                try:
                    page.goto(url, wait_until="load", timeout=8000)
                    page.wait_for_timeout(300)
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=8000)
                
                stem = Path(pg).stem
                out_file = out_dir / f"{stem}_{vp_name}.png"
                page.screenshot(path=str(out_file), full_page=True)
                print(f"  [+] Captured {out_file.name}")
            ctx.close()
        browser.close()

    server.shutdown()
    print("[✓] Screenshot capture complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="../ghostline_launch_video/run10/site_before")
    args = parser.parse_args()
    capture_all(args.out_dir)
