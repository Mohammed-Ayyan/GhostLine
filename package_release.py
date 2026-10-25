"""
Ghostline — Release Packaging & Checksum Generator.
Builds portable ZIP package, generates SHA-256 verification hashes, and creates release artifacts.
"""

import os
import sys
import shutil
import hashlib
import zipfile
from pathlib import Path

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def package():
    root = Path(__file__).resolve().parent
    dist_dir = root / "dist" / "Ghostline"
    out_dir = root / "release_dist"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not dist_dir.exists():
        print(f"[!] Error: {dist_dir} does not exist. Run PyInstaller build first.")
        sys.exit(1)

    print("=" * 60)
    print("  Packaging Ghostline v1.0.0 Release Artifacts")
    print("=" * 60)

    # 1. Create Portable Release ZIP
    zip_name = "Ghostline-v1.0.0-win64-portable.zip"
    zip_path = out_dir / zip_name
    print(f"\n[*] Creating {zip_name}...")

    # Create temporary portable folder
    temp_portable = out_dir / "Ghostline-Portable"
    if temp_portable.exists():
        shutil.rmtree(temp_portable)
    
    shutil.copytree(dist_dir, temp_portable / "app")
    
    # Portable runner batch file
    portable_bat = temp_portable / "Run-Ghostline.bat"
    portable_bat.write_text(
        "@echo off\r\n"
        "title Ghostline Portable\r\n"
        "cd /d \"%~dp0app\"\r\n"
        "start \"\" \"Ghostline.exe\"\r\n"
        "exit\r\n",
        encoding="utf-8"
    )

    # Quick start instructions in portable package
    instructions = temp_portable / "README.txt"
    instructions.write_text(
        "Ghostline — 100% Offline AI Question Recognition & Live Audio Assistant\n"
        "=======================================================================\n\n"
        "QUICK START:\n"
        "1. Ensure Ollama is installed and running on your PC (https://ollama.com).\n"
        "2. Recommended: Run `ollama pull phi3:mini` in your terminal.\n"
        "3. Double-click `Run-Ghostline.bat` or `app\\Ghostline.exe`.\n"
        "4. Place your mouse cursor over any question on your screen and press:\n\n"
        "     Alt + /\n\n"
        "   The answer and confidence badge will appear instantly in your tray and HUD!\n\n"
        "PRIVACY & OFFLINE GUARANTEE:\n"
        "Ghostline runs entirely locally on your Windows machine with 0 external network requests.\n",
        encoding="utf-8"
    )

    # Copy LICENSE if exists
    license_src = root / "LICENSE"
    if license_src.exists():
        shutil.copy2(license_src, temp_portable / "LICENSE.txt")

    # Zip the portable folder
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for file in temp_portable.rglob("*"):
            arcname = file.relative_to(temp_portable)
            zipf.write(file, arcname)

    shutil.rmtree(temp_portable)
    print(f"  [+] Created {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")

    # 2. Copy Standalone Executable to release_dist for direct inspection
    exe_source = dist_dir / "Ghostline.exe"
    exe_dest = out_dir / "Ghostline.exe"
    if exe_source.exists():
        shutil.copy2(exe_source, exe_dest)

    # 3. Generate SHA-256 Checksums
    checksums_file = out_dir / "checksums.txt"
    print("\n[*] Calculating SHA-256 Checksums...")
    lines = []
    for item in sorted(out_dir.glob("*")):
        if item.is_file() and item.name != "checksums.txt":
            sha = compute_sha256(item)
            size_mb = item.stat().st_size / (1024*1024)
            line = f"{sha}  {item.name}  ({size_mb:.2f} MB)"
            lines.append(f"{sha}  {item.name}")
            print(f"  {item.name:<40} {sha}")

    checksums_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[+] Checksums written to {checksums_file}")
    print("\n==========================================================")
    print("  Release Artifacts Ready in: release_dist/")
    print("==========================================================")

if __name__ == "__main__":
    package()
