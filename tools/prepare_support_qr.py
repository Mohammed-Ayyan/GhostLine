"""
Ghostline Run 16: Safe QR Code Preparation Script.
Decodes the user's UPI QR from support_inputs/, generates:
- website/assets/support/Ghostline-support-qr.svg (clean vector, 4-module quiet zone, crispEdges)
- website/assets/support/Ghostline-support-qr.png (600x600, <= 40KB, white background)
- website/assets/support/Ghostline-support-qr-original-cropped.png (cropped fallback)

Compares all decoded payloads in memory against the original payload to verify 100% byte-identity.
NEVER prints or logs unmasked payee name or UPI ID.
"""

import os
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import segno

def main():
    root = Path(__file__).resolve().parent.parent
    input_candidates = [
        root / "support_inputs" / "WhatsApp Image 2026-11-08 at 17.15.47.jpeg",
        root / "support_inputs" / "qr.png",
        root / "support_inputs" / "qr.jpg",
        root / "support_inputs" / "qr.webp",
    ]
    input_path = next((p for p in input_candidates if p.exists()), None)
    if not input_path:
        print("[!] No input QR image found in support_inputs/")
        return 1

    print(f"[*] Found input image: {input_path.name}")
    out_dir = root / "website" / "assets" / "support"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Decode original image using OpenCV QRCodeDetector
    img_bgr = cv2.imread(str(input_path))
    detector = cv2.QRCodeDetector()
    original_payload, pts, _ = detector.detectAndDecode(img_bgr)
    if not original_payload:
        print("[!] OpenCV QRCodeDetector could not decode input image directly; trying cropped center...")
        h, w = img_bgr.shape[:2]
        crop_center = img_bgr[int(h*0.2):int(h*0.75), int(w*0.15):int(w*0.85)]
        original_payload, pts, _ = detector.detectAndDecode(crop_center)

    if not original_payload:
        print("[!] Failed to decode QR payload from input image!")
        return 1

    print("[+] Successfully decoded original QR payload into memory.")

    # Masked payee ID for reporting
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(original_payload)
    scheme = parsed.scheme
    qs = parse_qs(parsed.query)
    pa = qs.get("pa", [""])[0]
    masked_id = (pa[:2] + "***@***") if pa else "unknown"
    print(f"[+] Payload scheme: {scheme}://, Masked payee: {masked_id}")

    # 2. Crop original image to QR + quiet zone and strip EXIF
    if pts is not None:
        pts_arr = pts[0]
        xmin = max(0, int(np.min(pts_arr[:, 0])) - 35)
        ymin = max(0, int(np.min(pts_arr[:, 1])) - 35)
        xmax = min(img_bgr.shape[1], int(np.max(pts_arr[:, 0])) + 35)
        ymax = min(img_bgr.shape[0], int(np.max(pts_arr[:, 1])) + 35)
    else:
        xmin, ymin, xmax, ymax = 190, 360, 960, 1130

    cropped_bgr = img_bgr[ymin:ymax, xmin:xmax]
    cropped_rgb = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2RGB)
    cropped_pil = Image.fromarray(cropped_rgb)
    cropped_path = out_dir / "Ghostline-support-qr-original-cropped.png"
    # Resize to clean square 600x600 and save without metadata
    cropped_600 = cropped_pil.resize((600, 600), Image.Resampling.LANCZOS)
    cropped_600.save(cropped_path, "PNG", optimize=True)
    print(f"[+] Saved cropped original: {cropped_path.name} ({cropped_path.stat().st_size / 1024:.1f} KB)")

    # 3. Generate clean vector SVG with segno
    # Use Error Correction 'M' (standard UPI default) or 'Q'
    qr = segno.make(original_payload, error="m")
    svg_path = out_dir / "Ghostline-support-qr.svg"
    # Generate SVG with 4-module border, crispEdges, black modules on white background
    qr.save(
        str(svg_path),
        scale=10,
        border=4,
        dark="#000000",
        light="#ffffff"
    )

    # Post-process SVG to ensure shape-rendering="crispEdges", responsive viewBox, and accessibility attributes
    svg_text = svg_path.read_text(encoding="utf-8")
    svg_text = svg_text.replace('width="450" height="450"', 'viewBox="0 0 450 450" width="100%" height="100%"')
    if 'shape-rendering="crispEdges"' not in svg_text:
        svg_text = svg_text.replace("<svg ", '<svg shape-rendering="crispEdges" role="img" aria-label="QR code to support Ghostline" ')
    svg_path.write_text(svg_text, encoding="utf-8")

    print(f"[+] Saved vector SVG: {svg_path.name} ({svg_path.stat().st_size / 1024:.1f} KB)")

    # 4. Generate Ghostline-support-qr.png (600x600, white background, <= 40KB)
    png_path = out_dir / "Ghostline-support-qr.png"
    # Compute scale so total size with 4-module border is ~600px
    # QR version size in modules = qr.symbol_size(border=4)[0]
    total_modules = qr.symbol_size(border=4)[0]
    scale_factor = max(1, 600 // total_modules)
    qr.save(
        str(png_path),
        scale=scale_factor,
        border=4,
        dark="#000000",
        light="#ffffff"
    )

    # Resize to exact 600x600 with Pillow using NEAREST to preserve crisp pixel edges
    png_img = Image.open(png_path)
    if png_img.size != (600, 600):
        png_600 = png_img.resize((600, 600), Image.Resampling.NEAREST)
        png_600.save(png_path, "PNG", optimize=True)

    png_size_kb = png_path.stat().st_size / 1024.0
    print(f"[+] Saved PNG for download: {png_path.name} ({png_size_kb:.1f} KB, size={Image.open(png_path).size})")
    assert png_size_kb <= 40.0, f"PNG size {png_size_kb:.1f} KB exceeds 40 KB limit!"

    # 5. Verify that PNG decodes byte-identical to original payload
    png_check_bgr = cv2.imread(str(png_path))
    png_decoded, _, _ = detector.detectAndDecode(png_check_bgr)
    assert png_decoded == original_payload, "Decoded PNG payload does NOT match original payload byte-for-byte!"
    print("[✓] Memory Verification: PNG decodes byte-identical to original payload!")

    # Verify cropped original also decodes byte-identical
    crop_check_bgr = cv2.imread(str(cropped_path))
    crop_decoded, _, _ = detector.detectAndDecode(crop_check_bgr)
    assert crop_decoded == original_payload, "Decoded cropped payload does NOT match original payload!"
    print("[✓] Memory Verification: Cropped original decodes byte-identical to original payload!")

    return 0

if __name__ == "__main__":
    sys.exit(main())
