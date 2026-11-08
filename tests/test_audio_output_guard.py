"""
Unit tests for AudioOutputGuard (Ghostline Run 15 Part A).
Verifies repetition loop filtering, Unicode script mismatch, echo rejection,
silence hallucinations, rate limits, and line character capping.
"""

import time
import unittest
from ghostline.audio.output_guard import AudioOutputGuard

class TestAudioOutputGuard(unittest.TestCase):
    def test_thai_unspaced_repetition_dropped(self):
        guard = AudioOutputGuard(language="en")
        thai_repeated = "ความ" * 500
        valid, text, reason = guard.validate_segment(thai_repeated, source="mic")
        self.assertFalse(valid)
        self.assertIn(reason, ("repetition", "script_mismatch"))
        self.assertTrue(guard.filter_counts["repetition"] > 0 or guard.filter_counts["script_mismatch"] > 0)

    def test_ascii_repetition_and_capping(self):
        guard = AudioOutputGuard(language="en")
        # 4 consecutive repeated words
        rep_text = "architecture architecture architecture architecture"
        valid, text, reason = guard.validate_segment(rep_text, source="mic")
        self.assertFalse(valid)
        self.assertEqual(reason, "repetition")

        # Genuine long non-repeating paragraph capped at 500 characters
        long_valid = (
            "In today's engineering review we will discuss several aspects of system reliability. "
            "First, we need to address database query latency across our read replicas. "
            "Second, we must ensure cache invalidation runs smoothly during peak traffic windows. "
            "Third, network connection pooling must be properly tuned to avoid socket exhaustion under high load. "
            "Finally, monitoring alerts should be updated with appropriate threshold boundaries so that on-call "
            "engineers are notified promptly when anomalies occur in our production deployment pipeline."
        )
        valid, text, reason = guard.validate_segment(long_valid, source="call", duration_sec=12.0)
        self.assertTrue(valid)
        self.assertLessEqual(len(text), 500)
        self.assertTrue(text.endswith("…"))

    def test_foreign_script_under_english_dropped(self):
        guard = AudioOutputGuard(language="en")
        # Japanese
        valid, _, reason = guard.validate_segment("お前はもう死んでいる", source="mic")
        self.assertFalse(valid)
        self.assertEqual(reason, "script_mismatch")

        # Thai
        valid, _, reason = guard.validate_segment("สวัสดีครับยินดีต้อนรับ", source="mic")
        self.assertFalse(valid)
        self.assertEqual(reason, "script_mismatch")

    def test_auto_detect_allows_foreign_scripts(self):
        guard = AudioOutputGuard(language="auto")
        # Under auto, a non-repeating Japanese sentence is permitted
        valid, text, reason = guard.validate_segment("こんにちは世界", source="mic")
        self.assertTrue(valid)
        self.assertEqual(text, "こんにちは世界")

        # But repetition loop is STILL dropped under auto
        thai_rep = "ความ" * 50
        valid, _, reason = guard.validate_segment(thai_rep, source="mic")
        self.assertFalse(valid)
        self.assertEqual(reason, "repetition")

    def test_silence_hallucination_phrase_dropped_on_low_energy(self):
        guard = AudioOutputGuard(language="en")
        valid, _, reason = guard.validate_segment("Thank you for watching.", source="mic", rms=0.005)
        self.assertFalse(valid)
        self.assertEqual(reason, "hallucination_phrase")

        # Same phrase with substantial energy passes
        valid, text, reason = guard.validate_segment("Thank you for watching.", source="mic", rms=0.15)
        self.assertTrue(valid)
        self.assertEqual(text, "Thank you for watching.")

    def test_speaker_acoustic_echo_cancellation(self):
        guard = AudioOutputGuard(language="en")
        # 1. System audio receives video speech
        sys_speech = "We need to discuss the architecture for the database migration."
        valid_sys, text_sys, _ = guard.validate_segment(sys_speech, source="system")
        self.assertTrue(valid_sys)
        self.assertEqual(text_sys, sys_speech)

        # 2. Mic captures speaker sound 200ms later (slight transcription variation)
        time.sleep(0.05)
        mic_echo = "We need to discuss the architecture for the database migration."
        valid_mic, _, reason_mic = guard.validate_segment(mic_echo, source="mic")
        self.assertFalse(valid_mic)
        self.assertEqual(reason_mic, "echo_speaker")
        self.assertEqual(guard.filter_counts["echo_speaker"], 1)

        # 3. Repeated echo triggers warning flag
        valid_mic2, _, _ = guard.validate_segment("architecture for the database migration", source="mic")
        self.assertFalse(valid_mic2)
        self.assertTrue(guard.should_show_echo_tip())
        # One-time flag resets
        self.assertFalse(guard.should_show_echo_tip())

    def test_normal_english_passes_clean(self):
        guard = AudioOutputGuard(language="en")
        sentence = "How does TCP window scaling prevent congestion on high latency networks?"
        valid, text, reason = guard.validate_segment(sentence, source="mic", rms=0.08)
        self.assertTrue(valid)
        self.assertEqual(text, sentence)
        self.assertIsNone(reason)

if __name__ == "__main__":
    unittest.main()
