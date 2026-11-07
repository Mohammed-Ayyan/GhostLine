import sys
import threading
from typing import Optional, Callable, Any
from PIL import Image, ImageDraw, ImageFont

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ghostline.core.llm_client import normalize_tray_badge

class TrayIndicator:
    """
    Dynamic taskbar answer indicator for Ghostline stealth tray icon:
    - 32x32 dark rounded card (#303036) with 7px corner radius
    - Bold Segoe UI centered text for confirmed answers (A, B, C, D, 1, 2, 3, 4, ✓)
    - Three-dot ellipsis for thinking (…)
    - Distinct badges for uncertain (?) and error (!)
    - Dynamic HICON replacement via Shell_NotifyIconW(NIM_MODIFY) without recreating icon
    - Concise tooltips (e.g. 'Ghostline — Answer 1: Paris')
    - Context menu with 'Show Answer Window' (default) and 'Solve Under Cursor (Alt+/)'
    """
    def __init__(
        self,
        on_trigger: Optional[Callable[[], None]] = None,
        on_open_main: Optional[Callable[[], None]] = None,
        on_toggle_hud: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        on_show_hud: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], bool]] = None,
        on_toggle_audio: Optional[Callable[[], None]] = None,
        on_toggle_audio_panel: Optional[Callable[[], None]] = None,
        on_show_last_answer: Optional[Callable[[], None]] = None,
        on_open_logs: Optional[Callable[[], None]] = None
    ):
        self.on_trigger = on_trigger
        self.on_open_main = on_open_main or on_show_hud
        self.on_toggle_hud = on_toggle_hud or on_show_hud
        self.on_show_last_answer = on_show_last_answer or self.on_toggle_hud
        self.on_open_logs = on_open_logs
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit
        self.on_toggle_pause = on_toggle_pause
        self.on_toggle_audio = on_toggle_audio
        self.on_toggle_audio_panel = on_toggle_audio_panel
        self.icon = None
        self.is_running = False
        self.custom_icon_path: Optional[str] = None
        self.custom_icon_preset: str = "default"

        self._has_pystray = False
        self._pystray = None
        self._thread: Optional[threading.Thread] = None
        self.current_badge = ""
        self.current_status = "ready"
        
        try:
            import pystray
            self._pystray = pystray
            self._has_pystray = True

            # Ensure pystray uses a stable uID (0) on Windows instead of transient heap id(self).
            # This enables Windows Explorer to associate the icon with NotifyIconSettings across runs.
            if hasattr(pystray, "_win32"):
                def _stable_message(icon_self, code, flags, **kwargs):
                    return pystray._win32.win32.Shell_NotifyIcon(
                        code,
                        pystray._win32.win32.NOTIFYICONDATAW(
                            cbSize=pystray._win32.ctypes.sizeof(pystray._win32.win32.NOTIFYICONDATAW),
                            hWnd=icon_self._hwnd,
                            hID=0,
                            uFlags=flags,
                            **kwargs
                        )
                    )
                pystray._win32.Icon._message = _stable_message
        except ImportError:
            self._has_pystray = False
            print("[!] WARNING: 'pystray' is not installed. System tray indicator is disabled.")
            print("[!] Run: pip install pystray>=0.19.5")

    def set_custom_icon(self, icon_path: Optional[str] = None, preset: str = "default"):
        """Sets custom icon path or preset and refreshes tray icon."""
        self.custom_icon_path = icon_path
        self.custom_icon_preset = preset or "default"
        if self.icon and self.is_running:
            try:
                self.icon.icon = self.create_image(self.current_badge, self.current_status)
            except Exception:
                pass

    def create_image(self, badge: str = "", status: str = "normal") -> Image.Image:
        """
        Generates a 32x32 notification-area icon for Ghostline:
        - When resting without active badge, respects custom icon path or stealth presets
        - When answering, draws dynamic 32x32 dark card with bold answer glyph (A, B, C, D, etc.)
        """
        width = 32
        height = 32

        # 1. Custom icon or preset rendering when no active badge is being signaled
        if not badge and status in ("ready", "normal"):
            if self.custom_icon_preset == "custom" and self.custom_icon_path:
                try:
                    import os
                    from pathlib import Path
                    if Path(self.custom_icon_path).exists():
                        img = Image.open(self.custom_icon_path).convert("RGBA")
                        return img.resize((width, height), getattr(Image, "Resampling", Image).LANCZOS)
                except Exception:
                    pass
            elif self.custom_icon_preset == "stealth_dot":
                image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.ellipse((10, 10, 21, 21), fill=(148, 163, 184, 240))
                return image
            elif self.custom_icon_preset == "windows_utility":
                image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.rounded_rectangle((4, 4, 27, 27), radius=5, fill=(35, 39, 47, 255), outline=(100, 116, 139, 255))
                draw.ellipse((11, 11, 20, 20), fill=(56, 189, 248, 255))
                return image
            else:
                # Official Ghostline Fluent Brand Icon
                try:
                    candidates = [
                        Path(__file__).resolve().parent.parent.parent / "assets" / "brand" / "ghostline-32.png",
                        Path("assets/brand/ghostline-32.png"),
                        Path("ghostline.ico"),
                    ]
                    for p in candidates:
                        if p.exists():
                            img = Image.open(p).convert("RGBA")
                            return img.resize((width, height), getattr(Image, "Resampling", Image).LANCZOS)
                except Exception:
                    pass

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Background card color (#303036)
        bg_color = (48, 48, 54, 255)  # #303036
        if status == "error" and not badge:
            bg_color = (220, 38, 38, 255)  # Red for system error

        # Draw rounded rectangle (corner radius 7px)
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=7, fill=bg_color)

        # Enforce centralized normalization so entire answers are never drawn inside tray icon
        glyph = normalize_tray_badge(
            badge,
            is_validated=(badge not in ["?", "!", "Uncertain", "uncertain"]),
            is_multiple_choice=(len(str(badge).strip()) <= 4 and badge not in ["✓"]),
            status=status
        ).strip()

        if not glyph:
            if status == "thinking":
                # Draw three centered amber dots for thinking state
                for cx in [9, 16, 23]:
                    draw.ellipse((cx - 2, 14, cx + 2, 18), fill=(245, 158, 11, 255))
                return image
            elif status == "ready":
                glyph = ""
            else:
                glyph = ""

        # Determine appropriate font size dynamically so glyph always fits inside 32x32 card
        target_size = 20
        if len(glyph) >= 5:
            target_size = 10
        elif len(glyph) >= 3:
            target_size = 13
        elif len(glyph) == 2:
            target_size = 16

        # Load bold Segoe UI font (system font on Windows)
        font = None
        for font_name in ["segoeuib.ttf", "arialbd.ttf", "segoeui.ttf", "arial.ttf"]:
            try:
                font = ImageFont.truetype(font_name, target_size)
                break
            except Exception:
                pass

        text_color = (255, 255, 255, 255)
        if status == "error":
            text_color = (245, 158, 11, 255) if glyph == "?" else (239, 68, 68, 255)

        if font:
            bbox = draw.textbbox((0, 0), glyph, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w > 24 and target_size > 10:
                try:
                    font = ImageFont.truetype("segoeuib.ttf", 10)
                    bbox = draw.textbbox((0, 0), glyph, font=font)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                except Exception:
                    pass
            x = (width - w) // 2 - bbox[0]
            y = (height - h) // 2 - bbox[1]
            draw.text((x, y), glyph, font=font, fill=text_color)
        else:
            draw.text((10, 6), glyph[:3], fill=text_color)

        return image

    def start(self):
        """Starts the system tray icon message pump in a daemon thread."""
        if not self._has_pystray or self._pystray is None:
            print("[!] Cannot start system tray: 'pystray' is not available.")
            return

        try:
            menu = (
                self._pystray.MenuItem("Open Ghostline", lambda icon, item: self._on_menu_open_main(), default=True),
                self._pystray.MenuItem("Show Last Answer", lambda icon, item: self._on_menu_show_last_answer()),
                self._pystray.MenuItem("Solve Under Cursor (Alt+/)", lambda icon, item: self._on_menu_trigger()),
                self._pystray.MenuItem("Show/Hide Mini HUD (Alt+T)", lambda icon, item: self._on_menu_toggle_hud()),
                self._pystray.MenuItem("Toggle Live Audio Capture (Alt+A)", lambda icon, item: self._on_menu_toggle_audio()),
                self._pystray.MenuItem("Show/Hide Audio Panel", lambda icon, item: self._on_menu_toggle_audio_panel()),
                self._pystray.MenuItem("Pause/Resume Hover-to-Answer", lambda icon, item: self._on_menu_toggle_pause()),
                self._pystray.MenuItem("Open Logs Folder", lambda icon, item: self._on_menu_open_logs()),
                self._pystray.MenuItem("System Tray Icon Instructions", lambda icon, item: self._on_menu_tray_instructions()),
                self._pystray.MenuItem("Settings", lambda icon, item: self._on_menu_open_settings()),
                self._pystray.Menu.SEPARATOR,
                self._pystray.MenuItem("Quit Ghostline", lambda icon, item: self._on_menu_exit())
            )

            self.icon = self._pystray.Icon(
                "Ghostline",
                self.create_image("G", "ready"),
                "Ghostline — Ready (Alt+/)",
                menu
            )
            self.current_badge = "G"
            self.current_status = "ready"
            self.is_running = True

            self._thread = threading.Thread(target=self._run_icon, daemon=True)
            self._thread.start()
            print("[*] System tray indicator started successfully.")
        except Exception as e:
            print(f"[!] Failed to initialize system tray icon: {e}")
            self.is_running = False

    def _run_icon(self):
        try:
            # Ensure thread is attached to user's interactive Default desktop if available
            import ctypes
            try:
                user32 = ctypes.windll.user32
                hDesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
                if hDesk:
                    user32.SetThreadDesktop(hDesk)
            except Exception:
                pass

            if self.icon:
                self.icon.run()
        except Exception as e:
            print(f"[!] System tray event loop error: {e}")
        finally:
            self.is_running = False

    def update_badge(
        self,
        badge: str,
        status: str = "normal",
        tooltip: Optional[str] = None,
        is_validated: bool = True,
        is_multiple_choice: bool = True
    ):
        """
        Updates the existing notification-area icon graphic (HICON) and tooltip.
        Does NOT destroy and recreate the icon.
        Centralizes badge normalization so no code path can ever pass full answer text to the renderer.
        """
        if not self.icon or not self._has_pystray:
            return

        try:
            norm_badge = normalize_tray_badge(
                badge,
                is_validated=is_validated,
                is_multiple_choice=is_multiple_choice,
                status=status
            )

            # Dynamically replace HICON
            new_img = self.create_image(norm_badge, status)
            self.icon.icon = new_img

            # Update tooltip consistently
            if tooltip:
                self.icon.title = tooltip[:128]
            elif norm_badge in ["?", "!"]:
                self.icon.title = "Ghostline — Uncertain (?)" if norm_badge == "?" else "Ghostline — Error (!)"
            elif norm_badge == "✓":
                self.icon.title = "Ghostline — Answer Verified (✓)"
            elif norm_badge and norm_badge not in ["R", "G"]:
                self.icon.title = f"Ghostline — Answer {norm_badge}"
            elif status == "thinking":
                self.icon.title = "Ghostline — Thinking…"
            elif status == "ready":
                self.icon.title = "Ghostline — Ready (Alt+/)"
            else:
                self.icon.title = f"Ghostline — {status.capitalize()}"

            self.current_badge = norm_badge
            self.current_status = status
            try:
                print(f"[*] [Tray Indicator] Icon graphic updated to '{norm_badge or status}', Tooltip: '{self.icon.title}'")
            except Exception:
                pass
        except Exception as e:
            print(f"[!] [Tray Indicator] Icon update error: {e}")
            try:
                self.icon.icon = self.create_image("!", "error")
                self.icon.title = "Ghostline — Error (!)"
            except Exception:
                pass

    def notify(self, message: str, title: str = "Ghostline"):
        """Optional secondary toast notification support."""
        if not self.icon or not self._has_pystray:
            return

        try:
            if getattr(self.icon, "HAS_NOTIFICATION", False):
                self.icon.notify(message, title)
        except Exception as e:
            print(f"[!] Tray notification error: {e}")

    def _on_menu_trigger(self):
        if self.on_trigger:
            self.on_trigger()

    def _on_menu_open_main(self):
        if self.on_open_main:
            self.on_open_main()

    def _on_menu_toggle_hud(self):
        if self.on_toggle_hud:
            self.on_toggle_hud()

    def _on_menu_toggle_pause(self):
        if self.on_toggle_pause:
            paused = self.on_toggle_pause()
            status_text = "Paused" if paused else "Active"
            try:
                print(f"[*] [Tray Indicator] Hover-to-Answer detection is now {status_text}.")
            except Exception:
                pass

    def _on_menu_open_settings(self):
        if self.on_open_settings:
            self.on_open_settings()
        elif self.on_open_main:
            self.on_open_main()

    def _on_menu_tray_instructions(self):
        if hasattr(self, "on_open_tray_instructions") and self.on_open_tray_instructions:
            self.on_open_tray_instructions()
        elif hasattr(self, "on_open_settings") and self.on_open_settings:
            self.on_open_settings()
        elif self.on_open_main:
            self.on_open_main()

    def _on_menu_show_hud(self):
        if hasattr(self, "on_toggle_hud") and self.on_toggle_hud:
            self.on_toggle_hud()
        elif self.on_open_main:
            self.on_open_main()

    def _on_menu_toggle_audio(self):
        if hasattr(self, "on_toggle_audio") and self.on_toggle_audio:
            self.on_toggle_audio()

    def _on_menu_toggle_audio_panel(self):
        if hasattr(self, "on_toggle_audio_panel") and self.on_toggle_audio_panel:
            self.on_toggle_audio_panel()

    def _on_menu_show_last_answer(self):
        if hasattr(self, "on_show_last_answer") and self.on_show_last_answer:
            self.on_show_last_answer()
        elif self.on_toggle_hud:
            self.on_toggle_hud()

    def _on_menu_open_logs(self):
        if hasattr(self, "on_open_logs") and self.on_open_logs:
            self.on_open_logs()
        else:
            try:
                from ghostline.config import get_app_dir
                import os
                os.startfile(str(get_app_dir()))
            except Exception as e:
                print(f"[!] Error opening logs folder: {e}")

    def show_balloon(self, title: str, text: str, icon_type: str = "info"):
        """Displays native Windows tray balloon/toast notification."""
        if self.icon and self._has_pystray:
            try:
                self.icon.notify(text, title)
            except Exception as e:
                pass

    def _on_menu_exit(self):
        self.stop()
        if self.on_exit:
            self.on_exit()


    def stop(self):
        """Stops the system tray icon cleanly."""
        if self.icon and self._has_pystray:
            try:
                self.icon.stop()
            except Exception:
                pass
        self.is_running = False

    def get_qt_tray_menu(self, parent: Optional[Any] = None) -> Any:
        """Returns a Microsoft Fluent 2 Dark styled QMenu for Qt system tray or render harness."""
        return create_qt_tray_menu(
            on_open_main=self.on_open_main,
            on_show_last_answer=self.on_show_last_answer,
            on_trigger=self.on_trigger,
            on_toggle_hud=self.on_toggle_hud,
            on_toggle_audio=self.on_toggle_audio,
            on_toggle_audio_panel=self.on_toggle_audio_panel,
            on_toggle_pause=self.on_toggle_pause,
            on_open_logs=self.on_open_logs,
            on_open_settings=self.on_open_settings,
            on_exit=self._on_menu_exit,
            parent=parent
        )


def create_qt_tray_menu(
    on_open_main: Optional[Callable[[], None]] = None,
    on_show_last_answer: Optional[Callable[[], None]] = None,
    on_trigger: Optional[Callable[[], None]] = None,
    on_toggle_hud: Optional[Callable[[], None]] = None,
    on_toggle_audio: Optional[Callable[[], None]] = None,
    on_toggle_audio_panel: Optional[Callable[[], None]] = None,
    on_toggle_pause: Optional[Callable[[], bool]] = None,
    on_open_logs: Optional[Callable[[], None]] = None,
    on_open_settings: Optional[Callable[[], None]] = None,
    on_exit: Optional[Callable[[], None]] = None,
    parent: Optional[Any] = None
) -> Any:
    """
    Constructs a Microsoft Fluent 2 Dark popup menu for the Ghostline system tray:
    - 4px control corner radius on items, 8px on menu surface
    - Official Fluent System vector icons for actions
    - Subtle hover overlay and danger exit styling
    - Native checkbox / checkmark indicators
    """
    from PyQt6.QtWidgets import QMenu
    from PyQt6.QtGui import QAction
    from ghostline.ui.theme.icons import get_fluent_icon
    from ghostline.ui.theme.tokens import (
        SURFACE_ELEVATED, TEXT_PRIMARY, TEXT_SECONDARY, STATUS_DANGER_TEXT,
        STROKE_CARD, RADIUS_CARD, RADIUS_CONTROL, OVERLAY_SELECTED, BRAND_FILL
    )

    menu = QMenu(parent)
    menu.setObjectName("GhostlineTrayMenu")
    menu.setTitle("Ghostline")

    # Actions with official Fluent System Icons
    act_open = menu.addAction(get_fluent_icon("home", size=16), "Open Ghostline")
    if on_open_main:
        act_open.triggered.connect(on_open_main)

    act_last = menu.addAction(get_fluent_icon("sparkle", size=16), "Show Last Answer")
    if on_show_last_answer:
        act_last.triggered.connect(on_show_last_answer)

    act_solve = menu.addAction(get_fluent_icon("sparkle", color="#58A6FF", size=16), "Solve Under Cursor (Alt+/)")
    if on_trigger:
        act_solve.triggered.connect(on_trigger)

    act_hud = menu.addAction(get_fluent_icon("desktop", size=16), "Show/Hide Mini HUD (Alt+T)")
    if on_toggle_hud:
        act_hud.triggered.connect(on_toggle_hud)

    act_audio = menu.addAction(get_fluent_icon("mic", size=16), "Toggle Live Audio Capture (Alt+A)")
    if on_toggle_audio:
        act_audio.triggered.connect(on_toggle_audio)

    act_panel = menu.addAction(get_fluent_icon("speaker", size=16), "Show/Hide Audio Panel")
    if on_toggle_audio_panel:
        act_panel.triggered.connect(on_toggle_audio_panel)

    act_pause = menu.addAction(get_fluent_icon("pause", size=16), "Pause/Resume Hover-to-Answer")
    act_pause.setCheckable(True)
    if on_toggle_pause:
        act_pause.triggered.connect(on_toggle_pause)

    act_logs = menu.addAction(get_fluent_icon("history", size=16), "Open Logs Folder")
    if on_open_logs:
        act_logs.triggered.connect(on_open_logs)

    act_settings = menu.addAction(get_fluent_icon("settings", size=16), "Settings")
    if on_open_settings:
        act_settings.triggered.connect(on_open_settings)

    menu.addSeparator()

    act_exit = menu.addAction(get_fluent_icon("power", color="#FF99A4", size=16), "Quit Ghostline")
    if on_exit:
        act_exit.triggered.connect(on_exit)

    menu.setStyleSheet(f"""
        QMenu#GhostlineTrayMenu {{
            background-color: {SURFACE_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {STROKE_CARD};
            border-radius: {RADIUS_CARD}px;
            padding: 6px;
            font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        QMenu#GhostlineTrayMenu::item {{
            height: 32px;
            padding: 4px 24px 4px 28px;
            border-radius: {RADIUS_CONTROL}px;
            color: {TEXT_PRIMARY};
            margin: 1px 2px;
        }}
        QMenu#GhostlineTrayMenu::item:selected {{
            background-color: {OVERLAY_SELECTED};
            color: #FFFFFF;
        }}
        QMenu#GhostlineTrayMenu::separator {{
            height: 1px;
            background: {STROKE_CARD};
            margin: 4px 6px;
        }}
        QMenu#GhostlineTrayMenu::indicator {{
            width: 16px;
            height: 16px;
            left: 6px;
        }}
        QMenu#GhostlineTrayMenu::indicator:checked {{
            background-color: {BRAND_FILL};
            border-radius: 3px;
        }}
    """)
    return menu


# Backwards compatibility alias
GhostlineTrayIndicator = TrayIndicator
