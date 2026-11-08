"""
Ghostline Microsoft Fluent System Icons Provider.
Loads, recolors, and renders official Microsoft Fluent System Icons (MIT License) via QtSvg.
Includes caching, High-DPI devicePixelRatio support, and fallback mechanisms.
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional, Dict, Tuple

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

from ghostline.ui.theme.tokens import TEXT_PRIMARY, TEXT_SECONDARY, BRAND_TEXT, BRAND_FILL

# Cache for rendered QIcon and QPixmap objects: (name, color, size, dpr, filled) -> QIcon / QPixmap
_ICON_CACHE: Dict[Tuple[str, str, int, float, bool], QIcon] = {}
_PIXMAP_CACHE: Dict[Tuple[str, str, int, float, bool], QPixmap] = {}
_SVG_RAW_CACHE: Dict[str, str] = {}

# Logical name to Fluent filename mapping
ICON_NAME_MAP = {
    "settings": "ic_fluent_settings_24",
    "general": "ic_fluent_settings_24",
    "desktop": "ic_fluent_desktop_24",
    "mode": "ic_fluent_desktop_24",
    "monitor": "ic_fluent_desktop_24",
    "home": "ic_fluent_home_24",
    "dashboard": "ic_fluent_home_24",
    "mic": "ic_fluent_mic_24",
    "audio": "ic_fluent_mic_24",
    "sparkle": "ic_fluent_sparkle_24",
    "ai": "ic_fluent_sparkle_24",
    "model": "ic_fluent_sparkle_24",
    "history": "ic_fluent_history_24",
    "person": "ic_fluent_person_24",
    "profile": "ic_fluent_person_24",
    "shield": "ic_fluent_shield_24",
    "security": "ic_fluent_shield_24",
    "pulse": "ic_fluent_heart_pulse_24",
    "diagnostics": "ic_fluent_heart_pulse_24",
    "power": "ic_fluent_power_24",
    "exit": "ic_fluent_sign_out_24",
    "sign_out": "ic_fluent_sign_out_24",
    "brightness": "ic_fluent_brightness_high_24",
    "hardware": "ic_fluent_brightness_high_24",
    "copy": "ic_fluent_copy_24",
    "refresh": "ic_fluent_arrow_clockwise_24",
    "check": "ic_fluent_checkmark_24",
    "checkmark": "ic_fluent_checkmark_24",
    "dismiss": "ic_fluent_dismiss_24",
    "close": "ic_fluent_dismiss_24",
    "chevron_down": "ic_fluent_chevron_down_20",
    "chevron_down_small": "ic_fluent_chevron_down_16",
    "eye": "ic_fluent_eye_24",
    "eye_off": "ic_fluent_eye_off_24",
    "play": "ic_fluent_play_24",
    "pause": "ic_fluent_pause_24",
    "speaker": "ic_fluent_speaker_2_24",
    "subtract": "ic_fluent_subtract_24",
    "minimize": "ic_fluent_subtract_24",
    "maximize": "ic_fluent_maximize_24",
    "lock": "ic_fluent_lock_closed_24",
    "key": "ic_fluent_key_24",
    "info": "ic_fluent_info_24",
    "warning": "ic_fluent_warning_24",
    "star": "ic_fluent_star_24",
    "heart": "ic_fluent_heart_24",
    "open": "ic_fluent_open_24",
    "link": "ic_fluent_open_24",
    "share": "ic_fluent_share_24",
}


def get_icons_dir() -> Path:
    """Locates the bundled assets/icons directory across development and frozen environments."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "assets" / "icons",
        Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icons",
        Path(sys.executable).resolve().parent / "assets" / "icons",
        Path(sys.executable).resolve().parent / "_internal" / "assets" / "icons",
        Path("assets/icons")
    ]
    for c in candidates:
        if c and c.exists() and c.is_dir():
            return c
    return Path("assets/icons")


def _load_raw_svg(base_filename: str) -> Optional[str]:
    if base_filename in _SVG_RAW_CACHE:
        return _SVG_RAW_CACHE[base_filename]

    icons_dir = get_icons_dir()
    svg_file = icons_dir / f"{base_filename}.svg"
    if not svg_file.exists():
        svg_file = icons_dir / base_filename
        if not svg_file.exists():
            return None

    try:
        content = svg_file.read_text(encoding="utf-8")
        _SVG_RAW_CACHE[base_filename] = content
        return content
    except Exception:
        return None


def get_fluent_pixmap(
    name: str,
    color: str = TEXT_PRIMARY,
    filled: bool = False,
    size: int = 20,
    dpr: float = 1.0
) -> QPixmap:
    """Generates a recolored QPixmap for the requested Fluent icon."""
    key = (name.lower(), color.upper(), size, dpr, filled)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]

    base_name = ICON_NAME_MAP.get(name.lower(), name)
    suffix = "_filled" if filled else "_regular"
    if not (base_name.endswith("_filled") or base_name.endswith("_regular")):
        target_name = f"{base_name}{suffix}"
    else:
        target_name = base_name

    raw_svg = _load_raw_svg(target_name)
    if raw_svg is None and filled:
        # Fall back to regular if filled variant doesn't exist
        raw_svg = _load_raw_svg(f"{base_name}_regular")

    if raw_svg is None:
        # Create empty transparent pixmap fallback
        pix = QPixmap(int(size * dpr), int(size * dpr))
        pix.fill(QColor(0, 0, 0, 0))
        _PIXMAP_CACHE[key] = pix
        return pix

    # Recolor SVG: replace default fills with target color
    recolored_svg = re.sub(r'fill="[^"]+"', f'fill="{color}"', raw_svg)
    if 'fill=' not in recolored_svg:
        recolored_svg = recolored_svg.replace('<path', f'<path fill="{color}"')

    renderer = QSvgRenderer(QByteArray(recolored_svg.encode("utf-8")))
    pixel_size = max(1, int(size * dpr))
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(QColor(0, 0, 0, 0))
    pixmap.setDevicePixelRatio(dpr)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    _PIXMAP_CACHE[key] = pixmap
    return pixmap


def get_fluent_icon(
    name: str,
    color: str = TEXT_PRIMARY,
    filled: bool = False,
    size: int = 20
) -> QIcon:
    """Returns a cached QIcon populated with standard and hover/selected states."""
    key = (name.lower(), color.upper(), size, 1.0, filled)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    icon = QIcon()
    for scale in [1.0, 1.25, 1.5, 2.0]:
        px = get_fluent_pixmap(name, color=color, filled=filled, size=size, dpr=scale)
        icon.addPixmap(px)

    _ICON_CACHE[key] = icon
    return icon


def get_app_icon() -> QIcon:
    """Returns the official Ghostline application icon."""
    candidates = [
        Path("ghostline.ico"),
        Path(__file__).resolve().parent.parent.parent.parent / "ghostline.ico",
        Path(getattr(sys, "_MEIPASS", "")) / "ghostline.ico",
        Path(sys.executable).resolve().parent / "ghostline.ico",
    ]
    for c in candidates:
        if c.exists():
            return QIcon(str(c))
    return get_fluent_icon("sparkle", color=BRAND_TEXT, size=24)

