"""
Unit and integration tests for Ghostline Audio Capture subsystems.
Tests device discovery, WASAPI loopback, microphone streams, volume scaling,
start/stop/pause/resume lifecycle, and error resilience.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from ghostline.audio.capture import (
    AudioDeviceManager,
    AudioCaptureManager,
    TARGET_SAMPLE_RATE,
    HAVE_LOOPBACK_SUPPORT
)


class TestAudioDeviceManager(unittest.TestCase):
    def setUp(self):
        self.dev_manager = AudioDeviceManager()

    def test_get_devices_returns_dict(self):
        devices = self.dev_manager.get_devices()
        self.assertIsInstance(devices, dict)
        self.assertIn("loopback", devices)
        self.assertIn("mic", devices)
        self.assertIsInstance(devices["loopback"], list)
        self.assertIsInstance(devices["mic"], list)

    def test_get_default_wasapi_loopback_fallback(self):
        # Even if hardware loopback is unavailable in CI/VM, method returns dict or None without error
        loopback = self.dev_manager.get_default_wasapi_loopback()
        self.assertTrue(loopback is None or isinstance(loopback, dict))

    def test_get_default_microphone(self):
        mic = self.dev_manager.get_default_microphone()
        self.assertTrue(mic is None or isinstance(mic, dict))


class TestAudioCaptureManager(unittest.TestCase):
    def setUp(self):
        self.chunks_received = []

        def _chunk_cb(data, rate, source):
            self.chunks_received.append((data, rate, source))

        self.cb = _chunk_cb
        self.manager = AudioCaptureManager(
            on_audio_chunk=self.cb,
            system_enabled=True,
            mic_enabled=True,
            chunk_duration_sec=1.0
        )

    def tearDown(self):
        if self.manager.is_capturing:
            self.manager.stop()

    def test_initial_state(self):
        self.assertFalse(self.manager.is_capturing)
        self.assertFalse(self.manager.is_paused)
        self.assertTrue(self.manager.system_enabled)
        self.assertTrue(self.manager.mic_enabled)
        self.assertEqual(self.manager.system_volume, 1.0)
        self.assertEqual(self.manager.mic_volume, 1.0)

    def test_volume_controls(self):
        self.manager.set_volume("call", 0.5)
        self.assertEqual(self.manager.system_volume, 0.5)

        self.manager.set_volume("mic", 1.8)
        self.assertEqual(self.manager.mic_volume, 1.8)

        # Clamping check
        self.manager.set_volume("call", -1.0)
        self.assertEqual(self.manager.system_volume, 0.0)
        self.manager.set_volume("mic", 5.0)
        self.assertEqual(self.manager.mic_volume, 2.0)

    def test_pause_resume_lifecycle(self):
        self.assertFalse(self.manager.is_paused)
        paused = self.manager.toggle_pause()
        self.assertTrue(paused)
        self.assertTrue(self.manager.is_paused)

        resumed = self.manager.toggle_pause()
        self.assertFalse(resumed)
        self.assertFalse(self.manager.is_paused)

        self.manager.pause()
        self.assertTrue(self.manager.is_paused)
        self.manager.resume()
        self.assertFalse(self.manager.is_paused)

    def test_stop_when_not_started_is_safe(self):
        # Calling stop on an unstarted manager should not raise any exceptions
        self.manager.stop()
        self.assertFalse(self.manager.is_capturing)

    def test_resample_audio(self):
        # Test resampling a 48kHz mono sine wave to 16kHz
        t = np.linspace(0, 0.1, int(48000 * 0.1), endpoint=False)
        orig_sig = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        resampled = self.manager._resample(orig_sig, orig_rate=48000, target_rate=16000)
        expected_len = int(len(orig_sig) * 16000 / 48000)
        self.assertAlmostEqual(len(resampled), expected_len, delta=5)

    def test_process_stream_buffer_feed(self):
        # Synthesize 16kHz float32 audio
        raw_samples = (np.random.randn(16000) * 0.1).astype(np.float32)
        # Push 1 second worth of audio
        self.manager._process_stream_buffer(raw_samples, sample_rate=16000, source="call")

        # Callback should have received the chunk
        self.assertGreaterEqual(len(self.chunks_received), 1)
        chunk_data, rate, source = self.chunks_received[0]
        self.assertEqual(rate, 16000)
        self.assertEqual(source, "call")
        self.assertEqual(len(chunk_data), 16000)

    def test_paused_stream_suppresses_callbacks(self):
        self.manager.pause()
        raw_samples = (np.random.randn(16000) * 0.1).astype(np.float32)
        self.manager._process_stream_buffer(raw_samples, sample_rate=16000, source="mic")

        # Nothing should be emitted while paused
        self.assertEqual(len(self.chunks_received), 0)

    def test_mock_start_and_stop_lifecycle(self):
        # Mock pyaudio device streams to verify start and stop lifecycle without requiring physical audio hardware
        with patch("ghostline.audio.capture.pyaudio") as mock_pa:
            mock_inst = MagicMock()
            mock_pa.PyAudio.return_value = mock_inst
            mock_stream = MagicMock()
            mock_inst.open.return_value = mock_stream

            res, msg = self.manager.start()
            self.assertTrue(res)
            self.assertTrue(self.manager.is_capturing)

            # Repeated start should be idempotent
            res2, msg2 = self.manager.start()
            self.assertTrue(res2)

            self.manager.stop()
            self.assertFalse(self.manager.is_capturing)

            # Repeated session lifecycle
            res3, msg3 = self.manager.start()
            self.assertTrue(res3)
            self.assertTrue(self.manager.is_capturing)
            self.manager.stop()
            self.assertFalse(self.manager.is_capturing)


if __name__ == "__main__":
    unittest.main()
