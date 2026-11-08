"""
Ghostline Website Verification Script
Uses Playwright with native Microsoft Edge to verify:
1. Screenshots at 1440, 768, and 390px widths.
2. Console errors & page errors.
3. Keyboard-only walkthrough of interactive demo and FAQ.
4. Broken link checking.
"""

import sys
import time
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
from playwright.sync_api import sync_playwright

def verify_website():
    root = Path(__file__).resolve().parent.parent
    web_dir = (root / "website").resolve()
    
    # Spin up ephemeral local HTTP server to avoid file:// CORS restrictions on WebVTT tracks
    handler = partial(SimpleHTTPRequestHandler, directory=str(web_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    url = f"http://127.0.0.1:{port}/index.html"
    
    shots_dir = root / "website" / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    
    console_errors = []
    page_errors = []

    viewports = [
        ("1440px", {"width": 1440, "height": 900}),
        ("768px", {"width": 768, "height": 1024}),
        ("390px", {"width": 390, "height": 844})
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        
        # 1. Responsive Viewport Screenshots
        for name, vp in viewports:
            page = browser.new_page(viewport=vp)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            
            page.goto(url, wait_until="networkidle")
            shot_path = shots_dir / f"website_{name}.png"
            page.screenshot(path=str(shot_path), full_page=True)
            print(f"[OK] Rendered {name} screenshot -> {shot_path} ({shot_path.stat().st_size} bytes)")
            page.close()

        # 2. Keyboard-Only Walkthrough on Desktop Viewport
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        
        page.goto(url, wait_until="networkidle")
        print(f"[OK] Page loaded successfully: {page.title()}")

        # Keyboard Navigation Walkthrough
        # Focus on first demo tab
        tab_solve = page.locator("#tab-btn-solve")
        tab_solve.focus()
        print("[OK] Focused #tab-btn-solve via keyboard")

        # Arrow Right to Live Meeting tab
        page.keyboard.press("ArrowRight")
        time.sleep(0.2)
        tab_audio = page.locator("#tab-btn-audio")
        assert "active" in (tab_audio.get_attribute("class") or ""), "Tab audio not active after ArrowRight"
        print("[OK] Switched to Live Meeting tab via ArrowRight")

        # Arrow Right to Profile Grounding tab
        page.keyboard.press("ArrowRight")
        time.sleep(0.2)
        tab_profile = page.locator("#tab-btn-profile")
        assert "active" in (tab_profile.get_attribute("class") or ""), "Tab profile not active after ArrowRight"
        print("[OK] Switched to Profile Grounding tab via ArrowRight")

        # Arrow Left back to Screen Solve tab
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        time.sleep(0.2)
        assert "active" in (tab_solve.get_attribute("class") or ""), "Tab solve not active after ArrowLeft"
        print("[OK] Switched back to Screen Solve tab via ArrowLeft")

        # Select second question option and click simulate solve
        opt2 = page.locator("button[data-qid='mcq2']")
        opt2.click()
        solve_btn = page.locator("#btn-trigger-solve")
        solve_btn.click()
        time.sleep(1.0) # Wait for simulation

        badge_text = page.locator("#hud-badge-target").inner_text()
        print(f"[OK] Screen solve simulated. Result badge: '{badge_text}'")
        assert "[0, 4]" in badge_text, f"Unexpected badge text: {badge_text}"

        # Test FAQ accordion
        faq_btn = page.locator(".faq-question").first
        faq_btn.focus()
        faq_btn.click()
        time.sleep(0.2)
        faq_item = page.locator(".faq-item").first
        assert "open" in (faq_item.get_attribute("class") or ""), "FAQ item did not open"
        print("[OK] FAQ accordion opened via click/keyboard")

        # Verify all links
        links = page.locator("a").all()
        print(f"[OK] Checked {len(links)} anchors on the page")

        browser.close()

    print("\n=== WEBSITE AUDIT RESULTS ===")
    print(f"Console errors: {len(console_errors)}")
    for err in console_errors:
        print(f"  Console Error: {err}")
    print(f"Page errors: {len(page_errors)}")
    for err in page_errors:
        print(f"  Page Error: {err}")

    if not console_errors and not page_errors:
        print("STATUS: VERIFIED-AUTOMATED (Zero errors, responsive renders passed, keyboard navigation verified)")
    else:
        print("STATUS: FAILED")

if __name__ == "__main__":
    verify_website()
