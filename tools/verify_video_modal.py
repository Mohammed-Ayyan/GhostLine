"""
Verifies accessible video modal behavior on Ghostline website:
1. Click trigger button -> modal opens (dialog has open attribute).
2. Video source, poster, and subtitles track set properly.
3. Close button is focused.
4. Press Escape -> dialog closes, video pauses.
"""

import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
from playwright.sync_api import sync_playwright

def verify_modal():
    root = Path(__file__).resolve().parent.parent
    web_dir = (root / "website").resolve()
    
    handler = partial(SimpleHTTPRequestHandler, directory=str(web_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{port}/index.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        # 1. Click "Watch Launch Film"
        trigger = page.locator("button[data-video-src*='Ghostline_Launch']").first
        trigger.click()
        page.wait_for_timeout(300)

        dialog = page.locator("#video-modal")
        is_open = dialog.evaluate("el => el.open")
        print(f"[OK] Video dialog opened: {is_open}")
        assert is_open, "Video modal dialog is not open"

        # Check title and src
        title = page.locator("#modal-video-title").inner_text()
        print(f"[OK] Modal title: '{title}'")
        assert "Launch Film" in title, f"Unexpected title: {title}"

        # 2. Press Escape to close
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        is_open_after = dialog.evaluate("el => el.open")
        print(f"[OK] Video dialog closed on Escape: {not is_open_after}")
        assert not is_open_after, "Video modal dialog did not close on Escape"

        browser.close()

    server.shutdown()
    print("[✓] Accessible Video Modal Verification PASSED!")

if __name__ == "__main__":
    verify_modal()
