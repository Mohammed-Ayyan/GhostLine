# Phase H Report — Release Build Execution & Verification

**Build Start Time:** 2026-11-01 19:12:45 +05:30  
**Build Completion Time:** 2026-11-01 19:20:45 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Pre-Build Archiving & Safety
- Archived pre-existing build artifacts into:
  `release_archive/20261101_191240/dist`
  `release_archive/20261101_191240/release_dist`
- Verified clean build directory before starting compilation.

---

## 2. Specification & Dependency Updates
Updated `Ghostline.spec`:
- Added hardware subsystem modules:
  - `ghostline.hardware`
  - `ghostline.hardware.lighting`
  - `ghostline.hardware.brightness`
- Added Win32 & cryptography dependencies:
  - `win32crypt` (DPAPI encryption)
  - `pythoncom`, `win32com`, `win32com.client` (WMI brightness queries)
  - `certifi` (TLS certificate bundle for HTTPS cloud AI providers)

---

## 3. Build Automation & Execution
- Executed: `python build_release.py --rebuild`
- Full build log saved to: `reports/build.log`
- Warnings analysis (`build/Ghostline/warn-Ghostline.txt`):
  - 1010 lines of standard conditional/optional imports inspected.
  - All missing modules are POSIX-only (`pwd`, `grp`, `posix`, `resource`) or legacy Python 2 fallbacks.
  - No critical Windows DLLs or runtime dependencies are missing.
- **Inno Setup Status**:
  - Compiler `ISCC.exe` checked at standard locations (`%LOCALAPPDATA%\Programs\InnoSetup6\ISCC.exe`, `C:\Program Files\Inno Setup 6\ISCC.exe`, `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`): NOT FOUND.
  - Status: `BLOCKED` (Inno Setup compiler not installed on host).
  - As specified by Operating Rules, no external third-party software was downloaded without user instruction. The build pipeline fell back cleanly to packaging the self-contained PyInstaller launcher `Ghostline-Setup.exe` bundling the payload zip.

---

## 4. Fresh Release Artifacts Table

| Artifact Name | Absolute Path | Size (Bytes) | Size (MB) | Modification Timestamp | SHA-256 Checksum | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Standalone Exe** | `dist\Ghostline\Ghostline.exe` | 82,335,506 | 78.52 MB | 2026-11-01 19:17:11 | `27320696190503539340F42D70227F4A766F88E3743CA1B3B28A31D59C577765` | `VERIFIED-AUTOMATED` |
| **Portable ZIP** | `release_dist\Ghostline-v1.0.2-win64-portable.zip` | 555,214,112 | 529.49 MB | 2026-11-01 19:19:56 | `af1b31ac323c226a42d135cf8ff69b2b0f0acc84347fe647b3e7828f3dcea06f` | `VERIFIED-AUTOMATED` |
| **Setup Launcher** | `release_dist\Ghostline-Setup.exe` | 567,032,155 | 540.76 MB | 2026-11-01 19:20:36 | `45c384900ceb2b8b2f3293a944dc7c9413bbec6a11ce1a159a7d8eec80cb3734` | `VERIFIED-AUTOMATED` |

> [!NOTE]
> All binaries are unsigned (no code-signing certificate exists on this machine). Windows SmartScreen may present an "Unknown Publisher" prompt on untrusted systems.

