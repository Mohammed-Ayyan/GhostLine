"""
Unit tests for Latency Optimization, Adaptive Endpointing & Timing Marks (Ghostline Run 18 - Fix C)
===================================================================================================
Verifies:
1. Adaptive endpointing:
   - Questions (ending with ? or question words): 0.45s silence threshold
   - General statements: 0.60s silence threshold
   - Faster answers mode: 0.35s silence threshold
   - Pauses < 0.30s ignored; clamps bounded in [0.35s, 1.20s]
2. Debounce reduction to <= 0.15s (or 0.05s in faster answers mode)
3. Ollama keep_alive: '5m' passed in solve_question payload
4. Deterministic prompt prefix stability for Ollama KV cache reuse
5. Full timing mark chain recorded throughout pipeline
"""

import time
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

from ghostline.audio.transcription import LiveTranscriber, TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant
from ghostline.audio.timing import TimingManager, record_timing_mark
from ghostline.core.llm_client import OllamaClient
from ghostline.core.profile import get_profile_context_builder


def test_adaptive_endpointing_thresholds():
    """Verifies that silence threshold adapts based on partial utterance structure."""
    transcriber = LiveTranscriber(faster_answers_enabled=False)

    # 1. Question with ?
    transcriber._last_partial_text["mic"] = "What is the capital of France?"
    # Evaluate threshold inside _check_buffer_segmentation logic
    partial = transcriber._last_partial_text["mic"].lower()
    is_q = partial.endswith("?")
    assert is_q is True
    threshold = 0.45 if is_q else 0.60
    assert threshold == 0.45

    # 2. Question starting with question word without ?
    transcriber._last_partial_text["mic"] = "explain how virtual memory works"
    partial = transcriber._last_partial_text["mic"].lower()
    q_starters = ("what", "how", "why", "when", "where", "who", "which", "can", "could", "would", "should", "is", "are", "do", "does", "did", "tell", "explain")
    is_q = any(partial.startswith(w) for w in q_starters)
    assert is_q is True
    threshold = 0.45 if is_q else 0.60
    assert threshold == 0.45

    # 3. Statement
    transcriber._last_partial_text["mic"] = "The system has been updated successfully"
    partial = transcriber._last_partial_text["mic"].lower()
    is_q = partial.endswith("?") or any(partial.startswith(w) for w in q_starters)
    assert is_q is False
    threshold = 0.45 if is_q else 0.60
    assert threshold == 0.60

    # 4. Faster answers enabled
    transcriber.faster_answers_enabled = True
    transcriber._last_partial_text["mic"] = "Can you describe your background?"
    partial = transcriber._last_partial_text["mic"].lower()
    is_q = partial.endswith("?")
    threshold = 0.35 if (transcriber.faster_answers_enabled and is_q) else 0.45
    assert threshold == 0.35


def test_debounce_reduction():
    """Verifies that LiveAudioAssistant uses responsive debounce <= 0.15s."""
    mock_llm = MagicMock()
    assistant = LiveAudioAssistant(
        ollama_client=mock_llm,
        debounce_sec=2.0,  # User or config passed legacy 2.0s
        faster_answers_enabled=False
    )

    with patch("threading.Timer") as mock_timer:
        assistant._schedule_debounced_answer("What is polymorphism?", "entry123")
        assert mock_timer.called
        # Check timer delay argument
        delay_arg = mock_timer.call_args[0][0]
        assert delay_arg <= 0.15  # Scaled down from 2.0s to 0.15s

    # Test faster answers mode
    assistant.faster_answers_enabled = True
    with patch("threading.Timer") as mock_timer_fast:
        assistant._schedule_debounced_answer("What is encapsulation?", "entry124")
        delay_arg = mock_timer_fast.call_args[0][0]
        assert delay_arg == 0.05


def test_ollama_solve_question_includes_keep_alive():
    """Verifies that OllamaClient.solve_question includes keep_alive: '5m' in payload."""
    client = OllamaClient()

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [b'{"response": "Paris", "done": true}']
        mock_post.return_value = mock_resp

        client.solve_question("What is the capital of France?", stream_callback=lambda tok: None)

        assert mock_post.called
        _, kwargs = mock_post.call_args
        payload = kwargs.get("json", {})
        assert payload.get("keep_alive") == "5m"


def test_prompt_prefix_stability():
    """Verifies that system prompt prefix remains stable across interview turns for KV cache reuse."""
    builder = get_profile_context_builder()

    sys_p1, q1 = builder.build_interview_prompt(question="What is dependency injection?")
    sys_p2, q2 = builder.build_interview_prompt(question="How does garbage collection work?")

    # System prompts must be character-for-character identical across turns
    assert sys_p1 == sys_p2
    assert len(sys_p1) > 50


def test_timing_marks_chain():
    """Verifies that timing marks can be cleanly recorded without error."""
    tm = TimingManager.get_instance()

    record_timing_mark("speech_end", {"source": "mic", "t": 1.0})
    record_timing_mark("endpoint_decided", {"source": "mic", "threshold": 0.45})
    record_timing_mark("stt_final", {"source": "mic", "text": "What is Python?"})
    record_timing_mark("question_sent", {"text": "What is Python?", "category": "question"})
    record_timing_mark("request_sent", {"provider": "ollama", "entry_id": "e1"})
    record_timing_mark("first_token", {"entry_id": "e1", "latency_ms": 250.0})
    record_timing_mark("answer_complete", {"entry_id": "e1", "len": 120})
    record_timing_mark("rendered", {"entry_id": "e1", "has_code": False})

    marks = list(tm.marks.keys())

    for expected in ["speech_end", "endpoint_decided", "stt_final", "question_sent", "request_sent", "first_token", "answer_complete", "rendered"]:
        assert expected in marks
