# Ghostline — Run 15 Decisions

| Date | Topic | Decision | Rationale |
| :--- | :--- | :--- | :--- |
| 2026-11-08 | Execution Order | Execute Part B first, then Part A | User priority: quick, low-risk video music removal for website publishing, followed by live HUD and transcript fixes. |
| 2026-11-08 | Video Audio Replacement | Replace audio with silent AAC track without re-encoding video stream (`-c:v copy`) | Preserves bit-exact visual quality, eliminates all music and SFX, keeps same durations and container structure. |
| 2026-11-08 | Default Spoken Language | English (`en`) as default spoken language with optional `Auto-detect` | Prevents foreign language hallucinations on noise/silence; English is the primary target language for users. |
| 2026-11-08 | HUD Geometry Clamp | Clamp to 90% of screen work area, max 720x900 logical px | Ensures HUD fits within viewport across multi-monitor setups and display scalings without off-screen bleed. |
| 2026-11-08 | Test Profile Usage | Use temporary isolated test directory for profile and audio tests | Adheres to strict safety rule: never touch or corrupt user's actual profile or AppData. |
