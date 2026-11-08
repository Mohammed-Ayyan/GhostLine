# Changelog

All notable changes to **Ghostline** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.2] - 2026-11-08

### Added
- **Native Inno Setup Installer & Portable Distribution**: Zero-dependency Windows installer (`Ghostline-Setup.exe`) and portable standalone package (`Ghostline-Portable.zip`) with SHA-256 integrity verification.
- **System Tray & Window Lifecycle Controls**: Configurable "Minimize to tray on close" and "Hide from taskbar" options with immediate Win32 runtime effect (`WS_EX_TOOLWINDOW` toggle and tray restoration).
- **Personal Profile Grounding for Interviews**: AI answers interview questions in authentic first-person voice using the candidate's saved education, skills, and experience rather than assistant meta-descriptions.
- **Provider-Aware Diagnostics & Sanitization**: Comprehensive diagnostics export with automatic DPAPI token redaction, system hardware detection, and active provider telemetry.
- **xAI Grok & Groq Cloud Engine Support**: Added custom User-Agent headers to prevent Cloudflare edge blocks (error 1010) and transformed raw JSON/HTTP errors into clear, actionable next steps.
- **Microsoft Fluent 2 Dark Restyle**: Complete UI transformation to the Fluent 2 design language across the Main Window, Sidebar, Navigation, Component Gallery, floating HUD, and system tray menu.
- **Fluent 2 Design Tokens**: Standardized color, elevation, typography (Segoe UI Variable), radii, spacing, and transition tokens.
- **Bring-Your-Own-Key (BYOK) Cloud Providers**: Integrated secure cloud LLM inference for OpenAI (`gpt-4o`, `gpt-4o-mini`), Anthropic (`claude-3-5-sonnet`), Google Gemini (`gemini-1.5-pro`, `gemini-1.5-flash`), Groq (`llama-3.3-70b-versatile`), and OpenRouter (`auto`).
- **Windows DPAPI Credential Security**: Cloud API keys are hardware-encrypted at rest using Windows DPAPI (`CryptProtectData`), tied to the active Windows user profile.
- **Personal Background Profile Grounding**: Users can upload or paste their resume/experience (PDF, DOCX, TXT) to ground behavioral, interview, and experience-based questions directly in their authentic background.
- **Enterprise Redaction Layer**: Real-time credential and sensitive profile fact scrubbing across logging handlers, formatters, Qt message handlers, and crash dumps (`ghostline/core/redaction.py`).
- **Transport Security & Endpoint Confirmation**: Strict HTTPS enforcement for cloud providers with loopback exemptions; interactive confirmation warning before sending credentials to non-default hosts.
- **Data Retention & Privacy Controls**: Added "Don't save history" option, automatic history retention purging (default 30 days), and a one-click "Clear History" confirmation modal. Default screenshot debug dumping disabled.
- **Path Traversal & Injection Safeguards**: Replaced unquoted shell commands with native Python; hardened file parsers with size caps (25MB file, 50-page PDF, 20MB XML) and Windows reserved device name checks (`CON`, `PRN`, `NUL`).
- **Third-Party Notices**: Comprehensive legal catalog in `THIRD_PARTY_NOTICES.md` detailing all dependencies and licenses.

### Fixed
- **Input Field Visibility & Contrast**: Redesigned all input fields across settings, profile, and provider configurations with distinct surface fills, subtle borders, focused glow states, and readable typography.
- **Label Transparency & Card Artifacts**: Eliminated canvas dark background "strips" behind card labels, ensuring clean rendering inside lighter card containers.
- **HUD Non-Stealing Focus & Auto-Show Honoring**: Scans via `Alt + /` strictly respect the "Show HUD automatically after a scan" setting, never raising or stealing focus when disabled.
- **Live Audio & Call Pipeline Stability**: Restored WASAPI loopback capture, Silero VAD segmentation, and Whisper int8 model loading with robust device error handling.
- **Ollama First-Run Lifecycle**: Graceful startup detection and auto-spawning for local Ollama daemons on clean systems.

---

## [1.0.1] - 2026-10-28

### Added
- **Dual-Stream Audio Pipeline**: Simultaneous microphone and system loopback audio capture using WASAPI.
- **Local Speech Transcription**: Offline int8 CPU transcription powered by `faster-whisper` and Silero VAD segmentation.
- **Live Audio HUD (`Alt + Q`)**: Dedicated floating HUD mode displaying live transcript streams, speaker attribution (`[You]` vs `[Call]`), and contextual AI assistance.
- **Per-Monitor V2 DPI Awareness**: Automatic coordinate translation across heterogeneous multi-monitor setups.

### Fixed
- **Question Extraction Pipeline**: Fixed multi-line question truncation by grouping OCR lines into cohesive question blocks.
- **Signal-to-Widget Thread Safety**: Resolved Qt cross-thread signal dispatch crashes.

---

## [1.0.0] - 2026-10-24

### Added
- **Native Windows OCR Engine**: Native C# Windows Runtime bridge (`bin/win_ocr.exe`) executing `Windows.Media.Ocr.OcrEngine`.
- **Local AI Reasoning Pipeline**: Integration with local Ollama daemon (`127.0.0.1:11434`).
- **Floating Glass HUD Overlay**: Translucent, non-focus-stealing floating window with draggable positioning.
- **Dynamic 32x32 Tray Indicator**: Pixel-perfect glyph rendering for answer options and status states.
- **Caps Lock Pulse Signaling**: Win32 `keybd_event` pulsed keyboard indicator with atomic state recovery.
- **Question Classification & Structured Output**: Automated classification into MCQ, Theory, and Code.
