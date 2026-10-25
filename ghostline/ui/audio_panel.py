"""
Ghostline — Live Audio & Transcript Assistant Panel.
100% Offline, Privacy-First Architecture with Stealth Dark Aesthetic.
Guaranteed Screen-Share Invisibility via WDA_EXCLUDEFROMCAPTURE.
"""

import os
import sys
import time
import ctypes
import logging
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, messagebox
from typing import Optional, Callable, Dict, Any, List, Tuple

from ghostline.audio.transcription import TranscriptSegment
from ghostline.ui.code_renderer import extract_code_and_prose, apply_syntax_highlighting
from ghostline.core.capture_exclusion import set_capture_exclusion

# Visual styling tokens: Stealth dark with emerald and sky cyan accents
C_BG_BASE = "#0f1117"        # Dark window canvas
C_BG_CARD = "#161b26"        # Surface container
C_BG_CARD_HOVER = "#1f2637"  # Hover card
C_BG_CODE = "#090d16"        # Code block deep background
C_BORDER_EMERALD = "#059669" # Emerald accent border
C_BORDER_MUTED = "#1e293b"   # Slate border
C_TEXT_PRIMARY = "#f8fafc"   # Clean bright white
C_TEXT_MUTED = "#94a3b8"     # Secondary slate
C_TEXT_DIM = "#64748b"       # Dim timestamp
C_EMERALD = "#10b981"        # Primary vibrant emerald accent
C_EMERALD_BG = "#064e3b"     # Badge container background
C_CYAN = "#38bdf8"           # Sky cyan for remote call audio
C_AMBER = "#f59e0b"          # Warning / thinking / pause
C_DANGER = "#f87171"         # Error text
C_REC = "#ef4444"            # Active recording bright red


class LiveAudioPanel:
    """
    Floating, stealth, draggable live transcription & AI assistance window.
    Features:
    - Guaranteed screen share invisibility: applies WDA_EXCLUDEFROMCAPTURE (Win10 2004+ / Win11)
    - Focus-free non-activating window: WS_EX_NOACTIVATE ensures video call / typing focus is never stolen
    - Dual-source live transcription display with distinct speaker labels ([Call] vs [You])
    - Partial vs finalized speech transcript distinctions
    - Real-time grounded AI answers from Ollama with code block extraction & copy button
    - Manual query input to ask questions about the ongoing conversation anytime
    - Pause, resume, toggle mic/loopback, clear, and export controls
    - Bounded memory auto-scrolling log
    """

    def __init__(
        self,
        on_start_capture: Optional[Callable[[], None]] = None,
        on_stop_capture: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], bool]] = None,
        on_toggle_call_audio: Optional[Callable[[bool], None]] = None,
        on_toggle_mic: Optional[Callable[[bool], None]] = None,
        on_ask_custom: Optional[Callable[[str], None]] = None,
        on_clear_transcript: Optional[Callable[[], None]] = None,
        on_export_transcript: Optional[Callable[[str], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        opacity: float = 0.95,
        width: int = 460,
        height: int = 560,
        always_on_top: bool = True,
        exclude_from_capture: bool = True,
        call_audio_enabled: bool = True,
        mic_enabled: bool = True
    ):
        self.on_start_capture = on_start_capture
        self.on_stop_capture = on_stop_capture
        self.on_toggle_pause = on_toggle_pause
        self.on_toggle_call_audio = on_toggle_call_audio
        self.on_toggle_mic = on_toggle_mic
        self.on_ask_custom = on_ask_custom
        self.on_clear_transcript = on_clear_transcript
        self.on_export_transcript = on_export_transcript
        self.on_close = on_close

        self.min_width = 420
        self.min_height = 500
        self.opacity = max(0.4, min(1.0, opacity))
        self.width = max(self.min_width, width if width >= 500 else 500)
        self.height = max(self.min_height, height if height >= 640 else 640)
        self.always_on_top = always_on_top
        self.exclude_from_capture = exclude_from_capture

        self.call_audio_enabled = call_audio_enabled
        self.mic_enabled = mic_enabled
        self.is_capturing = False
        self.is_paused = False
        self.is_minimized = False

        self.root: Optional[tk.Toplevel] = None
        self.hwnd: Optional[int] = None
        self.is_visible = False

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = 0
        self._resize_start_h = 0
        self.current_code_snippet: Optional[str] = None
        self.current_answer_text: str = ""

    def launch(self, parent: Optional[tk.Tk] = None, start_visible: bool = False):
        """Initializes the live audio panel as a Toplevel window."""
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Ghostline Live Audio Assistant")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.always_on_top)
        self.root.attributes("-alpha", self.opacity)

        # Positioning: top right near HUD or centered right
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        pos_x = max(20, sw - self.width - 30)
        pos_y = max(40, (sh - self.height) // 2)
        self.root.geometry(f"{self.width}x{self.height}+{pos_x}+{pos_y}")
        self.root.configure(bg=C_BG_BASE)

        # Fonts
        self.title_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.body_font = tkfont.Font(family="Segoe UI", size=9)
        self.kbd_font = tkfont.Font(family="Segoe UI", size=8)
        self.code_font = tkfont.Font(family="Consolas", size=9)
        self.tag_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")

        self._build_ui()

        # Keyboard shortcuts
        self.root.bind("<Escape>", lambda e: self.hide())

        # Win32 styles & Screen Share Invisibility
        self.root.update_idletasks()
        self._apply_win32_attributes()

        if start_visible:
            self.show()
        else:
            self.hide()

    def _apply_win32_attributes(self):
        """Applies WS_EX_NOACTIVATE (focus-free) and SetWindowDisplayAffinity (WDA_EXCLUDEFROMCAPTURE)."""
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
                    res, msg = set_capture_exclusion(self.hwnd, True)
                    logging.info("[AudioPanel] Capture exclusion applied (HWND=%s): %s", self.hwnd, msg)
        except Exception as e:
            logging.warning("[AudioPanel] Note applying Win32 attributes: %s", e)

    def _build_ui(self):
        # Outer Border with Emerald Accent
        self.outer_border = tk.Frame(self.root, bg=C_BORDER_EMERALD, bd=1)
        self.outer_border.pack(fill=tk.BOTH, expand=True)

        self.main_container = tk.Frame(self.outer_border, bg=C_BG_BASE)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # ------------------------------------------------------------------
        # 1. Header Bar (Draggable)
        # ------------------------------------------------------------------
        self.header = tk.Frame(self.main_container, bg=C_BG_CARD, height=32)
        self.header.pack(fill=tk.X, side=tk.TOP)
        self.header.pack_propagate(False)

        self.header.bind("<ButtonPress-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._on_drag)

        # Rec / Status indicator
        self.lbl_rec_indicator = tk.Label(
            self.header,
            text="⚪ IDLE",
            font=("Segoe UI", 8, "bold"),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        )
        self.lbl_rec_indicator.pack(side=tk.LEFT, padx=(8, 4), pady=6)
        self.lbl_rec_indicator.bind("<ButtonPress-1>", self._start_drag)
        self.lbl_rec_indicator.bind("<B1-Motion>", self._on_drag)

        self.lbl_title = tk.Label(
            self.header,
            text="Ghostline Live Audio",
            font=self.title_font,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD
        )
        self.lbl_title.pack(side=tk.LEFT, pady=6)
        self.lbl_title.bind("<ButtonPress-1>", self._start_drag)
        self.lbl_title.bind("<B1-Motion>", self._on_drag)

        # Close button
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
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.config(fg=C_DANGER))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.config(fg=C_TEXT_MUTED))

        # Minimize / Expand button
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

        # ------------------------------------------------------------------
        # 2. Control Quick-Bar
        # ------------------------------------------------------------------
        self.control_bar = tk.Frame(self.main_container, bg=C_BG_CARD, height=30)
        self.control_bar.pack(fill=tk.X, side=tk.TOP, pady=(1, 0))
        self.control_bar.pack_propagate(False)

        # Start / Stop Button
        self.btn_capture = tk.Button(
            self.control_bar,
            text="▶ Start",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg="#065f46",
            activebackground="#047857",
            activeforeground=C_TEXT_PRIMARY,
            bd=0,
            padx=8,
            cursor="hand2",
            command=self.toggle_capture
        )
        self.btn_capture.pack(side=tk.LEFT, padx=(6, 4), pady=4)

        # Pause / Resume Button
        self.btn_pause = tk.Button(
            self.control_bar,
            text="⏸ Pause",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg="#1e293b",
            activebackground="#334155",
            activeforeground=C_TEXT_PRIMARY,
            bd=0,
            padx=6,
            cursor="hand2",
            command=self.toggle_pause
        )
        self.btn_pause.pack(side=tk.LEFT, padx=2, pady=4)

        # Loopback Toggle Button
        self.btn_call = tk.Button(
            self.control_bar,
            text="🔊 Call: ON" if self.call_audio_enabled else "🔇 Call: OFF",
            font=self.kbd_font,
            fg=C_CYAN if self.call_audio_enabled else C_TEXT_MUTED,
            bg="#1e293b",
            activebackground="#334155",
            bd=0,
            padx=5,
            cursor="hand2",
            command=self.toggle_call_audio
        )
        self.btn_call.pack(side=tk.LEFT, padx=2, pady=4)

        # Mic Toggle Button
        self.btn_mic = tk.Button(
            self.control_bar,
            text="🎤 Mic: ON" if self.mic_enabled else "🎤 Mic: OFF",
            font=self.kbd_font,
            fg=C_EMERALD if self.mic_enabled else C_TEXT_MUTED,
            bg="#1e293b",
            activebackground="#334155",
            bd=0,
            padx=5,
            cursor="hand2",
            command=self.toggle_mic
        )
        self.btn_mic.pack(side=tk.LEFT, padx=2, pady=4)

        # Clear Button
        self.btn_clear = tk.Button(
            self.control_bar,
            text="🗑",
            font=self.kbd_font,
            fg=C_TEXT_MUTED,
            bg="#1e293b",
            activebackground="#334155",
            bd=0,
            padx=6,
            cursor="hand2",
            command=self.clear_transcript
        )
        self.btn_clear.pack(side=tk.RIGHT, padx=(2, 6), pady=4)

        # Export Button
        self.btn_export = tk.Button(
            self.control_bar,
            text="💾",
            font=self.kbd_font,
            fg=C_TEXT_MUTED,
            bg="#1e293b",
            activebackground="#334155",
            bd=0,
            padx=6,
            cursor="hand2",
            command=self.export_transcript
        )
        self.btn_export.pack(side=tk.RIGHT, padx=2, pady=4)

        # ------------------------------------------------------------------
        # 2.5 Live VU Level Meters & Audio Activity Indicator
        # ------------------------------------------------------------------
        self.meter_frame = tk.Frame(self.main_container, bg="#111827", height=24)
        self.meter_frame.pack(fill=tk.X, side=tk.TOP, padx=4, pady=(2, 0))
        self.meter_frame.pack_propagate(False)

        # Call Audio Meter (Cyan)
        self.lbl_meter_call = tk.Label(
            self.meter_frame,
            text="🔊 Call:",
            font=("Segoe UI", 7, "bold"),
            fg=C_CYAN,
            bg="#111827"
        )
        self.lbl_meter_call.pack(side=tk.LEFT, padx=(6, 2))

        self.canvas_meter_call = tk.Canvas(
            self.meter_frame,
            width=70,
            height=8,
            bg="#1e293b",
            highlightthickness=0,
            bd=0
        )
        self.canvas_meter_call.pack(side=tk.LEFT, padx=(0, 8), pady=8)

        # Mic Audio Meter (Emerald)
        self.lbl_meter_mic = tk.Label(
            self.meter_frame,
            text="🎤 Mic:",
            font=("Segoe UI", 7, "bold"),
            fg=C_EMERALD,
            bg="#111827"
        )
        self.lbl_meter_mic.pack(side=tk.LEFT, padx=(2, 2))

        self.canvas_meter_mic = tk.Canvas(
            self.meter_frame,
            width=70,
            height=8,
            bg="#1e293b",
            highlightthickness=0,
            bd=0
        )
        self.canvas_meter_mic.pack(side=tk.LEFT, padx=(0, 6), pady=8)

        # Activity Status Tag
        self.lbl_audio_activity = tk.Label(
            self.meter_frame,
            text="Idle",
            font=("Segoe UI", 7),
            fg=C_TEXT_MUTED,
            bg="#111827",
            anchor="e"
        )
        self.lbl_audio_activity.pack(side=tk.RIGHT, padx=(0, 6))

        # ------------------------------------------------------------------
        # 3. Footer Bar: Locked to Bottom (Custom Question Input + Resize Grip)
        # ------------------------------------------------------------------
        self.footer = tk.Frame(self.main_container, bg=C_BG_CARD, height=34)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM, padx=4, pady=(0, 4))
        self.footer.pack_propagate(False)

        # Corner resize grip handle (◢)
        self.grip_resize = tk.Label(
            self.footer,
            text="◢",
            font=("Segoe UI", 8),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            cursor="size_nw_se",
            padx=2,
            pady=2
        )
        self.grip_resize.pack(side=tk.RIGHT, padx=(2, 2))
        self.grip_resize.bind("<ButtonPress-1>", self._start_resize)
        self.grip_resize.bind("<B1-Motion>", self._on_resize)
        self.grip_resize.bind("<Enter>", lambda e: self.grip_resize.config(fg=C_EMERALD))
        self.grip_resize.bind("<Leave>", lambda e: self.grip_resize.config(fg=C_TEXT_MUTED))

        self.btn_ask = tk.Button(
            self.footer,
            text="Ask [Alt+Q]",
            font=self.kbd_font,
            fg=C_TEXT_PRIMARY,
            bg="#0284c7",
            activebackground="#0369a1",
            activeforeground=C_TEXT_PRIMARY,
            bd=0,
            padx=8,
            cursor="hand2",
            command=self._on_ask_button
        )
        self.btn_ask.pack(side=tk.RIGHT, padx=(2, 4), pady=4)

        self.entry_question = tk.Entry(
            self.footer,
            font=self.body_font,
            bg="#1e293b",
            fg=C_TEXT_PRIMARY,
            insertbackground=C_EMERALD,
            bd=0,
            relief=tk.FLAT
        )
        self.entry_question.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 4), pady=4)
        self.entry_question.insert(0, "Ask Ghostline about this conversation...")
        self.entry_question.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry_question.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry_question.bind("<Return>", lambda e: self._on_ask_button())

        # ------------------------------------------------------------------
        # 4. Central Vertical Split: Resizable PanedWindow
        # ------------------------------------------------------------------
        self.paned_container = tk.PanedWindow(
            self.main_container,
            orient=tk.VERTICAL,
            bg="#1e293b",
            bd=0,
            sashwidth=4,
            sashrelief=tk.FLAT,
            opaqueresize=True
        )
        self.paned_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 2))

        # Upper Pane: Live Transcript Text View (Scrollable & Non-clipping)
        self.transcript_frame = tk.Frame(self.paned_container, bg=C_BG_BASE)

        lbl_tr_title = tk.Label(
            self.transcript_frame,
            text="LIVE TRANSCRIPT (CALL & MICROPHONE)",
            font=("Segoe UI", 7, "bold"),
            fg=C_TEXT_MUTED,
            bg=C_BG_BASE,
            anchor="w"
        )
        lbl_tr_title.pack(fill=tk.X, padx=2, pady=(0, 2))

        tr_text_container = tk.Frame(self.transcript_frame, bg=C_BG_CARD, bd=1, highlightthickness=0)
        tr_text_container.pack(fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(tr_text_container, orient="vertical", width=8)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_transcript = tk.Text(
            tr_text_container,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            insertbackground=C_EMERALD,
            selectbackground="#064e3b",
            selectforeground=C_TEXT_PRIMARY,
            font=self.body_font,
            wrap=tk.WORD,
            bd=0,
            padx=6,
            pady=4,
            yscrollcommand=self.scrollbar.set
        )
        self.txt_transcript.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.txt_transcript.yview)
        self.txt_transcript.bind(
            "<MouseWheel>",
            lambda e: self.txt_transcript.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )

        # Text tags for transcript coloring
        self.txt_transcript.tag_configure("time", foreground=C_TEXT_DIM, font=("Consolas", 8))
        self.txt_transcript.tag_configure("call_tag", foreground=C_CYAN, font=("Segoe UI", 8, "bold"))
        self.txt_transcript.tag_configure("mic_tag", foreground=C_EMERALD, font=("Segoe UI", 8, "bold"))
        self.txt_transcript.tag_configure("final_text", foreground=C_TEXT_PRIMARY, font=self.body_font)
        self.txt_transcript.tag_configure("partial_text", foreground=C_TEXT_MUTED, font=("Segoe UI", 9, "italic"))

        self.paned_container.add(self.transcript_frame, height=220, minsize=130)

        # Lower Pane: AI Assistance Card with Dedicated Scrollable Answer View
        self.ai_card = tk.Frame(
            self.paned_container,
            bg=C_BG_CARD,
            bd=1,
            highlightbackground=C_BORDER_EMERALD,
            highlightthickness=1
        )

        ai_header = tk.Frame(self.ai_card, bg="#111827", height=24)
        ai_header.pack(fill=tk.X, side=tk.TOP)
        ai_header.pack_propagate(False)

        self.lbl_ai_status = tk.Label(
            ai_header,
            text="💡 GHOSTLINE AI ASSISTANT",
            font=("Segoe UI", 8, "bold"),
            fg=C_EMERALD,
            bg="#111827"
        )
        self.lbl_ai_status.pack(side=tk.LEFT, padx=6, pady=2)

        self.btn_copy_ans = tk.Label(
            ai_header,
            text="📋 Copy",
            font=self.kbd_font,
            fg=C_TEXT_MUTED,
            bg="#111827",
            cursor="hand2",
            padx=4
        )
        self.btn_copy_ans.pack(side=tk.RIGHT, padx=4)
        self.btn_copy_ans.bind("<Button-1>", lambda e: self.copy_answer())

        self.btn_copy_code = tk.Label(
            ai_header,
            text="📋 Copy Code",
            font=self.kbd_font,
            fg=C_CYAN,
            bg="#111827",
            cursor="hand2",
            padx=4
        )
        self.btn_copy_code.pack(side=tk.RIGHT, padx=2)
        self.btn_copy_code.bind("<Button-1>", lambda e: self.copy_code())

        # Detected Question / Topic line
        self.lbl_ai_question = tk.Label(
            self.ai_card,
            text="Awaiting question from call or manual inquiry...",
            font=("Segoe UI", 8, "italic"),
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            anchor="w",
            padx=6,
            pady=2
        )
        self.lbl_ai_question.pack(fill=tk.X)

        # Dedicated Scrollable Container for AI Answer (Eliminates clipping & allows long scrolling answers)
        ai_text_container = tk.Frame(self.ai_card, bg=C_BG_CARD, bd=0)
        ai_text_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.ai_scrollbar = tk.Scrollbar(ai_text_container, orient="vertical", width=8)
        self.ai_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_ai_answer = tk.Text(
            ai_text_container,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            insertbackground=C_EMERALD,
            selectbackground="#064e3b",
            selectforeground=C_TEXT_PRIMARY,
            font=self.body_font,
            wrap=tk.WORD,
            bd=0,
            padx=6,
            pady=4,
            yscrollcommand=self.ai_scrollbar.set
        )
        self.txt_ai_answer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ai_scrollbar.config(command=self.txt_ai_answer.yview)
        self.txt_ai_answer.bind(
            "<MouseWheel>",
            lambda e: self.txt_ai_answer.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )

        self.txt_ai_answer.tag_configure("code_block", font=self.code_font, background=C_BG_CODE, foreground="#38bdf8")
        self.txt_ai_answer.tag_configure("prose", font=self.body_font, foreground=C_TEXT_PRIMARY)
        self.txt_ai_answer.tag_configure("thinking", font=("Segoe UI", 9, "italic"), foreground=C_AMBER)

        self.paned_container.add(self.ai_card, height=280, minsize=180)

    # ----------------------------------------------------------------------
    # Event Handlers & Control Logic
    # ----------------------------------------------------------------------
    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        if self.is_minimized:
            return
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def _start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()

    def _on_resize(self, event):
        if self.is_minimized or not self.root:
            return
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        new_w = max(self.min_width, self._resize_start_w + dx)
        new_h = max(self.min_height, self._resize_start_h + dy)
        self.width = new_w
        self.height = new_h
        self.root.geometry(f"{new_w}x{new_h}")

    def _on_entry_focus_in(self, event):
        if self.entry_question.get() == "Ask Ghostline about this conversation...":
            self.entry_question.delete(0, tk.END)
            self.entry_question.config(fg=C_TEXT_PRIMARY)

    def _on_entry_focus_out(self, event):
        if not self.entry_question.get().strip():
            self.entry_question.insert(0, "Ask Ghostline about this conversation...")
            self.entry_question.config(fg=C_TEXT_MUTED)

    def _on_ask_button(self):
        query = self.entry_question.get().strip()
        if not query or query == "Ask Ghostline about this conversation...":
            return
        self.entry_question.delete(0, tk.END)
        self.set_ai_thinking(query)
        if self.on_ask_custom:
            self.on_ask_custom(query)

    def _dispatch(self, fn: Callable[[], None]):
        """Dispatches UI updates immediately if on main thread, or schedules via root.after(0) if on worker thread."""
        if not self.root:
            return
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            self.root.after(0, fn)

    def toggle_capture(self):
        """Toggles audio capture on/off."""
        if not self.is_capturing:
            if self.on_start_capture:
                self.on_start_capture()
        else:
            if self.on_stop_capture:
                self.on_stop_capture()

    def set_capture_state(self, is_capturing: bool):
        """Updates UI capture state."""
        def _update():
            self.is_capturing = is_capturing
            if is_capturing:
                self.btn_capture.config(text="⏹ Stop", bg="#991b1b")
                self.lbl_rec_indicator.config(text="🔴 REC 🎙️", fg=C_REC)
                if hasattr(self, "lbl_audio_activity"):
                    self.lbl_audio_activity.config(text="Listening...", fg=C_CYAN)
            else:
                self.btn_capture.config(text="▶ Start", bg="#065f46")
                self.lbl_rec_indicator.config(text="⚪ IDLE", fg=C_TEXT_MUTED)
                self.is_paused = False
                self.btn_pause.config(text="⏸ Pause")
                if hasattr(self, "lbl_audio_activity"):
                    self.lbl_audio_activity.config(text="Idle", fg=C_TEXT_MUTED)
                if hasattr(self, "canvas_meter_call"):
                    self.canvas_meter_call.delete("all")
                if hasattr(self, "canvas_meter_mic"):
                    self.canvas_meter_mic.delete("all")
        self._dispatch(_update)

    def update_level(self, source: str, rms: float, peak: float):
        """Updates live VU level meters and activity indicator with smooth visual response."""
        def _update():
            # Scale RMS: 0.0 to 0.05 mapped to 0-70px width (typical speaking RMS is 0.001 - 0.04)
            scaled = min(1.0, max(0.0, rms * 20.0))
            bar_w = int(scaled * 70)

            if source == "call":
                if hasattr(self, "canvas_meter_call") and self.canvas_meter_call.winfo_exists():
                    self.canvas_meter_call.delete("all")
                    if bar_w > 0:
                        self.canvas_meter_call.create_rectangle(0, 0, bar_w, 8, fill=C_CYAN, width=0)
            else: # mic
                if hasattr(self, "canvas_meter_mic") and self.canvas_meter_mic.winfo_exists():
                    self.canvas_meter_mic.delete("all")
                    if bar_w > 0:
                        col = C_EMERALD if scaled < 0.85 else C_AMBER
                        self.canvas_meter_mic.create_rectangle(0, 0, bar_w, 8, fill=col, width=0)

            if hasattr(self, "lbl_audio_activity") and self.lbl_audio_activity.winfo_exists():
                if rms > 0.0005:
                    src_name = "Call" if source == "call" else "Mic"
                    self.lbl_audio_activity.config(text=f"Active ({src_name})", fg=C_EMERALD)
                elif self.is_capturing and not self.is_paused:
                    self.lbl_audio_activity.config(text="Listening...", fg=C_CYAN)
        self._dispatch(_update)

    def toggle_pause(self):
        """Toggles pause/resume state."""
        if self.on_toggle_pause:
            paused = self.on_toggle_pause()
            self.set_pause_state(paused)

    def set_pause_state(self, is_paused: bool):
        def _update():
            self.is_paused = is_paused
            if is_paused:
                self.btn_pause.config(text="▶ Resume", bg="#854d0e")
                self.lbl_rec_indicator.config(text="⏸️ PAUSED", fg=C_AMBER)
                if hasattr(self, "lbl_audio_activity"):
                    self.lbl_audio_activity.config(text="Paused", fg=C_AMBER)
            else:
                self.btn_pause.config(text="⏸ Pause", bg="#1e293b")
                if self.is_capturing:
                    self.lbl_rec_indicator.config(text="🔴 REC 🎙️", fg=C_REC)
                    if hasattr(self, "lbl_audio_activity"):
                        self.lbl_audio_activity.config(text="Listening...", fg=C_CYAN)
        self._dispatch(_update)

    def toggle_call_audio(self):
        self.call_audio_enabled = not self.call_audio_enabled
        self.btn_call.config(
            text="🔊 Call: ON" if self.call_audio_enabled else "🔇 Call: OFF",
            fg=C_CYAN if self.call_audio_enabled else C_TEXT_MUTED
        )
        if self.on_toggle_call_audio:
            self.on_toggle_call_audio(self.call_audio_enabled)

    def toggle_mic(self):
        self.mic_enabled = not self.mic_enabled
        self.btn_mic.config(
            text="🎤 Mic: ON" if self.mic_enabled else "🎤 Mic: OFF",
            fg=C_EMERALD if self.mic_enabled else C_TEXT_MUTED
        )
        if self.on_toggle_mic:
            self.on_toggle_mic(self.mic_enabled)

    def clear_transcript(self):
        def _clear():
            self.txt_transcript.delete("1.0", tk.END)
            self.txt_ai_answer.delete("1.0", tk.END)
            self.lbl_ai_question.config(text="Awaiting question from call or manual inquiry...")
            if self.on_clear_transcript:
                self.on_clear_transcript()
        self._dispatch(_clear)


    def export_transcript(self):
        path = filedialog.asksaveasfilename(
            title="Export Call Transcript",
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("JSON File", "*.json")]
        )
        if path and self.on_export_transcript:
            self.on_export_transcript(path)
            messagebox.showinfo("Export Successful", f"Transcript exported to:\n{path}")

    def toggle_minimize(self):
        if not self.is_minimized:
            self.is_minimized = True
            self.control_bar.pack_forget()
            if hasattr(self, "meter_frame"):
                self.meter_frame.pack_forget()
            if hasattr(self, "paned_container"):
                self.paned_container.pack_forget()
            else:
                self.transcript_frame.pack_forget()
                self.ai_card.pack_forget()
            self.footer.pack_forget()
            self.root.geometry(f"{self.width}x34")
            self.btn_min.config(text="□")
        else:
            self.is_minimized = False
            self.control_bar.pack(fill=tk.X, side=tk.TOP, pady=(1, 0))
            if hasattr(self, "meter_frame"):
                self.meter_frame.pack(fill=tk.X, side=tk.TOP, padx=4, pady=(2, 0))
            self.footer.pack(fill=tk.X, side=tk.BOTTOM, padx=4, pady=(0, 4))
            if hasattr(self, "paned_container"):
                self.paned_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 2))
            else:
                self.transcript_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
                self.ai_card.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))
            self.root.geometry(f"{self.width}x{self.height}")
            self.btn_min.config(text="—")

    def show(self):
        if not self.root:
            return
        self.is_visible = True
        self.root.deiconify()
        self.root.lift()
        self._apply_win32_attributes()

    def hide(self):
        if not self.root:
            return
        self.is_visible = False
        self.root.withdraw()
        if self.on_close:
            self.on_close()

    def toggle_visibility(self):
        if self.is_visible:
            self.hide()
        else:
            self.show()

    # ----------------------------------------------------------------------
    # Live Transcript Callbacks (Thread-Safe)
    # ----------------------------------------------------------------------
    def append_final_segment(self, segment: TranscriptSegment):
        """Appends a finalized segment into the transcript box."""
        def _append():
            # Remove any trailing partial text first
            self._clear_partial()

            # Insert timestamp
            self.txt_transcript.insert(tk.END, f"[{segment.time_str}] ", "time")

            # Insert speaker label
            if segment.source == "call":
                self.txt_transcript.insert(tk.END, f"{segment.speaker_label} ", "call_tag")
            else:
                self.txt_transcript.insert(tk.END, f"{segment.speaker_label} ", "mic_tag")

            # Insert text
            self.txt_transcript.insert(tk.END, f"{segment.text}\n", "final_text")

            # Auto-scroll to end
            self.txt_transcript.see(tk.END)

        self._dispatch(_append)

    def update_partial(self, text: str, source: str = "call"):
        """Displays ongoing partial transcription preview."""
        def _update():
            self._clear_partial()
            if not text.strip():
                return
            tag = "[Call]" if source == "call" else "[You]"
            self.txt_transcript.insert(tk.END, f"… {tag} {text.strip()}", "partial_text")
            self.txt_transcript.see(tk.END)

        self._dispatch(_update)

    def _clear_partial(self):
        """Removes the partial line from the bottom of the transcript widget."""
        ranges = self.txt_transcript.tag_ranges("partial_text")
        if ranges:
            self.txt_transcript.delete(ranges[0], ranges[1])

    # ----------------------------------------------------------------------
    # Live AI Assistance Callbacks (Thread-Safe)
    # ----------------------------------------------------------------------
    def set_ai_thinking(self, question: str):
        """Displays thinking state for Ollama inference."""
        def _set():
            self.lbl_ai_status.config(text="💡 GHOSTLINE AI (THINKING…)", fg=C_AMBER)
            self.lbl_ai_question.config(
                text=f"Q: {question[:80]}{'…' if len(question) > 80 else ''}",
                fg=C_TEXT_PRIMARY
            )
            self.txt_ai_answer.delete("1.0", tk.END)
            self.txt_ai_answer.insert(tk.END, "Analyzing conversation context with Ollama…", "thinking")
        self._dispatch(_set)

    def set_ai_answer(self, question: str, answer_text: str, code_snippet: Optional[str] = None):
        """Renders grounded AI answer and code blocks."""
        def _set():
            self.lbl_ai_status.config(text="💡 GHOSTLINE AI (READY)", fg=C_EMERALD)
            self.lbl_ai_question.config(
                text=f"Q: {question[:80]}{'…' if len(question) > 80 else ''}",
                fg=C_CYAN
            )
            self.txt_ai_answer.delete("1.0", tk.END)
            self.current_answer_text = answer_text
            self.current_code_snippet = code_snippet

            prose, code, lang = extract_code_and_prose(answer_text)
            if code and not self.current_code_snippet:
                self.current_code_snippet = code

            if prose:
                self.txt_ai_answer.insert(tk.END, prose.strip() + "\n\n", "prose")

            if self.current_code_snippet:
                self.txt_ai_answer.insert(tk.END, "--- Code Snippet ---\n", "prose")
                self.txt_ai_answer.insert(tk.END, self.current_code_snippet.strip() + "\n", "code_block")
                self.btn_copy_code.config(state=tk.NORMAL)
            else:
                self.btn_copy_code.config(state=tk.DISABLED)

            self.txt_ai_answer.see("1.0")

        self._dispatch(_set)

    def set_ai_error(self, err_msg: str):
        """Displays recoverable AI error message."""
        def _set():
            self.lbl_ai_status.config(text="💡 GHOSTLINE AI (ERROR)", fg=C_DANGER)
            self.txt_ai_answer.delete("1.0", tk.END)
            self.txt_ai_answer.insert(tk.END, f"Inference Error: {err_msg}\nTranscription continues normally.", "thinking")
        self._dispatch(_set)


    def copy_answer(self):
        if not self.current_answer_text:
            return
        if self.root:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_answer_text)
            self.btn_copy_ans.config(text="✓ Copied!", fg=C_EMERALD)
            self.root.after(1500, lambda: self.btn_copy_ans.config(text="📋 Copy", fg=C_TEXT_MUTED))

    def copy_code(self):
        if not self.current_code_snippet:
            return
        if self.root:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_code_snippet)
            self.btn_copy_code.config(text="✓ Copied!", fg=C_EMERALD)
            self.root.after(1500, lambda: self.btn_copy_code.config(text="📋 Copy Code", fg=C_CYAN))

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, right, bottom) bounding rectangle of the audio panel window."""
        if not self.root or not self.is_visible:
            return None
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            return (x, y, x + w, y + h)
        except Exception:
            return None

    def destroy(self):
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None
