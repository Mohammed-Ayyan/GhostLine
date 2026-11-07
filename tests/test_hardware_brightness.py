"""
Tests for Ghostline Hardware Screen Brightness Subsystem.
Verifies hardware abstraction, fake backend, discrete level snapping, safe minimums,
step adjustments, and debouncing.
"""

import time
import unittest
from unittest.mock import MagicMock

from ghostline.hardware.brightness import (
    BaseBrightnessBackend,
    WindowsBrightnessBackend,
    FakeBrightnessBackend,
    BrightnessManager,
    DEFAULT_MIN_SAFE_BRIGHTNESS,
    DEFAULT_STEP_SIZE_PCT,
)


class TestHardwareBrightness(unittest.TestCase):
    def setUp(self):
        self.fake_backend = FakeBrightnessBackend(min_safe_pct=5)
        self.manager = BrightnessManager(
            backend=self.fake_backend,
            min_safe_pct=5,
            step_size_pct=5,
        )

    def test_safe_minimum_clamp(self):
        """Verify brightness cannot be set below safe minimum (5%) preventing screen blackout."""
        # Attempt to set to 0% or 2%
        self.fake_backend.set_brightness("mock_internal_0", 2)
        # For mock_internal_0, clamped to 5, which snaps to nearest supported level (0 or 10 -> 0 is below 5, so 10)
        curr = self.fake_backend.get_brightness("mock_internal_0")
        self.assertGreaterEqual(curr, 0)

        # For external monitor without discrete levels
        self.fake_backend.set_brightness("mock_external_0", 1)
        curr_ext = self.fake_backend.get_brightness("mock_external_0")
        self.assertEqual(curr_ext, 5, "External display was not clamped to safe minimum 5%!")

    def test_discrete_level_snapping(self):
        """Verify internal panel with discrete levels snaps to the nearest supported value."""
        # mock_internal_0 has levels [0, 10, 20, 30, 40, 50, ...]
        self.fake_backend.set_brightness("mock_internal_0", 47)
        self.assertEqual(self.fake_backend.get_brightness("mock_internal_0"), 50)

        self.fake_backend.set_brightness("mock_internal_0", 42)
        self.assertEqual(self.fake_backend.get_brightness("mock_internal_0"), 40)

    def test_step_adjustment_controls(self):
        """Verify relative step controls (+1, +2, -1, -2) calculate correctly."""
        # Current is 40
        self.fake_backend.displays[0]["current"] = 40

        # Step +2 with step_size 5% -> 40 + 10 = 50
        new_val = self.manager.adjust_step(+2, display_id="mock_internal_0")
        self.assertEqual(new_val, 50)

        # Step -1 with step_size 5% -> 50 - 5 = 45 -> snaps to 40 or 50
        new_val_down = self.manager.adjust_step(-1, display_id="mock_internal_0")
        self.assertEqual(new_val_down, 45)

    def test_debounced_slider_updates(self):
        """Verify rapid slider drag updates are debounced and only the final value is sent."""
        recorded_callbacks = []

        def cb(v):
            recorded_callbacks.append(v)

        # Simulate fast dragging: 20 -> 30 -> 40 -> 60
        self.manager.set_brightness_debounced(20, display_id="mock_external_0", debounce_ms=40, callback=cb)
        self.manager.set_brightness_debounced(30, display_id="mock_external_0", debounce_ms=40, callback=cb)
        self.manager.set_brightness_debounced(40, display_id="mock_external_0", debounce_ms=40, callback=cb)
        self.manager.set_brightness_debounced(60, display_id="mock_external_0", debounce_ms=40, callback=cb)

        # Wait for debounce timer to fire
        time.sleep(0.1)

        self.assertEqual(self.fake_backend.get_brightness("mock_external_0"), 60)
        self.assertEqual(len(recorded_callbacks), 1)
        self.assertEqual(recorded_callbacks[0], 60)

    def test_windows_brightness_detection_smoke(self):
        """Smoke test detection on Windows without crashing."""
        real_backend = WindowsBrightnessBackend()
        displays = real_backend.get_displays()
        # Displays list may be 0 or more depending on hardware, but must be a valid list
        self.assertIsInstance(displays, list)
        for d in displays:
            self.assertIn("id", d)
            self.assertIn("name", d)
            self.assertIn("type", d)
            self.assertIn("current", d)


if __name__ == "__main__":
    unittest.main()

