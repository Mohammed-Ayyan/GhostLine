"""
Ghostline — Simplified, Clean, Native Desktop Application Interface.
100% Offline, Privacy-First Architecture with Native Restrained Minimalist Aesthetic.
"""

import os
import sys
import json
import time
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from tkinter import messagebox
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple

from ghostline import __version__
from ghostline.config import AppConfig, save_config, get_app_dir, get_config_path

# Modern Restrained Minimalist Palette (Stealth Dark Theme)
C_BG_APP = "#0b0f17"          # Deep background canvas
C_BG_HEADER = "#111726"       # Header bar background
C_BG_CARD = "#161d2d"         # Surface card container
C_BG_CARD_HOVER = "#1f293d"   # Interactive card hover
C_BORDER = "#1e293b"          # Slate border
C_BORDER_ACCENT = "#059669"   # Emerald accent border
C_ACCENT = "#38bdf8"          # Sky cyan
C_SUCCESS = "#10b981"         # Vibrant emerald accent
C_EMERALD = "#10b981"         # Vibrant emerald accent
C_CYAN = "#38bdf8"            # Sky cyan
C_WARNING = "#f59e0b"         # Amber warning
C_AMBER = "#f59e0b"           # Amber
C_DANGER = "#ef4444"          # Red danger
C_TEXT_PRIMARY = "#f8fafc"    # Clean bright white
C_TEXT_SECONDARY = "#94a3b8"  # Slate secondary text
C_TEXT_MUTED = "#64748b"      # Muted slate text


class GhostlineMainWindow:
    """
    Radically simplified main desktop interface for Ghostline.
    Designed around one simple main screen:
    - Primary Action: Start / Stop
    - Screen Assistance: Capture screen and run OCR + answer pipeline
    - Audio Assistance: Start and stop microphone & system audio transcription
    - Live Activity: Small, readable area showing status, transcript, and latest result
    - Settings: Separate, minimal screen with collapsible Advanced section
    - Help / Diagnostics: One-click health check and setup problem resolution
    """

    def __init__(
        self,
        config: AppConfig,
        on_trigger_solve: Optional[Callable[[], None]] = None,
        on_settings_saved: Optional[Callable[[AppConfig], None]] = None,
        on_toggle_hud: Optional[Callable[[], None]] = None,
        on_test_caps: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        ollama_client: Optional[Any] = None,
        on_test_mic: Optional[Callable[..., Dict[str, Any]]] = None,
        on_test_loopback: Optional[Callable[..., Dict[str, Any]]] = None,
        on_test_transcription: Optional[Callable[[], Dict[str, Any]]] = None,
        get_audio_diagnostics: Optional[Callable[[], Dict[str, Any]]] = None,
        on_toggle_audio: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.on_trigger_solve = on_trigger_solve
        self.on_settings_saved = on_settings_saved
        self.on_toggle_hud = on_toggle_hud
        self.on_test_caps = on_test_caps
        self.on_exit = on_exit
        self.ollama_client = ollama_client
        self.on_test_mic = on_test_mic
        self.on_test_loopback = on_test_loopback
        self.on_test_transcription = on_test_transcription
        self.get_audio_diagnostics = get_audio_diagnostics
        self.on_toggle_audio = on_toggle_audio

        self.root: Optional[tk.Tk] = None
        self.current_screen = "main"
        self.screen_frames: Dict[str, tk.Frame] = {}
        self.nav_buttons: Dict[str, tk.Label] = {}
        self.last_result: Optional[Any] = None
        self._is_minimized_to_tray = False

        # State flags
        self.is_ghostline_active = True
        self.is_audio_active = False
        self.show_advanced_settings = False

        # Backward compatibility for history inspection and tests
        self.history_records: List[Dict[str, Any]] = []
        self.history_path = get_app_dir() / "history.jsonl"
        self.hist_search_var = tk.StringVar(value="") if tk._default_root else None
        self.hist_listbox = None

    @property
    def _history_entries(self) -> List[Dict[str, Any]]:
        return self.history_records

    @_history_entries.setter
    def _history_entries(self, val: List[Dict[str, Any]]):
        self.history_records = val

    def build(self) -> tk.Tk:
        """Constructs and returns the main Tk window."""
        self.root = tk.Tk()
        self.root.title("Ghostline — Offline AI Assistant")
        self.root.geometry("620x680")
        self.root.minsize(540, 560)
        self.root.configure(bg=C_BG_APP)

        # Set App Icon if present
        for cand in [
            Path(__file__).resolve().parent.parent.parent / "ghostline.ico",
            Path(getattr(sys, "_MEIPASS", "")) / "ghostline.ico",
        ]:
            if cand.exists():
                try:
                    self.root.iconbitmap(str(cand))
                    break
                except Exception:
                    pass

        # Close button minimizes to tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Escape>", lambda e: self.hide_to_tray())

        # Fonts
        self.font_logo = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.font_h2 = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.font_body = tkfont.Font(family="Segoe UI", size=9)
        self.font_body_bold = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_code = tkfont.Font(family="Consolas", size=9)
        self.font_badge = tkfont.Font(family="Segoe UI", size=24, weight="bold")
        self.font_sm = tkfont.Font(family="Segoe UI", size=8)

        # Ensure StringVar initialized
        if self.hist_search_var is None:
            self.hist_search_var = tk.StringVar(value="")

        # Build Header & Tab Container
        self._build_header()
        self._build_content_area()

        self.ans_badge_label = self.lbl_badge
        self.ans_option_text_lbl = self.lbl_result_headline

        # Handle start minimized
        if getattr(self.config, "start_minimized", False):
            self.root.withdraw()
            self._is_minimized_to_tray = True
        else:
            self.show_screen("dashboard")

        return self.root

    def _build_header(self):
        """Builds clean top navigation bar."""
        header = tk.Frame(self.root, bg=C_BG_HEADER, height=52)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # Left: App Brand & Status Dot
        left_box = tk.Frame(header, bg=C_BG_HEADER)
        left_box.pack(side=tk.LEFT, padx=16, pady=10)

        self.lbl_status_dot = tk.Label(
            left_box,
            text="●",
            font=("Segoe UI", 12),
            fg=C_SUCCESS,
            bg=C_BG_HEADER
        )
        self.lbl_status_dot.pack(side=tk.LEFT, padx=(0, 6))

        lbl_brand = tk.Label(
            left_box,
            text="Ghostline",
            font=self.font_logo,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_HEADER
        )
        lbl_brand.pack(side=tk.LEFT)

        self.lbl_header_state = tk.Label(
            left_box,
            text="Ready (Alt+/)",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_HEADER
        )
        self.lbl_header_state.pack(side=tk.LEFT, padx=(8, 0))

        # Right: Clean Tabs (Main | Settings | Help & Diagnostics)
        nav_box = tk.Frame(header, bg=C_BG_HEADER)
        nav_box.pack(side=tk.RIGHT, padx=12, pady=10)

        tabs = [
            ("main", "Main"),
            ("settings", "Settings"),
            ("diagnostics", "Help & Diagnostics"),
        ]

        for screen_id, label in tabs:
            btn = tk.Label(
                nav_box,
                text=label,
                font=self.font_body_bold,
                fg=C_TEXT_SECONDARY,
                bg=C_BG_HEADER,
                padx=10,
                pady=4,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=2)
            btn.bind("<Button-1>", lambda e, s=screen_id: self.show_screen(s))
            self.nav_buttons[screen_id] = btn

    def _build_content_area(self):
        """Constructs content container and registers screens."""
        self.container = tk.Frame(self.root, bg=C_BG_APP)
        self.container.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        # 1. Main Screen
        self.screen_frames["main"] = self._build_screen_main(self.container)

        # 2. Settings Screen
        self.screen_frames["settings"] = self._build_screen_settings(self.container)

        # 3. Help / Diagnostics Screen
        self.screen_frames["diagnostics"] = self._build_screen_diagnostics(self.container)

        # Aliases for backward-compatibility with tests and older URLs
        self.screen_frames["dashboard"] = self.screen_frames["main"]
        self.screen_frames["answer"] = self.screen_frames["main"]
        self.screen_frames["history"] = self.screen_frames["main"]
        self.screen_frames["setup"] = self.screen_frames["diagnostics"]
        self.screen_frames["about"] = self.screen_frames["diagnostics"]

    # ------------------------------------------------------------------
    # 1. The Simple Main Screen
    # ------------------------------------------------------------------
    def _build_screen_main(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=C_BG_APP)

        # --------------------------------------------------------------
        # Section 1: Primary Action (Start / Stop)
        # --------------------------------------------------------------
        action_card = tk.Frame(frame, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        action_card.pack(fill=tk.X, pady=(0, 10), padx=2)

        action_inner = tk.Frame(action_card, bg=C_BG_CARD, padx=14, pady=12)
        action_inner.pack(fill=tk.X)

        self.btn_primary_toggle = tk.Button(
            action_inner,
            text="▶ Ghostline Active",
            font=self.font_h2,
            fg="#ffffff",
            bg="#065f46",
            activebackground="#047857",
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=10,
            cursor="hand2",
            command=self._toggle_ghostline_active
        )
        self.btn_primary_toggle.pack(fill=tk.X)

        self.lbl_primary_hint = tk.Label(
            action_inner,
            text="Global Hotkey Alt + / is active • Hover cursor over question and press to solve",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD
        )
        self.lbl_primary_hint.pack(pady=(6, 0))

        # --------------------------------------------------------------
        # Section 2: Assistance Modes (Screen Assistance & Audio Assistance)
        # --------------------------------------------------------------
        modes_row = tk.Frame(frame, bg=C_BG_APP)
        modes_row.pack(fill=tk.X, pady=(0, 10))

        # Left Card: Screen Assistance
        scr_card = tk.Frame(modes_row, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        scr_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        scr_inner = tk.Frame(scr_card, bg=C_BG_CARD, padx=12, pady=10)
        scr_inner.pack(fill=tk.BOTH, expand=True)

        scr_header = tk.Frame(scr_inner, bg=C_BG_CARD)
        scr_header.pack(fill=tk.X)

        tk.Label(
            scr_header,
            text="⚡ Screen Assistance",
            font=self.font_body_bold,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD
        ).pack(side=tk.LEFT)

        self.lbl_scr_badge = tk.Label(
            scr_header,
            text="Ready (Alt+/)",
            font=self.font_sm,
            fg=C_SUCCESS,
            bg="#064e3b",
            padx=6,
            pady=1
        )
        self.lbl_scr_badge.pack(side=tk.RIGHT)

        tk.Label(
            scr_inner,
            text="Reads on-screen questions & displays answers instantly.",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            anchor="w",
            justify=tk.LEFT
        ).pack(fill=tk.X, pady=(4, 8))

        self.btn_scr_action = tk.Button(
            scr_inner,
            text="Capture Screen Now [Alt+/]",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#0284c7",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._on_solve_clicked
        )
        self.btn_scr_action.pack(fill=tk.X)

        # Right Card: Audio Assistance
        aud_card = tk.Frame(modes_row, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        aud_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        aud_inner = tk.Frame(aud_card, bg=C_BG_CARD, padx=12, pady=10)
        aud_inner.pack(fill=tk.BOTH, expand=True)

        aud_header = tk.Frame(aud_inner, bg=C_BG_CARD)
        aud_header.pack(fill=tk.X)

        tk.Label(
            aud_header,
            text="🎙️ Audio Assistance",
            font=self.font_body_bold,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD
        ).pack(side=tk.LEFT)

        self.lbl_aud_badge = tk.Label(
            aud_header,
            text="Idle",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg="#1e293b",
            padx=6,
            pady=1
        )
        self.lbl_aud_badge.pack(side=tk.RIGHT)

        tk.Label(
            aud_inner,
            text="Transcribes live speech from microphone & video calls.",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            anchor="w",
            justify=tk.LEFT
        ).pack(fill=tk.X, pady=(4, 8))

        self.btn_aud_action = tk.Button(
            aud_inner,
            text="Open Audio HUD",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#4338ca",
            activebackground="#3730a3",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._on_toggle_audio_clicked
        )
        self.btn_aud_action.pack(fill=tk.X)

        # --------------------------------------------------------------
        # Section 3: Live Activity & Latest Result
        # --------------------------------------------------------------
        act_card = tk.Frame(frame, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        act_card.pack(fill=tk.BOTH, expand=True, padx=2)

        act_header = tk.Frame(act_card, bg="#111827", height=28)
        act_header.pack(fill=tk.X, side=tk.TOP)
        act_header.pack_propagate(False)

        tk.Label(
            act_header,
            text="LIVE ACTIVITY",
            font=("Segoe UI", 8, "bold"),
            fg=C_TEXT_SECONDARY,
            bg="#111827"
        ).pack(side=tk.LEFT, padx=10, pady=4)

        self.lbl_act_stage = tk.Label(
            act_header,
            text="READY",
            font=("Segoe UI", 8, "bold"),
            fg=C_SUCCESS,
            bg="#111827"
        )
        self.lbl_act_stage.pack(side=tk.RIGHT, padx=10, pady=4)

        # Result Body
        result_box = tk.Frame(act_card, bg=C_BG_CARD, padx=12, pady=10)
        result_box.pack(fill=tk.BOTH, expand=True)

        # Top line: Badge + Headline + Copy Button
        badge_row = tk.Frame(result_box, bg=C_BG_CARD)
        badge_row.pack(fill=tk.X, pady=(0, 6))

        self.lbl_badge = tk.Label(
            badge_row,
            text="?",
            font=self.font_badge,
            fg=C_TEXT_MUTED,
            bg="#111827",
            width=3,
            pady=2
        )
        self.lbl_badge.pack(side=tk.LEFT, padx=(0, 10))

        headline_box = tk.Frame(badge_row, bg=C_BG_CARD)
        headline_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.lbl_result_headline = tk.Label(
            headline_box,
            text="Awaiting question capture...",
            font=self.font_body_bold,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD,
            anchor="w"
        )
        self.lbl_result_headline.pack(fill=tk.X)

        self.lbl_result_meta = tk.Label(
            headline_box,
            text="Press Alt + / over any question to solve instantly.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            anchor="w"
        )
        self.lbl_result_meta.pack(fill=tk.X, pady=(2, 0))

        self.btn_copy_answer = tk.Button(
            badge_row,
            text="📋 Copy",
            font=self.font_sm,
            fg=C_TEXT_PRIMARY,
            bg="#1e293b",
            activebackground="#334155",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._copy_answer_to_clipboard
        )
        self.btn_copy_answer.pack(side=tk.RIGHT)

        # Detailed Question & Answer Text Box
        self.txt_result_details = tk.Text(
            result_box,
            bg="#0f141f",
            fg=C_TEXT_PRIMARY,
            font=self.font_body,
            wrap=tk.WORD,
            bd=0,
            padx=8,
            pady=6,
            height=6
        )
        self.txt_result_details.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.txt_result_details.insert("1.0", "When you press Alt + /, the captured question text, confirmed answer, and explanation will appear here.")
        self.txt_result_details.configure(state="disabled")

        # Audio transcript preview line
        self.lbl_transcript_preview = tk.Label(
            act_card,
            text="Audio: Idle",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            anchor="w",
            padx=12,
            pady=4
        )
        self.lbl_transcript_preview.pack(fill=tk.X, side=tk.BOTTOM)

        return frame

    # ------------------------------------------------------------------
    # 2. Minimal Settings Screen
    # ------------------------------------------------------------------
    def _build_screen_settings(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=C_BG_APP)

        card = tk.Frame(frame, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=2)

        content = tk.Frame(card, bg=C_BG_CARD, padx=16, pady=14)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="Essential Configuration",
            font=self.font_h2,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(0, 12))

        # Model Selection
        tk.Label(content, text="Reasoning AI Model (Ollama):", font=self.font_body_bold, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.var_model = tk.StringVar(value=getattr(self.config, "model_name", "phi3:mini"))
        models_combo = ttk.Combobox(
            content,
            textvariable=self.var_model,
            values=["phi3:mini", "llama3.2:3b", "llama3.2:1b", "mistral:7b", "qwen2.5-coder:3b"],
            state="readonly",
            font=self.font_body
        )
        models_combo.pack(fill=tk.X, pady=(4, 12))

        # Capture Mode
        tk.Label(content, text="Screen Capture Area:", font=self.font_body_bold, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w")
        self.var_capture_mode = tk.StringVar(value=getattr(self.config, "capture_mode", "full_screen"))
        capture_combo = ttk.Combobox(
            content,
            textvariable=self.var_capture_mode,
            values=["full_screen", "cursor_monitor", "active_window", "cursor"],
            state="readonly",
            font=self.font_body
        )
        capture_combo.pack(fill=tk.X, pady=(4, 12))

        # HUD Toggle
        self.var_show_hud = tk.BooleanVar(value=getattr(self.config, "show_hud_on_solve", True))
        chk_hud = tk.Checkbutton(
            content,
            text="Display floating stealth answer HUD on screen",
            variable=self.var_show_hud,
            font=self.font_body,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD,
            selectcolor="#0f141f",
            activebackground=C_BG_CARD,
            activeforeground=C_TEXT_PRIMARY,
            bd=0
        )
        chk_hud.pack(anchor="w", pady=(2, 6))

        # Audio Toggles
        self.var_audio_mic = tk.BooleanVar(value=getattr(self.config, "audio_source_mic", True))
        chk_mic = tk.Checkbutton(
            content,
            text="Capture Microphone (You)",
            variable=self.var_audio_mic,
            font=self.font_body,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD,
            selectcolor="#0f141f",
            activebackground=C_BG_CARD,
            activeforeground=C_TEXT_PRIMARY,
            bd=0
        )
        chk_mic.pack(anchor="w", pady=(2, 6))

        self.var_audio_sys = tk.BooleanVar(value=getattr(self.config, "audio_source_system", True))
        chk_sys = tk.Checkbutton(
            content,
            text="Capture System Audio / Video Calls (Call)",
            variable=self.var_audio_sys,
            font=self.font_body,
            fg=C_TEXT_PRIMARY,
            bg=C_BG_CARD,
            selectcolor="#0f141f",
            activebackground=C_BG_CARD,
            activeforeground=C_TEXT_PRIMARY,
            bd=0
        )
        chk_sys.pack(anchor="w", pady=(2, 12))

        # Collapsible Advanced Section
        self.btn_toggle_adv = tk.Label(
            content,
            text="▶ Advanced Settings (Optional)",
            font=self.font_body_bold,
            fg=C_ACCENT,
            bg=C_BG_CARD,
            cursor="hand2"
        )
        self.btn_toggle_adv.pack(anchor="w", pady=(4, 8))
        self.btn_toggle_adv.bind("<Button-1>", lambda e: self._toggle_advanced_settings())

        self.adv_container = tk.Frame(content, bg=C_BG_CARD)

        # Advanced fields
        tk.Label(self.adv_container, text="Ollama Endpoint URL:", font=self.font_sm, fg=C_TEXT_SECONDARY, bg=C_BG_CARD).pack(anchor="w")
        self.entry_ollama_url = tk.Entry(self.adv_container, font=self.font_body, bg="#0f141f", fg=C_TEXT_PRIMARY, bd=1, relief=tk.FLAT)
        self.entry_ollama_url.insert(0, getattr(self.config, "ollama_url", "http://127.0.0.1:11434"))
        self.entry_ollama_url.pack(fill=tk.X, pady=(2, 6))

        self.var_auto_copy = tk.BooleanVar(value=getattr(self.config, "auto_copy_answer", False))
        tk.Checkbutton(
            self.adv_container,
            text="Auto-copy verified answer letter to clipboard",
            variable=self.var_auto_copy,
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            selectcolor="#0f141f",
            activebackground=C_BG_CARD,
            bd=0
        ).pack(anchor="w", pady=2)

        self.var_start_min = tk.BooleanVar(value=getattr(self.config, "start_minimized", False))
        tk.Checkbutton(
            self.adv_container,
            text="Start minimized to Windows notification tray",
            variable=self.var_start_min,
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            selectcolor="#0f141f",
            activebackground=C_BG_CARD,
            bd=0
        ).pack(anchor="w", pady=2)

        self.var_caps_pulse = tk.BooleanVar(value=getattr(self.config, "caps_lock_indicator", False))
        tk.Checkbutton(
            self.adv_container,
            text="Pulse Caps Lock LED on answer (Stealth hardware indicator)",
            variable=self.var_caps_pulse,
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            selectcolor="#0f141f",
            activebackground=C_BG_CARD,
            bd=0
        ).pack(anchor="w", pady=2)

        # Save Button
        btn_box = tk.Frame(content, bg=C_BG_CARD)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))

        btn_save = tk.Button(
            btn_box,
            text="Save Settings",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#065f46",
            activebackground="#047857",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._save_settings
        )
        btn_save.pack(side=tk.LEFT)

        return frame

    def _toggle_advanced_settings(self):
        self.show_advanced_settings = not self.show_advanced_settings
        if self.show_advanced_settings:
            self.adv_container.pack(fill=tk.X, pady=(0, 10))
            self.btn_toggle_adv.config(text="▼ Hide Advanced Settings")
        else:
            self.adv_container.pack_forget()
            self.btn_toggle_adv.config(text="▶ Advanced Settings (Optional)")

    def _save_settings(self):
        self.config.model_name = self.var_model.get()
        self.config.capture_mode = self.var_capture_mode.get()
        self.config.show_hud_on_solve = self.var_show_hud.get()
        self.config.audio_source_mic = self.var_audio_mic.get()
        self.config.audio_source_system = self.var_audio_sys.get()

        if hasattr(self, "entry_ollama_url") and self.entry_ollama_url.get().strip():
            self.config.ollama_url = self.entry_ollama_url.get().strip()
        self.config.auto_copy_answer = self.var_auto_copy.get()
        self.config.start_minimized = self.var_start_min.get()
        self.config.caps_lock_indicator = self.var_caps_pulse.get()

        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)
        messagebox.showinfo("Settings Saved", "Ghostline settings updated successfully.")
        self.show_screen("main")

    # ------------------------------------------------------------------
    # 3. Help & Diagnostics Screen
    # ------------------------------------------------------------------
    def _build_screen_diagnostics(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=C_BG_APP)

        card = tk.Frame(frame, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=2)

        content = tk.Frame(card, bg=C_BG_CARD, padx=16, pady=12)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="System Setup & Diagnostics", font=self.font_h2, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w", pady=(0, 8))

        # Checklist
        chk_box = tk.Frame(content, bg="#111827", padx=12, pady=10)
        chk_box.pack(fill=tk.X, pady=(0, 10))

        self.lbl_diag_ollama = tk.Label(chk_box, text="● Checking Ollama...", font=self.font_body, fg=C_TEXT_SECONDARY, bg="#111827", anchor="w")
        self.lbl_diag_ollama.pack(fill=tk.X, pady=2)

        self.lbl_diag_model = tk.Label(chk_box, text="● Checking Model...", font=self.font_body, fg=C_TEXT_SECONDARY, bg="#111827", anchor="w")
        self.lbl_diag_model.pack(fill=tk.X, pady=2)

        self.lbl_diag_ocr = tk.Label(chk_box, text="● Windows Native OCR: Ready", font=self.font_body, fg=C_SUCCESS, bg="#111827", anchor="w")
        self.lbl_diag_ocr.pack(fill=tk.X, pady=2)

        self.lbl_diag_audio = tk.Label(chk_box, text="● Windows Audio Subsystem: Ready", font=self.font_body, fg=C_SUCCESS, bg="#111827", anchor="w")
        self.lbl_diag_audio.pack(fill=tk.X, pady=2)

        # Test Action Buttons
        btn_bar = tk.Frame(content, bg=C_BG_CARD)
        btn_bar.pack(fill=tk.X, pady=(0, 10))

        self.btn_test_mic = tk.Button(
            btn_bar,
            text="🎤 Test Mic",
            font=self.font_sm,
            fg="#ffffff",
            bg="#065f46",
            activebackground="#047857",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self._run_test_mic
        )
        self.btn_test_mic.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_test_sys = tk.Button(
            btn_bar,
            text="🔊 Test System Audio",
            font=self.font_sm,
            fg="#ffffff",
            bg="#0284c7",
            activebackground="#0369a1",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self._run_test_loopback
        )
        self.btn_test_sys.pack(side=tk.LEFT, padx=6)

        self.btn_test_trans = tk.Button(
            btn_bar,
            text="⚡ Test Transcription",
            font=self.font_sm,
            fg="#ffffff",
            bg="#4338ca",
            activebackground="#3730a3",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self._run_test_transcription
        )
        self.btn_test_trans.pack(side=tk.LEFT, padx=6)

        btn_refresh = tk.Button(
            btn_bar,
            text="🔄 Refresh",
            font=self.font_sm,
            fg=C_TEXT_PRIMARY,
            bg="#1e293b",
            activebackground="#334155",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self._check_system_health
        )
        btn_refresh.pack(side=tk.RIGHT)

        # Output Text Box
        self.txt_diag_output = tk.Text(
            content,
            bg="#0f141f",
            fg=C_TEXT_PRIMARY,
            font=self.font_code,
            wrap=tk.WORD,
            bd=0,
            padx=8,
            pady=6,
            height=10
        )
        self.txt_diag_output.pack(fill=tk.BOTH, expand=True)

        return frame

    def _check_system_health(self):
        """Verifies local dependencies and displays actionable fix steps."""
        self.txt_diag_output.delete("1.0", tk.END)
        self.txt_diag_output.insert(tk.END, "Running Ghostline System Check...\n\n")

        # 1. Ollama status
        ollama_ok = False
        models = []
        if self.ollama_client:
            ollama_ok, models = self.ollama_client.check_health()

        if ollama_ok:
            self.lbl_diag_ollama.config(text=f"● Ollama Engine: Running ({self.config.ollama_url})", fg=C_SUCCESS)
            self.txt_diag_output.insert(tk.END, f"[✓] Ollama is running and responding at {self.config.ollama_url}\n")
        else:
            self.lbl_diag_ollama.config(text=f"✗ Ollama Engine: Not Running", fg=C_DANGER)
            self.txt_diag_output.insert(
                tk.END,
                f"[✗] Ollama not found at {self.config.ollama_url}\n"
                f"    Fix: Download and install Ollama from https://ollama.com\n"
                f"    Then launch Ollama and verify it is running in your taskbar.\n\n"
            )

        # 2. Model status
        target_model = getattr(self.config, "model_name", "phi3:mini")
        has_model = any(target_model in m for m in models)
        if has_model:
            self.lbl_diag_model.config(text=f"● AI Model: '{target_model}' Ready", fg=C_SUCCESS)
            self.txt_diag_output.insert(tk.END, f"[✓] AI model '{target_model}' is installed locally.\n")
        else:
            self.lbl_diag_model.config(text=f"✗ AI Model: '{target_model}' Missing", fg=C_WARNING)
            self.txt_diag_output.insert(
                tk.END,
                f"[!] AI model '{target_model}' is not pulled yet.\n"
                f"    Fix: Open Windows Terminal or Command Prompt and run:\n"
                f"         ollama pull {target_model}\n\n"
            )

        # 3. OCR Status
        from ghostline.core.ocr_engine import get_win_ocr_binary_path
        ocr_path = get_win_ocr_binary_path()
        if ocr_path.exists():
            self.lbl_diag_ocr.config(text=f"● Windows Native OCR: Ready", fg=C_SUCCESS)
            self.txt_diag_output.insert(tk.END, f"[✓] Windows OCR engine found at: {ocr_path}\n")
        else:
            self.lbl_diag_ocr.config(text=f"✗ Windows OCR: Binary Missing", fg=C_DANGER)
            self.txt_diag_output.insert(tk.END, f"[✗] OCR binary missing at: {ocr_path}\n")

    # ------------------------------------------------------------------
    # Diagnostic Button Actions
    # ------------------------------------------------------------------
    def _run_test_mic(self):
        if not self.on_test_mic:
            messagebox.showinfo("Test", "Microphone test callback not available.")
            return
        self.btn_test_mic.config(text="Listening (3s)...", bg="#047857")
        self.txt_diag_output.insert(tk.END, "\n[Test] Listening to microphone for 3 seconds... Please speak.\n")

        def _worker():
            try:
                res = self.on_test_mic(duration_sec=3.0, update_fn=self.update_audio_level)
                def _done():
                    self.btn_test_mic.config(text="🎤 Test Mic", bg="#065f46")
                    msg = res.get("message", "Completed")
                    self.txt_diag_output.insert(tk.END, f"Microphone Test Result:\n{msg}\n")
                if self.root:
                    self.root.after(0, _done)
            except Exception as e:
                if self.root:
                    self.root.after(0, lambda: self.txt_diag_output.insert(tk.END, f"Mic Test Error: {e}\n"))

        threading.Thread(target=_worker, daemon=True).start()

    def _run_test_loopback(self):
        if not self.on_test_loopback:
            messagebox.showinfo("Test", "Loopback test callback not available.")
            return
        self.btn_test_sys.config(text="Capturing (3s)...", bg="#0369a1")
        self.txt_diag_output.insert(tk.END, "\n[Test] Capturing loopback for 3s... (Play YouTube or sound now)\n")

        def _worker():
            try:
                res = self.on_test_loopback(duration_sec=3.0, update_fn=self.update_audio_level)
                def _done():
                    self.btn_test_sys.config(text="🔊 Test System Audio", bg="#0284c7")
                    msg = res.get("message", "Completed")
                    self.txt_diag_output.insert(tk.END, f"System Audio Loopback Result:\n{msg}\n")
                if self.root:
                    self.root.after(0, _done)
            except Exception as e:
                if self.root:
                    self.root.after(0, lambda: self.txt_diag_output.insert(tk.END, f"Loopback Test Error: {e}\n"))

        threading.Thread(target=_worker, daemon=True).start()

    def _run_test_transcription(self):
        if not self.on_test_transcription:
            messagebox.showinfo("Test", "Transcription test callback not available.")
            return
        self.btn_test_trans.config(text="Testing...", bg="#3730a3")
        self.txt_diag_output.insert(tk.END, "\n[Test] Running local transcription engine benchmark...\n")

        def _worker():
            try:
                res = self.on_test_transcription()
                def _done():
                    self.btn_test_trans.config(text="⚡ Test Transcription", bg="#4338ca")
                    msg = res.get("message", res.get("text", "Completed"))
                    self.txt_diag_output.insert(tk.END, f"Transcription Result:\n{msg}\n")
                if self.root:
                    self.root.after(0, _done)
            except Exception as e:
                if self.root:
                    self.root.after(0, lambda: self.txt_diag_output.insert(tk.END, f"Transcription Test Error: {e}\n"))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # State Management & Navigation
    # ------------------------------------------------------------------
    def show_screen(self, screen_id: str):
        """Switches active view and updates tab highlight."""
        target_id = screen_id if screen_id in self.screen_frames else "main"
        self.current_screen = screen_id

        for s_id, f in self.screen_frames.items():
            f.pack_forget()

        self.screen_frames[target_id].pack(fill=tk.BOTH, expand=True)

        # Update tab highlights
        for b_id, btn in self.nav_buttons.items():
            if b_id == target_id:
                btn.config(fg=C_TEXT_PRIMARY, bg=C_BG_CARD)
            else:
                btn.config(fg=C_TEXT_SECONDARY, bg=C_BG_HEADER)

        if target_id == "diagnostics":
            self._check_system_health()

    def _toggle_ghostline_active(self):
        self.is_ghostline_active = not self.is_ghostline_active
        if self.is_ghostline_active:
            self.btn_primary_toggle.config(text="▶ Ghostline Active", bg="#065f46")
            self.lbl_status_dot.config(fg=C_SUCCESS)
            self.lbl_header_state.config(text="Ready (Alt+/)")
            self.lbl_primary_hint.config(text="Global Hotkey Alt + / is active • Hover cursor over question and press to solve")
        else:
            self.btn_primary_toggle.config(text="⏸ Ghostline Paused", bg="#854d0e")
            self.lbl_status_dot.config(fg=C_WARNING)
            self.lbl_header_state.config(text="Paused")
            self.lbl_primary_hint.config(text="Ghostline is paused. Click to re-activate.")

    def _on_solve_clicked(self):
        if self.on_trigger_solve:
            self.on_trigger_solve()

    def _on_toggle_audio_clicked(self):
        if self.on_toggle_hud:
            # Toggles audio HUD
            if hasattr(self, "on_toggle_audio") and self.on_toggle_audio:
                self.on_toggle_audio()
            else:
                self.on_toggle_hud()

    def _copy_answer_to_clipboard(self):
        if self.last_result and hasattr(self.last_result, "answer_result"):
            ans = self.last_result.answer_result
            opt = getattr(ans, "answer_option", getattr(ans, "source_option_label", ""))
            if self.root and opt:
                self.root.clipboard_clear()
                self.root.clipboard_append(opt)
                self.btn_copy_answer.config(text="✓ Copied!", fg=C_SUCCESS)
                self.root.after(1500, lambda: self.btn_copy_answer.config(text="📋 Copy", fg=C_TEXT_PRIMARY))

    # ------------------------------------------------------------------
    # Thread-Safe Pipeline & Solve Updates
    # ------------------------------------------------------------------
    def on_solve_started(self):
        def _apply():
            self.lbl_act_stage.config(text="SOLVING...", fg=C_WARNING)
            self.lbl_badge.config(text="…", fg=C_WARNING)
            self.lbl_result_headline.config(text="Analyzing question on screen...")
            self.lbl_result_meta.config(text="Extracting OCR text and reasoning locally with Ollama...")
            self.lbl_status_dot.config(fg=C_WARNING)
        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    def on_solve_completed(self, res: Any):
        self.last_result = res
        def _apply():
            ans = getattr(res, "answer_result", None)
            badge = getattr(ans, "tray_badge", getattr(ans, "source_option_label", "?")) if ans else "?"
            timing_str = f"Capture: {getattr(res, 'capture_time_ms', 0):.0f}ms | OCR: {getattr(res, 'ocr_time_ms', 0):.0f}ms | LLM: {getattr(res, 'llm_time_ms', 0):.0f}ms | Total: {getattr(res, 'total_time_ms', 0):.0f}ms"

            if not getattr(ans, "is_validated", True) or badge in ["Uncertain", "?"]:
                self.lbl_act_stage.config(text="UNCERTAIN", fg=C_WARNING)
                self.lbl_badge.config(text="?", fg=C_WARNING)
                self.lbl_result_headline.config(text="Answer Could Not Be Reliably Validated")
                self.lbl_result_meta.config(text="Explicit uncertain state: Question lacked distinguishable choices.")
            else:
                self.lbl_act_stage.config(text="ANSWER READY", fg=C_SUCCESS)
                self.lbl_badge.config(text=badge, fg=C_ACCENT)
                opt_desc = getattr(ans, "option_text", "")
                if opt_desc:
                    self.lbl_result_headline.config(text=f"Option {badge}: {opt_desc}")
                else:
                    self.lbl_result_headline.config(text=f"Option {badge}")
                conf = getattr(ans, "confidence", 1.0)
                self.lbl_result_meta.config(text=f"Confidence: {conf*100:.0f}% • {timing_str}")

            # Populate text details
            q_text = getattr(getattr(res, "parsed_question", None), "question_text", "")
            exp_text = getattr(ans, "explanation", "")
            full_text = f"Question:\n{q_text}\n\nExplanation:\n{exp_text}"

            self.txt_result_details.configure(state="normal")
            self.txt_result_details.delete("1.0", tk.END)
            self.txt_result_details.insert("1.0", full_text)
            self.txt_result_details.configure(state="disabled")

            self.lbl_status_dot.config(fg=C_SUCCESS)
            self.show_screen("main")

        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    def on_solve_error(self, err_msg: str):
        def _apply():
            self.lbl_act_stage.config(text="ERROR", fg=C_DANGER)
            self.lbl_badge.config(text="!", fg=C_DANGER)
            self.lbl_result_headline.config(text="Solve Execution Error")
            self.lbl_result_meta.config(text=err_msg[:90])
            self.lbl_status_dot.config(fg=C_DANGER)
        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    def update_audio_level(self, source: str, rms: float, peak: float):
        """Thread-safe live audio status update."""
        def _apply():
            src_label = "Mic" if source == "mic" else "Call"
            if rms > 0.0005:
                self.lbl_transcript_preview.config(
                    text=f"Audio: Active ({src_label} - RMS {rms:.4f})",
                    fg=C_SUCCESS if source == "mic" else C_CYAN
                )
                self.lbl_aud_badge.config(text="Active", fg=C_SUCCESS, bg="#064e3b")
            else:
                self.lbl_transcript_preview.config(text=f"Audio: Listening ({src_label})...", fg=C_TEXT_MUTED)
        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    # ------------------------------------------------------------------
    # Backward Compatibility for History List
    # ------------------------------------------------------------------
    def refresh_history_list(self, custom_path: Optional[Path] = None):
        """Mock/compat helper to satisfy test_desktop_ui."""
        path = custom_path or self.history_path
        entries = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
            except Exception:
                pass
        self.history_records = list(reversed(entries))

        if self.hist_listbox is None and self.root:
            self.hist_listbox = tk.Listbox(self.root)

        if self.hist_listbox:
            self.hist_listbox.delete(0, tk.END)
            q = self.hist_search_var.get().lower() if self.hist_search_var else ""
            for item in self.history_records:
                ans = item.get("answer", "?")
                quest = item.get("question", "")
                if not q or q in quest.lower():
                    self.hist_listbox.insert(tk.END, f"[{ans}] {quest}")

    # ------------------------------------------------------------------
    # Window Lifecycle & Tray Management
    # ------------------------------------------------------------------
    def show_window(self):
        """Restores window from minimized or hidden state and raises to foreground."""
        def _show():
            if self.root:
                self.root.deiconify()
                self.root.state("normal")
                self.root.lift()
                self.root.focus_force()
                try:
                    self.root.attributes("-topmost", True)
                    self.root.attributes("-topmost", False)
                except Exception:
                    pass
                self._is_minimized_to_tray = False
        if self.root:
            if threading.current_thread() is threading.main_thread():
                _show()
            else:
                self.root.after(0, _show)

    def hide_to_tray(self):
        """Hides window to notification tray without exiting."""
        if self.root:
            self.root.withdraw()
            self._is_minimized_to_tray = True

    def toggle_visibility(self):
        if self._is_minimized_to_tray:
            self.show_window()
        else:
            self.hide_to_tray()

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if not self.root or self._is_minimized_to_tray:
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

