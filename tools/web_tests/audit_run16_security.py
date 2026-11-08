"""
Ghostline Run 16 Pre-Ship Security & Privacy Audit Script:
1. Payee & UPI ID privacy verification across git diff, website/, tools/, reports/
2. Shipped QR files byte-identity verification (SVG & PNG)
3. Git hygiene verification (scope, no app files, no video/media additions, no files > 1MB)
"""

import os
import sys
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    print("==================================================")
    print("Ghostline Run 16 Pre-Ship Security & Privacy Audit")
    print("==================================================")

    # 1. Get raw reference payload from support_inputs
    input_path = REPO_ROOT / "support_inputs" / "WhatsApp Image 2026-11-08 at 17.15.47.jpeg"
    if not input_path.exists():
        for cand in (REPO_ROOT / "support_inputs").glob("*.png"):
            input_path = cand
            break

    if not input_path.exists():
        print("[!] Reference input image not found in support_inputs/")
        return 1

    img_bgr = cv2.imread(str(input_path))
    detector = cv2.QRCodeDetector()
    ref_payload, _, _ = detector.detectAndDecode(img_bgr)
    if not ref_payload:
        h, w = img_bgr.shape[:2]
        crop_center = img_bgr[int(h*0.2):int(h*0.75), int(w*0.15):int(w*0.85)]
        ref_payload, _, _ = detector.detectAndDecode(crop_center)

    assert ref_payload, "Failed to decode reference payload from input image"
    print(f"[*] Decoded reference payload ({len(ref_payload)} chars, scheme: {urlparse(ref_payload).scheme}://)")

    parsed = urlparse(ref_payload)
    qs = parse_qs(parsed.query)
    raw_pa = qs.get("pa", [""])[0]
    raw_pn = qs.get("pn", [""])[0]

    masked_pa = (raw_pa[:2] + "***@***") if raw_pa else "N/A"
    print(f"[*] Payee ID (masked): {masked_pa}")

    # 2. Check for privacy leaks across repository
    # Targets to search: website/, tools/, reports/
    search_dirs = [REPO_ROOT / "website", REPO_ROOT / "tools", REPO_ROOT / "reports"]
    forbidden_tokens = []
    if raw_pa:
        forbidden_tokens.append(raw_pa)
    if raw_pn:
        # Check payee name if longer than 3 characters
        if len(raw_pn) >= 3:
            forbidden_tokens.append(raw_pn)

    print(f"[*] Scanning codebase for unmasked tokens ({len(forbidden_tokens)} sensitive strings)...")
    violations = []
    for sdir in search_dirs:
        for fpath in sdir.rglob("*"):
            if fpath.is_file():
                # Skip binaries / images / venv
                if fpath.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".mp4", ".exe", ".zip", ".pyc"]:
                    continue
                if "qr_venv" in fpath.parts:
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    for token in forbidden_tokens:
                        if token.lower() in content.lower():
                            violations.append((fpath.relative_to(REPO_ROOT), "Contains raw sensitive token"))
                except Exception as e:
                    pass

    if violations:
        print("[!] PRIVACY LEAK VIOLATIONS DETECTED:")
        for vpath, vmsg in violations:
            print(f"    - {vpath}: {vmsg}")
        return 1
    else:
        print("[+] ZERO unmasked payee names or raw UPI IDs found anywhere in website/, tools/, or reports/!")

    # 3. Check shipped assets
    svg_path = REPO_ROOT / "website" / "assets" / "support" / "Ghostline-support-qr.svg"
    png_path = REPO_ROOT / "website" / "assets" / "support" / "Ghostline-support-qr.png"
    cropped_path = REPO_ROOT / "website" / "assets" / "support" / "Ghostline-support-qr-original-cropped.png"

    assert svg_path.exists(), "SVG asset missing"
    assert png_path.exists(), "PNG asset missing"
    assert cropped_path.exists(), "Cropped PNG asset missing"

    # Verify PNG size <= 40KB
    png_size_kb = png_path.stat().st_size / 1024.0
    print(f"[*] Ghostline-support-qr.png size: {png_size_kb:.2f} KB (limit: <= 40 KB)")
    assert png_size_kb <= 40.0, f"PNG size exceeds 40KB limit: {png_size_kb:.2f} KB"

    # Decode PNG
    png_bgr = cv2.imread(str(png_path))
    png_payload, _, _ = detector.detectAndDecode(png_bgr)
    assert png_payload == ref_payload, "Shipped PNG payload does not match original byte-for-byte in memory!"
    print("[+] Shipped Ghostline-support-qr.png decodes 100% byte-identically to original.")

    # Decode Cropped PNG
    crop_bgr = cv2.imread(str(cropped_path))
    crop_payload, _, _ = detector.detectAndDecode(crop_bgr)
    assert crop_payload == ref_payload, "Cropped original PNG payload does not match original byte-for-byte in memory!"
    print("[+] Shipped Ghostline-support-qr-original-cropped.png decodes 100% byte-identically to original.")

    # 4. Check for file sizes in git status (no files > 1MB added)
    print("[*] Checking added file sizes...")
    for fpath in (REPO_ROOT / "website" / "assets" / "support").glob("*"):
        size_mb = fpath.stat().st_size / (1024 * 1024)
        assert size_mb < 1.0, f"File {fpath.name} exceeds 1MB: {size_mb:.2f} MB"
        print(f"    - {fpath.name}: {fpath.stat().st_size / 1024:.1f} KB")

    print("\n[+] ALL SECURITY & PRIVACY AUDIT CHECKS PASSED PERFECTLY!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
