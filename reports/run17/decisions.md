# Ghostline — Run 17 Decisions Log

| Date | Topic | Decision | Rationale |
| :--- | :--- | :--- | :--- |
| 2026-11-08 | Scope & Boundaries | Confined strictly to app UI (`ghostline/ui/`), assets, tests, version bump, spec, packaging | Strictly preserves website, video pipeline, hotkeys, HUD behavior, audio copilot, tray, and installer logic. |
| 2026-11-08 | Privacy Mandate | Raw UPI ID and payee name exist ONLY inside QR pixels; masked as `mo***@***` in reports | Adheres to strict privacy rules: no raw payment details anywhere in text, tooltips, alt text, or accessibility names. |
| 2026-11-08 | Zero Network Calls | App makes 0 network requests for support features; buttons open OS default browser on click via `QDesktopServices.openUrl` | Guarantees zero tracking, no telemetry, and zero unauthenticated GitHub rate-limiting in app. |
| 2026-11-08 | Zero Nagging | No popups, no banners, no timers, no counters, no reminders, no "rate us" | Support must remain completely inert and purely optional. |
| 2026-11-08 | QR Asset Location | Stored under `assets/support/` alongside `assets/icons/` | Consistent with application asset structure and bundled into both development root and PyInstaller `_internal/assets/support`. |
| 2026-11-08 | Vector QR Rendering | Render SVG via `QSvgRenderer` directly onto high-DPI `QPixmap` with logical-to-physical devicePixelRatio scaling | Guarantees razor-sharp vector QR rendering on 100%, 125%, 150%, and 200% displays with smooth PNG fallback. |
| 2026-11-08 | Solid White QR Tile | Pinned `#FFFFFF` background with 12px corner radius and dark-on-light pixels | Ensures QR scanners can read the code instantly in dark mode without inverted colors. |
| 2026-11-08 | Non-blocking Modal Capture | Used `dlg.adjustSize()` and `dlg.grab()` for headless capture script | Prevents Windows modal event loop re-entrancy from hanging headless automated captures. |
| 2026-11-08 | Version Bump | Bumped from 1.0.5 to 1.0.6 across build_info, setup, and changelog | Correct semantic versioning for new in-app support feature release. |
