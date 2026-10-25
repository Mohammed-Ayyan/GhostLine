import sys
import ctypes
from typing import Tuple

# Windows Display Affinity Constants
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Introduced in Windows 10 Version 2004 (Build 19041+)

user32 = ctypes.windll.user32 if sys.platform == "win32" and hasattr(ctypes, "windll") else None


def check_capture_exclusion_support() -> Tuple[bool, str]:
    """
    Checks whether the current Windows operating system supports WDA_EXCLUDEFROMCAPTURE.
    Requires Windows 10 Version 2004 (Build 19041) or Windows 11.
    """
    if sys.platform != "win32":
        return False, "Not supported on non-Windows platforms"

    try:
        ver = sys.getwindowsversion()
        # Build 19041 = Windows 10 2004 (May 2020 Update)
        if ver.major > 10 or (ver.major == 10 and ver.build >= 19041):
            return True, f"Supported (Windows Build {ver.build}: WDA_EXCLUDEFROMCAPTURE available)"
        elif ver.major == 10 or ver.major >= 6:
            return True, f"Partial (Windows Build {ver.build}: WDA_MONITOR fallback available)"
        else:
            return False, f"Unsupported legacy Windows version (Build {ver.build})"
    except Exception as e:
        return False, f"Version check error: {e}"


def set_capture_exclusion(hwnd: int, enable: bool = True) -> Tuple[bool, str]:
    """
    Applies or removes window display affinity on the target HWND to exclude it from
    Windows desktop screen captures (BitBlt, PrintWindow, ImageGrab).

    Args:
        hwnd: Win32 HWND of the window.
        enable: If True, applies WDA_EXCLUDEFROMCAPTURE (or WDA_MONITOR). If False, restores WDA_NONE.

    Returns:
        Tuple of (success: bool, description: str)
    """
    if sys.platform != "win32" or not hwnd or not user32:
        return False, "Invalid HWND or non-Windows system"

    if not enable:
        try:
            res = user32.SetWindowDisplayAffinity(hwnd, WDA_NONE)
            if res:
                return True, "Capture exclusion disabled (WDA_NONE)"
            err = ctypes.GetLastError()
            return False, f"Failed to reset display affinity (Win32 Error: {err})"
        except Exception as e:
            return False, f"Exception disabling affinity: {e}"

    # First attempt: WDA_EXCLUDEFROMCAPTURE (Win10 2004+ / Win11)
    try:
        res = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if res:
            return True, "Window excluded from screen capture (WDA_EXCLUDEFROMCAPTURE)"
        
        # Second attempt fallback: WDA_MONITOR for older Win10 builds
        res_mon = user32.SetWindowDisplayAffinity(hwnd, WDA_MONITOR)
        if res_mon:
            return True, "Window display affinity set to monitor only (WDA_MONITOR fallback)"
        
        err = ctypes.GetLastError()
        return False, f"SetWindowDisplayAffinity failed (Win32 Error: {err})"
    except Exception as e:
        return False, f"Exception setting display affinity: {e}"


def get_capture_exclusion_status(hwnd: int) -> Tuple[int, str]:
    """
    Queries the current display affinity on the specified HWND.

    Returns:
        Tuple of (affinity_code: int, description: str)
    """
    if sys.platform != "win32" or not hwnd:
        return WDA_NONE, "Unavailable on non-Windows"

    try:
        curr = ctypes.c_ulong()
        if user32 and user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(curr)):
            val = curr.value
            if val == WDA_EXCLUDEFROMCAPTURE:
                return val, "Active: Excluded from capture (WDA_EXCLUDEFROMCAPTURE)"
            elif val == WDA_MONITOR:
                return val, "Active: Monitor-only affinity (WDA_MONITOR)"
            elif val == WDA_NONE:
                return val, "Inactive: Included in normal capture (WDA_NONE)"
            return val, f"Active: Custom affinity (0x{val:08x})"
        err = ctypes.GetLastError()
        return WDA_NONE, f"Query failed (Win32 Error: {err})"
    except Exception as e:
        return WDA_NONE, f"Query error: {e}"
