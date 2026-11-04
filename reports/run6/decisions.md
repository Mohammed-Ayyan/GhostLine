# Ghostline Run 6 — Decisions Log (Autonomous Mode)

**Date**: 2026-11-02  
**Context**: Autonomous UI Defect Remediation, Quality Linting, and Release Packaging (Run 6).  
**Operating Principle**: Evidence first; real-window capture proof required; no interactive user queries; document all decisions here.

| Decision ID | Context / Area | Selected Option | Rationale |
| :--- | :--- | :--- | :--- |
| **DEC-001** | Branch Strategy | Branch `feature/run6-real-ui-fix` from `feature/hardware-controls-and-release` | Carries all previous work and preserves safety for clean PR creation. |
| **DEC-002** | Real-Window Capture | `screen.grabWindow(int(window.winId()))` via Windows native Qt platform plugin | Directly extracts the native DWM/HWND client surface without capturing background desktop or taskbar pixels. |
| **DEC-003** | Brand Asset System | Source SVG at `assets/brand/ghostline.svg`, compiled into multi-res `.ico` (16 to 256px) and PNGs | Eliminates the legacy "R" icon and cyan square mismatch with an official, clean geometric ghost mark on `#0F6CBD` rounded square. |
| **DEC-004** | Profile Isolation | Disposable temp profile via `--capture-pages` | Prevents test artifacts from contaminating production user AppData or leaking sensitive state. |
| **DEC-005** | Qt Style Enforcement | Force `Fusion` style + dark palette programmatically at `QApplication` initialization | Eliminates fallback to unthemed Windows host styles, ensuring 100% theme consistency across dev and frozen builds. |
