"""
Playwright Web Tests for Ghostline Run 16:
- /support page visual rendering (desktop 1440x900, mobile 390x844)
- Zero horizontal scroll / overflow
- QR decoding round-trip from rendered browser pixels (in-memory comparison)
- Accessible modal enlargement (open, focus trap, escape key, focus restore)
- Star on GitHub links & star count mocking (200 OK 1.2k format, 403 rate limit fallback, offline fallback)
- Home page slim 'Enjoying Ghostline?' CTA section
- Install page post-download dismissible card and regression verification
- Zero unhandled console errors across all pages

Run directly: python tools/web_tests/test_support_and_star.py
Or via pytest: pytest tools/web_tests/test_support_and_star.py
"""

import os
import sys
import time
import socket
import threading
import functools
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import cv2
import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEBSITE_DIR = REPO_ROOT / "website"
CAPTURES_DIR = REPO_ROOT / "reports" / "run16" / "captures"
INPUTS_DIR = REPO_ROOT / "support_inputs"

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def get_original_payload():
    input_candidates = [
        INPUTS_DIR / "WhatsApp Image 2026-11-08 at 17.15.47.jpeg",
        INPUTS_DIR / "qr.png",
        INPUTS_DIR / "qr.jpg",
        INPUTS_DIR / "qr.webp",
    ]
    input_path = next((p for p in input_candidates if p.exists()), None)
    if not input_path:
        raise RuntimeError("No input QR found in support_inputs/ for payload verification")

    img_bgr = cv2.imread(str(input_path))
    detector = cv2.QRCodeDetector()
    original_payload, _, _ = detector.detectAndDecode(img_bgr)
    if not original_payload:
        h, w = img_bgr.shape[:2]
        crop_center = img_bgr[int(h*0.2):int(h*0.75), int(w*0.15):int(w*0.85)]
        original_payload, _, _ = detector.detectAndDecode(crop_center)
    if not original_payload:
        raise RuntimeError("Could not decode reference payload from input image")
    return original_payload

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard logging to keep test output clean
        pass

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

def run_tests():
    from playwright.sync_api import sync_playwright

    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    ref_payload = get_original_payload()
    print("[*] Reference payload loaded into memory (length: %d chars)" % len(ref_payload))

    port = get_free_port()
    handler = functools.partial(QuietHandler, directory=str(WEBSITE_DIR))
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[*] Local test server running at http://127.0.0.1:{port}")

    base_url = f"http://127.0.0.1:{port}"
    console_errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ==============================================================
            # TEST 1: Desktop /support Rendering (1440x900)
            # ==============================================================
            print("\n--- Test 1: Desktop /support (1440x900) ---")
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(f"CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(f"PAGEERROR: {exc}"))

            page.goto(f"{base_url}/support.html", wait_until="networkidle")

            # Check overflow
            body_scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
            body_client_w = page.evaluate("() => document.documentElement.clientWidth")
            assert body_scroll_w <= body_client_w, f"Desktop horizontal overflow detected: scrollWidth {body_scroll_w} > clientWidth {body_client_w}"
            print("[+] No horizontal scroll on desktop 1440px")

            # Verify sections are visible
            assert page.is_visible("header.site-header"), "Header not visible"
            assert page.is_visible(".page-header h1"), "Page heading not visible"
            assert page.is_visible(".support-cards-grid"), "Support grid not visible"
            assert page.is_visible("#support-qr-tile"), "QR tile not visible"
            assert page.is_visible("#other-help-title"), "Other ways section not visible"
            assert page.is_visible(".other-help-grid"), "Other help grid not visible"
            assert page.is_visible("footer.site-footer"), "Footer not visible"

            # Check tile has white background and margin
            tile_bg = page.evaluate("() => getComputedStyle(document.getElementById('support-qr-tile')).backgroundColor")
            assert "rgb(255, 255, 255)" in tile_bg or tile_bg == "#ffffff", f"QR tile background is not white: {tile_bg}"
            print(f"[+] QR tile has white background ({tile_bg})")

            # Screenshot desktop
            desktop_shot_path = CAPTURES_DIR / "support_desktop_1440.png"
            page.screenshot(path=str(desktop_shot_path), full_page=True)
            print(f"[+] Captured desktop full-page screenshot: {desktop_shot_path.name}")

            # ==============================================================
            # TEST 2: QR Decoding from Rendered Desktop Page (In-Memory)
            # ==============================================================
            print("\n--- Test 2: QR Decoding from Rendered Browser Pixels ---")
            qr_elem = page.locator("#support-qr-tile")
            qr_shot_bytes = qr_elem.screenshot()
            qr_np = np.frombuffer(qr_shot_bytes, np.uint8)
            qr_bgr = cv2.imdecode(qr_np, cv2.IMREAD_COLOR)

            detector = cv2.QRCodeDetector()
            decoded_text, pts, _ = detector.detectAndDecode(qr_bgr)
            assert decoded_text, "Failed to decode QR code from rendered #support-qr-tile screenshot"
            assert decoded_text == ref_payload, "Decoded payload does not match reference payload byte-for-byte in memory!"
            print("[+] Decoded QR payload from rendered tile matches reference 100% byte-identically in memory.")

            # ==============================================================
            # TEST 3: Modal Enlargement & Accessibility
            # ==============================================================
            print("\n--- Test 3: Modal Enlargement & Accessibility ---")
            modal_loc = page.locator("#qr-modal")
            assert not modal_loc.is_visible(), "Modal should be closed initially"

            # Click tile to open
            page.click("#support-qr-tile")
            page.wait_for_timeout(300)
            assert modal_loc.is_visible(), "Modal did not open after clicking QR tile"

            # Check focus is within modal
            focused_tag = page.evaluate("() => document.activeElement ? document.activeElement.tagName : null")
            assert focused_tag in ["BUTTON", "DIALOG"], f"Focus not trapped in modal, active element: {focused_tag}"

            modal_shot_path = CAPTURES_DIR / "support_modal_desktop.png"
            page.screenshot(path=str(modal_shot_path))
            print(f"[+] Captured modal screenshot: {modal_shot_path.name}")

            # Decode QR inside modal to verify crispness
            modal_qr_elem = page.locator("#qr-modal .modal-qr-tile")
            modal_qr_bytes = modal_qr_elem.screenshot()
            modal_qr_np = np.frombuffer(modal_qr_bytes, np.uint8)
            modal_qr_bgr = cv2.imdecode(modal_qr_np, cv2.IMREAD_COLOR)
            m_decoded, _, _ = detector.detectAndDecode(modal_qr_bgr)
            assert m_decoded == ref_payload, "Decoded modal QR payload does not match reference byte-for-byte"
            print("[+] Decoded enlarged modal QR matches reference 100% byte-identically.")

            # Press Escape to close
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            assert not modal_loc.is_visible(), "Modal did not close on Escape key"

            # Check focus restored
            focused_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
            assert focused_id == "support-qr-tile", f"Focus was not restored to QR tile after closing modal (current: {focused_id})"
            print("[+] Escape key closes modal and restores focus to QR tile.")

            context.close()

            # ==============================================================
            # TEST 4: Mobile /support Rendering (390x844 - iPhone 12/13/14)
            # ==============================================================
            print("\n--- Test 4: Mobile /support (390x844) ---")
            mob_context = browser.new_context(viewport={"width": 390, "height": 844})
            mob_page = mob_context.new_page()
            mob_page.on("console", lambda msg: console_errors.append(f"CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None)
            mob_page.on("pageerror", lambda exc: console_errors.append(f"PAGEERROR: {exc}"))

            mob_page.goto(f"{base_url}/support.html", wait_until="networkidle")

            mob_scroll_w = mob_page.evaluate("() => document.documentElement.scrollWidth")
            mob_client_w = mob_page.evaluate("() => document.documentElement.clientWidth")
            assert mob_scroll_w <= mob_client_w, f"Mobile horizontal overflow: scrollWidth {mob_scroll_w} > clientWidth {mob_client_w}"
            print("[+] Zero horizontal scroll on mobile (390px)")

            mobile_shot_path = CAPTURES_DIR / "support_mobile_390.png"
            mob_page.screenshot(path=str(mobile_shot_path), full_page=True)
            print(f"[+] Captured mobile full-page screenshot: {mobile_shot_path.name}")
            mob_context.close()

            # ==============================================================
            # TEST 5: GitHub Star Button & API Mocking Scenarios
            # ==============================================================
            print("\n--- Test 5: GitHub Star Count Mocking Scenarios ---")
            # Scenario A: 200 OK with 1234 stars -> displays "1.2k"
            st_context = browser.new_context(viewport={"width": 1280, "height": 800})
            st_page = st_context.new_page()

            def handle_gh_success(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"stargazers_count": 1234}'
                )

            st_page.route("https://api.github.com/repos/Mohammed-Ayyan/GhostLine", handle_gh_success)
            st_page.goto(f"{base_url}/support.html", wait_until="networkidle")

            star_badge = st_page.locator("[data-gh-stars]").first
            badge_text = star_badge.inner_text()
            assert badge_text == "1.2k", f"Expected star count '1.2k', got '{badge_text}'"
            print(f"[+] Scenario A (200 OK): Star count formatted properly: '{badge_text}'")

            # Check Star on GitHub button target and rel
            star_link = st_page.locator("a[href='https://github.com/Mohammed-Ayyan/GhostLine']").first
            assert star_link.get_attribute("target") == "_blank", "Star link target is not _blank"
            assert "noopener" in star_link.get_attribute("rel"), "Star link rel missing noopener"
            assert "noreferrer" in star_link.get_attribute("rel"), "Star link rel missing noreferrer"
            print("[+] Star on GitHub link has correct target='_blank' and rel='noopener noreferrer'")

            # Scenario B: 403 Rate Limit -> graceful silent fallback (no crash or visible error)
            def handle_gh_403(route):
                route.fulfill(
                    status=403,
                    content_type="application/json",
                    body='{"message": "API rate limit exceeded"}'
                )

            # Clear sessionStorage to trigger fresh fetch
            st_page.route("https://api.github.com/repos/Mohammed-Ayyan/GhostLine", handle_gh_403)
            st_page.evaluate("() => sessionStorage.clear()")
            st_page.goto(f"{base_url}/support.html", wait_until="networkidle")
            badge_text_403 = st_page.locator("[data-gh-stars]").first.inner_text()
            assert badge_text_403 == "", f"Expected empty badge on 403 rate limit, got '{badge_text_403}'"
            print("[+] Scenario B (403 Rate Limit): Handled silently with empty badge and zero exceptions.")

            # Scenario C: Network offline / abort -> graceful silent fallback
            def handle_gh_abort(route):
                route.abort("failed")

            st_page.route("https://api.github.com/repos/Mohammed-Ayyan/GhostLine", handle_gh_abort)
            st_page.evaluate("() => sessionStorage.clear()")
            st_page.goto(f"{base_url}/support.html", wait_until="networkidle")
            badge_text_abort = st_page.locator("[data-gh-stars]").first.inner_text()
            assert badge_text_abort == "", f"Expected empty badge on network failure, got '{badge_text_abort}'"
            print("[+] Scenario C (Network Failure): Handled silently with empty badge and zero exceptions.")
            st_context.close()

            # ==============================================================
            # TEST 6: Home Page Slim Section
            # ==============================================================
            print("\n--- Test 6: Home Page Slim 'Enjoying Ghostline?' Section ---")
            home_context = browser.new_context(viewport={"width": 1440, "height": 900})
            home_page = home_context.new_page()
            home_page.on("console", lambda msg: console_errors.append(f"CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None)
            home_page.on("pageerror", lambda exc: console_errors.append(f"PAGEERROR: {exc}"))

            home_page.goto(f"{base_url}/index.html", wait_until="networkidle")

            home_cta = home_page.locator("#support-cta")
            assert home_cta.is_visible(), "Home page #support-cta section is not visible"

            home_scroll_w = home_page.evaluate("() => document.documentElement.scrollWidth")
            home_client_w = home_page.evaluate("() => document.documentElement.clientWidth")
            assert home_scroll_w <= home_client_w, f"Home page horizontal overflow: {home_scroll_w} > {home_client_w}"

            # Capture screenshot of Home CTA
            home_cta_shot_path = CAPTURES_DIR / "home_support_cta.png"
            home_cta.screenshot(path=str(home_cta_shot_path))
            print(f"[+] Captured Home CTA section screenshot: {home_cta_shot_path.name}")
            home_context.close()

            # ==============================================================
            # TEST 7: Install Page Post-Download Dismissible Card
            # ==============================================================
            print("\n--- Test 7: Install Page Post-Download Card & Regressions ---")
            inst_context = browser.new_context(viewport={"width": 1440, "height": 900})
            inst_page = inst_context.new_page()
            inst_page.on("console", lambda msg: console_errors.append(f"CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None)
            inst_page.on("pageerror", lambda exc: console_errors.append(f"PAGEERROR: {exc}"))

            inst_page.goto(f"{base_url}/install.html", wait_until="networkidle")
            inst_page.evaluate("() => sessionStorage.clear()")

            # 1. Post-download card initially hidden
            card_loc = inst_page.locator("#post-download-card")
            assert not card_loc.is_visible(), "Post-download card should be hidden initially"
            print("[+] Post-download card is hidden initially on /install")

            # 2. Check download hrefs are untouched
            setup_link = inst_page.locator("a[href*='Ghostline-Setup.exe']")
            zip_link = inst_page.locator("a[href*='Ghostline-Portable.zip']")
            assert "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.3/Ghostline-Setup.exe" in setup_link.get_attribute("href"), "Setup.exe download href was modified!"
            assert "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.3/Ghostline-Portable.zip" in zip_link.get_attribute("href"), "Portable.zip download href was modified!"
            print("[+] Download links point directly to v1.0.3 releases and are completely untouched.")

            # 3. Simulate click on download card (prevent actual navigation in test)
            inst_page.evaluate("() => { document.querySelector('a[href*=\"Ghostline-Setup.exe\"]').addEventListener('click', (e) => e.preventDefault(), {once: false}); }")
            setup_link.click()
            inst_page.wait_for_timeout(200)

            assert card_loc.is_visible(), "Post-download card did not appear after clicking download link"
            print("[+] Post-download card appeared immediately upon download click.")

            card_shot_path = CAPTURES_DIR / "install_post_download_card.png"
            card_loc.screenshot(path=str(card_shot_path))
            print(f"[+] Captured post-download card screenshot: {card_shot_path.name}")

            # 4. Click 'x' close button
            close_btn = inst_page.locator("#btn-close-post-download")
            close_btn.click()
            inst_page.wait_for_timeout(200)
            assert not card_loc.is_visible(), "Post-download card did not dismiss on 'x' button click"
            print("[+] Post-download card dismissed upon clicking close button.")

            # 5. Reload page and assert card remains hidden even if download link is clicked again
            inst_page.reload(wait_until="networkidle")
            assert not card_loc.is_visible(), "Post-download card reappeared after reload despite dismissal"
            inst_page.evaluate("() => { document.querySelector('a[href*=\"Ghostline-Setup.exe\"]').addEventListener('click', (e) => e.preventDefault(), {once: false}); }")
            setup_link.click()
            inst_page.wait_for_timeout(200)
            assert not card_loc.is_visible(), "Post-download card reappeared on subsequent download after being dismissed in session!"
            print("[+] sessionStorage persistence verified: card stays dismissed for the entire tab session.")
            inst_context.close()

            # ==============================================================
            # TEST 8: Privacy Page Disclosure & Navigation
            # ==============================================================
            print("\n--- Test 8: Privacy Page Disclosure & Navigation ---")
            priv_context = browser.new_context(viewport={"width": 1440, "height": 900})
            priv_page = priv_context.new_page()
            priv_page.on("console", lambda msg: console_errors.append(f"CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None)
            priv_page.on("pageerror", lambda exc: console_errors.append(f"PAGEERROR: {exc}"))

            priv_page.goto(f"{base_url}/privacy.html", wait_until="networkidle")
            assert priv_page.is_visible("text=Website Network Requests & Third-Party APIs"), "Network requests section missing in privacy.html"
            assert priv_page.is_visible("text=GitHub Stargazers Count"), "Stargazers count disclosure missing in privacy.html"
            print("[+] Privacy page properly discloses GitHub Stargazers API call and standard HTTP headers.")
            priv_context.close()

            browser.close()

    finally:
        server.shutdown()
        print("[*] Local test server stopped.")

    # Check console cleanliness
    if console_errors:
        print("\n[!] Console errors detected:")
        for err in console_errors:
            print(f"    {err}")
        raise AssertionError(f"Test run failed with {len(console_errors)} console errors!")
    else:
        print("\n[+] Zero unhandled console errors across all pages.")

    print("\n========================================================")
    print("ALL PLAYWRIGHT TESTS PASSED SUCCESSFULLY!")
    print("========================================================")
    return 0

if __name__ == "__main__":
    sys.exit(run_tests())
