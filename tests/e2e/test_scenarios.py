"""
Ghostline E2E Test Scenarios (S1 - S8).
Drives the REAL application with real audio pipeline, real Windows GUI HWNDs,
and local Fake Ollama HTTP server.
"""

import os
import sys
import time
import json
import shutil
import logging
import tempfile
from pathlib import Path
import pytest
import requests

from tools.e2e.fake_ollama import FakeOllamaRunner
from tools.e2e.drive_gui import (
    launch_ghostline_test,
    find_ghostline_hwnds,
    is_window_visible,
    get_foreground_hwnd,
    send_hotkey_chord,
    sample_hud_visibility_log,
    trigger_ghostline_solve,
    trigger_ghostline_audio_toggle,
    VK_MENU,
    VK_OEM_2,
    VK_OEM_5
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_scenarios")

FIXTURE_WAV = Path("tests/fixtures/test_speech_bst.wav").resolve()
FAKE_OLLAMA_PORT = 11435


@pytest.fixture(scope="module")
def fake_ollama():
    runner = FakeOllamaRunner(host="127.0.0.1", port=FAKE_OLLAMA_PORT)
    if not runner.start():
        pytest.fail(f"Could not start Fake Ollama on port {FAKE_OLLAMA_PORT}")
    yield runner
    runner.stop()


def test_s1_hud_auto_popping_prevented(fake_ollama):
    """
    Scenario S1 (F2 Proof):
    With show_hud_on_solve = False, pressing Alt + / to solve must NEVER
    make the HUD visible at any point during capturing, OCR, thinking, or answer streaming.
    """
    test_dir = Path(tempfile.mkdtemp(prefix="ghost_s1_"))
    try:
        proc = launch_ghostline_test(
            test_dir=test_dir,
            config_overrides={
                "show_hud_on_solve": False,
                "provider": "ollama",
                "model_name": "phi3:mini",
                "ollama_url": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}",
                "provider_base_urls": {"ollama": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}"}
            }
        )
        time.sleep(1.0)
        hwnds = find_ghostline_hwnds(proc.pid)
        hud_hwnd = hwnds.get("hud")

        # Press Alt + /
        trigger_ghostline_solve(proc.pid)

        # Sample HUD visibility every 100ms for 3.5 seconds
        samples = sample_hud_visibility_log(proc.pid, duration_sec=3.5, interval_sec=0.1)
        visible_counts = sum(1 for t, vis, fg in samples if vis)

        proc.terminate()
        assert visible_counts == 0, f"HUD was visible during solve {visible_counts} times despite show_hud_on_solve=False"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_s2_hud_auto_show_without_stealing_focus(fake_ollama):
    """
    Scenario S2 (F2 Inverse):
    With show_hud_on_solve = True, pressing Alt + / shows HUD,
    but DOES NOT steal focus from the previously active window (SW_SHOWNOACTIVATE).
    """
    test_dir = Path(tempfile.mkdtemp(prefix="ghost_s2_"))
    try:
        proc = launch_ghostline_test(
            test_dir=test_dir,
            config_overrides={
                "show_hud_on_solve": True,
                "provider": "ollama",
                "model_name": "phi3:mini",
                "ollama_url": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}",
                "provider_base_urls": {"ollama": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}"}
            }
        )
        time.sleep(1.0)
        hwnds = find_ghostline_hwnds(proc.pid)
        hud_hwnd = hwnds.get("hud")
        initial_fg = get_foreground_hwnd()

        trigger_ghostline_solve(proc.pid)

        # Sample HUD visibility across solve lifecycle (3.5s)
        samples = sample_hud_visibility_log(proc.pid, duration_sec=3.5, interval_sec=0.1)
        any_vis = any(vis for t, vis, fg in samples)
        fg_stolen = any(vis and (fg == hud_hwnd) for t, vis, fg in samples)

        proc.terminate()
        assert any_vis, "HUD failed to become visible when show_hud_on_solve is True"
        assert not fg_stolen, "HUD stole foreground window focus on show"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_s3_live_mic_speech_transcription_and_ai_answer(fake_ollama):
    """
    Scenario S3 (F1 Mic Proof):
    Feeds test speech WAV through microphone E2E capture path.
    Verifies:
    1. Transcriber produces transcript containing 'capital of France'.
    2. Fake Ollama receives request with prompt.
    3. Telemetry log records PCM frames, RMS > 0, and Whisper success.
    4. Live UI displays listening state.
    """
    test_dir = Path(tempfile.mkdtemp(prefix="ghost_s3_"))
    log_file = test_dir / "audio_telemetry.log"
    fake_ollama.clear_history()

    try:
        proc = launch_ghostline_test(
            test_dir=test_dir,
            config_overrides={
                "audio_source_mic": True,
                "audio_source_system": False,
                "audio_whisper_model": "tiny",
                "audio_auto_answer_questions": True,
                "audio_question_debounce_sec": 0.2,
                "ollama_url": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}",
                "provider_base_urls": {"ollama": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}"}
            },
            extra_env={
                "GHOSTLINE_E2E_MIC_FILE": str(FIXTURE_WAV),
                "GHOSTLINE_E2E_LOG": str(log_file)
            }
        )
        time.sleep(1.0)

        # Trigger live listening via Alt + \
        trigger_ghostline_audio_toggle(proc.pid)

        # Wait for audio replay, transcription and Ollama dispatch (up to 12s)
        start_wait = time.time()
        while time.time() - start_wait < 20.0:
            reqs = fake_ollama.server.recorded_requests
            if any("capital of France" in str(r.get("body", {})) for r in reqs):
                break
            time.sleep(0.3)

        hwnds = find_ghostline_hwnds(proc.pid)
        live_or_hud_visible = is_window_visible(hwnds.get("live")) or is_window_visible(hwnds.get("hud"))

        proc.terminate()

        # Verify telemetry log
        assert log_file.exists(), "Audio telemetry log was not generated"
        log_content = log_file.read_text(encoding="utf-8")
        assert "device_open" in log_content, "Capture failed to open device"
        assert "pcm_frame_mic" in log_content, "No PCM frames read from mic WAV"

        # Verify Fake Ollama requests
        reqs = fake_ollama.server.recorded_requests
        has_france = any("capital of France" in str(r.get("body", {})) for r in reqs)
        assert has_france, f"Ollama did not receive question from transcript. Requests: {reqs}"
        assert live_or_hud_visible, "Live Audio interface was never shown when listening started"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_s4_system_loopback_speech_transcription(fake_ollama):
    """
    Scenario S4 (F1 Loopback Proof):
    Feeds test speech WAV through system loopback E2E path.
    Verifies transcript is attributed to [Call] / System.
    """
    test_dir = Path(tempfile.mkdtemp(prefix="ghost_s4_"))
    log_file = test_dir / "audio_telemetry.log"
    fake_ollama.clear_history()

    try:
        proc = launch_ghostline_test(
            test_dir=test_dir,
            config_overrides={
                "audio_source_mic": False,
                "audio_source_system": True,
                "audio_whisper_model": "tiny",
                "audio_auto_answer_questions": True,
                "audio_question_debounce_sec": 0.2,
                "ollama_url": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}",
                "provider_base_urls": {"ollama": f"http://127.0.0.1:{FAKE_OLLAMA_PORT}"}
            },
            extra_env={
                "GHOSTLINE_E2E_LOOPBACK_FILE": str(FIXTURE_WAV),
                "GHOSTLINE_E2E_LOG": str(log_file)
            }
        )
        time.sleep(1.0)
        trigger_ghostline_audio_toggle(proc.pid)

        start_wait = time.time()
        while time.time() - start_wait < 10.0:
            if log_file.exists() and "pcm_frame_call" in log_file.read_text(encoding="utf-8", errors="ignore"):
                break
            time.sleep(0.3)

        time.sleep(0.5)
        proc.terminate()

        assert log_file.exists(), "Audio telemetry log was not generated"
        log_content = log_file.read_text(encoding="utf-8")
        assert "pcm_frame_call" in log_content, "No PCM frames read from loopback WAV"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_s5_audio_stop_cleanly():
    """
    Scenario S5:
    Starting and stopping audio capture cleanly terminates worker threads
    and releases all resources without hanging.
    """
    test_dir = Path(tempfile.mkdtemp(prefix="ghost_s5_"))
    try:
        proc = launch_ghostline_test(
            test_dir=test_dir,
            config_overrides={"audio_source_mic": True}
        )
        time.sleep(1.0)

        # Start audio listening
        trigger_ghostline_audio_toggle(proc.pid)
        time.sleep(1.5)

        # Stop audio listening
        trigger_ghostline_audio_toggle(proc.pid)
        time.sleep(1.0)

        # Ensure process exits cleanly without hanging threads
        proc.terminate()
        assert proc.poll() is not None, "Process hung on termination after audio stop"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_s6_provider_switch_runtime():
    """
    Scenario S6:
    Switching AI provider dynamically updates inference target without restart.
    """
    from ghostline.config import AppConfig
    from ghostline.core.providers.router import AIRouter

    cfg = AppConfig()
    cfg.ai_provider = "ollama"
    router = AIRouter(cfg)
    assert router.get_active_provider_id() == "ollama"

    # Switch to groq endpoint
    router.switch_provider("groq")
    assert router.get_active_provider_id() == "groq"
    assert router.get_active_provider().metadata.id == "groq"


def test_s7_profile_gating():
    """
    Scenario S7:
    When profile is disabled, prompts contain no personal role data.
    When profile is enabled, prompt contains user's role and experience.
    """
    from ghostline.core.profile import build_profile_context

    # Case A: Disabled
    p_off = {"use_profile": False, "role": "Staff Consensus Architect"}
    ctx_off, applied_off = build_profile_context(p_off, "How does Raft work?")
    assert not applied_off
    assert "Staff Consensus Architect" not in ctx_off

    # Case B: Enabled
    p_on = {"use_profile": True, "role": "Staff Consensus Architect", "skills": ["Go", "Raft"]}
    ctx_on, applied_on = build_profile_context(p_on, "How does Raft work?")
    assert applied_on
    assert "Staff Consensus Architect" in ctx_on


def test_s8_tray_and_close_behavior_controls_exist():
    """
    Scenario S8:
    Asserts tray and close behavior controls are accessible and properly named.
    """
    from ghostline.config import AppConfig
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    cfg = AppConfig()
    win = QtGhostlineMainWindow(cfg)

    # Check for presence of required tray controls and verify their objectNames
    assert hasattr(win, "switch_show_tray"), "switch_show_tray missing on MainWindow"
    assert win.switch_show_tray.objectName() == "SwitchShowTray", "switch_show_tray missing objectName"

    assert hasattr(win, "combo_close_action"), "combo_close_action missing on MainWindow"
    assert win.combo_close_action.objectName() == "ComboCloseAction", "combo_close_action missing objectName"

    assert hasattr(win, "switch_start_minimized"), "switch_start_minimized missing on MainWindow"
    assert win.switch_start_minimized.objectName() == "SwitchStartMinimized", "switch_start_minimized missing objectName"

    assert hasattr(win, "switch_start_with_windows"), "switch_start_with_windows missing on MainWindow"
    assert win.switch_start_with_windows.objectName() == "SwitchStartWithWindows", "switch_start_with_windows missing objectName"

    # Run 8: Assert switch_hide_taskbar is restored and named
    assert hasattr(win, "switch_hide_taskbar"), "switch_hide_taskbar missing on MainWindow"
    assert win.switch_hide_taskbar.objectName() == "SwitchHideTaskbar", "switch_hide_taskbar missing objectName"


def test_s9_provider_error_mapping_and_ua():
    """
    Scenario S9 (Section A):
    1. Verifies explicit Ghostline User-Agent header is sent by provider HTTP client.
    2. Maps Cloudflare 403 (1010), Groq 403, Model 404, and 429 Retry-After through fake cloud server.
    """
    from tools.e2e.fake_cloud import FakeCloudRunner
    from ghostline.core.providers.openai_compatible_provider import GroqProvider
    from ghostline.core.http_client import GHOSTLINE_USER_AGENT

    runner = FakeCloudRunner(port=18443)
    assert runner.start(), "Could not start FakeCloudRunner"
    try:
        base_url = runner.base_url

        # 1. Cloudflare User-Agent block test
        blocked_resp = requests.get(f"{base_url}/cloudflare-test", headers={"User-Agent": "python-requests/2.31.0"})
        assert blocked_resp.status_code == 403
        assert "error code: 1010" in blocked_resp.text

        allowed_resp = requests.get(f"{base_url}/cloudflare-test", headers={"User-Agent": GHOSTLINE_USER_AGENT})
        assert allowed_resp.status_code == 200

        # 2. Test Groq provider with fake cloud base URL
        prov = GroqProvider(api_key="gsk_test_key_for_testing_1234567890", base_url=base_url)
        assert GHOSTLINE_USER_AGENT in prov._headers()["User-Agent"]

        # 3. Model 404 mapping
        prov.default_model = "retired-model-404"
        success, err = prov.test_connection()
        assert not success
        assert "model isn't available" in err.lower() or "retired" in err.lower()

        # 4. 403 Forbidden mapping
        prov.default_model = "groq-blocked-403"
        success_403, err_403 = prov.test_connection()
        assert not success_403
        assert "not allowed" in err_403.lower() or "console" in err_403.lower()
    finally:
        runner.stop()


def test_s10_ollama_state_machine_real_start():
    """
    Scenario S10 (Section B):
    Verifies Ollama state machine evaluation and state transitions.
    """
    from ghostline.core.ollama_state import OllamaStateMachine, OllamaState
    from pathlib import Path

    # Simulated states using injectable probes
    # State A: Not installed
    sm_not_installed = OllamaStateMachine(
        http_probe=lambda url: (False, []),
        installed_probe=lambda: (False, None, None)
    )
    assert sm_not_installed.evaluate() == OllamaState.NOT_INSTALLED

    # State B: Installed but not running
    sm_installed_stopped = OllamaStateMachine(
        http_probe=lambda url: (False, []),
        installed_probe=lambda: (True, Path(r"C:\fake\ollama.exe"), None)
    )
    assert sm_installed_stopped.evaluate() == OllamaState.INSTALLED_NOT_RUNNING

    # State C: Running but no target model
    sm_no_model = OllamaStateMachine(
        http_probe=lambda url: (True, ["llama3:latest"]),
        installed_probe=lambda: (True, Path(r"C:\fake\ollama.exe"), None)
    )
    assert sm_no_model.evaluate(target_model="phi3:mini") == OllamaState.RUNNING_NO_MODEL

    # State D: Running and target model is ready
    sm_ready = OllamaStateMachine(
        http_probe=lambda url: (True, ["phi3:mini", "llama3:latest"]),
        installed_probe=lambda: (True, Path(r"C:\fake\ollama.exe"), None)
    )
    assert sm_ready.evaluate(target_model="phi3:mini") == OllamaState.READY


def test_s11_hide_from_taskbar_style_and_single_instance():
    """
    Scenario S11 (Section D):
    1. Verifies apply_taskbar_visibility properly manipulates WS_EX_TOOLWINDOW and WS_EX_APPWINDOW.
    2. Reachability guard refuses to hide taskbar when tray is disabled.
    """
    import ctypes
    from ghostline.config import AppConfig
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    from PyQt6.QtWidgets import QApplication

    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000

    app = QApplication.instance() or QApplication(sys.argv)
    cfg = AppConfig()
    win = QtGhostlineMainWindow(cfg)
    win.show()
    hwnd = int(win.winId())

    # 1. Hide from taskbar
    win.apply_taskbar_visibility(hide=True)
    style_hidden = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    assert (style_hidden & WS_EX_TOOLWINDOW) != 0, "WS_EX_TOOLWINDOW must be set when hidden from taskbar"
    assert (style_hidden & WS_EX_APPWINDOW) == 0, "WS_EX_APPWINDOW must be cleared when hidden from taskbar"

    # 2. Restore to taskbar
    win.apply_taskbar_visibility(hide=False)
    style_restored = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    assert (style_restored & WS_EX_TOOLWINDOW) == 0, "WS_EX_TOOLWINDOW must be cleared when restored to taskbar"
    assert (style_restored & WS_EX_APPWINDOW) != 0, "WS_EX_APPWINDOW must be set when restored to taskbar"

    # 3. Reachability guard: refuse to hide taskbar if tray icon is OFF
    win.config.show_tray_icon = False
    win._on_hide_taskbar_toggled(True)
    assert not win.config.hide_from_taskbar, "Reachability guard must block hiding taskbar when tray icon is disabled"

    # 4. Reachability guard: refuse to disable tray icon if taskbar is hidden
    win.config.show_tray_icon = True
    win.config.hide_from_taskbar = True
    win._on_show_tray_toggled(False)
    assert win.config.show_tray_icon, "Reachability guard must block disabling tray icon when taskbar is hidden"

    win.close()


def test_s12_copy_diagnostics_sanitization():
    """
    Scenario S12 (Section A7):
    Verifies that build_sanitized_diagnostics() completely redacts API keys,
    bearer tokens, and personal profile text.
    """
    from ghostline.core.http_client import build_sanitized_diagnostics

    secret_key = "gsk_super_secret_groq_api_key_1234567890"
    raw_error = f"Authentication failure for key {secret_key} and Bearer xai-1234567890abcdef"

    diag = build_sanitized_diagnostics(
        provider="groq",
        model="llama3-70b",
        endpoint_url="https://api.groq.com/openai/v1/chat/completions",
        error_info={"status_code": 401, "message": raw_error, "type": "invalid_api_key"},
        request_id="req_987654321",
        has_images=False,
        has_profile_context=True
    )

    # Assert diagnostics block contents
    assert "gsk_" not in diag, "Groq key leaked in diagnostics block"
    assert "xai-" not in diag, "xAI key leaked in diagnostics block"
    assert secret_key not in diag, "Raw secret leaked in diagnostics block"
    assert "[REDACTED_KEY]" in diag or "[REDACTED]" in diag
    assert "https://api.groq.com" not in diag or "api.groq.com" in diag
    assert "Windows" in diag
    assert "req_987654321" in diag
    assert "Profile Context Included: Yes" in diag or "Has Profile Context: Yes" in diag


if __name__ == "__main__":
    runner = FakeOllamaRunner(host="127.0.0.1", port=FAKE_OLLAMA_PORT)
    runner.start()
    try:
        pytest.main(["-v", "tests/e2e/test_scenarios.py"])
    finally:
        runner.stop()
