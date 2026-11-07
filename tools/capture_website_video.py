"""
Ghostline Website Interaction Recorder
Uses Playwright with Microsoft Edge to capture high-definition landscape (1920x1080)
and vertical (1080x1920) interactions of the Ghostline landing page and interactive sandbox.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def record_website_interactions():
    root = Path(__file__).resolve().parent.parent
    html_file = (root / "website" / "index.html").resolve()
    url = html_file.as_uri()

    out_dir = (root.parent / "ghostline_launch_video" / "assets").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = out_dir / "_temp_vids"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting website interaction recorder...")
    print(f"[*] Website URL: {url}")
    print(f"[*] Destination: {out_dir}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # ---------------------------------------------------------
        # 1. LANDSCAPE RECORDING (1920x1080)
        # ---------------------------------------------------------
        print("[*] Recording Landscape 1920x1080...")
        context_ls = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080}
        )
        page = context_ls.new_page()
        page.goto(url, wait_until="networkidle")

        # Hero view
        page.wait_for_timeout(2000)

        # Smooth scroll to interactive sandbox
        demo_elem = page.locator("#demo")
        demo_elem.scroll_into_view_if_needed()
        page.wait_for_timeout(1500)

        # Tab 1: Screen Solve
        btn_solve = page.locator("#btn-trigger-solve")
        if btn_solve.is_visible():
            btn_solve.click()
            page.wait_for_timeout(2500)

        # Tab 2: Live Meeting
        tab_audio = page.locator("#tab-btn-audio")
        if tab_audio.is_visible():
            tab_audio.click()
            page.wait_for_timeout(1000)
            btn_audio = page.locator("#btn-start-audio")
            if btn_audio.is_visible():
                btn_audio.click()
                page.wait_for_timeout(3000)

        # Tab 3: Profile Grounding
        tab_profile = page.locator("#tab-btn-profile")
        if tab_profile.is_visible():
            tab_profile.click()
            page.wait_for_timeout(1000)
            btn_ground = page.locator("#btn-ground-profile")
            if btn_ground.is_visible():
                btn_ground.click()
                page.wait_for_timeout(3000)

        # Tab 4: Data Boundary
        tab_boundary = page.locator("#tab-btn-boundary")
        if tab_boundary.is_visible():
            tab_boundary.click()
            page.wait_for_timeout(1000)
            # Toggle provider
            prov_toggle = page.locator("button[data-prov='openai']")
            if prov_toggle.is_visible():
                prov_toggle.click()
                page.wait_for_timeout(1500)
            prov_ollama = page.locator("button[data-prov='ollama']")
            if prov_ollama.is_visible():
                prov_ollama.click()
                page.wait_for_timeout(1500)

        # Scroll to 3-Step Setup
        setup_elem = page.locator("#setup")
        if setup_elem.is_visible():
            setup_elem.scroll_into_view_if_needed()
            page.wait_for_timeout(2500)

        # Scroll to Hotkeys
        hotkeys_elem = page.locator("#hotkeys")
        if hotkeys_elem.is_visible():
            hotkeys_elem.scroll_into_view_if_needed()
            page.wait_for_timeout(2500)

        # Scroll back to Ethical Banner / Footer
        faq_elem = page.locator("#faq")
        if faq_elem.is_visible():
            faq_elem.scroll_into_view_if_needed()
            page.wait_for_timeout(2000)

        # Close landscape context to finish video
        video_ls_path = page.video.path()
        context_ls.close()
        print(f"[+] Landscape raw video saved: {video_ls_path}")

        # Move to assets/website_landscape_raw.webm
        dest_ls = out_dir / "website_landscape_raw.webm"
        if dest_ls.exists():
            dest_ls.unlink()
        Path(video_ls_path).rename(dest_ls)
        print(f"[+] Final landscape asset: {dest_ls} ({dest_ls.stat().st_size} bytes)")

        # ---------------------------------------------------------
        # 2. VERTICAL RECORDING (1080x1920)
        # ---------------------------------------------------------
        print("[*] Recording Vertical 1080x1920...")
        context_vt = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1080, "height": 1920}
        )
        page_vt = context_vt.new_page()
        page_vt.goto(url, wait_until="networkidle")

        # Hero view
        page_vt.wait_for_timeout(2000)

        # Interactive Demo
        demo_elem_vt = page_vt.locator("#demo")
        demo_elem_vt.scroll_into_view_if_needed()
        page_vt.wait_for_timeout(1500)

        btn_solve_vt = page_vt.locator("#btn-trigger-solve")
        if btn_solve_vt.is_visible():
            btn_solve_vt.click()
            page_vt.wait_for_timeout(2500)

        tab_audio_vt = page_vt.locator("#tab-btn-audio")
        if tab_audio_vt.is_visible():
            tab_audio_vt.click()
            page_vt.wait_for_timeout(1000)
            btn_audio_vt = page_vt.locator("#btn-start-audio")
            if btn_audio_vt.is_visible():
                btn_audio_vt.click()
                page_vt.wait_for_timeout(3000)

        tab_profile_vt = page_vt.locator("#tab-btn-profile")
        if tab_profile_vt.is_visible():
            tab_profile_vt.click()
            page_vt.wait_for_timeout(1000)
            btn_ground_vt = page_vt.locator("#btn-ground-profile")
            if btn_ground_vt.is_visible():
                btn_ground_vt.click()
                page_vt.wait_for_timeout(3000)

        setup_elem_vt = page_vt.locator("#setup")
        if setup_elem_vt.is_visible():
            setup_elem_vt.scroll_into_view_if_needed()
            page_vt.wait_for_timeout(2500)

        video_vt_path = page_vt.video.path()
        context_vt.close()
        print(f"[+] Vertical raw video saved: {video_vt_path}")

        # Move to assets/website_vertical_raw.webm
        dest_vt = out_dir / "website_vertical_raw.webm"
        if dest_vt.exists():
            dest_vt.unlink()
        Path(video_vt_path).rename(dest_vt)
        print(f"[+] Final vertical asset: {dest_vt} ({dest_vt.stat().st_size} bytes)")

        browser.close()

    # Clean up temp dir
    try:
        temp_dir.rmdir()
    except Exception:
        pass

    print("[+] All website video captures completed successfully!")

if __name__ == "__main__":
    record_website_interactions()
