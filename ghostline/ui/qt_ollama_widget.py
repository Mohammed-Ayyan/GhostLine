"""
Ghostline — Qt Ollama First-Run & Lifecycle State Widget.
Displays clear primary actions per state:
- NOT_INSTALLED: [Download Ollama], installer polling, [I've installed it: check again]
- INSTALLED_NOT_RUNNING: [Start Ollama], 30s timer, log tail diagnosis
- RUNNING_NO_MODEL: [Download model], progress bar, cancel, disk check
- READY: "Ollama · Ready"
Includes collapsible "Advanced: do it manually" with copyable commands.
"""

import os
import sys
import time
import shutil
import threading
from typing import Optional, Callable, Any

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from ghostline.core.ollama_state import (
    OllamaState, OllamaStateMachine,
    start_ollama_process, get_ollama_log_tail,
    pull_ollama_model, check_free_disk_space
)
from ghostline.ui.theme.tokens import (
    SURFACE_CARD, SURFACE_INPUT, SURFACE_ELEVATED, SURFACE_CARD_HOVER,
    STROKE_CARD, STROKE_CONTROL, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BRAND_TEXT, BRAND_FILL, STATUS_SUCCESS_TEXT,
    STATUS_SUCCESS_BG, STATUS_WARNING_TEXT, STATUS_DANGER_TEXT,
    RADIUS_CARD, RADIUS_CONTROL
)
from ghostline.ui.theme.icons import get_fluent_icon


class QtOllamaStateCard(QFrame):
    """
    Self-contained Ollama lifecycle card for Wizard Step 1, AI Settings, and Home page.
    """
    sig_state_changed = pyqtSignal(str)

    def __init__(
        self,
        config: Any,
        parent: Optional[QWidget] = None,
        state_machine: Optional[OllamaStateMachine] = None,
        compact: bool = False
    ):
        super().__init__(parent)
        self.config = config
        self.state_machine = state_machine or OllamaStateMachine()
        self.compact = compact
        self._current_state = OllamaState.NOT_INSTALLED
        self._is_starting = False
        self._start_deadline = 0.0
        self._is_pulling = False
        self._pull_cancel_event = threading.Event()

        self.setObjectName("OllamaStateCard")
        self.setStyleSheet(f"""
            QFrame#OllamaStateCard {{
                background-color: {SURFACE_CARD};
                border: 1px solid {STROKE_CARD};
                border-radius: {RADIUS_CARD}px;
                padding: { '8px' if compact else '12px' };
            }}
        """)

        self._build_ui()

        # Polling timer (2 seconds)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self.poll_state)

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(8)

        # 1. Status row (icon + headline + action)
        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(8)

        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(20, 20)
        self.status_row.addWidget(self.lbl_icon)

        self.lbl_headline = QLabel("Checking local Ollama service...")
        self.lbl_headline.setStyleSheet(f"background: transparent; font-size: 13px; font-weight: 600; color: {TEXT_PRIMARY};")
        self.status_row.addWidget(self.lbl_headline, 1)

        self.btn_primary = QPushButton("Check Again")
        self.btn_primary.setFixedHeight(30)
        self.btn_primary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_primary.setStyleSheet(f"""
            QPushButton {{
                background-color: {BRAND_FILL};
                color: #FFFFFF;
                border: none;
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #2563EB;
            }}
        """)
        self.btn_primary.clicked.connect(self._on_primary_action)
        self.status_row.addWidget(self.btn_primary)

        self.btn_secondary = QPushButton("Check Again")
        self.btn_secondary.setFixedHeight(30)
        self.btn_secondary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_secondary.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {STROKE_CONTROL};
                border-radius: {RADIUS_CONTROL}px;
                padding: 0 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {SURFACE_CARD_HOVER};
            }}
        """)
        self.btn_secondary.clicked.connect(lambda: self.poll_state(force=True))
        self.status_row.addWidget(self.btn_secondary)

        self.main_layout.addLayout(self.status_row)

        # 2. Detailed guidance / Subtext
        self.lbl_subtext = QLabel("")
        self.lbl_subtext.setWordWrap(True)
        self.lbl_subtext.setStyleSheet(f"background: transparent; font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        self.main_layout.addWidget(self.lbl_subtext)

        # 3. Progress bar (for model pull or startup timer)
        self.progress_frame = QWidget()
        pf_layout = QVBoxLayout(self.progress_frame)
        pf_layout.setContentsMargins(0, 4, 0, 0)
        pf_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {SURFACE_INPUT};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {BRAND_FILL};
                border-radius: 3px;
            }}
        """)
        pf_layout.addWidget(self.progress_bar)

        p_sub = QHBoxLayout()
        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setStyleSheet(f"background: transparent; font-size: 11px; color: {TEXT_TERTIARY};")
        p_sub.addWidget(self.lbl_progress_status, 1)

        self.btn_cancel_pull = QPushButton("Cancel")
        self.btn_cancel_pull.setFixedHeight(24)
        self.btn_cancel_pull.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {STATUS_DANGER_TEXT};
                border: none;
                font-size: 11px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        self.btn_cancel_pull.clicked.connect(self._cancel_pull)
        p_sub.addWidget(self.btn_cancel_pull)
        pf_layout.addLayout(p_sub)

        self.progress_frame.hide()
        self.main_layout.addWidget(self.progress_frame)

        # 4. Diagnostics / Error log display
        self.diag_frame = QWidget()
        df_layout = QVBoxLayout(self.diag_frame)
        df_layout.setContentsMargins(0, 4, 0, 0)
        df_layout.setSpacing(4)

        self.lbl_diag_summary = QLabel("")
        self.lbl_diag_summary.setWordWrap(True)
        self.lbl_diag_summary.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {STATUS_DANGER_TEXT}; font-weight: 500;")
        df_layout.addWidget(self.lbl_diag_summary)

        self.txt_diag_log = QTextEdit()
        self.txt_diag_log.setReadOnly(True)
        self.txt_diag_log.setFixedHeight(80)
        self.txt_diag_log.setStyleSheet(f"""
            QTextEdit {{
                background: #0B0E14;
                color: #E6EDF3;
                border: 1px solid {STROKE_CARD};
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 4px;
            }}
        """)
        df_layout.addWidget(self.txt_diag_log)

        self.diag_frame.hide()
        self.main_layout.addWidget(self.diag_frame)

        # 5. Collapsible "Advanced: do it manually"
        self.adv_btn = QPushButton("▾ Advanced: do it manually")
        self.adv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adv_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_TERTIARY};
                border: none;
                text-align: left;
                font-size: 11.5px;
                padding: 2px 0;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)
        self.adv_btn.clicked.connect(self._toggle_advanced)
        self.main_layout.addWidget(self.adv_btn)

        self.adv_content = QWidget()
        adv_l = QVBoxLayout(self.adv_content)
        adv_l.setContentsMargins(4, 2, 4, 4)
        adv_l.setSpacing(6)

        adv_desc = QLabel("If you prefer terminal control, run these commands in Command Prompt or PowerShell:")
        adv_desc.setStyleSheet(f"background: transparent; font-size: 11.5px; color: {TEXT_SECONDARY};")
        adv_l.addWidget(adv_desc)

        cmd_row1 = QHBoxLayout()
        self.lbl_cmd1 = QLabel("ollama serve")
        self.lbl_cmd1.setStyleSheet("background: #0B0E14; color: #58A6FF; font-family: Consolas, monospace; font-size: 11.5px; padding: 4px 8px; border-radius: 4px;")
        cmd_row1.addWidget(self.lbl_cmd1, 1)
        btn_copy1 = QPushButton("Copy")
        btn_copy1.setFixedHeight(26)
        btn_copy1.clicked.connect(lambda: QApplication.clipboard().setText("ollama serve"))
        cmd_row1.addWidget(btn_copy1)
        adv_l.addLayout(cmd_row1)

        cmd_row2 = QHBoxLayout()
        target_m = getattr(self.config, "model_name", "phi3:mini") or "phi3:mini"
        self.lbl_cmd2 = QLabel(f"ollama pull {target_m}")
        self.lbl_cmd2.setStyleSheet("background: #0B0E14; color: #58A6FF; font-family: Consolas, monospace; font-size: 11.5px; padding: 4px 8px; border-radius: 4px;")
        cmd_row2.addWidget(self.lbl_cmd2, 1)
        btn_copy2 = QPushButton("Copy")
        btn_copy2.setFixedHeight(26)
        btn_copy2.clicked.connect(lambda: QApplication.clipboard().setText(self.lbl_cmd2.text()))
        cmd_row2.addWidget(btn_copy2)
        adv_l.addLayout(cmd_row2)

        self.adv_content.hide()
        self.main_layout.addWidget(self.adv_content)

    def start_polling(self):
        """Starts 2-second periodic evaluation timer."""
        self.poll_state(force=True)
        if not self._poll_timer.isActive():
            self._poll_timer.start()

    def stop_polling(self):
        """Stops evaluation timer."""
        self._poll_timer.stop()

    def poll_state(self, force: bool = False):
        """Evaluates state machine and updates UI."""
        if self._is_starting:
            elapsed = time.time() - (self._start_deadline - 30.0)
            remaining = max(0, int(self._start_deadline - time.time()))
            self.lbl_progress_status.setText(f"Starting Ollama in background... {int(elapsed)}s / 30s")
            self.progress_bar.setValue(min(100, int((elapsed / 30.0) * 100)))

            # Check if running now
            target_m = getattr(self.config, "model_name", "phi3:mini") or "phi3:mini"
            base_url = getattr(self.config, "ollama_url", "http://127.0.0.1:11434")
            state = self.state_machine.evaluate(base_url=base_url, target_model=target_m)
            if state in [OllamaState.READY, OllamaState.RUNNING_NO_MODEL]:
                self._is_starting = False
                self.progress_frame.hide()
                self._render_state(state)
                return

            if remaining <= 0:
                self._is_starting = False
                self.progress_frame.hide()
                tail, diag = get_ollama_log_tail()
                self.lbl_diag_summary.setText(f"Ollama did not respond after 30s. {diag}")
                self.txt_diag_log.setPlainText(tail)
                self.diag_frame.show()
                self._render_state(OllamaState.INSTALLED_NOT_RUNNING)
            return

        if self._is_pulling:
            return

        target_m = getattr(self.config, "model_name", "phi3:mini") or "phi3:mini"
        base_url = getattr(self.config, "ollama_url", "http://127.0.0.1:11434")
        state = self.state_machine.evaluate(base_url=base_url, target_model=target_m)
        if state != self._current_state or force:
            self._render_state(state)

    def set_state(self, state: OllamaState):
        """Manually sets and renders a specific Ollama state (used for testing and immediate transitions)."""
        self._render_state(state)

    def _render_state(self, state: OllamaState):
        self._current_state = state
        self.sig_state_changed.emit(state.value)

        target_m = getattr(self.config, "model_name", "phi3:mini") or "phi3:mini"
        self.lbl_cmd2.setText(f"ollama pull {target_m}")

        if state == OllamaState.NOT_INSTALLED:
            self.lbl_icon.setPixmap(get_fluent_icon("arrow_download", color=STATUS_WARNING_TEXT, size=16).pixmap(16, 16))
            self.lbl_headline.setText("Ollama is not installed.")
            self.lbl_headline.setStyleSheet(f"background: transparent; font-size: 13px; font-weight: 600; color: {STATUS_WARNING_TEXT};")
            self.lbl_subtext.setText("Ghostline uses Ollama to run models locally and privately. The installer runs Ollama in the background and can start with Windows, so this setup is needed only once.")
            self.btn_primary.setText("Download Ollama")
            self.btn_primary.show()
            self.btn_secondary.setText("I've installed it: check again")
            self.btn_secondary.show()
            self.diag_frame.hide()

        elif state == OllamaState.INSTALLED_NOT_RUNNING:
            self.lbl_icon.setPixmap(get_fluent_icon("power", color=STATUS_WARNING_TEXT, size=16).pixmap(16, 16))
            self.lbl_headline.setText("Ollama is installed but not running.")
            self.lbl_headline.setStyleSheet(f"background: transparent; font-size: 13px; font-weight: 600; color: {STATUS_WARNING_TEXT};")
            self.lbl_subtext.setText("The Ollama service is not currently active on http://127.0.0.1:11434. Start it to use local models.")
            self.btn_primary.setText("Start Ollama")
            self.btn_primary.show()
            self.btn_secondary.setText("Check Again")
            self.btn_secondary.show()

        elif state == OllamaState.RUNNING_NO_MODEL:
            self.lbl_icon.setPixmap(get_fluent_icon("arrow_download", color=BRAND_TEXT, size=16).pixmap(16, 16))
            self.lbl_headline.setText(f"Download the AI model ({target_m}, about 2.2 GB).")
            self.lbl_headline.setStyleSheet(f"background: transparent; font-size: 13px; font-weight: 600; color: {BRAND_TEXT};")
            self.lbl_subtext.setText(f"Ollama is running, but {target_m} is not downloaded yet. Downloads once and runs fully offline.")
            self.btn_primary.setText("Download model")
            self.btn_primary.show()
            self.btn_secondary.setText("Check Again")
            self.btn_secondary.show()
            self.diag_frame.hide()

        elif state == OllamaState.READY:
            self.lbl_icon.setPixmap(get_fluent_icon("checkmark_circle", color=STATUS_SUCCESS_TEXT, size=16).pixmap(16, 16))
            self.lbl_headline.setText("Ollama · Ready")
            self.lbl_headline.setStyleSheet(f"background: transparent; font-size: 13px; font-weight: 600; color: {STATUS_SUCCESS_TEXT};")
            self.lbl_subtext.setText(f"Running locally on 127.0.0.1:11434 with model '{target_m}'. Answers process 100% on-device.")
            self.btn_primary.hide()
            self.btn_secondary.setText("Check Again")
            self.btn_secondary.show()
            self.diag_frame.hide()

    def _on_primary_action(self):
        if self._current_state == OllamaState.NOT_INSTALLED:
            QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
            self.lbl_subtext.setText("Waiting for the installer to finish… Ghostline is polling automatically.")
            self.btn_primary.setText("Download Page Opened")
            self.btn_primary.setEnabled(False)

        elif self._current_state == OllamaState.INSTALLED_NOT_RUNNING:
            self._start_ollama_click()

        elif self._current_state == OllamaState.RUNNING_NO_MODEL:
            self._download_model_click()

    def _start_ollama_click(self):
        """Starts Ollama detached and initiates 30s polling."""
        ok, msg = self.state_machine.start()
        if not ok:
            self.lbl_diag_summary.setText(msg)
            self.diag_frame.show()
            return

        self._is_starting = True
        self._start_deadline = time.time() + 30.0
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText("Starting Ollama in background... 0s / 30s")
        self.progress_frame.show()
        self.btn_primary.setEnabled(False)

    def _download_model_click(self):
        """Initiates streaming download of target model."""
        target_m = getattr(self.config, "model_name", "phi3:mini") or "phi3:mini"
        base_url = getattr(self.config, "ollama_url", "http://127.0.0.1:11434")

        # Check free disk space
        has_space, free_gb = check_free_disk_space(3.0)
        if not has_space:
            self.lbl_diag_summary.setText(f"Insufficient disk space: {free_gb:.1f} GB available, need at least 3.0 GB.")
            self.diag_frame.show()
            return

        self._is_pulling = True
        self._pull_cancel_event.clear()
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText(f"Connecting to download {target_m}...")
        self.btn_primary.setEnabled(False)

        def _pull_worker():
            def _prog(status, completed, total):
                if total > 0:
                    pct = int((completed / total) * 100)
                    comp_mb = completed / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    msg = f"{status}: {comp_mb:.0f} MB / {tot_mb:.0f} MB ({pct}%)"
                    QTimer.singleShot(0, lambda: self._update_pull_ui(pct, msg))
                else:
                    QTimer.singleShot(0, lambda: self._update_pull_ui(0, status))

            ok, res_msg = pull_ollama_model(
                base_url=base_url,
                model_name=target_m,
                progress_callback=_prog,
                cancel_event=self._pull_cancel_event
            )

            def _finish():
                self._is_pulling = False
                self.progress_frame.hide()
                self.btn_primary.setEnabled(True)
                if ok:
                    self.poll_state(force=True)
                else:
                    self.lbl_diag_summary.setText(res_msg)
                    self.diag_frame.show()

            QTimer.singleShot(0, _finish)

        threading.Thread(target=_pull_worker, daemon=True).start()

    def _update_pull_ui(self, pct: int, msg: str):
        if self._is_pulling:
            self.progress_bar.setValue(pct)
            self.lbl_progress_status.setText(msg)

    def _cancel_pull(self):
        if self._is_pulling:
            self._pull_cancel_event.set()
            self.lbl_progress_status.setText("Cancelling download...")

    def _toggle_advanced(self):
        is_vis = self.adv_content.isVisible()
        self.adv_content.setVisible(not is_vis)
        self.adv_btn.setText("▴ Advanced: do it manually" if not is_vis else "▾ Advanced: do it manually")
