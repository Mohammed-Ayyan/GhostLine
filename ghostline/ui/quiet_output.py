"""
Ghostline — Quiet Output & Notification System.
Provides unobtrusive, discreet signaling channels for solve results and errors:
- Taskbar button flash (FlashWindowEx)
- Taskbar overlay icon badge (ITaskbarList3::SetOverlayIcon)
- System tray balloon/toast notifications
- Generic hardware status signals (Caps/Num LED pulse or keyboard backlight)
"""

import sys
import os
import time
import ctypes
from ctypes import wintypes
import logging
from typing import Optional, Any

from PyQt6.QtGui import QImage, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QBuffer, QTimer

user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32

# Win32 Constants
FLASHW_STOP = 0
FLASHW_CAPTION = 1
FLASHW_TRAY = 2
FLASHW_ALL = 3
FLASHW_TIMER = 4
FLASHW_TIMERNOFG = 12

class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]

# ITaskbarList3 COM Definitions
CLSID_TaskbarList = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
IID_ITaskbarList3 = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"


def flash_window(hwnd: int, count: int = 3) -> bool:
    """Flashes the taskbar button for hwnd unobtrusively using FlashWindowEx."""
    if not hwnd or sys.platform != "win32":
        return False
    try:
        fwi = FLASHWINFO()
        fwi.cbSize = ctypes.sizeof(FLASHWINFO)
        fwi.hwnd = hwnd
        fwi.dwFlags = FLASHW_TRAY | FLASHW_TIMERNOFG
        fwi.uCount = count
        fwi.dwTimeout = 0
        return bool(user32.FlashWindowEx(ctypes.byref(fwi)))
    except Exception as e:
        logging.debug("[QuietOutput] flash_window error: %s", e)
        return False


class TaskbarBadgeManager:
    """Manages ITaskbarList3 overlay badges on Windows taskbar icons."""

    def __init__(self):
        self._taskbar_list = None
        self._fn_set_overlay = None
        self._current_hicon = None
        self._clear_timer: Optional[QTimer] = None
        self._init_com()

    def _init_com(self):
        if sys.platform != "win32":
            return
        try:
            import comtypes
            clsid = comtypes.GUID(CLSID_TaskbarList)
            iid = comtypes.GUID(IID_ITaskbarList3)
            p_unk = ctypes.c_void_p()
            hr = ole32.CoCreateInstance(
                ctypes.byref(clsid),
                None,
                1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(iid),
                ctypes.byref(p_unk)
            )
            if hr == 0 and p_unk.value:
                self._taskbar_list = p_unk
                vtable_ptr = ctypes.cast(p_unk.value, ctypes.POINTER(ctypes.c_void_p))[0]
                vtable = ctypes.cast(vtable_ptr, ctypes.POINTER(ctypes.c_void_p))
                # Method 18: SetOverlayIcon(this, hwnd, hIcon, pszDescription)
                proto = ctypes.WINFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_void_p,
                    wintypes.HWND,
                    wintypes.HICON,
                    wintypes.LPCWSTR
                )
                self._fn_set_overlay = proto(vtable[18])
        except Exception as e:
            logging.debug("[QuietOutput] Taskbar COM init note: %s", e)

    def create_badge_icon(self, text: str, bg_color: str = "#10b981", fg_color: str = "#ffffff") -> int:
        """Renders a 16x16 icon with the badge letter and returns an HICON handle."""
        try:
            img = QImage(16, 16, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setBrush(QColor(bg_color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(0, 0, 15, 15)
            p.setPen(QColor(fg_color))
            font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, str(text)[:2])
            p.end()

            buf = QBuffer()
            buf.open(QBuffer.OpenModeFlag.ReadWrite)
            img.save(buf, "PNG")
            png_bytes = bytes(buf.data())

            hicon = user32.CreateIconFromResourceEx(
                png_bytes, len(png_bytes), True, 0x00030000, 16, 16, 0
            )
            return hicon
        except Exception as e:
            logging.debug("[QuietOutput] create_badge_icon error: %s", e)
            return 0

    def set_badge(self, hwnd: int, text: str, description: str = "", duration_sec: float = 8.0) -> bool:
        """Sets an overlay icon badge on the window's taskbar button."""
        if not hwnd or not self._taskbar_list or not self._fn_set_overlay:
            return False

        self.clear_badge(hwnd)

        bg = "#10b981"  # Emerald green for normal
        if text in ("?", "!"):
            bg = "#ef4444"  # Red for error/uncertain

        hicon = self.create_badge_icon(text, bg_color=bg)
        if not hicon:
            return False

        self._current_hicon = hicon
        try:
            res = self._fn_set_overlay(self._taskbar_list, hwnd, hicon, description or text)
            if res == 0:
                # Set up auto-clear timer
                if duration_sec > 0:
                    self._clear_timer = QTimer()
                    self._clear_timer.setSingleShot(True)
                    self._clear_timer.timeout.connect(lambda: self.clear_badge(hwnd))
                    self._clear_timer.start(int(duration_sec * 1000))
                return True
        except Exception as e:
            logging.debug("[QuietOutput] SetOverlayIcon call note: %s", e)
        return False

    def clear_badge(self, hwnd: int) -> bool:
        """Clears the overlay icon badge."""
        if self._clear_timer and self._clear_timer.isActive():
            self._clear_timer.stop()
            self._clear_timer = None

        if self._current_hicon:
            try:
                user32.DestroyIcon(self._current_hicon)
            except Exception:
                pass
            self._current_hicon = None

        if not hwnd or not self._taskbar_list or not self._fn_set_overlay:
            return False

        try:
            res = self._fn_set_overlay(self._taskbar_list, hwnd, 0, None)
            return res == 0
        except Exception:
            return False


# Singleton instances
_taskbar_mgr: Optional[TaskbarBadgeManager] = None

def get_taskbar_badge_manager() -> TaskbarBadgeManager:
    global _taskbar_mgr
    if _taskbar_mgr is None:
        _taskbar_mgr = TaskbarBadgeManager()
    return _taskbar_mgr


def dispatch_quiet_result(
    config: Any,
    presentation: Any,
    hwnd: Optional[int] = None,
    tray: Optional[Any] = None,
    lighting_mgr: Optional[Any] = None
) -> None:
    """
    Dispatches quiet result signals across all enabled channels without unhiding any HUD.
    """
    badge = getattr(presentation, "badge", "") or "✓"
    headline = getattr(presentation, "headline", "Result Ready")
    is_error = not getattr(presentation, "is_validated", True)

    # 1. Taskbar Flash
    if hwnd and getattr(config, "quiet_taskbar_flash", True):
        flash_window(hwnd, count=2 if not is_error else 3)

    # 2. Taskbar Badge
    if hwnd and getattr(config, "quiet_taskbar_badge", True):
        mgr = get_taskbar_badge_manager()
        mgr.set_badge(hwnd, badge if not is_error else "?", description=headline, duration_sec=8.0)

    # 3. Tray Balloon (Disabled by default to prevent unwanted popups on AI answers; respects quiet_tray_notification)
    if tray and getattr(config, "quiet_tray_notification", False):
        if hasattr(tray, "show_balloon"):
            tray.show_balloon(
                title=f"Ghostline \u2014 {headline}",
                text=str(getattr(presentation, "direct_answer", "") or headline),
                icon_type="info" if not is_error else "warning"
            )

    # 4. Hardware Generic Signal (Single pulse <= 3 Hz; NEVER encoding answer letters)
    if lighting_mgr and getattr(config, "quiet_hardware_signal", False):
        try:
            # Single pulse as generic "ready" signal
            lighting_mgr.start_flash(target="caps_lock", count=1, speed="medium")
        except Exception as e:
            logging.debug("[QuietOutput] Hardware signal note: %s", e)


def dispatch_quiet_error(
    config: Any,
    error_message: str,
    hwnd: Optional[int] = None,
    tray: Optional[Any] = None,
    lighting_mgr: Optional[Any] = None
) -> None:
    """Dispatches error signal across enabled quiet channels."""
    # 1. Taskbar Flash
    if hwnd and getattr(config, "quiet_taskbar_flash", True):
        flash_window(hwnd, count=3)

    # 2. Taskbar Badge
    if hwnd and getattr(config, "quiet_taskbar_badge", True):
        mgr = get_taskbar_badge_manager()
        mgr.set_badge(hwnd, "!", description=error_message, duration_sec=8.0)

    # 3. Tray Balloon
    if tray and getattr(config, "quiet_tray_notification", True):
        if hasattr(tray, "show_balloon"):
            tray.show_balloon(
                title="Ghostline Error",
                text=error_message[:120],
                icon_type="error"
            )

    # 4. Hardware Generic Error Pulse
    if lighting_mgr and getattr(config, "quiet_hardware_signal", False):
        try:
            lighting_mgr.start_flash(target="caps_lock", count=2, speed="fast")
        except Exception as e:
            logging.debug("[QuietOutput] Hardware error signal note: %s", e)

