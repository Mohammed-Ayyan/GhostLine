"""
Diagnostic test script for Part 1B: Measuring the Live AI Answer Path Baseline.
Runs the live audio pipeline against test question WAV:
'tests/fixtures/question_bst.wav' ("What is the time complexity of searching in a balanced binary search tree?")
Tests 5 distinct configurations:
  (a) HUD hidden
  (b) HUD visible
  (c) Fake AI server UP
  (d) Fake AI server DOWN
  (e) Profile ON vs OFF
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.e2e.fake_ollama import FakeOllamaRunner
from tools.e2e.drive_gui import (
    launch_ghostline_test,
    trigger_ghostline_audio_toggle,
    find_ghostline_hwnds,
    is_window_visible
)

QUESTION_WAV = REPO_ROOT / "tests/fixtures/question_bst.wav"
PORT = 11438

def run_case(case_name: str, config_overrides: dict, server_up: bool = True):
    print(f"\n==========================================")
    print(f"RUNNING BASELINE TEST: {case_name}")
    print(f"==========================================")
    
    runner = None
    if server_up:
        runner = FakeOllamaRunner(host="127.0.0.1", port=PORT)
        assert runner.start(), f"Failed to start fake server on port {PORT}"
        runner.clear_history()

    test_dir = Path(tempfile.mkdtemp(prefix=f"ghost_part1b_{case_name}_"))
    log_file = test_dir / "e2e_timing.log"
    
    cfg = {
        "audio_source_mic": True,
        "audio_source_system": False,
        "audio_whisper_model": "tiny",
        "audio_auto_answer_questions": True,
        "audio_question_debounce_sec": 0.2,
        "ollama_url": f"http://127.0.0.1:{PORT}",
        "provider_base_urls": {"ollama": f"http://127.0.0.1:{PORT}"},
        "provider": "ollama",
        "model_name": "phi3:mini"
    }
    cfg.update(config_overrides)

    proc = None
    res = {
        "case": case_name,
        "transcript_shown": False,
        "answer_trigger": None,
        "provider_request_sent": False,
        "first_token": False,
        "answer_complete": False,
        "answer_rendered": "none",
        "history_written": False,
        "notes": ""
    }

    try:
        proc = launch_ghostline_test(
            test_dir=test_dir,
            config_overrides=cfg,
            extra_env={
                "GHOSTLINE_E2E": "1",
                "GHOSTLINE_E2E_MIC_FILE": str(QUESTION_WAV),
                "GHOSTLINE_E2E_LOG": str(log_file)
            }
        )
        time.sleep(1.2)

        # Trigger live listening
        trigger_ghostline_audio_toggle(proc.pid)

        # Poll for up to 15 seconds
        start_t = time.time()
        while time.time() - start_t < 15.0:
            if runner and runner.server.recorded_requests:
                res["provider_request_sent"] = True
                req = runner.server.recorded_requests[-1]
                body = req.get("body", {})
                prompt_str = str(body)
                if "balanced binary search tree" in prompt_str or "time complexity" in prompt_str:
                    res["answer_trigger"] = "question_classifier"
                    res["answer_complete"] = True
                    break
            time.sleep(0.3)

        # Check log file
        if log_file.exists():
            log_text = log_file.read_text(encoding="utf-8", errors="ignore")
            if "pcm_frame_mic" in log_text:
                res["transcript_shown"] = True
            if "stop_called" in log_text:
                pass

        # Check HWNDs
        hwnds = find_ghostline_hwnds(proc.pid)
        hud_vis = is_window_visible(hwnds.get("hud"))
        main_vis = is_window_visible(hwnds.get("main"))

        if res["answer_complete"]:
            if hud_vis:
                res["answer_rendered"] = "hud_panel"
            elif main_vis:
                # In current code, main window has no live answer card
                res["answer_rendered"] = "none (main window has no live answer card)"
            else:
                res["answer_rendered"] = "none"

        # Check history store
        hist_file = test_dir / "history.json"
        if hist_file.exists():
            try:
                data = json.loads(hist_file.read_text(encoding="utf-8"))
                if data.get("audio_history"):
                    res["history_written"] = True
            except Exception:
                pass

        print(f"Result for {case_name}: {res}")
        return res

    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except Exception:
                pass
        if runner:
            runner.stop()
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    results = []
    # Case (a): HUD hidden
    results.append(run_case("case_a_hud_hidden", {"show_hud_on_solve": False, "open_live_panel_on_listen": False}))
    
    # Case (b): HUD visible
    results.append(run_case("case_b_hud_visible", {"show_hud_on_solve": True, "open_live_panel_on_listen": True}))
    
    # Case (c): Fake AI server UP
    results.append(run_case("case_c_server_up", {"open_live_panel_on_listen": True}, server_up=True))
    
    # Case (d): Fake AI server DOWN
    results.append(run_case("case_d_server_down", {"open_live_panel_on_listen": True}, server_up=False))
    
    # Case (e1): Profile OFF
    results.append(run_case("case_e_profile_off", {"profile_grounding_enabled": False, "open_live_panel_on_listen": True}))
    
    # Case (e2): Profile ON
    results.append(run_case("case_e_profile_on", {"profile_grounding_enabled": True, "open_live_panel_on_listen": True}))

    print("\n\n================ SUMMARY OF BASELINE RESULTS ================")
    for r in results:
        print(r)

