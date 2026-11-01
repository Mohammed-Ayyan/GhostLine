"""
Ghostline Microsoft Fluent 2 WCAG AA Contrast Audit Tool.
Verifies all semantic text color tokens against Fluent 2 dark surface backgrounds.
WCAG AA standards:
- Normal body text: >= 4.5:1
- Large text (>= 18pt or 14pt bold) / graphical elements: >= 3.0:1
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(REPO_ROOT))

from ghostline.ui.theme.tokens import (
    SURFACE_CANVAS, SURFACE_SIDEBAR, SURFACE_CARD, SURFACE_ELEVATED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BRAND_TEXT, BRAND_FILL, STATUS_SUCCESS_TEXT, STATUS_WARNING_TEXT, STATUS_DANGER_TEXT
)

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)

def contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = relative_luminance(hex_to_rgb(hex1))
    l2 = relative_luminance(hex_to_rgb(hex2))
    lum_top = max(l1, l2)
    lum_bot = min(l1, l2)
    return (lum_top + 0.05) / (lum_bot + 0.05)

def run_contrast_audit() -> Dict[str, Any]:
    surfaces = {
        "SURFACE_CANVAS (#141414)": SURFACE_CANVAS,
        "SURFACE_SIDEBAR (#1F1F1F)": SURFACE_SIDEBAR,
        "SURFACE_CARD (#292929)": SURFACE_CARD,
        "SURFACE_ELEVATED (#333333)": SURFACE_ELEVATED
    }
    
    text_tokens = {
        "TEXT_PRIMARY": (TEXT_PRIMARY, "body"),
        "TEXT_SECONDARY": (TEXT_SECONDARY, "body"),
        "TEXT_TERTIARY": (TEXT_TERTIARY, "large/caption"),
        "BRAND_TEXT": (BRAND_TEXT, "body"),
        "STATUS_SUCCESS_TEXT": (STATUS_SUCCESS_TEXT, "body"),
        "STATUS_WARNING_TEXT": (STATUS_WARNING_TEXT, "body"),
        "STATUS_DANGER_TEXT": (STATUS_DANGER_TEXT, "body")
    }
    
    results = []
    all_passed = True
    
    for s_name, s_hex in surfaces.items():
        for t_name, (t_hex, target_type) in text_tokens.items():
            ratio = contrast_ratio(t_hex, s_hex)
            min_req = 3.0 if target_type == "large/caption" else 4.5
            passed = ratio >= min_req
            if not passed:
                all_passed = False
            results.append({
                "surface": s_name,
                "token": t_name,
                "text_hex": t_hex,
                "surface_hex": s_hex,
                "target_type": target_type,
                "min_required_ratio": min_req,
                "measured_ratio": round(ratio, 2),
                "passed": passed
            })
            
    return {
        "wcag_aa_compliant": all_passed,
        "total_checks": len(results),
        "results": results
    }

if __name__ == "__main__":
    audit = run_contrast_audit()
    print("=" * 60)
    print("MICROSOFT FLUENT 2 WCAG AA CONTRAST AUDIT")
    print("=" * 60)
    print(f"Overall Compliant: {audit['wcag_aa_compliant']}")
    print(f"Total Checks: {audit['total_checks']}")
    print("-" * 60)
    for r in audit["results"]:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        print(f"[{status}] {r['token']:<20} ({r['text_hex']}) on {r['surface']:<26} -> {r['measured_ratio']}:1 (min {r['min_required_ratio']}:1)")
        
    out_file = REPO_ROOT / "reports" / "ui_contrast_audit.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    print("=" * 60)
    print(f"[+] Saved audit report to {out_file}")
