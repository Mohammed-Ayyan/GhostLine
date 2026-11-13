"""
Window geometry and screen resolution helpers.
Provides central work area calculation, screen boundary validation, and E2E fake screen simulation.
"""

import os
import re
import ctypes
from typing import Optional
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QScreen, QGuiApplication


def get_work_area(screen: Optional[QScreen] = None) -> QRect:
    """
    Returns the usable desktop work area (screen geometry minus taskbars/docks).
    Supports E2E fake screen simulation when GHOSTLINE_E2E=1 and GHOSTLINE_E2E_FAKE_SCREEN is set.
    Format: '<W>x<H>@<scale>' (e.g. '800x600@100', '1366x768@150').
    Subtracts a standard 48px taskbar from the height.
    """
    # 1. E2E Fake Screen override (test-only, active when GHOSTLINE_E2E_FAKE_SCREEN is set)
    fake_spec = os.environ.get("GHOSTLINE_E2E_FAKE_SCREEN")
    if fake_spec:
        m = re.match(r"^(\d+)[xX](\d+)(?:@(\d+(?:\.\d+)?))?$", fake_spec.strip())
        if m:
            w_phys = int(m.group(1))
            h_phys = int(m.group(2))
            raw_scale = float(m.group(3)) if m.group(3) else 100.0
            scale_factor = (raw_scale / 100.0) if raw_scale >= 50.0 else raw_scale
            if scale_factor <= 0:
                scale_factor = 1.0

            # Subtract 48 px taskbar in physical pixels, clamp to at least 200px
            h_work_phys = max(200, h_phys - 48)

            # Logical dimensions for Qt widgets
            logical_w = int(w_phys / scale_factor)
            logical_h = int(h_work_phys / scale_factor)
            return QRect(0, 0, logical_w, logical_h)

    # 2. Qt Screen Available Geometry
    if screen is not None:
        try:
            return screen.availableGeometry()
        except Exception:
            pass

    app = QApplication.instance()
    if app:
        try:
            primary = app.primaryScreen()
            if primary:
                return primary.availableGeometry()
        except Exception:
            pass

    # 3. Native Win32 SPI_GETWORKAREA fallback
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]
        rect = RECT()
        SPI_GETWORKAREA = 0x0030
        if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass

    # 4. Standard 1080p fallback (1920x1032 with 48px taskbar)
    return QRect(0, 0, 1920, 1032)


def get_screen_at_point(pos: QPoint) -> Optional[QScreen]:
    """Finds the QScreen that contains the given coordinate point."""
    app = QApplication.instance()
    if not app:
        return None
    try:
        for s in app.screens():
            if s.geometry().contains(pos):
                return s
        return app.primaryScreen()
    except Exception:
        return None


def validate_window_geometry(
    x: Optional[int] = None,
    y: Optional[int] = None,
    w: Optional[int] = None,
    h: Optional[int] = None,
    min_visible_px: int = 100,
    **kwargs
) -> QRect:
    """
    Validates saved window geometry against active screens or simulated work area.
    If geometry is invalid, off-screen, or too large, falls back to 85% of work area, centered.
    Supports either positional x, y, w, h or kwargs pos_x, pos_y, width, height.
    """
    x = x if x is not None else kwargs.get("pos_x")
    y = y if y is not None else kwargs.get("pos_y")
    w = w if w is not None else kwargs.get("width")
    h = h if h is not None else kwargs.get("height")
    work = get_work_area()

    if w is None or h is None or w <= 0 or h <= 0:
        return get_default_centered_geometry(work)

    clamped_w = min(w, work.width())
    clamped_h = min(h, work.height())

    if x is None or y is None:
        center_x = max(0, work.x() + (work.width() - clamped_w) // 2)
        center_y = max(0, work.y() + (work.height() - clamped_h) // 2)
        return QRect(center_x, center_y, clamped_w, clamped_h)

    # Check minimum visibility
    win_rect = QRect(x, y, clamped_w, clamped_h)

    # If in E2E fake screen mode, validate strictly within fake work area
    if os.environ.get("GHOSTLINE_E2E") == "1" and os.environ.get("GHOSTLINE_E2E_FAKE_SCREEN"):
        intersect = win_rect.intersected(work)
        if intersect.width() < min_visible_px or intersect.height() < min_visible_px or w > work.width() or h > work.height():
            return get_default_centered_geometry(work)
        return win_rect

    # Live multi-monitor check
    app = QApplication.instance()
    if app:
        screens = app.screens()
        has_visible_screen = False
        for s in screens:
            intersect = win_rect.intersected(s.availableGeometry())
            if intersect.width() >= min_visible_px and intersect.height() >= min_visible_px:
                has_visible_screen = True
                break
        if not has_visible_screen:
            return get_default_centered_geometry(work)

    # Prevent window larger than work area
    if w > work.width() or h > work.height():
        return get_default_centered_geometry(work)

    return win_rect


def get_default_centered_geometry(work_area: Optional[QRect] = None, fraction: float = 0.85) -> QRect:
    """Calculates a centered window rectangle occupying fraction (default 85%) of work area."""
    work = work_area if work_area is not None else get_work_area()
    target_w = max(760, int(work.width() * fraction))
    target_h = max(520, int(work.height() * fraction))

    # Clamp to work area bounds
    target_w = min(target_w, work.width())
    target_h = min(target_h, work.height())

    x = work.x() + (work.width() - target_w) // 2
    y = work.y() + (work.height() - target_h) // 2
    return QRect(x, y, target_w, target_h)
