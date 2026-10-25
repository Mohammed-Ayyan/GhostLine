# Ghostline — Windows Post-Installation Setup & Security Guide

This comprehensive, beginner-friendly guide walks you through configuring Windows 11 and Windows 10 for **Ghostline**. It covers security verification (SmartScreen and Defender), taskbar and system tray visibility, microphone and sound loopback setup, display scaling, hotkey customization, and clean uninstallation.

> [!NOTE]
> Ghostline is 100% offline and privacy-first. All OCR processing and AI reasoning occur locally on your machine (`127.0.0.1:11434`). It never sends your screen, microphone, or system audio to external servers.

---

## Table of Contents
1. [Windows Defender & SmartScreen Guide](#1-windows-defender--smartscreen-guide)
   - [SmartScreen Warning vs. Antivirus Detection](#11-smartscreen-warning-vs-antivirus-detection)
   - [Cryptographic Hash (SHA-256) Verification](#12-cryptographic-hash-sha-256-verification)
   - [Responding Safely to "Windows protected your PC"](#13-responding-safely-to-windows-protected-your-pc)
   - [Handling Quarantine & Submitting False Positives](#14-handling-quarantine--submitting-false-positives)
   - [What NOT to Do: Security Best Practices](#15-what-not-to-do-security-best-practices)
2. [Taskbar and System Tray Setup](#2-taskbar-and-system-tray-setup)
   - [Pinning Ghostline to the Taskbar](#21-pinning-ghostline-to-the-taskbar)
   - [Showing Ghostline in the Notification Area (System Tray)](#22-showing-ghostline-in-the-notification-area-system-tray)
   - [Locating Hidden Tray Icons (Upward Arrow `^`)](#23-locating-hidden-tray-icons-upward-arrow-)
   - [Creating a Desktop Shortcut](#24-creating-a-desktop-shortcut)
   - [Configuring Startup with Windows](#25-configuring-startup-with-windows)
   - [Windows Firewall Configuration](#26-windows-firewall-configuration)
3. [Microphone Permissions & Audio Configuration](#3-microphone-permissions--audio-configuration)
   - [Granting Windows Microphone Access](#31-granting-windows-microphone-access)
   - [System Audio & WASAPI Loopback Recording](#32-system-audio--wasapi-loopback-recording)
   - [Sound Device Selection & Exclusive Mode Troubleshooting](#33-sound-device-selection--exclusive-mode-troubleshooting)
4. [Display Scaling, Multi-Monitor & Hotkeys](#4-display-scaling-multi-monitor--hotkeys)
   - [High-DPI Scaling (100%, 125%, 150%)](#41-high-dpi-scaling-100-125-150)
   - [Multi-Monitor Window Positioning & HUD Recovery](#42-multi-monitor-window-positioning--hud-recovery)
   - [Resolving Keyboard Shortcut Conflicts](#43-resolving-keyboard-shortcut-conflicts)
5. [Local AI Model Setup (Ollama)](#5-local-ai-model-setup-ollama)
6. [Updates, Configuration Storage & Clean Uninstallation](#6-updates-configuration-storage--clean-uninstallation)

---

## 1. Windows Defender & SmartScreen Guide

### 1.1 SmartScreen Warning vs. Antivirus Detection
When launching newly downloaded open-source software on Windows, it is critical to understand the difference between a **reputation warning** and an **antivirus detection**:

| Attribute | Microsoft Defender SmartScreen | Microsoft Defender Antivirus |
| :--- | :--- | :--- |
| **Trigger** | Executable has low download volume / unknown cloud reputation | Known virus, Trojan, or heuristic malware signature |
| **Dialog Appearance** | Blue banner: *"Windows protected your PC"* | Red/amber Windows notification: *"Threat found - action needed"* |
| **File Status** | File remains on disk; execution is paused pending confirmation | File is quarantined or blocked from execution |
| **Why Ghostline Triggers It** | Ghostline is free open-source software and does **not** use an expensive corporate EV (Extended Validation) code-signing certificate ($400–$700/year). SmartScreen flags newly compiled releases as having an *"Unknown Publisher"* until sufficient reputation builds. | Ghostline clean builds contain zero malware. If triggered, it is typically a generic heuristic false positive on PyInstaller runtime loaders. |

---

### 1.2 Cryptographic Hash (SHA-256) Verification
Before bypassing any prompt, always verify that your downloaded file is authentic and unaltered.

1. Open **Windows PowerShell** (Press `Win + X` → select **Terminal** or **PowerShell**).
2. Run the `Get-FileHash` command against your downloaded installer or portable archive:

```powershell
Get-FileHash -Algorithm SHA256 "$HOME\Downloads\Ghostline-Setup.exe"
```

3. Compare the output hash against the official values published in `checksums.txt`:

| Release Asset | Official SHA-256 Hash |
| :--- | :--- |
| **`Ghostline-Setup.exe`** | `692034bd97883f4f093f25ae32e61a06c2a1adb945da09583a152680e5391775` |
| **`Ghostline-v1.0.0-win64-portable.zip`** | `a3e95684b7d2c25f95071f508a9ac76380e5152dc3c7858949781f7c6d8aaf04` |
| **`RELEASE_NOTES.md`** | `5f47a3d9fdce67a7f24e721d789517c6f02df406b86a5cae331ea30cd5ae753b` |

> [!TIP]
> If the hashes match, your file is byte-for-byte identical to the official release built directly from the open-source repository.

---

### 1.3 Responding Safely to "Windows protected your PC"
When running `Ghostline-Setup.exe` or `Ghostline.exe` for the first time, Windows SmartScreen may present a dialog:

```
┌─────────────────────────────────────────────────────────────┐
│  Windows protected your PC                                  │
│                                                             │
│  Microsoft Defender SmartScreen prevented an unrecognized   │
│  app from starting. Running this app might put your PC      │
│  at risk.                                                   │
│                                                             │
│  <u>More info</u>                                                │
│                                           [ Don't run ]     │
└─────────────────────────────────────────────────────────────┘
```

**Step-by-Step Safe Resolution:**
1. Click the underlined **"More info"** link on the dialog.
2. The dialog expands to reveal:
   - **App:** `Ghostline-Setup.exe` (or `Ghostline.exe`)
   - **Publisher:** Unknown publisher
3. Verify the app name matches what you downloaded.
4. Click the newly revealed **"Run anyway"** button.

```
┌─────────────────────────────────────────────────────────────┐
│  Windows protected your PC                                  │
│                                                             │
│  App:       Ghostline-Setup.exe                             │
│  Publisher: Unknown publisher                               │
│                                                             │
│                     [ Run anyway ]        [ Don't run ]     │
└─────────────────────────────────────────────────────────────┘
```

---

### 1.4 Handling Quarantine & Submitting False Positives
If Microsoft Defender or a third-party antivirus flags Ghostline due to a heuristic false-positive (common with Python/PyInstaller packaged executables):

1. Open **Windows Security**:
   - Press `Win + S` → type **Windows Security** → press `Enter`.
2. Navigate to **Virus & threat protection** → click **Protection history**.
3. Inspect the quarantined item. Confirm the path points to `%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe` or your extracted folder.
4. If quarantined mistakenly, select **Actions** → **Restore**.
5. **Report the False Positive directly to Microsoft:**
   - Visit the official portal: [Microsoft Security Intelligence File Submission](https://www.microsoft.com/en-us/wdsi/filesubmission).
   - Select **"I believe this file is not malware (false positive)"**.
   - Upload the executable so Microsoft's automated analysis team can whitelist the SHA-256 hash in future definition updates.

---

### 1.5 What NOT to Do: Security Best Practices

> [!CAUTION]
> **Never disable Microsoft Defender Antivirus or turn off Real-Time Protection** just to run Ghostline. A legitimate open-source application should never require compromising your machine's security posture.

- **DO NOT** disable Windows Defender Real-Time Protection.
- **DO NOT** create broad drive-level exclusions (e.g., excluding all of `C:\`, `C:\Users`, or your entire `Downloads` folder).
- **ONLY IF NECESSARY:** If Windows Defender repeatedly quarantines a verified binary after hash verification, add an exclusion **only** for the single verified file path:
  - `Windows Security` → `Virus & threat protection settings` → `Manage settings` → `Exclusions` → `Add or remove exclusions` → `File` → `%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe`.

---

## 2. Taskbar and System Tray Setup

Ghostline is designed to live quietly in your taskbar and notification area (system tray) so it remains instantly accessible without cluttering your workspace.

### 2.1 Pinning Ghostline to the Taskbar
Pinning ensures Ghostline is always one click away from your Windows taskbar:

1. Launch **Ghostline** (via Start Menu, Desktop shortcut, or `%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe`).
2. While Ghostline is open, find its ghost icon in the Windows taskbar.
3. **Right-click** the Ghostline taskbar icon.
4. Select **Pin to taskbar**.

```
  ┌───────────────────────────────┐
  │ 👻 Ghostline                  │
  ├───────────────────────────────┤
  │ 📌 Pin to taskbar      <─── Select this
  │ ❌ Close window               │
  └───────────────────────────────┘
  [ 🪟 Start ] [ 🔍 Search ] [ 👻 ]  ... [ 🔊 ] [ 12:00 PM ]
```

---

### 2.2 Showing Ghostline in the Notification Area (System Tray)
By default, Windows hides background app icons inside the overflow flyout. Follow these steps to ensure Ghostline's tray icon is permanently visible near the system clock:

#### On Windows 11:
1. Press `Win + I` to open **Windows Settings**.
2. Navigate to **Personalization** → **Taskbar**.
3. Click to expand **Other system tray icons**.
4. Scroll through the list to find **Ghostline**.
5. Switch the toggle to **On**.

```
Windows Settings > Personalization > Taskbar > Other system tray icons
┌─────────────────────────────────────────────────────────────┐
│  👻 Ghostline                                     [  ON  ]  │
│     Ghostline Background Engine & Tray Status               │
└─────────────────────────────────────────────────────────────┘
```

#### On Windows 10:
1. Press `Win + I` to open **Windows Settings**.
2. Navigate to **Personalization** → **Taskbar**.
3. Under the **Notification area** heading, click **Select which icons appear on the taskbar**.
4. Find **Ghostline** and toggle the switch to **On**.

---

### 2.3 Locating Hidden Tray Icons (Upward Arrow `^`)
If Ghostline is running but you do not see its icon beside your clock:

1. Look at the right side of your taskbar near the clock and sound icon.
2. Click the **upward arrow (`^`)** to open the hidden notification icons flyout.
3. Look for the **Ghostline** icon.
4. **Quick drag trick:** Click and hold the Ghostline icon inside the flyout, then drag it directly onto the main taskbar tray to keep it visible permanently!

```
       ┌───────────────┐
       │   [ 👻 ]      │  <─── Ghostline in overflow flyout
       │ [ 🛡️ ] [ 📶 ] │
       └───────┬───────┘
  ─────────────┴──────────────────────
  ... [ ^ ] [ 🔊 ] [ ENG ] [ 12:00 PM ]
        │
     Click here
```

---

### 2.4 Creating a Desktop Shortcut
The Ghostline standard installer creates a Desktop shortcut automatically. If you are using the portable ZIP distribution or need to re-create the shortcut:

1. Open File Explorer and navigate to your Ghostline folder:
   - Installed version: `%LOCALAPPDATA%\Programs\Ghostline\`
   - Portable version: Where you extracted `Ghostline-v1.0.0-win64-portable.zip`.
2. Locate `Ghostline.exe`.
3. **Right-click `Ghostline.exe`**:
   - **Windows 11:** Select **Show more options** → **Send to** → **Desktop (create shortcut)**.
   - **Windows 10:** Select **Send to** → **Desktop (create shortcut)**.

---

### 2.5 Configuring Startup with Windows
If you want Ghostline to be ready whenever you boot your PC:

#### Method A: Windows Settings
1. Open **Settings** (`Win + I`) → **Apps** → **Startup**.
2. Locate **Ghostline** in the list.
3. Toggle the switch to **On**.

#### Method B: Task Manager
1. Press `Ctrl + Shift + Esc` to open **Task Manager**.
2. Click the **Startup apps** tab (the speedometer icon on Windows 11).
3. Right-click **Ghostline** and select **Enable**.

#### Method C: Startup Folder (Works for both Portable & Installed)
1. Press `Win + R`, type `shell:startup`, and press `Enter`.
2. Copy and paste your `Ghostline` shortcut into this folder (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`).

---

### 2.6 Windows Firewall Configuration
Ghostline is an entirely local, on-device application. It uses a **Zero-Socket architecture**—it does not expose any open listening network ports to the outside world.

```
┌─────────────────────────────────────────────────────────────┐
│  Windows Defender Firewall Prompt                           │
│                                                             │
│  Windows Defender Firewall has blocked some features of     │
│  this app.                                                  │
│                                                             │
│  [✓] Private networks (home or work)  <─── KEEP CHECKED     │
│  [ ] Public networks (airports, cafes) <─── UNCHECK THIS    │
│                                                             │
│                    [ Allow access ]      [ Cancel ]         │
└─────────────────────────────────────────────────────────────┘
```

- Ghostline only connects to **Ollama** via the local loopback interface: `127.0.0.1:11434`.
- If Windows Firewall prompts you:
  - Ensure **Private networks** is checked.
  - **UNCHECK Public networks** to maintain maximum device security.
  - Ghostline never accepts inbound connections from other computers on your network.

---

## 3. Microphone Permissions & Audio Configuration

Ghostline includes real-time live transcription and meeting question assistance (`Alt + L`). To capture both your voice and remote participants in video calls, configure the following settings:

### 3.1 Granting Windows Microphone Access
If pressing `Alt + L` produces no transcript or shows a microphone error, Windows privacy settings may be blocking desktop audio input.

#### Windows 11:
1. Press `Win + I` → **Privacy & security** → **Microphone**.
2. Verify **Microphone access** is turned **On**.
3. Verify **Let apps access your microphone** is turned **On**.
4. Scroll down to **Let desktop apps access your microphone** and verify it is toggled **On**.

#### Windows 10:
1. Press `Win + I` → **Privacy** → **Microphone**.
2. Ensure **Allow apps to access your microphone** is **On**.
3. Scroll down and verify **Allow desktop apps to access your microphone** is set to **On**.

---

### 3.2 System Audio & WASAPI Loopback Recording
Ghostline uses the high-performance Windows Audio Session API (**WASAPI Loopback**) to capture system audio.

- **No Virtual Cables Needed:** You do **not** need to install third-party software like "Virtual Audio Cable" or enable legacy "Stereo Mix".
- **Dual-Stream Mixing:** Ghostline captures your local microphone (so questions you speak aloud are transcribed) and the system playback stream (so questions asked by interviewers, teachers, or colleagues on Zoom, Teams, Google Meet, or Discord are transcribed).

---

### 3.3 Sound Device Selection & Exclusive Mode Troubleshooting

#### Setting the Default Audio Device:
1. Press `Win + I` → **System** → **Sound** (or press `Win + R`, type `mmsys.cpl`, and press `Enter`).
2. Under **Output**, set your primary headset or speakers as the **Default Device**.
3. Under **Input**, set your primary microphone as the **Default Device**.

#### Troubleshooting Exclusive Mode:
Some USB audio interfaces and DAC drivers enable "Exclusive Mode", which prevents other programs from accessing the audio stream:
1. In `mmsys.cpl` (Sound Control Panel), right-click your output device → **Properties**.
2. Go to the **Advanced** tab.
3. If loopback audio capture fails, uncheck **"Allow applications to take exclusive control of this device"**.
4. Click **Apply** and **OK**.

---

## 4. Display Scaling, Multi-Monitor & Hotkeys

### 4.1 High-DPI Scaling (100%, 125%, 150%)
Ghostline is built with full Windows Per-Monitor DPI awareness:
- The floating HUD overlay and main dashboard automatically scale their typography, borders, and margins based on your active monitor's DPI setting (e.g. 125% or 150% on laptops, 200% on 4K displays).
- To adjust scaling: Open **Settings** (`Win + I`) → **System** → **Display** → **Scale**.

---

### 4.2 Multi-Monitor Window Positioning & HUD Recovery
Ghostline uses global virtual desktop coordinates (`SM_XVIRTUALSCREEN`, `SM_YVIRTUALSCREEN`) to span seamlessly across multi-monitor setups.

- **HUD Appears Off-Screen?** If you disconnect an external monitor and the HUD was previously positioned there:
  - Press `Ctrl + Shift + P` to toggle and reset the HUD to your current cursor position.
  - Or edit `%APPDATA%\Ghostline\config.json` and reset `"hud_x": 100`, `"hud_y": 100`.
- **Main Window Off-Screen?**
  - Click Ghostline on the taskbar.
  - Press `Alt + Space`, then press `M` (Move).
  - Use your keyboard arrow keys to bring the window back into view.

---

### 4.3 Resolving Keyboard Shortcut Conflicts
Ghostline uses global Windows hotkeys:

| Default Shortcut | Action |
| :--- | :--- |
| **`Alt + /`** | Screen Question Solve (captures region under cursor and solves via local AI) |
| **`Alt + L`** | Audio Assistance Toggle (starts/stops microphone & meeting transcription) |
| **`Alt + A`** | Toggle Floating Audio Panel |
| **`Alt + Q`** | Query Local AI about the recent audio transcript |
| **`Ctrl + Shift + P`** | Pause / Freeze HUD Position |

**If a shortcut conflicts with an IDE, Discord, or graphics software:**
1. Open Ghostline → Click **Settings** in the left navigation sidebar.
2. Under **General Settings → Shortcuts**, enter your preferred key combination.
3. Click **Save Changes**.
4. Alternatively, you can trigger Screen Solve and Audio Listen directly from the **System Tray menu** without using any keyboard shortcut.

---

## 5. Local AI Model Setup (Ollama)

Ghostline relies on a locally running Ollama instance for 100% private, on-device inference.

### Step 1: Install Ollama
Download and run the Windows installer from [https://ollama.com](https://ollama.com).

### Step 2: Verify Ollama Service is Running
Ollama runs in your Windows notification area. You can verify it is active by opening PowerShell and running:
```powershell
curl http://127.0.0.1:11434/api/tags
```
If active, it returns a JSON response listing your installed models.

### Step 3: Pull Recommended Models
Open Windows Terminal / Command Prompt and pull the recommended high-speed reasoning model:
```powershell
# Recommended for standard laptops & PCs (approx. 2.3 GB)
ollama pull phi3:mini

# Alternative high-quality model (approx. 2.0 GB)
ollama pull llama3.2:3b
```

Once pulled, Ghostline automatically connects to `phi3:mini` and marks the engine status as **Ready**.

---

## 6. Updates, Configuration Storage & Clean Uninstallation

### 6.1 Preserving User Settings During Updates
Ghostline cleanly separates executable binaries from user configuration:
- **Application Binaries:** `%LOCALAPPDATA%\Programs\Ghostline\`
- **User Settings & History:** `%APPDATA%\Ghostline\` (`config.json`, `history.jsonl`, `app.log`)

When you download an updated version of `Ghostline-Setup.exe` and install it, your custom hotkeys, selected AI model, and question history in `%APPDATA%\Ghostline` are **automatically preserved**.

---

### 6.2 Clean Uninstallation
If you ever need to uninstall Ghostline:

1. Open **Windows Settings** (`Win + I`) → **Apps** → **Installed apps**.
2. Find **Ghostline** in the list, click the three-dots menu (`...`), and select **Uninstall**.
3. Or run the uninstaller directly:
   ```cmd
   "%LOCALAPPDATA%\Programs\Ghostline\uninstall.bat"
   ```
4. **Choose whether to keep user data:** The uninstaller will ask if you want to keep or delete `%APPDATA%\Ghostline`. To completely wipe all traces, confirm deletion.
