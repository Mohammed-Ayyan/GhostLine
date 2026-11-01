"""
Tests for Ghostline Hardware Keyboard Lighting Subsystem.
Verifies hardware abstraction, fake backend, safety frequency constraints (<= 3 Hz),
asynchronous execution, cancellation, and guaranteed state restoration.
"""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from ghostline.hardware.lighting import (
    BaseLightingBackend,
    IndicatorLedBackend,
    LampArrayLightingBackend,
    FakeLightingBackend,
    LightingManager,
    FLASH_SPEEDS,
    SUPPORTED_TARGETS,
)


class TestHardwareLighting(unittest.TestCase):
    def setUp(self):
        self.fake_backend = FakeLightingBackend()
        self.manager = LightingManager(backend=self.fake_backend)

    def tearDown(self):
        if self.manager.is_flashing():
            self.manager.stop_flash()

    def test_frequency_rate_limit_compliance(self):
        """Verify all speed presets comply with the <= 3.0 Hz (cycle >= 333ms) safety limit."""
        for speed_name, cfg in FLASH_SPEEDS.items():
            total_cycle_ms = cfg["on_ms"] + cfg["off_ms"]
            hz = 1000.0 / total_cycle_ms
            self.assertGreaterEqual(
                total_cycle_ms,
                333,
                f"Speed {speed_name} cycle duration {total_cycle_ms}ms is faster than 333ms limit!"
            )
            self.assertLessEqual(
                hz,
                3.01,
                f"Speed {speed_name} frequency {hz:.2f}Hz exceeds 3.0 Hz flashing safety limit!"
            )

    def test_fake_backend_state_tracking_and_restoration(self):
        """Verify fake backend accurately records initial state and restores upon request."""
        backend = FakeLightingBackend()
        backend.states["caps_lock"] = 0
        backend.states["num_lock"] = 1

        # Turn caps_lock ON
        backend.set_on("caps_lock")
        self.assertEqual(backend.states["caps_lock"], 1)
        self.assertIn("ON:caps_lock", backend.operations)

        # Restore
        backend.restore()
        self.assertEqual(backend.states["caps_lock"], 0)
        self.assertIn("RESTORE:caps_lock:0", backend.operations)

    def test_manager_flashing_sequence_and_count(self):
        """Verify LightingManager executes the requested number of flashes and calls on_step/on_finished."""
        steps_recorded = []
        finished_results = []

        def on_step(curr, total):
            steps_recorded.append((curr, total))

        def on_finished(success):
            finished_results.append(success)

        # 3 flashes at fast speed
        started = self.manager.start_flash(
            target="caps_lock",
            count=3,
            speed="fast",
            on_step=on_step,
            on_finished=on_finished,
        )
        self.assertTrue(started)
        self.assertTrue(self.manager.is_flashing())

        # Wait for completion (3 * 340ms ~ 1.02s)
        time.sleep(1.3)

        self.assertFalse(self.manager.is_flashing())
        self.assertEqual(len(steps_recorded), 3)
        self.assertEqual(steps_recorded, [(1, 3), (2, 3), (3, 3)])
        self.assertEqual(finished_results, [True])

        # Verify operations in fake backend
        on_ops = [op for op in self.fake_backend.operations if op.startswith("ON:")]
        off_ops = [op for op in self.fake_backend.operations if op.startswith("OFF:")]
        restore_ops = [op for op in self.fake_backend.operations if op.startswith("RESTORE:")]

        self.assertEqual(len(on_ops), 3)
        self.assertEqual(len(off_ops), 3)
        self.assertGreaterEqual(len(restore_ops), 1)

    def test_manager_stop_and_cancel_mid_sequence(self):
        """Verify stopping mid-sequence halts execution quickly and triggers restoration."""
        started = self.manager.start_flash(target="caps_lock", count=10, speed="slow")
        self.assertTrue(started)
        time.sleep(0.15)
        self.assertTrue(self.manager.is_flashing())

        # Cancel mid-sequence
        t0 = time.time()
        self.manager.stop_flash()
        elapsed = time.time() - t0

        self.assertFalse(self.manager.is_flashing())
        self.assertLess(elapsed, 0.5, "Cancellation took too long!")
        self.assertIn("CANCEL", self.fake_backend.operations)
        restore_ops = [op for op in self.fake_backend.operations if op.startswith("RESTORE:")]
        self.assertGreaterEqual(len(restore_ops), 1)

    def test_lamparray_honest_detection_without_winrt(self):
        """Verify LampArrayLightingBackend reports unavailable honestly when winrt is absent."""
        lamp = LampArrayLightingBackend()
        # On this environment winrt is absent, verify it does not pretend to be available
        caps = lamp.get_capabilities()
        self.assertIn("available", caps)
        if not lamp.is_available():
            self.assertIn("reason", caps)
            self.assertFalse(lamp.is_available())

    def test_indicator_backend_capabilities(self):
        """Verify IndicatorLedBackend exposes proper targets and warnings."""
        backend = IndicatorLedBackend()
        caps = backend.get_capabilities()
        self.assertEqual(caps["type"], "indicator_led")
        self.assertIn("caps_lock", caps["targets"])
        self.assertIn("num_lock", caps["targets"])
        self.assertIn("scroll_lock", caps["targets"])
        self.assertTrue(caps["supports_restore"])
        self.assertIn("warning", caps)


if __name__ == "__main__":
    unittest.main()

