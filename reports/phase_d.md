# Phase D Report — Keyboard Lighting Subsystem

**Execution Timestamp:** 2026-11-01 18:54:00 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Architecture Overview
Implemented a modular hardware abstraction layer under `ghostline/hardware/lighting.py` with:
- `BaseLightingBackend`: Common abstract interface defining `detect()`, `is_available()`, `get_name()`, `get_capabilities()`, `set_on()`, `set_off()`, `restore()`, and `cancel()`.
- `IndicatorLedBackend`: Windows `user32` `GetKeyState` and `SendInput` controlling Caps Lock (`0x14`), Num Lock (`0x90`), and Scroll Lock (`0x91`).
  - Events tagged with `dwExtraInfo = 0x47484F53` (`GHOS`) to prevent Ghostline hotkey self-triggering.
  - Initial key states are recorded and guaranteed to be restored in `try/finally` blocks and `atexit` handlers.
  - Warns in capabilities that physical lock state is altered and may impact typing while active.
- `LampArrayLightingBackend`: Probes for Windows 11 Dynamic Lighting (`Windows.Devices.Lights.LampArray`).
  - Reports honestly if `winrt` is unavailable or no LampArray device is present. Does not fake or simulate success.
- `FakeLightingBackend`: In-memory test backend tracking states, operations, cancellations, and restoration.
- `LightingManager`: Asynchronous orchestration on a dedicated background thread (`GhostlineHardwareLightingWorker`) off the PyQt UI thread.
  - Enforces flashing rate limit $\le 3.0$ Hz (cycle time $\ge 333$ ms):
    - `slow`: 300ms ON / 300ms OFF (1.67 Hz)
    - `medium`: 200ms ON / 200ms OFF (2.50 Hz)
    - `fast`: 170ms ON / 170ms OFF (2.94 Hz $\le$ 3.0 Hz)
  - Hard watchdog limit of 30.0s prevents runaway operations.
  - Immediate cancellation via `stop_flash()` ($\le 50$ ms abort response).

---

## 2. Hardware Detection Findings on Current Machine
- **Indicator LEDs (Caps Lock / Num Lock / Scroll Lock)**:
  - Status: `VERIFIED-AUTOMATED` (API readback/toggles pass), `NEEDS-USER-CHECK` (for human observing physical LED).
  - Virtual keys `0x14`, `0x90`, and `0x91` are present and controllable via `SendInput`.
- **Windows Dynamic Lighting / LampArray**:
  - Status: `NOT-TESTED` / Unsupported.
  - Reason: `winrt` module is not installed in the Python environment, and host lacks HID LampArray hardware.
- **Vendor SDKs**:
  - Status: `NOT-TESTED` / Unsupported.
  - Checked: Razer Chroma, Logitech G HUB, Corsair iCUE, SteelSeries, ASUS Aura, Lenovo Vantage/Spectrum.
  - Findings: No vendor lighting SDK DLLs or services present. Built-in laptop keyboard backlight is firmware/Fn-key controlled without documented public Windows API.

---

## 3. Test Verification
- Test file: `tests/test_hardware_lighting.py`
- Test run: `python -m unittest tests/test_hardware_lighting.py`
- Result: **6 tests passed in 1.461s** (`VERIFIED-AUTOMATED`).
- Covered:
  - Safety frequency $\le 3$ Hz compliance for all speed presets (`slow`, `medium`, `fast`).
  - Accurate state tracking and restoration in `FakeLightingBackend`.
  - Full sequence execution, count verification (1..10), and step callbacks.
  - Immediate mid-sequence cancellation and guaranteed restoration.
  - Honest LampArray capability reporting without simulation.
  - Indicator LED backend capability schema and typing warning metadata.
