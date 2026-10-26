import os
import sys
import json
import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
from PIL import Image, ImageGrab, ImageDraw

# Enable Per-Monitor DPI Awareness V2 to ensure cursor and window coordinates match physical pixels
try:
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong)
    ]

# Capture mode constants
CAPTURE_MODE_FULL_SCREEN = "full_screen"
CAPTURE_MODE_ACTIVE_WINDOW = "active_window"
CAPTURE_MODE_CURSOR_MONITOR = "cursor_monitor"
CAPTURE_MODE_PRIMARY_MONITOR = "primary_monitor"
CAPTURE_MODE_CURSOR = "cursor"

def get_display_topology() -> Dict[str, Any]:
    """
    Queries Windows display topology:
    - Primary monitor size
    - Multi-monitor count and virtual screen bounds
    - Individual monitor physical rectangles
    - System DPI scaling factors
    """
    diag: Dict[str, Any] = {
        "monitor_count": 1,
        "primary_screen": (1920, 1080),
        "virtual_screen": (0, 0, 1920, 1080),
        "monitors": [],
        "dpi_scaling": 1.0,
    }
    if sys.platform != "win32":
        return diag

    try:
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        diag["primary_screen"] = (sw, sh)

        mon_count = user32.GetSystemMetrics(80)  # SM_CMONITORS
        diag["monitor_count"] = max(1, mon_count)

        v_left = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        v_top = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
        v_width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        v_height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
        if v_width <= 0:
            v_width = sw if sw > 0 else 1920
        if v_height <= 0:
            v_height = sh if sh > 0 else 1080
        v_right = v_left + v_width
        v_bottom = v_top + v_height
        diag["virtual_screen"] = (v_left, v_top, v_right, v_bottom)

        # Enumerate individual monitors
        monitors_list: List[Dict[str, int]] = []
        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM
        )

        def _enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
                r = mi.rcMonitor
                monitors_list.append({
                    "left": r.left,
                    "top": r.top,
                    "right": r.right,
                    "bottom": r.bottom,
                    "width": r.right - r.left,
                    "height": r.bottom - r.top,
                    "is_primary": bool(mi.dwFlags & 1)
                })
            return True

        user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_enum_proc), 0)
        diag["monitors"] = monitors_list

        # Estimate primary DPI
        try:
            dpi = user32.GetDpiForSystem()
            diag["dpi_scaling"] = round(dpi / 96.0, 2)
        except Exception:
            diag["dpi_scaling"] = 1.0

    except Exception as e:
        diag["error"] = str(e)

    return diag

def get_cursor_position() -> Tuple[int, int]:
    """
    Returns current mouse cursor (x, y) coordinates on the screen.
    Gracefully falls back to primary monitor center if headless or error.
    """
    pt = POINT()
    try:
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return (pt.x, pt.y)
    except Exception:
        pass

    try:
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        return (sw // 2, sh // 2)
    except Exception:
        return (960, 540)

def get_monitor_bounds_for_point(x: int, y: int) -> Tuple[int, int, int, int]:
    """
    Returns (left, top, right, bottom) of the display monitor containing (x, y).
    """
    if sys.platform != "win32":
        return (0, 0, 1920, 1080)

    try:
        user32 = ctypes.windll.user32
        pt = POINT(x, y)
        # MONITOR_DEFAULTTONEAREST = 2
        hmon = user32.MonitorFromPoint(pt, 2)
        if hmon:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcMonitor
                return (r.left, r.top, r.right, r.bottom)
    except Exception:
        pass

    sw = ctypes.windll.user32.GetSystemMetrics(0) or 1920
    sh = ctypes.windll.user32.GetSystemMetrics(1) or 1080
    return (0, 0, sw, sh)

def inspect_capture_environment() -> Dict[str, Any]:
    """
    Inspects the active foreground window environment:
    - Foreground window HWND, sanitized title, class name
    - Window bounding rect (using DwmGetWindowAttribute when available)
    - Fullscreen detection
    - Windows Display Affinity (WDA_MONITOR / WDA_EXCLUDEFROMCAPTURE)
    - Virtual screen & display topology
    """
    topology = get_display_topology()
    diag: Dict[str, Any] = {
        "hwnd": 0,
        "title": "",
        "class_name": "",
        "window_rect": None,
        "is_fullscreen": False,
        "display_affinity": 0,
        "is_capture_protected": False,
        "topology": topology
    }
    if sys.platform != "win32":
        return diag

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return diag

        # Check if foreground window belongs to Ghostline itself
        my_pid = os.getpid()
        fg_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(fg_pid))
        if fg_pid.value == my_pid:
            # Foreground window is Ghostline's own window/HUD; resolve target window under cursor
            pt = POINT()
            target_found = False
            if user32.GetCursorPos(ctypes.byref(pt)):
                cand_hwnd = user32.WindowFromPoint(pt)
                root_cand = user32.GetAncestor(cand_hwnd, 2) if cand_hwnd else 0  # GA_ROOT = 2
                if root_cand:
                    c_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(root_cand, ctypes.byref(c_pid))
                    if c_pid.value != my_pid and user32.IsWindowVisible(root_cand):
                        hwnd = root_cand
                        target_found = True
            if not target_found:
                # Fallback to topmost non-Ghostline visible window
                top_hwnd = user32.GetTopWindow(0)
                while top_hwnd:
                    t_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(top_hwnd, ctypes.byref(t_pid))
                    if t_pid.value != my_pid and user32.IsWindowVisible(top_hwnd):
                        if user32.GetWindowTextLengthW(top_hwnd) > 0:
                            hwnd = top_hwnd
                            break
                    top_hwnd = user32.GetWindow(top_hwnd, 2)  # GW_HWNDNEXT = 2

        diag["hwnd"] = hwnd
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        raw_title = title_buf.value
        # Sanitize title length for log privacy
        diag["title"] = raw_title[:64] if raw_title else ""

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        diag["class_name"] = class_buf.value

        # Window Rect: Try DWM extended frame bounds first for exact pixel border
        rect = RECT()
        got_rect = False
        try:
            # DWMWA_EXTENDED_FRAME_BOUNDS = 9
            hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
            )
            if hr == 0 and (rect.right > rect.left) and (rect.bottom > rect.top):
                got_rect = True
        except Exception:
            pass

        if not got_rect:
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                got_rect = True

        if got_rect:
            diag["window_rect"] = (rect.left, rect.top, rect.right, rect.bottom)
            sw, sh = topology["primary_screen"]
            if rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh:
                diag["is_fullscreen"] = True

        # Check SetWindowDisplayAffinity
        affinity = ctypes.c_uint32(0)
        if hasattr(user32, "GetWindowDisplayAffinity"):
            if user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity)):
                diag["display_affinity"] = affinity.value
                if affinity.value > 0:
                    diag["is_capture_protected"] = True
                    logging.warning(
                        "[Capture Diagnostic] Target window HWND %s has Display Affinity %d (Capture Protected)",
                        hwnd, affinity.value
                    )
    except Exception as e:
        diag["error"] = str(e)

    return diag

def capture_screen(
    mode: str = CAPTURE_MODE_FULL_SCREEN,
    width: int = 900,
    height: int = 600,
    offset_y_ratio: float = 0.2,
    custom_bbox: Optional[Tuple[int, int, int, int]] = None,
    diagnostic_mode: bool = False,
    excluded_rects: Optional[List[Tuple[int, int, int, int]]] = None
) -> Tuple[Image.Image, Tuple[int, int, int, int], Dict[str, Any]]:
    """
    Captures screen region according to configurable mode:
    - 'full_screen': Virtual desktop across all connected monitors.
    - 'active_window': Exact bounding frame of current foreground window.
    - 'cursor_monitor': The specific monitor containing mouse cursor.
    - 'primary_monitor': Primary display surface (0, 0, w, h).
    - 'cursor': Fixed-size bounding box around mouse cursor.
    
    Returns:
        (PIL Image, bbox (left, top, right, bottom), diagnostic_metadata)
    """
    diag = inspect_capture_environment()
    topology = diag.get("topology", get_display_topology())
    v_left, v_top, v_right, v_bottom = topology.get("virtual_screen", (0, 0, 1920, 1080))
    v_width = v_right - v_left
    v_height = v_bottom - v_top

    cx, cy = get_cursor_position()
    diag["cursor"] = (cx, cy)
    diag["configured_mode"] = mode

    # Determine bounding box
    effective_mode = mode
    bbox: Tuple[int, int, int, int]

    if custom_bbox is not None:
        bbox = custom_bbox
        effective_mode = "custom_bbox"
    elif mode == CAPTURE_MODE_FULL_SCREEN:
        bbox = (v_left, v_top, v_right, v_bottom)
    elif mode == CAPTURE_MODE_PRIMARY_MONITOR:
        sw, sh = topology.get("primary_screen", (1920, 1080))
        bbox = (0, 0, sw, sh)
    elif mode == CAPTURE_MODE_CURSOR_MONITOR:
        bbox = get_monitor_bounds_for_point(cx, cy)
    elif mode == CAPTURE_MODE_ACTIVE_WINDOW:
        w_rect = diag.get("window_rect")
        if w_rect and (w_rect[2] > w_rect[0]) and (w_rect[3] > w_rect[1]):
            # Clamp window rect to virtual screen bounds
            l = max(v_left, min(w_rect[0], v_right - 100))
            t = max(v_top, min(w_rect[1], v_bottom - 100))
            r = min(v_right, max(w_rect[2], l + 100))
            b = min(v_bottom, max(w_rect[3], t + 100))
            bbox = (l, t, r, b)
        else:
            # Fallback to cursor monitor if no active window rect
            logging.info("[Capture] No valid active window rect detected; falling back to cursor monitor.")
            bbox = get_monitor_bounds_for_point(cx, cy)
            effective_mode = "cursor_monitor_fallback"
    else:  # CAPTURE_MODE_CURSOR
        left = int(cx - (width / 2))
        top = int(cy - (height * offset_y_ratio))
        left = max(v_left, min(left, v_right - width))
        top = max(v_top, min(top, v_bottom - height))
        bbox = (left, top, left + width, top + height)

    diag["bbox"] = bbox
    diag["effective_mode"] = effective_mode
    bbox_w = bbox[2] - bbox[0]
    bbox_h = bbox[3] - bbox[1]

    # Perform ImageGrab
    screenshot: Optional[Image.Image] = None
    grab_method = "unknown"

    try:
        # ImageGrab with all_screens=True supports multi-monitor and virtual desktop coordinates
        screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
        grab_method = "all_screens"
    except Exception as e_all:
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            grab_method = "primary_only"
        except Exception as e_prim:
            # Synthetic fallback for headless testing environments
            screenshot = Image.new("RGB", (max(10, bbox_w), max(10, bbox_h)), (255, 255, 255))
            grab_method = "synthetic_fallback"
            diag["grab_error"] = f"{type(e_all).__name__}: {e_all} | {type(e_prim).__name__}: {e_prim}"

    diag["grab_method"] = grab_method
    diag["image_size"] = screenshot.size if screenshot else (0, 0)

    # Exclude designated windows (e.g. Ghostline HUD) by masking them out
    if screenshot is not None and excluded_rects:
        try:
            draw = ImageDraw.Draw(screenshot)
            for ex in excluded_rects:
                if len(ex) == 4:
                    ex_l, ex_t, ex_r, ex_b = ex
                    int_l = max(bbox[0], ex_l)
                    int_t = max(bbox[1], ex_t)
                    int_r = min(bbox[2], ex_r)
                    int_b = min(bbox[3], ex_b)
                    if int_r > int_l and int_b > int_t:
                        rel_l = int_l - bbox[0]
                        rel_t = int_t - bbox[1]
                        rel_r = int_r - bbox[0]
                        rel_b = int_b - bbox[1]
                        draw.rectangle([rel_l, rel_t, rel_r, rel_b], fill=(255, 255, 255))
                        logging.debug("[Capture] Masked excluded window rect (%d, %d, %d, %d)", rel_l, rel_t, rel_r, rel_b)
        except Exception as ex_mask:
            logging.debug("[Capture] Excluded rect masking error: %s", ex_mask)

    # Blank frame / uniform surface check (e.g. DRM, black screen, lockscreen)
    try:
        gray = screenshot.convert("L")
        extrema = gray.getextrema()
        diag["pixel_extrema"] = extrema
        if extrema[0] == extrema[1]:
            diag["is_blank_frame"] = True
            logging.warning(
                "[Capture Diagnostic] Captured image is uniform (all pixels=%d). "
                "Possible cause: DRM, display affinity, or minimized window.",
                extrema[0]
            )
        else:
            diag["is_blank_frame"] = False
    except Exception:
        diag["is_blank_frame"] = False

    # Log safe diagnostic telemetry (dimensions, coordinates, DPI, mode)
    logging.info(
        "[Capture Telemetry] Mode: %s (req: %s) | Size: %dx%d | BBox: %s | Monitors: %d | DPI Scale: %s | Method: %s | Blank: %s | Protected: %s",
        effective_mode, mode, screenshot.width, screenshot.height,
        bbox, topology.get("monitor_count", 1), topology.get("dpi_scaling", 1.0),
        grab_method, diag.get("is_blank_frame", False), diag.get("is_capture_protected", False)
    )

    if diagnostic_mode:
        save_diagnostic_artifacts(screenshot, diag_info=diag)

    return screenshot, bbox, diag

def capture_screen_around_cursor(
    width: int = 900, 
    height: int = 600, 
    offset_y_ratio: float = 0.2
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """Backward-compatible wrapper for cursor region capture."""
    screenshot, bbox, _ = capture_screen(
        mode=CAPTURE_MODE_CURSOR,
        width=width,
        height=height,
        offset_y_ratio=offset_y_ratio
    )
    return screenshot, bbox

def capture_screen_around_cursor_with_diagnostics(
    width: int = 900,
    height: int = 600,
    offset_y_ratio: float = 0.2
) -> Tuple[Image.Image, Tuple[int, int, int, int], Dict[str, Any]]:
    """Backward-compatible wrapper for cursor region capture with diagnostics."""
    return capture_screen(
        mode=CAPTURE_MODE_CURSOR,
        width=width,
        height=height,
        offset_y_ratio=offset_y_ratio
    )

def save_diagnostic_artifacts(
    screenshot: Optional[Image.Image] = None,
    ocr_data: Optional[Dict[str, Any]] = None,
    parsed_question: Optional[Any] = None,
    diag_info: Optional[Dict[str, Any]] = None,
    directory: Optional[Path] = None
) -> Path:
    """
    Saves capture preview image, OCR JSON, and pipeline telemetry
    to reproduce failures in diagnostic mode.
    """
    if directory is None:
        try:
            from ghostline.config import get_app_dir
            directory = get_app_dir() / "diagnostics"
        except Exception:
            app_data = os.environ.get("APPDATA")
            base = Path(app_data) / "Ghostline" if app_data else Path.home() / ".ghostline"
            directory = base / "diagnostics"
    
    directory.mkdir(parents=True, exist_ok=True)

    try:
        if screenshot is not None:
            img_path = directory / "latest_capture.png"
            screenshot.save(img_path, format="PNG")

        meta: Dict[str, Any] = {}
        if diag_info:
            meta["capture_diagnostics"] = diag_info
        if ocr_data:
            meta["ocr_stats"] = {
                "text_length": len(ocr_data.get("text", "")),
                "lines_count": len(ocr_data.get("lines", [])),
                "has_boxes": bool(ocr_data.get("line_boxes")),
                "text_angle": ocr_data.get("text_angle", 0.0)
            }
            with open(directory / "latest_ocr.json", "w", encoding="utf-8") as f:
                json.dump(ocr_data, f, indent=2)

        if parsed_question:
            pq_dict = getattr(parsed_question, "model_dump", None)
            if callable(pq_dict):
                meta["parsed_question"] = pq_dict()
            elif hasattr(parsed_question, "__dict__"):
                meta["parsed_question"] = str(parsed_question)

        with open(directory / "latest_metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, default=str)

    except Exception as e:
        logging.warning("[Capture Diagnostics] Could not write diagnostic artifacts: %s", e)

    return directory
