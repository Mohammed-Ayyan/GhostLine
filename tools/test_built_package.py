"""
Test script to verify the built release package.
Extracts Ghostline-Portable.zip, runs --self-test against Ghostline.exe with a clean profile,
and removes the temporary folder completely.
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

def test_package():
    root = Path(__file__).resolve().parent.parent
    zip_path = root / "release_dist" / "Ghostline-Portable.zip"
    if not zip_path.exists():
        print(f"[!] Release zip not found at {zip_path}")
        return 1

    temp_dir = root / "temp_portable_test"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Extracting {zip_path.name} into {temp_dir}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_dir)

    exe_path = temp_dir / "app" / "Ghostline.exe"
    if not exe_path.exists():
        print(f"[!] Ghostline.exe not found at {exe_path}")
        shutil.rmtree(temp_dir)
        return 1

    print(f"[*] Executing --self-test on: {exe_path}...")
    res = subprocess.run([str(exe_path), "--self-test"], capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("[stderr]:", res.stderr)
    print(f"[*] Exit code: {res.returncode}")

    # Clean up completely
    shutil.rmtree(temp_dir)
    print("[*] Cleaned up temporary test directory.")
    return res.returncode

if __name__ == "__main__":
    sys.exit(test_package())
