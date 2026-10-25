"""
Ghostline Floating HUD Overlay — Premium, Translucent, Always-On-Top Assistant.
Features:
- Stealth dark acrylic aesthetic with refined charcoal surfaces and cyan/emerald accents
- Compact top toolbar with capture status, mode selectors (Answer / Audio), Screenshot (Alt+/),
  Pin, Minimize, and Close controls
- Slim contextual prompt row showing recent question with Clear action
- Main answer surface with Question Type Badge, Answer Pill, selectable explanation,
  syntax-highlighted code block with horizontal scrolling, and non-obstructive Copy controls
- Uncertainty and error recovery card displaying captured raw OCR text with Retry action
- Integrated Live Audio HUD mode with microphone and system audio distinction, active REC pulse,
  live timestamped transcript, and independent scrollable AI response panel
- Compact bottom input bar to manually ask Ghostline questions anytime
- Focus-free window (WS_EX_NOACTIVATE) and screen capture exclusion (WDA_EXCLUDEFROMCAPTURE)
"""

import os
import sys
import ctypes
import logging
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Callable, Tuple, Dict, Any, List

from ghostline.ui.code_renderer import extract_code_and_prose, apply_syntax_highlighting
from ghostline.core.capture_exclusion import set_capture_exclusion, get_capture_exclusion_status
from ghostline.ui.presentation import (
    PresentedAnswer,
    build_answer_presentation,
    TYPE_MCQ,
    TYPE_CODE,
    TYPE_THEORY,
    TYPE_TRUE_FALSE,
    TYPE_NUMERICAL,
    TYPE_FILL_BLANK,
    TYPE_GENERIC,
    TYPE_UNCERTAIN,
    TYPE_ERROR
)
from ghostline.ui.theme import (
    C_BG_APP,
    C_BG_HEADER,
    C_BG_CARD,
    C_BG_CARD_HOVER,
    C_BG_SURFACE_ALT,
    C_BG_CODE,
    C_BG_INPUT,
    C_BORDER,
    C_BORDER_LIGHT,
    C_BORDER_ACCENT,
    C_BORDER_EMERALD,
    C_CYAN,
    C_CYAN_LIGHT,
    C_CYAN_BG,
    C_CYAN_BORDER,
    C_EMERALD,
    C_EMERALD_LIGHT,
    C_EMERALD_BG,
    C_EMERALD_BORDER,
    C_AMBER,
    C_AMBER_LIGHT,
    C_AMBER_BG,
    C_DANGER,
    C_DANGER_LIGHT,
    C_DANGER_BG,
    C_REC,
    C_REC_BG,
    C_TEXT_PRIMARY,
    C_TEXT_SECONDARY,
    C_TEXT_MUTED,
    C_TEXT_DIM,
    C_GOLD,
    C_SPEECH
)

# Aliases for backward compatibility with existing tests
C_BG_BASE = C_BG_APP
C_BORDER_MUTED = C_BORDER
C_TEXT_EXPLAIN = "#cbd5e1"
C_EMERALD_TEXT = C_EMERALD_LIGHT


class GhostlineHudOverlay:
    """
    Compact, translucent, floating AI HUD overlay for Windows.
    Designed for seamless screen assistance, coding co-pilot, and live audio assistance.
    """

    def __init__(
        self,
        on_close: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], bool]] = None,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
        on_retry: Optional[Callable[[], None]] = None,
        opacity: float = 0.94,
        width: int = 440,
        height: int = 380,
        max_width: int = 600,
        max_height: int = 540,
        scroll_speed: int = 2,
        pos_x: Optional[int] = None,
        pos_y: Optional[int] = None,
        is_pinned: bool = False,
        always_on_top: bool = True,
        exclude_from_capture: bool = True,
        is_paused: bool = False,
        on_toggle_audio: Optional[Callable[[], None]] = None,
        on_ask_custom: Optional[Callable[[str], None]] = None,
        on_trigger_screenshot: Optional[Callable[[], None]] = None,
    ):
        self.root: Optional[tk.Tk] = None
        self.hwnd: Optional[int] = None
        self.on_close = on_close
        self.on_toggle_pause = on_toggle_pause
        self.on_position_changed = on_position_changed
        self.on_retry = on_retry
        self.on_toggle_audio = on_toggle_audio
        self.on_ask_custom = on_ask_custom
        self.on_trigger_screenshot = on_trigger_screenshot

        self.opacity = max(0.4, min(1.0, opacity))
        self.width = max(340, min(width, max_width))
        self.height = max(240, min(height, max_height))
        self.max_width = max_width
        self.max_height = max_height
        self.scroll_speed = max(1, scroll_speed)
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.is_pinned = is_pinned
        self.always_on_top = always_on_top
        self.exclude_from_capture = exclude_from_capture
        self.is_paused = is_paused

        self.is_visible = False
        self.is_minimized = False
        self.timeout_sec = 0.0
        self._dismiss_timer = None
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Active HUD mode: 'answer' | 'audio'
        self.active_mode = "answer"

        # Spinner animation state
        self._spinner_running = False
        self._spinner_angle = 0
        self._spinner_after_id = None

        # Solve tracking
        self._current_solve_id: int = 0
        self.current_presentation: Optional[PresentedAnswer] = None
        self.is_code_collapsed: bool = False

        # State cache
        self.phase = "ready"  # ready | capturing | recognizing | thinking | answer | error
        self.question_text = ""
        self.answer_text = ""
        self.answer_badge = ""
        self.raw_explanation = ""
        self.current_code = ""
        self.current_lang = ""

        # Audio HUD state cache
        self.is_audio_capturing = False
        self.is_audio_paused = False

    def launch(self, parent: Optional[tk.Tk] = None, start_visible: bool = False):
        """Initializes HUD window as Toplevel child or standalone Tk instance."""
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Ghostline Floating HUD")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.always_on_top)
        self.root.attributes("-alpha", self.opacity)

        # Positioning within display bounds
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if self.pos_x is None or self.pos_y is None:
            self.pos_x = max(20, sw - self.width - 35)
            self.pos_y = max(40, sh - self.height - 80)
        else:
            self.pos_x = max(0, min(self.pos_x, sw - self.width))
            self.pos_y = max(0, min(self.pos_y, sh - self.height))

        self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
        self.root.configure(bg=C_BG_APP)

        # Fonts
        self.title_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.body_font = tkfont.Font(family="Segoe UI", size=9)
        self.badge_font = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        self.kbd_font = tkfont.Font(family="Segoe UI", size=8)
        self.small_font = tkfont.Font(family="Segoe UI", size=8)
        self.code_font = tkfont.Font(family="Consolas", size=9)

        # Build UI
        self._build_ui()

        # Keyboard Navigation
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Up>", lambda e: self._on_key_scroll(-1))
        self.root.bind("<Down>", lambda e: self._on_key_scroll(1))
        self.root.bind("<Prior>", lambda e: self._on_key_page_scroll(-1))
        self.root.bind("<Next>", lambda e: self._on_key_page_scroll(1))
        self.root.bind("<Home>", lambda e: self.canvas.yview_moveto(0.0) if self.canvas else None)
        self.root.bind("<End>", lambda e: self.canvas.yview_moveto(1.0) if self.canvas else None)

        # Mouse Wheel bindings
        self.root.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.root.bind("<Leave>", lambda e: self._unbind_mousewheel())

        # Win32 extended styles (WS_EX_NOACTIVATE & Capture Exclusion)
        self.root.update_idletasks()
        self._apply_win32_attributes()

        if start_visible:
            self.show()
        else:
            self.is_visible = False
            self.root.withdraw()

        if not parent:
            self.root.mainloop()

    def _apply_win32_attributes(self):
        """Applies WS_EX_NOACTIVATE (focus-free) and SetWindowDisplayAffinity."""
        if sys.platform != "win32" or not self.root:
            return
        try:
            try:
                frame_id = self.root.frame()
                self.hwnd = int(frame_id, 16) if frame_id.startswith("0x") else int(frame_id)
            except Exception:
                self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()

            if self.hwnd:
                GWL_EXSTYLE = -20
                WS_EX_NOACTIVATE = 0x08000000
                WS_EX_TOPMOST = 0x00000008
                WS_EX_TOOLWINDOW = 0x00000080

                current_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
                new_style = current_style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
                ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)

                # Set display affinity for invisible screen capture
                if self.exclude_from_capture:
                    set_capture_exclusion(self.hwnd, True)
        except Exception as e:
            logging.debug("[HUD] Win32 attribute configuration note: %s", e)

    # -------------------------------------------------------------------------
    # Layout Builder
    # -------------------------------------------------------------------------
    def _build_ui(self):
        # Outer border wrapper for high-precision 1px sleek dark border
        self.border_frame = tk.Frame(self.root, bg=C_BORDER, bd=1)
        self.border_frame.pack(fill=tk.BOTH, expand=True)

        self.main_container = tk.Frame(self.border_frame, bg=C_BG_APP)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ---------------------------------------------------------------------
        # Island 1: Floating Action Pill Bar (Reference 2 Top Bar)
        # ---------------------------------------------------------------------
        self.header = tk.Frame(self.main_container, bg="#1a1d27", bd=1, highlightbackground="#2e3345", highlightthickness=1, height=38)
        self.header.pack(fill=tk.X, side=tk.TOP, pady=(0, 6))
        self.header.pack_propagate(False)

        # Dragging on header
        self.header.bind("<ButtonPress-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._on_drag)

        # Status Canvas (Eyes & animated inference spinner)
        self.status_canvas = tk.Canvas(self.header, width=20, height=16, bg="#1a1d27", highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(8, 4), pady=11)
        self.status_canvas.bind("<ButtonPress-1>", self._start_drag)
        self.status_canvas.bind("<B1-Motion>", self._on_drag)
        self._draw_eyes(C_EMERALD)

        # Status Label (Tested directly by test_hud_state_transitions)
        self.status_label = tk.Label(
            self.header,
            text="Ready",
            font=self.title_font,
            fg=C_TEXT_PRIMARY,
            bg="#1a1d27"
        )
        self.status_label.pack(side=tk.LEFT, pady=9)
        self.status_label.bind("<ButtonPress-1>", self._start_drag)
        self.status_label.bind("<B1-Motion>", self._on_drag)

        # Live Audio REC Indicator Pill
        self.lbl_hud_rec = tk.Label(
            self.header,
            text="● REC",
            font=("Segoe UI", 7, "bold"),
            fg=C_REC,
            bg=C_REC_BG,
            padx=5,
            pady=1
        )
        # Initially hidden until audio capture is active

        # Capture & Mic Indicators with red dots (Reference 2)
        self.lbl_icon_screen = tk.Label(
            self.header,
            text="💻🔴",
            font=("Segoe UI", 7),
            fg="#94a3b8",
            bg="#1a1d27"
        )
        self.lbl_icon_screen.pack(side=tk.LEFT, padx=(6, 2))

        self.lbl_icon_mic = tk.Label(
            self.header,
            text="🎙️🔴",
            font=("Segoe UI", 7),
            fg="#94a3b8",
            bg="#1a1d27"
        )
        self.lbl_icon_mic.pack(side=tk.LEFT, padx=(0, 6))

        # Action Capsule Buttons: Answer | Screenshot | Chat (Reference 2)
        self.mode_frame = tk.Frame(self.header, bg="#1a1d27")
        self.mode_frame.pack(side=tk.LEFT, padx=(2, 0))

        self.tab_answer = tk.Label(
            self.mode_frame,
            text="Answer  Alt+/",
            font=("Segoe UI", 8, "bold"),
            fg=C_TEXT_PRIMARY,
            bg="#272c3d",
            cursor="hand2",
            padx=7,
            pady=2,
            bd=1,
            highlightbackground=C_CYAN_BORDER,
            highlightthickness=1
        )
        self.tab_answer.pack(side=tk.LEFT, padx=2)
        self.tab_answer.bind("<Button-1>", lambda e: self.switch_mode("answer"))

        self.btn_screenshot = tk.Label(
            self.mode_frame,
            text="Screenshot  Alt+S",
            font=("Segoe UI", 8),
            fg=C_TEXT_SECONDARY,
            bg="#202433",
            cursor="hand2",
            padx=7,
            pady=2
        )
        self.btn_screenshot.pack(side=tk.LEFT, padx=2)
        self.btn_screenshot.bind("<Button-1>", lambda e: self._on_click_solve())

        self.btn_chat = tk.Label(
            self.mode_frame,
            text="Chat  Alt+C",
            font=("Segoe UI", 8),
            fg=C_TEXT_SECONDARY,
            bg="#202433",
            cursor="hand2",
            padx=7,
            pady=2
        )
        self.btn_chat.pack(side=tk.LEFT, padx=2)
        self.btn_chat.bind("<Button-1>", lambda e: self._focus_query_input())

        self.tab_audio = tk.Label(
            self.mode_frame,
            text="Audio",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            cursor="hand2",
            padx=6,
            pady=2
        )
        self.tab_audio.pack(side=tk.LEFT, padx=2)
        self.tab_audio.bind("<Button-1>", lambda e: self.switch_mode("audio"))

        # Right-aligned Toolbar Controls (Reference 2)
        # End Button (Red pill button)
        self.btn_close = tk.Label(
            self.header,
            text="End",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff",
            bg="#ef4444",
            cursor="hand2",
            padx=9,
            pady=2
        )
        self.btn_close.pack(side=tk.RIGHT, padx=(0, 6))
        self.btn_close.bind("<Button-1>", lambda e: self.hide())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.config(bg="#dc2626"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.config(bg="#ef4444"))

        # More Options / Pin Button
        self.btn_pin = tk.Label(
            self.header,
            text="⋮",
            font=("Segoe UI", 10, "bold"),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            cursor="hand2",
            padx=4
        )
        self.btn_pin.pack(side=tk.RIGHT, padx=2)
        self.btn_pin.bind("<Button-1>", lambda e: self.toggle_pin())

        # Minimize / Expand Button (Tested by test_hud_scrollable_viewport_and_controls)
        self.btn_min = tk.Label(
            self.header,
            text="—",
            font=("Segoe UI", 10, "bold"),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            cursor="hand2",
            padx=4
        )
        self.btn_min.pack(side=tk.RIGHT, padx=2)
        self.btn_min.bind("<Button-1>", lambda e: self.toggle_minimize())
        self.btn_min.bind("<Enter>", lambda e: self.btn_min.config(fg=C_TEXT_PRIMARY))
        self.btn_min.bind("<Leave>", lambda e: self.btn_min.config(fg=C_TEXT_MUTED))

        # Reposition 4-way arrow icon
        self.btn_drag = tk.Label(
            self.header,
            text="✥",
            font=("Segoe UI", 10),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            cursor="fleur",
            padx=4
        )
        self.btn_drag.pack(side=tk.RIGHT, padx=2)
        self.btn_drag.bind("<ButtonPress-1>", self._start_drag)
        self.btn_drag.bind("<B1-Motion>", self._on_drag)

        # Pause / Resume Hover Button (Tested)
        self.btn_pause = tk.Label(
            self.header,
            text="⏸" if not self.is_paused else "▶",
            font=("Segoe UI", 8, "bold"),
            fg=C_EMERALD if not self.is_paused else C_AMBER,
            bg="#1a1d27",
            cursor="hand2",
            padx=4
        )
        self.btn_pause.pack(side=tk.RIGHT, padx=2)
        self.btn_pause.bind("<Button-1>", lambda e: self.toggle_pause())

        # Audio Toggle / Status Button (Tested by test_hud_audio_status_updates)
        self.btn_audio = tk.Label(
            self.header,
            text="🎙️",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            cursor="hand2",
            padx=4
        )
        self.btn_audio.pack(side=tk.RIGHT, padx=2)
        self.btn_audio.bind("<Button-1>", lambda e: self._on_toggle_audio())

        # ---------------------------------------------------------------------
        # Island 2: Contextual Prompt & Keyword Chip Bar (Reference 2 Middle Bar)
        # ---------------------------------------------------------------------
        self.prompt_bar = tk.Frame(self.main_container, bg="#1a1d27", bd=1, highlightbackground="#2e3345", highlightthickness=1, height=34)
        self.prompt_bar.pack(fill=tk.X, side=tk.TOP, pady=(0, 6))
        self.prompt_bar.pack_propagate(False)

        # Waveform Canvas (Audio Visualizer Green Bars)
        self.waveform_canvas = tk.Canvas(self.prompt_bar, width=22, height=16, bg="#1a1d27", highlightthickness=0)
        self.waveform_canvas.pack(side=tk.LEFT, padx=(8, 4), pady=9)
        self._draw_waveform()

        # Keyword Chips Container
        self.chips_container = tk.Frame(self.prompt_bar, bg="#1a1d27")
        self.chips_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4))

        self.lbl_prompt_text = tk.Label(
            self.chips_container,
            text="Press [Alt+/] to capture or enter question below",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            anchor="w"
        )
        self.lbl_prompt_text.pack(side=tk.LEFT)

        self.btn_expand_prompt = tk.Label(
            self.prompt_bar,
            text="⤢",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1a1d27",
            cursor="hand2",
            padx=4
        )
        self.btn_expand_prompt.pack(side=tk.RIGHT, padx=2)

        self.btn_clear_prompt = tk.Label(
            self.prompt_bar,
            text="Clear  Alt+X",
            font=("Segoe UI", 7, "bold"),
            fg=C_TEXT_MUTED,
            bg="#252936",
            cursor="hand2",
            padx=7,
            pady=2,
            bd=1,
            highlightbackground="#353b4e",
            highlightthickness=1
        )
        self.btn_clear_prompt.pack(side=tk.RIGHT, padx=4)
        self.btn_clear_prompt.bind("<Button-1>", lambda e: self.clear_content())
        self.btn_clear_prompt.bind("<Enter>", lambda e: self.btn_clear_prompt.config(fg=C_TEXT_PRIMARY, bg="#2e3444"))
        self.btn_clear_prompt.bind("<Leave>", lambda e: self.btn_clear_prompt.config(fg=C_TEXT_MUTED, bg="#252936"))

        # ---------------------------------------------------------------------
        # Island 3: Main Assistant Surface Card (Reference 2 Core Panel)
        # ---------------------------------------------------------------------
        self.island_card = tk.Frame(self.main_container, bg="#161822", bd=1, highlightbackground="#2a2f3f", highlightthickness=1)
        self.island_card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # Card Top Navigation Bar (History ← → and Clear)
        self.card_top_nav = tk.Frame(self.island_card, bg="#161822", height=24)
        self.card_top_nav.pack(fill=tk.X, side=tk.TOP, padx=6, pady=(4, 2))
        self.card_top_nav.pack_propagate(False)

        self.btn_nav_prev = tk.Label(
            self.card_top_nav,
            text="←",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1e2230",
            cursor="hand2",
            padx=6,
            pady=1,
            bd=1,
            highlightbackground="#2c3244",
            highlightthickness=1
        )
        self.btn_nav_prev.pack(side=tk.LEFT, padx=(2, 2))

        self.btn_nav_next = tk.Label(
            self.card_top_nav,
            text="→",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1e2230",
            cursor="hand2",
            padx=6,
            pady=1,
            bd=1,
            highlightbackground="#2c3244",
            highlightthickness=1
        )
        self.btn_nav_next.pack(side=tk.LEFT, padx=(2, 6))

        self.btn_card_expand = tk.Label(
            self.card_top_nav,
            text="⤢",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#161822",
            cursor="hand2",
            padx=4
        )
        self.btn_card_expand.pack(side=tk.RIGHT, padx=2)

        self.btn_card_clear = tk.Label(
            self.card_top_nav,
            text="Clear",
            font=("Segoe UI", 7, "bold"),
            fg=C_TEXT_MUTED,
            bg="#1e2230",
            cursor="hand2",
            padx=6,
            pady=1,
            bd=1,
            highlightbackground="#2c3244",
            highlightthickness=1
        )
        self.btn_card_clear.pack(side=tk.RIGHT, padx=4)
        self.btn_card_clear.bind("<Button-1>", lambda e: self.clear_content())

        # Question Row (Reference 2 Speech Bubble + Question)
        self.question_container = tk.Frame(self.island_card, bg="#161822")
        self.question_container.pack(fill=tk.X, padx=8, pady=(2, 4))

        q_head_row = tk.Frame(self.question_container, bg="#161822")
        q_head_row.pack(fill=tk.X)

        self.lbl_q_icon = tk.Label(
            q_head_row,
            text="💬 Question:",
            font=("Segoe UI", 9, "bold"),
            fg=C_TEXT_PRIMARY,
            bg="#161822"
        )
        self.lbl_q_icon.pack(side=tk.LEFT, padx=(2, 6))

        self.lbl_question_type_badge = tk.Label(
            q_head_row,
            text="",
            font=("Segoe UI", 7, "bold"),
            fg=C_CYAN_LIGHT,
            bg=C_CYAN_BG
        )
        self.lbl_question_type_badge.pack(side=tk.LEFT)

        self.btn_copy_q = tk.Label(
            q_head_row,
            text="⧉",
            font=("Segoe UI", 9),
            fg=C_TEXT_MUTED,
            bg="#161822",
            cursor="hand2"
        )
        self.btn_copy_q.pack(side=tk.RIGHT, padx=4)
        self.btn_copy_q.bind("<Button-1>", lambda e: self._copy_question_to_clipboard())

        self.lbl_question_body = tk.Label(
            self.question_container,
            text="No question detected yet. Press [Alt+/] to solve.",
            font=self.body_font,
            fg=C_TEXT_PRIMARY,
            bg="#161822",
            justify=tk.LEFT,
            wraplength=410,
            anchor="w"
        )
        self.lbl_question_body.pack(fill=tk.X, padx=(2, 4), pady=(2, 4))

        # Answer Row (Reference 2 Gold Star + Answer)
        self.answer_head_container = tk.Frame(self.island_card, bg="#161822")
        self.answer_head_container.pack(fill=tk.X, padx=8, pady=(2, 4))

        ans_title_row = tk.Frame(self.answer_head_container, bg="#161822")
        ans_title_row.pack(fill=tk.X)

        self.lbl_star_icon = tk.Label(
            ans_title_row,
            text="⭐ Answer:",
            font=("Segoe UI", 9, "bold"),
            fg=C_GOLD,
            bg="#161822"
        )
        self.lbl_star_icon.pack(side=tk.LEFT, padx=(2, 6))

        self.badge_box = tk.Frame(
            ans_title_row,
            bg=C_EMERALD_BG,
            padx=6,
            pady=1,
            bd=1,
            highlightbackground=C_EMERALD,
            highlightthickness=1
        )
        self.badge_label = tk.Label(
            self.badge_box,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg=C_EMERALD_LIGHT,
            bg=C_EMERALD_BG
        )
        self.badge_label.pack()

        self.ans_summary_label = tk.Label(
            ans_title_row,
            text="Hover over question and press [Alt+/]",
            font=("Segoe UI", 9, "bold"),
            fg=C_CYAN_LIGHT,
            bg="#161822",
            justify=tk.LEFT,
            wraplength=340,
            anchor="w"
        )
        self.ans_summary_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # ---------------------------------------------------------------------
        # Viewport Containers: Switchable (Answer View vs Live Audio View)
        # ---------------------------------------------------------------------
        self.viewport_container = tk.Frame(self.island_card, bg="#161822")
        self.viewport_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # 4A. Dedicated Answer View (Scrollable Canvas + Content Frame)
        self.answer_view_frame = tk.Frame(self.viewport_container, bg="#161822")
        self.answer_view_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.answer_view_frame,
            bg="#161822",
            highlightthickness=0,
            bd=0
        )
        self.v_scrollbar = tk.Scrollbar(
            self.answer_view_frame,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
            width=6
        )
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.scrollable_content = tk.Frame(self.canvas, bg="#161822")
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_content,
            anchor="nw"
        )

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_content.bind("<Configure>", self._on_content_configure)

        # Selectable Explanation Text Widget (Structured Bullet Points & Paragraphs)
        self.explanation_frame = tk.Frame(self.scrollable_content, bg="#161822")
        self.explanation_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        self.explanation_text = tk.Text(
            self.explanation_frame,
            font=self.body_font,
            fg="#e2e8f0",
            bg="#161822",
            bd=0,
            highlightthickness=0,
            wrap=tk.WORD,
            exportselection=False,
            height=4,
            padx=2,
            pady=2,
            cursor="arrow"
        )
        self.explanation_text.pack(fill=tk.BOTH, expand=True)
        self.explanation_text.config(state=tk.DISABLED)

        # Code Container (Tested)
        self.code_container = tk.Frame(
            self.scrollable_content,
            bg=C_BG_CODE,
            bd=1,
            highlightbackground="#2c3242",
            highlightthickness=1
        )

        code_top = tk.Frame(self.code_container, bg="#11141c", height=24)
        code_top.pack(fill=tk.X, side=tk.TOP)
        self.code_lang_label = tk.Label(
            code_top,
            text="CODE",
            font=("Segoe UI", 7, "bold"),
            fg=C_CYAN_LIGHT,
            bg="#11141c"
        )
        self.code_lang_label.pack(side=tk.LEFT, padx=8)

        self.btn_toggle_code = tk.Label(
            code_top,
            text="[-] Collapse",
            font=("Segoe UI", 7),
            fg=C_TEXT_MUTED,
            bg="#11141c",
            cursor="hand2",
            padx=6
        )
        self.btn_toggle_code.pack(side=tk.RIGHT)
        self.btn_toggle_code.bind("<Button-1>", lambda e: self.toggle_code_collapse())

        self.code_text_frame = tk.Frame(self.code_container, bg=C_BG_CODE)
        self.code_text_frame.pack(fill=tk.BOTH, expand=True)

        self.code_scroll_x = tk.Scrollbar(self.code_container, orient=tk.HORIZONTAL)
        self.code_scroll_y = tk.Scrollbar(self.code_text_frame, orient=tk.VERTICAL)

        self.code_text = tk.Text(
            self.code_text_frame,
            font=self.code_font,
            bg=C_BG_CODE,
            fg=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=0,
            wrap=tk.NONE,
            height=4,
            padx=8,
            pady=4,
            xscrollcommand=self.code_scroll_x.set,
            yscrollcommand=self.code_scroll_y.set
        )
        self.code_scroll_x.config(command=self.code_text.xview)
        self.code_scroll_y.config(command=self.code_text.yview)
        self.code_text.bind("<MouseWheel>", lambda e: self.code_text.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self.code_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.code_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.code_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Uncertainty / Error Recovery Box
        self.recovery_frame = tk.Frame(self.scrollable_content, bg="#1a1313", bd=1, highlightbackground=C_DANGER, highlightthickness=1)

        # Card Footer Row (Reference 2: Answer · 19:01, 👍, 👎, Copy Answer, Retry)
        self.footer = tk.Frame(self.island_card, bg="#161822")
        self.footer.pack(fill=tk.X, side=tk.BOTTOM, padx=6, pady=(2, 4))

        self.footer_actions = tk.Frame(self.footer, bg="#161822", height=26)
        self.footer_actions.pack(fill=tk.X, side=tk.TOP)
        self.footer_actions.pack_propagate(False)

        self.lbl_card_meta = tk.Label(
            self.footer_actions,
            text="Answer · 19:01",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#161822"
        )
        self.lbl_card_meta.pack(side=tk.LEFT, padx=(4, 6))

        self.btn_thumb_up = tk.Label(
            self.footer_actions,
            text="👍",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#161822",
            cursor="hand2",
            padx=3
        )
        self.btn_thumb_up.pack(side=tk.LEFT)

        self.btn_thumb_down = tk.Label(
            self.footer_actions,
            text="👎",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#161822",
            cursor="hand2",
            padx=3
        )
        self.btn_thumb_down.pack(side=tk.LEFT, padx=(0, 6))

        # Copy Answer Button (Tested)
        self.btn_copy_ans = tk.Label(
            self.footer_actions,
            text="📋 Copy Answer",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg="#1e2230",
            cursor="hand2",
            padx=8,
            pady=2,
            bd=1,
            highlightbackground="#2c3244",
            highlightthickness=1
        )
        self.btn_copy_ans.pack(side=tk.LEFT, padx=(2, 4))
        self.btn_copy_ans.bind("<Button-1>", lambda e: self.copy_answer_to_clipboard())

        # Copy Code Button (Tested)
        self.btn_copy_code = tk.Label(
            self.footer_actions,
            text="💻 Copy Code",
            font=self.kbd_font,
            fg=C_EMERALD_LIGHT,
            bg="#1e2230",
            cursor="hand2",
            padx=8,
            pady=2,
            bd=1,
            highlightbackground="#2c3244",
            highlightthickness=1
        )
        self.btn_copy_code.bind("<Button-1>", lambda e: self.copy_code_to_clipboard())

        # Retry Button (Tested)
        self.btn_retry = tk.Label(
            self.footer_actions,
            text="🔄 Retry",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg="#1e2230",
            cursor="hand2",
            padx=8,
            pady=2,
            bd=1,
            highlightbackground="#2c3244",
            highlightthickness=1
        )
        self.btn_retry.pack(side=tk.LEFT, padx=(2, 4))
        self.btn_retry.bind("<Button-1>", lambda e: self.retry_solve())

        self.footer_hint = tk.Label(
            self.footer_actions,
            text="[Alt+/] Solve",
            font=self.kbd_font,
            fg=C_TEXT_MUTED,
            bg="#161822"
        )
        self.footer_hint.pack(side=tk.RIGHT, padx=6)

        # ---------------------------------------------------------------------
        # Island 4: Manual Question Input Bar (Reference 2 Bottom Input)
        # ---------------------------------------------------------------------
        self.query_row = tk.Frame(self.main_container, bg="#1a1d27", bd=1, highlightbackground="#2e3345", highlightthickness=1, height=34)
        self.query_row.pack(fill=tk.X, side=tk.BOTTOM)
        self.query_row.pack_propagate(False)

        self.entry_manual_query = tk.Entry(
            self.query_row,
            font=("Segoe UI", 9),
            bg="#12141a",
            fg=C_TEXT_PRIMARY,
            insertbackground=C_CYAN_LIGHT,
            bd=0,
            highlightthickness=1,
            highlightbackground="#2c3242",
            highlightcolor=C_BORDER_ACCENT
        )
        self.entry_manual_query.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 4), pady=4)
        self.entry_manual_query.insert(0, "Ask Ghostline a question...")
        self.entry_manual_query.bind("<FocusIn>", self._on_query_focus_in)
        self.entry_manual_query.bind("<FocusOut>", self._on_query_focus_out)
        self.entry_manual_query.bind("<Return>", lambda e: self._on_submit_manual_query())

        self.btn_ask_manual = tk.Label(
            self.query_row,
            text="Ask",
            font=("Segoe UI", 8, "bold"),
            fg=C_CYAN_LIGHT,
            bg=C_CYAN_BG,
            cursor="hand2",
            padx=10,
            pady=2,
            bd=1,
            highlightbackground=C_CYAN_BORDER,
            highlightthickness=1
        )
        self.btn_ask_manual.pack(side=tk.RIGHT, padx=(0, 6), pady=4)
        self.btn_ask_manual.bind("<Button-1>", lambda e: self._on_submit_manual_query())

        # 4B. Live Audio Assistance View (Initially hidden, switchable)
        self.audio_view_frame = tk.Frame(self.viewport_container, bg="#161822")

        # Audio View Controls Header
        self.audio_ctrl_bar = tk.Frame(self.audio_view_frame, bg=C_BG_CARD, height=30)
        self.audio_ctrl_bar.pack(fill=tk.X, side=tk.TOP, padx=4, pady=(2, 4))
        self.audio_ctrl_bar.pack_propagate(False)

        self.btn_audio_start_stop = tk.Label(
            self.audio_ctrl_bar,
            text="▶ Start Listening",
            font=("Segoe UI", 8, "bold"),
            fg=C_EMERALD_LIGHT,
            bg=C_EMERALD_BG,
            cursor="hand2",
            padx=8,
            pady=2,
            bd=1,
            highlightbackground=C_EMERALD_BORDER,
            highlightthickness=1
        )
        self.btn_audio_start_stop.pack(side=tk.LEFT, padx=4, pady=3)
        self.btn_audio_start_stop.bind("<Button-1>", lambda e: self._on_toggle_audio())

        self.lbl_mic_badge = tk.Label(
            self.audio_ctrl_bar,
            text="Microphone",
            font=("Segoe UI", 7, "bold"),
            fg=C_CYAN_LIGHT,
            bg=C_CYAN_BG,
            padx=6,
            pady=1
        )
        self.lbl_mic_badge.pack(side=tk.LEFT, padx=2)

        self.lbl_sys_badge = tk.Label(
            self.audio_ctrl_bar,
            text="System Audio",
            font=("Segoe UI", 7, "bold"),
            fg="#a5b4fc",
            bg="#1e1b4b",
            padx=6,
            pady=1
        )
        self.lbl_sys_badge.pack(side=tk.LEFT, padx=2)

        self.btn_clear_audio = tk.Label(
            self.audio_ctrl_bar,
            text="Clear",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=6,
            pady=2
        )
        self.btn_clear_audio.pack(side=tk.RIGHT, padx=4, pady=3)
        self.btn_clear_audio.bind("<Button-1>", lambda e: self.clear_audio_transcript())

        # Dual panels: Transcript (top) and AI Response (bottom)
        self.audio_paned = tk.PanedWindow(self.audio_view_frame, orient=tk.VERTICAL, bg=C_BORDER, sashwidth=4, bd=0)
        self.audio_paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))

        # Transcript pane
        self.transcript_pane = tk.Frame(self.audio_paned, bg=C_BG_APP)
        t_header = tk.Frame(self.transcript_pane, bg="#0d1421", height=20)
        t_header.pack(fill=tk.X, side=tk.TOP)
        t_header.pack_propagate(False)
        tk.Label(t_header, text="LIVE TRANSCRIPT", font=("Segoe UI", 7, "bold"), fg=C_TEXT_MUTED, bg="#0d1421").pack(side=tk.LEFT, padx=6)

        t_scroll = tk.Scrollbar(self.transcript_pane, orient=tk.VERTICAL)
        self.txt_hud_transcript = tk.Text(
            self.transcript_pane,
            font=("Segoe UI", 9),
            bg=C_BG_APP,
            fg=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=t_scroll.set
        )
        t_scroll.config(command=self.txt_hud_transcript.yview)
        self.txt_hud_transcript.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        t_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_hud_transcript.tag_configure("source_call", foreground="#38bdf8", font=("Segoe UI", 9, "bold"))
        self.txt_hud_transcript.tag_configure("source_mic", foreground="#34d399", font=("Segoe UI", 9, "bold"))
        self.txt_hud_transcript.tag_configure("timestamp", foreground="#64748b", font=("Segoe UI", 8))
        self.txt_hud_transcript.tag_configure("partial", foreground="#94a3b8")
        self.txt_hud_transcript.tag_configure("final", foreground="#f8fafc")

        # AI Copilot Response pane
        self.ai_audio_pane = tk.Frame(self.audio_paned, bg=C_BG_CARD)
        ai_head = tk.Frame(self.ai_audio_pane, bg="#0d1421", height=20)
        ai_head.pack(fill=tk.X, side=tk.TOP)
        ai_head.pack_propagate(False)
        tk.Label(ai_head, text="AI COPILOT INSIGHTS", font=("Segoe UI", 7, "bold"), fg=C_EMERALD_LIGHT, bg="#0d1421").pack(side=tk.LEFT, padx=6)

        ai_scroll = tk.Scrollbar(self.ai_audio_pane, orient=tk.VERTICAL)
        self.txt_hud_ai = tk.Text(
            self.ai_audio_pane,
            font=("Segoe UI", 9),
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=ai_scroll.set
        )
        ai_scroll.config(command=self.txt_hud_ai.yview)
        self.txt_hud_ai.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ai_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.audio_paned.add(self.transcript_pane, minsize=80)
        self.audio_paned.add(self.ai_audio_pane, minsize=80)

    # -------------------------------------------------------------------------
    # Mode Switching: Answer vs Audio
    # -------------------------------------------------------------------------
    def switch_mode(self, mode: str):
        self.active_mode = mode
        if mode == "answer":
            self.tab_answer.config(fg=C_CYAN_LIGHT, bg=C_CYAN_BG, bd=1, highlightbackground=C_CYAN_BORDER, highlightthickness=1)
            self.tab_audio.config(fg=C_TEXT_MUTED, bg=C_BG_CARD, highlightthickness=0)
            self.audio_view_frame.pack_forget()
            self.answer_view_frame.pack(fill=tk.BOTH, expand=True)
            self.prompt_bar.pack(fill=tk.X, side=tk.TOP, after=self.header)
        else:
            self.tab_audio.config(fg=C_EMERALD_LIGHT, bg=C_EMERALD_BG, bd=1, highlightbackground=C_EMERALD_BORDER, highlightthickness=1)
            self.tab_answer.config(fg=C_TEXT_MUTED, bg=C_BG_CARD, highlightthickness=0)
            self.answer_view_frame.pack_forget()
            self.prompt_bar.pack_forget()
            self.audio_view_frame.pack(fill=tk.BOTH, expand=True)

    # -------------------------------------------------------------------------
    # Manual Query Handling
    # -------------------------------------------------------------------------
    def _on_query_focus_in(self, event):
        if self.entry_manual_query.get() == "Ask Ghostline a question...":
            self.entry_manual_query.delete(0, tk.END)
            self.entry_manual_query.config(fg=C_TEXT_PRIMARY)

    def _on_query_focus_out(self, event):
        if not self.entry_manual_query.get().strip():
            self.entry_manual_query.insert(0, "Ask Ghostline a question...")
            self.entry_manual_query.config(fg=C_TEXT_MUTED)

    def _on_submit_manual_query(self):
        query = self.entry_manual_query.get().strip()
        if not query or query == "Ask Ghostline a question...":
            return
        self.entry_manual_query.delete(0, tk.END)
        self.lbl_prompt_text.config(text=query[:60] + ("..." if len(query) > 60 else ""), fg=C_CYAN_LIGHT)
        if self.on_ask_custom:
            self.on_ask_custom(query)

    def _on_click_solve(self):
        if self.on_trigger_screenshot:
            self.on_trigger_screenshot()
        elif self.on_retry:
            self.on_retry()

    def _draw_waveform(self):
        if not hasattr(self, "waveform_canvas") or not self.waveform_canvas:
            return
        self.waveform_canvas.delete("all")
        # 4 vertical green bars of varying heights (ılı)
        bars = [(3, 6), (8, 14), (13, 10), (18, 5)]
        for x, bar_h in bars:
            y1 = 8 - bar_h // 2
            y2 = 8 + bar_h // 2
            self.waveform_canvas.create_line(x, y1, x, y2, fill=C_EMERALD_LIGHT, width=2)

    def _update_prompt_chips(self, prompt_text: str):
        if not hasattr(self, "chips_container") or not self.chips_container:
            return
        for child in self.chips_container.winfo_children():
            child.destroy()
        if not prompt_text or not prompt_text.strip():
            self.lbl_prompt_text = tk.Label(
                self.chips_container,
                text="Press [Alt+/] to capture or enter question below",
                font=("Segoe UI", 8),
                fg=C_TEXT_MUTED,
                bg="#1a1d27",
                anchor="w"
            )
            self.lbl_prompt_text.pack(side=tk.LEFT)
            return

        words = prompt_text.strip().split()
        chunks = []
        current = []
        for w in words:
            current.append(w)
            if len(current) >= 3 or (len(chunks) == 3 and len(current) >= 2):
                chunks.append(" ".join(current))
                current = []
            if len(chunks) >= 4:
                break
        if current and len(chunks) < 4:
            chunks.append(" ".join(current))
        if not chunks:
            chunks = [prompt_text[:35]]

        for chunk in chunks:
            chip = tk.Frame(self.chips_container, bg="#272b38", bd=1, highlightbackground="#383e52", highlightthickness=1)
            chip.pack(side=tk.LEFT, padx=(0, 4), pady=2)
            lbl = tk.Label(chip, text=chunk, font=("Segoe UI", 8), fg=C_TEXT_PRIMARY, bg="#272b38", padx=6, pady=1)
            lbl.pack()

    def _copy_question_to_clipboard(self):
        if not self.root:
            return
        q_text = self.lbl_question_body.cget("text")
        if q_text and q_text.strip():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(q_text.strip())
                self.btn_copy_q.config(text="✓", fg=C_EMERALD_LIGHT)
                self.root.after(1500, lambda: self.btn_copy_q.config(text="⧉", fg=C_TEXT_MUTED))
            except Exception as e:
                logging.warning("[HUD] Question copy failed: %s", e)

    def _focus_query_input(self):
        if hasattr(self, "entry_manual_query") and self.entry_manual_query:
            self.entry_manual_query.focus_set()
            if self.entry_manual_query.get() == "Ask Ghostline a question...":
                self.entry_manual_query.delete(0, tk.END)
                self.entry_manual_query.config(fg=C_TEXT_PRIMARY)

    def clear_content(self):
        self._update_prompt_chips("")
        self.lbl_question_body.config(text="No question detected yet. Press [Alt+/] to solve.")
        self.ans_summary_label.config(text="Hover over question and press [Alt+/]\nto recognize and solve offline.")
        self._set_explanation_text("")
        self.badge_box.pack_forget()
        self.code_container.pack_forget()
        self.btn_copy_code.pack_forget()
        self.recovery_frame.pack_forget()

    # -------------------------------------------------------------------------
    # Viewport & Scrolling Events
    # -------------------------------------------------------------------------
    def _on_canvas_configure(self, event):
        if self.canvas and self.canvas_window:
            self.canvas.itemconfig(self.canvas_window, width=event.width)
            wrap = max(220, event.width - 70)
            self.ans_summary_label.config(wraplength=wrap)
            self.lbl_question_body.config(wraplength=max(220, event.width - 30))

    def _on_content_configure(self, event=None):
        if self.canvas:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _bind_mousewheel(self):
        if self.root:
            self.root.bind_all("<MouseWheel>", self._on_mousewheel)
            self.root.bind_all("<Button-4>", lambda e: self._on_key_scroll(-1))
            self.root.bind_all("<Button-5>", lambda e: self._on_key_scroll(1))

    def _unbind_mousewheel(self):
        if self.root:
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if not self.canvas:
            return "break"
        delta = event.delta
        step = int(-1 * (delta / 120)) * self.scroll_speed
        self.canvas.yview_scroll(step, "units")
        return "break"

    def _on_key_scroll(self, direction: int):
        if self.canvas and not self.is_minimized:
            self.canvas.yview_scroll(direction * self.scroll_speed, "units")

    def _on_key_page_scroll(self, direction: int):
        if self.canvas and not self.is_minimized:
            self.canvas.yview_scroll(direction, "pages")

    # -------------------------------------------------------------------------
    # Visual State & Spinner (Tested by test_hud_scrollable_viewport_and_controls)
    # -------------------------------------------------------------------------
    def _draw_eyes(self, color: str):
        self._stop_spinner()
        self.status_canvas.delete("all")
        self.status_canvas.create_oval(2, 2, 9, 13, outline=color, width=1)
        self.status_canvas.create_oval(4, 5, 7, 10, fill=color, outline="")
        self.status_canvas.create_oval(13, 2, 20, 13, outline=color, width=1)
        self.status_canvas.create_oval(15, 5, 18, 10, fill=color, outline="")

    def _start_spinner(self, color: str = C_AMBER):
        self._spinner_running = True
        self._spinner_angle = 0
        self._animate_spinner(color)

    def _animate_spinner(self, color: str):
        if not self._spinner_running or not self.status_canvas:
            return
        self.status_canvas.delete("all")
        cx, cy, r = 10, 8, 6
        self.status_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#2a374d", width=1.5)
        self.status_canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=self._spinner_angle,
            extent=90,
            outline=color,
            width=2,
            style="arc"
        )
        self._spinner_angle = (self._spinner_angle + 30) % 360
        if self.root:
            self._spinner_after_id = self.root.after(70, lambda: self._animate_spinner(color))

    def _stop_spinner(self):
        self._spinner_running = False
        if self._spinner_after_id and self.root:
            try:
                self.root.after_cancel(self._spinner_after_id)
            except Exception:
                pass
            self._spinner_after_id = None

    # -------------------------------------------------------------------------
    # Drag & Positioning
    # -------------------------------------------------------------------------
    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        if not self.root or self.is_pinned:
            return
        new_x = self.root.winfo_x() + (event.x - self._drag_start_x)
        new_y = self.root.winfo_y() + (event.y - self._drag_start_y)
        self.pos_x = new_x
        self.pos_y = new_y
        self.root.geometry(f"+{new_x}+{new_y}")
        if self.on_position_changed:
            self.on_position_changed(new_x, new_y)

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if not self.root or not self.is_visible:
            return None
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            return (x, y, x + w, y + h)
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Controls: Pin, Pause, Minimize
    # -------------------------------------------------------------------------
    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.btn_pin.config(
            text="📌" if self.is_pinned else "📍",
            fg=C_EMERALD_LIGHT if self.is_pinned else C_TEXT_MUTED
        )
        logging.info("[HUD] Pin state changed: %s", self.is_pinned)

    def toggle_pause(self):
        if self.on_toggle_pause:
            self.is_paused = self.on_toggle_pause()
        else:
            self.is_paused = not self.is_paused

        self.btn_pause.config(
            text="⏸" if not self.is_paused else "▶",
            fg=C_EMERALD_LIGHT if not self.is_paused else C_AMBER
        )
        if self.is_paused:
            self.status_label.config(text="Hover Paused", fg=C_AMBER)
            self._draw_eyes(C_AMBER)
        elif self.phase == "ready":
            self.status_label.config(text="Ready", fg=C_EMERALD_LIGHT)
            self._draw_eyes(C_EMERALD_LIGHT)

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.prompt_bar.pack_forget()
            self.viewport_container.pack_forget()
            self.footer.pack_forget()
            self.btn_min.config(text="⤢")
            compact_h = 36
            self.root.geometry(f"{self.width}x{compact_h}+{self.pos_x}+{self.pos_y}")
        else:
            self.btn_min.config(text="—")
            if self.active_mode == "answer":
                self.prompt_bar.pack(fill=tk.X, side=tk.TOP, after=self.header)
            self.viewport_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            self.footer.pack(fill=tk.X, side=tk.BOTTOM)
            self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
            if self.canvas:
                self.canvas.yview_moveto(0.0)

    def _on_toggle_audio(self):
        if self.on_toggle_audio:
            self.on_toggle_audio()

    def update_audio_status(self, is_capturing: bool, is_paused: bool = False):
        self.is_audio_capturing = is_capturing
        self.is_audio_paused = is_paused

        def _update():
            if not hasattr(self, "btn_audio") or not self.btn_audio:
                return
            if is_capturing:
                if is_paused:
                    self.btn_audio.config(text="⏸️ 🎙️", fg=C_AMBER)
                    self.lbl_hud_rec.config(text="⏸ PAUSED", bg=C_AMBER_BG, fg=C_AMBER_LIGHT)
                    self.lbl_hud_rec.pack(side=tk.LEFT, padx=(4, 2), before=self.mode_frame)
                else:
                    self.btn_audio.config(text="🔴 🎙️", fg=C_REC)
                    self.lbl_hud_rec.config(text="● REC", bg=C_REC_BG, fg=C_REC)
                    self.lbl_hud_rec.pack(side=tk.LEFT, padx=(4, 2), before=self.mode_frame)
                self.btn_audio_start_stop.config(text="⏹ Stop Listening", fg=C_DANGER_LIGHT, bg=C_DANGER_BG)
            else:
                self.btn_audio.config(text="🎙️", fg=C_TEXT_MUTED)
                self.lbl_hud_rec.pack_forget()
                self.btn_audio_start_stop.config(text="▶ Start Listening", fg=C_EMERALD_LIGHT, bg=C_EMERALD_BG)

        if self.root:
            if threading.current_thread() is threading.main_thread():
                _update()
            else:
                self.root.after(0, _update)

    # -------------------------------------------------------------------------
    # Audio HUD Segment Appending
    # -------------------------------------------------------------------------
    def append_transcript_segment(self, segment):
        def _append():
            if not hasattr(self, "txt_hud_transcript"):
                return
            src_tag = "source_call" if segment.source == "call" else "source_mic"
            self.txt_hud_transcript.insert(tk.END, f"[{segment.time_str}] ", "timestamp")
            self.txt_hud_transcript.insert(tk.END, f"{segment.speaker_label}: ", src_tag)
            self.txt_hud_transcript.insert(tk.END, f"{segment.text}\n", "final")
            self.txt_hud_transcript.see(tk.END)
        if self.root:
            self.root.after(0, _append)

    def append_ai_answer(self, text: str):
        def _append():
            if not hasattr(self, "txt_hud_ai"):
                return
            self.txt_hud_ai.insert(tk.END, f"{text}\n\n")
            self.txt_hud_ai.see(tk.END)
        if self.root:
            self.root.after(0, _append)

    def clear_audio_transcript(self):
        if hasattr(self, "txt_hud_transcript"):
            self.txt_hud_transcript.delete("1.0", tk.END)
        if hasattr(self, "txt_hud_ai"):
            self.txt_hud_ai.delete("1.0", tk.END)

    # -------------------------------------------------------------------------
    # Clipboard Operations
    # -------------------------------------------------------------------------
    def copy_answer_to_clipboard(self):
        if not self.root:
            return
        if self.current_presentation:
            payload = self.current_presentation.formatted_clipboard_text
        else:
            payload = ""
            if self.answer_badge:
                payload += f"Option {self.answer_badge}\n"
            if self.answer_text:
                payload += f"{self.answer_text}\n\n"
            if self.raw_explanation:
                payload += f"{self.raw_explanation}\n"
            if self.current_code:
                payload += f"\nCode:\n{self.current_code}"

        if payload.strip():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(payload.strip())
                self.btn_copy_ans.config(text="✓ Copied!", fg=C_EMERALD_LIGHT)
                self.root.after(1500, lambda: self.btn_copy_ans.config(text="📋 Copy Answer", fg=C_TEXT_PRIMARY))
            except Exception as e:
                logging.warning("[HUD] Clipboard copy failed: %s", e)

    def copy_code_to_clipboard(self):
        if not self.root or not self.current_code:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_code)
            self.btn_copy_code.config(text="✓ Code Copied!", fg=C_TEXT_PRIMARY)
            self.root.after(1500, lambda: self.btn_copy_code.config(text="💻 Copy Code", fg=C_EMERALD_LIGHT))
        except Exception as e:
            logging.warning("[HUD] Code copy failed: %s", e)

    def retry_solve(self):
        if self.on_retry:
            try:
                self.btn_retry.config(text="🔄 Retrying...", fg=C_AMBER)
                if self.root:
                    self.root.after(1000, lambda: self.btn_retry.config(text="🔄 Retry", fg=C_TEXT_PRIMARY))
            except Exception:
                pass
            self.on_retry()

    def toggle_code_collapse(self):
        self.is_code_collapsed = not self.is_code_collapsed
        if self.is_code_collapsed:
            self.code_text_frame.pack_forget()
            self.code_scroll_x.pack_forget()
            self.btn_toggle_code.config(text="[+] Expand", fg=C_CYAN_LIGHT)
        else:
            self.code_text_frame.pack(fill=tk.BOTH, expand=True)
            self.code_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            self.btn_toggle_code.config(text="[-] Collapse", fg=C_TEXT_MUTED)
        self._fit_window_to_content()

    def start_solve(self) -> int:
        self._current_solve_id += 1
        return self._current_solve_id

    # -------------------------------------------------------------------------
    # State Updates & Scrollable Viewport
    # -------------------------------------------------------------------------
    def set_state(
        self,
        phase: str,
        text: str = "",
        badge: str = "",
        presentation: Optional[PresentedAnswer] = None,
        solve_id: Optional[int] = None
    ):
        if not self.root:
            return
        if solve_id is not None and solve_id < self._current_solve_id:
            logging.debug("[HUD] Stale update ignored: phase=%s, solve_id=%s", phase, solve_id)
            return
        self.root.after(0, self._apply_state, phase, text, badge, presentation, solve_id)

    def _apply_state(
        self,
        phase: str,
        text: str = "",
        badge: str = "",
        presentation: Optional[PresentedAnswer] = None,
        solve_id: Optional[int] = None
    ):
        if solve_id is not None and solve_id < self._current_solve_id:
            return

        if self._dismiss_timer and self.root:
            try:
                self.root.after_cancel(self._dismiss_timer)
            except Exception:
                pass
            self._dismiss_timer = None

        self.phase = phase
        self.current_presentation = presentation

        if self.canvas:
            self.canvas.yview_moveto(0.0)

        self.btn_retry.config(text="🔄 Retry", fg=C_TEXT_PRIMARY)
        self.recovery_frame.pack_forget()

        if phase == "ready":
            self._stop_spinner()
            self.status_label.config(text="Ready", fg=C_EMERALD_LIGHT if not self.is_paused else C_AMBER)
            self._draw_eyes(C_EMERALD_LIGHT if not self.is_paused else C_AMBER)
            self.badge_box.pack_forget()
            self.code_container.pack_forget()
            self.btn_copy_code.pack_forget()
            self.ans_summary_label.config(
                text="Hover over question and press [Alt+/]\nto recognize and solve offline.",
                fg=C_TEXT_MUTED
            )
            self._set_explanation_text("")
            return

        elif phase in ["capturing", "recognizing", "thinking"]:
            status_text = {
                "capturing": "Capturing Screen...",
                "recognizing": "Recognizing Text (OCR)...",
                "thinking": "Thinking (Local AI)..."
            }.get(phase, "Processing...")
            self.status_label.config(text=status_text, fg=C_AMBER)
            self._start_spinner(C_AMBER)
            self.badge_box.pack_forget()
            self.code_container.pack_forget()
            self.btn_copy_code.pack_forget()
            self.ans_summary_label.config(text="Analyzing on-screen content...", fg=C_TEXT_PRIMARY)
            self._set_explanation_text("")
            return

        # Phase is answer or error
        self._stop_spinner()

        if presentation is not None:
            q_type = presentation.question_type
            badge = presentation.badge
            headline = presentation.headline
            direct_ans = presentation.direct_answer
            explanation = presentation.explanation
            code = presentation.code or ""
            lang = presentation.code_language or ""
            is_valid = presentation.is_validated
            raw_ocr = getattr(presentation, "raw_ocr_text", "")
            recovery = getattr(presentation, "recovery_guidance", "")
        else:
            prose, code, lang = extract_code_and_prose(text)
            explanation = prose or text
            is_valid = (phase == "answer" and badge not in ["?", "!"])
            q_type = TYPE_ERROR if badge == "!" else (
                TYPE_UNCERTAIN if badge == "?" else (
                    TYPE_MCQ if badge in ["1", "2", "3", "4", "5", "A", "B", "C", "D", "E"] else (
                        TYPE_CODE if code else TYPE_THEORY
                    )
                )
            )
            headline = (
                f"Option {badge}" if badge in ["1", "2", "3", "4", "5", "A", "B", "C", "D", "E"]
                else ("Verified Answer" if is_valid else text)
            )
            raw_ocr = ""
            recovery = ""

        self.answer_badge = badge
        self.answer_text = headline
        self.raw_explanation = explanation
        self.current_code = code
        self.current_lang = lang

        # Update Question Container & Keyword Chips (Reference 2)
        q_str = getattr(presentation, "question_text", "") if presentation else ""
        if not q_str and presentation:
            q_str = getattr(presentation, "raw_ocr_text", "")
        if not q_str and text:
            q_str = text
        if q_str:
            self.lbl_question_body.config(text=q_str)
            self._update_prompt_chips(q_str)

        if presentation and getattr(presentation, "options", None) and len(presentation.options) >= 2:
            self.lbl_question_type_badge.config(text="MULTIPLE CHOICE", fg=C_CYAN_LIGHT, bg=C_CYAN_BG)
        elif q_type == TYPE_CODE:
            self.lbl_question_type_badge.config(text="CODING CHALLENGE", fg=C_EMERALD_LIGHT, bg=C_EMERALD_BG)
        elif q_type == TYPE_NUMERICAL:
            self.lbl_question_type_badge.config(text="NUMERICAL CALCULATION", fg=C_AMBER_LIGHT, bg=C_AMBER_BG)
        else:
            self.lbl_question_type_badge.config(text="SCREEN QUESTION", fg=C_TEXT_SECONDARY, bg=C_BG_CARD)

        if not is_valid or q_type in [TYPE_ERROR, TYPE_UNCERTAIN] or phase == "error":
            is_uncertain = (q_type == TYPE_UNCERTAIN or badge == "?")
            status_title = "Uncertain (?)" if is_uncertain else "Error (!)"
            color = C_AMBER if is_uncertain else C_DANGER
            self.status_label.config(text=status_title, fg=color)
            self._draw_eyes(color)

            if badge:
                self.badge_box.pack(side=tk.LEFT, padx=(0, 8))
                bg_err = C_AMBER_BG if is_uncertain else C_DANGER_BG
                self.badge_box.config(bg=bg_err, highlightbackground=color)
                self.badge_label.config(text=badge, fg=color, bg=bg_err)
            else:
                self.badge_box.pack_forget()

            self.code_container.pack_forget()
            self.btn_copy_code.pack_forget()

            summary = headline or ("Could not validate answer reliably" if is_uncertain else "Inference Pipeline Error")
            self.ans_summary_label.config(text=summary, fg=color)
            self._set_explanation_text(explanation)
            self.btn_retry.config(fg=color)

            # Render recovery card if extraction uncertainty occurred
            if is_uncertain or raw_ocr:
                self._render_recovery_card(raw_ocr, recovery)

            self._fit_window_to_content()

            if self.timeout_sec > 0 and self.root:
                self._dismiss_timer = self.root.after(int(self.timeout_sec * 1000), self.hide)
            return

        # Valid answer ready
        self.status_label.config(text="Answer Ready", fg=C_EMERALD_LIGHT)
        self._draw_eyes(C_EMERALD_LIGHT)

        if badge:
            self.badge_box.pack(side=tk.LEFT, padx=(0, 8))
            self.badge_box.config(bg=C_EMERALD_BG, highlightbackground=C_EMERALD)
            self.badge_label.config(text=badge, fg=C_EMERALD_LIGHT, bg=C_EMERALD_BG)
        else:
            self.badge_box.pack_forget()

        self.ans_summary_label.config(text=headline or "Identified Answer", fg=C_TEXT_PRIMARY)
        self._set_explanation_text(explanation)

        if code:
            from ghostline.core.llm_client import extract_and_normalize_code
            clean_code, clean_lang, _ = extract_and_normalize_code(code, lang)
            code = clean_code
            lang = clean_lang or lang
            self.current_code = code
            self.current_lang = lang

            self.code_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 6))
            self.code_lang_label.config(text=lang.upper() if lang else "CODE")
            code_lines = len(code.splitlines())
            self.code_text.config(height=max(4, min(14, code_lines)))
            apply_syntax_highlighting(self.code_text, code, lang)
            self.btn_copy_code.pack(side=tk.LEFT, padx=4, pady=2)
            if self.is_code_collapsed:
                self.code_text_frame.pack_forget()
                self.code_scroll_x.pack_forget()
                self.btn_toggle_code.config(text="[+] Expand", fg=C_CYAN_LIGHT)
            else:
                self.code_text_frame.pack(fill=tk.BOTH, expand=True)
                self.code_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
                self.btn_toggle_code.config(text="[-] Collapse", fg=C_TEXT_MUTED)
        else:
            self.code_container.pack_forget()
            self.btn_copy_code.pack_forget()

        self._fit_window_to_content()

        if self.timeout_sec > 0 and self.root:
            self._dismiss_timer = self.root.after(int(self.timeout_sec * 1000), self.hide)

    def _render_recovery_card(self, raw_ocr: str, recovery: str):
        """Displays clear diagnostic card when question extraction was uncertain."""
        for child in self.recovery_frame.winfo_children():
            child.destroy()

        self.recovery_frame.pack(fill=tk.X, padx=8, pady=(4, 6))
        head = tk.Frame(self.recovery_frame, bg="#1a1313")
        head.pack(fill=tk.X, padx=6, pady=(4, 2))

        tk.Label(
            head,
            text="RECOVERY GUIDANCE",
            font=("Segoe UI", 7, "bold"),
            fg=C_AMBER_LIGHT,
            bg="#1a1313"
        ).pack(side=tk.LEFT)

        if raw_ocr:
            snippet = raw_ocr.strip()
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."
            tk.Label(
                self.recovery_frame,
                text=f"Raw Captured OCR:\n\"{snippet}\"",
                font=("Consolas", 8),
                fg=C_TEXT_MUTED,
                bg="#1a1313",
                justify=tk.LEFT,
                wraplength=380
            ).pack(fill=tk.X, padx=8, pady=(2, 4))

        rec_btn_row = tk.Frame(self.recovery_frame, bg="#1a1313")
        rec_btn_row.pack(fill=tk.X, padx=8, pady=(2, 6))

        btn_retry_rec = tk.Label(
            rec_btn_row,
            text="↻ Retry Capture [Alt+/]",
            font=("Segoe UI", 8, "bold"),
            fg=C_CYAN_LIGHT,
            bg=C_CYAN_BG,
            cursor="hand2",
            padx=8,
            pady=2,
            bd=1,
            highlightbackground=C_CYAN_BORDER,
            highlightthickness=1
        )
        btn_retry_rec.pack(side=tk.LEFT, padx=(0, 6))
        btn_retry_rec.bind("<Button-1>", lambda e: self.retry_solve())

        tk.Label(
            rec_btn_row,
            text="Or use input bar below",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg="#1a1313"
        ).pack(side=tk.LEFT)

    def _set_explanation_text(self, text: str):
        self.explanation_text.config(state=tk.NORMAL)
        self.explanation_text.delete("1.0", tk.END)
        if text.strip():
            self.explanation_text.insert("1.0", text.strip())
            line_count = int(self.explanation_text.index("end-1c").split(".")[0])
            self.explanation_text.config(height=max(2, min(14, line_count)))
            self.explanation_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 6))
        else:
            self.explanation_frame.pack_forget()
        self.explanation_text.config(state=tk.DISABLED)
        self._on_content_configure()

    def _fit_window_to_content(self):
        if not self.root or self.is_minimized:
            return
        self.root.update_idletasks()
        content_h = self.scrollable_content.winfo_reqheight()
        target_h = max(260, min(content_h + 110, self.max_height))
        if target_h != self.height:
            self.height = target_h
            self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def append_stream_token(self, token: str, solve_id: Optional[int] = None):
        if not self.root:
            return
        if solve_id is not None and solve_id < self._current_solve_id:
            return
        self.root.after(0, self._append_token_ui, token)

    def _append_token_ui(self, token: str):
        self.explanation_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 6))
        self.explanation_text.config(state=tk.NORMAL)
        self.explanation_text.insert(tk.END, token)
        self.explanation_text.config(state=tk.DISABLED)
        self._on_content_configure()

    # -------------------------------------------------------------------------
    # Visibility & Lifecycle
    # -------------------------------------------------------------------------
    def show(self):
        if self.root:
            self.root.after(0, self._show_ui)

    def _show_ui(self):
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", self.always_on_top)
            if sys.platform == "win32" and self.hwnd and self.always_on_top:
                try:
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOACTIVATE = 0x0010
                    SWP_SHOWWINDOW = 0x0040
                    ctypes.windll.user32.SetWindowPos(
                        self.hwnd, -1, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                    )
                except Exception:
                    pass
            self.is_visible = True

    def hide(self):
        if self.root:
            self.root.after(0, self._hide_ui)

    def _hide_ui(self):
        if self._dismiss_timer and self.root:
            try:
                self.root.after_cancel(self._dismiss_timer)
            except Exception:
                pass
            self._dismiss_timer = None
        self._stop_spinner()
        if self.root:
            self.root.withdraw()
            self.is_visible = False
        if self.on_close:
            self.on_close()

    def toggle_visibility(self):
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def destroy(self):
        if self._dismiss_timer and self.root:
            try:
                self.root.after_cancel(self._dismiss_timer)
            except Exception:
                pass
            self._dismiss_timer = None
        self._stop_spinner()
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass
            self.root = None
            self.is_visible = False
