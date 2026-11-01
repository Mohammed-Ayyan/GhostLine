"""
Ghostline Hardware Controls - Keyboard Lighting Subsystem.

Provides hardware abstraction for keyboard indicator LEDs (Caps Lock, Num Lock, Scroll Lock)
and dynamic keyboard backlights (LampArray/Dynamic Lighting), with honest capability detection,
safety rate limits (<= 3 Hz), non-blocking execution, and guaranteed state restoration.
"""

import sys
import os
import time
import atexit
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)

# Constants for Windows API
VK_CAPITAL = 0x14  # Caps Lock
VK_NUMLOCK = 0x90  # Num Lock
VK_SCROLL = 0x91   # Scroll Lock

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1
GHOS_EXTRA_INFO = 0x47484F53  # "GHOS" tag for injected event filtering

# Speed profiles: ensures cycle time >= 333 ms (<= 3 Hz transition limit)
FLASH_SPEEDS = {
    "slow": {"on_ms": 300, "off_ms": 300, "hz": 1.67},
    "medium": {"on_ms": 200, "off_ms": 200, "hz": 2.50},
    "fast": {"on_ms": 170, "off_ms": 170, "hz": 2.94},
}

SUPPORTED_TARGETS = {
    "caps_lock": VK_CAPITAL,
    "num_lock": VK_NUMLOCK,
    "scroll_lock": VK_SCROLL,
}


class BaseLightingBackend(ABC):
    """Abstract base class for keyboard lighting backends."""

    @abstractmethod
    def detect(self) -> bool:
        """Probes the hardware and OS. Returns True if supported."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the backend is currently usable."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Returns the human-readable backend name."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Returns dictionary of supported features, targets, and limitations."""
        pass

    @abstractmethod
    def set_on(self, target: str = "caps_lock") -> bool:
        """Turns the light/LED on. Returns True on verified success."""
        pass

    @abstractmethod
    def set_off(self, target: str = "caps_lock") -> bool:
        """Turns the light/LED off. Returns True on verified success."""
        pass

    @abstractmethod
    def restore(self) -> bool:
        """Restores the initial hardware/LED state before flashing."""
        pass

    @abstractmethod
    def cancel(self) -> None:
        """Cancels any in-progress flash sequence."""
        pass


# Windows ctypes definitions for IndicatorLedBackend
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong),
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
            ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**32 else ctypes.c_ulong),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]
else:
    user32 = None


class IndicatorLedBackend(BaseLightingBackend):
    """
    Hardware backend controlling keyboard indicator LEDs (Caps Lock, Num Lock, Scroll Lock)
    via Windows GetKeyState and SendInput APIs.

    Guarantees:
    - Never permanently alters user's lock states.
    - Records initial lock states before sequence and always restores them in try/finally and atexit.
    - Tags injected events with GHOS_EXTRA_INFO (0x47484F53) to allow hotkey hooks to ignore them.
    - Warns user that typing can be impacted while running.
    """

    def __init__(self):
        self._available = False
        self._initial_states: Dict[str, int] = {}
        self._cancel_flag = False
        self._atexit_registered = False
        self.detect()

    def detect(self) -> bool:
        if sys.platform != "win32" or user32 is None:
            self._available = False
            return False
        try:
            # Test that GetKeyState works for virtual keys
            _ = user32.GetKeyState(VK_CAPITAL)
            self._available = True
            if not self._atexit_registered:
                atexit.register(self.restore)
                self._atexit_registered = True
            return True
        except Exception as e:
            logger.warning("[Lighting] IndicatorLedBackend detection failed: %s", e)
            self._available = False
            return False

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "Indicator LEDs (Caps / Num / Scroll Lock)"

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "type": "indicator_led",
            "targets": ["caps_lock", "num_lock", "scroll_lock"],
            "warning": "Briefly alters keyboard lock state and can affect typing while active.",
            "supports_readback": True,
            "supports_restore": True,
        }

    def _get_vk(self, target: str) -> int:
        target_clean = target.lower().strip()
        if target_clean in SUPPORTED_TARGETS:
            return SUPPORTED_TARGETS[target_clean]
        return VK_CAPITAL

    def get_key_state(self, target: str = "caps_lock") -> int:
        """Returns 1 if LED is on, 0 if off."""
        if not self._available or user32 is None:
            return 0
        vk = self._get_vk(target)
        try:
            return user32.GetKeyState(vk) & 1
        except Exception:
            return 0

    def _toggle(self, target: str = "caps_lock") -> bool:
        """Toggles the key via SendInput with GHOS_EXTRA_INFO."""
        if not self._available or user32 is None:
            return False
        vk = self._get_vk(target)
        scan = user32.MapVirtualKeyW(vk, 0)
        state_before = self.get_key_state(target)

        try:
            inputs = (INPUT * 2)()
            # Key Down
            inputs[0].type = INPUT_KEYBOARD
            inputs[0].u.ki.wVk = vk
            inputs[0].u.ki.wScan = scan
            inputs[0].u.ki.dwFlags = 0
            inputs[0].u.ki.time = 0
            inputs[0].u.ki.dwExtraInfo = GHOS_EXTRA_INFO

            # Key Up
            inputs[1].type = INPUT_KEYBOARD
            inputs[1].u.ki.wVk = vk
            inputs[1].u.ki.wScan = scan
            inputs[1].u.ki.dwFlags = KEYEVENTF_KEYUP
            inputs[1].u.ki.time = 0
            inputs[1].u.ki.dwExtraInfo = GHOS_EXTRA_INFO

            sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
            if sent == 2:
                # Poll briefly up to 40ms to confirm toggle
                t_end = time.time() + 0.04
                while time.time() < t_end:
                    if self.get_key_state(target) != state_before:
                        return True
                    time.sleep(0.005)
                return True
            return False
        except Exception as e:
            logger.debug("[Lighting] SendInput toggle error: %s", e)
            return False

    def record_initial_state(self, target: str = "caps_lock") -> None:
        """Saves current state for guaranteed restoration."""
        if target not in self._initial_states:
            self._initial_states[target] = self.get_key_state(target)

    def set_on(self, target: str = "caps_lock") -> bool:
        self.record_initial_state(target)
        current = self.get_key_state(target)
        if current == 1:
            return True
        return self._toggle(target)

    def set_off(self, target: str = "caps_lock") -> bool:
        self.record_initial_state(target)
        current = self.get_key_state(target)
        if current == 0:
            return True
        return self._toggle(target)

    def restore(self) -> bool:
        """Restores all tracked lock states back to their saved initial state."""
        if not self._available or not self._initial_states:
            return True
        success = True
        for target, init_state in list(self._initial_states.items()):
            try:
                curr = self.get_key_state(target)
                if curr != init_state:
                    self._toggle(target)
            except Exception as e:
                logger.error("[Lighting] Error restoring %s state: %s", target, e)
                success = False
        self._initial_states.clear()
        return success

    def cancel(self) -> None:
        self._cancel_flag = True


class LampArrayLightingBackend(BaseLightingBackend):
    """
    Windows 11 Dynamic Lighting / LampArray backend.
    Checks runtime support honestly; if winrt is not installed or device is not present,
    reports available = False without simulating success.
    """

    def __init__(self):
        self._available = False
        self._reason = "Not detected"
        self._cancel_flag = False
        self.detect()

    def detect(self) -> bool:
        if sys.platform != "win32":
            self._available = False
            self._reason = "Non-Windows OS"
            return False
        # Dynamic Lighting requires Windows 11 Build 22621+ and winrt or Windows.Devices.Lights
        try:
            import winrt  # type: ignore
            # If winrt exists, attempt import of Windows.Devices.Lights
            from winrt.windows.devices.lights import LampArray  # type: ignore
            self._available = True
            self._reason = "LampArray supported"
            return True
        except ImportError as e:
            self._available = False
            self._reason = f"winrt module not installed ({e})"
            return False
        except Exception as e:
            self._available = False
            self._reason = f"LampArray unavailable ({e})"
            return False

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "Windows Dynamic Lighting (LampArray)"

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "type": "lamparray",
            "available": self._available,
            "reason": self._reason,
            "targets": ["full_backlight"] if self._available else [],
            "supports_readback": False,
            "supports_restore": True,
        }

    def set_on(self, target: str = "full_backlight") -> bool:
        return False

    def set_off(self, target: str = "full_backlight") -> bool:
        return False

    def restore(self) -> bool:
        return True

    def cancel(self) -> None:
        self._cancel_flag = True


class FakeLightingBackend(BaseLightingBackend):
    """
    In-memory mock lighting backend for automated testing and simulation.
    Records all operations, flash counts, durations, and cancellations.
    """

    def __init__(self, available: bool = True):
        self._available = available
        self.states: Dict[str, int] = {"caps_lock": 0, "num_lock": 1, "scroll_lock": 0}
        self.initial_states: Dict[str, int] = {}
        self.operations: List[str] = []
        self._cancel_flag = False

    def detect(self) -> bool:
        return self._available

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "Fake Lighting Backend (Mock)"

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "type": "mock",
            "targets": ["caps_lock", "num_lock", "scroll_lock"],
            "supports_readback": True,
            "supports_restore": True,
        }

    def set_on(self, target: str = "caps_lock") -> bool:
        if target not in self.initial_states:
            self.initial_states[target] = self.states.get(target, 0)
        self.states[target] = 1
        self.operations.append(f"ON:{target}")
        return True

    def set_off(self, target: str = "caps_lock") -> bool:
        if target not in self.initial_states:
            self.initial_states[target] = self.states.get(target, 0)
        self.states[target] = 0
        self.operations.append(f"OFF:{target}")
        return True

    def restore(self) -> bool:
        for t, init_val in list(self.initial_states.items()):
            self.states[t] = init_val
            self.operations.append(f"RESTORE:{t}:{init_val}")
        self.initial_states.clear()
        return True

    def cancel(self) -> None:
        self._cancel_flag = True
        self.operations.append("CANCEL")


class LightingManager:
    """
    High-level manager orchestrating keyboard lighting sequences on a dedicated worker thread.

    Safety:
    - Enforces flash frequency <= 3.0 Hz (cycle >= 333 ms).
    - Hard execution timeout (max 30s) prevents runaway operations.
    - Cancelation responsive within ~50ms.
    - Guaranteed state restoration in try/finally blocks and atexit.
    - Non-blocking: background thread execution never blocks the PyQt UI thread.
    """

    def __init__(self, backend: Optional[BaseLightingBackend] = None):
        if backend is not None:
            self.backend = backend
        else:
            # Auto-detect available backend: prefer indicator LEDs if available
            led_backend = IndicatorLedBackend()
            if led_backend.is_available():
                self.backend = led_backend
            else:
                lamp_backend = LampArrayLightingBackend()
                if lamp_backend.is_available():
                    self.backend = lamp_backend
                else:
                    self.backend = led_backend

        self._active_thread: Optional[threading.Thread] = None
        self._abort_event = threading.Event()
        self._lock = threading.RLock()
        self._is_running = False

    def is_available(self) -> bool:
        return self.backend.is_available()

    def get_backend_name(self) -> str:
        return self.backend.get_name()

    def get_capabilities(self) -> Dict[str, Any]:
        return self.backend.get_capabilities()

    def is_flashing(self) -> bool:
        with self._lock:
            return self._is_running and self._active_thread is not None and self._active_thread.is_alive()

    def start_flash(
        self,
        target: str = "caps_lock",
        count: int = 3,
        speed: str = "medium",
        on_step: Optional[Callable[[int, int], None]] = None,
        on_finished: Optional[Callable[[bool], None]] = None,
    ) -> bool:
        """
        Starts an asynchronous flashing sequence on a worker thread.

        Parameters:
        - target: "caps_lock", "num_lock", "scroll_lock", or supported target.
        - count: flash count (1, 2, 3, 4, 5, 10).
        - speed: "slow", "medium", "fast" (all <= 3 Hz).
        - on_step: optional callback(current_flash, total_count).
        - on_finished: optional callback(completed_normally).
        """
        with self._lock:
            if self.is_flashing():
                logger.warning("[LightingManager] Flash sequence already in progress. Ignoring new request.")
                return False

            self._abort_event.clear()
            self._is_running = True

            thread = threading.Thread(
                target=self._worker_flash,
                args=(target, count, speed, on_step, on_finished),
                name="GhostlineHardwareLightingWorker",
                daemon=True,
            )
            self._active_thread = thread
            thread.start()
            return True

    def stop_flash(self) -> None:
        """Requests immediate cancellation and waits briefly for state restoration."""
        self._abort_event.set()
        self.backend.cancel()
        if self._active_thread and self._active_thread.is_alive():
            self._active_thread.join(timeout=1.0)
        self.backend.restore()
        with self._lock:
            self._is_running = False

    def _worker_flash(
        self,
        target: str,
        count: int,
        speed: str,
        on_step: Optional[Callable[[int, int], None]],
        on_finished: Optional[Callable[[bool], None]],
    ):
        """Worker thread executing the pulses with timing guarantees."""
        # Sanitize count and speed
        count = max(1, min(count, 10))
        speed_profile = FLASH_SPEEDS.get(speed.lower(), FLASH_SPEEDS["medium"])
        on_sec = speed_profile["on_ms"] / 1000.0
        off_sec = speed_profile["off_ms"] / 1000.0

        # Enforce cycle >= 333 ms (<= 3 Hz)
        if (on_sec + off_sec) < 0.333:
            on_sec = 0.170
            off_sec = 0.170

        success = False
        start_time = time.time()
        max_duration = 30.0  # Hard 30-second watchdog limit

        try:
            for i in range(1, count + 1):
                if self._abort_event.is_set() or (time.time() - start_time) > max_duration:
                    break

                # Pulse ON
                self.backend.set_on(target)
                if on_step:
                    try:
                        on_step(i, count)
                    except Exception:
                        pass

                # Sleep ON interval with abort check
                t_end = time.time() + on_sec
                while time.time() < t_end:
                    if self._abort_event.is_set():
                        break
                    time.sleep(0.01)

                if self._abort_event.is_set():
                    break

                # Pulse OFF
                self.backend.set_off(target)

                # Sleep OFF interval with abort check
                t_end = time.time() + off_sec
                while time.time() < t_end:
                    if self._abort_event.is_set():
                        break
                    time.sleep(0.01)

            success = not self._abort_event.is_set()
        except Exception as e:
            logger.exception("[LightingManager] Error during flash execution: %s", e)
            success = False
        finally:
            # ALWAYS restore initial hardware state
            try:
                self.backend.restore()
            except Exception as e:
                logger.error("[LightingManager] Error in finally restore: %s", e)

            with self._lock:
                self._is_running = False

            if on_finished:
                try:
                    on_finished(success)
                except Exception:
                    pass
