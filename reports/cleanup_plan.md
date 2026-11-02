# Ghostline — Repository Cleanup Plan (Run 3)

**Date**: 2026-11-02  
**Branch**: `feature/hardware-controls-and-release`  
**Execution Context**: Run 3 of 3 (Repo Hygiene, Interactive Website, Release Rebuild, Fresh Install, Push)  
**Safety Rule**: **NEVER DELETE OUTRIGHT**. Move untracked artifacts to `../ghostline_archive/<timestamp>/`. Use `git rm --cached` for tracked build output.

---

## 1. Repository Inventory Analysis

### 1.1 Directory & Folder Sizes
| Directory / Item | Size (MB) | Git Status | Classification / Action Plan |
| :--- | :---: | :--- | :--- |
| `release_archive/` | 2,270.81 MB | Ignored | Local build archives. **Move to archive**. |
| `dist/` | 1,201.53 MB | Ignored | Local PyInstaller builds. **Move to archive**. |
| `website_download/` | 1,083.98 MB | Ignored | Old binary downloads. **Move to archive**. |
| `release_dist/` | 1,070.98 MB | Ignored | Previous release packages. **Move to archive**. |
| `build/` | 810.58 MB | Ignored | PyInstaller build artifacts. **Move to archive**. |
| `.git/` | 234.20 MB | Git Internal | Retain intact. |
| `ghostline-history-backup.bundle` | 94.06 MB | Ignored | Git history bundle backup. **Move to archive**. |
| `ghostline/` | 77.82 MB | Tracked | Main source package. (`model.bin` is 72.04 MB). |
| `ui_shots/` | 70.33 MB | Partially Tracked | 516 tracked images from Slice 0; ignored now. **Untrack via `git rm --cached`**. Retain on disk. |
| `recordings/` | 60.63 MB | Ignored | Video recording masters. **Move to archive**. |
| `.agent/` | 52.01 MB | Ignored | Audit virtual environment & rules. Retain in `.agent/`. |
| `.agents/` | 15.95 MB | Tracked | Agent instructions and skills. Retain intact. |
| `backups/` | 13.99 MB | Ignored | Local database/config backups. **Move to archive**. |
| `brag-output-2026-10-26-021000/` | 5.88 MB | Ignored | Video build output. **Move to archive**. |
| `Ghostline-Launch-Landscape.mp4` | 3.46 MB | Ignored | Video master. **Move to archive**. |
| `Ghostline-Launch-Portrait.mp4` | 2.56 MB | Ignored | Video master. **Move to archive**. |
| `tests/` | 1.97 MB | Tracked | Test suite. Retain intact. |
| `reports/` | 0.48 MB | Partially Tracked | 32 tracked historical reports; ignored now. **Untrack via `git rm --cached`**. Retain on disk. |
| `scratch/` | 0.32 MB | Ignored | Scratch scripts. Retain or archive. |
| `tools/` | 0.26 MB | Tracked | Render harness and theme builders. Retain intact. |
| `docs/` | 0.12 MB | Tracked | Documentation. Rewrite/update. |
| `installer/` | 0.09 MB | Tracked | Installer assets. Retain intact. |
| `bin/win_ocr.exe` | 0.01 MB (11 KB) | Tracked | Core native OCR engine binary. Retain intact. |

---

### 1.2 Tracked Files Over 5 MB
- `ghostline/models/tiny/model.bin`: **72.04 MB**.
  - **Status**: Tracked in commit `929331a`.
  - **Resolution**: In order to satisfy the strict pre-push rule ("no tracked file over 50 MB"), untrack from Git index using `git rm --cached ghostline/models/tiny/model.bin` while keeping the local file on disk so that `resolve_whisper_model_path()` and offline Whisper tests pass. Add `ghostline/models/tiny/model.bin` to `.gitignore`.

---

### 1.3 Tracked Build Junk & Historical Artifacts (To Untrack via `git rm --cached`)
1. `ui_shots/`: 516 tracked PNG screenshots from Slice 0. Run `git rm -r --cached ui_shots/`.
2. `reports/`: 32 tracked Markdown/JSON reports from previous development slices. Run `git rm -r --cached reports/`.
3. `ui_inventory_before.json`, `ui_inventory_after.json`, `ui_inventory_after_a.json`: Tracked UI inventory dumps (~1 MB). Keep `ui_inventory_before.json` if required by harness, untrack `after` variants.

---

### 1.4 Dead Scripts & Duplicates Analysis
1. `capture_ui_screenshots.py`: 120 lines. One-off capture script from Prompt 2. Not called by any pipeline, test, or build. **Move to archive**.
2. `verify_and_capture_screenshots.py`: 140 lines. One-off verification capture script from Prompt 4. Unused by test suite. **Move to archive**.
3. `package_release.py`: 115 lines. Precursor script to `build_release.py`. Fully superseded by `build_release.py`. **Move to archive**.
4. Root launch scripts (`run.bat`, `run.ps1`, `run_dev.bat`, `install.bat`, `setup.ps1`, `uninstall.ps1`): Verified actively used by development and user environments. **Retain**.

---

### 1.5 Leftover "Rubric" Analysis
- Scanned all tracked files. Zero functional code dependencies on "Rubric".
- All remaining occurrences are either:
  1. The local working directory path name (`C:\...\Rubric Reverse Engineer\...`).
  2. Architectural comparison documentation in `docs/ARCHITECTURE.md`.
  3. Legacy ignored directory entries in `.gitignore` (`rubric_local_app/`, `rubric_extracted/`).
  4. Historical release notes and video generation scripts.

---

## 2. Execution Steps

1. **Create External Archive**:
   - Create destination: `../ghostline_archive/<timestamp>/`.
2. **Move Large Untracked Artifacts** to `../ghostline_archive/<timestamp>/`:
   - `build/`
   - `dist/`
   - `release_dist/`
   - `release_archive/`
   - `website_download/`
   - `recordings/`
   - `backups/`
   - `brag-output-2026-10-26-021000/`
   - `ghostline-history-backup.bundle`
   - `Ghostline-Launch-Landscape.mp4`
   - `Ghostline-Launch-Portrait.mp4`
   - `prompt_10.txt`
   - `capture_ui_screenshots.py`
   - `verify_and_capture_screenshots.py`
   - `package_release.py`
3. **Untrack Cached Build Junk**:
   - `git rm -r --cached ui_shots/`
   - `git rm -r --cached reports/`
   - `git rm --cached ghostline/models/tiny/model.bin`
4. **Harden `.gitignore`**:
   - Ensure comprehensive ignore rules for all build outputs, models, zips, archives, logs, AppData, and secret files.
5. **Update Core Documentation**:
   - Rewrite `README.md` (Fluent 2 dark screenshots, 3-step setup, hotkeys, provider data flows, zero hype).
   - Create `docs/ARCHITECTURE.md` (clean, accurate architectural summary).
   - Create/update `CHANGELOG.md`.
   - Maintain `SECURITY.md` and `THIRD_PARTY_NOTICES.md`.

