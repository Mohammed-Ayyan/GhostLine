"""
Ghostline - Unified HUD Coordinator & State Manager
Ensures strict mutual exclusivity across HUD views:
- Exactly one HUD is visible at any time: SCREEN, AUDIO, HISTORY, or HIDDEN.
- Single choke point via request_show() with ShowReason gating against config.show_hud_on_solve.
- Windows SW_SHOWNOACTIVATE focus preservation so user focus is never stolen.
"""

import logging
import ctypes
from enum import Enum
from typing import Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger("ghostline.hud_manager")
SW_SHOWNOACTIVATE = 4


class HudMode(str, Enum):
    HIDDEN = "hidden"
    SCREEN = "screen"
    AUDIO = "audio"
    HISTORY = "history"


class ShowReason(str, Enum):
    USER_HOTKEY = "user_hotkey"
    USER_TRAY_CLICK = "user_tray_click"
    SOLVE_COMPLETE = "solve_complete"
    AUTO_STREAM = "auto_stream"
    NOTIFICATION = "notification"
    AUDIO_START = "audio_start"


class HudManager(QObject):
    """
    Central controller for Ghostline floating HUD overlays.
    Enforces mutual exclusivity, clean transitions, focus preservation, and safe hotkey dispatch.
    """
    mode_changed = pyqtSignal(str)

    def __init__(
        self,
        screen_hud: Optional[QWidget] = None,
        audio_hud: Optional[QWidget] = None,
        history_hud: Optional[QWidget] = None,
        config: Optional[Any] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.screen_hud = screen_hud
        self.audio_hud = audio_hud
        self.history_hud = history_hud
        self.config = config
        self.active_mode = HudMode.HIDDEN
        self._last_active_mode = HudMode.SCREEN

    def set_huds(
        self,
        screen_hud: Optional[QWidget] = None,
        audio_hud: Optional[QWidget] = None,
        history_hud: Optional[QWidget] = None,
        config: Optional[Any] = None
    ):
        """Allows deferred attachment of HUD widgets and configuration."""
        if screen_hud is not None:
            self.screen_hud = screen_hud
        if audio_hud is not None:
            self.audio_hud = audio_hud
        if history_hud is not None:
            self.history_hud = history_hud
        if config is not None:
            self.config = config

    def get_active_mode(self) -> HudMode:
        return self.active_mode

    def set_mode(self, mode: HudMode):
        """Compatibility setter transitioning to mode or hiding all if HIDDEN."""
        if mode == HudMode.HIDDEN:
            self.hide_all()
        else:
            self.show_mode(mode)

    def is_visible(self) -> bool:
        return self.active_mode != HudMode.HIDDEN

    def request_show(
        self,
        mode: HudMode = HudMode.SCREEN,
        reason: ShowReason = ShowReason.USER_HOTKEY,
        config: Optional[Any] = None
    ) -> bool:
        """
        Architectural single choke point for HUD visibility.
        If reason is SOLVE_COMPLETE or AUTO_STREAM and show_hud_on_solve is False:
        Silently drops request and returns False.
        """
        cfg = config or self.config
        if reason in (ShowReason.SOLVE_COMPLETE, ShowReason.AUTO_STREAM):
            if cfg and not getattr(cfg, "show_hud_on_solve", True):
                logger.info("[HudController] Dropping show request (reason=%s, show_hud_on_solve=False)", reason.value)
                return False

        self.show_mode(mode, activate=(reason == ShowReason.USER_HOTKEY))
        return True

    def show_mode(self, mode: HudMode, activate: bool = False):
        """
        Transitions display to the requested mode without stealing foreground focus
        unless explicitly requested by activate=True.
        """
        logger.info("[HudManager] Transitioning HUD mode from %s -> %s (activate=%s)",
                    self.active_mode.value, mode.value, activate)
        if mode == HudMode.HIDDEN:
            self.hide_all()
            return

        # 1. Hide previous views
        self._hide_current_widgets()

        # 2. Show requested view with focus preservation
        target_widget = None
        if mode == HudMode.SCREEN:
            target_widget = self.screen_hud
        elif mode == HudMode.AUDIO:
            target_widget = self.audio_hud
        elif mode == HudMode.HISTORY:
            target_widget = self.history_hud

        if target_widget:
            self._show_widget_safely(target_widget, activate=activate)

        self._last_active_mode = mode
        self.active_mode = mode
        self.mode_changed.emit(mode.value)

    def _show_widget_safely(self, widget: QWidget, activate: bool = False):
        """Presents widget using SW_SHOWNOACTIVATE unless user explicitly asked to focus."""
        try:
            if hasattr(widget, "show_overlay"):
                widget.show_overlay(activate=activate)
            elif hasattr(widget, "show_panel"):
                widget.show_panel(activate=activate)
            else:
                widget.show()
                if activate:
                    widget.raise_()
                    widget.activateWindow()
                else:
                    hwnd = int(widget.winId())
                    if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
                        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        except Exception as e:
            logger.debug("[HudManager] Safe show widget note: %s", e)

    def toggle_mode(self, mode: HudMode):
        """Toggles mode: hides if already active in this mode, otherwise shows."""
        if self.active_mode == mode:
            self.hide_all()
        else:
            self.show_mode(mode, activate=True)

    def toggle_active(self):
        """Alt + T: Toggles currently visible HUD, or restores last active."""
        if self.active_mode != HudMode.HIDDEN:
            self.hide_all()
        else:
            self.show_mode(self._last_active_mode or HudMode.SCREEN, activate=True)

    def hide_all(self):
        """Hides every HUD window and sets mode to HIDDEN."""
        if self.active_mode != HudMode.HIDDEN:
            self._last_active_mode = self.active_mode
        self._hide_current_widgets()
        self.active_mode = HudMode.HIDDEN
        self.mode_changed.emit(HudMode.HIDDEN.value)

    def _hide_current_widgets(self):
        """Hides all QWidget overlays without modifying state tracking."""
        for hud in (self.screen_hud, self.audio_hud, self.history_hud):
            if hud:
                try:
                    if hasattr(hud, "hide_overlay"):
                        hud.hide_overlay()
                    elif hasattr(hud, "hide_panel"):
                        hud.hide_panel()
                    else:
                        hud.hide()
                except Exception as e:
                    logger.debug("[HudManager] Note hiding widget: %s", e)
