"""
Capture script for Run 18 visual proof
======================================
Captures real Qt widget renders of:
1. HUD Overlay Ask input active with sample question
2. Settings > Audio screen showing 'Faster answers (early start)' toggle
3. Live Audio Panel Ask input
Saves images to reports/run18/captures/
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication, QScrollArea
from PyQt6.QtCore import Qt

from ghostline.config import AppConfig
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.audio.transcription import LiveTranscriber


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    
    out_dir = Path("reports/run18/captures")
    out_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(LiveTranscriber, "preload_in_background", return_value=None):
        cfg = AppConfig()
        cfg.first_run_complete = True
        cfg.faster_answers_enabled = True

        # 1. Capture HUD Ask input
        hud = QtGhostlineHudOverlay(width=620, height=480)
        hud.input_custom.setText("Explain the difference between TCP and UDP in networking.")
        hud.adjustSize()
        app.processEvents()
        pix_hud = hud.grab()
        hud_path = out_dir / "hud_ask_entry.png"
        pix_hud.save(str(hud_path))
        print(f"Captured: {hud_path} ({pix_hud.width()}x{pix_hud.height()})")
        hud.close()

        # 2. Capture Audio Panel Ask input
        panel = QtLiveAudioPanel(width=440, height=520)
        panel.input_custom.setText("Summarize the candidate's experience with distributed systems.")
        panel.adjustSize()
        app.processEvents()
        pix_panel = panel.grab()
        panel_path = out_dir / "audio_panel_ask_entry.png"
        pix_panel.save(str(panel_path))
        print(f"Captured: {panel_path} ({pix_panel.width()}x{pix_panel.height()})")
        panel.close()

        # 3. Capture Audio screen with Faster Answers toggle
        win = QtGhostlineMainWindow(config=cfg)
        win.show_screen("audio")
        win.resize(1100, 1400)
        win.adjustSize()
        # Scroll down to reveal Faster Answers toggle
        for child in win.findChildren(QScrollArea):
            child.verticalScrollBar().setValue(child.verticalScrollBar().maximum())
        app.processEvents()
        pix_win = win.grab()
        win_path = out_dir / "settings_faster_answers.png"
        pix_win.save(str(win_path))
        print(f"Captured: {win_path} ({pix_win.width()}x{pix_win.height()})")
        win._is_force_exit = True
        win.close()


if __name__ == "__main__":
    main()
