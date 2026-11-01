"""
Ghostline — Unified HUD Coordinator & State Manager
Ensures strict mutual exclusivity across HUD views:
- Exactly one HUD is visible at any time: SCREEN, AUDIO, HISTORY, or HIDDEN.
- Hotkeys explicitly command specific views without background cross-talk.
- Background audio events never force the Screen HUD open.
"""

import logging
from enum import Enum
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget


class HudMode(str, Enum):
    HIDDEN = "hidden"
    SCREEN = "screen"
    AUDIO = "audio"
    HISTORY = "history"


class HudManager(QObject):
    """
    Central controller for Ghostline floating HUD overlays.
    Enforces mutual exclusivity, clean transitions, and safe hotkey dispatch.
    """
    mode_changed = pyqtSignal(str)

    def __init__(
        self,
        screen_hud: Optional[QWidget] = None,
        audio_hud: Optional[QWidget] = None,
        history_hud: Optional[QWidget] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.screen_hud = screen_hud
        self.audio_hud = audio_hud
        self.history_hud = history_hud
        self.active_mode = HudMode.HIDDEN
        self._last_active_mode = HudMode.SCREEN

    def set_huds(
        self,
        screen_hud: Optional[QWidget] = None,
        audio_hud: Optional[QWidget] = None,
        history_hud: Optional[QWidget] = None
    ):
        """Allows deferred attachment of HUD widgets."""
        if screen_hud is not None:
            self.screen_hud = screen_hud
        if audio_hud is not None:
            self.audio_hud = audio_hud
        if history_hud is not None:
            self.history_hud = history_hud

    def get_active_mode(self) -> HudMode:
        return self.active_mode

    def is_visible(self) -> bool:
        return self.active_mode != HudMode.HIDDEN

    def show_mode(self, mode: HudMode):
        """
        Transitions display to the requested mode.
        Guarantees that all other HUD windows are hidden first.
        """
        logging.info("[HudManager] Transitioning HUD mode from %s -> %s", self.active_mode.value, mode.value)
        if mode == HudMode.HIDDEN:
            self.hide_all()
            return

        # 1. Hide previous views
        self._hide_current_widgets()

        # 2. Show requested view
        if mode == HudMode.SCREEN:
            if self.screen_hud:
                if hasattr(self.screen_hud, "show_overlay"):
                    self.screen_hud.show_overlay()
                else:
                    self.screen_hud.show()
                    self.screen_hud.raise_()
        elif mode == HudMode.AUDIO:
            if self.audio_hud:
                if hasattr(self.audio_hud, "show_panel"):
                    self.audio_hud.show_panel()
                else:
                    self.audio_hud.show()
                    self.audio_hud.raise_()
        elif mode == HudMode.HISTORY:
            if self.history_hud:
                if hasattr(self.history_hud, "show_panel"):
                    self.history_hud.show_panel()
                else:
                    self.history_hud.show()
                    self.history_hud.raise_()

        self._last_active_mode = mode
        self.active_mode = mode
        self.mode_changed.emit(mode.value)

    def toggle_mode(self, mode: HudMode):
        """
        Toggles the requested mode:
        If already visible in this mode, hides it.
        Otherwise, switches to this mode.
        """
        if self.active_mode == mode:
            self.hide_all()
        else:
            self.show_mode(mode)

    def toggle_active(self):
        """Alt + T: Toggles the currently visible HUD, or restores last active."""
        if self.active_mode != HudMode.HIDDEN:
            self.hide_all()
        else:
            self.show_mode(self._last_active_mode or HudMode.SCREEN)

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
                    else:
                        hud.hide()
                except Exception as e:
                    logging.debug("[HudManager] Note hiding widget: %s", e)
