"""
Ghostline — Professional Desktop Application Interface.
Modern dark charcoal aesthetic with left sidebar navigation,
refined cards matching Reference 3 (General) and Reference 4 (Mode),
and comprehensive diagnostics and activity log.
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
from ghostline.ui.theme import (
    C_BG_APP,
    C_BG_SIDEBAR,
    C_BG_HEADER,
    C_BG_CARD,
    C_BG_CARD_HOVER,
    C_BG_CARD_ACTIVE,
    C_BG_SURFACE_ALT,
    C_BG_CODE,
    C_BG_INPUT,
    C_BORDER,
    C_BORDER_LIGHT,
    C_BORDER_ACCENT,
    C_BORDER_EMERALD,
    C_BORDER_FOCUS,
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
    ModernToggleSwitch
)

# Backward-compatibility color aliases
C_SUCCESS = C_EMERALD
C_BORDER_ACCENT = C_CYAN


class GhostlineMainWindow:
    """
    Professional desktop interface for Ghostline:
    - Left Navigation Sidebar: Ghostline branding, engine status, and menu items
    - General Screen: Reference 3 layout with Usage card, Shortcut card, and App Visibility toggles
    - Mode Screen: Reference 4 layout with interaction cards and graphic taskbar preview
    - Dashboard Screen: Hero toggle, Screen/Audio assistance cards, and Live Activity solve log
    - Diagnostics Screen: Health checks and interactive test benchmarks
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
        self.nav_buttons: Dict[str, Any] = {}
        self.last_result: Optional[Any] = None
        self._is_minimized_to_tray = False

        # State flags
        self.is_ghostline_active = True
        self.is_audio_active = False

        # Configuration variables (deferred until root exists)
        self.var_caps_pulse: Optional[tk.BooleanVar] = None
        self.var_capture_mode: Optional[tk.StringVar] = None
        self.var_show_hud: Optional[tk.BooleanVar] = None
        self.var_auto_copy: Optional[tk.BooleanVar] = None
        self.var_audio_mic: Optional[tk.BooleanVar] = None
        self.var_audio_sys: Optional[tk.BooleanVar] = None
        self.var_model: Optional[tk.StringVar] = None
        self.var_start_min: Optional[tk.BooleanVar] = None
        self.var_exclude_capture: Optional[tk.BooleanVar] = None

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
        self.root.geometry("860x700")
        self.root.minsize(720, 600)
        self.root.configure(bg=C_BG_APP)

        # Initialize Tk Variables once root window exists
        self.var_caps_pulse = tk.BooleanVar(value=getattr(self.config, "caps_lock_indicator", False))
        self.var_capture_mode = tk.StringVar(value=getattr(self.config, "capture_mode", "full_screen"))
        self.var_show_hud = tk.BooleanVar(value=getattr(self.config, "show_hud_on_solve", True))
        self.var_auto_copy = tk.BooleanVar(value=getattr(self.config, "auto_copy_answer", False))
        self.var_audio_mic = tk.BooleanVar(value=getattr(self.config, "audio_source_mic", True))
        self.var_audio_sys = tk.BooleanVar(value=getattr(self.config, "audio_source_system", True))
        self.var_model = tk.StringVar(value=getattr(self.config, "model_name", "phi3:mini"))
        self.var_start_min = tk.BooleanVar(value=getattr(self.config, "start_minimized", False))
        self.var_exclude_capture = tk.BooleanVar(value=getattr(self.config, "exclude_from_capture", True))

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
        self.font_logo = tkfont.Font(family="Segoe UI", size=15, weight="bold")
        self.font_h1 = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.font_h2 = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.font_body = tkfont.Font(family="Segoe UI", size=9)
        self.font_body_bold = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_code = tkfont.Font(family="Consolas", size=9)
        self.font_badge = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self.font_sm = tkfont.Font(family="Segoe UI", size=8)

        # Ensure StringVar initialized
        if self.hist_search_var is None:
            self.hist_search_var = tk.StringVar(value="")

        # Root Horizontal Split Layout: Left Sidebar + Right Content Area
        self.main_split = tk.Frame(self.root, bg=C_BG_APP)
        self.main_split.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(self.main_split)
        self._build_content_area(self.main_split)

        self.ans_badge_label = self.lbl_badge
        self.ans_option_text_lbl = self.lbl_result_headline

        # Handle start minimized
        if getattr(self.config, "start_minimized", False):
            self.root.withdraw()
            self._is_minimized_to_tray = True
        else:
            self.show_screen("dashboard")

        return self.root

    # -------------------------------------------------------------------------
    # Left Navigation Sidebar (References 3 & 4)
    # -------------------------------------------------------------------------
    def _build_sidebar(self, parent: tk.Widget):
        self.sidebar_frame = tk.Frame(parent, bg="#151821", width=210)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        # Brand row
        brand_box = tk.Frame(self.sidebar_frame, bg="#151821")
        brand_box.pack(fill=tk.X, padx=18, pady=(20, 16))

        lbl_brand = tk.Label(
            brand_box,
            text="Ghostline",
            font=self.font_logo,
            fg="#ffffff",
            bg="#151821"
        )
        lbl_brand.pack(anchor="w")

        # System Readiness Pill
        self.readiness_pill = tk.Frame(
            brand_box,
            bg=C_EMERALD_BG,
            bd=1,
            highlightbackground=C_EMERALD_BORDER,
            highlightthickness=1,
            padx=8,
            pady=2
        )
        self.readiness_pill.pack(anchor="w", pady=(8, 0))

        self.lbl_status_dot = tk.Label(
            self.readiness_pill,
            text="●",
            font=("Segoe UI", 8),
            fg=C_EMERALD_LIGHT,
            bg=C_EMERALD_BG
        )
        self.lbl_status_dot.pack(side=tk.LEFT, padx=(0, 4))

        self.lbl_header_state = tk.Label(
            self.readiness_pill,
            text="Engine Ready",
            font=("Segoe UI", 8, "bold"),
            fg=C_EMERALD_LIGHT,
            bg=C_EMERALD_BG
        )
        self.lbl_header_state.pack(side=tk.LEFT)

        # Navigation Menu (Vertical list matching References 3 & 4)
        nav_container = tk.Frame(self.sidebar_frame, bg="#151821")
        nav_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        menu_items = [
            ("settings", "⚙  General"),
            ("setup", "💻  Mode"),
            ("main", "⚡  Dashboard"),
            ("audio", "🎙️  Audio"),
            ("model", "🧠  Model"),
            ("about", "🛡️  Security"),
            ("diagnostics", "✉️  Diagnostics"),
            ("history", "📋  History"),
        ]

        self.nav_buttons = {}
        for screen_id, label in menu_items:
            item_frame = tk.Frame(
                nav_container,
                bg="#151821",
                cursor="hand2"
            )
            item_frame.pack(fill=tk.X, pady=2)

            btn_lbl = tk.Label(
                item_frame,
                text=label,
                font=("Segoe UI", 9, "bold"),
                fg="#94a3b8",
                bg="#151821",
                anchor="w",
                padx=12,
                pady=7,
                cursor="hand2"
            )
            btn_lbl.pack(fill=tk.X)

            def _make_handler(s_id):
                return lambda e: self.show_screen(s_id)
            item_frame.bind("<Button-1>", _make_handler(screen_id))
            btn_lbl.bind("<Button-1>", _make_handler(screen_id))

            def _on_hover(e, f=item_frame, l=btn_lbl, s=screen_id):
                if not self._is_active_nav(s):
                    f.config(bg="#1e2230")
                    l.config(bg="#1e2230", fg="#f8fafc")
            def _on_leave(e, f=item_frame, l=btn_lbl, s=screen_id):
                if not self._is_active_nav(s):
                    f.config(bg="#151821")
                    l.config(bg="#151821", fg="#94a3b8")

            item_frame.bind("<Enter>", _on_hover)
            item_frame.bind("<Leave>", _on_leave)
            btn_lbl.bind("<Enter>", _on_hover)
            btn_lbl.bind("<Leave>", _on_leave)

            self.nav_buttons[screen_id] = (item_frame, btn_lbl)

        # Bottom Sidebar Tag
        foot = tk.Frame(self.sidebar_frame, bg="#151821")
        foot.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=16)

        lbl_offline = tk.Label(
            foot,
            text="100% Offline Local AI",
            font=("Segoe UI", 8, "bold"),
            fg="#64748b",
            bg="#151821"
        )
        lbl_offline.pack(anchor="w")

        lbl_v = tk.Label(
            foot,
            text=f"v{__version__} • Windows Native",
            font=("Segoe UI", 8),
            fg="#475569",
            bg="#151821"
        )
        lbl_v.pack(anchor="w", pady=(2, 0))

    def _is_active_nav(self, s: str) -> bool:
        cur = self.current_screen
        if s == "main" and cur in ["main", "dashboard", "answer"]:
            return True
        if s == "settings" and cur in ["settings", "general"]:
            return True
        if s == "setup" and cur in ["setup", "mode"]:
            return True
        if s == "about" and cur in ["about", "security"]:
            return True
        return cur == s

    # -------------------------------------------------------------------------
    # Content Area & Screen Registration
    # -------------------------------------------------------------------------
    def _build_content_area(self, parent: tk.Widget):
        self.content_container = tk.Frame(parent, bg=C_BG_APP)
        self.content_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 1. Main Dashboard Screen
        self.screen_frames["main"] = self._build_screen_main(self.content_container)

        # 2. General Settings Screen (Reference 3)
        self.screen_frames["settings"] = self._build_screen_general(self.content_container)

        # 3. Mode Settings Screen (Reference 4)
        self.screen_frames["setup"] = self._build_screen_mode(self.content_container)

        # 4. Help & Diagnostics Screen
        self.screen_frames["diagnostics"] = self._build_screen_diagnostics(self.content_container)

        # 5. Audio Settings Screen
        self.screen_frames["audio"] = self._build_screen_audio(self.content_container)

        # 6. Model Settings Screen
        self.screen_frames["model"] = self._build_screen_model(self.content_container)

        # 7. History Screen
        self.screen_frames["history"] = self._build_screen_history(self.content_container)

        # 8. Security / About Screen
        self.screen_frames["about"] = self._build_screen_about(self.content_container)

        # Aliases for backward compatibility with tests
        self.screen_frames["dashboard"] = self.screen_frames["main"]
        self.screen_frames["answer"] = self.screen_frames["main"]
        self.screen_frames["general"] = self.screen_frames["settings"]
        self.screen_frames["mode"] = self.screen_frames["setup"]
        self.screen_frames["security"] = self.screen_frames["about"]

    # -------------------------------------------------------------------------
    # Screen 1: General Settings (Reference 3)
    # -------------------------------------------------------------------------
    def _build_screen_general(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)

        canvas = tk.Canvas(outer, bg=C_BG_APP, highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=C_BG_APP)
        canvas_win = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_cfg(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_cfg)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        pad_box = tk.Frame(content, bg=C_BG_APP, padx=28, pady=24)
        pad_box.pack(fill=tk.BOTH, expand=True)

        # Header Title: General
        lbl_title = tk.Label(
            pad_box,
            text="General",
            font=self.font_h1,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_title.pack(anchor="w", pady=(0, 18))

        # --- Section 1: Usage ---
        lbl_sec1 = tk.Label(
            pad_box,
            text="Usage",
            font=self.font_h2,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_sec1.pack(anchor="w", pady=(0, 8))

        card_usage = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card_usage.pack(fill=tk.X, pady=(0, 20))

        usage_inner = tk.Frame(card_usage, bg=C_BG_CARD, padx=16, pady=14)
        usage_inner.pack(fill=tk.X)

        # Top row: Searches left ... 5 left
        row_left = tk.Frame(usage_inner, bg=C_BG_CARD)
        row_left.pack(fill=tk.X)

        tk.Label(
            row_left,
            text="Searches left",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(side=tk.LEFT)

        tk.Label(
            row_left,
            text="5 left",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(side=tk.RIGHT)

        tk.Label(
            usage_inner,
            text="New accounts get 5 free searches.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(2, 10))

        # Thin divider line
        tk.Frame(usage_inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(0, 12))

        # Bottom row: Pro badge, Need more searches?, Subscribe button
        row_sub = tk.Frame(usage_inner, bg=C_BG_CARD)
        row_sub.pack(fill=tk.X)

        badge_pro = tk.Label(
            row_sub,
            text="Pro",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff",
            bg="#252936",
            padx=8,
            pady=3,
            bd=1,
            highlightbackground="#383e52",
            highlightthickness=1
        )
        badge_pro.pack(side=tk.LEFT, padx=(0, 10))

        desc_box = tk.Frame(row_sub, bg=C_BG_CARD)
        desc_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            desc_box,
            text="Need more searches?",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            desc_box,
            text="When your free searches run out, subscribe to Pro or Max to keep going.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(1, 0))

        btn_subscribe = tk.Label(
            row_sub,
            text="Subscribe",
            font=("Segoe UI", 9, "bold"),
            fg="#0f1117",
            bg="#ffffff",
            padx=14,
            pady=5,
            cursor="hand2"
        )
        btn_subscribe.pack(side=tk.RIGHT, padx=(8, 0))
        btn_subscribe.bind("<Button-1>", lambda e: messagebox.showinfo("Ghostline Pro", "Ghostline is free, open source, and 100% offline local AI! No subscription required."))

        # --- Section 2: Shortcut ---
        lbl_sec2 = tk.Label(
            pad_box,
            text="Shortcut",
            font=self.font_h2,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_sec2.pack(anchor="w", pady=(0, 8))

        card_short = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card_short.pack(fill=tk.X, pady=(0, 20))

        short_inner = tk.Frame(card_short, bg=C_BG_CARD, padx=16, pady=14)
        short_inner.pack(fill=tk.X)

        row_sc = tk.Frame(short_inner, bg=C_BG_CARD)
        row_sc.pack(fill=tk.X)

        sc_text_box = tk.Frame(row_sc, bg=C_BG_CARD)
        sc_text_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            sc_text_box,
            text="Custom Shortcut",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            sc_text_box,
            text="Set your own shortcut: Ctrl, Alt or Win, plus one key (e.g. Alt + /).",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(2, 0))

        pill_shortcut = tk.Label(
            row_sc,
            text="Ctrl + Alt + Win",
            font=("Segoe UI", 8, "bold"),
            fg="#f8fafc",
            bg="#252936",
            padx=10,
            pady=4,
            bd=1,
            highlightbackground="#383e52",
            highlightthickness=1,
            cursor="hand2"
        )
        pill_shortcut.pack(side=tk.RIGHT)

        # --- Section 3: App Visibility ---
        lbl_sec3 = tk.Label(
            pad_box,
            text="App Visibility",
            font=self.font_h2,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_sec3.pack(anchor="w", pady=(0, 8))

        card_vis = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card_vis.pack(fill=tk.X, pady=(0, 20))

        vis_inner = tk.Frame(card_vis, bg=C_BG_CARD, padx=16, pady=14)
        vis_inner.pack(fill=tk.X)

        # Row 1: Default icon
        row_icon = tk.Frame(vis_inner, bg=C_BG_CARD)
        row_icon.pack(fill=tk.X, pady=(0, 10))

        icon_text = tk.Frame(row_icon, bg=C_BG_CARD)
        icon_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            icon_text,
            text="Default icon",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            icon_text,
            text="Looks like an ordinary system icon rather than a special app.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(2, 0))

        btn_icon_dropdown = tk.Label(
            row_icon,
            text="⚙  ˇ",
            font=("Segoe UI", 9),
            fg="#f8fafc",
            bg="#252936",
            padx=10,
            pady=4,
            bd=1,
            highlightbackground="#383e52",
            highlightthickness=1,
            cursor="hand2"
        )
        btn_icon_dropdown.pack(side=tk.RIGHT)

        tk.Frame(vis_inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(0, 10))

        # Row 2: Hide from taskbar
        row_hide = tk.Frame(vis_inner, bg=C_BG_CARD)
        row_hide.pack(fill=tk.X, pady=(0, 10))

        hide_text = tk.Frame(row_hide, bg=C_BG_CARD)
        hide_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            hide_text,
            text="Hide from taskbar",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            hide_text,
            text="Hides the Ghostline button from the taskbar. You can open the app from the Ghostline icon in the system tray.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            wraplength=460,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 0))

        self.toggle_taskbar = ModernToggleSwitch(
            row_hide,
            checked=getattr(self.config, "start_minimized", False),
            command=self._on_toggle_hide_taskbar
        )
        self.toggle_taskbar.pack(side=tk.RIGHT)

        tk.Frame(vis_inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(0, 10))

        # Row 3: Floating stealth HUD
        row_hud = tk.Frame(vis_inner, bg=C_BG_CARD)
        row_hud.pack(fill=tk.X, pady=(0, 10))

        hud_text = tk.Frame(row_hud, bg=C_BG_CARD)
        hud_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            hud_text,
            text="Floating stealth HUD",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            hud_text,
            text="Display the floating overlay window when question is detected.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            wraplength=460,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 0))

        self.toggle_hud = ModernToggleSwitch(
            row_hud,
            checked=getattr(self.config, "show_hud_on_solve", True),
            command=self._on_toggle_show_hud
        )
        self.toggle_hud.pack(side=tk.RIGHT)

        tk.Frame(vis_inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(0, 10))

        # Row 4: Auto-copy verified answer
        row_copy = tk.Frame(vis_inner, bg=C_BG_CARD)
        row_copy.pack(fill=tk.X, pady=(0, 10))

        copy_text = tk.Frame(row_copy, bg=C_BG_CARD)
        copy_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            copy_text,
            text="Auto-copy verified answer",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            copy_text,
            text="Automatically copies verified answers to system clipboard.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            wraplength=460,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 0))

        self.toggle_copy = ModernToggleSwitch(
            row_copy,
            checked=getattr(self.config, "auto_copy_answer", False),
            command=self._on_toggle_auto_copy
        )
        self.toggle_copy.pack(side=tk.RIGHT)

        tk.Frame(vis_inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(0, 10))

        # Row 5: Screen-Share Invisibility
        row_invis = tk.Frame(vis_inner, bg=C_BG_CARD)
        row_invis.pack(fill=tk.X)

        invis_text = tk.Frame(row_invis, bg=C_BG_CARD)
        invis_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            invis_text,
            text="Screen-Share Invisibility (WDA_EXCLUDEFROMCAPTURE)",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            invis_text,
            text="Hides Ghostline windows from meeting screen capture and recordings.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            wraplength=460,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 0))

        self.toggle_invis = ModernToggleSwitch(
            row_invis,
            checked=getattr(self.config, "exclude_from_capture", True),
            command=self._on_toggle_exclude_capture
        )
        self.toggle_invis.pack(side=tk.RIGHT)

        # Save Settings Action Row
        btn_box = tk.Frame(pad_box, bg=C_BG_APP)
        btn_box.pack(fill=tk.X, pady=(4, 16))

        btn_save = tk.Button(
            btn_box,
            text="Save Settings",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#065f46",
            activebackground="#047857",
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._save_settings
        )
        btn_save.pack(side=tk.LEFT)

        btn_reset = tk.Button(
            btn_box,
            text="Reset to Defaults",
            font=self.font_body,
            fg=C_TEXT_SECONDARY,
            bg="#1e293b",
            activebackground="#334155",
            activeforeground="#ffffff",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._reset_settings_to_defaults
        )
        btn_reset.pack(side=tk.LEFT, padx=10)

        return outer

    def _on_toggle_hide_taskbar(self, val: bool):
        self.var_start_min.set(val)

    def _on_toggle_show_hud(self, val: bool):
        self.var_show_hud.set(val)

    def _on_toggle_auto_copy(self, val: bool):
        self.var_auto_copy.set(val)

    def _on_toggle_exclude_capture(self, val: bool):
        self.var_exclude_capture.set(val)

    # -------------------------------------------------------------------------
    # Screen 2: Mode Settings (Reference 4)
    # -------------------------------------------------------------------------
    def _build_screen_mode(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)

        canvas = tk.Canvas(outer, bg=C_BG_APP, highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=C_BG_APP)
        canvas_win = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_cfg(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_cfg)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        pad_box = tk.Frame(content, bg=C_BG_APP, padx=28, pady=24)
        pad_box.pack(fill=tk.BOTH, expand=True)

        # Header Title: Mode
        lbl_title = tk.Label(
            pad_box,
            text="Mode",
            font=self.font_h1,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_title.pack(anchor="w", pady=(0, 18))

        lbl_sec = tk.Label(
            pad_box,
            text="Mode Settings",
            font=self.font_h2,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_sec.pack(anchor="w", pady=(0, 10))

        # Card 1: Point at a question number and press Ctrl + Alt + Win.
        c1 = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        c1.pack(fill=tk.X, pady=(0, 12))

        c1_in = tk.Frame(c1, bg=C_BG_CARD, padx=16, pady=14)
        c1_in.pack(fill=tk.X)

        tk.Label(
            c1_in,
            text="👆",
            font=("Segoe UI", 13),
            fg="#f8fafc",
            bg=C_BG_CARD
        ).pack(side=tk.LEFT, padx=(0, 12))

        c1_text = tk.Frame(c1_in, bg=C_BG_CARD)
        c1_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            c1_text,
            text="Point at a question number and press Ctrl + Alt + Win.",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            c1_text,
            text="The answer appears using the selected display method.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(2, 0))

        # Card 2: System tray icon with Set up button
        c2 = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        c2.pack(fill=tk.X, pady=(0, 12))

        c2_in = tk.Frame(c2, bg=C_BG_CARD, padx=16, pady=14)
        c2_in.pack(fill=tk.X)

        tk.Label(
            c2_in,
            text="🖥️",
            font=("Segoe UI", 13),
            fg="#f8fafc",
            bg=C_BG_CARD
        ).pack(side=tk.LEFT, padx=(0, 12))

        c2_text = tk.Frame(c2_in, bg=C_BG_CARD)
        c2_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            c2_text,
            text="System tray icon",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            c2_text,
            text="Turn it on in Settings so answers appear on the system tray icon.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD
        ).pack(anchor="w", pady=(2, 0))

        btn_setup = tk.Label(
            c2_in,
            text="Set up",
            font=("Segoe UI", 9, "bold"),
            fg="#0f1117",
            bg="#ffffff",
            padx=14,
            pady=5,
            cursor="hand2"
        )
        btn_setup.pack(side=tk.RIGHT, padx=(8, 0))
        btn_setup.bind("<Button-1>", lambda e: self.show_screen("settings"))

        # Card 3: Current mode & Taskbar Preview
        c3 = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        c3.pack(fill=tk.X, pady=(0, 12))

        c3_top = tk.Frame(c3, bg=C_BG_CARD, padx=16, pady=14)
        c3_top.pack(fill=tk.X)

        tk.Label(
            c3_top,
            text="🗂️",
            font=("Segoe UI", 13),
            fg="#f8fafc",
            bg=C_BG_CARD
        ).pack(side=tk.LEFT, padx=(0, 12))

        c3_text = tk.Frame(c3_top, bg=C_BG_CARD)
        c3_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            c3_text,
            text="Current mode",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=C_BG_CARD
        ).pack(anchor="w")

        tk.Label(
            c3_text,
            text="Answers appear as a small system tray icon. For multiple answers,\nthe icon shows each one in turn.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 0))

        btn_mode_dropdown = tk.Label(
            c3_top,
            text="System Tray Icon  ˇ",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#252936",
            padx=12,
            pady=6,
            bd=1,
            highlightbackground="#383e52",
            highlightthickness=1,
            cursor="hand2"
        )
        btn_mode_dropdown.pack(side=tk.RIGHT)

        # Graphic preview card recreating the taskbar preview seen in Reference 4
        preview_container = tk.Frame(c3, bg="#0d1017", padx=12, pady=12)
        preview_container.pack(fill=tk.X, padx=14, pady=(0, 14))

        preview_canvas = tk.Canvas(preview_container, bg="#0d1017", height=130, highlightthickness=0)
        preview_canvas.pack(fill=tk.X, expand=True)

        def _draw_taskbar_preview():
            preview_canvas.delete("all")
            w = preview_canvas.winfo_width() or 460
            h = 130
            # Monitor curve / dark glass background
            preview_canvas.create_rectangle(0, 0, w, h, fill="#0d1017", outline="")
            # Curved monitor glare line at top
            preview_canvas.create_arc(-50, -80, w + 50, 160, start=190, extent=160, outline="#1e2433", width=2, style="arc")
            # Bottom taskbar strip
            bar_y = 75
            preview_canvas.create_rectangle(0, bar_y, w, h, fill="#07090e", outline="#1c2130")

            # Tray Icons area right-aligned
            rx = w - 30
            # Clock
            preview_canvas.create_text(rx, bar_y + 25, text="20:00", fill="#94a3b8", font=("Segoe UI", 8), anchor="e")
            rx -= 55
            # Speaker
            preview_canvas.create_text(rx, bar_y + 25, text="🔊", fill="#94a3b8", font=("Segoe UI", 8), anchor="e")
            rx -= 25
            # WiFi
            preview_canvas.create_text(rx, bar_y + 25, text="📶", fill="#94a3b8", font=("Segoe UI", 8), anchor="e")
            rx -= 25
            # Font icon 'A'
            preview_canvas.create_text(rx, bar_y + 25, text="A", fill="#e2e8f0", font=("Segoe UI", 9, "bold"), anchor="e")
            rx -= 30

            # Active Ghostline Answer Badge: Circular amber/cyan pill with 'R' / 'A'
            # Simulating Reference 4 yellow circle on sync arrow!
            cx = rx - 10
            cy = bar_y + 25
            # Sync arrow arc
            preview_canvas.create_arc(cx - 10, cy - 10, cx + 10, cy + 10, start=45, extent=270, outline="#f59e0b", width=2, style="arc")
            # Glowing dot
            preview_canvas.create_oval(cx + 2, cy - 8, cx + 8, cy - 2, fill="#f59e0b", outline="")
            # Answer badge letter
            preview_canvas.create_text(cx - 1, cy, text="R", fill="#ffffff", font=("Segoe UI", 8, "bold"))

            rx -= 45
            # Three dots '...'
            preview_canvas.create_text(rx, bar_y + 25, text="•••", fill="#64748b", font=("Segoe UI", 8), anchor="e")
            rx -= 30
            # Chevron '^'
            preview_canvas.create_text(rx, bar_y + 25, text="^", fill="#94a3b8", font=("Segoe UI", 9, "bold"), anchor="e")

        preview_canvas.bind("<Configure>", lambda e: _draw_taskbar_preview())

        tk.Label(
            preview_container,
            text="System Tray Mode: When question is solved, verified answer letter displays directly in the Windows taskbar.",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg="#0d1017"
        ).pack(anchor="w", pady=(4, 0))

        return outer

    # -------------------------------------------------------------------------
    # Screen 3: Main Dashboard Screen
    # -------------------------------------------------------------------------
    def _build_screen_main(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)

        canvas = tk.Canvas(outer, bg=C_BG_APP, highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=C_BG_APP)
        canvas_win = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_cfg(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_cfg)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        pad_box = tk.Frame(content, bg=C_BG_APP, padx=24, pady=20)
        pad_box.pack(fill=tk.BOTH, expand=True)

        # Header Title: Dashboard
        lbl_title = tk.Label(
            pad_box,
            text="Dashboard",
            font=self.font_h1,
            fg="#ffffff",
            bg=C_BG_APP
        )
        lbl_title.pack(anchor="w", pady=(0, 14))

        # Section 1: Hero Start / Stop Action Card
        action_card = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        action_card.pack(fill=tk.X, pady=(0, 12))

        action_inner = tk.Frame(action_card, bg=C_BG_CARD, padx=16, pady=12)
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

        # Section 2: Assistance Cards (Screen Assistance & Audio Assistance)
        modes_row = tk.Frame(pad_box, bg=C_BG_APP)
        modes_row.pack(fill=tk.X, pady=(0, 12))

        # Left Card: Screen Assistance
        scr_card = tk.Frame(modes_row, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        scr_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        scr_inner = tk.Frame(scr_card, bg=C_BG_CARD, padx=14, pady=12)
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
            text="Ready [Alt+/]",
            font=self.font_sm,
            fg=C_EMERALD_LIGHT,
            bg=C_EMERALD_BG,
            padx=6,
            pady=1,
            bd=1,
            highlightbackground=C_EMERALD_BORDER,
            highlightthickness=1
        )
        self.lbl_scr_badge.pack(side=tk.RIGHT)

        tk.Label(
            scr_inner,
            text="Captures screen, recognizes question stems, and computes instant local AI solutions.",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            anchor="w",
            justify=tk.LEFT,
            wraplength=250
        ).pack(fill=tk.X, pady=(4, 10))

        self.btn_scr_action = tk.Button(
            scr_inner,
            text="Run Screen Solve [Alt+/]",
            font=self.font_body_bold,
            fg="#ffffff",
            bg="#0284c7",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
            command=self._on_solve_clicked
        )
        self.btn_scr_action.pack(fill=tk.X)

        # Right Card: Audio Assistance
        aud_card = tk.Frame(modes_row, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        aud_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        aud_inner = tk.Frame(aud_card, bg=C_BG_CARD, padx=14, pady=12)
        aud_inner.pack(fill=tk.BOTH, expand=True)

        aud_header = tk.Frame(aud_inner, bg=C_BG_CARD)
        aud_header.pack(fill=tk.X)

        tk.Label(
            aud_header,
            text="🎙 Audio Assistance",
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
            text="Transcribes live microphone and system video call audio with real-time AI copilot responses.",
            font=self.font_sm,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            anchor="w",
            justify=tk.LEFT,
            wraplength=250
        ).pack(fill=tk.X, pady=(4, 10))

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
            pady=7,
            cursor="hand2",
            command=self._on_toggle_audio_clicked
        )
        self.btn_aud_action.pack(fill=tk.X)

        # Section 3: Live Activity Panel & Solve Log
        act_card = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        act_card.pack(fill=tk.BOTH, expand=True)

        act_header = tk.Frame(act_card, bg="#0d1421", height=32)
        act_header.pack(fill=tk.X, side=tk.TOP)
        act_header.pack_propagate(False)

        tk.Label(
            act_header,
            text="LIVE ACTIVITY & SOLVE LOG",
            font=("Segoe UI", 8, "bold"),
            fg=C_TEXT_SECONDARY,
            bg="#0d1421"
        ).pack(side=tk.LEFT, padx=12, pady=6)

        self.lbl_act_stage = tk.Label(
            act_header,
            text="READY",
            font=("Segoe UI", 8, "bold"),
            fg=C_EMERALD_LIGHT,
            bg="#0d1421"
        )
        self.lbl_act_stage.pack(side=tk.RIGHT, padx=12, pady=6)

        # Result Body
        result_box = tk.Frame(act_card, bg=C_BG_CARD, padx=14, pady=12)
        result_box.pack(fill=tk.BOTH, expand=True)

        # Headline Row
        badge_row = tk.Frame(result_box, bg=C_BG_CARD)
        badge_row.pack(fill=tk.X, pady=(0, 6))

        self.lbl_badge = tk.Label(
            badge_row,
            text="Ready",
            font=self.font_badge,
            fg=C_TEXT_MUTED,
            bg="#0d1421",
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

        # Copy Answer Action Button
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
            bg="#090d16",
            fg=C_TEXT_PRIMARY,
            font=self.font_body,
            wrap=tk.WORD,
            bd=0,
            padx=10,
            pady=8,
            height=6
        )
        self.txt_result_details.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.txt_result_details.insert(
            "1.0",
            "When you press [Alt + /], the captured question, verified answer, and explanation will appear here."
        )
        self.txt_result_details.configure(state="disabled")

        # Recovery guidance frame (shown when extraction fails)
        self.main_recovery_box = tk.Frame(result_box, bg="#1a1313", bd=1, highlightbackground=C_DANGER, highlightthickness=1)

        # Footer audio status preview line
        self.lbl_transcript_preview = tk.Label(
            act_card,
            text="Audio: Idle",
            font=self.font_sm,
            fg=C_TEXT_MUTED,
            bg=C_BG_CARD,
            anchor="w",
            padx=14,
            pady=6
        )
        self.lbl_transcript_preview.pack(fill=tk.X, side=tk.BOTTOM)

        return outer

    # -------------------------------------------------------------------------
    # Screen 4: Help & Diagnostics Screen
    # -------------------------------------------------------------------------
    def _build_screen_diagnostics(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=C_BG_APP)

        card = tk.Frame(frame, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        content = tk.Frame(card, bg=C_BG_CARD, padx=16, pady=14)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="System Setup & Diagnostics", font=self.font_h1, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(anchor="w", pady=(0, 10))

        # Checklist Cards
        chk_box = tk.Frame(content, bg="#0d1421", padx=12, pady=10)
        chk_box.pack(fill=tk.X, pady=(0, 12))

        self.lbl_diag_ollama = tk.Label(chk_box, text="● Checking Ollama connection...", font=self.font_body, fg=C_TEXT_SECONDARY, bg="#0d1421", anchor="w")
        self.lbl_diag_ollama.pack(fill=tk.X, pady=2)

        self.lbl_diag_model = tk.Label(chk_box, text="● Checking AI model...", font=self.font_body, fg=C_TEXT_SECONDARY, bg="#0d1421", anchor="w")
        self.lbl_diag_model.pack(fill=tk.X, pady=2)

        self.lbl_diag_ocr = tk.Label(chk_box, text="● Windows Native OCR: Ready", font=self.font_body, fg=C_EMERALD_LIGHT, bg="#0d1421", anchor="w")
        self.lbl_diag_ocr.pack(fill=tk.X, pady=2)

        self.lbl_diag_audio = tk.Label(chk_box, text="● Windows Audio Subsystem: Ready", font=self.font_body, fg=C_EMERALD_LIGHT, bg="#0d1421", anchor="w")
        self.lbl_diag_audio.pack(fill=tk.X, pady=2)

        # Test Action Buttons
        btn_bar = tk.Frame(content, bg=C_BG_CARD)
        btn_bar.pack(fill=tk.X, pady=(0, 12))

        self.btn_test_mic = tk.Button(
            btn_bar,
            text="🎤 Test Mic",
            font=self.font_sm,
            fg="#ffffff",
            bg="#065f46",
            activebackground="#047857",
            activeforeground="#ffffff",
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
            activeforeground="#ffffff",
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
            activeforeground="#ffffff",
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
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self._check_system_health
        )
        btn_refresh.pack(side=tk.RIGHT)

        # Output Terminal Box
        self.txt_diag_output = tk.Text(
            content,
            bg="#090d16",
            fg=C_TEXT_PRIMARY,
            font=self.font_code,
            wrap=tk.WORD,
            bd=0,
            padx=10,
            pady=8,
            height=10
        )
        self.txt_diag_output.pack(fill=tk.BOTH, expand=True)

        return frame

    # -------------------------------------------------------------------------
    # Screen 5: Audio Settings Screen
    # -------------------------------------------------------------------------
    def _build_screen_audio(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)
        pad_box = tk.Frame(outer, bg=C_BG_APP, padx=28, pady=24)
        pad_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(pad_box, text="Audio & Voice Assistance", font=self.font_h1, fg="#ffffff", bg=C_BG_APP).pack(anchor="w", pady=(0, 14))

        card = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card, bg=C_BG_CARD, padx=16, pady=14)
        inner.pack(fill=tk.X)

        tk.Label(inner, text="Capture Sources", font=self.font_h2, fg="#ffffff", bg=C_BG_CARD).pack(anchor="w", pady=(0, 8))

        row1 = tk.Frame(inner, bg=C_BG_CARD)
        row1.pack(fill=tk.X, pady=4)
        tk.Label(row1, text="Microphone Capture (Your voice)", font=self.font_body, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(side=tk.LEFT)
        t_mic = ModernToggleSwitch(row1, checked=getattr(self.config, "audio_source_mic", True), command=lambda v: self.var_audio_mic.set(v))
        t_mic.pack(side=tk.RIGHT)

        tk.Frame(inner, bg=C_BORDER, height=1).pack(fill=tk.X, pady=8)

        row2 = tk.Frame(inner, bg=C_BG_CARD)
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="System Loopback Audio (Call speaker / video call output)", font=self.font_body, fg=C_TEXT_PRIMARY, bg=C_BG_CARD).pack(side=tk.LEFT)
        t_sys = ModernToggleSwitch(row2, checked=getattr(self.config, "audio_source_system", True), command=lambda v: self.var_audio_sys.set(v))
        t_sys.pack(side=tk.RIGHT)

        return outer

    # -------------------------------------------------------------------------
    # Screen 6: Model Settings Screen
    # -------------------------------------------------------------------------
    def _build_screen_model(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)
        pad_box = tk.Frame(outer, bg=C_BG_APP, padx=28, pady=24)
        pad_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(pad_box, text="Local AI Reasoning Model", font=self.font_h1, fg="#ffffff", bg=C_BG_APP).pack(anchor="w", pady=(0, 14))

        card = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card, bg=C_BG_CARD, padx=16, pady=14)
        inner.pack(fill=tk.X)

        tk.Label(inner, text="Ollama Model:", font=self.font_body_bold, fg="#ffffff", bg=C_BG_CARD).pack(anchor="w", pady=(0, 4))
        models_combo = ttk.Combobox(
            inner,
            textvariable=self.var_model,
            values=["phi3:mini", "llama3.2:3b", "llama3.2:1b", "mistral:7b", "qwen2.5-coder:3b"],
            state="readonly",
            font=self.font_body
        )
        models_combo.pack(fill=tk.X, pady=(0, 10))

        tk.Label(inner, text="Ollama Endpoint URL:", font=self.font_body_bold, fg="#ffffff", bg=C_BG_CARD).pack(anchor="w", pady=(0, 4))
        self.entry_ollama_url = tk.Entry(inner, font=self.font_body, bg="#090d16", fg=C_TEXT_PRIMARY, bd=1, relief=tk.FLAT)
        self.entry_ollama_url.insert(0, getattr(self.config, "ollama_url", "http://127.0.0.1:11434"))
        self.entry_ollama_url.pack(fill=tk.X, pady=(0, 10))

        return outer

    # -------------------------------------------------------------------------
    # Screen 7: History Screen
    # -------------------------------------------------------------------------
    def _build_screen_history(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)
        pad_box = tk.Frame(outer, bg=C_BG_APP, padx=28, pady=24)
        pad_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(pad_box, text="Solve History", font=self.font_h1, fg="#ffffff", bg=C_BG_APP).pack(anchor="w", pady=(0, 14))

        # Search box
        search_row = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1, padx=8, pady=4)
        search_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(search_row, text="🔍", font=("Segoe UI", 9), fg=C_TEXT_MUTED, bg=C_BG_CARD).pack(side=tk.LEFT, padx=(4, 6))
        entry_search = tk.Entry(search_row, textvariable=self.hist_search_var, font=self.font_body, bg=C_BG_CARD, fg=C_TEXT_PRIMARY, bd=0)
        entry_search.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        entry_search.bind("<KeyRelease>", lambda e: self.refresh_history_list())

        # Listbox
        list_card = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        list_card.pack(fill=tk.BOTH, expand=True)

        self.hist_listbox = tk.Listbox(
            list_card,
            font=self.font_body,
            bg=C_BG_CARD,
            fg=C_TEXT_PRIMARY,
            bd=0,
            highlightthickness=0,
            selectbackground="#272a33"
        )
        self.hist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        scroll = tk.Scrollbar(list_card, orient=tk.VERTICAL, command=self.hist_listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_listbox.config(yscrollcommand=scroll.set)

        return outer

    # -------------------------------------------------------------------------
    # Screen 8: Security & About Screen
    # -------------------------------------------------------------------------
    def _build_screen_about(self, parent: tk.Widget) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_BG_APP)
        pad_box = tk.Frame(outer, bg=C_BG_APP, padx=28, pady=24)
        pad_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(pad_box, text="Security & Local Privacy", font=self.font_h1, fg="#ffffff", bg=C_BG_APP).pack(anchor="w", pady=(0, 14))

        card = tk.Frame(pad_box, bg=C_BG_CARD, bd=1, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card, bg=C_BG_CARD, padx=16, pady=14)
        inner.pack(fill=tk.X)

        tk.Label(inner, text="🔒 100% Offline Local Architecture", font=self.font_h2, fg=C_EMERALD_LIGHT, bg=C_BG_CARD).pack(anchor="w", pady=(0, 4))
        tk.Label(
            inner,
            text="Ghostline executes all screen OCR and AI reasoning locally on your device via Windows Native OCR and local Ollama inference. No screen captures, transcripts, or queries are ever sent to external cloud servers.",
            font=self.font_body,
            fg=C_TEXT_SECONDARY,
            bg=C_BG_CARD,
            wraplength=520,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(0, 8))

        return outer

    # -------------------------------------------------------------------------
    # System Diagnostics Implementation
    # -------------------------------------------------------------------------
    def _check_system_health(self):
        """Verifies local dependencies and displays actionable fix steps."""
        if not hasattr(self, "txt_diag_output") or not self.txt_diag_output:
            return
        self.txt_diag_output.delete("1.0", tk.END)
        self.txt_diag_output.insert(tk.END, "Running Ghostline System Check...\n\n")

        # 1. Ollama status
        ollama_ok = False
        models = []
        if self.ollama_client:
            ollama_ok, models = self.ollama_client.check_health()

        if ollama_ok:
            self.lbl_diag_ollama.config(text=f"● Ollama Engine: Running ({self.config.ollama_url})", fg=C_EMERALD_LIGHT)
            self.txt_diag_output.insert(tk.END, f"[✓] Ollama is running and responding at {self.config.ollama_url}\n")
        else:
            self.lbl_diag_ollama.config(text="✗ Ollama Engine: Not Running", fg=C_DANGER_LIGHT)
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
            self.lbl_diag_model.config(text=f"● AI Model: '{target_model}' Ready", fg=C_EMERALD_LIGHT)
            self.txt_diag_output.insert(tk.END, f"[✓] AI model '{target_model}' is installed locally.\n")
        else:
            self.lbl_diag_model.config(text=f"✗ AI Model: '{target_model}' Missing", fg=C_AMBER_LIGHT)
            self.txt_diag_output.insert(
                tk.END,
                f"[!] AI model '{target_model}' is not pulled yet.\n"
                f"    Fix: Open Windows Terminal or Command Prompt and run:\n"
                f"         ollama pull {target_model}\n\n"
            )

        # 3. OCR Status
        from ghostline.core.ocr_engine import get_win_ocr_binary_path
        try:
            ocr_path = get_win_ocr_binary_path()
            if ocr_path.exists():
                self.lbl_diag_ocr.config(text="● Windows Native OCR: Ready", fg=C_EMERALD_LIGHT)
                self.txt_diag_output.insert(tk.END, f"[✓] Windows OCR engine verified at: {ocr_path}\n")
            else:
                self.lbl_diag_ocr.config(text="✗ Windows OCR: Binary Missing", fg=C_DANGER_LIGHT)
                self.txt_diag_output.insert(tk.END, f"[✗] OCR binary missing at: {ocr_path}\n")
        except Exception as e:
            self.lbl_diag_ocr.config(text="✗ Windows OCR Error", fg=C_DANGER_LIGHT)
            self.txt_diag_output.insert(tk.END, f"[✗] OCR search note: {e}\n")

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
        self.txt_diag_output.insert(tk.END, "\n[Test] Capturing loopback audio for 3s... (Play YouTube or sound now)\n")

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

    # -------------------------------------------------------------------------
    # State Management & Navigation
    # -------------------------------------------------------------------------
    def show_screen(self, screen_id: str):
        target_id = screen_id if screen_id in self.screen_frames else "main"
        self.current_screen = screen_id

        for s_id, f in self.screen_frames.items():
            f.pack_forget()

        self.screen_frames[target_id].pack(fill=tk.BOTH, expand=True)

        # Highlight sidebar navigation button
        active_key = target_id
        if target_id in ["main", "dashboard", "answer"]:
            active_key = "main"
        elif target_id in ["settings", "general"]:
            active_key = "settings"
        elif target_id in ["setup", "mode"]:
            active_key = "setup"
        elif target_id in ["about", "security"]:
            active_key = "about"

        for b_id, item in self.nav_buttons.items():
            if isinstance(item, tuple):
                f_widget, l_widget = item
                if b_id == active_key:
                    f_widget.config(bg="#272a33")
                    l_widget.config(bg="#272a33", fg="#ffffff")
                else:
                    f_widget.config(bg="#151821")
                    l_widget.config(bg="#151821", fg="#94a3b8")
            elif isinstance(item, tk.Label):
                if b_id == active_key:
                    item.config(fg=C_CYAN_LIGHT, bg=C_BG_CARD)
                else:
                    item.config(fg=C_TEXT_SECONDARY, bg=C_BG_HEADER)

        if target_id == "diagnostics":
            self._check_system_health()

    def _toggle_ghostline_active(self):
        self.is_ghostline_active = not self.is_ghostline_active
        if self.is_ghostline_active:
            self.btn_primary_toggle.config(text="▶ Ghostline Active", bg="#065f46")
            self.lbl_status_dot.config(fg=C_EMERALD_LIGHT)
            self.lbl_header_state.config(text="Engine Ready", fg=C_EMERALD_LIGHT)
            self.readiness_pill.config(bg=C_EMERALD_BG, highlightbackground=C_EMERALD_BORDER)
            self.lbl_primary_hint.config(text="Global Hotkey Alt + / is active • Hover cursor over question and press to solve")
        else:
            self.btn_primary_toggle.config(text="⏸ Ghostline Paused", bg="#854d0e")
            self.lbl_status_dot.config(fg=C_AMBER_LIGHT)
            self.lbl_header_state.config(text="Paused", fg=C_AMBER_LIGHT)
            self.readiness_pill.config(bg=C_AMBER_BG, highlightbackground=C_AMBER)
            self.lbl_primary_hint.config(text="Ghostline is paused. Click to re-activate.")

    def _on_solve_clicked(self):
        if self.on_trigger_solve:
            self.on_trigger_solve()

    def _on_toggle_audio_clicked(self):
        if hasattr(self, "on_toggle_audio") and self.on_toggle_audio:
            self.on_toggle_audio()
        elif self.on_toggle_hud:
            self.on_toggle_hud()

    def _copy_answer_to_clipboard(self):
        if self.last_result and hasattr(self.last_result, "answer_result"):
            ans = self.last_result.answer_result
            opt = getattr(ans, "answer_option", getattr(ans, "source_option_label", ""))
            if self.root and opt:
                self.root.clipboard_clear()
                self.root.clipboard_append(opt)
                self.btn_copy_answer.config(text="✓ Copied!", fg=C_EMERALD_LIGHT)
                self.root.after(1500, lambda: self.btn_copy_answer.config(text="📋 Copy", fg=C_TEXT_PRIMARY))

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
        self.config.exclude_from_capture = self.var_exclude_capture.get()

        save_config(self.config)
        if self.on_settings_saved:
            self.on_settings_saved(self.config)
        messagebox.showinfo("Settings Saved", "Ghostline settings updated successfully.")
        self.show_screen("main")

    def _reset_settings_to_defaults(self):
        default_cfg = AppConfig()
        self.var_model.set(default_cfg.model_name)
        self.var_capture_mode.set(default_cfg.capture_mode)
        self.var_show_hud.set(default_cfg.show_hud_on_solve)
        self.var_audio_mic.set(default_cfg.audio_source_mic)
        self.var_audio_sys.set(default_cfg.audio_source_system)
        self.var_auto_copy.set(default_cfg.auto_copy_answer)
        self.var_start_min.set(default_cfg.start_minimized)
        self.var_caps_pulse.set(default_cfg.caps_lock_indicator)
        self.var_exclude_capture.set(default_cfg.exclude_from_capture)
        if hasattr(self, "entry_ollama_url"):
            self.entry_ollama_url.delete(0, tk.END)
            self.entry_ollama_url.insert(0, default_cfg.ollama_url)

        if hasattr(self, "toggle_taskbar"):
            self.toggle_taskbar.set_state(default_cfg.start_minimized)
        if hasattr(self, "toggle_hud"):
            self.toggle_hud.set_state(default_cfg.show_hud_on_solve)
        if hasattr(self, "toggle_copy"):
            self.toggle_copy.set_state(default_cfg.auto_copy_answer)
        if hasattr(self, "toggle_invis"):
            self.toggle_invis.set_state(default_cfg.exclude_from_capture)

    # -------------------------------------------------------------------------
    # Thread-Safe Pipeline & Solve Updates
    # -------------------------------------------------------------------------
    def on_solve_started(self):
        def _apply():
            self.lbl_act_stage.config(text="SOLVING...", fg=C_AMBER_LIGHT)
            self.lbl_badge.config(text="…", fg=C_AMBER_LIGHT)
            self.lbl_result_headline.config(text="Analyzing question on screen...")
            self.lbl_result_meta.config(text="Extracting OCR text and reasoning locally with Ollama...")
            self.lbl_status_dot.config(fg=C_AMBER_LIGHT)
            self.main_recovery_box.pack_forget()
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

            self.main_recovery_box.pack_forget()

            if not getattr(ans, "is_validated", True) or badge in ["Uncertain", "?"]:
                self.lbl_act_stage.config(text="UNCERTAIN", fg=C_AMBER_LIGHT)
                self.lbl_badge.config(text="?", fg=C_AMBER_LIGHT)
                self.lbl_result_headline.config(text="Answer Could Not Be Reliably Validated")
                self.lbl_result_meta.config(text="Explicit uncertain state: Question lacked distinguishable choices.")
            else:
                self.lbl_act_stage.config(text="ANSWER READY", fg=C_EMERALD_LIGHT)
                self.lbl_badge.config(text=badge, fg=C_CYAN_LIGHT)
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

            self.lbl_status_dot.config(fg=C_EMERALD_LIGHT)
            self.show_screen("main")

        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    def on_solve_error(self, err_msg: str, raw_text: str = ""):
        def _apply():
            is_extraction_uncertain = ("Unreliable question extraction" in err_msg or "does not contain question indicators" in err_msg)
            
            if is_extraction_uncertain:
                self.lbl_act_stage.config(text="UNCERTAIN EXTRACTION", fg=C_AMBER_LIGHT)
                self.lbl_badge.config(text="?", fg=C_AMBER_LIGHT)
                self.lbl_result_headline.config(text="Uncertain Question Extraction")
                clean_reason = err_msg.replace("Unreliable question extraction:", "").strip()
                self.lbl_result_meta.config(text=f"Note: {clean_reason[:80]}")
                self.lbl_status_dot.config(fg=C_AMBER_LIGHT)
                
                full_text = (
                    f"Question Validation Notice:\n{clean_reason}\n\n"
                    f"Captured Raw OCR Text:\n\"{raw_text.strip() if raw_text else 'None'}\"\n\n"
                    f"Recovery Steps:\n"
                    f"• Position your cursor directly over the question prompt and press [Alt+/]\n"
                    f"• Ensure problem text is not covered by popups or window chrome\n"
                    f"• Or open the Floating HUD to enter the question manually."
                )
            else:
                self.lbl_act_stage.config(text="ERROR", fg=C_DANGER_LIGHT)
                self.lbl_badge.config(text="!", fg=C_DANGER_LIGHT)
                self.lbl_result_headline.config(text="Solve Execution Error")
                self.lbl_result_meta.config(text=err_msg[:90])
                self.lbl_status_dot.config(fg=C_DANGER_LIGHT)
                full_text = f"Error Details:\n{err_msg}\n\nActionable Fix:\nVerify Ollama is running and model is downloaded."

            self.txt_result_details.configure(state="normal")
            self.txt_result_details.delete("1.0", tk.END)
            self.txt_result_details.insert("1.0", full_text)
            self.txt_result_details.configure(state="disabled")

        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    def update_audio_level(self, source: str, rms: float, peak: float):
        def _apply():
            src_label = "Mic" if source == "mic" else "Call"
            if rms > 0.0005:
                self.lbl_transcript_preview.config(
                    text=f"Audio: Active ({src_label} - RMS {rms:.4f})",
                    fg=C_EMERALD_LIGHT if source == "mic" else C_CYAN_LIGHT
                )
                self.lbl_aud_badge.config(text="Active", fg=C_EMERALD_LIGHT, bg=C_EMERALD_BG)
            else:
                self.lbl_transcript_preview.config(text=f"Audio: Listening ({src_label})...", fg=C_TEXT_MUTED)
        if self.root:
            if threading.current_thread() is threading.main_thread():
                _apply()
            else:
                self.root.after(0, _apply)

    # -------------------------------------------------------------------------
    # Backward Compatibility for History List
    # -------------------------------------------------------------------------
    def refresh_history_list(self, custom_path: Optional[Path] = None):
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

    # -------------------------------------------------------------------------
    # Window Lifecycle & Tray Management
    # -------------------------------------------------------------------------
    def show_window(self):
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
