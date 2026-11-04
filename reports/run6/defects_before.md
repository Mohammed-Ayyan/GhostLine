# Ghostline Run 6 — Ground-Truth Defect Inventory (Before Fixes)

**Audit Target**: Ghostline Release Build v1.0.2  
**Baseline Geometry**: Window ~1916x1140 at 100% DPI scale on Windows 10/11 Desktop  
**Status**: REGISTERED FOR REPRODUCTION & LINT AUDIT  

---

## 1. Defect Registry Table

| Defect ID | Title | Summary / User Symptom | Suspected Code Location | Reproduction Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **D1** | Dark Strips behind Labels | Dark rectangles behind titles, descriptions, and text inside lighter cards. Labels paint canvas background `#181818` inside `#242424` cards. | `ghostline/ui/fluent_theme.py`, label stylesheet rules, missing `background: transparent;`. | Pixel difference between label center and card surface > 2 RGB. |
| **D2** | Clipped Page Subtitles | Subtitles clipped at top of first line (Help, Settings, Home) due to fixed heights or wrapped QLabels with insufficient vertical metrics. | `ghostline/ui/pages/` page headers, `QLabel.setWordWrap(True)`. | `QFontMetrics.boundingRect` height > widget height. |
| **D3** | Inconsistent / Narrow Column | Content column is narrow (~600px Home/Help vs ~800px Settings), leaving ~45% of 1920px width blank. Header buttons misaligned with card edges. | Layout wrappers across pages lacking unified `PageColumn` container. | Column width != `min(width - 64, 960)` or header right edge != card right edge. |
| **D4** | Ampersand Mnemonic Marker Loss | "Configure AI Models & Providers →" renders as "Models _Providers" due to unescaped `&` consumed by Qt mnemonic system. | Button text strings with single `&` in `ghostline/ui/pages/` and navigation menus. | Label/button visible text differs from source containing `" & "`. |
| **D5** | Button Icon Spacing & Semantic Mismatch | Icons touch label text (<8px spacing); differing sizes/weights; "Show Last Answer" uses AI sparkle icon; "Toggle HUD" is empty rectangle; "Copy Answer" looks broken. | `QPushButton` default icon layout, icon resource mapping in `ghostline/ui/`. | Icon-to-text gap < 8px; non-standard icon mappings. |
| **D6** | Clipped Help Hotkey Keycap | Keycap "Alt + 1 / 2 / 3 / ·" is clipped at the right. Fixed width causes overflow. Typography too heavy. | `ghostline/ui/pages/help.py`, hardcoded keycap width. | Text bounds exceed keycap geometry. |
| **D7** | Combobox Chevron & Cramped Icon Row | "Default Ghostline" dropdown lacks down chevron; "Browse..." and "Reset" look like plain flat text; icon configuration row is cramped. | Missing `QComboBox::drop-down` SVG/image url in stylesheet; layout of icon preset row. | Combobox arrow region matches field background; button lacks pushable chrome. |
| **D8** | Meaningless Blue Progress Bar | Solid blue progress bar in Settings > Inference Engine has no meaning (leftover from legacy "searches left" quota). | `ghostline/ui/pages/settings.py` (Inference Engine section). | Progress bar present without active task/quota. |
| **D9** | Seeded / Fake Recent Results | Home > Recent Results displays a hardcoded sample MCQ ("Which algorithm computes single-source shortest path...") with fake "Confidence: 99.4% • Windows OCR Verified". | `ghostline/ui/pages/home.py` static placeholder data. | Unscanned session displays non-empty result card with uncomputed confidence. |
| **D10** | Brand Asset Mismatch | Sidebar and tray show an "R"; window/taskbar and preset swatch show a cyan square. | Outdated `icon.png`, `rubric.ico` or missing multi-res `ghostline.ico`. | Window, taskbar, sidebar and tray icons not derived from unified ghostline SVG. |
| **D11** | Section Heading Left Offset | Section headings are indented ~5px to the right of page title and card edges. | Margin / padding offset in section headers (`ghostline/ui/pages/`). | `heading.x() != card.x()` (tolerance ±1px). |
| **D12** | Taskbar Button Visibility Bug | "Hide from taskbar" toggle is ON but taskbar button remains visible. | `ghostline/app.py` window flags handling (`Qt.Tool` vs `Qt.SubWindow` vs taskbar state). | Truthful explanation/fix without violating Windows window manager rules. |
| **D13** | Unverifiable Marketing Claims | Copy contains claims like "Zero artificial quotas or telemetry" without verification. | UI copy in `ghostline/ui/pages/` and help text. | Copy contains unverified superlatives. |
| **D14** | Uneven Help Hotkey Rows | Help hotkey rows have uneven heights and dark strips behind labels. | `ghostline/ui/pages/help.py` layout container. | Row heights vary or contain background strip artifacts. |
