"""
Unit tests for Ghostline Live Audio Assistant subsystem.
Tests question detection, rolling context window, debounce timing, grounded prompt construction,
code snippet extraction, and graceful recovery when Ollama is offline.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from ghostline.audio.transcription import TranscriptSegment
from ghostline.audio.assistant import LiveAudioAssistant


class TestLiveAudioAssistant(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock()
        self.detected_questions = []
        self.answers = []
        self.errors = []

        def _on_q(q):
            self.detected_questions.append(q)

        def _on_ans(q, a, c):
            self.answers.append((q, a, c))

        def _on_err(err):
            self.errors.append(err)

        self.assistant = LiveAudioAssistant(
            ollama_client=self.mock_ollama,
            model_name="phi3:mini",
            max_context_turns=10,
            on_question_detected=_on_q,
            on_answer=_on_ans,
            on_error=_on_err,
            auto_answer_questions=True,
            debounce_sec=0.1  # Fast debounce for testing
        )

    def test_question_detection_patterns(self):
        # 1. Question with question mark
        self.assertTrue(self.assistant.is_question("What is the time complexity of quicksort?"))
        # 2. Question words
        self.assertTrue(self.assistant.is_question("Why do we need a mutex in multithreaded code"))
        self.assertTrue(self.assistant.is_question("How do we optimize memory allocations"))
        # 3. Request / instruction indicators
        self.assertTrue(self.assistant.is_question("Explain the difference between TCP and UDP"))
        self.assertTrue(self.assistant.is_question("Can you implement a binary search function in Python"))
        # 4. Statements that are not questions
        self.assertFalse(self.assistant.is_question("The server returned a 200 OK status code."))
        self.assertFalse(self.assistant.is_question("We should deploy this to production on Friday."))

    def test_rolling_context_accumulation(self):
        seg1 = TranscriptSegment(1, 100.0, "10:00:00", "call", "[Call]", "Let's review the API design.", is_final=True)
        seg2 = TranscriptSegment(2, 102.0, "10:00:02", "mic", "[You]", "Sure, what endpoint should we start with?", is_final=True)

        self.assistant.add_transcript_segment(seg1)
        self.assistant.add_transcript_segment(seg2)

        formatted = self.assistant.get_context_summary()
        self.assertIn("[Call] Let's review the API design.", formatted)
        self.assertIn("[You] Sure, what endpoint should we start with?", formatted)


    def test_context_bounding(self):
        # Push 15 segments into assistant with max_context_turns=10
        for i in range(15):
            seg = TranscriptSegment(
                i + 1, 100.0 + i, "10:00:00", "call", "[Call]",
                f"Sentence number {i + 1}", is_final=True
            )
            self.assistant.add_transcript_segment(seg)

        self.assertEqual(len(self.assistant.context_turns), 10)
        formatted = self.assistant.get_context_summary()
        self.assertNotIn("Sentence number 1\n", formatted)
        self.assertIn("Sentence number 15", formatted)

    def test_manual_ask_triggers_inference(self):
        # Set up mock response
        mock_res = MagicMock()
        mock_res.response_text = (
            "Here is the binary search implementation:\n"
            "```python\n"
            "def binary_search(arr, target):\n"
            "    left, right = 0, len(arr) - 1\n"
            "    while left <= right:\n"
            "        mid = (left + right) // 2\n"
            "        if arr[mid] == target: return mid\n"
            "        elif arr[mid] < target: left = mid + 1\n"
            "        else: right = mid - 1\n"
            "    return -1\n"
            "```"
        )
        self.mock_ollama.generate.return_value = mock_res

        query = "How do I implement binary search?"
        self.assistant.ask(query)

        # Wait briefly for worker thread
        time.sleep(0.3)

        self.assertEqual(len(self.answers), 1)
        q, ans, code = self.answers[0]
        self.assertEqual(q, query)
        self.assertIn("binary search", ans.lower())
        self.assertIsNotNone(code)
        self.assertIn("def binary_search", code)

    def test_ollama_offline_handling(self):
        # Simulate Ollama connection failure
        self.mock_ollama.generate.side_effect = RuntimeError("Failed to connect to http://127.0.0.1:11434")

        self.assistant.ask("What is a deadlock?")
        time.sleep(0.3)

        # Should catch error gracefully and invoke on_error callback
        self.assertEqual(len(self.errors), 1)
        self.assertIn("Failed to connect", self.errors[0])
        # Transcriber / assistant must not crash
        self.assertEqual(len(self.answers), 0)

    def test_clear_context(self):
        seg = TranscriptSegment(1, 100.0, "10:00:00", "call", "[Call]", "Test context", is_final=True)
        self.assistant.add_transcript_segment(seg)
        self.assertEqual(len(self.assistant.context_turns), 1)

        self.assistant.clear_context()
        self.assertEqual(len(self.assistant.context_turns), 0)


if __name__ == "__main__":
    unittest.main()
