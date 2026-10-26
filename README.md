# Ghostline

**100% Offline, Privacy-First On-Device AI Question Recognition, Screen Reasoning & Voice Assistant for Windows 10 & 11.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)](https://microsoft.com/windows)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python)](https://python.org)
[![Inference: Ollama](https://img.shields.io/badge/Inference-Ollama%20(Local)-white.svg?logo=ollama)](https://ollama.com)
[![Tests: 201 Passed](https://img.shields.io/badge/Tests-201%2F201%20Passed-success.svg)](tests/)

Ghostline is a lightweight, zero-telemetry Windows desktop application that solves multiple-choice questions, code challenges, and technical prompts directly on your screen and live from video calls. It uses native Windows Media OCR and local Ollama inference with zero external network requests.

---

## 1. Quick Start: One-Click Installation

No terminal, virtual environment, or manual package setup is required.

### Step 1: Install Ollama (Prerequisite)
1. Download and install Ollama from [https://ollama.com](https://ollama.com).
2. Open Windows Terminal / Command Prompt and pull the recommended model:
   ```cmd
   ollama pull phi3:mini
   ```

### Step 2: Download & Launch Ghostline
Ghostline is distributed in two official, pre-compiled verified packages for 64-bit Windows 11 & 10:

| Distribution Package | Size | SHA-256 Checksum | Best For |
| :--- | :--- | :--- | :--- |
| **`Ghostline-v1.0.0-win64-portable.zip`** | **387.11 MB** | `ec40ee74e129683f71f204ca86f98592d72917094f75a2338c6c2d7274775484` | Zero installation; extract and double-click `Run-Ghostline.bat` anywhere |
| **`Ghostline-Setup.exe`** | **394.64 MB** | `1552017645d5c6305dc2a7c3ca9658ecd85c01651f000103d57f02f66b74b51c` | Standard auto-installer into `%LOCALAPPDATA%` with Desktop & Start Menu shortcuts |
| **`Setup-Offline-AI.bat`** | **2.4 KB** | `1-Click script` | Optional guided batch script to verify Ollama and pull `phi3:mini` |

- **Official Launch Film (20s MP4):** [`website_download/videos/ghostline_launch.mp4`](website_download/videos/ghostline_launch.mp4)
- **Step-by-Step Installation Tutorial (82s MP4):** [`website_download/videos/ghostline_tutorial.mp4`](website_download/videos/ghostline_tutorial.mp4)
- **Interactive Download Website:** [`website_download/index.html`](website_download/index.html)

For step-by-step instructions on configuring Windows Defender, SmartScreen, system tray icons, and microphone access, see the [Windows Post-Installation Setup & Security Guide](docs/WINDOWS_SETUP_GUIDE.md).


---

## 2. Windows Post-Installation & Security Quick Guide

> [!IMPORTANT]
> Ghostline is free open-source software built without expensive commercial code-signing certificates. Windows SmartScreen may show an *"Unknown Publisher"* warning on first run. Never disable Windows Defender; follow verified cryptographic verification instead.

| Topic | Quick Action / Setting Path | Documentation |
| :--- | :--- | :--- |
| **SmartScreen Warning** | Click **"More info"** on the blue dialog, then click **"Run anyway"**. | [SmartScreen Guide](docs/WINDOWS_SETUP_GUIDE.md#1-windows-defender--smartscreen-guide) |
| **Verify SHA-256 Hash** | `Get-FileHash -Algorithm SHA256 .\Ghostline-Setup.exe` (matches `checksums.txt`) | [Hash Verification](docs/WINDOWS_SETUP_GUIDE.md#12-cryptographic-hash-sha-256-verification) |
| **Pin to Taskbar** | Right-click the running Ghostline taskbar icon → Select **Pin to taskbar**. | [Taskbar Setup](docs/WINDOWS_SETUP_GUIDE.md#21-pinning-ghostline-to-the-taskbar) |
| **Show in System Tray** | **Win 11:** Settings → *Personalization* → *Taskbar* → *Other system tray icons* → Ghostline **On**.<br>**Win 10:** Settings → *Personalization* → *Taskbar* → *Select which icons appear* → Ghostline **On**. | [System Tray Guide](docs/WINDOWS_SETUP_GUIDE.md#22-showing-ghostline-in-the-notification-area-system-tray) |
| **Find Hidden Tray Icon** | Click the **`^` (upward arrow)** near the system clock, then drag the Ghostline icon out. | [Hidden Tray Icons](docs/WINDOWS_SETUP_GUIDE.md#23-locating-hidden-tray-icons-upward-arrow-) |
| **Microphone Access** | Settings → *Privacy & security* → *Microphone* → Ensure **Let desktop apps access your microphone** is **On**. | [Microphone Guide](docs/WINDOWS_SETUP_GUIDE.md#31-granting-windows-microphone-access) |
| **System Audio Capture** | Ghostline uses WASAPI loopback directly from your default speakers. No "Stereo Mix" or virtual audio cables needed. | [Audio Setup](docs/WINDOWS_SETUP_GUIDE.md#32-system-audio--wasapi-loopback-recording) |
| **Startup with Windows** | Settings → *Apps* → *Startup* (or Task Manager `Ctrl+Shift+Esc` → *Startup apps* tab). | [Startup Guide](docs/WINDOWS_SETUP_GUIDE.md#25-configuring-startup-with-windows) |

*For visual illustrations and interactive steps, see the [Interactive Web Guide](website_download/index.html#windows-setup) and [Full Offline Setup Guide](docs/WINDOWS_SETUP_GUIDE.md).*

---

## 3. Radical UI Simplification

Ghostline has been completely redesigned around a single, distraction-free main screen. Complex dashboards, multi-tab sidebars, and nested menus have been replaced with a clear, functional interface.

```
┌────────────────────────────────────────────────────────────┐
│  👻 Ghostline v1.0.0            ● Ready   [⚙ Settings] [?] │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [  ■  Stop Ghostline Engine  ]                            │
│  Live Status: Active & Listening for Hotkeys               │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 🖥 Screen Assistance                        [Alt + /]│  │
│  │ Capture full screen and solve question with local AI │  │
│  │ [ Run Screen Solve ]                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 🎙 Audio Assistance                         [Alt + L]│  │
│  │ Capture system/mic audio & live transcribe meetings  │  │
│  │ [ Start Listening ]   Mic: [||||  ] Loopback: [||    ]│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ LIVE ACTIVITY & RESULTS                              │  │
│  │ [Option B] What is the primary role of GC in Python? │  │
│  │ Generational cyclic garbage collector manages memory │  │
│  │ [ Copy Answer ]                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### Main Screen Components
1. **Start / Stop** — The primary toggle action to start or pause Ghostline's background engine and hotkeys.
2. **Screen Assistance** — Capture the screen and trigger the OCR + Ollama question solving pipeline (`Alt + /`).
3. **Audio Assistance** — Start/stop live microphone and system-audio loopback capture and transcription (`Alt + L`).
4. **Live Activity** — Compact, readable area displaying the current action, rolling transcript, latest result badge (`A-D`, `Code`), and one-click copy.
5. **Settings** — Minimal screen for essential configuration (Ollama URL, model name, capture mode), with an optional collapsible **Advanced Settings** section.
6. **Help & Diagnostics** — One-click health checklist (Ollama, Model, Windows OCR, Audio Devices) and interactive test buttons (`Test Mic`, `Test System Audio`, `Test Transcription`).

---

## 4. Core Features & Hotkeys

All core capabilities are preserved and operate entirely offline:

| Action | Hotkey | Description |
| :--- | :---: | :--- |
| **Screen Solve** | `Alt + /` | Captures active display, runs native Windows OCR (<40ms), reasons with local Ollama, and displays answer in HUD overlay. |
| **Audio Listen Toggle** | `Alt + L` | Starts or stops live audio capture (Microphone + Video Call loopback). |
| **Audio Panel Toggle** | `Alt + A` | Opens the dedicated Live Audio transcription overlay. |
| **Ask Ghostline** | `Alt + Q` | Queries the local AI model regarding the current conversation transcript. |
| **Pause Hover HUD** | `Ctrl + Shift + P` | Temporarily freezes the floating HUD overlay position. |

### Floating HUD Overlay
- Translucent, stealth dark glassmorphic window (`WS_EX_TOPMOST`, `WS_EX_NOACTIVATE`).
- Never steals focus from active exams, code editors, or video call applications.
- Displays question type, confidence rating, structured explanation, and formatted code blocks.

---

## 5. Repository Structure

```
Ghostline/
├── bin/
│   └── win_ocr.exe               # High-speed native Windows Media OCR binary
├── dist/
│   └── Ghostline/                # Standalone packaged application directory
│       ├── Ghostline.exe         # Main application executable
│       └── _internal/            # Bundled Python runtime, CTranslate2 & PyTorch
├── installer/
│   └── setup_gui.py              # Standalone dark-themed Windows installer GUI
├── release_dist/
│   ├── Ghostline-Setup.exe       # 100% self-contained one-click Windows installer
│   ├── Ghostline-v1.0.0-win64-portable.zip # Portable distribution package
│   └── checksums.txt             # Cryptographic SHA-256 verification hashes
├── ghostline/
│   ├── app.py                   # Application lifecycle, single-instance mutex & tray
│   ├── config.py                # AppData configuration management
│   ├── core/
│   │   ├── audio_capture.py     # WASAPI loopback & microphone audio engine
│   │   ├── llm_client.py        # Local Ollama client & health check
│   │   ├── ocr_engine.py        # Windows OCR integration & question parsing
│   │   ├── pipeline.py          # Question recognition & solving pipeline
│   │   └── transcriber.py       # Local Faster-Whisper transcription engine
│   ├── fixtures/
│   │   └── test_speech.wav      # Bundled audio test fixture
│   └── ui/
│       ├── audio_panel.py       # Live audio floating panel
│       ├── hud_overlay.py       # Floating non-activating HUD overlay
│       └── main_window.py       # Radically simplified single main screen
├── tests/                       # 22 automated test suites (201 passing tests)
├── build_release.py             # Reproducible release packaging build script
├── installer.iss                # Inno Setup 6 compilation script
├── installer.ps1                # PowerShell automated installer
├── uninstall.ps1                # PowerShell clean uninstaller
├── ghostline.ico                # Application icon
└── requirements.txt             # Pinned Python dependencies
```

---

## 6. Building From Source

To build Ghostline and its release installers from source:

```cmd
git clone https://github.com/Mohammed-Ayyan/GhostLine.git
cd GhostLine

:: Install dependencies
pip install -r requirements.txt

:: Run full regression test suite (22 suites, 201 tests)
python tests/run_all_tests.py

:: Build application, standalone installer & portable zip
python build_release.py
```

Generated artifacts are automatically placed into `release_dist/`:
- **`release_dist/Ghostline-Setup.exe`**: Self-contained installer for end users.
- **`release_dist/Ghostline-v1.0.0-win64-portable.zip`**: Portable distribution.
- **`release_dist/checksums.txt`**: SHA-256 verification hashes.

---

## 7. Testing & Headless Diagnostics

You can test any packaged executable or development source without opening a GUI window by using the `--diagnostics` CLI flag:

```cmd
Ghostline.exe --diagnostics
```

Outputs machine-readable JSON status:
```json
{
  "status": "ok",
  "app": "Ghostline",
  "version": "1.0.0",
  "frozen": true,
  "app_dir": "%APPDATA%\\Ghostline",
  "win_ocr_path": "%LOCALAPPDATA%\\Programs\\Ghostline\\_internal\\bin\\win_ocr.exe",
  "win_ocr_exists": true,
  "fixture_exists": true,
  "ollama_running": true,
  "models_available": ["phi3:mini"],
  "target_model_installed": true
}
```

---

## 8. Clean Uninstallation

Ghostline can be uninstalled cleanly at any time:
1. Open **Windows Settings** -> **Apps** -> **Installed Apps**.
2. Find **Ghostline** and click **Uninstall**.
3. Or run the uninstaller directly:
   ```cmd
   "%LOCALAPPDATA%\Programs\Ghostline\uninstall.bat"
   ```

The uninstaller removes all application files, Start Menu entries, Desktop shortcuts, and registry keys while preserving or clearing user configuration as desired.

---

## 9. License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
