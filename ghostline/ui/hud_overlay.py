import os
import sys
import ctypes
import logging
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Callable, Tuple, Dict, Any

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


# Visual styling constants: Ghostline stealth dark aesthetic with emerald green accents
C_BG_BASE = "#0f1117"        # Dark window canvas
C_BG_CARD = "#161b26"        # Header and card surface
C_BG_CODE = "#090d16"        # Deep black for code block
C_BORDER_EMERALD = "#059669" # Emerald green accent border
C_BORDER_MUTED = "#1e293b"   # Slate border
C_TEXT_PRIMARY = "#f8fafc"   # Clean white
C_TEXT_MUTED = "#94a3b8"     # Secondary slate
C_TEXT_EXPLAIN = "#cbd5e1"   # Explanation body
C_EMERALD = "#10b981"        # Primary vibrant emerald accent
C_EMERALD_BG = "#064e3b"     # Badge container background
C_EMERALD_TEXT = "#34d399"   # Badge text
C_AMBER = "#f59e0b"          # Warning / thinking / pause
C_DANGER = "#f87171"         # Error text


class GhostlineHudOverlay:
    """
    Floating, translucent, draggable AI HUD overlay.
    Features:
    - Subtle emerald green stealth aesthetics matching Ghostline AnswerWindow
    - Dedicated scrollable viewport (Canvas + Scrollbar) supporting mouse-wheel,
      scrollbar dragging, and keyboard navigation
    - Selectable, word-wrapped explanation text
    - Code container with syntax highlighting, horizontal scrolling, and Copy Code button
    - WS_EX_NOACTIVATE focus-free window handling (never steals user typing focus)
    - SetWindowDisplayAffinity screen capture exclusion support
    - Minimize (compact pill) and Expand (full card) modes
    - Copy Answer & Copy Code buttons with visual feedback
    - Pause/Resume hover detection controls
    - Pin/Unpin position locking
    - Animated inference progress indicator
    - Bounds constraints ensuring HUD never overflows configured screen dimensions
    """
    def __init__(
        self,
        on_close: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], bool]] = None,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
        on_retry: Optional[Callable[[], None]] = None,
        opacity: float = 0.95,
        width: int = 400,
        height: int = 320,
        max_width: int = 520,
        max_height: int = 460,
        scroll_speed: int = 2,
        pos_x: Optional[int] = None,
        pos_y: Optional[int] = None,
        is_pinned: bool = False,
        always_on_top: bool = True,
        exclude_from_capture: bool = True,
        is_paused: bool = False,
        on_toggle_audio: Optional[Callable[[], None]] = None
    ):
        self.root: Optional[tk.Tk] = None
        self.hwnd: Optional[int] = None
        self.on_close = on_close
        self.on_toggle_pause = on_toggle_pause
        self.on_position_changed = on_position_changed
        self.on_retry = on_retry
        self.on_toggle_audio = on_toggle_audio

        self.opacity = max(0.4, min(1.0, opacity))
        self.width = max(280, min(width, max_width))
        self.height = max(200, min(height, max_height))
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

        # Spinner animation state
        self._spinner_running = False
        self._spinner_angle = 0
        self._spinner_after_id = None

        # Solve ID to prevent stale updates from overwriting newer solves
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

    def launch(self, parent: Optional[tk.Tk] = None, start_visible: bool = False):
        """Initializes HUD as Toplevel child or standalone Tk instance."""
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Ghostline Floating HUD")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.always_on_top)
        self.root.attributes("-alpha", self.opacity)

        # Calculate initial position within display bounds
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if self.pos_x is None or self.pos_y is None:
            self.pos_x = max(20, sw - self.width - 40)
            self.pos_y = max(20, sh - self.height - 60)
        else:
            self.pos_x = max(0, min(self.pos_x, sw - self.width))
            self.pos_y = max(0, min(self.pos_y, sh - self.height))

        self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
        self.root.configure(bg=C_BG_BASE)

        # Typography
        self.title_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.body_font = tkfont.Font(family="Segoe UI", size=9)
        self.badge_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.kbd_font = tkfont.Font(family="Segoe UI", size=8)
        self.code_font = tkfont.Font(family="Consolas", size=9)

        # Build UI with dedicated scrollable viewport
        self._build_ui()

        # Keyboard shortcuts & Navigation
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Up>", lambda e: self._on_key_scroll(-1))
        self.root.bind("<Down>", lambda e: self._on_key_scroll(1))
        self.root.bind("<Prior>", lambda e: self._on_key_page_scroll(-1))
        self.root.bind("<Next>", lambda e: self._on_key_page_scroll(1))
        self.root.bind("<Home>", lambda e: self.canvas.yview_moveto(0.0))
        self.root.bind("<End>", lambda e: self.canvas.yview_moveto(1.0))

        # Mouse Wheel bindings
        self.root.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.root.bind("<Leave>", lambda e: self._unbind_mousewheel())

        # Apply Win32 extended styles (WS_EX_NOACTIVATE & Capture Exclusion)
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
                WS_EX_TOOLWINDOW = 0x00000080
                cur_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    self.hwnd, GWL_EXSTYLE, cur_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                )

                if self.exclude_from_capture:
                    set_capture_exclusion(self.hwnd, True)
                logging.info("[HUD] Applied Win32 styles (HWND=%s, NoActivate=True, ExcludeFromCapture=%s)",
                             self.hwnd, self.exclude_from_capture)
        except Exception as e:
            logging.warning("[HUD] Note on Win32 attributes application: %s", e)

    def _build_ui(self):
        # Outer Border with subtle emerald accent
        self.outer_border = tk.Frame(self.root, bg=C_BORDER_EMERALD, bd=1)
        self.outer_border.pack(fill=tk.BOTH, expand=True)

        self.main_container = tk.Frame(self.outer_border, bg=C_BG_BASE)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # ---------------------------------------------------------
        # 1. Header Control Bar (Fixed, never scrolls)
        # ---------------------------------------------------------
        self.header = tk.Frame(self.main_container, bg=C_BG_CARD, height=32)
        self.header.pack(fill=tk.X, side=tk.TOP)
        self.header.pack_propagate(False)

        # Dragging bindings on header
        self.header.bind("<ButtonPress-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._on_drag)

        # Status Icon (Canvas for eyes and animated spinner)
        self.status_canvas = tk.Canvas(self.header, width=22, height=16, bg=C_BG_CARD, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(8, 4), pady=7)
        self.status_canvas.bind("<ButtonPress-1>", self._start_drag)
        self.status_canvas.bind("<B1-Motion>", self._on_drag)
        self._draw_eyes(C_EMERALD)

        # Status Label
        self.status_label = tk.Label(
            self.header,
            text="Ready",
            font=self.title_font,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD
        )
        self.status_label.pack(side=tk.LEFT, pady=5)
        self.status_label.bind("<ButtonPress-1>", self._start_drag)
        self.status_label.bind("<B1-Motion>", self._on_drag)

        # Header Control Buttons (Right aligned)
        # Close Button
        self.btn_close = tk.Label(
            self.header,
            text="×",
            font=("Segoe UI", 12, "bold"),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=6
        )
        self.btn_close.pack(side=tk.RIGHT, padx=(0, 4))
        self.btn_close.bind("<Button-1>", lambda e: self.hide())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.config(fg="#fca5a5"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.config(fg=C_TEXT_MUTED))

        # Minimize / Expand Button
        self.btn_min = tk.Label(
            self.header,
            text="—",
            font=("Segoe UI", 10, "bold"),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=4
        )
        self.btn_min.pack(side=tk.RIGHT, padx=2)
        self.btn_min.bind("<Button-1>", lambda e: self.toggle_minimize())
        self.btn_min.bind("<Enter>", lambda e: self.btn_min.config(fg=C_TEXT_PRIMARY))
        self.btn_min.bind("<Leave>", lambda e: self.btn_min.config(fg=C_TEXT_MUTED))

        # Pin / Unpin Button
        self.btn_pin = tk.Label(
            self.header,
            text="📌" if self.is_pinned else "📍",
            font=("Segoe UI", 8),
            fg=C_EMERALD if self.is_pinned else C_TEXT_MUTED,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=4
        )
        self.btn_pin.pack(side=tk.RIGHT, padx=2)
        self.btn_pin.bind("<Button-1>", lambda e: self.toggle_pin())

        # Pause / Resume Hover Button
        self.btn_pause = tk.Label(
            self.header,
            text="⏸" if not self.is_paused else "▶",
            font=("Segoe UI", 8, "bold"),
            fg=C_EMERALD if not self.is_paused else C_AMBER,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=4
        )
        self.btn_pause.pack(side=tk.RIGHT, padx=2)
        self.btn_pause.bind("<Button-1>", lambda e: self.toggle_pause())

        # Audio Assistant Toggle / Status Button
        self.btn_audio = tk.Label(
            self.header,
            text="🎙️",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=4
        )
        self.btn_audio.pack(side=tk.RIGHT, padx=2)
        self.btn_audio.bind("<Button-1>", lambda e: self._on_toggle_audio())

        # ---------------------------------------------------------
        # 2. Action Bar / Footer (Fixed at bottom)
        # ---------------------------------------------------------
        self.footer = tk.Frame(self.main_container, bg=C_BG_CARD, height=28)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)

        self.btn_copy_ans = tk.Label(
            self.footer,
            text="📋 Copy Answer",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=8,
            pady=3
        )
        self.btn_copy_ans.pack(side=tk.LEFT, padx=(6, 4), pady=2)
        self.btn_copy_ans.bind("<Button-1>", lambda e: self.copy_answer_to_clipboard())
        self.btn_copy_ans.bind("<Enter>", lambda e: self.btn_copy_ans.config(fg=C_EMERALD))
        self.btn_copy_ans.bind("<Leave>", lambda e: self.btn_copy_ans.config(fg=C_TEXT_PRIMARY))

        self.btn_copy_code = tk.Label(
            self.footer,
            text="💻 Copy Code",
            font=self.kbd_font,
            fg=C_EMERALD,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=8,
            pady=3
        )
        self.btn_copy_code.bind("<Button-1>", lambda e: self.copy_code_to_clipboard())

        self.btn_retry = tk.Label(
            self.footer,
            text="🔄 Retry",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD,
            cursor="hand2",
            padx=8,
            pady=3
        )
        self.btn_retry.pack(side=tk.LEFT, padx=(2, 4), pady=2)
        self.btn_retry.bind("<Button-1>", lambda e: self.retry_solve())
        self.btn_retry.bind("<Enter>", lambda e: self.btn_retry.config(fg=C_EMERALD))
        self.btn_retry.bind("<Leave>", lambda e: self.btn_retry.config(fg=C_TEXT_PRIMARY))

        self.footer_hint = tk.Label(
            self.footer,
            text="[Alt+/] Solve · [Esc] Hide",
            font=self.kbd_font,
            fg="#64748b",
            bg=C_BG_CARD
        )
        self.footer_hint.pack(side=tk.RIGHT, padx=8, pady=3)

        # ---------------------------------------------------------
        # 3. Dedicated Scrollable Viewport (Canvas + Scrollbar)
        # ---------------------------------------------------------
        self.viewport_container = tk.Frame(self.main_container, bg=C_BG_BASE)
        self.viewport_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.canvas = tk.Canvas(
            self.viewport_container,
            bg=C_BG_BASE,
            highlightthickness=0,
            bd=0
        )
        self.v_scrollbar = tk.Scrollbar(
            self.viewport_container,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
            width=8
        )
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.scrollable_content = tk.Frame(self.canvas, bg=C_BG_BASE)
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_content,
            anchor="nw"
        )

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Automatically update scrollable width and scroll region on resize
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_content.bind("<Configure>", self._on_content_configure)

        # ---------------------------------------------------------
        # 4. Content Cards (Inside scrollable content)
        # ---------------------------------------------------------
        # Answer Top Row: Badge + Headline
        self.ans_row = tk.Frame(self.scrollable_content, bg=C_BG_BASE)
        self.ans_row.pack(fill=tk.X, padx=8, pady=(6, 4))

        self.badge_box = tk.Frame(
            self.ans_row,
            bg=C_EMERALD_BG,
            padx=8,
            pady=2,
            bd=1,
            highlightbackground=C_EMERALD,
            highlightthickness=1
        )
        self.badge_box.pack(side=tk.LEFT, padx=(0, 8))
        self.badge_label = tk.Label(
            self.badge_box,
            text="",
            font=self.badge_font,
            fg=C_EMERALD_TEXT,
            bg=C_EMERALD_BG
        )
        self.badge_label.pack()

        self.ans_summary_label = tk.Label(
            self.ans_row,
            text="Hover over question and press [Alt+/]\nto recognize and solve offline.",
            font=self.title_font,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_BASE,
            justify=tk.LEFT,
            wraplength=280,
            anchor="w"
        )
        self.ans_summary_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Selectable Explanation Text Widget with Word Wrap
        self.explanation_frame = tk.Frame(self.scrollable_content, bg=C_BG_BASE)
        self.explanation_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 6))

        self.explanation_text = tk.Text(
            self.explanation_frame,
            font=self.body_font,
            fg=C_TEXT_EXPLAIN,
            bg=C_BG_BASE,
            bd=0,
            highlightthickness=0,
            wrap=tk.WORD,
            exportselection=False,
            height=3,
            padx=2,
            pady=2,
            cursor="arrow"
        )
        self.explanation_text.pack(fill=tk.BOTH, expand=True)
        self.explanation_text.config(state=tk.DISABLED)

        # Code Block Container (shown only when code snippet exists)
        self.code_container = tk.Frame(
            self.scrollable_content,
            bg=C_BG_CODE,
            bd=1,
            highlightbackground=C_BORDER_MUTED,
            highlightthickness=1
        )

        code_top = tk.Frame(self.code_container, bg="#0d131f", height=22)
        code_top.pack(fill=tk.X, side=tk.TOP)
        self.code_lang_label = tk.Label(
            code_top,
            text="CODE",
            font=("Segoe UI", 7, "bold"),
            fg=C_EMERALD,
            bg="#0d131f"
        )
        self.code_lang_label.pack(side=tk.LEFT, padx=6)

        self.btn_toggle_code = tk.Label(
            code_top,
            text="[-] Collapse",
            font=("Segoe UI", 7),
            fg=C_TEXT_MUTED,
            bg="#0d131f",
            cursor="hand2",
            padx=6
        )
        self.btn_toggle_code.pack(side=tk.RIGHT)
        self.btn_toggle_code.bind("<Button-1>", lambda e: self.toggle_code_collapse())
        self.btn_toggle_code.bind("<Enter>", lambda e: self.btn_toggle_code.config(fg=C_TEXT_PRIMARY))
        self.btn_toggle_code.bind("<Leave>", lambda e: self.btn_toggle_code.config(fg=C_TEXT_MUTED))

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
            padx=6,
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

    # -------------------------------------------------------------
    # Scrollable Viewport Events
    # -------------------------------------------------------------
    def _on_canvas_configure(self, event):
        """Ensures the inner scrollable content frame matches canvas width."""
        if self.canvas and self.canvas_window:
            self.canvas.itemconfig(self.canvas_window, width=event.width)
            # Update summary wraplength to match canvas width minus padding
            wrap = max(200, event.width - 80)
            self.ans_summary_label.config(wraplength=wrap)

    def _on_content_configure(self, event=None):
        """Updates canvas scrollregion when content changes."""
        if self.canvas:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _bind_mousewheel(self):
        """Binds mouse-wheel scrolling when cursor is over HUD."""
        if self.root:
            self.root.bind_all("<MouseWheel>", self._on_mousewheel)
            self.root.bind_all("<Button-4>", lambda e: self._on_key_scroll(-1))
            self.root.bind_all("<Button-5>", lambda e: self._on_key_scroll(1))

    def _unbind_mousewheel(self):
        """Unbinds mouse-wheel scrolling when cursor leaves HUD."""
        if self.root:
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        """Handles smooth mouse-wheel scrolling."""
        if not self.canvas:
            return "break"
        delta = event.delta
        # Windows event.delta is typically +/- 120
        step = int(-1 * (delta / 120)) * self.scroll_speed
        self.canvas.yview_scroll(step, "units")
        return "break"

    def _on_key_scroll(self, direction: int):
        """Handles keyboard arrow up/down scrolling."""
        if self.canvas and not self.is_minimized:
            self.canvas.yview_scroll(direction * self.scroll_speed, "units")

    def _on_key_page_scroll(self, direction: int):
        """Handles PageUp / PageDown scrolling."""
        if self.canvas and not self.is_minimized:
            self.canvas.yview_scroll(direction, "pages")

    # -------------------------------------------------------------
    # Visual State & Spinner
    # -------------------------------------------------------------
    def _draw_eyes(self, color: str):
        self._stop_spinner()
        self.status_canvas.delete("all")
        self.status_canvas.create_oval(2, 2, 9, 13, outline=color, width=1)
        self.status_canvas.create_oval(4, 5, 7, 10, fill=color, outline="")
        self.status_canvas.create_oval(13, 2, 20, 13, outline=color, width=1)
        self.status_canvas.create_oval(15, 5, 18, 10, fill=color, outline="")

    def _start_spinner(self, color: str = C_AMBER):
        """Starts a subtle spinning progress indicator during AI inference."""
        self._spinner_running = True
        self._spinner_angle = 0
        self._animate_spinner(color)

    def _animate_spinner(self, color: str):
        if not self._spinner_running or not self.status_canvas:
            return
        self.status_canvas.delete("all")
        cx, cy, r = 11, 8, 6
        self.status_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#334155", width=1.5)
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

    # -------------------------------------------------------------
    # Drag & Positioning
    # -------------------------------------------------------------
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
        """Returns (left, top, right, bottom) bounding box for screen capture exclusion."""
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

    # -------------------------------------------------------------
    # Controls: Pin, Pause, Minimize
    # -------------------------------------------------------------
    def toggle_pin(self):
        """Toggles position pinning."""
        self.is_pinned = not self.is_pinned
        self.btn_pin.config(
            text="📌" if self.is_pinned else "📍",
            fg=C_EMERALD if self.is_pinned else C_TEXT_MUTED
        )
        logging.info("[HUD] Pin state changed: %s", self.is_pinned)

    def toggle_pause(self):
        """Toggles hover detection pause state."""
        if self.on_toggle_pause:
            self.is_paused = self.on_toggle_pause()
        else:
            self.is_paused = not self.is_paused

        self.btn_pause.config(
            text="⏸" if not self.is_paused else "▶",
            fg=C_EMERALD if not self.is_paused else C_AMBER
        )
        if self.is_paused:
            self.status_label.config(text="Hover Paused", fg=C_AMBER)
            self._draw_eyes(C_AMBER)
        elif self.phase == "ready":
            self.status_label.config(text="Ready", fg=C_EMERALD)
            self._draw_eyes(C_EMERALD)

    def toggle_minimize(self):
        """Switches between compact pill view and expanded scrollable view."""
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.viewport_container.pack_forget()
            self.footer.pack_forget()
            self.btn_min.config(text="⤢")
            compact_h = 34
            self.root.geometry(f"{self.width}x{compact_h}+{self.pos_x}+{self.pos_y}")
        else:
            self.btn_min.config(text="—")
            self.viewport_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            self.footer.pack(fill=tk.X, side=tk.BOTTOM)
            self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
            self.canvas.yview_moveto(0.0)

    def _on_toggle_audio(self):
        """Dispatches audio panel toggle callback."""
        if self.on_toggle_audio:
            self.on_toggle_audio()

    def update_audio_status(self, is_capturing: bool, is_paused: bool = False):
        """Updates the audio status indicator in HUD header."""
        def _update():
            if not hasattr(self, "btn_audio") or not self.btn_audio:
                return
            if is_capturing:
                if is_paused:
                    self.btn_audio.config(text="⏸️ 🎙️", fg=C_AMBER)
                else:
                    self.btn_audio.config(text="🔴 🎙️", fg=C_EMERALD)
            else:
                self.btn_audio.config(text="🎙️", fg=C_TEXT_MUTED)
        if self.root:
            if threading.current_thread() is threading.main_thread():
                _update()
            else:
                self.root.after(0, _update)


    # -------------------------------------------------------------
    # Clipboard Operations
    # -------------------------------------------------------------
    def copy_answer_to_clipboard(self):
        """Copies formatted answer and explanation to system clipboard."""
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
                self.btn_copy_ans.config(text="✓ Copied!", fg=C_EMERALD)
                self.root.after(1500, lambda: self.btn_copy_ans.config(text="📋 Copy Answer", fg=C_TEXT_PRIMARY))
            except Exception as e:
                logging.warning("[HUD] Clipboard copy failed: %s", e)

    def copy_code_to_clipboard(self):
        """Copies code snippet to system clipboard."""
        if not self.root or not self.current_code:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_code)
            self.btn_copy_code.config(text="✓ Code Copied!", fg=C_TEXT_PRIMARY)
            self.root.after(1500, lambda: self.btn_copy_code.config(text="💻 Copy Code", fg=C_EMERALD))
        except Exception as e:
            logging.warning("[HUD] Code copy failed: %s", e)

    def retry_solve(self):
        """Triggers registered solve retry callback."""
        if self.on_retry:
            try:
                self.btn_retry.config(text="🔄 Retrying...", fg=C_AMBER)
                if self.root:
                    self.root.after(1000, lambda: self.btn_retry.config(text="🔄 Retry", fg=C_TEXT_PRIMARY))
            except Exception:
                pass
            self.on_retry()

    def toggle_code_collapse(self):
        """Toggles expanding / collapsing of code block."""
        self.is_code_collapsed = not self.is_code_collapsed
        if self.is_code_collapsed:
            self.code_text_frame.pack_forget()
            self.code_scroll_x.pack_forget()
            self.btn_toggle_code.config(text="[+] Expand", fg=C_EMERALD)
        else:
            self.code_text_frame.pack(fill=tk.BOTH, expand=True)
            self.code_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            self.btn_toggle_code.config(text="[-] Collapse", fg=C_TEXT_MUTED)
        self._fit_window_to_content()

    def start_solve(self) -> int:
        """Starts a new solve cycle, returning unique solve_id to prevent stale responses."""
        self._current_solve_id += 1
        return self._current_solve_id

    # -------------------------------------------------------------
    # State Updates & Dedicated Scrollable Viewport Management
    # -------------------------------------------------------------
    def set_state(
        self,
        phase: str,
        text: str = "",
        badge: str = "",
        presentation: Optional[PresentedAnswer] = None,
        solve_id: Optional[int] = None
    ):
        """Thread-safe UI state update with stale update protection."""
        if not self.root:
            return
        if solve_id is not None and solve_id < self._current_solve_id:
            logging.debug("[HUD] Ignoring stale set_state: phase=%s, solve_id=%s, current=%s",
                          phase, solve_id, self._current_solve_id)
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

        # Restore sensible scroll position to top whenever state changes
        if self.canvas:
            self.canvas.yview_moveto(0.0)

        # Reset retry button styling to default
        self.btn_retry.config(text="🔄 Retry", fg=C_TEXT_PRIMARY)

        if phase == "ready":
            self._stop_spinner()
            self.status_label.config(text="Ready", fg=C_EMERALD if not self.is_paused else C_AMBER)
            self._draw_eyes(C_EMERALD if not self.is_paused else C_AMBER)
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

        # Handle answer, uncertain, or error states
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
        else:
            # Fallback path if presentation wasn't provided directly
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

        self.answer_badge = badge
        self.answer_text = headline
        self.raw_explanation = explanation
        self.current_code = code
        self.current_lang = lang

        if not is_valid or q_type in [TYPE_ERROR, TYPE_UNCERTAIN] or phase == "error":
            is_uncertain = (q_type == TYPE_UNCERTAIN or badge == "?")
            status_title = "Uncertain (?)" if is_uncertain else "Error (!)"
            color = C_AMBER if is_uncertain else C_DANGER
            self.status_label.config(text=status_title, fg=color)
            self._draw_eyes(color)

            if badge:
                self.badge_box.pack(side=tk.LEFT, padx=(0, 8))
                bg_err = "#3d2e05" if is_uncertain else "#3b1d1d"
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
            self._fit_window_to_content()

            if self.timeout_sec > 0 and self.root:
                self._dismiss_timer = self.root.after(int(self.timeout_sec * 1000), self.hide)
            return

        self.status_label.config(text="Answer Ready", fg=C_EMERALD)
        self._draw_eyes(C_EMERALD)

        if badge:
            self.badge_box.pack(side=tk.LEFT, padx=(0, 8))
            self.badge_box.config(bg=C_EMERALD_BG, highlightbackground=C_EMERALD)
            self.badge_label.config(text=badge, fg=C_EMERALD_TEXT, bg=C_EMERALD_BG)
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
                self.btn_toggle_code.config(text="[+] Expand", fg=C_EMERALD)
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

    def _set_explanation_text(self, text: str):
        """Populates selectable explanation text widget."""
        self.explanation_text.config(state=tk.NORMAL)
        self.explanation_text.delete("1.0", tk.END)
        if text.strip():
            self.explanation_text.insert("1.0", text.strip())
            # Calculate required line height
            line_count = int(self.explanation_text.index("end-1c").split(".")[0])
            self.explanation_text.config(height=max(2, min(14, line_count)))
            self.explanation_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 6))
        else:
            self.explanation_frame.pack_forget()
        self.explanation_text.config(state=tk.DISABLED)
        self._on_content_configure()

    def _fit_window_to_content(self):
        """Dynamically adjusts window height up to max_height, keeping header visible."""
        if not self.root or self.is_minimized:
            return
        self.root.update_idletasks()
        content_h = self.scrollable_content.winfo_reqheight()
        target_h = max(220, min(content_h + 75, self.max_height))
        if target_h != self.height:
            self.height = target_h
            self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def append_stream_token(self, token: str, solve_id: Optional[int] = None):
        """Appends streaming tokens from model generation in real time."""
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

    # -------------------------------------------------------------
    # Visibility & Lifecycle
    # -------------------------------------------------------------
    def show(self):
        if self.root:
            self.root.after(0, self._show_ui)

    def _show_ui(self):
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", self.always_on_top)
            # Re-assert HWND_TOPMOST via Win32 API without stealing keyboard focus
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

