# Phase F Report — Overlay UI Integration & Settings Persistence

**Execution Timestamp:** 2026-11-01 19:06:30 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Floating HUD Overlay Integration
Modified `ghostline/ui/qt_hud_overlay.py` to seamlessly embed the hardware controls:
- **Collapsible Drawer (`island_hardware`)**:
  - Inserted directly below `island_toolbar` and above `island_context`.
  - Acrylic dark card styling (`QFrame#IslandHardware`) adhering to Ghostline design system.
  - Toggled via dedicated toolbar button `self.btn_hw` ("🔆") with tooltip.
  - Drawer visibility state is persisted to `config.json` via `hw_controls_collapsed`.
- **Screen Brightness Controls**:
  - Dynamically populates connected displays (`QComboBox`).
  - Discrete step buttons (`-4`, `-1`, `+1`, `+4`) scaled by `hw_brightness_step_pct`.
  - Real-time slider bounded between `min_safe_pct` and 100%.
  - Asynchronous, debounced dispatch off the GUI thread (`set_brightness_debounced`).
  - Thread-safe GUI updates via `sig_hw_brightness_updated`.
  - Fallback message ("Brightness not controllable on this device") if no controllable panels exist.
- **Keyboard Lighting Controls**:
  - Target key selector (`Caps Lock`, `Num Lock`, `Scroll Lock`).
  - Flash count selector (`1x`, `2x`, `3x`, `4x`, `5x`, `10x`).
  - Speed selector (`slow [1.67 Hz]`, `medium [2.5 Hz]`, `fast [2.94 Hz]`).
  - "Flash" and "Stop" action buttons with real-time status label.
  - Thread-safe GUI updates via `sig_hw_flash_step` and `sig_hw_flash_finished`.
  - Explicit warning alert: *"⚠️ Indicator LEDs briefly toggle lock state and may affect typing while flashing."*
  - Fallback message ("Keyboard lighting not controllable on this device") if unsupported.
- **Window Safety & Capture Guarantees**:
  - Window flags `FramelessWindowHint | WindowStaysOnTopHint | Tool` preserved.
  - Win32 extended style `WS_EX_NOACTIVATE` (never steals focus from active applications) maintained.
  - `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` remains strictly active.

---

## 2. Configuration & Atomic Persistence
Updated `ghostline/config.py`:
- Added hardware settings to `AppConfig`:
  - `hw_brightness_step_pct: int = 5`
  - `hw_brightness_min_safe_pct: int = 5`
  - `hw_led_target: str = "caps_lock"`
  - `hw_flash_count: int = 3`
  - `hw_flash_speed: str = "medium"`
  - `hw_controls_collapsed: bool = True`
- Implemented **Atomic Config Save**:
  - Writes to a temporary `.tmp` file in the same directory.
  - Flushes and executes `os.fsync`.
  - Replaces atomically via `os.replace` to prevent config corruption on unexpected termination.
- **Backward Compatibility Verified**:
  - Tested deserializing legacy config dictionaries lacking hardware keys.
  - All keys defaulted safely without loss or errors (`VERIFIED-AUTOMATED`).

---

## 3. Test Verification
- Offscreen Headless Qt test (`QT_QPA_PLATFORM=offscreen`):
  - Verified `QtGhostlineHudOverlay` instantiates without crash or missing attributes.
  - Verified `toggle_hardware_drawer()` expands and collapses `island_hardware` properly.
  - Status: `VERIFIED-AUTOMATED` (headless UI behavior), `NEEDS-USER-CHECK` (for human visual inspection on desktop).

