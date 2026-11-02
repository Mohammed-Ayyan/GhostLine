# Ghostline — Information Architecture (IA) Plan & Control Mapping

**Date:** 2026-11-02  
**Target:** 6-Item Modern Navigation Structure  
**Design Standard:** Microsoft Fluent 2 (Dark), Grade 8 Plain Language

---

## 1. Structural Navigation Overview

To reduce cognitive load from 8 fragmented views down to an intuitive desktop application workflow, Ghostline consolidates into at most **6 primary navigation items**:

| # | Nav Item | Screen ID | Core Function |
| :-: | :--- | :--- | :--- |
| 1 | **Home** | `dashboard` / `home` | Glanceable status line, prominent keycap actions (Scan question, Meeting transcription), and latest answer card. |
| 2 | **My Profile** | `profile` | Personal resume, background facts, and strict answer grounding preferences (Part C). |
| 3 | **AI** | `model` / `ai` | Local Ollama vs Cloud BYOK provider setup, API keys, model picker, and connection health. |
| 4 | **History** | `history` | Searchable past questions, OCR extracts, and AI answers with copy and export. |
| 5 | **Settings** | `settings` / `general` / `mode` | Solution delivery modes (Tray, HUD, LED, Clipboard), quiet channels, taskbar/startup preferences. |
| 6 | **Help** | `help` / `about` / `security` / `diagnostics` | Hotkey cheat sheet, first-run setup wizard re-opener, privacy overview, and system diagnostics. |

---

## 2. Complete Control Mapping Table

Every existing widget and objectName is preserved in the Qt widget hierarchy to ensure 100% test compatibility.

| Original Page | Widget / Control `objectName` | Legacy Role | New Location in Consolidated IA | Tier (Basic / Advanced) |
| :--- | :--- | :--- | :--- | :--- |
| **Dashboard** | `btn_solve` | Trigger solve | **Home** > Primary Action Card | Basic |
| **Dashboard** | `hud_btn` | Toggle floating HUD | **Home** > Header Actions | Basic |
| **Dashboard** | `card_recent` | Solved answer display | **Home** > Latest Answer Card | Basic |
| **Dashboard** | `lbl_ans` | Answer text label | **Home** > Latest Answer Card | Basic |
| **General** | `btn_hotkey_chip` | Custom hotkey dialog | **Settings** > Shortcut row | Basic |
| **General** | `switch_hide_taskbar` | Hide from taskbar | **Settings** > Tray & Startup row | Basic |
| **General** | `switch_hud` | Show HUD on solve | **Settings** > HUD Behavior row | Basic |
| **General** | `switch_autocopy` | Auto-copy answer | **Settings** > Automation row | Basic |
| **Mode** | `combo_mode` | Indicator selector | **Settings** > Display Mode card | Basic |
| **Mode** | `preview_lbl` | Mode preview text | **Settings** > Display Mode card | Basic |
| **Mode** | `switch_quiet_taskbar_flash` | Taskbar flash toggle | **Settings** > Quiet Channels | Advanced |
| **Mode** | `switch_quiet_taskbar_badge` | Taskbar badge toggle | **Settings** > Quiet Channels | Advanced |
| **Mode** | `switch_quiet_tray_notification` | Tray balloon toggle | **Settings** > Quiet Channels | Advanced |
| **Mode** | `switch_quiet_hardware_signal` | Hardware signal pulse | **Settings** > Quiet Channels | Advanced |
| **Model** | `card_mode_local` | Local Ollama card | **AI** > Mode Selectors | Basic |
| **Model** | `card_mode_cloud` | Cloud BYOK card | **AI** > Mode Selectors | Basic |
| **Model** | `combo_provider` | AI provider selector | **AI** > Provider card | Basic |
| **Model** | `card_api_key` | Key config container | **AI** > API Key card | Basic (Cloud) |
| **Model** | `txt_api_key` | API key password line | **AI** > API Key card | Basic (Cloud) |
| **Model** | `btn_save_key` | Save encrypted key | **AI** > API Key card | Basic (Cloud) |
| **Model** | `btn_del_key` | Delete key from DPAPI | **AI** > API Key card | Basic (Cloud) |
| **Model** | `combo_model` | Model selection | **AI** > Model card | Basic |
| **Model** | `btn_fetch_models` | Query remote models | **AI** > Model card | Basic |
| **Model** | `btn_test_conn` | Connectivity test | **AI** > Connection Health | Basic |
| **Model** | `card_advanced` | Advanced options | **AI** > Advanced Options | Advanced (Collapsible) |
| **Model** | `txt_endpoint` | Endpoint Base URL | **AI** > Advanced Options | Advanced |
| **Model** | `switch_fallback` | Ollama fallback | **AI** > Advanced Options | Advanced |
| **Model** | `btn_save_settings` | Save & activate | **AI** > Bottom Save Row | Basic |
| **Audio** | `sw_mic` | Mic recording switch | **Home / Settings** > Audio Capture | Basic |
| **Audio** | `sw_sys` | System audio switch | **Home / Settings** > Audio Capture | Basic |
| **History** | `history_search` | History filter line | **History** > Top Search Bar | Basic |
| **Security** | `infobar_security_active` | Provider privacy bar | **Help** > Privacy & Data Handling | Basic |
| **Diagnostics** | `btn_run_tests` | Run offscreen checks | **Help** > Diagnostics & Health | Advanced |

---

## 3. Backward Compatibility & Routing Guarantees

In `QtGhostlineMainWindow`:
1. Nav sidebar renders 6 items: `Home`, `My Profile`, `AI`, `History`, `Settings`, `Help`.
2. `self.screen_frames` dictionary maps:
   - `"home"`, `"dashboard"`, `"main"`, `"answer"` -> Home View.
   - `"profile"` -> Profile View (Part C).
   - `"model"`, `"ai"`, `"setup"` -> AI View.
   - `"history"` -> History View.
   - `"settings"`, `"general"`, `"mode"` -> Settings View.
   - `"help"`, `"about"`, `"security"`, `"diagnostics"` -> Help View.
3. Any test or external caller calling `show_screen("general")`, `show_screen("mode")`, `show_screen("security")`, or `show_screen("diagnostics")` will navigate cleanly without an exception or blank frame.

