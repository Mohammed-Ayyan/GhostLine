# Ghostline — Run 11 Scope Definition

**Execution Date:** 2026-11-08  
**Objective:** Fix text rendering defect (missing-glyph boxes / tofu) across all Ghostline videos and posters.

---

## 1. Allowed Paths to Create / Modify / Delete
The following paths constitute the video pipeline sources, rendering infrastructure, master storage, and shipped media:

1. **Video Pipeline Sources (`tools/`):**
   - `tools/build_run11_videos.py` (New robust rendering pipeline)
   - `tools/build_run10_videos.py` (Legacy Run 10 pipeline)
   - `tools/generate_synth_audio.py` (Sound synthesis script)
   - `tools/capture_video_assets.py` (App UI capture script for video)
   - `tools/audit_run10_videos.py` & `tools/audit_run11_videos.py` (Video validation suite)
   - `tools/forensic_video_test.py` (Video forensics test script)
   - `tools/video/` (Bundled font files, font guards, output guards)
   - `video_engine/*` (HTML/CSS video templates and layouts)

2. **External Working Storage (`../ghostline_launch_video/`):**
   - `../ghostline_launch_video/run11/` (Run 11 video masters, high-res captures, audio stems, contact sheets)
   - `../ghostline_launch_video/run10/` (Run 10 masters and archives)

3. **Shipped Media Files (`website/media/*`):**
   - `website/media/*.mp4` (Videos: H1, H2, V1, V2, S1–S5)
   - `website/media/*.jpg` (Video poster frames $\le 60$ KB)
   - `website/media/*.vtt` (WebVTT subtitle tracks)
   - `website/media/*.txt` (Plain text transcripts)

4. **Run 11 Documentation & Reports (`reports/run11/`):**
   - `reports/run11/scope.md`
   - `reports/run11/decisions.md`
   - `reports/run11/progress.md`
   - `reports/run11/root_cause.md`
   - `reports/run11/needs_other_changes.md`
   - `reports/run11/other_assets_check.md`
   - `RELEASE_REPORT_RUN11.md` (Repo root)

---

## 2. Forbidden Paths (Strict Hands-Off)
No changes will be made to:
- Application source code (`ghostline/*`)
- Non-video tests (`tests/*`)
- Website code (`website/*.html`, `website/*.css`, `website/*.js`, `website/site-config.js`, `website/vercel.json`)
- Project root configurations (`README.md`, `requirements.txt`, `Ghostline.spec`, `installer.iss`, `version_info.txt`, `build_release.py`)
- Ollama data or models (`%LOCALAPPDATA%\Programs\Ollama`, `%USERPROFILE%\.ollama`)
- User credentials and data profiles
- GitHub releases or remote tags

If any issue appears to require changing a forbidden path, it will be strictly recorded in `reports/run11/needs_other_changes.md` without modifying the forbidden file.

