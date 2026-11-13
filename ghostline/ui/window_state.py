"""
Central Window State Manager for Ghostline Main Window.
Handles maximized opening, geometry persistence, screen boundary validation, and debounced config saves.
"""

import os
import logging
from typing import Optional
from PyQt6.QtCore import QTimer, QRect, QPoint, Qt
from PyQt6.QtWidgets import QMainWindow, QApplication

from ghostline.config import AppConfig, save_config
from ghostline.ui.window_geometry import get_work_area, validate_window_geometry, get_default_centered_geometry

logger = logging.getLogger(__name__)


class WindowStateManager:
    """
    Manages main window geometry, maximized state, and screen adaptation.
    Ensures safe restoration, small-screen compatibility, and debounced persistence.
    """

    def __init__(self, window: QMainWindow, config: AppConfig):
        self.window = window
        self.config = config
        self._save_timer = QTimer(window)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)  # 300ms debounce to prevent disk stalls during drag/resize
        self._save_timer.timeout.connect(self._do_save_config)

    def apply_initial_geometry_and_state(self, start_minimized: bool = False):
        """
        Applies validated window geometry and maximized state on startup.
        Safe for small screens, multiple monitors, and high-DPI scaling.
        """
        work = get_work_area()

        # Logical minimum constraint for small screens: at most 760x520
        min_w = min(760, work.width())
        min_h = min(520, work.height())
        self.window.setMinimumSize(min_w, min_h)

        # Retrieve saved normal geometry
        saved_w = getattr(self.config, "main_window_width", 960)
        saved_h = getattr(self.config, "main_window_height", 680)
        pos_x = getattr(self.config, "main_window_pos_x", None)
        pos_y = getattr(self.config, "main_window_pos_y", None)

        validated_rect = validate_window_geometry(pos_x, pos_y, saved_w, saved_h)
        self.window.resize(validated_rect.width(), validated_rect.height())
        self.window.move(validated_rect.x(), validated_rect.y())

        should_maximize = getattr(self.config, "open_maximized", True) or getattr(self.config, "main_window_maximized", False)

        if start_minimized:
            # Started minimized to tray: don't show yet, but remember maximized target
            self.window.hide()
        else:
            if should_maximize:
                self.window.showMaximized()
            else:
                self.window.show()

    def restore_from_tray(self):
        """Restores window from system tray with remembered maximized state."""
        should_maximize = getattr(self.config, "open_maximized", True) or getattr(self.config, "main_window_maximized", False)
        self.window.show()
        if should_maximize:
            self.window.showMaximized()
        else:
            if self.window.isMinimized():
                self.window.showNormal()
        self.window.activateWindow()
        self.window.raise_()

    def on_window_resized_or_moved(self):
        """Tracks geometry changes and triggers debounced save."""
        if not self.window.isVisible():
            return
        # Debounce disk write
        self._save_timer.start()

    def _do_save_config(self):
        """Performs actual config update and save."""
        try:
            is_max = self.window.isMaximized()
            if not is_max and not self.window.isMinimized():
                self.config.main_window_width = self.window.width()
                self.config.main_window_height = self.window.height()
                self.config.main_window_pos_x = self.window.x()
                self.config.main_window_pos_y = self.window.y()
            self.config.main_window_maximized = is_max
            save_config(self.config)
        except Exception as e:
            logger.debug("Failed to persist window state: %s", e)

