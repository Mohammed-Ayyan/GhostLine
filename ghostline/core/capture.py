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

def ensure_thread_desktop_access():
    """Ensures calling thread has access to the interactive desktop station."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)  # GENERIC_ALL
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            user32.CloseDesktop(hdesk)
    except Exception:
        pass

def _mss_screen_capture(bbox: Tuple[int, int, int, int]) -> Optional[Image.Image]:
    """
    Captures screen bbox using mss as fallback when PIL or GDI BitBlt fails or returns blank frames.
    """
    try:
        ensure_thread_desktop_access()
        import mss
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return None
        with mss.MSS() as sct:
            monitor = {"top": y1, "left": x1, "width": width, "height": height}
            grab = sct.grab(monitor)
            return Image.frombytes("RGB", grab.size, grab.bgra, "raw", "BGRX")
    except Exception as ex:
        logging.warning("[Capture] MSS screen capture fallback failed: %s", ex)
        return None

def _gdi_screen_capture(bbox: Tuple[int, int, int, int]) -> Optional[Image.Image]:
    """
    Fallback desktop capture using Win32 GDI BitBlt and OpenDesktopW.
    Used when PIL ImageGrab fails or when running in background threads without an active desktop context.
    """
    if sys.platform != "win32":
        return None
    try:
        ensure_thread_desktop_access()
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return None

        hwnd = 0  # Desktop window
        hdc_screen = user32.GetDC(hwnd)
        if not hdc_screen:
            return None
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        old_bm = gdi32.SelectObject(hdc_mem, hbm)

        # SRCCOPY = 0x00CC0020, CAPTUREBLT = 0x40000000
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x1, y1, 0x00CC0020 | 0x40000000)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # Top-down bitmap
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        buf = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(hdc_mem, hbm, 0, height, buf, ctypes.byref(bmi), 0)

        # Cleanup GDI handles
        gdi32.SelectObject(hdc_mem, old_bm)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_screen)

        if lines > 0:
            img = Image.frombuffer("RGBA", (width, height), buf.raw, "raw", "BGRA", 0, 1)
            return img.convert("RGB")
    except Exception as ex:
        logging.warning("[Capture] GDI BitBlt capture fallback failed: %s", ex)
    return None

def capture_screen(
    mode: str = CAPTURE_MODE_FULL_SCREEN,
    width: int = 1400,
    height: int = 900,
    offset_y_ratio: float = 0.50,
    custom_bbox: Optional[Tuple[int, int, int, int]] = None,
    diagnostic_mode: bool = False,
    excluded_rects: Optional[List[Tuple[int, int, int, int]]] = None
) -> Tuple[Image.Image, Tuple[int, int, int, int], Dict[str, Any]]:
    """
    Captures screen region according to configurable mode:
    - 'full_screen': The monitor under the mouse cursor (Alt + Shift + /).
    - 'cursor': Generous rectangular region (~1400x900) centered on mouse cursor, clamped strictly to monitor bounds (Alt + /).
    - 'active_window': Exact bounding frame of current foreground window.
    - 'cursor_monitor': The specific monitor containing mouse cursor.
    - 'primary_monitor': Primary display surface (0, 0, w, h).
    
    Returns:
        (PIL Image, bbox (left, top, right, bottom), diagnostic_metadata)
    """
    ensure_thread_desktop_access()
    diag = inspect_capture_environment()
    topology = diag.get("topology", get_display_topology())
    v_left, v_top, v_right, v_bottom = topology.get("virtual_screen", (0, 0, 1920, 1080))

    cx, cy = get_cursor_position()
    diag["cursor"] = (cx, cy)
    diag["configured_mode"] = mode

    # Determine bounding box
    effective_mode = mode
    bbox: Tuple[int, int, int, int]

    if custom_bbox is not None:
        bbox = custom_bbox
        effective_mode = "custom_bbox"
    elif mode in (CAPTURE_MODE_FULL_SCREEN, "full_screen", CAPTURE_MODE_CURSOR_MONITOR, "cursor_monitor"):
        # For full-screen hotkey (Alt + Shift + /), capture the specific monitor under cursor
        bbox = get_monitor_bounds_for_point(cx, cy)
        effective_mode = "cursor_monitor"
    elif mode == CAPTURE_MODE_PRIMARY_MONITOR:
        sw, sh = topology.get("primary_screen", (1920, 1080))
        bbox = (0, 0, sw, sh)
    elif mode == CAPTURE_MODE_ACTIVE_WINDOW:
        w_rect = diag.get("window_rect")
        if w_rect and (w_rect[2] > w_rect[0]) and (w_rect[3] > w_rect[1]):
            l = max(v_left, min(w_rect[0], v_right - 100))
            t = max(v_top, min(w_rect[1], v_bottom - 100))
            r = min(v_right, max(w_rect[2], l + 100))
            b = min(v_bottom, max(w_rect[3], t + 100))
            bbox = (l, t, r, b)
        else:
            logging.info("[Capture] No valid active window rect detected; falling back to cursor monitor.")
            bbox = get_monitor_bounds_for_point(cx, cy)
            effective_mode = "cursor_monitor_fallback"
    elif mode in (CAPTURE_MODE_CURSOR, "cursor", "cursor_centered"):
        m_left, m_top, m_right, m_bottom = get_monitor_bounds_for_point(cx, cy)
        m_width = m_right - m_left
        m_height = m_bottom - m_top
        w = min(width, m_width)
        h = min(height, m_height)

        # Center horizontally on cursor, center vertically around cursor (ratio 0.50 by default)
        left = int(cx - (w / 2))
        top = int(cy - (h * offset_y_ratio))

        # Strictly clamp within monitor boundaries containing cursor
        left = max(m_left, min(left, m_right - w))
        top = max(m_top, min(top, m_bottom - h))
        bbox = (left, top, left + w, top + h)
    else:
        # Fallback to cursor monitor
        bbox = get_monitor_bounds_for_point(cx, cy)

    diag["bbox"] = bbox
    diag["effective_mode"] = effective_mode

    # Perform ImageGrab with MSS and GDI BitBlt fallbacks
    screenshot: Optional[Image.Image] = None
    grab_method = "unknown"

    try:
        screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
        grab_method = "all_screens"
    except Exception as e_all:
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            grab_method = "primary_only"
        except Exception as e_prim:
            logging.info("[Capture] ImageGrab failed (%s / %s); attempting MSS fallback...", e_all, e_prim)
            mss_img = _mss_screen_capture(bbox)
            if mss_img is not None:
                screenshot = mss_img
                grab_method = "mss"
            else:
                logging.info("[Capture] MSS failed; attempting GDI BitBlt fallback...")
                gdi_img = _gdi_screen_capture(bbox)
                if gdi_img is not None:
                    screenshot = gdi_img
                    grab_method = "gdi_bitblt"
                else:
                    err_msg = f"Screen capture failed: {e_all} | {e_prim}. Both MSS and GDI fallbacks failed."
                    diag["grab_error"] = err_msg
                    logging.error("[Capture] %s", err_msg)
                    raise RuntimeError(err_msg)

    # Blank frame / uniform surface check (e.g. BitBlt failure or black frame)
    is_blank = False
    try:
        gray = screenshot.convert("L")
        extrema = gray.getextrema()
        diag["pixel_extrema"] = extrema
        if extrema[0] == extrema[1]:
            is_blank = True
            logging.warning("[Capture] Primary grab returned blank/uniform image (pixels=%d). Trying MSS/GDI fallback...", extrema[0])
            # Attempt MSS fallback for blank frames
            alt_img = _mss_screen_capture(bbox)
            if alt_img is not None:
                alt_gray = alt_img.convert("L")
                alt_extrema = alt_gray.getextrema()
                if alt_extrema[0] != alt_extrema[1]:
                    screenshot = alt_img
                    grab_method = "mss_fallback_from_blank"
                    is_blank = False
                    diag["pixel_extrema"] = alt_extrema

            if is_blank:
                # Attempt GDI fallback
                gdi_img = _gdi_screen_capture(bbox)
                if gdi_img is not None:
                    gdi_gray = gdi_img.convert("L")
                    gdi_extrema = gdi_gray.getextrema()
                    if gdi_extrema[0] != gdi_extrema[1]:
                        screenshot = gdi_img
                        grab_method = "gdi_fallback_from_blank"
                        is_blank = False
                        diag["pixel_extrema"] = gdi_extrema
    except Exception:
        pass

    diag["is_blank_frame"] = is_blank
    diag["grab_method"] = grab_method
    diag["image_size"] = screenshot.size if screenshot else (0, 0)

    # Note: Destructive white rectangle painting over excluded_rects is intentionally omitted
    # to avoid obliterating questions under transparent/layered windows.

    # Log safe diagnostic telemetry
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
    width: int = 1400, 
    height: int = 900, 
    offset_y_ratio: float = 0.50
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
    width: int = 1400,
    height: int = 900,
    offset_y_ratio: float = 0.50
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

def save_stage_debug_dump(
    raw_img: Optional[Image.Image],
    crop_bbox: Tuple[int, int, int, int],
    preprocessed_img: Optional[Image.Image],
    raw_ocr_data: Optional[Dict[str, Any]],
    filtered_text: str,
    parsed_question: Optional[Any],
    prompt_sent: str,
    raw_llm_response: str
) -> Path:
    """
    Saves comprehensive stage debug dump to %APPDATA%\\Ghostline\\debug\\<timestamp>\\:
    - Raw captured image
    - Cropped region and its coordinates
    - Image after preprocessing
    - Raw OCR text with word boxes and confidence
    - Text after filtering
    - Parsed question and options
    - The exact prompt sent to the LLM
    - The raw LLM response
    """
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) / "Ghostline" if app_data else Path.home() / ".ghostline"
    timestamp_str = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
    dump_dir = base / "debug" / timestamp_str
    dump_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Raw captured image
        if raw_img is not None:
            raw_img.save(dump_dir / "01_raw_capture.png", format="PNG")

        # 2. Cropped region and coordinates
        coords_info = {
            "bbox": crop_bbox,
            "left": crop_bbox[0],
            "top": crop_bbox[1],
            "right": crop_bbox[2],
            "bottom": crop_bbox[3],
            "width": crop_bbox[2] - crop_bbox[0],
            "height": crop_bbox[3] - crop_bbox[1]
        }
        with open(dump_dir / "02_crop_coordinates.json", "w", encoding="utf-8") as f:
            json.dump(coords_info, f, indent=2)

        if raw_img is not None:
            # Crop image file for stage 2
            raw_img.save(dump_dir / "02_cropped_region.png", format="PNG")

        # 3. Image after preprocessing
        if preprocessed_img is not None:
            preprocessed_img.save(dump_dir / "03_preprocessed.png", format="PNG")

        # 4. Raw OCR text with word boxes and confidence
        if raw_ocr_data is not None:
            with open(dump_dir / "04_raw_ocr.json", "w", encoding="utf-8") as f:
                json.dump(raw_ocr_data, f, indent=2, default=str)

        # 5. Text after filtering
        with open(dump_dir / "05_filtered_text.txt", "w", encoding="utf-8") as f:
            f.write(filtered_text or "")

        # 6. Parsed question and options
        pq_dict = {}
        if parsed_question is not None:
            dump_fn = getattr(parsed_question, "model_dump", None)
            if callable(dump_fn):
                pq_dict = dump_fn()
            elif hasattr(parsed_question, "__dict__"):
                pq_dict = parsed_question.__dict__
            else:
                pq_dict = {"raw": str(parsed_question)}
        with open(dump_dir / "06_parsed_question.json", "w", encoding="utf-8") as f:
            json.dump(pq_dict, f, indent=2, default=str)

        # 7. Exact prompt sent to LLM
        with open(dump_dir / "07_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt_sent or "")

        # 8. Raw LLM response
        with open(dump_dir / "08_raw_llm_response.txt", "w", encoding="utf-8") as f:
            f.write(raw_llm_response or "")

        logging.info("[Capture Diagnostics] Saved comprehensive stage debug dump to: %s", dump_dir)
    except Exception as e:
        logging.warning("[Capture Diagnostics] Failed to write stage debug dump: %s", e)

    return dump_dir
