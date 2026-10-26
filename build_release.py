"""
Ghostline — Unified Release Build & Packaging Automation Script
Builds the standalone application, native Windows installer, portable distribution,
and SHA-256 integrity checksums reproducibly in a single run.
"""

import os
import sys
import shutil
import hashlib
import zipfile
import subprocess
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 checksum for a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_release():
    root = Path(__file__).resolve().parent
    out_dir = root / "release_dist"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  Ghostline v1.0.1 — Unified Release Packaging")
    print("  Offline AI Desktop Question Recognition & Voice Assistant")
    print("=" * 65)

    dist_dir = root / "dist" / "Ghostline"
    rebuild = ("--rebuild" in sys.argv) or ("--clean" in sys.argv) or not (dist_dir / "Ghostline.exe").exists()

    if rebuild:
        spec_file = "Ghostline.spec"
        print(f"\n[*] Compiling standalone application with PyInstaller ({spec_file})...")
        res = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "-y", spec_file],
            cwd=str(root),
            check=True
        )
        dist_dir = root / "dist" / "Ghostline"

    print(f"\n[+] Application binaries verified in: {dist_dir}")

    # Ensure Ghostline.exe exists in distribution
    primary_exe = dist_dir / "Ghostline.exe"
    if not primary_exe.exists():
        raise FileNotFoundError(f"Primary executable not found in {dist_dir}")

    # Copy native OCR binary into dist root bin if missing
    dist_bin = dist_dir / "bin" / "win_ocr.exe"
    if not dist_bin.exists():
        dist_bin.parent.mkdir(parents=True, exist_ok=True)
        src_bin = root / "bin" / "win_ocr.exe"
        if src_bin.exists():
            shutil.copy2(src_bin, dist_bin)

    # ------------------------------------------------------------------
    # 2. Create Portable Release ZIP
    # ------------------------------------------------------------------
    print("\n[*] Step 2: Packaging Portable Distribution ZIP...")
    zip_name = "Ghostline-v1.0.0-win64-portable.zip"
    zip_path = out_dir / zip_name

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

    # Quick start instructions
    readme_txt = temp_portable / "README.txt"
    readme_txt.write_text(
        "Ghostline — 100% Offline AI Desktop Assistant\n"
        "============================================\n\n"
        "QUICK START:\n"
        "1. Ensure Ollama is installed and running on your PC (https://ollama.com).\n"
        "2. Run `ollama pull phi3:mini` in your terminal.\n"
        "3. Double-click `Run-Ghostline.bat` or `app\\Ghostline.exe`.\n"
        "4. Place your mouse cursor over any question on your screen and press:\n\n"
        "     Alt + /\n\n"
        "   The answer and confidence badge will appear instantly in your HUD!\n\n"
        "PRIVACY & OFFLINE GUARANTEE:\n"
        "Ghostline runs completely locally with 0 external network requests.\n",
        encoding="utf-8"
    )

    license_src = root / "LICENSE"
    if license_src.exists():
        shutil.copy2(license_src, temp_portable / "LICENSE.txt")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for file in temp_portable.rglob("*"):
            arcname = file.relative_to(temp_portable)
            zipf.write(file, arcname)

    shutil.rmtree(temp_portable)
    print(f"  [+] Created {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")

    # ------------------------------------------------------------------
    # 3. Build Standalone Installer (Ghostline-Setup.exe)
    # ------------------------------------------------------------------
    print("\n[*] Step 3: Packaging One-Click Windows Installer...")
    installer_script = root / "installer" / "setup_gui.py"
    installer_exe = out_dir / "Ghostline-Setup.exe"
    
    # Build setup executable using PyInstaller with bundled payload zip
    print("  [*] Compiling self-contained Ghostline-Setup.exe launcher...")
    pyi_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "Ghostline-Setup",
        "--icon", str(root / "ghostline.ico"),
        "--add-data", f"{zip_path};.",
        "--distpath", str(out_dir),
        "--workpath", str(root / "build" / "installer"),
        str(installer_script)
    ]
    res = subprocess.run(
        pyi_cmd,
        cwd=str(root),
        capture_output=True,
        text=True
    )
    if installer_exe.exists():
        print(f"  [+] Standalone Self-Contained Installer created: {installer_exe} ({installer_exe.stat().st_size / (1024*1024):.2f} MB)")
    else:
        print(f"  [!] Note: PyInstaller onefile returned: {res.stderr[:300]}")
        shutil.copy2(installer_script, out_dir / "Ghostline-Setup.py")

    # If Inno Setup compiler (ISCC.exe) is present on system, also build Inno installer
    iscc_paths = [
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\InnoSetup6\ISCC.exe")),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
    ]
    iscc_exe = next((p for p in iscc_paths if p.exists()), None)
    if iscc_exe:
        print(f"  [*] Compiling Inno Setup package using {iscc_exe}...")
        try:
            subprocess.run([str(iscc_exe), str(root / "installer.iss")], cwd=str(root), check=True)
            print("  [+] Inno Setup installer compiled successfully.")
        except Exception as e:
            print(f"  [!] Inno Setup compilation warning: {e}")

    # ------------------------------------------------------------------
    # 4. Generate SHA-256 Checksums
    # ------------------------------------------------------------------
    checksums_file = out_dir / "checksums.txt"
    print("\n[*] Step 4: Generating Cryptographic Verification Hashes...")
    lines = []
    for item in sorted(out_dir.glob("*")):
        if item.is_file() and item.name != "checksums.txt":
            sha = compute_sha256(item)
            size_mb = item.stat().st_size / (1024*1024)
            lines.append(f"{sha}  {item.name}")
            print(f"  {item.name:<42} {size_mb:>7.2f} MB  {sha}")

    checksums_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[+] Checksums written to: {checksums_file}")

    print("\n" + "=" * 65)
    print("  RELEASE ARTIFACTS READY IN: release_dist/")
    print("=" * 65)


if __name__ == "__main__":
    build_release()
