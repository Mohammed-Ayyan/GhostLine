import unittest
import time
import threading
from pathlib import Path
import sys

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.ui.caps_indicator import CapsLockIndicator

class TestCapsLockIndicator(unittest.TestCase):
    """
    Automated tests verifying Caps Lock LED indicator behavior:
    - Pulse count mapping for letters, numbers, and Roman numerals (1, 2, 3, 4, 5 pulses)
    - Configuration and disabled state
    - State preservation: initial typing state is preserved without drift
    - Abort, cancellation, and shutdown recovery
    - Exception safety and concurrent request handling

    IMPORTANT HARDWARE NOTE:
    Software tests via Win32 GetKeyState / SendInput verify that the Windows OS
    keyboard state machine toggles and restores with millisecond accuracy.
    However, software tests cannot definitively prove that the physical keyboard
    LED is visible or wired to state changes without direct physical hardware observation,
    as some external keyboards or OEM firmware control LEDs independently.
    """

    def test_pulse_count_mappings(self):
        """Verify label to pulse count mapping for all supported formats."""
        # Single / first
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("1"), 1)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("A"), 1)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("(i)"), 1)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("i"), 1)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("True"), 1)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("O"), 1)

        # Second
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("2"), 2)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("B"), 2)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("(ii)"), 2)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("ii"), 2)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("False"), 2)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("X"), 2)

        # Third
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("3"), 3)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("C"), 3)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("(iii)"), 3)

        # Fourth
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("4"), 4)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("D"), 4)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("(iv)"), 4)

        # Fifth
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("5"), 5)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("E"), 5)

        # Unknown / non-existent
        self.assertEqual(CapsLockIndicator.label_to_pulse_count(""), 0)
        self.assertEqual(CapsLockIndicator.label_to_pulse_count("Z"), 0)

    def test_disabled_mode_does_nothing(self):
        """Verify that when enabled=False, pulse() returns immediately without spawning threads."""
        indicator = CapsLockIndicator(enabled=False)
        threads_before = threading.active_count()
        indicator.pulse("3")
        time.sleep(0.05)
        threads_after = threading.active_count()
        self.assertEqual(threads_before, threads_after)
        self.assertIsNone(indicator._active_thread)

    def test_key_state_toggle_transition(self):
        """Verify that _toggle() actually changes the OS key state and is not a no-op."""
        initial = CapsLockIndicator.get_caps_state()
        try:
            # Toggle once -> must invert
            CapsLockIndicator._toggle()
            time.sleep(0.04)
            inverted = CapsLockIndicator.get_caps_state()
            self.assertNotEqual(initial, inverted, "OS Caps Lock key state must invert after _toggle()")

            # Toggle back -> must restore
            CapsLockIndicator._toggle()
            time.sleep(0.04)
            restored = CapsLockIndicator.get_caps_state()
            self.assertEqual(initial, restored, "OS Caps Lock key state must restore after second _toggle()")
        finally:
            if CapsLockIndicator.get_caps_state() != initial:
                CapsLockIndicator._toggle()

    def test_single_pulse_lifecycle_initially_off(self):
        """Verify single pulse lifecycle when Caps Lock is initially OFF (0 -> 1 -> 0)."""
        # Ensure initial state is OFF
        if CapsLockIndicator.get_caps_state() == 1:
            CapsLockIndicator._toggle()
            time.sleep(0.04)
        self.assertEqual(CapsLockIndicator.get_caps_state(), 0, "Pre-condition: Caps Lock must be OFF")

        indicator = CapsLockIndicator(enabled=True, pulse_ms=50, gap_ms=50)
        completed = threading.Event()
        indicator.pulse("A", on_complete=completed.set)
        
        self.assertTrue(completed.wait(timeout=2.0), "Pulse worker must complete within timeout")
        self.assertEqual(indicator.get_caps_state(), 0, "Caps Lock must be restored to OFF after pulse")

    def test_multiple_pulses_lifecycle_initially_on(self):
        """Verify multiple pulses lifecycle when Caps Lock is initially ON (1 -> 0 -> 1)."""
        # Ensure initial state is ON
        if CapsLockIndicator.get_caps_state() == 0:
            CapsLockIndicator._toggle()
            time.sleep(0.04)
        self.assertEqual(CapsLockIndicator.get_caps_state(), 1, "Pre-condition: Caps Lock must be ON")

        try:
            indicator = CapsLockIndicator(enabled=True, pulse_ms=40, gap_ms=40)
            completed = threading.Event()
            indicator.pulse("C", on_complete=completed.set)  # 3 pulses
            
            self.assertTrue(completed.wait(timeout=3.0), "Multi-pulse worker must complete within timeout")
            self.assertEqual(indicator.get_caps_state(), 1, "Caps Lock must be restored to ON after pulses")
        finally:
            # Always leave Caps Lock in clean state (OFF by default for user comfort)
            if CapsLockIndicator.get_caps_state() == 1:
                CapsLockIndicator._toggle()
                time.sleep(0.04)

    def test_pulse_timing_duration(self):
        """Verify pulse timing duration matches configured ON and OFF times."""
        # 2 pulses: pulse_on_ms=100, pulse_off_ms=80 -> ~280ms
        indicator = CapsLockIndicator(enabled=True, pulse_on_ms=100, pulse_off_ms=80)
        completed = threading.Event()
        
        t0 = time.time()
        indicator.pulse("B", on_complete=completed.set)
        self.assertTrue(completed.wait(timeout=2.0), "Pulse worker must complete")
        elapsed_ms = (time.time() - t0) * 1000

        # Minimum expected: 2 * 100ms on + 1 * 80ms gap = 280ms (with tolerance for thread scheduling)
        self.assertGreaterEqual(elapsed_ms, 240, f"Elapsed time {elapsed_ms}ms should reflect 2 pulses + gap")

    def test_concurrent_pulse_requests_handle_cleanly(self):
        """Verify that a second pulse request during an active sequence aborts the first predictably."""
        indicator = CapsLockIndicator(enabled=True, pulse_on_ms=150, pulse_off_ms=150)
        initial = indicator.get_caps_state()

        # Start long 5-pulse sequence
        indicator.pulse("5")
        time.sleep(0.08)  # mid-pulse

        # Interrupt with single pulse for 'A'
        completed = threading.Event()
        indicator.pulse("A", on_complete=completed.set)

        self.assertTrue(completed.wait(timeout=2.0), "Second pulse should complete successfully")
        final_state = indicator.get_caps_state()
        self.assertEqual(initial, final_state, "State must remain consistent and restored after interruption")

    def test_state_preservation_lifecycle(self):
        """Verify initial state is recorded and cleanly restored after pulsing."""
        indicator = CapsLockIndicator(enabled=True, pulse_ms=40, gap_ms=40)
        initial = indicator.get_caps_state()

        completed = threading.Event()
        indicator.pulse("1", on_complete=completed.set)
        
        completed.wait(timeout=2.0)
        final_state = indicator.get_caps_state()

        self.assertEqual(initial, final_state, "Caps Lock state must match initial state after pulsing")

    def test_abort_and_shutdown_recovery(self):
        """Verify abort safely stops in-flight pulse and restores safety state."""
        indicator = CapsLockIndicator(enabled=True, pulse_ms=80, gap_ms=80)
        initial = indicator.get_caps_state()

        indicator.pulse("5")
        time.sleep(0.05)  # In-flight
        indicator.restore_safety_state()

        final_state = indicator.get_caps_state()
        self.assertEqual(initial, final_state, "State must be preserved on abort/shutdown")

    def test_cancellation_preserves_state(self):
        """Verify explicit cancellation cleanly terminates pulsing and restores original state."""
        indicator = CapsLockIndicator(enabled=True, pulse_on_ms=200, pulse_off_ms=200)
        initial = indicator.get_caps_state()

        indicator.pulse("4")
        time.sleep(0.05)
        indicator.cancel()
        time.sleep(0.08)

        self.assertFalse(indicator.is_pulsing)
        self.assertEqual(indicator.get_caps_state(), initial, "Cancellation must restore original state")

if __name__ == "__main__":
    unittest.main()


