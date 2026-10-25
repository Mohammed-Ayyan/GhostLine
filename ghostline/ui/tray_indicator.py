import sys
import threading
from typing import Optional, Callable
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
        on_toggle_audio_panel: Optional[Callable[[], None]] = None
    ):
        self.on_trigger = on_trigger
        self.on_open_main = on_open_main or on_show_hud
        self.on_toggle_hud = on_toggle_hud or on_show_hud
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit
        self.on_toggle_pause = on_toggle_pause
        self.on_toggle_audio = on_toggle_audio
        self.on_toggle_audio_panel = on_toggle_audio_panel
        self.icon = None
        self.is_running = False

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

    def create_image(self, badge: str = "", status: str = "normal") -> Image.Image:
        """
        Generates a 32x32 notification-area icon for Ghostline:
        - 32x32 dark rounded-rectangle card (#303036) with 7px corner radius
        - Bold Segoe UI white text for answer glyphs (A, B, C, D, 1, 2, 3, 4, ✓)
        - Distinct accents for error/uncertain (!) and thinking (…)
        """
        width = 32
        height = 32
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
                glyph = "R"
            else:
                glyph = "R"

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
                self._pystray.MenuItem("Solve Under Cursor (Alt+/)", lambda icon, item: self._on_menu_trigger()),
                self._pystray.MenuItem("Show/Hide Mini HUD", lambda icon, item: self._on_menu_toggle_hud()),
                self._pystray.MenuItem("Toggle Live Audio Capture (Alt+A)", lambda icon, item: self._on_menu_toggle_audio()),
                self._pystray.MenuItem("Show/Hide Audio Panel", lambda icon, item: self._on_menu_toggle_audio_panel()),
                self._pystray.MenuItem("Pause/Resume Hover-to-Answer", lambda icon, item: self._on_menu_toggle_pause()),
                self._pystray.MenuItem("Settings", lambda icon, item: self._on_menu_open_settings()),
                self._pystray.Menu.SEPARATOR,
                self._pystray.MenuItem("Quit", lambda icon, item: self._on_menu_exit())
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


# Backwards compatibility alias
GhostlineTrayIndicator = TrayIndicator
