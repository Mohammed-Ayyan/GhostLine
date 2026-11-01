# Hardware Diagnostics & Telemetry Report

**Date**: 2026-11-01  
**System**: Lenovo 82XW (Lenovo Notebook)  
**Status**: VERIFIED-LIVE (Readback verification on internal panel)  
**Visual Status**: NEEDS-USER-CHECK (Real perceived panel luminescence and key illumination)  

---

## 1. Machine Identification & Platform

| Attribute | Detected Value | Evidence Source |
| :--- | :--- | :--- |
| **Manufacturer** | LENOVO | `Win32_ComputerSystem.Manufacturer` |
| **Model** | 82XW (Lenovo LOQ / Gaming Notebook) | `Win32_ComputerSystem.Model` |
| **System Type** | x64-based PC | `Win32_ComputerSystem.SystemType` |
| **Chassis Type** | Notebook (Chassis ID 10) | `Win32_SystemEnclosure.ChassisTypes` |
| **OS Name & Build** | Windows 10/11 Build 10.0.26300 (AMD64) | `platform.version()` |

---

## 2. Graphics Accelerators & Video Controllers

| Device Name | Driver Version | PNP Device ID |
| :--- | :--- | :--- |
| **NVIDIA GeForce RTX 4050 Laptop GPU** | `32.0.15.9186` | `PCI\VEN_10DE&DEV_28E1&SUBSYS_3C9017AA&REV_A1` |
| **Intel(R) UHD Graphics** | `32.0.101.6733` | `PCI\VEN_8086&DEV_A7A8&SUBSYS_3C9017AA&REV_04` |

---

## 3. Display Interfaces & Brightness Subsystems

### A. Internal Panel (WMI ACPI)
- **Device ID**: `DISPLAY\CMN1621\4&1c38a0f4&0&UID8388688_0`
- **Friendly Name**: `Generic PnP Monitor` (Internal Panel CMN1621)
- **WMI Brightness Support**: **True** (`root\wmi` `WmiMonitorBrightness`)
- **Current Brightness**: `80%`
- **Discrete Firmware Levels**: 101 discrete levels: `[0, 1, 2, ..., 99, 100]` (full granularity)
- **Control Interface**: `root\wmi` `WmiMonitorBrightnessMethods` (`WmiSetBrightness`)

### B. External / Physical Displays (DDC/CI dxva2)
- **Monitors Enumerated**: HMONITOR `65537`
- **Description**: `Generic PnP Monitor`
- **DDC/CI VCP 0x10 Read**: `False`
- **Win32 Error Code**: `31` (`ERROR_GEN_FAILURE`)
- **Reason**: Internal laptop eDP panels communicate backlight controls exclusively via ACPI/WMI methods, not via I2C DDC/CI buses. No external DDC/CI monitors are currently attached.

---

## 4. Live Brightness Stepping Verification (VERIFIED-LIVE)

Tested via `BrightnessManager` using native Win32 WMI `ExecMethod_('WmiSetBrightness', in_params)`:
1. **Initial Baseline**: `80%` readback.
2. **Apply Step (+1 Step, +5%)**: Target requested: `85%`.
   - WMI Readback: `85%` (**VERIFIED-LIVE**).
3. **Apply Step (-1 Step, -5%)**: Target requested: `80%`.
   - WMI Readback: `80%` (**VERIFIED-LIVE**).
4. **Restoration**: Immediate write `80%`.
   - Final Readback: `80%` (**VERIFIED-LIVE**).

*Note: Visual panel luminescence change is marked `NEEDS-USER-CHECK`.*

### Why Controls Previously Failed in GUI:
In `ghostline/hardware/brightness.py`, Python `win32com.client` dispatched `m.WmiSetBrightness(1, snapped)` via late-binding IDispatch. In Python `win32com`, dynamic late-binding on `SWbemObjectEx` does not pass method arguments as named Wbem parameters, triggering `(-2147352567, 'Exception occurred.', (0, 'SWbemObjectEx', 'Invalid parameter ', None, 0, -2147217400), None)`.
The fix instantiates `in_params = m.Methods_('WmiSetBrightness').inParameters.SpawnInstance_()` and invokes `m.ExecMethod_('WmiSetBrightness', in_params)`, which succeeds reliably.

---

## 5. Keyboard Backlight & Dynamic Lighting Diagnosis

### A. Windows Dynamic Lighting (LampArray)
- **Runtime Support**: **False**
- **Reason**: `winrt` module not installed (`No module named 'winrt'`). Windows Dynamic Lighting is not present in this Python environment.

### B. Installed OEM Vendor Software
The following vendor processes are actively running on this system:
- `LenovoUtilityService.exe`
- `LenovoVantageService.exe`
- `Lenovo.Modern.ImController.exe`
- `LenovoVantage-(VantageCoreAddin).exe`
- `LenovoVantage-(LenovoGamingSystemAddin).exe`

### C. Capability Reality Check (Anti-Hallucination)
- On Lenovo LOQ / Legion notebooks (model `82XW`), keyboard backlight illumination is handled directly by Embedded Controller (EC) firmware and toggled via hardware key combinations (`Fn + Space`).
- Microsoft Windows provides **no standard public OS API** for controlling proprietary OEM keyboard backlights on laptops without LampArray hardware.
- Controlling this backlight from third-party user-mode code without reverse-engineering proprietary EC registers or Lenovo Vantage private WMI methods (`\ _SB.PCI0.LPC0.EC0.HKEY.SKBL`) is neither documented nor supported.
- **UI Action**: Display a visible, disabled row in the hardware drawer:
  `"Keyboard backlight: not supported on this device (firmware/Fn controlled)"`
  and present the indicator LED system (Caps Lock, Num Lock, Scroll Lock) as the reliable native hardware signaling alternative.

