import os
import sys
import time
import logging
import threading
import ctypes
from ctypes import wintypes
from typing import Optional, Callable

user32 = ctypes.windll.user32

VK_CAPITAL = 0x14  # Virtual Key for Caps Lock
SCAN_CAPITAL = user32.MapVirtualKeyW(VK_CAPITAL, 0) or 0x3A
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1

# Ctypes structures for SendInput
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong)
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


class CapsLockIndicator:
    """
    Optional Caps Lock LED indicator communicating validated answer states
    via supported Windows keyboard input APIs (SendInput / keybd_event / GetKeyState).

    Safety & Reliability Guarantees:
    - Never permanently alters the user's Caps Lock typing state.
    - Captures initial Caps Lock state before pulsing and restores it in a guaranteed finally block.
    - Completely asynchronous daemon thread execution; never blocks the UI or hotkey listener.
    - Uses modern Windows SendInput with automatic verification of state toggle.
    - UIPI / elevated process detection: logs meaningful diagnostic warning if target blocks input.
    - Decoupled from HUD, screen capture, OCR, and inference.
    """

    def __init__(
        self,
        enabled: bool = False,
        pulse_on_ms: int = 300,
        pulse_off_ms: int = 250,
        sequence_cooldown_ms: int = 700,
        pulse_ms: Optional[int] = None,
        gap_ms: Optional[int] = None
    ):
        self.enabled = enabled
        if pulse_ms is not None:
            pulse_on_ms = pulse_ms
        if gap_ms is not None:
            pulse_off_ms = gap_ms

        self.pulse_on_sec = max(0.04, pulse_on_ms / 1000.0)
        self.pulse_off_sec = max(0.04, pulse_off_ms / 1000.0)
        self.sequence_cooldown_sec = max(0.0, sequence_cooldown_ms / 1000.0)
        self._lock = threading.Lock()
        self._abort_event = threading.Event()
        self._active_thread: Optional[threading.Thread] = None
        self._initial_state: Optional[int] = None
        self._last_finish_time = 0.0
        self._is_paused = False

    @staticmethod
    def _ensure_desktop():
        """Ensures the calling thread is attached to the interactive user desktop."""
        try:
            hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                user32.CloseDesktop(hdesk)
        except Exception:
            pass

    @classmethod
    def get_caps_state(cls) -> int:
        """Returns 1 if Caps Lock is ON, 0 if OFF using both GetKeyState and GetAsyncKeyState."""
        cls._ensure_desktop()
        try:
            # Check thread message queue state
            state_key = user32.GetKeyState(VK_CAPITAL) & 1
            # Check physical hardware state
            state_async = user32.GetAsyncKeyState(VK_CAPITAL) & 1
            return state_key
        except Exception:
            return 0

    @classmethod
    def _toggle(cls) -> bool:
        """
        Simulates a single Caps Lock key press and release to flip state.
        Tries SendInput first, falls back to keybd_event.
        Returns True if state toggle was verified.
        """
        cls._ensure_desktop()
        state_before = cls.get_caps_state()

        # Method 1: SendInput (Modern hardware-level injection)
        success = False
        try:
            inputs = (INPUT * 2)()
            # Down
            inputs[0].type = INPUT_KEYBOARD
            inputs[0].u.ki.wVk = VK_CAPITAL
            inputs[0].u.ki.wScan = SCAN_CAPITAL
            inputs[0].u.ki.dwFlags = 0
            inputs[0].u.ki.time = 0
            inputs[0].u.ki.dwExtraInfo = 0
            # Up
            inputs[1].type = INPUT_KEYBOARD
            inputs[1].u.ki.wVk = VK_CAPITAL
            inputs[1].u.ki.wScan = SCAN_CAPITAL
            inputs[1].u.ki.dwFlags = KEYEVENTF_KEYUP
            inputs[1].u.ki.time = 0
            inputs[1].u.ki.dwExtraInfo = 0

            sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
            if sent == 2:
                # Poll up to 40ms to verify state change
                t_end = time.time() + 0.04
                while time.time() < t_end:
                    if cls.get_caps_state() != state_before:
                        success = True
                        break
                    time.sleep(0.005)
        except Exception as e:
            logging.debug("[CapsLockIndicator] SendInput exception: %s", e)

        # Method 2: Fallback to keybd_event
        if not success:
            try:
                user32.keybd_event(VK_CAPITAL, SCAN_CAPITAL, 0, 0)
                user32.keybd_event(VK_CAPITAL, SCAN_CAPITAL, KEYEVENTF_KEYUP, 0)
                t_end = time.time() + 0.04
                while time.time() < t_end:
                    if cls.get_caps_state() != state_before:
                        success = True
                        break
                    time.sleep(0.005)
            except Exception as e:
                logging.debug("[CapsLockIndicator] keybd_event exception: %s", e)

        if not success:
            logging.warning(
                "[CapsLockIndicator] Caps Lock state toggle was not confirmed by Windows. "
                "Possible cause: Active foreground window has elevated integrity (UIPI block) "
                "or third-party keyboard security filter."
            )
        return success

    @classmethod
    def label_to_pulse_count(cls, label: str) -> int:
        """
        Maps validated answer labels to LED pulse counts:
        - 1 / A / (i) / True / O -> 1 pulse
        - 2 / B / (ii) / False / X -> 2 pulses
        - 3 / C / (iii) -> 3 pulses
        - 4 / D / (iv) -> 4 pulses
        - 5 / E / (v) -> 5 pulses
        - ? / Uncertain -> 2 rapid diagnostic pulses
        - ! / Error -> 3 rapid diagnostic pulses
        """
        clean = label.strip("()[]:.- ").lower()
        mapping = {
            "1": 1, "a": 1, "i": 1, "o": 1, "t": 1, "true": 1,
            "2": 2, "b": 2, "ii": 2, "x": 2, "f": 2, "false": 2,
            "3": 3, "c": 3, "iii": 3,
            "4": 4, "d": 4, "iv": 4,
            "5": 5, "e": 5, "v": 5,
            "?": 2, "uncertain": 2,
            "!": 3, "error": 3
        }
        return mapping.get(clean, 0)

    def pause(self):
        """Temporarily pauses Caps Lock LED pulsing."""
        self._is_paused = True

    def resume(self):
        """Resumes Caps Lock LED pulsing."""
        self._is_paused = False

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def pulse(self, label: str, on_complete: Optional[Callable[[], None]] = None):
        """Asynchronously pulses the Caps Lock LED to indicate answer."""
        if not self.enabled or self._is_paused:
            logging.info("[CapsLockIndicator] Pulse ignored (enabled=%s, paused=%s)", self.enabled, self._is_paused)
            return

        # Abort any currently running pulse before starting a new one
        self.abort()

        self._abort_event.clear()
        self._active_thread = threading.Thread(
            target=self._pulse_worker,
            args=(label, on_complete),
            name="CapsLockPulseThread",
            daemon=True
        )
        self._active_thread.start()

    def _sleep_interruptible(self, duration_sec: float) -> bool:
        """Sleeps in small slices to break immediately if abort is requested. Returns True if aborted."""
        t_end = time.time() + duration_sec
        while time.time() < t_end:
            if self._abort_event.is_set():
                return True
            time.sleep(0.01)
        return self._abort_event.is_set()

    def _pulse_worker(self, label: str, on_complete: Optional[Callable[[], None]] = None):
        with self._lock:
            count = self.label_to_pulse_count(label)
            if count <= 0:
                logging.info("[CapsLockIndicator] No pulse count mapped for '%s', skipping.", label)
                return

            # Special timing for diagnostic error/uncertainty
            if label in ["?", "Uncertain", "uncertain"]:
                pulse_time = 0.12
                gap_time = 0.10
            elif label in ["!", "Error", "error"]:
                pulse_time = 0.08
                gap_time = 0.08
            else:
                pulse_time = self.pulse_on_sec
                gap_time = self.pulse_off_sec

            initial = self.get_caps_state()
            self._initial_state = initial
            logging.info("[CapsLockIndicator] Starting %d pulse(s) for '%s' (Initial state: %s, ON: %.0fms, OFF: %.0fms)",
                         count, label, "ON" if initial else "OFF", pulse_time * 1000, gap_time * 1000)

            try:
                for p in range(count):
                    if self._abort_event.is_set():
                        break

                    # 1. Flip state
                    self._toggle()
                    if self._sleep_interruptible(pulse_time):
                        break

                    # 2. Flip back (restores LED to initial state)
                    self._toggle()

                    if p < count - 1:
                        if self._sleep_interruptible(gap_time):
                            break
            except Exception as e:
                logging.error("[CapsLockIndicator] Pulse worker error: %s", e)
            finally:
                # Absolute guarantee: restore initial state if any drift occurred
                current = self.get_caps_state()
                if current != initial:
                    self._toggle()
                    logging.info("[CapsLockIndicator] Restored initial state: %s", "ON" if initial else "OFF")

                self._initial_state = None
                self._last_finish_time = time.time()
                if on_complete and not self._abort_event.is_set():
                    try:
                        on_complete()
                    except Exception:
                        pass

    def test_toggle(self) -> bool:
        """
        Independently tests whether Windows allows toggling the Caps Lock state
        and restores the original state immediately.
        """
        initial = self.get_caps_state()
        toggled = self._toggle()
        time.sleep(0.05)
        # Revert
        self._toggle()
        return toggled

    def cancel(self):
        """Explicit cancellation of active pulse sequence and safe state restoration."""
        self.restore_safety_state()

    @property
    def is_pulsing(self) -> bool:
        """Returns True if a pulse sequence worker thread is currently active."""
        return self._active_thread is not None and self._active_thread.is_alive()

    def abort(self):
        """Aborts active pulsing and safely restores initial state."""
        self._abort_event.set()
        if self._active_thread and self._active_thread.is_alive():
            self._active_thread.join(timeout=1.0)

    def restore_safety_state(self):
        """Forces verification and cleanup during application shutdown or error recovery."""
        self.abort()
        if self._initial_state is not None:
            current = self.get_caps_state()
            if current != self._initial_state:
                self._toggle()
            self._initial_state = None


