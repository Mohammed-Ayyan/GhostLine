"""
Ghostline — One-Click Windows Application Installer & Uninstaller
Provides a modern dark-themed GUI installer as well as headless silent (/S) installation.
Installs to %LOCALAPPDATA%\\Programs\\Ghostline without requiring administrator privileges.
Creates Desktop and Start Menu shortcuts and registers Windows Add/Remove Programs uninstaller.
"""

import os
import sys
import shutil
import subprocess
import threading
import time
import winreg
from pathlib import Path
from typing import Tuple, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ----------------------------------------------------------------------
# Constants & Defaults
# ----------------------------------------------------------------------
APP_NAME = "Ghostline"
APP_VERSION = "1.0.0"
PUBLISHER = "Ghostline Open Source Project"
APP_DESC = "Ghostline — 100% Offline AI Desktop Assistant"
DEFAULT_INSTALL_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ghostline")

# Modern Stealth Palette (matches Ghostline)
C_BG = "#090d16"
C_PANEL = "#0f172a"
C_BORDER = "#1e293b"
C_TEXT = "#f8fafc"
C_MUTED = "#94a3b8"
C_PRIMARY = "#38bdf8"
C_PRIMARY_HOVER = "#0284c7"
C_SUCCESS = "#34d399"
C_DANGER = "#f87171"
FONT_FAMILY = "Segoe UI"


def find_payload_zip() -> Optional[Path]:
    """Finds bundled or adjacent application distribution zip."""
    if hasattr(sys, "_MEIPASS"):
        for name in ["Ghostline-v1.0.0-win64-portable.zip", "payload.zip"]:
            p = Path(sys._MEIPASS) / name
            if p.exists():
                return p

    exe_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for cand_dir in [exe_dir, exe_dir.parent, exe_dir / "release_dist", exe_dir.parent / "release_dist", Path.cwd(), Path.cwd() / "release_dist"]:
        for name in ["Ghostline-v1.0.0-win64-portable.zip", "payload.zip"]:
            p = cand_dir / name
            if p.exists():
                return p
    return None


def get_source_dir() -> Optional[Path]:
    """Finds distribution application directory when not using zip."""
    if hasattr(sys, "_MEIPASS"):
        meipass_app = Path(sys._MEIPASS) / "app"
        if meipass_app.exists():
            return meipass_app

    exe_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for cand in [
        exe_dir / "dist" / "Ghostline",
        exe_dir.parent / "dist" / "Ghostline",
        Path.cwd() / "dist" / "Ghostline",
    ]:
        if cand.exists() and (cand / "Ghostline.exe").exists():
            return cand
    return None


def create_windows_shortcut(target_exe: Path, lnk_path: Path, working_dir: Path, icon_path: Path = None, description: str = APP_DESC):
    """Creates a Windows .lnk shortcut using Windows Script Host."""
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    ps_cmd = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk_path}'); "
        f"$s.TargetPath = '{target_exe}'; "
        f"$s.WorkingDirectory = '{working_dir}'; "
        f"$s.Description = '{description}'; "
    )
    if icon_path and icon_path.exists():
        ps_cmd += f"$s.IconLocation = '{icon_path},0'; "
    ps_cmd += "$s.Save()"
    
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], check=True, creationflags=0x08000000)


def register_uninstaller(install_dir: Path, exe_path: Path):
    """Registers application in Windows Add/Remove Programs (Control Panel & Windows Settings)."""
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Ghostline"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f"{exe_path},0")
            
            uninstall_bat = install_dir / "uninstall.bat"
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_bat}"')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            
            # Calculate total size in KB
            total_size_kb = sum(f.stat().st_size for f in install_dir.rglob('*') if f.is_file()) // 1024
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, total_size_kb)
    except Exception as e:
        print(f"[!] Warning: Could not register in Windows Registry: {e}")


def terminate_running_instances():
    """Safely terminates existing Ghostline processes before file copy."""
    for proc_name in ["Ghostline"]:
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", f"Get-Process -Name '{proc_name}' -ErrorAction SilentlyContinue | Stop-Process -Force"],
                creationflags=0x08000000
            )
        except Exception:
            pass
    time.sleep(1)


def perform_installation(install_dir: Path, create_desktop: bool, create_startmenu: bool, progress_callback=None) -> Tuple[bool, str]:
    """Executes the complete installation pipeline."""
    try:
        payload_zip = find_payload_zip()
        source_dir = get_source_dir() if not payload_zip else None

        if not payload_zip and not source_dir:
            return False, "Installation payload not found (missing both payload zip and dist directory)."

        if progress_callback: progress_callback(10, "Closing running instances...")
        terminate_running_instances()

        if progress_callback: progress_callback(25, f"Creating destination: {install_dir}")
        install_dir.mkdir(parents=True, exist_ok=True)

        if payload_zip:
            if progress_callback: progress_callback(35, f"Extracting {payload_zip.name}...")
            import zipfile
            with zipfile.ZipFile(payload_zip, "r") as zf:
                members = zf.infolist()
                total = len(members)
                for i, member in enumerate(members):
                    target_path = Path(member.filename)
                    # Strip top-level wrapper folder if present (e.g. app/ or Ghostline-Portable/)
                    if target_path.parts and target_path.parts[0] in ["app", "Ghostline-Portable", "Ghostline"]:
                        rel_parts = target_path.parts[1:]
                        if not rel_parts:
                            continue
                        dest = install_dir.joinpath(*rel_parts)
                    else:
                        dest = install_dir / target_path

                    if member.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src_f, open(dest, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)

                    if progress_callback and i % 40 == 0:
                        pct = 35 + int(35 * (i / max(1, total)))
                        progress_callback(pct, f"Installing {dest.name}...")
        else:
            if progress_callback: progress_callback(40, "Copying application binaries and models...")
            for root, dirs, files in os.walk(source_dir):
                rel_path = Path(root).relative_to(source_dir)
                dest_subdir = install_dir / rel_path
                dest_subdir.mkdir(parents=True, exist_ok=True)
                for file in files:
                    shutil.copy2(Path(root) / file, dest_subdir / file)

        # Copy icon if present
        for ico_name in ["ghostline.ico"]:
            ico_target = install_dir / ico_name
            if not ico_target.exists():
                for cand_dir in [source_dir, source_dir.parent if source_dir else None, Path.cwd()]:
                    if cand_dir:
                        src_ico = cand_dir / ico_name
                        if src_ico.exists():
                            shutil.copy2(src_ico, ico_target)
                            break

        # Generate portable uninstaller batch script
        if progress_callback: progress_callback(70, "Creating uninstaller...")
        uninstall_bat = install_dir / "uninstall.bat"
        uninstall_bat.write_text(
            f'@echo off\r\n'
            f'title Ghostline Uninstaller\r\n'
            f'echo ==========================================================\r\n'
            f'echo   Uninstalling Ghostline...\r\n'
            f'echo ==========================================================\r\n'
            f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "'
            f'Stop-Process -Name Ghostline -Force -ErrorAction SilentlyContinue; '
            f'Remove-Item \\"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Ghostline\\" -Recurse -Force -ErrorAction SilentlyContinue; '
            f'Remove-Item \\"$([System.Environment]::GetFolderPath(\'Desktop\'))\\Ghostline.lnk\\" -Force -ErrorAction SilentlyContinue; '
            f'Remove-Item \\"HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Ghostline\\" -Recurse -Force -ErrorAction SilentlyContinue; '
            f'Start-Process cmd.exe -ArgumentList \'/c timeout /t 2 /nobreak >nul ^& rmdir /s /q \\"{install_dir}\\"\' -WindowStyle Hidden"\r\n'
            f'echo Ghostline has been uninstalled successfully.\r\n'
            f'timeout /t 2 /nobreak >nul\r\n'
            f'exit\r\n',
            encoding="utf-8"
        )

        # Create Shortcuts
        if progress_callback: progress_callback(85, "Creating Windows shortcuts...")
        if create_desktop:
            desktop_dir = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
            desktop_lnk = desktop_dir / "Ghostline.lnk"
            create_windows_shortcut(primary_exe, desktop_lnk, install_dir, ico_path)

        if create_startmenu:
            sm_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Ghostline"))
            sm_lnk = sm_dir / "Ghostline.lnk"
            create_windows_shortcut(primary_exe, sm_lnk, install_dir, ico_path)

        # Register uninstaller in Registry
        if progress_callback: progress_callback(95, "Registering Windows uninstaller...")
        register_uninstaller(install_dir, primary_exe)

        if progress_callback: progress_callback(100, "Installation Complete!")
        return True, "Installation succeeded!"

    except Exception as e:
        return False, f"Installation error: {e}"


# ----------------------------------------------------------------------
# Modern Tkinter Setup GUI
# ----------------------------------------------------------------------
class GhostlineInstallerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ghostline Setup")
        self.root.geometry("560x520")
        self.root.resizable(False, False)
        self.root.configure(bg=C_BG)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 560) // 2
        y = (sh - 520) // 2
        self.root.geometry(f"560x520+{x}+{y}")

        self.install_dir_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.chk_desktop_var = tk.BooleanVar(value=True)
        self.chk_startmenu_var = tk.BooleanVar(value=True)
        self.chk_launch_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        # 1. Header Banner
        header = tk.Frame(self.root, bg=C_PANEL, height=90, highlightthickness=1, highlightbackground=C_BORDER)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        lbl_title = tk.Label(header, text="👻 Ghostline", font=(FONT_FAMILY, 18, "bold"), fg=C_TEXT, bg=C_PANEL)
        lbl_title.pack(anchor="w", padx=24, pady=(16, 2))

        lbl_sub = tk.Label(header, text="Offline AI Question Recognition & Voice Assistance — One-Click Setup", font=(FONT_FAMILY, 9), fg=C_PRIMARY, bg=C_PANEL)
        lbl_sub.pack(anchor="w", padx=24)

        # 2. Main Content
        content = tk.Frame(self.root, bg=C_BG, padx=24, pady=20)
        content.pack(fill="both", expand=True)

        # Destination Folder Card
        lbl_dest = tk.Label(content, text="Installation Location", font=(FONT_FAMILY, 10, "bold"), fg=C_TEXT, bg=C_BG)
        lbl_dest.pack(anchor="w", pady=(0, 6))

        dir_frame = tk.Frame(content, bg=C_BG)
        dir_frame.pack(fill="x", pady=(0, 16))

        self.entry_dir = tk.Entry(dir_frame, textvariable=self.install_dir_var, font=(FONT_FAMILY, 9), bg=C_PANEL, fg=C_TEXT, insertbackground=C_TEXT, relief="flat", highlightthickness=1, highlightbackground=C_BORDER)
        self.entry_dir.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        btn_browse = tk.Button(dir_frame, text="Browse...", font=(FONT_FAMILY, 9), bg=C_PANEL, fg=C_TEXT, activebackground=C_BORDER, activeforeground=C_TEXT, relief="flat", padx=12, command=self._browse_dir, cursor="hand2")
        btn_browse.pack(side="right")

        # Options Card
        lbl_opt = tk.Label(content, text="Shortcuts & Launch Options", font=(FONT_FAMILY, 10, "bold"), fg=C_TEXT, bg=C_BG)
        lbl_opt.pack(anchor="w", pady=(8, 6))

        opt_frame = tk.Frame(content, bg=C_PANEL, highlightthickness=1, highlightbackground=C_BORDER, padx=16, pady=12)
        opt_frame.pack(fill="x", pady=(0, 16))

        chk1 = tk.Checkbutton(opt_frame, text="Create Ghostline Desktop Shortcut (Recommended)", variable=self.chk_desktop_var, font=(FONT_FAMILY, 9), fg=C_TEXT, bg=C_PANEL, selectcolor=C_BG, activebackground=C_PANEL, activeforeground=C_TEXT)
        chk1.pack(anchor="w", pady=3)

        chk2 = tk.Checkbutton(opt_frame, text="Create Start Menu Program Entry", variable=self.chk_startmenu_var, font=(FONT_FAMILY, 9), fg=C_TEXT, bg=C_PANEL, selectcolor=C_BG, activebackground=C_PANEL, activeforeground=C_TEXT)
        chk2.pack(anchor="w", pady=3)

        chk3 = tk.Checkbutton(opt_frame, text="Launch Ghostline immediately when finished", variable=self.chk_launch_var, font=(FONT_FAMILY, 9), fg=C_TEXT, bg=C_PANEL, selectcolor=C_BG, activebackground=C_PANEL, activeforeground=C_TEXT)
        chk3.pack(anchor="w", pady=3)

        # Progress / Status Area
        self.lbl_status = tk.Label(content, text="Ready to install into your user profile (No admin required).", font=(FONT_FAMILY, 9), fg=C_MUTED, bg=C_BG)
        self.lbl_status.pack(anchor="w", pady=(4, 6))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Installer.Horizontal.TProgressbar", troughcolor=C_PANEL, background=C_PRIMARY, bordercolor=C_BORDER)
        self.pbar = ttk.Progressbar(content, style="Installer.Horizontal.TProgressbar", orient="horizontal", mode="determinate")
        self.pbar.pack(fill="x", pady=(0, 16))

        # 3. Footer Action Buttons
        footer = tk.Frame(self.root, bg=C_PANEL, height=65, highlightthickness=1, highlightbackground=C_BORDER, padx=24)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.btn_install = tk.Button(footer, text="Install Ghostline", font=(FONT_FAMILY, 10, "bold"), bg=C_PRIMARY, fg="#090d16", activebackground=C_PRIMARY_HOVER, relief="flat", padx=24, pady=8, cursor="hand2", command=self._start_install)
        self.btn_install.pack(side="right", pady=12)

        self.btn_cancel = tk.Button(footer, text="Cancel", font=(FONT_FAMILY, 9), bg=C_PANEL, fg=C_MUTED, activebackground=C_BORDER, activeforeground=C_TEXT, relief="flat", padx=16, pady=8, cursor="hand2", command=self.root.destroy)
        self.btn_cancel.pack(side="right", padx=(0, 10), pady=12)

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.install_dir_var.get(), title="Select Ghostline Installation Folder")
        if d:
            self.install_dir_var.set(d)

    def _start_install(self):
        self.btn_install.config(state="disabled", bg=C_BORDER, text="Installing...")
        self.btn_cancel.config(state="disabled")
        self.entry_dir.config(state="disabled")

        install_path = Path(self.install_dir_var.get().strip())

        def _worker():
            def _prog(pct, msg):
                if self.root:
                    self.root.after(0, lambda: self._update_progress(pct, msg))

            success, message = perform_installation(
                install_dir=install_path,
                create_desktop=self.chk_desktop_var.get(),
                create_startmenu=self.chk_startmenu_var.get(),
                progress_callback=_prog
            )

            if self.root:
                self.root.after(0, lambda: self._on_install_finish(success, message, install_path))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, pct: int, msg: str):
        self.pbar["value"] = pct
        self.lbl_status.config(text=msg, fg=C_PRIMARY if pct < 100 else C_SUCCESS)

    def _on_install_finish(self, success: bool, message: str, install_path: Path):
        if success:
            self.lbl_status.config(text="✓ Ghostline installed successfully!", fg=C_SUCCESS)
            self.btn_install.config(state="normal", text="Finish", bg=C_SUCCESS, command=self.root.destroy)
            self.btn_cancel.pack_forget()

            if self.chk_launch_var.get():
                exe_to_launch = install_path / "Ghostline.exe"
                if exe_to_launch.exists():
                    subprocess.Popen([str(exe_to_launch)], cwd=str(install_path))
                    self.root.after(1000, self.root.destroy)
        else:
            self.lbl_status.config(text=f"✗ {message}", fg=C_DANGER)
            messagebox.showerror("Installation Error", message)
            self.btn_install.config(state="normal", text="Retry", bg=C_PRIMARY, command=self._start_install)
            self.btn_cancel.config(state="normal")


# ----------------------------------------------------------------------
# CLI / Entry Point
# ----------------------------------------------------------------------
def main():
    # Silent Installation Mode (/S, --silent, /silent, /verysilent)
    is_silent = any(arg.lower() in ["/s", "--silent", "-s", "/silent", "/verysilent"] for arg in sys.argv)
    
    # Custom destination flag: --dir "path" or /DIR="path"
    custom_dir = DEFAULT_INSTALL_DIR
    for i, arg in enumerate(sys.argv):
        if arg.startswith("/DIR="):
            custom_dir = arg.split("=", 1)[1].strip('"')
        elif arg in ["--dir", "-d"] and i + 1 < len(sys.argv):
            custom_dir = sys.argv[i + 1].strip('"')

    if is_silent:
        print("=" * 60)
        print("  Ghostline Silent Installer")
        print("=" * 60)
        print(f"Target Directory: {custom_dir}")
        success, msg = perform_installation(
            install_dir=Path(custom_dir),
            create_desktop=True,
            create_startmenu=True,
            progress_callback=lambda pct, m: print(f"[{pct}%] {m}")
        )
        if success:
            print("[+] Silent installation completed successfully.")
            sys.exit(0)
        else:
            print(f"[!] Silent installation failed: {msg}")
            sys.exit(1)

    # Interactive GUI Mode
    root = tk.Tk()
    app = GhostlineInstallerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
