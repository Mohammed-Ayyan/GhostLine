"""
Verifies that the generated Ghostline-support-qr.svg renders cleanly in Chromium (Playwright)
at 300px and 600px, and that both rendered captures decode in memory byte-identical to the original payload.
"""

import sys
import tempfile
from pathlib import Path
import cv2
from playwright.sync_api import sync_playwright

def main():
    root = Path(__file__).resolve().parent.parent
    input_path = root / "support_inputs" / "WhatsApp Image 2026-11-08 at 17.15.47.jpeg"
    svg_path = root / "website" / "assets" / "support" / "Ghostline-support-qr.svg"
    
    if not input_path.exists() or not svg_path.exists():
        print("[!] Input image or SVG file missing!")
        return 1

    # 1. Decode original payload in memory
    detector = cv2.QRCodeDetector()
    original_img = cv2.imread(str(input_path))
    original_payload, _, _ = detector.detectAndDecode(original_img)
    if not original_payload:
        print("[!] Could not decode original input payload!")
        return 1

    # 2. Render SVG in Playwright Chromium at 300px and 600px
    svg_content = svg_path.read_text(encoding="utf-8")
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 20px; background: #ffffff; }}
  .box-300 {{ width: 300px; height: 300px; padding: 16px; background: #ffffff; box-sizing: border-box; }}
  .box-600 {{ width: 600px; height: 600px; padding: 24px; background: #ffffff; box-sizing: border-box; }}
  svg {{ width: 100%; height: 100%; display: block; }}
</style>
</head>
<body>
  <div id="qr300" class="box-300">{svg_content}</div>
  <div id="qr600" class="box-600">{svg_content}</div>
</body>
</html>"""

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        html_file = Path(f.name)
        f.write(html_content)

    temp_shots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 1600})
            page.goto(html_file.as_uri())
            page.wait_for_load_state("networkidle")

            shot300_path = root / "scratch" / "test_render_300.png"
            shot600_path = root / "scratch" / "test_render_600.png"
            temp_shots.extend([shot300_path, shot600_path])

            page.locator("#qr300").screenshot(path=str(shot300_path))
            page.locator("#qr600").screenshot(path=str(shot600_path))
            browser.close()

        # 3. Decode screenshots in memory and compare
        for size, shot_path in [(300, shot300_path), (600, shot600_path)]:
            shot_bgr = cv2.imread(str(shot_path))
            decoded, _, _ = detector.detectAndDecode(shot_bgr)
            if not decoded:
                print(f"[!] Failed to decode rendered QR screenshot at {size}px!")
                return 1
            if decoded != original_payload:
                print(f"[!] Rendered QR at {size}px decoded payload does not match original payload!")
                return 1
            print(f"[✓] Chromium render at {size}px decoded byte-identical to original payload!")

        print("[✓✓✓] All SVG rendering and decoding verification tests PASSED!")
        return 0
    finally:
        if html_file.exists():
            html_file.unlink()
        for s in temp_shots:
            if s.exists():
                s.unlink()

if __name__ == "__main__":
    sys.exit(main())
