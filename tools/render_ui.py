"""
CLI entry point for Ghostline UI Render Harness.
Supports rendering at individual scales or across all standard scales (100%, 125%, 150%, 200%).
Generates:
- PNG renders in <outdir>/<scale>/
- ui_inventory_before.json (or specified inventory output)
- reports/ui_layout_audit_before.json
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

# Ensure repo root is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_single_scale_process(scale: float, outdir: str, dump_inventory: bool = False, inventory_file: str = "ui_inventory_before.json"):
    from ghostline.ui.render_harness import render_all_for_scale
    out_path = Path(outdir)
    sizes = [(900, 640), (1100, 720), (1400, 900)]
    res = render_all_for_scale(scale=scale, outdir=out_path, sizes=sizes, dump_inventory=dump_inventory)
    
    if dump_inventory and res.get("inventory"):
        inv_path = Path(inventory_file)
        inv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(inv_path, "w", encoding="utf-8") as f:
            json.dump(res["inventory"], f, indent=2, ensure_ascii=False)
        print(f"[+] Dumped widget inventory ({len(res['inventory'])} widgets) to {inv_path}")

    return res


def run_render_harness(outdir: str = "ui_shots/before", scales: list = None, inventory_file: str = "ui_inventory_before.json"):
    if scales is None:
        scales = [1.0, 1.25, 1.5, 2.0]

    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    all_issues = []
    all_rendered = []

    print(f"[*] Starting Ghostline UI Render Harness...")
    print(f"[*] Output directory: {out_path.resolve()}")
    print(f"[*] Scales to render: {scales}")

    for idx, scale in enumerate(scales):
        dump_inv = (idx == 0)
        print(f"\n---> Rendering Scale {int(scale * 100)}% (scale={scale})...")
        env = os.environ.copy()
        env["QT_SCALE_FACTOR"] = str(scale)
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONIOENCODING"] = "utf-8"

        cmd = [
            sys.executable,
            "-c",
            f"import sys; from pathlib import Path; sys.path.insert(0, r'{REPO_ROOT}'); "
            f"from tools.render_ui import run_single_scale_process; "
            f"res = run_single_scale_process(scale={scale}, outdir=r'{outdir}', dump_inventory={dump_inv}, inventory_file=r'{inventory_file}'); "
            f"import json; print('__ISSUES_JSON__:' + json.dumps(res['issues'])); "
            f"print('__IMAGES_JSON__:' + json.dumps(res['images']))"
        ]

        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            print(f"[!] Subprocess failed for scale {scale}:\n{proc.stderr}")
            continue

        stdout = proc.stdout
        for line in stdout.splitlines():
            if line.startswith("__ISSUES_JSON__:"):
                issues_data = json.loads(line.replace("__ISSUES_JSON__:", ""))
                all_issues.extend(issues_data)
            elif line.startswith("__IMAGES_JSON__:"):
                imgs_data = json.loads(line.replace("__IMAGES_JSON__:", ""))
                all_rendered.extend(imgs_data)
            elif line.startswith("[+]"):
                print(line)

        print(f"[+] Scale {int(scale * 100)}% complete. Rendered images: {len(all_rendered)}")

    # Save layout audit report
    audit_path = Path("reports/ui_layout_audit_before.json")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_issues": len(all_issues),
            "issues": all_issues,
            "images_rendered_count": len(all_rendered)
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Total Images Rendered: {len(all_rendered)}")
    print(f"[+] Total Layout Issues Detected: {len(all_issues)}")
    print(f"[+] Audit Report Saved: {audit_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Ghostline UI Render & Layout Audit Tool")
    parser.add_argument("--outdir", default="ui_shots/before", help="Output directory for PNG renders")
    parser.add_argument("--scale", type=float, default=None, help="Specific scale factor (e.g. 1.0, 1.25, 1.5, 2.0)")
    parser.add_argument("--inventory-file", default="ui_inventory_before.json", help="Path to dump widget inventory JSON")
    args = parser.parse_args()

    if args.scale is not None:
        scales = [args.scale]
    else:
        scales = [1.0, 1.25, 1.5, 2.0]

    code = run_render_harness(outdir=args.outdir, scales=scales, inventory_file=args.inventory_file)
    sys.exit(code)


if __name__ == "__main__":
    main()

