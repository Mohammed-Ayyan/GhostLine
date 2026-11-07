"""
Windows Startup and Taskbar Registry Management for Ghostline.

Manages automatic startup on Windows login via the per-user Run registry key:
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Ghostline

Requires no administrator privileges (per-user registry hive).
Provides launch helper for Windows 11 Taskbar overflow settings page:
    ms-settings:taskbar
"""

import sys
import os
import logging
from typing import Optional

logger = logging.getLogger("ghostline.startup")

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "Ghostline"


def set_start_with_windows(enable: bool, custom_command: Optional[str] = None) -> bool:
    """
    Enables or disables automatic launch on Windows login via HKCU Run registry key.

    Args:
        enable: True to register startup key, False to delete it.
        custom_command: Optional executable command string. Defaults to python/executable invocation.

    Returns:
        True if operation succeeded, False otherwise.
    """
    if sys.platform != "win32":
        logger.info("Startup registry only supported on Windows.")
        return False

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        try:
            if enable:
                if custom_command:
                    cmd = custom_command
                elif getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    app_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
                    cmd = f'"{sys.executable}" "{app_py}"'

                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                logger.info("Successfully enabled Windows startup entry for Ghostline: %s", cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                    logger.info("Successfully removed Windows startup entry for Ghostline.")
                except FileNotFoundError:
                    pass
            return True
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.warning("Failed to update Windows startup registry key: %s", e)
        return False


def get_start_with_windows() -> bool:
    """
    Checks if Ghostline is currently registered in HKCU Run registry key.

    Returns:
        True if startup key exists and has a non-empty value, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_READ
        )
        try:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(val)
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.debug("Could not read Windows startup key: %s", e)
        return False


def open_taskbar_settings() -> bool:
    """
    Launches Windows 11 Taskbar settings page (ms-settings:taskbar) where users can
    enable Ghostline under 'Other system tray icons'.
    """
    try:
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        return QDesktopServices.openUrl(QUrl("ms-settings:taskbar"))
    except Exception:
        try:
            os.system("start ms-settings:taskbar")
            return True
        except Exception as e:
            logger.warning("Could not open taskbar settings: %s", e)
            return False

