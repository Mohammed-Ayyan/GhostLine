"""
Ghostline — Part 4 Read-Only Pre-Flight Inspection & AppData Backup
Gathers system telemetry on Ghostline and Ollama installations without making any changes.
"""

import os
import sys
import json
import shutil
import winreg
import psutil
import subprocess
from datetime import datetime
from pathlib import Path

def query_registry_key(root_hkey, subkey):
    try:
        with winreg.OpenKey(root_hkey, subkey) as key:
            values = {}
            for i in range(winreg.QueryInfoKey(key)[1]):
                name, val, _ = winreg.EnumValue(key, i)
                values[name] = val
            return values
    except OSError:
        return None

def inspect():
    results = {}

    # 1. Ghostline Installed Locations & Uninstallers
    ghostline_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Ghostline"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Ghostline"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{D37E88BC-3FA8-4E0E-8521-1D0A3C9A8B62}_is1"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{D37E88BC-3FA8-4E0E-8521-1D0A3C9A8B62}_is1"),
    ]
    ghostline_uninstall = None
    for hkey, subkey in ghostline_keys:
        data = query_registry_key(hkey, subkey)
        if data:
            ghostline_uninstall = {
                "key": subkey,
                "InstallLocation": data.get("InstallLocation"),
                "UninstallString": data.get("UninstallString"),
                "QuietUninstallString": data.get("QuietUninstallString"),
                "DisplayVersion": data.get("DisplayVersion")
            }
            break
    results["ghostline_uninstall_reg"] = ghostline_uninstall

    # 2. Ghostline AppData folders
    app_data = Path(os.path.expandvars(r"%APPDATA%\Ghostline"))
    local_app_data = Path(os.path.expandvars(r"%LOCALAPPDATA%\Ghostline"))
    programs_dir = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ghostline"))
    
    def folder_info(p: Path):
        if not p.exists():
            return {"exists": False, "size_mb": 0}
        total = 0
        file_count = 0
        for root, dirs, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                    file_count += 1
                except OSError:
                    pass
        return {"exists": True, "path": str(p), "size_mb": round(total / (1024*1024), 2), "files": file_count}

    results["folders"] = {
        "appdata_roaming": folder_info(app_data),
        "appdata_local": folder_info(local_app_data),
        "programs_install": folder_info(programs_dir)
    }

    # 3. Windows Run Key
    run_vals = query_registry_key(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") or {}
    results["run_key_ghostline"] = {k: v for k, v in run_vals.items() if "ghostline" in k.lower() or "ghostline" in str(v).lower()}

    # Scheduled Tasks
    try:
        sch_out = subprocess.check_output(["schtasks", "/query", "/fo", "CSV"], text=True, stderr=subprocess.DEVNULL)
        results["scheduled_tasks_ghostline"] = [l for l in sch_out.splitlines() if "ghostline" in l.lower()]
    except Exception:
        results["scheduled_tasks_ghostline"] = []

    # 4. Ollama Telemetry
    try:
        ver_out = subprocess.check_output(["ollama", "--version"], text=True, stderr=subprocess.STDOUT).strip()
        results["ollama_version"] = ver_out
    except Exception as e:
        results["ollama_version"] = str(e)

    try:
        where_out = subprocess.check_output(["where", "ollama"], text=True, stderr=subprocess.STDOUT).strip()
        results["ollama_path"] = where_out.splitlines()
    except Exception as e:
        results["ollama_path"] = str(e)

    # Ollama registry uninstaller
    ollama_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Ollama"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Ollama"),
    ]
    ollama_uninstall = None
    for hkey, subkey in ollama_keys:
        data = query_registry_key(hkey, subkey)
        if data:
            ollama_uninstall = {
                "key": subkey,
                "InstallLocation": data.get("InstallLocation"),
                "UninstallString": data.get("UninstallString"),
                "DisplayVersion": data.get("DisplayVersion")
            }
            break
    results["ollama_uninstall_reg"] = ollama_uninstall

    # 5. Ollama List
    try:
        list_out = subprocess.check_output(["ollama", "list"], text=True, stderr=subprocess.STDOUT).strip()
        results["ollama_list"] = list_out.splitlines()
    except Exception as e:
        results["ollama_list"] = [str(e)]

    # 6. Ollama Data Folder
    results["ollama_models_env"] = os.environ.get("OLLAMA_MODELS")
    user_ollama = Path(os.path.expandvars(r"%USERPROFILE%\.ollama"))
    results["user_ollama_dir"] = folder_info(user_ollama)

    # 7. Running Processes
    active_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = proc.info['name'] or ''
            if any(k in name.lower() for k in ['ghostline', 'ollama']):
                active_procs.append({
                    "pid": proc.info['pid'],
                    "name": name,
                    "exe": proc.info.get('exe')
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    results["active_processes"] = active_procs

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    inspect()

