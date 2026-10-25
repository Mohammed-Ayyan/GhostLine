# Offline Operation & Network Isolation Verification

**Subject:** Ghostline Network Audit & Air-Gap Verification  
**Date:** 2026-10-23  
**Status:** Verification Protocol & Isolation Matrix  

---

## 1. Network Boundary & Isolation Architecture

To ensure total user privacy and guarantee 100% offline autonomy, `Ghostline` is engineered with an air-tight network boundary:

```
+-------------------------------------------------------------+
|                     USER WORKSTATION                        |
|                                                             |
|  +--------------------+         +------------------------+  |
|  |    Ghostline    | <=====> |  Ollama Local Daemon   |  |
|  | Application Engine | (HTTP)  |   (127.0.0.1:11434)    |  |
|  +--------------------+         +------------------------+  |
|           |                                                 |
|           | (IPC / Direct Win32 Memory)                     |
|           v                                                 |
|  +--------------------+                                     |
|  | Windows.Media.Ocr  |                                     |
|  | Built-in OS Engine |                                     |
|  +--------------------+                                     |
+-------------------------------------------------------------+
                              ||
                    AIR-GAP BOUNDARY (DENY ALL)
                              ||
                              X
                [ No Outbound Internet Requests ]
                [ No Telemetry / Analytics / Pings ]
                [ No Cloud API Fallbacks ]
```

---

## 2. Test Scenarios & Audit Procedures

### 2.1 Test 1: Full Adapter Disconnection (Air-Gap Simulation)
- **Method:** Disable all physical and virtual network adapters via PowerShell (`Disable-NetAdapter -Name * -Confirm:$false`) or disconnect Wi-Fi and Ethernet.
- **Verification Criterion:**
  - Launch `Ghostline`.
  - Place cursor over an on-screen question.
  - Trigger capture hotkey.
  - Verify that OCR extraction, LLM inference, and indicator updates complete successfully with zero error banners.
  - Expected Result: **PASS** (100% functionality preserved).

### 2.2 Test 2: Process Network Socket Audit (`netstat` / `Get-NetTCPConnection`)
- **Method:** While `Ghostline` is executing question captures and local inference loops, monitor open sockets for the process PID:
  ```powershell
  Get-NetTCPConnection -OwningProcess <PID> | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State
  ```
- **Verification Criterion:**
  - Only loopback addresses (`127.0.0.1` / `::1`) connected to port `11434` (Ollama) may be observed.
  - Zero non-loopback connections (`0.0.0.0` or WAN IPs) permitted.
  - Expected Result: **PASS** (Strict localhost containment).

### 2.3 Test 3: DNS Query & Outbound Packet Inspection
- **Method:** Run Windows Packet Monitor (`pktmon`) or Wireshark during application startup, execution, and shutdown.
- **Verification Criterion:**
  - Filter by process name or host.
  - Ensure zero DNS queries (no lookup for `supabase.co`, `vercel.app`, `googleapis.com`, or telemetry hubs).
  - Expected Result: **PASS** (Zero DNS queries generated).

### 2.4 Test 4: Offline Feature Availability & Graceful Degradation
- **Method:** Disable Ollama daemon (`Stop-Process -Name ollama*`) while in offline mode.
- **Verification Criterion:**
  - The application must explicitly display:  
    `"Local AI engine unreachable at 127.0.0.1:11434. Ensure Ollama is running."`
  - The application must **never** silently attempt to switch to a cloud endpoint.
  - Expected Result: **PASS** (Deterministic fail-closed behavior).

---

## 3. Configuration & State Persistence Across Restarts

All user settings, hotkey preferences, HUD geometry, and indicator modes are stored in local JSON format:
- **Location:** `%APPDATA%\Ghostline\config.json`
- **Schema:**
  ```json
  {
    "hotkey": "Alt+`",
    "model_name": "phi3:mini",
    "indicator_mode": "hud",
    "tray_camouflage": true,
    "capture_width": 800,
    "capture_height": 600,
    "ocr_language": "en-US",
    "auto_copy_answer": false
  }
  ```
- Restarts confirm that configuration persists across process lifecycles without requiring remote profile sync.
