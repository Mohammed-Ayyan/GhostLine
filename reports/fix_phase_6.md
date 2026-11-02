# Phase 6 Report — Screen Brightness: Diagnosis & Live Verification

**Execution Date:** 2026-11-01 20:54:50 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  

---

## 1. Machine Hardware Summary (`reports/hardware_diag.md`)
- **System Model:** Lenovo 82XW (Lenovo LOQ 15IRH8 Notebook)
- **Chassis Type:** Laptop (Chassis type 10)
- **Active GPUs:**
  1. NVIDIA GeForce RTX 4050 Laptop GPU (Driver: 32.0.15.6094)
  2. Intel(R) UHD Graphics (Driver: 31.0.101.4502)
- **Displays:**
  - `DISPLAY\CMN1621\4&1c38a0f4&0&UID8388688_0` (Internal Laptop eDP Panel)
  - WMI Brightness: Supported via `root\wmi` `WmiMonitorBrightness` and `WmiMonitorBrightnessMethods`.
  - Supported discrete brightness levels: 101 discrete steps `[0, 1, 2, ..., 99, 100]`.
  - DDC/CI: Physical monitor handle `65537` returned Win32 Error 31 (`ERROR_GEN_FAILURE`) via `dxva2.dll::GetVCPFeatureAndVCPFeatureReply`. Internal eDP panels communicate via embedded DisplayPort AUX channels rather than I2C DDC/CI.

---

## 2. Root Cause Analysis of Brightness Control Failure
- **Bug 1: COM IDispatch Parameter Mismatch in `WmiSetBrightness`**:
  - `ghostline/hardware/brightness.py` previously attempted late-bound IDispatch calls:
    ```python
    m.WmiSetBrightness(1, snapped)
    ```
  - On 64-bit Windows with `pywin32` / `win32com.client`, passing raw integers directly to `WmiSetBrightness` fails with `SWbemObjectEx: Invalid parameter (-2147217400)` because WMI expects an in-parameter SWbemObject (`Timeout` as uint32 and `Brightness` as uint8).
- **The Fix**:
  - Rewrote parameter packaging in `ghostline/hardware/brightness.py:311`:
    ```python
    in_params = m.Methods_('WmiSetBrightness').inParameters.SpawnInstance_()
    in_params.Properties_('Timeout').Value = 1
    in_params.Properties_('Brightness').Value = int(snapped)
    m.ExecMethod_('WmiSetBrightness', in_params)
    ```

---

## 3. Real Hardware Stepping Verification (`VERIFIED-LIVE`)
A live stepping test was executed directly on the host panel (`scratch/hardware_diag_collector.py`):
1. **Initial Brightness:** Read $80\%$ (`WmiMonitorBrightness.CurrentBrightness`).
2. **Apply Step (+1 Step / +5%):** Applied $85\%$.
3. **Readback:** Confirmed $85\%$ (`VERIFIED-LIVE`).
4. **Apply Step (-1 Step / -5%):** Applied $80\%$.
5. **Readback:** Confirmed $80\%$ (`VERIFIED-LIVE`).
6. **Restoration:** Restored initial $80\%$ level cleanly.

> [!NOTE]
> Physical display luminance variation is marked `NEEDS-USER-CHECK` as the agent cannot physically see the screen.

---

## 4. UI Wiring & Safe Bounds
- Hardware slider and step buttons (`-4`, `-1`, `+1`, `+4`) are wired in `ghostline/ui/qt_hud_overlay.py:1485`.
- Safe minimum brightness constraint ($5\%$) is strictly enforced in `ghostline/hardware/brightness.py:270` to prevent accidental screen blackout.
- If no displays are controllable, the UI displays:
  *"No internal panel brightness interface found; external monitor does not respond to DDC/CI. Enable DDC/CI in the monitor's on-screen menu, or try a direct HDMI/DP connection."*

