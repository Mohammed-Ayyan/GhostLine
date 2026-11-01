# Phase 7 Report — Keyboard Backlight: Honest Hardware Assessment

**Execution Date:** 2026-11-01 20:55:00 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Machine Keyboard Hardware & Windows Lighting Subsystem Diagnosis
- **Host Device:** Lenovo 82XW (Lenovo LOQ 15IRH8 Notebook)
- **OS Build:** Windows 11 Build 26300 (`VERIFIED-LIVE`)
- **Windows Dynamic Lighting (`LampArray`):**
  - Queried `Windows.Devices.Lights.LampArray` via WinRT metadata (`scratch/hardware_diag_collector.py`).
  - Enumeration returned `0` devices (`VERIFIED-LIVE`).
  - Result: No Windows Dynamic Lighting LampArray devices are attached or exposed by the system firmware.
- **Embedded Controller Firmware Backlight:**
  - The built-in laptop keyboard backlight is controlled exclusively at the hardware Embedded Controller (EC) layer via the physical hotkey combination `Fn + Space`.
  - Microsoft Windows exposes no public API, WMI class, or driver interface for controlling this EC-driven backlight without vendor-specific proprietary ACPI calls.
- **Vendor Software Status:**
  - Neither Lenovo Vantage nor Lenovo Legion Toolkit is installed or registered in the Windows system path.

---

## 2. Transparent UI Communication (No Faked Capabilities)
In accordance with Operating Rules, Ghostline never fakes hardware success or simulates unsupported backlight features:
1. **Disabled UI Explanatory Row (`ghostline/ui/qt_hud_overlay.py:1533`)**:
   - The hardware drawer explicitly renders:
     - Icon: `⌨️ Backlight:`
     - Text: *"Not supported on this laptop (firmware/Fn controlled, no Windows API)."*
     - Styled in muted italic gray (`#94a3b8`), clearly explaining why the control is unavailable.
2. **Indicator LED Alternative Offered (`ghostline/ui/qt_hud_overlay.py:1545`)**:
   - Directly below the backlight notice, the UI offers:
     - `💡 LED Alternative:` with target dropdown (`Caps Lock`, `Num Lock`, `Scroll Lock`), flash count (`1x` to `10x`), and speed (`slow`, `medium`, `fast`).
   - Side-effect warning prominently displayed:
     - *"⚠️ Indicator LEDs briefly toggle lock state and may affect typing while flashing."*

---

## 3. Potential Future Vendor Integrations
If the user desires custom hardware backlight control on this Lenovo model, open-source documentation exists for Lenovo ACPI:
- **Lenovo Legion Toolkit (LLT)**: Utilizes the `\\_SB.PCI0.LPC0.EC0.HKEY` ACPI method `VBDC` (Variable Backlight Device Control) via Lenovo ACPI drivers. (Reference: https://github.com/BartoszCichecki/LenovoLegionToolkit).
- As specified by Section 0, undocumented or reverse-engineered kernel drivers are not injected into the Ghostline binary.

