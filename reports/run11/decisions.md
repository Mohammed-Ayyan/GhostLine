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

