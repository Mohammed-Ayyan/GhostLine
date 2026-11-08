"""
Ghostline HUD Focus Controller
==============================
Manages seamless, non-intrusive keyboard focus and Win32 window activation
for floating, focus-free HUD overlays (QtGhostlineHudOverlay & QtLiveAudioPanel).

Design:
1. Normal State:
   - Window has WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW.
   - Window NEVER steals focus from foreground applications during screen solves,
     audio recording, or background streaming.
   - WDA_EXCLUDEFROMCAPTURE protects HUD contents from screen capture.

2. Text Entry State (Active Input):
   - When the user explicitly clicks the "Ask" input field:
     a. Records previous foreground window HWND.
     b. Temporarily removes WS_EX_NOACTIVATE.
     c. Calls SetForegroundWindow on the HUD and widget.setFocus().
     d. Preserves WDA_EXCLUDEFROMCAPTURE.
     e. Starts a 10-second idle timer.

3. Exit Text Entry State:
   - When user presses Enter, Escape, clicks outside, or 10s of idle elapses:
     a. Restores WS_EX_NOACTIVATE.
     b. Restores foreground focus to the previous active window.
     c. Clears input focus.
"""

from __future__ import annotations

import sys
import time
import logging
from typing import Optional, Any

from PyQt6.QtCore import QObject, QTimer, QEvent, Qt
from PyQt6.QtWidgets import QWidget, QLineEdit, QTextEdit

logger = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class HudFocusController(QObject):
    """
    Controller that dynamically toggles Win32 WS_EX_NOACTIVATE and coordinates
    transient keyboard focus for floating HUD inputs without losing stealth.
    """

    def __init__(self, hud_window: QWidget, parent: Optional[QObject] = None):
        super().__init__(parent or hud_window)
        self.hud_window = hud_window
        self.prev_hwnd: Optional[int] = None
        self.is_text_entry_active = False
        self.current_input: Optional[QWidget] = None
        self.last_activity_time = time.time()

        # 10-second inactivity watchdog
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(1000)  # Check every second
        self.idle_timer.timeout.connect(self._check_idle)

    def attach_input(self, input_widget: QWidget):
        """Attaches event filtering and click hooks to an input widget."""
        self.current_input = input_widget
        input_widget.installEventFilter(self)

    def get_hwnd(self) -> Optional[int]:
        """Resolves the Win32 HWND of the HUD window."""
        try:
            return int(self.hud_window.winId())
        except Exception:
            return None

    def begin_text_entry(self, widget: Optional[QWidget] = None):
        """
        Activates the HUD window for text entry:
        - Saves the currently active foreground window
        - Strips WS_EX_NOACTIVATE
        - Sets foreground window and focuses the input widget
        - Keeps WDA_EXCLUDEFROMCAPTURE intact
        """
        target = widget or self.current_input
        if not target:
            return

        self.last_activity_time = time.time()

        if self.is_text_entry_active:
            target.setFocus(Qt.FocusReason.MouseFocusReason)
            return

        if sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = self.get_hwnd()
            if hwnd:
                try:
                    # Save current foreground window to restore later
                    fg_hwnd = user32.GetForegroundWindow()
                    if fg_hwnd and fg_hwnd != hwnd:
                        self.prev_hwnd = fg_hwnd

                    # Strip WS_EX_NOACTIVATE so Windows accepts keyboard input
                    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    new_style = style & ~WS_EX_NOACTIVATE
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    user32.SetWindowPos(
                        hwnd, 0, 0, 0, 0, 0,
                        SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                    )

                    # Activate window
                    user32.SetForegroundWindow(hwnd)

                    # Re-assert stealth capture exclusion
                    if getattr(self.hud_window, "exclude_from_capture", True):
                        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
                except Exception as ex:
                    logger.warning("[HudFocusController] Failed to strip WS_EX_NOACTIVATE: %s", ex)

        self.is_text_entry_active = True
        target.setFocus(Qt.FocusReason.MouseFocusReason)
        self.idle_timer.start()

    def end_text_entry(self):
        """
        Restores the HUD window to its default focus-free state:
        - Re-applies WS_EX_NOACTIVATE
        - Restores focus to previous foreground window
        - Clears widget focus
        """
        if not self.is_text_entry_active:
            return

        self.idle_timer.stop()
        self.is_text_entry_active = False

        if self.current_input:
            self.current_input.clearFocus()

        if sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = self.get_hwnd()
            if hwnd:
                try:
                    # Re-apply WS_EX_NOACTIVATE
                    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    new_style = style | WS_EX_NOACTIVATE | WS_EX_TOPMOST
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    user32.SetWindowPos(
                        hwnd, 0, 0, 0, 0, 0,
                        SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                    )

                    # Re-assert capture exclusion
                    if getattr(self.hud_window, "exclude_from_capture", True):
                        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

                    # Restore focus to previous application
                    if self.prev_hwnd and user32.IsWindow(self.prev_hwnd):
                        user32.SetForegroundWindow(self.prev_hwnd)
                except Exception as ex:
                    logger.warning("[HudFocusController] Failed to restore WS_EX_NOACTIVATE: %s", ex)

        self.prev_hwnd = None

    def _check_idle(self):
        """Automatically releases focus if idle for more than 10 seconds."""
        if not self.is_text_entry_active:
            self.idle_timer.stop()
            return
        if time.time() - self.last_activity_time >= 10.0:
            logger.info("[HudFocusController] 10s idle elapsed; releasing HUD focus.")
            self.end_text_entry()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Monitors keyboard and mouse events on the input widget."""
        if watched == self.current_input:
            # Mouse click on input begins text entry
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                self.last_activity_time = time.time()
                if not self.is_text_entry_active:
                    self.begin_text_entry(self.current_input)

            # Key press updates activity and handles Escape
            elif event.type() == QEvent.Type.KeyPress:
                self.last_activity_time = time.time()
                key = getattr(event, "key", lambda: None)()
                if key == Qt.Key.Key_Escape:
                    self.end_text_entry()
                    return True

            # Focus loss ends text entry unless moving to another child of HUD
            elif event.type() == QEvent.Type.FocusOut:
                # Small delayed check in case focus moved within HUD (e.g., clicking Ask button)
                QTimer.singleShot(150, self._on_deferred_focus_check)

        return super().eventFilter(watched, event)

    def _on_deferred_focus_check(self):
        """Checks if HUD still has focus after FocusOut on input widget."""
        if not self.is_text_entry_active:
            return
        # If input widget no longer has focus and active widget is not inside HUD, end text entry
        if self.current_input and not self.current_input.hasFocus():
            active_w = self.hud_window.focusWidget()
            if not active_w or active_w == self.hud_window:
                self.end_text_entry()
