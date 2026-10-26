import time
import threading
from unittest.mock import MagicMock, patch
import pytest

from ghostline.audio import LiveAudioAssistant, TranscriptSegment


def make_segment(text: str, source: str = "call", seg_id: int = 1) -> TranscriptSegment:
    t = time.time()
    lbl = "[Call]" if source == "call" else "[You]"
    return TranscriptSegment(
        id=seg_id,
        timestamp=t,
        time_str="12:00:00",
        source=source,
        speaker_label=lbl,
        text=text
    )


class TestLiveAudioAnswersPipeline:
    """
    Focused regression tests for Live Audio Answers pipeline:
    - Alt + Q triggers answer generation
    - Rolling context accumulation and inclusion in model prompt
    - Generated output delivery to audio panel
    - Automatic question detection where supported
    - Empty transcript and error feedback
    - Concurrency/duplicate request prevention
    """

    def test_recent_transcript_context_included_in_model_request(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Python uses the Global Interpreter Lock (GIL) for memory thread-safety."

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            model_name="phi3:mini",
            max_context_turns=10,
            auto_answer_questions=False
        )

        # Accumulate interview transcript segments
        seg1 = make_segment("Can you describe how Python manages multi-threading?", source="call", seg_id=1)
        seg2 = make_segment("In CPython, multi-threading is constrained by the GIL.", source="mic", seg_id=2)
        assistant.add_transcript_segment(seg1)
        assistant.add_transcript_segment(seg2)

        # Trigger manual ask (Alt + Q)
        assistant.ask(custom_query=None)

        # Wait for background thread
        time.sleep(0.3)

        assert mock_llm.generate.called
        call_kwargs = mock_llm.generate.call_args[1]
        prompt = call_kwargs.get("prompt", "")
        assert "Can you describe how Python manages multi-threading?" in prompt
        assert "In CPython, multi-threading is constrained by the GIL." in prompt
        assert "Ghostline Live AI Assistant" in prompt

    def test_generated_output_reaches_visible_audio_panel_callback(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = (
            "Here is the solution in Python:\n"
            "```python\ndef reverse_str(s):\n    return s[::-1]\n```\n"
            "This runs in O(N) time."
        )

        on_answer_mock = MagicMock()
        on_thinking_mock = MagicMock()

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            model_name="phi3:mini",
            on_question_detected=on_thinking_mock,
            on_answer=on_answer_mock,
            auto_answer_questions=False
        )

        seg = make_segment("Write a function to reverse a string.", source="call")
        assistant.add_transcript_segment(seg)

        assistant.ask(custom_query=None)
        time.sleep(0.3)

        # Verify on_question_detected (thinking state) was called
        assert on_thinking_mock.called

        # Verify on_answer was called with question, answer, and code snippet
        assert on_answer_mock.called
        args, kwargs = on_answer_mock.call_args
        question_stem = args[0]
        answer_text = args[1]
        code_snippet = args[2]

        assert "Write a function to reverse a string." in question_stem
        assert "This runs in O(N) time." in answer_text or "reverse_str" in answer_text
        assert code_snippet is not None
        assert "def reverse_str" in code_snippet

    def test_empty_transcript_shows_actionable_error(self):
        mock_llm = MagicMock()
        on_error_mock = MagicMock()
        on_status_mock = MagicMock()

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            model_name="phi3:mini",
            on_error=on_error_mock,
            on_status=on_status_mock,
            auto_answer_questions=False
        )

        # Trigger ask with empty context
        assistant.ask(custom_query=None)
        time.sleep(0.2)

        # Ensure LLM was NOT called
        assert not mock_llm.generate.called

        # Actionable error was emitted
        assert on_error_mock.called
        err_msg = on_error_mock.call_args[0][0]
        assert "No audio transcript recorded yet" in err_msg
        assert "Alt+A" in err_msg

    def test_repeated_hotkeys_prevent_duplicate_concurrent_requests(self):
        call_count = {"count": 0}

        def slow_generate(*args, **kwargs):
            call_count["count"] += 1
            time.sleep(0.4)
            return "Answer"

        mock_llm = MagicMock()
        mock_llm.generate.side_effect = slow_generate

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            model_name="phi3:mini",
            auto_answer_questions=False
        )

        seg = make_segment("Explain binary search complexity.", source="call")
        assistant.add_transcript_segment(seg)

        # First ask begins inference
        assistant.ask(custom_query=None)
        time.sleep(0.05)

        # Second overlapping ask while thinking must be rejected
        assistant.ask(custom_query=None)
        assistant.ask(custom_query=None)

        time.sleep(0.5)

        # Exactly 1 inference execution occurred
        assert call_count["count"] == 1

    def test_automatic_question_detection_triggers_inference(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "A process has independent memory; threads share memory."

        on_answer_mock = MagicMock()

        assistant = LiveAudioAssistant(
            ollama_client=mock_llm,
            model_name="phi3:mini",
            on_answer=on_answer_mock,
            auto_answer_questions=True,
            debounce_sec=0.1
        )

        # Utterance with clear question
        q_seg = make_segment("What is the difference between a process and a thread?", source="call")
        assistant.add_transcript_segment(q_seg)

        # Wait for debounce timer (0.1s) + worker execution
        time.sleep(0.4)

        assert mock_llm.generate.called
        assert on_answer_mock.called
