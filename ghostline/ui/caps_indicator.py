import os
import sys
import time
import logging
import threading
import ctypes
from ctypes import wintypes
from typing import Optional, Callable, Dict

user32 = ctypes.windll.user32

# Virtual Key constants
VK_CAPITAL = 0x14   # Caps Lock
VK_NUMLOCK = 0x90   # Num Lock
VK_SCROLL = 0x91    # Scroll Lock

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1

TARGET_VK: Dict[str, int] = {
    "caps_lock": VK_CAPITAL,
    "num_lock": VK_NUMLOCK,
    "scroll_lock": VK_SCROLL,
}

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
    Keyboard LED indicator (Caps Lock, Num Lock, Scroll Lock) communicating
    answer states (A->1, B->2, C->3, D->4 and vice-versa) via supported Windows
    keyboard input APIs (SendInput / keybd_event / GetKeyState).

    Safety & Reliability Guarantees:
    - Never permanently alters the user's Lock key typing state.
    - Captures initial key state before pulsing and restores it in a guaranteed finally block.
    - Completely asynchronous daemon thread execution; never blocks the UI or hotkey listener.
    - Uses modern Windows SendInput with automatic verification of state toggle.
    - Rate limits: Enforces <= 3 Hz transition limit (cycle >= 333ms).
    """

    def __init__(
        self,
        enabled: bool = False,
        pulse_on_ms: int = 170,
        pulse_off_ms: int = 170,
        sequence_cooldown_ms: int = 500,
        pulse_ms: Optional[int] = None,
        gap_ms: Optional[int] = None,
        target: str = "caps_lock"
    ):
        self.enabled = enabled
        if pulse_ms is not None:
            pulse_on_ms = pulse_ms
        if gap_ms is not None:
            pulse_off_ms = gap_ms

        self.pulse_on_sec = max(0.04, pulse_on_ms / 1000.0)
        self.pulse_off_sec = max(0.04, pulse_off_ms / 1000.0)
        self.sequence_cooldown_sec = max(0.0, sequence_cooldown_ms / 1000.0)
        self._target = target if target in TARGET_VK else "caps_lock"
        self._lock = threading.Lock()
        self._abort_event = threading.Event()
        self._active_thread: Optional[threading.Thread] = None
        self._initial_state: Optional[int] = None
        self._last_finish_time = 0.0
        self._is_paused = False

    @property
    def target(self) -> str:
        return self._target

    @target.setter
    def target(self, val: str):
        if val in TARGET_VK:
            self._target = val

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
        """Returns 1 if Caps Lock is ON, 0 if OFF."""
        cls._ensure_desktop()
        try:
            return user32.GetKeyState(VK_CAPITAL) & 1
        except Exception:
            return 0

    def get_key_state(self, target: Optional[str] = None) -> int:
        """Returns 1 if target lock key is ON, 0 if OFF."""
        self._ensure_desktop()
        t = target or self._target
        vk = TARGET_VK.get(t, VK_CAPITAL)
        try:
            return user32.GetKeyState(vk) & 1
        except Exception:
            return 0

    @classmethod
    def _toggle(cls, target: str = "caps_lock") -> bool:
        """
        Simulates a single lock key press and release to flip state.
        Tries SendInput first, falls back to keybd_event.
        Returns True if state toggle was verified.
        """
        cls._ensure_desktop()
        vk = TARGET_VK.get(target, VK_CAPITAL)
        scan = user32.MapVirtualKeyW(vk, 0)
        state_before = user32.GetKeyState(vk) & 1

        success = False
        try:
            inputs = (INPUT * 2)()
            # Down
            inputs[0].type = INPUT_KEYBOARD
            inputs[0].u.ki.wVk = vk
            inputs[0].u.ki.wScan = scan
            inputs[0].u.ki.dwFlags = 0
            inputs[0].u.ki.time = 0
            inputs[0].u.ki.dwExtraInfo = 0
            # Up
            inputs[1].type = INPUT_KEYBOARD
            inputs[1].u.ki.wVk = vk
            inputs[1].u.ki.wScan = scan
            inputs[1].u.ki.dwFlags = KEYEVENTF_KEYUP
            inputs[1].u.ki.time = 0
            inputs[1].u.ki.dwExtraInfo = 0

            sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
            if sent == 2:
                t_end = time.time() + 0.05
                while time.time() < t_end:
                    if (user32.GetKeyState(vk) & 1) != state_before:
                        success = True
                        break
                    time.sleep(0.005)
        except Exception as e:
            logging.debug("[CapsLockIndicator] SendInput exception: %s", e)

        if not success:
            try:
                user32.keybd_event(vk, scan, 0, 0)
                user32.keybd_event(vk, scan, KEYEVENTF_KEYUP, 0)
                t_end = time.time() + 0.05
                while time.time() < t_end:
                    if (user32.GetKeyState(vk) & 1) != state_before:
                        success = True
                        break
                    time.sleep(0.005)
            except Exception as e:
                logging.debug("[CapsLockIndicator] keybd_event exception: %s", e)

        return success

    @classmethod
    def _detailed_pulse_count(cls, label: str) -> int:
        """
        Maps multiple-choice options and numbers to LED pulse counts (Legacy detailed mode):
        - 1 or A -> 1 blink
        - 2 or B -> 2 blinks
        - 3 or C -> 3 blinks
        - 4 or D -> 4 blinks
        - 5 or E -> 5 blinks
        """
        if not label:
            return 0
        clean = str(label).strip("()[]:.- \t\r\n")
        if not clean:
            return 0

        # Handle "Option X" prefix
        if clean.lower().startswith("option"):
            clean = clean[6:].strip("()[]:.- \t\r\n")

        if not clean:
            return 0

        # Boolean check
        if clean.lower() == "true":
            return 1
        if clean.lower() == "false":
            return 2

        # Roman numerals check
        roman_map = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}
        if clean.lower() in roman_map:
            return roman_map[clean.lower()]

        # Letter check
        first = clean[0].upper()
        if 'A' <= first <= 'Z' and (len(clean) == 1 or clean[1:2] in " .):"):
            return ord(first) - ord('A') + 1

        # Digit check
        if first.isdigit():
            val = int(first)
            return val if val > 0 else 1

        # Status / error signals
        if clean.lower() in ["ready", "ok", "success"]:
            return 1
        if clean.lower() in ["?", "!", "error", "fail", "uncertain"]:
            return 2

        # General single letter fallback
        if len(clean) == 1 and 'A' <= first <= 'Z':
            return ord(first) - ord('A') + 1

        return 1

    def _instance_pulse_count(self, label: str) -> int:
        """
        Generic status pulse mode (Run 8 anti-leak specification):
        - Answer ready / valid response -> 1 pulse
        - Error / failure / uncertainty -> 2 pulses
        - Empty -> 0 pulses
        """
        clean = str(label).strip("()[]:.- \t\r\n").lower()
        if not clean:
            return 0
        if clean in ["?", "!", "error", "fail", "uncertain"]:
            return 2
        return 1

    class _PulseHelper:
        def __get__(self, instance, owner=None):
            if instance is None:
                return owner._detailed_pulse_count
            return instance._instance_pulse_count

    label_to_pulse_count = _PulseHelper()

    def pause(self):
        """Temporarily pauses LED pulsing."""
        self._is_paused = True

    def resume(self):
        """Resumes LED pulsing."""
        self._is_paused = False

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def pulse(self, label: str, on_complete: Optional[Callable[[], None]] = None):
        """Asynchronously pulses the target LED to indicate answer."""
        if not self.enabled or self._is_paused:
            logging.info("[CapsLockIndicator] Pulse ignored (enabled=%s, paused=%s)", self.enabled, self._is_paused)
            return

        self.abort()
        self._abort_event.clear()
        self._active_thread = threading.Thread(
            target=self._pulse_worker,
            args=(label, on_complete),
            name="KeyboardLedPulseThread",
            daemon=True
        )
        self._active_thread.start()

    def _sleep_interruptible(self, duration_sec: float) -> bool:
        """Sleeps in small slices to break immediately if abort is requested."""
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
                if on_complete:
                    try:
                        on_complete()
                    except Exception:
                        pass
                return

            target = self._target
            # Enforce cycle >= 333 ms (<= 3 Hz safety limit)
            pulse_time = max(0.170, self.pulse_on_sec)
            gap_time = max(0.170, self.pulse_off_sec)
            if (pulse_time + gap_time) < 0.333:
                gap_time = 0.333 - pulse_time

            initial = self.get_key_state(target)
            self._initial_state = initial
            logging.info(
                "[CapsLockIndicator] Starting %d pulse(s) for '%s' on %s (Initial: %s, ON: %.0fms, OFF: %.0fms)",
                count, label, target, "ON" if initial else "OFF", pulse_time * 1000, gap_time * 1000
            )

            try:
                for p in range(count):
                    if self._abort_event.is_set():
                        break

                    # 1. Flip state
                    self._toggle(target)
                    if self._sleep_interruptible(pulse_time):
                        break

                    # 2. Flip back (restores LED to initial state)
                    self._toggle(target)

                    if p < count - 1:
                        if self._sleep_interruptible(gap_time):
                            break
            except Exception as e:
                logging.error("[CapsLockIndicator] Pulse worker error: %s", e)
            finally:
                # Absolute guarantee: restore initial state if any drift occurred
                current = self.get_key_state(target)
                if current != initial:
                    self._toggle(target)
                    logging.info("[CapsLockIndicator] Restored initial %s state: %s", target, "ON" if initial else "OFF")

                self._initial_state = None
                self._last_finish_time = time.time()
                if on_complete and not self._abort_event.is_set():
                    try:
                        on_complete()
                    except Exception:
                        pass

    def test_toggle(self) -> bool:
        """Tests whether Windows allows toggling target lock state and restores it."""
        target = self._target
        initial = self.get_key_state(target)
        toggled = self._toggle(target)
        time.sleep(0.05)
        self._toggle(target)
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
            target = self._target
            current = self.get_key_state(target)
            if current != self._initial_state:
                self._toggle(target)
            self._initial_state = None


# Alias for clarity
KeyboardLedIndicator = CapsLockIndicator
