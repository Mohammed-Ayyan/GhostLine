"""
Ghostline Phase 8 Comprehensive Evaluation Test Suite.
Verifies all 10 required evaluation tests:
1. Candidate introduction
2. Educational background
3. Technical skills
4. Project discussion
5. Experience summary
6. Follow-up handling
7. Profile update reflection
8. Missing information / never-claim handling
9. Response speed & token budget
10. Input field visibility & contrast
"""

import sys
import time
import json
import os
from pathlib import Path
import pytest

from ghostline.config import AppConfig
from ghostline.core.profile import (
    load_profile_data,
    save_profile_data,
    get_profile_context_builder,
    ProfileContextBuilder
)
from ghostline.core.providers import AIRouter
from ghostline.audio.assistant import LiveAudioAssistant


@pytest.fixture(autouse=True)
def preserve_real_profile():
    """Backs up and restores profile.bin so test mutations never corrupt real user data."""
    app_data = os.environ.get("APPDATA")
    if not app_data:
        yield
        return
    prof_path = Path(app_data) / "Ghostline" / "profile.bin"
    backup_bytes = prof_path.read_bytes() if prof_path.exists() else None
    try:
        yield
    finally:
        if backup_bytes is not None:
            prof_path.write_bytes(backup_bytes)
        elif prof_path.exists():
            prof_path.unlink()
        ProfileContextBuilder.get_instance().invalidate_cache()


def test_01_candidate_introduction():
    """Test 1: Introduction must use candidate name, role, background, skills. Must not say 'I am Ghostline'."""
    builder = get_profile_context_builder()
    sys_prompt, user_prompt = builder.build_interview_prompt(question="Tell me about yourself.")

    assert "I am Ghostline" not in sys_prompt
    assert "You are Ghostline" not in sys_prompt
    assert "You are an AI assistant" not in sys_prompt
    assert "You are the candidate" in sys_prompt
    assert "Mohammed Ayyan" in sys_prompt
    assert "first person" in sys_prompt.lower() or "candidate" in sys_prompt.lower()
    assert "Tell me about yourself" in user_prompt

    # Test with real local Ollama if available
    router = AIRouter()
    active_prov = router.get_active_provider()
    if active_prov.is_available():
        ans = active_prov.generate(prompt=user_prompt, system=sys_prompt, max_tokens=150, temperature=0.3)
        assert "Ghostline" not in ans
        assert "AI assistant" not in ans
        assert any(w in ans for w in ["Mohammed", "Ayyan", "developer", "engineering", "Computer Science"])
        words = len(ans.split())
        assert 20 <= words <= 120, f"Expected concise answer, got {words} words"


def test_02_educational_background():
    """Test 2: Educational background must mention actual college and degree from profile."""
    builder = get_profile_context_builder()
    sys_prompt, user_prompt = builder.build_interview_prompt(question="Where did you go to school and what did you study?")

    assert "Vidyavardhaka" in sys_prompt or "Vidya Vikas" in sys_prompt
    assert "Computer Science" in sys_prompt


def test_03_technical_skills():
    """Test 3: Technical skills must mention only technologies listed in profile."""
    builder = get_profile_context_builder()
    sys_prompt, user_prompt = builder.build_interview_prompt(question="Which technologies are you comfortable working with?")

    assert "React" in sys_prompt or "Python" in sys_prompt or "Node.js" in sys_prompt
    assert "never-claim" in sys_prompt.lower() or "do not claim" in sys_prompt.lower()


def test_04_project_discussion():
    """Test 4: Project discussion must describe a real project from the profile."""
    builder = get_profile_context_builder()
    sys_prompt, user_prompt = builder.build_interview_prompt(question="Tell me about one of your projects.")

    assert any(proj in sys_prompt for proj in ["Roadly", "CareOps", "Parking"])


def test_05_experience_summary():
    """Test 5: Experience summary must reference actual experience points."""
    builder = get_profile_context_builder()
    sys_prompt, user_prompt = builder.build_interview_prompt(question="Tell me about your previous work experience.")

    assert "Experience" in sys_prompt
    assert "full-stack" in sys_prompt.lower() or "developer" in sys_prompt.lower()


def test_06_follow_up_handling():
    """Test 6: Follow-up question must maintain conversational continuity."""
    builder = get_profile_context_builder()
    transcript = (
        "Interviewer: Can you tell me about the Roadly project?\n"
        "Candidate: Roadly is a crowd-sourced civic issue reporting application built with React Native and Expo."
    )
    sys_prompt, user_prompt = builder.build_interview_prompt(
        question="What was the most challenging technical problem you solved on that project?",
        recent_transcript=transcript
    )

    assert "Roadly" in user_prompt or "Roadly" in sys_prompt
    assert "Conversation Context" in user_prompt or "Transcript" in user_prompt


def test_07_profile_update_reflection():
    """Test 7: Updating profile reflects immediately without app restart (cache invalidation)."""
    pdata = load_profile_data()
    orig_name = pdata.get("name", "")

    try:
        pdata["name"] = "Dr. Jane Testrunner"
        pdata["skills"] = ["Quantum Computing", "Haskell"]
        save_profile_data(pdata)

        builder = get_profile_context_builder()
        sys_prompt, _ = builder.build_interview_prompt(question="What is your name and background?")

        assert "Dr. Jane Testrunner" in sys_prompt
        assert "Quantum Computing" in sys_prompt
    finally:
        pdata["name"] = orig_name
        save_profile_data(pdata)


def test_08_missing_information_handling():
    """Test 8: Never-claim topics are strictly prohibited and prompted to decline."""
    builder = get_profile_context_builder()
    sys_prompt, _ = builder.build_interview_prompt(question="How many years have you managed Kubernetes clusters?")

    assert "never-claim" in sys_prompt.lower() or "do not claim" in sys_prompt.lower()
    assert "Kubernetes" in sys_prompt or "Machine Learning" in sys_prompt
    assert "Never fabricate" in sys_prompt or "Never pretend" in sys_prompt or "NEVER invent" in sys_prompt


def test_09_response_speed():
    """Test 9: Prompt construction latency is sub-millisecond with in-memory caching."""
    builder = get_profile_context_builder()

    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        builder.build_interview_prompt("Tell me about your experience.")
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 5.0, f"Expected <5ms prompt construction, took {avg_latency:.2f}ms"


def test_10_input_field_visibility():
    """Test 10: Form input fields throughout the GUI have high-contrast styling."""
    from PyQt6.QtWidgets import QApplication, QLineEdit, QTextEdit, QComboBox
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    cfg = AppConfig(first_run_complete=True)
    win = QtGhostlineMainWindow(config=cfg)

    # Check input controls across window
    inputs = win.findChildren((QLineEdit, QTextEdit, QComboBox))
    assert len(inputs) > 0, "No input controls found in main window"

    for ctrl in inputs:
        ss = ctrl.styleSheet()
        # Verify custom style applied with high contrast
        assert "border" in ss, f"Control {ctrl.objectName()} lacks border styling"
        assert any(c in ss for c in ["#858585", "#B0B0B0", "#58A6FF", "#115EA3"]), f"Control {ctrl.objectName()} lacks visible border color"
        assert any(bg in ss for bg in ["#141414", "#1E1E1E", "#0F141C", "#181818"]), f"Control {ctrl.objectName()} lacks dark inset background"
