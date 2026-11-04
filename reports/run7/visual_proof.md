# Ghostline Run 7 — Visual Verification Proof

**Platform:** Native Windows 11 DWM (`windows` Qt platform plugin)  
**Display Scale:** 125% DPI Scale (DPR = 1.25)  
**Resolution:** 1600x900 client pixels (1280x720 logical)  
**Status:** **VERIFIED-VISUAL**

---

## 1. Visual Proof per Screen

### Screen 1: Dashboard (`ui_shots/run7/scale_125pct/main_dashboard_1280x720.png`)
- **Dimensions:** 1600x900 px (1280x720 logical)
- **Specific Visual Evidence:**
  1. **Fluent 2 Dark Canvas & Navigation:** Dark background surface (`#202020` / mean RGB 68.6) with the left-hand navigation sidebar showing icons for Home, Modes, AI Providers, Audio & Calls, Personal Profile, History, Settings, Diagnostics, and Help.
  2. **Hero Header & Status Pill:** Top hero displays title "Ghostline" with a green status indicator pill showing "Ready (Alt + /)" and subtitle "On-device question recognition and live call assistant".
  3. **Feature Action Cards:** Three rounded action cards rendered with `#292929` card surface, 1px `#383838` stroke, displaying "Cursor Screen Solve (Alt + /)", "Live Audio & Calls (Alt + \\)", and "Session History (Alt + Shift + A)".

### Screen 2: My Profile (`ui_shots/run7/scale_125pct/main_profile_1280x720.png`)
- **Dimensions:** 1600x900 px (1280x720 logical)
- **Specific Visual Evidence:**
  1. **High-Contrast Input Boundaries (F3 Proof):** Input text boxes have high contrast against the `#292929` card background with darker surface `#202020` and distinct 1px border `#858585` (measured contrast ratio 3.94:1, exceeding the 3:1 WCAG requirement).
  2. **Standard Heights & Visible QLabel Titles:** Single-line fields (Full Name, Current Role, Target Company) render at 34px height; multi-line text areas (Technical Skills, Resume / Bio Summary) render at $\ge 96$px height with clear `<QLabel>` field titles.
  3. **Save Button & Dirty Indicator:** Prominent primary blue accent Save button (`#0078d4`) in the action footer with an unsaved changes indicator dot.

### Screen 3: Settings — General (`ui_shots/run7/scale_125pct/main_general_1280x720.png`)
- **Dimensions:** 1600x900 px (1280x720 logical)
- **Specific Visual Evidence:**
  1. **System Tray Options Card (F4 Proof):** Dedicated Fluent card titled "System Tray & Notifications" containing checkboxes for "Show icon in system notification tray" (`chk_show_tray_icon`), "Minimize window to system tray" (`chk_minimize_to_tray`), and "Close window minimizes to tray instead of exiting" (`chk_close_to_tray`).
  2. **Hotkey Configuration Section:** Visual shortcut keybind boxes showing `Alt + /` for scan solve, `Alt + \` for audio toggle, and `Alt + Q` for quick ask.
  3. **Window Behavior Toggles:** Checkboxes for "Start Ghostline minimized to system tray" and "Always on top when active".

### Screen 4: Audio & Calls Settings (`ui_shots/run7/scale_125pct/main_audio_1280x720.png`)
- **Dimensions:** 1600x900 px (1280x720 logical)
- **Specific Visual Evidence:**
  1. **Device Selection Dropdowns:** Distinct dropdown combo boxes for Microphone Device (`cmb_mic_device`) and System / Meeting Loopback Device (`cmb_system_device`).
  2. **Live VU Meter & Volume Sliders:** Interactive level meters for Mic and System audio alongside volume sliders.
  3. **Hardware Test Button (F4 Proof):** A dedicated "Test Audio Hardware" action button (`btn_test_audio_hw`) that runs real device enumeration and signal probe.

### Screen 5: Setup Wizard Dialog (`ui_shots/run7/scale_125pct/dialog_wizard_640x520.png`)
- **Dimensions:** 775x785 px (620x628 logical)
- **Specific Visual Evidence:**
  1. **Centered Fluent Modal Frame:** Dark acrylic-style card with soft rounded corners and subtle drop shadow.
  2. **Progress Step Indicator:** Step indicator showing Step 1: Provider Setup (Ollama / Local model selection), Step 2: Audio & Screen permissions.
  3. **Action Navigation:** Clear "Next" and "Skip" action buttons styled with standard Fluent tokens.

