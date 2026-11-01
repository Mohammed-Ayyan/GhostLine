# UI Slice 0 Report — Inventory and Pipeline Proof

**Execution Date:** 2026-11-01 22:26:00 +05:30  
**Target Branch:** `feature/hardware-controls-and-release`  
**Git HEAD Commit:** `181a62d`  
**Installed Target Binary:** `%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe` (Commit: `929331a`)  

---

## 1. System & Architecture Detection (`VERIFIED-AUTOMATED`)

- **Qt Binding & Version**: `PyQt6` version `6.11.0` (Underlying Qt `6.11.2`, Platform: Windows 11 64-bit DirectWrite/GDI).
- **Main Window Class**: `QtGhostlineMainWindow` located at [ghostline/ui/qt_main_window.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/ui/qt_main_window.py).
  - Window flags: `Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint`.
  - Configured minimum size: `880x640` (discovered minimum supported size).
  - Navigation: `QStackedWidget` containing 8 distinct view builders:
    1. `_build_dashboard_view` (`dashboard`)
    2. `_build_general_view` (`general`)
    3. `_build_model_view` (`model`)
    4. `_build_audio_view` (`audio`)
    5. `_build_mode_view` (`mode`)
    6. `_build_history_view` (`history`)
    7. `_build_security_view` (`security`)
    8. `_build_diagnostics_view` (`diagnostics`)
- **HUD Overlay Window**: `QtGhostlineHudOverlay` located at [ghostline/ui/qt_hud_overlay.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/ui/qt_hud_overlay.py) (includes `ConversationCardWidget`).
  - Window styles: Frameless, focus-free (`WS_EX_NOACTIVATE`), capture exclusion (`WDA_EXCLUDEFROMCAPTURE`), topmost.
- **Audio & History Panels**:
  - `QtLiveAudioPanel` at [ghostline/ui/qt_audio_panel.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/ui/qt_audio_panel.py).
  - `QtHistoryHudOverlay` at [ghostline/ui/qt_history_panel.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/ui/qt_history_panel.py).
- **System Tray**: `TrayIndicator` at [ghostline/ui/tray_indicator.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/ui/tray_indicator.py).
- **Dialogs & Messages**:
  - `QtShortcutDialog` (dialog for setting custom global key combinations).
  - `QMessageBox` (informational, warning, and confirmation alerts).
  - First-run experience: Config flag `first_run_complete: bool` with non-intrusive Windows system tray balloon notification.

---

## 2. Style Inventory (`VERIFIED-AUTOMATED`)

Audit artifact: [reports/style_inventory.json](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/reports/style_inventory.json).

- **Global Stylesheet**: 2 locations:
  1. `ghostline/app.py:364`: `self.qapp.setStyleSheet(QT_MAIN_STYLESHEET)`.
  2. `ghostline/ui/qt_main_window.py:299`: `self.btn_exit_app.setStyleSheet(...)` (inline override on creation).
- **Per-Widget `setStyleSheet` Calls**: **227 total calls** overriding global styles:
  - `ghostline/ui/qt_main_window.py`: 99 calls
  - `ghostline/ui/qt_hud_overlay.py`: 70 calls
  - `ghostline/ui/qt_audio_panel.py`: 37 calls
  - `ghostline/ui/qt_history_panel.py`: 21 calls
- **External `.qss` Files**: **0** (all styles are embedded Python string templates in `qt_theme.py` and widget files).
- **QPalette Usage**: **0** occurrences.
- **Hardcoded Hex Colors**: **107 distinct hex values** across 388 code lines.
  - Most frequent: `#FFFFFF` (86), `#94A3B8` (29), `#161822` (25), `#38BDF8` (24), `#EF4444` (22), `#10B981` (19), `#1A1D27` (19), `#1E293B` (16).
- **Font Sizes**: 10 distinct values (`12px` 60, `11px` 54, `13px` 30, `10px` 9, `16px` 4, `14px` 4, `22px` 2, `17px` 2, `20px` 1, `15px` 1).
- **Size Constraint Calls**: `setFixedWidth`: 4, `setFixedSize`: 14, `setMinimumWidth`: 0, `setMaximumWidth`: 0.
- **Emoji Characters in UI Strings**: **246 occurrences** across **63 distinct symbols**:
  - `👻` (Ghostline brand logo), `🖥️` (Screen / Desktop), `🎙️` (Microphone / Audio), `⚡` (Dashboard / Connection), `⚙️` (General / Settings), `🧠` (Model), `📜` (History), `🛡️` (Security), `🩺` (Diagnostics), `🚪` (Exit), `⭐` (Star answer).
- **Theme Loading**: `ghostline/app.py` loads `QT_MAIN_STYLESHEET` from `ghostline/ui/qt_theme.py`. In the frozen PyInstaller build (`Ghostline.spec`), `ghostline.ui` is packaged as pure Python bytecode.

---

## 3. Render Harness & Layout Audit Tool (`VERIFIED-AUTOMATED`)

- **Harness Module**: [ghostline/ui/render_harness.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/ui/render_harness.py).
- **CLI Entry Point**: [tools/render_ui.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/tools/render_ui.py).
- **Hidden CLI Flag**: `Ghostline.exe --render-ui <outdir>` integrated into [ghostline/app.py](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ghostline/app.py#L2731).
- **Safety Profile**: Uses `tempfile.TemporaryDirectory()`; loads sample configuration without accessing real user credentials or `%APPDATA%\Ghostline\config.json`.
- **System Fonts for Offscreen QPA**: Discovered that Qt's `qoffscreen` platform plugin does not automatically enumerate Windows system fonts. Added `load_system_fonts_for_offscreen()` loading `segoeui.ttf`, `segoeuib.ttf`, `segoeuisb.ttf`, `seguiemj.ttf`, `consola.ttf` via `QFontDatabase.addApplicationFont`.
- **Render Matrix Executed**:
  - Scales: 100% (`1.0`), 125% (`1.25`), 150% (`1.5`), 200% (`2.0`).
  - Window Sizes: `900x640` (minimum supported), `1100x720`, `1400x900`.
  - Pages: `dashboard`, `general`, `model`, `audio`, `mode`, `history`, `security`, `diagnostics`.
  - HUD States: `idle`, `answer`, `error`, `hardware drawer open`.
  - Dialogs: `QtShortcutDialog`, `QMessageBox`.
  - Menus: `QMenu` (System tray menu).
  - Total Images Rendered: **124 PNG files** in `ui_shots/before/`.

---

## 4. Root Cause Analysis of Layout & Clipping Bugs

Audit artifact: [reports/ui_layout_audit_before.json](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/reports/ui_layout_audit_before.json).  
Total layout issues detected before restyling: **764 issues** across the 4 scales.

### Identified Root Causes:
1. **Sidebar Fixed Width & Margin Overlap**:
   - `sidebar.setFixedWidth(220)` with `sidebar_layout.setContentsMargins(16, 24, 16, 20)` leaves only **188px** of horizontal content area.
   - `SidebarExitBtn` (`🚪  Exit Ghostline`): Font advance is **221px**, overflowing by 33px.
   - Status Box `Engine Ready`: Advance is **144px** inside a 104px container, overflowing by 40px.
   - Version label `Ghostline v1.0.2 [DEV]...`: Advance is **627px** without word wrapping, overflowing by 439px.
2. **Missing ScrollArea Horizontal Policy on Model Page**:
   - In `_build_model_view`, `scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)` was omitted.
   - `btn_test_conn.setFixedWidth(160)` and unconstrained model combo-box row force minimum content width to exceed viewport width, causing a persistent horizontal scrollbar across the entire page.
3. **Card Row Action Buttons Forced Offscreen**:
   - In `_build_dashboard_view` and `_build_general_view`, cards use `QHBoxLayout` placing wide action buttons (`Run Screen Solve (Alt + /)`, `Start Listening...`, `Configure Local AI Models ->`) at the right edge without minimum layout constraints. When the window width is $\le 1100$px, the buttons are pushed past the right margin and clipped.
4. **HUD Toolbar Button Collisions**:
   - In `qt_hud_overlay.py`, the top island toolbar contains 13 buttons in a fixed-height layout with `setContentsMargins(12, 8, 12, 8)`. When rendered at standard width (680px), button labels overlap and clip (`swer`, `nshot`, `Paus`).
   - The secondary status bar has two labels (`lbl_source_badge` and `lbl_model_status`) that overlap directly over each other, rendering garbled text (`Ghoiisteiie`).

---

## 5. Behavior-Freeze Widget Inventory Baseline (`VERIFIED-AUTOMATED`)

- Artifact: [ui_inventory_before.json](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/ui_inventory_before.json).
- Total Widgets Captured: **672 widgets**.
- Fields Recorded: `page`, `class`, `objectName`, `text`, `tooltip`, `enabled`, `visible`, `parent_chain`.
- No widget will be deleted or renamed during subsequent slices.

---

## 6. Pipeline Probe & Theme Override Analysis (`VERIFIED-AUTOMATED`)

- **Probe Configuration**: Temporarily set `C_CYAN = "#ff00ff"` and `C_BORDER_ACCENT = "#ff00ff"` in `ghostline/ui/qt_theme.py`.
- **Probe Execution**: Rendered all pages with the magenta accent and measured pixel colors.
- **Findings**:
  - Found **7 images with 5,965 cyan pixels that remained `#38bdf8`** despite the theme token change.
  - Worst offenders:
    - `hud_answer_680x580_100pct.png`: **3,637 cyan pixels remained** (badge chip styling, button borders, keyword chips).
    - `hud_error_680x580_100pct.png`: **613 cyan pixels remained**.
    - `hud_hardware_680x580_100pct.png`: **589 cyan pixels remained**.
    - `main_general_1100x720_100pct.png`: **168 cyan pixels remained**.
  - **Conclusion**: Local widget `setStyleSheet` calls and hardcoded painter brush colors in `qt_hud_overlay.py` and `qt_main_window.py` override the application stylesheet. These must be systematically migrated to token-driven global QSS selectors in Slice 1.
- **Probe Reverted**: `ghostline/ui/qt_theme.py` restored to original tokens.
- **Installed Build vs Git HEAD Mismatch**:
  - Installed binary stamp: Commit `929331a` (built prior to Slice 0).
  - Git HEAD: Commit `181a62d`.
  - Mismatch will be reconciled in Slice 6 when the binary is rebuilt.

---

## 7. Baseline Test Suite Results (`VERIFIED-AUTOMATED`)

Test log: [reports/ui_baseline_test_run.txt](file:///c:/Users/sumiy/OneDrive/Desktop/web%20development/Rubric%20Reverse%20Engineer/reports/ui_baseline_test_run.txt).

```
pytest tests/
402 passed, 14 skipped, 0 failed, 1 warning in 209.03s
```
- **Passed**: 402
- **Skipped**: 14 (hardware audio / CUDA device dependent tests)
- **Failed**: 0
- **Headless Self-Test (`--self-test`)**: All 5 checks passed (`providers_import`, `settings_load`, `dpapi_roundtrip`, `qt_platform_plugin`, `hardware_detection`).

---

## 8. Visual Audit of "Before" Images (`VERIFIED-VISUAL`)

Inspected actual rendered PNG images in `ui_shots/before/100pct/`:

1. **`main_dashboard_1100x720_100pct.png`**:
   - *Observation A*: Card action buttons (`Run Screen Solve (Alt + /)`, `Start Listening...`, `Copy Answer`) are pushed past the right viewport boundary and visibly clipped at the edge.
   - *Observation B*: Left sidebar uses emojis (`⚙`, `🖥`, `⚡`, `🎙`, `🧠`, `📜`, `🛡`, `🩺`, `🚪`) for every navigation item, and `Engine Ready` is enclosed in a nested double-bordered box.
   - *Observation C*: Exit button at the bottom is a loud red outline block (`🚪 Exit Ghostline`) with an emoji and letter-spaced text.
2. **`main_model_1100x720_100pct.png`**:
   - *Observation A*: A prominent white horizontal scrollbar runs across the bottom of the entire view.
   - *Observation B*: In "Model Selection", the `🔄 Fetch Models` button is completely pushed off the right edge and hidden.
   - *Observation C*: Subtitle text `...high-speed cloud intelli...` is truncated at the right margin.
3. **`main_general_1100x720_100pct.png`**:
   - *Observation A*: Uses marketing claims ("Searches left", "100% on-device inference via local Ollama. Zero rate limits, zero subscriptions.") that are inaccurate now that BYOK cloud models are supported.
   - *Observation B*: In "Application icon", the combobox text `Default Ghostl...` is truncated, and in "Custom Shortcut" the shortcut configuration button is completely clipped offscreen.
   - *Observation C*: Section headings (`USAGE`, `SHORTCUT`, `APP VISIBILITY`) use letter-spaced all-caps rather than Fluent 2 sentence case typography.
4. **`hud_answer_680x580_100pct.png`**:
   - *Observation A*: Island toolbar buttons at the top are severely clipped and truncated (`swer`, `nshot`, `Paus`).
   - *Observation B*: The secondary status bar has two labels (`Ghostline` and `Offline AI MCQ Ready`) that overlap directly on top of each other, creating garbled text (`Ghoiisteiie`).
   - *Observation C*: Card answer uses an outdated "AI look" with a star emoji `⭐` before the answer, desktop emoji `🖥` before the question, and an oversized cyan `[Screen MCQ]` badge.
5. **`tray_menu_100pct.png`**:
   - *Observation A*: Completely unthemed default Windows white background (`#FFFFFF`) with sharp rectangular corners and zero padding.
   - *Observation B*: Black monospace text (`Consolas`) with no dark mode integration or Fluent hover states.
   - *Observation C*: Separator is a stark gray hairline with no elevation or modern menu styling.
6. **`dialog_shortcut_460x240_100pct.png`**:
   - *Observation A*: Monospace font throughout the dialog without Fluent body or caption typography.
   - *Observation B*: "Cancel" button has a dark navy box background (`#242a38`), while "Save Shortcut" is an intense solid cyan button (`#38bdf8`), creating unbalanced visual weight.
   - *Observation C*: Input box lacks Fluent bottom-accent focus indicator and elevation styling.

---

## 9. Slice 0 Gate Conclusion

- [x] All 8 requirements of Slice 0 completed.
- [x] Render harness built and operational (`tools/render_ui.py` & `--render-ui`).
- [x] All 124 baseline images rendered and saved to `ui_shots/before/`.
- [x] Widget inventory baseline saved to `ui_inventory_before.json` (672 widgets).
- [x] Full automated test suite passes (402 passed, 0 failed).
- [x] Pipeline probe completed; hardcoded overriding styles identified and cataloged.
- [x] Gate passed: Ready to proceed to **Slice 1 (Theme Infrastructure)**.
