# Ghostline v1.0.0 — Official Release Notes

**Release Date:** October 2026  
**Build:** v1.0.0-win64 (Standalone & Portable)  
**Platform:** Windows 10 & Windows 11 (64-bit)

---

## Highlights

Ghostline v1.0.0 is the official release of the 100% offline, privacy-first AI question recognition, screen reasoning, and voice assistant engine. Designed for zero-cloud autonomy, it delivers sub-second local Windows Media OCR, hardware-accelerated local LLM inference, dynamic system tray badges, live meeting loopback transcription, and an unintrusive floating HUD overlay.

### 1. Zero-Crash Startup Architecture
- **Pre-GUI Mutex Guard:** Solved the instant startup crash/flash caused by secondary instances constructing Tkinter windows before mutex verification. Secondary instances immediately wake the primary instance via custom Win32 message filter and exit cleanly with code 0.
- **UIPI Message Filter:** Registered `WM_GHOSTLINE_WAKEUP` through `ChangeWindowMessageFilter` to guarantee wake-up message delivery across integrity levels.
- **Resilient Hotkey Registration:** If hotkey `Alt + /` encounters Windows conflict error 1409, the engine logs diagnostic guidance without killing the message pump.
- **Asynchronous Ollama Probing:** Decoupled local Ollama HTTP reachability checks to background daemon threads, reducing startup latency to <20ms.

### 2. Radical UI Simplification
- Redesigned around a single, distraction-free main screen with Zinc/Slate dark aesthetic.
- **Start / Stop** toggle for background engine and hotkeys.
- **Screen Assistance (`Alt + /`)**: Captures active screen, runs native Windows OCR (<40ms), and queries local Ollama models.
- **Audio Assistance (`Alt + L`, `Alt + A`, `Alt + Q`)**: WASAPI loopback system-audio and microphone capture with local Faster-Whisper transcription.
- **Floating HUD Overlay**: Stealth non-activating topmost window with instant copy buttons and structured code blocks.

### 3. Packaging & Distribution
- **One-Click Installer (`Ghostline-Setup.exe`)**: Self-contained installer installing into `%LOCALAPPDATA%\Programs\Ghostline`.
- **Portable ZIP (`Ghostline-v1.0.0-win64-portable.zip`)**: Zero-setup distribution package.
- **Clean Uninstallation**: Registered Windows Settings uninstaller and `uninstall.bat`.

---

## System Requirements

- **Operating System:** Windows 10 (20H2+) or Windows 11 (64-bit)
- **Processor:** x86_64 Dual-Core or higher
- **RAM:** 8 GB minimum (16 GB recommended)
- **GPU (Optional):** NVIDIA GeForce (4 GB+ VRAM recommended for <300ms inference)
- **Local AI Daemon:** [Ollama](https://ollama.com) v0.1.30+ running locally

---

## Artifact Verification Hashes (SHA-256)

```text
692034bd97883f4f093f25ae32e61a06c2a1adb945da09583a152680e5391775  Ghostline-Setup.exe
a3e95684b7d2c25f95071f508a9ac76380e5152dc3c7858949781f7c6d8aaf04  Ghostline-v1.0.0-win64-portable.zip
```
