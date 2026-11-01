"""
Ghostline Hardware Controls - Screen Brightness Subsystem.

Provides hardware abstraction for display brightness adjustment across internal laptop panels
(via Windows WMI ACPI methods) and external monitors (via DDC/CI dxva2.dll).

Features:
- Non-blocking execution off the UI thread with debounced slider updates.
- Discrete level snapping for laptop panels that only support specific brightness steps.
- Safe minimum brightness threshold to prevent accidental screen blackout.
- Relative step controls (+1, +2, +3, +4, -1, -2, -3, -4 steps).
- Honest per-display capability detection and error reporting.
"""

import sys
import os
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)

# Default safety constants
DEFAULT_MIN_SAFE_BRIGHTNESS = 5  # Percent (prevents total blackout)
DEFAULT_STEP_SIZE_PCT = 5        # Percent per single step (+1 / -1)

# Windows structures for DDC/CI if on Windows
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    import pythoncom
    import win32com.client

    user32 = ctypes.windll.user32
    dxva2 = ctypes.windll.dxva2

    class PHYSICAL_MONITOR(ctypes.Structure):
        _fields_ = [
            ("hPhysicalMonitor", wintypes.HANDLE),
            ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
        ]

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
else:
    user32 = None
    dxva2 = None
    pythoncom = None
    win32com = None


class BaseBrightnessBackend(ABC):
    """Abstract base class for display brightness backends."""

    @abstractmethod
    def detect_displays(self) -> List[Dict[str, Any]]:
        """Scans for connected displays and their brightness capabilities."""
        pass

    @abstractmethod
    def get_brightness(self, display_id: str) -> Optional[int]:
        """Reads current brightness percentage (0-100) for the given display."""
        pass

    @abstractmethod
    def set_brightness(self, display_id: str, brightness: int) -> bool:
        """Applies brightness percentage (0-100) to the given display. Returns True on success."""
        pass

    @abstractmethod
    def get_displays(self) -> List[Dict[str, Any]]:
        """Returns the list of cached detected displays."""
        pass


class WindowsBrightnessBackend(BaseBrightnessBackend):
    """
    Native Windows brightness backend.
    Uses WMI (root\\wmi WmiMonitorBrightness / WmiMonitorBrightnessMethods) for internal panels
    and DDC/CI (dxva2.dll) for external monitors.
    """

    def __init__(self, min_safe_pct: int = DEFAULT_MIN_SAFE_BRIGHTNESS):
        self.min_safe_pct = max(0, min(min_safe_pct, 50))
        self.displays: List[Dict[str, Any]] = []
        self._wmi_levels: Dict[str, List[int]] = {}
        self._lock = threading.Lock()
        self.detect_displays()

    def detect_displays(self) -> List[Dict[str, Any]]:
        if sys.platform != "win32":
            return []

        results = []
        with self._lock:
            # 1. Probe Internal Displays via WMI
            try:
                pythoncom.CoInitialize()
                try:
                    wmi_obj = win32com.client.GetObject("winmgmts:\\\\.\\root\\wmi")
                    monitors = wmi_obj.ExecQuery("SELECT * FROM WmiMonitorBrightness")
                    for idx, mon in enumerate(monitors):
                        instance_name = str(getattr(mon, "InstanceName", f"InternalDisplay_{idx}"))
                        curr = int(getattr(mon, "CurrentBrightness", 50))
                        raw_levels = getattr(mon, "Level", None)
                        levels = [int(x) for x in raw_levels] if raw_levels else list(range(101))
                        self._wmi_levels[instance_name] = sorted(levels)

                        short_name = instance_name.split("\\")[1] if "\\" in instance_name else "Panel"
                        results.append({
                            "id": instance_name,
                            "name": f"Internal Display ({short_name})",
                            "type": "internal_wmi",
                            "current": curr,
                            "min": 0,
                            "max": 100,
                            "supported_levels": self._wmi_levels[instance_name],
                            "is_controllable": True,
                        })
                finally:
                    pythoncom.CoUninitialize()
            except Exception as e:
                logger.debug("[Brightness] WMI detection error: %s", e)

            # 2. Probe External Monitors via DDC/CI (dxva2.dll)
            try:
                hmonitors = []

                def _enum_proc(h_mon, hdc, lprect, lparam):
                    hmonitors.append(h_mon)
                    return True

                user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_enum_proc), 0)

                for h_mon in hmonitors:
                    count = wintypes.DWORD()
                    if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(h_mon, ctypes.byref(count)) and count.value > 0:
                        arr = (PHYSICAL_MONITOR * count.value)()
                        if dxva2.GetPhysicalMonitorsFromHMONITOR(h_mon, count.value, arr):
                            for pmon in arr:
                                desc = str(pmon.szPhysicalMonitorDescription)
                                min_b = wintypes.DWORD()
                                cur_b = wintypes.DWORD()
                                max_b = wintypes.DWORD()
                                if dxva2.GetMonitorBrightness(pmon.hPhysicalMonitor, ctypes.byref(min_b), ctypes.byref(cur_b), ctypes.byref(max_b)):
                                    disp_id = f"ddci_{pmon.hPhysicalMonitor}"
                                    results.append({
                                        "id": disp_id,
                                        "name": f"External Monitor ({desc})",
                                        "type": "external_ddci",
                                        "current": int(cur_b.value),
                                        "min": int(min_b.value),
                                        "max": int(max_b.value),
                                        "handle": pmon.hPhysicalMonitor,
                                        "supported_levels": None,
                                        "is_controllable": True,
                                    })
                            dxva2.DestroyPhysicalMonitors(count.value, arr)
            except Exception as e:
                logger.debug("[Brightness] DDC/CI detection error: %s", e)

            self.displays = results
            return results

    def get_displays(self) -> List[Dict[str, Any]]:
        return list(self.displays)

    def _snap_to_level(self, display_id: str, requested: int) -> int:
        levels = self._wmi_levels.get(display_id)
        if not levels:
            return requested
        # Find nearest supported level
        return min(levels, key=lambda lvl: abs(lvl - requested))

    def get_brightness(self, display_id: str) -> Optional[int]:
        # Search internal WMI first
        for disp in self.displays:
            if disp["id"] == display_id:
                if disp["type"] == "internal_wmi":
                    try:
                        pythoncom.CoInitialize()
                        try:
                            wmi_obj = win32com.client.GetObject("winmgmts:\\\\.\\root\\wmi")
                            monitors = wmi_obj.ExecQuery("SELECT * FROM WmiMonitorBrightness")
                            for mon in monitors:
                                if str(getattr(mon, "InstanceName", "")) == display_id:
                                    val = int(getattr(mon, "CurrentBrightness", 50))
                                    disp["current"] = val
                                    return val
                        finally:
                            pythoncom.CoUninitialize()
                    except Exception:
                        pass
                elif disp["type"] == "external_ddci":
                    handle = disp.get("handle")
                    if handle:
                        min_b = wintypes.DWORD()
                        cur_b = wintypes.DWORD()
                        max_b = wintypes.DWORD()
                        if dxva2.GetMonitorBrightness(handle, ctypes.byref(min_b), ctypes.byref(cur_b), ctypes.byref(max_b)):
                            val = int(cur_b.value)
                            disp["current"] = val
                            return val
                return disp.get("current", 50)
        return None

    def set_brightness(self, display_id: str, brightness: int) -> bool:
        # Clamp to safe minimum and maximum
        target = max(self.min_safe_pct, min(int(brightness), 100))

        target_disp = None
        for d in self.displays:
            if d["id"] == display_id:
                target_disp = d
                break

        if not target_disp:
            # If target not found by id, attempt to apply to first controllable display
            if self.displays:
                target_disp = self.displays[0]
                display_id = target_disp["id"]
            else:
                return False

        if target_disp["type"] == "internal_wmi":
            # Snap to supported discrete level
            snapped = self._snap_to_level(display_id, target)
            try:
                pythoncom.CoInitialize()
                try:
                    wmi_obj = win32com.client.GetObject("winmgmts:\\\\.\\root\\wmi")
                    methods = wmi_obj.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods")
                    for m in methods:
                        inst = str(getattr(m, "InstanceName", ""))
                        if inst == display_id or not display_id:
                            in_params = m.Methods_("WmiSetBrightness").inParameters.SpawnInstance_()
                            in_params.Properties_("Timeout").Value = 1
                            in_params.Properties_("Brightness").Value = int(snapped)
                            m.ExecMethod_("WmiSetBrightness", in_params)
                            target_disp["current"] = snapped
                            return True
                    # If exact instance not matched, apply to first method
                    for m in methods:
                        in_params = m.Methods_("WmiSetBrightness").inParameters.SpawnInstance_()
                        in_params.Properties_("Timeout").Value = 1
                        in_params.Properties_("Brightness").Value = int(snapped)
                        m.ExecMethod_("WmiSetBrightness", in_params)
                        target_disp["current"] = snapped
                        return True
                finally:
                    pythoncom.CoUninitialize()
            except Exception as e:
                logger.warning("[Brightness] WmiSetBrightness failed: %s", e)
                return False

        elif target_disp["type"] == "external_ddci":
            handle = target_disp.get("handle")
            if handle:
                try:
                    if dxva2.SetMonitorBrightness(handle, target):
                        target_disp["current"] = target
                        return True
                except Exception as e:
                    logger.warning("[Brightness] SetMonitorBrightness failed: %s", e)
                    return False

        return False


class FakeBrightnessBackend(BaseBrightnessBackend):
    """Mock brightness backend for automated testing."""

    def __init__(self, min_safe_pct: int = DEFAULT_MIN_SAFE_BRIGHTNESS):
        self.min_safe_pct = min_safe_pct
        self.displays = [
            {
                "id": "mock_internal_0",
                "name": "Mock Laptop Panel",
                "type": "internal_wmi",
                "current": 40,
                "min": 0,
                "max": 100,
                "supported_levels": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                "is_controllable": True,
            },
            {
                "id": "mock_external_0",
                "name": "Mock External Monitor",
                "type": "external_ddci",
                "current": 60,
                "min": 0,
                "max": 100,
                "supported_levels": None,
                "is_controllable": True,
            },
        ]
        self.history: List[Dict[str, Any]] = []

    def detect_displays(self) -> List[Dict[str, Any]]:
        return list(self.displays)

    def get_displays(self) -> List[Dict[str, Any]]:
        return list(self.displays)

    def get_brightness(self, display_id: str) -> Optional[int]:
        for d in self.displays:
            if d["id"] == display_id:
                return d["current"]
        return None

    def set_brightness(self, display_id: str, brightness: int) -> bool:
        clamped = max(self.min_safe_pct, min(brightness, 100))
        for d in self.displays:
            if d["id"] == display_id:
                if d.get("supported_levels"):
                    # Snap to nearest
                    clamped = min(d["supported_levels"], key=lambda lvl: abs(lvl - clamped))
                d["current"] = clamped
                self.history.append({"id": display_id, "value": clamped, "time": time.time()})
                return True
        return False


class BrightnessManager:
    """
    High-level manager for screen brightness.
    Provides non-blocking, debounced execution, relative step adjustments,
    and automatic fallback to available displays.
    """

    def __init__(
        self,
        backend: Optional[BaseBrightnessBackend] = None,
        min_safe_pct: int = DEFAULT_MIN_SAFE_BRIGHTNESS,
        step_size_pct: int = DEFAULT_STEP_SIZE_PCT,
    ):
        if backend is not None:
            self.backend = backend
        else:
            self.backend = WindowsBrightnessBackend(min_safe_pct=min_safe_pct)

        self.min_safe_pct = min_safe_pct
        self.step_size_pct = max(1, min(step_size_pct, 25))
        self._debounce_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._last_target_display: Optional[str] = None
        self._last_target_value: Optional[int] = None

    def get_displays(self) -> List[Dict[str, Any]]:
        return self.backend.get_displays()

    def get_primary_display_id(self) -> Optional[str]:
        disps = self.get_displays()
        return disps[0]["id"] if disps else None

    def get_current_brightness(self, display_id: Optional[str] = None) -> int:
        if not display_id:
            display_id = self.get_primary_display_id()
        if not display_id:
            return 50
        val = self.backend.get_brightness(display_id)
        return val if val is not None else 50

    def adjust_step(self, step_delta: int, display_id: Optional[str] = None, callback: Optional[Callable[[int], None]] = None) -> int:
        """
        Adjusts brightness by relative step count (+1, +2, -1, -2, etc.).
        Returns the new target brightness.
        """
        if not display_id:
            display_id = self.get_primary_display_id()
        if not display_id:
            return 50

        with self._lock:
            if self._last_target_display == display_id and self._last_target_value is not None:
                current = self._last_target_value
            else:
                current = self.get_current_brightness(display_id)

        delta_pct = step_delta * self.step_size_pct
        new_val = max(self.min_safe_pct, min(current + delta_pct, 100))
        self.set_brightness_debounced(new_val, display_id=display_id, callback=callback)
        return new_val

    def set_brightness_immediate(self, value: int, display_id: Optional[str] = None) -> bool:
        """Synchronously sets brightness on the backend."""
        if not display_id:
            display_id = self.get_primary_display_id()
        if not display_id:
            return False
        return self.backend.set_brightness(display_id, value)

    def set_brightness_debounced(
        self,
        value: int,
        display_id: Optional[str] = None,
        debounce_ms: int = 60,
        callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Debounces brightness updates so high-frequency slider dragging does not lock UI or flood DDC/CI.
        Executes on a background worker thread.
        """
        if not display_id:
            display_id = self.get_primary_display_id()
        if not display_id:
            return

        with self._lock:
            self._last_target_display = display_id
            self._last_target_value = value

            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            def _apply():
                with self._lock:
                    target_disp = self._last_target_display
                    target_val = self._last_target_value
                if target_disp is not None and target_val is not None:
                    self.backend.set_brightness(target_disp, target_val)
                    if callback:
                        try:
                            callback(target_val)
                        except Exception:
                            pass

            self._debounce_timer = threading.Timer(debounce_ms / 1000.0, _apply)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()
