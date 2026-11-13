# Changelog

All notable changes to **Ghostline** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.8] - 2026-11-13

### Fixed
- **Open Maximized Window State**: Implemented "Open maximized" setting (Settings > General, default `True`) so Ghostline opens maximized to fill the display on launch while keeping window controls and the Windows taskbar visible. When restored to normal, validates saved geometry against the current screen work area (off-screen or too large coordinates automatically reset to 85% centered).
- **Setup Wizard Layout & Small Screen Support**: Fixed broken layout on laptops with 1366x768 at 150% scaling (480px work area). Removed hardcoded `setFixedSize(620, 520)`, replaced with responsive sizing `min(work_area * 0.9, 680x560)`, wrapped all 3 step pages in frameless `QScrollArea`s, permanently pinned footer navigation buttons (`Skip Setup`, `Back`, `Next`) to the bottom dialog layout, enabled word-wrapping across all text labels, and added keyboard navigation (Escape to skip, Enter to advance).
- **Startup Latency & UI Thread Stalls**:
  - Converted heavy dependencies (`torch`, `faster-whisper`, `scipy.signal.resample_poly`) to lazy PEP 562 imports, slashing cold import time from ~10.0s down to ~1.6s (-84%).
  - Replaced synchronous `save_config` on window resize and move with a 300ms debounced timer in `WindowStateManager`, eliminating a 124ms disk I/O stall on the UI thread.
  - Moved periodic Ollama connection status checks to asynchronous background worker threads, eliminating 104–155ms socket read stalls on the main UI thread.
  - Paused polling timers when the main window is hidden or minimized to tray.
- **Laptop & Weak PC Performance (Lite Mode)**:
  - Added zero-PII Hardware Profile detection (< 2ms) checking RAM, logical cores, and Windows Battery Saver status.
  - Added `Performance Mode` setting (`Auto (Recommended)` / `Standard` / `Lite`) in Settings > General. In Lite mode, document history blocks are capped at 100, visual effects are streamlined, and background meter update rates are throttled.
  - Displayed hardware profile summary line in Setup Wizard Step 1 and Help > Diagnostics.

## [1.0.7] - 2026-11-08

### Fixed
- **HUD "Ask" Input & Activation**: Implemented dynamic Win32 activation state machine (`HudFocusController`) for floating HUD overlays (`QtGhostlineHudOverlay` and `QtLiveAudioPanel`). Temporarily strips `WS_EX_NOACTIVATE` upon mouse focus to accept keyboard input, submits on Enter or Ask button, and reinstates `WS_EX_NOACTIVATE` upon Enter, Escape, click-away, or 10s idle while strictly preserving `WDA_EXCLUDEFROMCAPTURE`.
- **Global Hotkeys with Visible HUD**: Updated solve worker and event bridge to stream tokens and transition status states directly to the HUD in place when it is already open (`isVisible()`), eliminating HUD dropouts without flicker or focus-stealing. Preserved rule that hidden HUD never auto-shows on `Alt + /` unless `show_hud_on_solve` is explicitly enabled.
- **Missing Global Hotkeys Registered**: Registered `HOTKEY_COPY_LAST` (`Alt + Shift + C`) and `HOTKEY_OPTION_1..4` (`Alt + 1 / 2 / 3 / 4`) in Win32 `RegisterHotKey` listener loop, enabling immediate clipboard copying and option selection from anywhere in Windows.
- **Live Answering Latency & Adaptive Endpointing**:
  - Replaced hardcoded 2.0s debounce timer with responsive 0.15s (0.05s in early start) delay for finalized speech utterances.
  - Implemented adaptive endpointing: utterance silence threshold dynamically scales to 0.45s (0.35s in early start) for questions, with pauses < 0.30s ignored and boundaries clamped between [0.35s, 1.20s].
  - Pinned Ollama model weights in RAM via `"keep_alive": "5m"` in `solve_question` requests to prevent cold unload stalls.
  - Added experimental *"Faster answers (early start)"* toggle in Settings > Audio.
  - Instrumented end-to-end timing marks: `speech_end`, `endpoint_decided`, `stt_final`, `question_sent`, `request_sent`, `first_token`, `answer_complete`, `rendered`.

## [1.0.6] - 2026-11-08

### Added
- **In-App Support & Community Section**: Added an accessible, theme-consistent "Support Ghostline" card in the Help view (placed right after the keyboard hotkey cheat sheet) and a subtle "Star · Support" navigation link in the sidebar footer.
  - Primary **Star on GitHub** call to action opening the official repository in the system browser via `QDesktopServices.openUrl`.
  - Dark-on-light **Buy Me a Coffee (UPI)** QR card rendered on a crisp solid white tile (`#FFFFFF`), with [Show larger] modal viewer dialog and [Save QR image] action.
  - Transparent bank account and fraud safety disclosure notes (*"Scanning shows the payee name from my bank account."* and *"Only pay through this app or the official GitHub repository."*).
  - Quick action links for [Report a bug], [Suggest a feature], and [Copy repo link].
  - Strictly local, zero-network, zero-telemetry architecture: no star count scraping, no polling, no reminders, no popups or banners.

## [1.0.5] - 2026-11-08

### Fixed
- **HUD Live Panel Text Overflow**: Replaced `QLabel` with `QTextBrowser` configured with `WrapAtWordBoundaryOrAnywhere`, `ScrollBarAlwaysOff` for horizontal bar, and automatic newest-line scrolling. Clamped HUD overlay dimensions to 90% of screen work area (maximum 720×900 px) and bounded history to 200 lines, preventing unspaced foreign scripts or long strings from blowing out window geometry.
- **Wrong-Language Hallucinations & Looping Text**: Pinned default audio language to `"en"`. Added multi-tier `AudioOutputGuard` filter that detects and drops token/n-gram repetition loops, Unicode script mismatches (Thai, Lao, Japanese under English mode), silence hallucinations on low RMS energy, and excessively fast speech rates.
- **Acoustic Speaker Echo Guard**: Cross-channel acoustic echo guard buffers system loopback speech for 4.5 seconds and cancels microphone segments matching speaker playback above 70% similarity, with a one-time non-intrusive tip to use headphones.
- **Silent Video Audio**: Removed background music from all website and master launch videos, replacing with clean silent AAC tracks.

## [1.0.4] - 2026-11-08

### Added
- **Dedicated Live Session Card on Home**: Synchronized live transcription, turn-by-turn dialogue, real-time thinking elapsed timer ticker (`lbl_live_thinking`), and streaming AI answers directly within the main dashboard window.
- **Token-by-Token Live LLM Streaming**: Replaced blocking inference with sub-second streaming tokens across both the Home Live session card and floating HUD overlay simultaneously via `LiveSessionViewModel`.
- **Speech-to-Text Performance & Policies Suite**: Added Speed ↔ Accuracy model selector (`tiny`, `base`, `small`), "When to answer" trigger selector (`Questions only`, `After every pause`, `Manual only`), and a built-in one-click latency benchmark in Settings.
- **Provider Offline Error Recovery Banner**: Clear plain-English error states with actionable one-click recovery buttons (`[Start Ollama]` background launch, `[Open AI Settings]`).
- **Privacy-Safe Performance Telemetry**: Standardized non-content STT diagnostics line (`faster-whisper [tiny] | int8 | 6 threads | load: 245ms | avg RTF 0.027`) capturing pure hardware and pipeline performance without logging user speech or prompt text.

### Performance & Speed
- **51% Faster Transcription on Hybrid CPUs**: Clamped Whisper STT threads to 6 on Intel hybrid architecture (13th Gen i5-13420H), eliminating thread thrashing across P-cores and E-cores and cutting latency on 7.6s audio from 421.8ms to 205.0ms (RTF: 0.0270, 37.1x real-time).
- **Zero Cold-Start Lag via Background Preloading**: Asynchronously loads Whisper weights and performs silent warmup inference on application launch, completely eliminating the first-turn model load freeze.
- **Fair Dual Audio Queuing**: Separated microphone and system loopback audio into dedicated bounded queues (maxlen=25) with fair round-robin scheduling and backlog pressure protection.
- **Low-Latency VAD & Streaming Partials**: Shortened pause split threshold to 0.70s and added streaming partial transcript previews every 0.9s–1.2s during active speech.
- **Ollama CPU Contention Elimination**: Clamped local Ollama LLM worker to `num_thread: 4` with `keep_alive: "5m"` warm model retention, preventing CPU core starvation during live sessions.

---

## [1.0.3] - 2026-11-08

### Added
- **Multi-Key Hardware Keyboard LED Signalling**: Restored physical keyboard LED blinking across Caps Lock, Num Lock, and Scroll Lock keys (1 pulse for A/Option 1/True, 2 pulses for B/Option 2/False, 3 pulses for C/Option 3, 4 pulses for D/Option 4) via Win32 `SendInput`/`keybd_event` without stealing window focus.
- **Rebuilt Master Video Suite**: Complete re-generation of Launch Film (H1, 92s, 1080p), seamless hero loop (H2, 8s, 720p, <=2MB), Setup Tutorial (V1, 140s), Usage Walkthrough (V2, 180s), and Vertical Shorts (S1–S5, 35s each, 1080x1920) with synthesized electronic sound bed (-14.1 LUFS / <= -1.5 dBTP), kinetic typography, WebVTT subtitles, plain text transcripts, and JPEG posters <= 60 KB.
- **Fluent 2 Dark Website Overhaul**: Redesigned marketing website featuring an interactive 3D tilted hero application card preview, accessible native HTML5 `<dialog>` video modal with focus trapping and keyboard navigation, responsive 12-column Bento Grid, preserved interactive demo sandbox, and updated documentation.

### Fixed
- **Silent Output Mode**: Completely eliminated intrusive desktop tray balloon notifications on answer generation in favor of silent status badges and keyboard LED signalling.
- **Web Video Faststart & Zero Freeze Verification**: Encoded all web media assets with `+faststart` (moov atom at byte 36) enabling immediate seeking and verified zero static freezes > 1.2s across all videos.

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
