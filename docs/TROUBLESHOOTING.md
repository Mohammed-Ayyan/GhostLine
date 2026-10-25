# Ghostline — Troubleshooting & Diagnostics Guide

This guide provides practical diagnostic procedures and resolutions for issues encountered when running Ghostline.

---

## 1. Quick Diagnostic Probe

Before troubleshooting individual components, execute the built-in diagnostic probe:

```powershell
python -m ghostline.cli diagnose
```
This checks Windows Media OCR availability, Ollama daemon status, installed models, and DPI scaling factors.

---

## 2. Common Issues & Resolutions

### 2.1 OCR Failures or "Cannot find win_ocr.exe"
- **Symptom:** Logs show `RuntimeError: Native OCR binary not found` or question capture returns empty text.
- **Cause:** `bin/win_ocr.exe` is missing, blocked by antivirus, or executing on a non-Windows OS.
- **Resolution:**
  1. Verify the binary exists at `bin/win_ocr.exe` relative to the application root.
  2. If missing, compile it from C# source using the native Windows .NET Framework compiler (pre-installed on Windows 10/11):
     ```cmd
     C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:exe /out:bin\win_ocr.exe bin\src\WinOcr.cs
     ```
  3. Ensure Windows 10 (20H2+) or Windows 11 with the English language pack installed (`Settings > Time & Language > Language > Add a language > English`).

---

### 2.2 Ollama Connection Errors: "Cannot connect to local Ollama daemon"
- **Symptom:** UI displays "Ollama Disconnected" or logs show `requests.exceptions.ConnectionError`.
- **Cause:** Ollama service is not running locally on port 11434.
- **Resolution:**
  1. Start the Ollama background service:
     ```powershell
     ollama serve
     ```
  2. Verify the endpoint responds in PowerShell:
     ```powershell
     curl http://127.0.0.1:11434/api/tags
     ```
  3. Verify the required model is pulled:
     ```powershell
     ollama list
     ollama pull phi3:mini
     ```

---

### 2.3 Global Hotkey Conflicts (`Alt + /` Does Not Trigger)
- **Symptom:** Pressing `Alt + /` does not initiate screen capture.
- **Cause:** Another background application (e.g., Discord, GeForce Experience, IDE shortcuts) has registered the same hotkey, or the app lacks permissions.
- **Resolution:**
  1. Check if another program claims `Alt + /`.
  2. Change the hotkey in `config.json` located at `%APPDATA%\Ghostline\config.json`:
     ```json
     {
       "capture_hotkey": "Ctrl+Shift+F"
     }
     ```
  3. Restart Ghostline.

---

### 2.4 HUD Does Not Display / Floating Window Disappears
- **Symptom:** Capture succeeds and tray icon changes, but the floating HUD window is not visible.
- **Cause:** HUD coordinates are positioned off-screen (e.g. after disconnecting a secondary monitor) or opacity is set too low.
- **Resolution:**
  1. Press `Ctrl + Shift + H` to force toggle the HUD visible and bring it to the cursor position.
  2. Reset HUD coordinates in `%APPDATA%\Ghostline\config.json`:
     ```json
     {
       "hud_x": 100,
       "hud_y": 100,
       "hud_opacity": 0.95,
       "hud_visible": true
     }
     ```

---

### 2.5 Caps Lock Indicator Does Not Pulse
- **Symptom:** Answer solves, but Caps Lock does not flash.
- **Cause:** Caps Lock signaling is disabled in configuration or another application is hooking low-level keyboard events.
- **Resolution:**
  1. In Settings or `config.json`, verify:
     ```json
     {
       "enable_caps_indicator": true,
       "caps_pulse_duration_ms": 60,
       "caps_pulse_gap_ms": 100
     }
     ```
  2. On anti-cheat or protected exam browsers, hardware keyboard synthesis may be intercepted. Use the Floating HUD or System Tray badge instead.

---

## 3. Log Locations & Inspection

Ghostline maintains a rotating diagnostic log:
- **Default Path:** `%APPDATA%\Ghostline\app.log`
- **Session History:** `%APPDATA%\Ghostline\history.jsonl`

To inspect the live log stream in real time:
```powershell
Get-Content -Path "$env:APPDATA\Ghostline\app.log" -Wait -Tail 30
```
