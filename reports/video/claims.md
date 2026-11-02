# Ghostline Launch Video — Verified Claims & Evidence Registry

**Audit Date**: 2026-11-02  
**Constraint**: Every spoken or displayed claim must be strictly grounded in the codebase or verified command output. Unverifiable claims (e.g. latency numbers like "<50ms", "zero latency", "100% offline without qualification", testimonials, fake ratings) are completely omitted.

---

## Claims Registry Table

| # | Promoted Claim | Visual / Voice Copy | Codebase Evidence (File:Line) | Verification Status |
| :- | :--- | :--- | :--- | :--- |
| **C-01** | Native Windows desktop assistive AI application | "Ghostline — Native Windows Assistive AI & Meeting Copilot" | `README.md:3`, `website/index.html:6-7, 42` | VERIFIED-AUTOMATED |
| **C-02** | Fluent 2 Dark design language | "Designed natively in Microsoft Fluent 2 Dark for Windows 10 & 11" | `README.md:5`, `ghostline/ui/fluent_theme.py:1-60` | VERIFIED-AUTOMATED |
| **C-03** | 3-Step Setup | "1. Download. 2. Choose AI Provider. 3. Use Hotkeys." | `README.md:22-39`, `website/index.html:245-280` | VERIFIED-AUTOMATED |
| **C-04** | Hotkey `Alt + /` | "Alt + / : Instant cursor question solve" | `README.md:35`, `ghostline/app.py:1680`, `website/index.html:147` | VERIFIED-AUTOMATED |
| **C-05** | Hotkey `Alt + Shift + /` | "Alt + Shift + / : Full-screen solve" | `README.md:36`, `ghostline/app.py:1710` | VERIFIED-AUTOMATED |
| **C-06** | Hotkey `Alt + Q` | "Alt + Q : Live Audio Meeting Copilot" | `README.md:37`, `ghostline/audio_assistant.py:45` | VERIFIED-AUTOMATED |
| **C-07** | Hotkey `Alt + Shift + X` | "Alt + Shift + X : Instantly hide or show HUD" | `README.md:38`, `ghostline/app.py:1735` | VERIFIED-AUTOMATED |
| **C-08** | Local-first privacy with Ollama | "Run 100% locally with Ollama. Screen and audio data never leave your PC." | `README.md:48`, `website/index.html:64, 314-325`, `ghostline/providers/ollama.py:1-40` | VERIFIED-AUTOMATED |
| **C-09** | BYOK Cloud Flexibility | "Connect cloud providers: OpenAI, Anthropic, Google Gemini, Groq, OpenRouter" | `README.md:32, 46-53`, `website/index.html:327-375`, `ghostline/config.py:120-180` | VERIFIED-AUTOMATED |
| **C-10** | Hardware-grade key encryption | "API keys encrypted at rest with Windows DPAPI" | `README.md:32, 49-53`, `website/index.html:68`, `ghostline/security/dpapi.py:1-60` | VERIFIED-AUTOMATED |
| **C-11** | Live Audio dual-stream attribution | "Dual-stream live transcription: separates [You] from [Call]" | `README.md:18`, `website/index.html:158-180`, `ghostline/audio_assistant.py:110-180` | VERIFIED-AUTOMATED |
| **C-12** | Personal Profile Grounding | "Ground responses in your genuine resume, projects, and skills" | `website/index.html:115-118, 185-215`, `ghostline/profile_manager.py:30-90` | VERIFIED-AUTOMATED |
| **C-13** | System Tray integration | "Unobtrusive system tray presence with quick controls and diagnostics" | `README.md:60-66`, `ghostline/ui/tray.py:1-80` | VERIFIED-AUTOMATED |
| **C-14** | Verified Packaging | "Available as Windows Installer (`Ghostline-Setup.exe`) and Portable Zip" | `README.md:26-27, 98-103`, `build_release.py:280-310` | VERIFIED-AUTOMATED |
| **C-15** | Mandatory Ethical Notice | "Follow the rules of your school, employer or interviewer." | `README.md:122-125`, `website/index.html:76-81` | VERIFIED-AUTOMATED |

---

## Prohibited Claims (Omitted by Policy)

1. *No latency numbers*: Claims like "<50ms" or "zero latency" are omitted.
2. *No unqualified 100% offline*: Stated strictly as "100% offline when using Ollama".
3. *No stealth or evasion features*: Screen-share capture exclusion, taskbar hiding, and keyboard flashing are strictly excluded.
4. *No fake social proof*: Zero fabricated testimonials, awards, or user numbers.
