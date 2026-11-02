# Ghostline Launch Video — Decisions Log (Autonomous Mode)

**Date**: 2026-11-02  
**Context**: Autonomous video production (Run 4) without interactive user queries.  
**Principle**: Pick safest default grounded in repo evidence; document here.

| Decision ID | Context | Selected Option | Rationale |
| :--- | :--- | :--- | :--- |
| **DEC-001** | Music & Licensing | Silent AAC track / verified CC0 asset only | Zero risk of copyright claims or monetization strikes on YouTube/Instagram. |
| **DEC-002** | Voiceover | Caption-first visual typography (no synthetic voiceover) | Avoids robotic TTS or unverified online voice synthesis APIs. Maximizes mobile viewer engagement where 80%+ watch muted. |
| **DEC-003** | Sensitive Features Omission | Strictly exclude capture exclusion, taskbar hiding, stealth mode, and keyboard flashing | Aligns with ethical use rules, platform policies, and prompt constraints. |
| **DEC-004** | Output Location | `../ghostline_launch_video/` outside the repo | Keeps Git history free from massive binary video/asset files. |
