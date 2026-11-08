# Ghostline — Run 17 Out of Scope Log

The following areas are strictly OUT OF SCOPE for Run 17 and must NOT be modified:
1. **Website & Web Pages** (`website/**`): Run 16 support page and CTAs are shipped and complete.
2. **Video Pipeline & Shipped Media** (`tools/video/**`, `website/media/**`).
3. **Hotkeys & Shortcuts**: Global hotkeys (Alt+/, Alt+A, etc.) remain untouched; HUD must NEVER auto-show on Alt+/.
4. **HUD Behaviour & Window Flags**: Floating HUD overlay, non-focus-stealing properties, and cloaking remain unchanged.
5. **AI Providers & Inference Engine**: Ollama, OpenAI, Gemini, Groq clients.
6. **Audio Copilot & Hardware**: Loopback audio, microphone, Faster-Whisper, LED indicators.
7. **Tray Menu**: System tray menu logic and context options remain untouched.
8. **Native Installer Logic**: Inno Setup script `installer/ghostline.iss`.
9. **README.md & SECURITY.md**: Shipped documentation.
