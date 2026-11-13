"""
Hardware Profile & Performance Mode Resolution Engine.
Collects zero-PII hardware metrics via pure Windows stdlib/ctypes in < 2ms,
and automatically selects Lite vs Standard mode on weak laptops or battery saver.
"""

import os
import sys
import platform
import ctypes
from typing import Dict, Any, Tuple
from ctypes import wintypes


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


def get_hardware_info() -> Dict[str, Any]:
    """Returns sanitized hardware facts without personal data, username, or computer name."""
    # 1. CPU Name
    cpu_name = "Unknown CPU"
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        cpu_name = " ".join(val.split())
    except Exception:
        cpu_name = platform.processor() or "Multi-Core Processor"

    # 2. Cores
    cores = os.cpu_count() or 4

    # 3. RAM in GB
    ram_gb = 8
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            ram_gb = int(round(stat.ullTotalPhys / (1024**3)))
    except Exception:
        pass

    # 4. Battery Saver State
    battery_saver = False
    try:
        sps = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
            battery_saver = (sps.SystemStatusFlag == 1)
    except Exception:
        pass

    # 5. OS Name
    win_ver = platform.version()
    os_name = f"Windows {platform.release()} ({win_ver})"

    return {
        "cpu_name": cpu_name,
        "cores": cores,
        "ram_gb": ram_gb,
        "battery_saver": battery_saver,
        "os_name": os_name,
    }


def is_weak_hardware(hw: Dict[str, Any] = None) -> Tuple[bool, str]:
    """
    Evaluates whether system hardware qualifies as weak/laptop:
    Returns (True, reason) if RAM <= 8GB, cores <= 4, or Battery Saver is active.
    """
    if hw is None:
        hw = get_hardware_info()

    reasons = []
    if hw["ram_gb"] <= 8:
        reasons.append(f"{hw['ram_gb']}GB RAM (<=8GB)")
    if hw["cores"] <= 4:
        reasons.append(f"{hw['cores']} CPU cores (<=4)")
    if hw["battery_saver"]:
        reasons.append("Windows Battery Saver active")

    if reasons:
        return True, ", ".join(reasons)
    return False, "Hardware capable"


def is_weak_hardware_or_battery(hw: Dict[str, Any] = None) -> bool:
    """Boolean helper returning True if hardware qualifies as weak or battery saver is active."""
    weak, _ = is_weak_hardware(hw)
    return weak


get_hardware_profile = get_hardware_info


def resolve_effective_performance_mode(configured_mode: str, hw: Dict[str, Any] = None) -> str:
    """
    Resolves effective mode ('lite' or 'standard') given the configured setting ('auto', 'standard', 'lite').
    """
    mode = (configured_mode or "auto").lower().strip()
    if mode == "lite":
        return "lite"
    if mode == "standard":
        return "standard"

    # Auto: Choose lite if weak hardware or battery saver
    is_weak, _ = is_weak_hardware(hw)
    return "lite" if is_weak else "standard"


def get_hardware_summary_string(configured_mode: str = "auto", screen_res_str: str = "") -> str:
    """
    Generates a single human-readable hardware line for Wizard Step 1 and Help > Diagnostics.
    Format: 'Your PC: CPU name, N cores, X GB RAM, Windows version, screen resolution and scale, performance mode'
    Guaranteed zero PII.
    """
    hw = get_hardware_info()
    effective_mode = resolve_effective_performance_mode(configured_mode, hw)
    mode_label = f"{effective_mode.capitalize()} (Auto)" if configured_mode == "auto" else effective_mode.capitalize()

    parts = [
        f"Your PC: {hw['cpu_name']}",
        f"{hw['cores']} cores",
        f"{hw['ram_gb']} GB RAM",
        hw["os_name"],
    ]
    if screen_res_str:
        parts.append(screen_res_str)
    parts.append(f"Performance Mode: {mode_label}")

    return ", ".join(parts)

