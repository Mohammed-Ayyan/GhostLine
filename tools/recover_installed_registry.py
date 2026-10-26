"""
Ghostline — Safe Registry & Uninstaller Recovery Tool
Repairs the broken Windows Add/Remove Programs registry entry in-place,
pointing it to the permanent installed location and writing the robust uninstaller script.
Preserves user data in %APPDATA%\\Ghostline.
"""

import os
import sys
import winreg
from pathlib import Path

def recover_installation():
    localappdata = os.environ.get("LOCALAPPDATA", "")
    install_dir = Path(localappdata) / "Programs" / "Ghostline"
    exe_path = install_dir / "Ghostline.exe"

    if not install_dir.exists():
        print(f"[!] Installed directory does not exist at: {install_dir}")
        return False

    if not exe_path.exists():
        print(f"[!] Ghostline.exe does not exist at: {exe_path}")
        return False

    print(f"[*] Found verified Ghostline installation at: {install_dir}")
    print(f"[*] Verified primary executable: {exe_path} ({exe_path.stat().st_size} bytes)")

    # 1. Update uninstall.bat in the permanent directory
    uninstall_bat = install_dir / "uninstall.bat"
    resolved_install_dir = str(install_dir.resolve())
    uninstall_content = (
        "@echo off\r\n"
        "setlocal enabledelayedexpansion\r\n"
        "title Ghostline Uninstaller\r\n"
        "echo ==========================================================\r\n"
        "echo   Ghostline Uninstaller\r\n"
        "echo ==========================================================\r\n"
        "\r\n"
        "set \"SILENT_MODE=0\"\r\n"
        "set \"PURGE_DATA=0\"\r\n"
        "for %%A in (%*) do (\r\n"
        "    if /i \"%%A\"==\"/S\" set \"SILENT_MODE=1\"\r\n"
        "    if /i \"%%A\"==\"--silent\" set \"SILENT_MODE=1\"\r\n"
        "    if /i \"%%A\"==\"/silent\" set \"SILENT_MODE=1\"\r\n"
        "    if /i \"%%A\"==\"/verysilent\" set \"SILENT_MODE=1\"\r\n"
        "    if /i \"%%A\"==\"--purge-data\" set \"PURGE_DATA=1\"\r\n"
        "    if /i \"%%A\"==\"/PURGEDATA\" set \"PURGE_DATA=1\"\r\n"
        ")\r\n"
        "\r\n"
        "if \"!SILENT_MODE!\"==\"0\" (\r\n"
        "    echo Uninstalling Ghostline...\r\n"
        "    echo Note: User configuration and data in %%APPDATA%%\\Ghostline are preserved.\r\n"
        "    echo (To remove user data as well, run: uninstall.bat --purge-data)\r\n"
        "    echo.\r\n"
        ")\r\n"
        "\r\n"
        ":: 1. Terminate running Ghostline instances\r\n"
        "taskkill /f /im Ghostline.exe >nul 2>&1\r\n"
        "taskkill /f /im win_ocr.exe >nul 2>&1\r\n"
        "ping 127.0.0.1 -n 2 >nul\r\n"
        "\r\n"
        ":: 2. Remove Start Menu folder\r\n"
        "if exist \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Ghostline\" (\r\n"
        "    rmdir /s /q \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Ghostline\" >nul 2>&1\r\n"
        ")\r\n"
        "\r\n"
        ":: 3. Remove Desktop shortcuts\r\n"
        "if exist \"%USERPROFILE%\\Desktop\\Ghostline.lnk\" del /f /q \"%USERPROFILE%\\Desktop\\Ghostline.lnk\" >nul 2>&1\r\n"
        "if exist \"%USERPROFILE%\\OneDrive\\Desktop\\Ghostline.lnk\" del /f /q \"%USERPROFILE%\\OneDrive\\Desktop\\Ghostline.lnk\" >nul 2>&1\r\n"
        "if defined ONEDRIVE if exist \"%ONEDRIVE%\\Desktop\\Ghostline.lnk\" del /f /q \"%ONEDRIVE%\\Desktop\\Ghostline.lnk\" >nul 2>&1\r\n"
        "\r\n"
        ":: 4. Remove Windows Registry Uninstall Entry\r\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Ghostline\" /f >nul 2>&1\r\n"
        "\r\n"
        ":: 5. Purge user data only if requested\r\n"
        "if \"!PURGE_DATA!\"==\"1\" (\r\n"
        "    if exist \"%APPDATA%\\Ghostline\" (\r\n"
        "        rmdir /s /q \"%APPDATA%\\Ghostline\" >nul 2>&1\r\n"
        "    )\r\n"
        ")\r\n"
        "\r\n"
        ":: 6. Detached self-deletion of install directory\r\n"
        f"set \"TARGET_DIR={resolved_install_dir}\"\r\n"
        "if \"!SILENT_MODE!\"==\"0\" (\r\n"
        "    echo Ghostline uninstalled successfully.\r\n"
        ")\r\n"
        f"start \"\" powershell.exe -NoProfile -WindowStyle Hidden -Command \"Start-Sleep -Seconds 2; Remove-Item -LiteralPath '{resolved_install_dir}' -Recurse -Force -ErrorAction SilentlyContinue\"\r\n"
        "exit /b 0\r\n"
    )
    uninstall_bat.write_text(uninstall_content, encoding="utf-8")
    print(f"[+] Written permanent uninstaller to: {uninstall_bat}")

    # 2. Update Registry key
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Ghostline"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Ghostline")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.0.1")
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Ghostline Open Source Project")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir.resolve()))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f'"{exe_path.resolve()}",0')
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_bat.resolve()}"')
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{uninstall_bat.resolve()}" /S')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        total_size_kb = sum(f.stat().st_size for f in install_dir.rglob('*') if f.is_file()) // 1024
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, max(1, total_size_kb))

    print(f"[+] Successfully repaired Windows Registry entry:")
    print(f"    InstallLocation = {install_dir.resolve()}")
    print(f"    UninstallString = \"{uninstall_bat.resolve()}\"")
    print(f"    DisplayIcon     = \"{exe_path.resolve()}\",0")
    return True

if __name__ == "__main__":
    recover_installation()
