# Ghostline — Run 11 Architectural & Operational Decisions

## Context & Ground Rules
- Mode: Unattended execution, safest defaults selected automatically, recorded here.
- Strict Scope: Video pipeline only (`tools/`, `../ghostline_launch_video/`, `website/media/*`). Zero modifications to application code, website HTML/JS/CSS, configs, installer, or releases.
- Strict Safety: No `reset --hard/clean/checkout --/stash drop`. No secrets printed or committed. No history rewriting, no force-push.

## Decisions Log
- *2026-11-08 (Preflight)*:
  - Safety checkpoint branch created: `backup/pre-run11-20261108_122359`.
  - Full git bundle created: `../ghostline_backups/pre_run11_20261108_122359.bundle`.
  - Scope documented in `reports/run11/scope.md`.
  - Unstaged line-ending / BOM differences on website HTML files left untouched and strictly unstaged.
- *2026-11-08 (Root Cause & Inoculation)*:
  - Verified root cause: `QT_QPA_PLATFORM="offscreen"` in PyQt6 does not initialize Windows GDI/DirectWrite font enumeration; `QFontDatabase.families()` returned an empty list.
  - Inoculation: Bundled open-license fonts (Inter, JetBrains Mono) directly in `tools/video/fonts/` and registered via `QFontDatabase.addApplicationFont()`.
  - Pre-render FontGuard and post-render OutputGuard (1 fps OCR + tofu detection regex) built to fail fast on any tofu.
- *2026-11-08 (Poster Compression Architecture)*:
  - Posters capped strictly at $\le 60.0$ KB using adaptive progressive JPEG compression loop (`-q:v 8..31`, fallback scale `1600:-1`). All 9 posters range between 31 KB and 55 KB.
- *2026-11-08 (Total Media Budget <= 90.0 MB)*:
  - Re-encoded high-efficiency H.264 streams across all 9 videos to achieve a total folder size of 80.96 MB, well below the 90.0 MB ceiling, while maintaining crisp legibility and 0 tofu.
- *2026-11-08 (Shipping Strategy)*:
  - Tiers shipped strictly in order: Tier 1 (H1 + H2), Tier 2 (V1 + V2), Tier 3 (S1–S5).
  - Web contract preserved: exact filenames, durations ($\pm 0.5$s), aspect ratios, and VTT cues matched.


