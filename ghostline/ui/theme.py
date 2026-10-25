"""
Ghostline Design System — Shared visual styling tokens, palette, and Tkinter UI components.
Provides a unified modern dark desktop aesthetic across the Main Application and Floating HUD.
"""

import sys
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Callable, Tuple

# -----------------------------------------------------------------------------
# Color Palette: Deep Charcoal, Slate Borders, Cyan Accent, Emerald / Crimson
# -----------------------------------------------------------------------------
C_BG_APP = "#12141a"           # Deep canvas background
C_BG_SIDEBAR = "#151821"       # Clean navigation sidebar background
C_BG_HEADER = "#151821"        # Header bar & top navigation
C_BG_CARD = "#1b1e28"          # Primary surface card container
C_BG_CARD_HOVER = "#232734"    # Interactive card hover state
C_BG_CARD_ACTIVE = "#2d3242"   # Active / selected card container
C_BG_SURFACE_ALT = "#191c26"   # Subtle alternative container surface
C_BG_CODE = "#0a0d14"          # Deep code block surface
C_BG_INPUT = "#0f121a"         # Input text boxes

# Pill and Chip Tokens
C_BG_PILL = "#252936"          # Contextual keyword chip & toolbar pill background
C_BG_PILL_HOVER = "#2e3344"    # Pill hover
C_BG_PILL_ACTIVE = "#353b4e"   # Active pill capsule button

# Borders
C_BORDER = "#282c3c"           # Subtle slate border
C_BORDER_LIGHT = "#353b4e"     # Refined inner border
C_BORDER_ACCENT = "#0ea5e9"    # Ghostline Sky Cyan accent border
C_BORDER_EMERALD = "#059669"   # Active / running green border
C_BORDER_FOCUS = "#38bdf8"     # Focused interactive border

# Accent Colors
C_CYAN = "#0ea5e9"             # Ghostline Sky Cyan
C_CYAN_LIGHT = "#38bdf8"       # Bright Sky Cyan
C_CYAN_BG = "#0c283d"          # Cyan badge / pill background
C_CYAN_BORDER = "#0284c7"      # Cyan badge border

C_EMERALD = "#10b981"          # Active / validated / success green
C_EMERALD_LIGHT = "#34d399"    # Light emerald
C_EMERALD_BG = "#064e3b"       # Emerald badge background
C_EMERALD_BORDER = "#059669"   # Emerald badge border

C_AMBER = "#f59e0b"            # Thinking / warning / caution amber
C_AMBER_LIGHT = "#fbbf24"      # Light amber
C_AMBER_BG = "#451a03"         # Amber badge background

C_DANGER = "#ef4444"           # Danger / error crimson
C_DANGER_LIGHT = "#f87171"     # Light crimson
C_DANGER_BG = "#450a0a"        # Danger badge background

C_REC = "#ef4444"              # Recording bright red indicator
C_REC_BG = "#3c0d0d"           # Recording badge background

# Brand & Feature Accents matching Reference images
C_GOLD = "#facc15"             # ⭐ Answer Gold Star
C_SPEECH = "#38bdf8"           # 💬 Question Speech Bubble Accent
C_BTN_WHITE = "#ffffff"        # High-contrast action pill button (Subscribe / Set up)
C_BTN_WHITE_TEXT = "#0f1117"   # Text on white action button
C_BTN_WHITE_HOVER = "#e2e8f0"  # Hover state for white button

# Typography Colors
C_TEXT_PRIMARY = "#f8fafc"     # Clean bright white
C_TEXT_SECONDARY = "#94a3b8"   # Slate secondary text
C_TEXT_MUTED = "#64748b"       # Muted metadata & hint text
C_TEXT_DIM = "#475569"         # Subtle dim text

# -----------------------------------------------------------------------------
# Typography Helpers
# -----------------------------------------------------------------------------
def get_font(family: str = "Segoe UI", size: int = 9, weight: str = "normal", slant: str = "roman") -> Tuple[str, int, str]:
    """Returns portable font tuple for Tkinter widgets."""
    return (family, size, weight if weight != "normal" else "roman")

def get_code_font(size: int = 9, weight: str = "normal") -> Tuple[str, int, str]:
    """Returns preferred monospace code font (Cascadia Code / Consolas)."""
    return ("Consolas", size, weight if weight != "normal" else "roman")


# -----------------------------------------------------------------------------
# Modern Canvas-Drawn Toggle Switch (matches Reference 3 "Hide from taskbar")
# -----------------------------------------------------------------------------
class ModernToggleSwitch(tk.Canvas):
    """
    Modern iOS/macOS/Windows style toggle switch rendered smoothly on a Canvas.
    Supports checked/unchecked states, click toggle, and command callback.
    """
    def __init__(
        self,
        parent: tk.Widget,
        checked: bool = False,
        command: Optional[Callable[[bool], None]] = None,
        bg_canvas: str = C_BG_CARD,
        on_color: str = C_EMERALD,
        off_color: str = "#333a4d",
        knob_color: str = "#ffffff",
        width: int = 38,
        height: int = 20
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg_canvas,
            highlightthickness=0,
            cursor="hand2"
        )
        self._checked = bool(checked)
        self._command = command
        self._bg_canvas = bg_canvas
        self._on_color = on_color
        self._off_color = off_color
        self._knob_color = knob_color
        self._sw = width
        self._sh = height

        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self._sw, self._sh
        r = h // 2
        track_color = self._on_color if self._checked else self._off_color
        # Draw pill track
        self.create_arc(0, 0, h, h, start=90, extent=180, fill=track_color, outline=track_color)
        self.create_arc(w - h, 0, w, h, start=270, extent=180, fill=track_color, outline=track_color)
        self.create_rectangle(r, 0, w - r, h, fill=track_color, outline=track_color)
        # Draw circular knob
        kx = (w - r - 2) if self._checked else (r + 2)
        kr = r - 2
        self.create_oval(kx - kr, r - kr, kx + kr, r + kr, fill=self._knob_color, outline=self._knob_color)

    def _on_click(self, event=None):
        self._checked = not self._checked
        self._draw()
        if self._command:
            self._command(self._checked)

    def set_state(self, checked: bool):
        self._checked = bool(checked)
        self._draw()

    def get_state(self) -> bool:
        return self._checked


# -----------------------------------------------------------------------------
# Reusable UI Styling Functions
# -----------------------------------------------------------------------------
def make_pill_badge(
    parent: tk.Widget,
    text: str,
    bg: str = C_CYAN_BG,
    fg: str = C_CYAN_LIGHT,
    border_color: str = C_CYAN_BORDER,
    font_size: int = 8,
    padx: int = 7,
    pady: int = 2
) -> tk.Frame:
    """Creates a pill-shaped container badge for labels, statuses, and tags."""
    pill = tk.Frame(
        parent,
        bg=bg,
        bd=1,
        highlightbackground=border_color,
        highlightthickness=1,
        padx=padx,
        pady=pady
    )
    lbl = tk.Label(
        pill,
        text=text,
        font=("Segoe UI", font_size, "bold"),
        fg=fg,
        bg=bg
    )
    lbl.pack()
    pill.label = lbl
    return pill


def style_button(
    btn: tk.Label,
    bg: str = C_BG_CARD,
    fg: str = C_TEXT_PRIMARY,
    hover_bg: str = C_BG_CARD_HOVER,
    hover_fg: str = C_CYAN_LIGHT,
    active_bg: Optional[str] = None
):
    """Applies smooth hover effects to label-based buttons."""
    btn.config(bg=bg, fg=fg, cursor="hand2")

    def _on_enter(e):
        btn.config(bg=hover_bg, fg=hover_fg)

    def _on_leave(e):
        btn.config(bg=bg, fg=fg)

    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)
