# Ghostline — Run 17 Release Report: In-App Support & Star on GitHub

**Release Version**: Ghostline v1.0.6  
**Date**: 2026-11-08  
**Scope**: In-app "About & Support" card in Help view, sidebar footer navigation link, bundled support QR assets, Fluent System Icons, unit/UI test suite, PyInstaller spec updates, standalone release packaging, and self-test verification.

---

## 1. Discovery & Architecture

### 1.1 Single Authoritative Source for Repository URLs
To eliminate URL duplication and hardcoded strings across the codebase, repository URLs are centralized in `ghostline/build_info.py` and exported by `ghostline/__init__.py`:
- `REPO_URL = "https://github.com/Mohammed-Ayyan/GhostLine"`
- `REPO_ISSUES_URL = f"{REPO_URL}/issues"`

### 1.2 UI Placement & Navigation
- **Help View Card**: Placed directly after Card 2 (Hotkey Cheat Sheet) in `ghostline/ui/qt_main_window.py` via `_build_help_view()`.
- **Sidebar Footer Link**: Subtle `Star · Support` button with star icon added in the sidebar footer beneath the version tag. Clicking this link switches the main window to the Help view and smoothly scrolls the viewport to reveal the `supportCard`.
- **Asset Resolver**: `get_support_dir()` and `get_support_asset_path(filename)` dynamically resolve assets across both local development trees and PyInstaller frozen bundles (`sys._MEIPASS / assets / support` and `_internal / assets / support`).

### 1.3 Bundled Assets
- **Support QR Assets** (`assets/support/`):
  - `Ghostline-support-qr.svg` (crisp vector SVG rendered via `QSvgRenderer`)
  - `Ghostline-support-qr.png` (high-res dark-on-light PNG fallback)
  - `Ghostline-support-qr-original-cropped.png` (cropped original bitmap)
- **Fluent System Icons** (`assets/icons/`):
  - `ic_fluent_star_24_regular.svg` & `ic_fluent_star_24_filled.svg`
  - `ic_fluent_heart_24_regular.svg` & `ic_fluent_heart_24_filled.svg`
  - `ic_fluent_open_24_regular.svg`
  - `ic_fluent_share_24_regular.svg`

---

## 2. Privacy & Telemetry Mandate

- **QR Image Only**: Raw payee details (payee name and UPI ID) exist **ONLY** within the QR image pixels.
- **Zero Raw Text**: Zero occurrences of raw UPI ID or payee name in code, UI strings, tooltips, alt text, accessibility names, tests, fixtures, logs, or reports.
- **Masked Reporting**: All verification logs and documentation strictly use the masked format: `mo***@***`.
- **No Direct App Execution of UPI**: No `upi://` URI schemes or "Open in UPI app" buttons exist in desktop code.
- **Completely Offline & Inert**:
  - Zero network requests triggered during page load, rendering, or button interactions.
  - Zero telemetry, zero star count scraping, and zero background polling.
  - Zero nagging: No popups, no banners, no timers, no reminders, no modal interrupts.

---

## 3. Verification & Test Results

### 3.1 QR Payload Decoding Verification
- **In-Memory Decode Check**: Verified using OpenCV `cv2.QRCodeDetector` in an isolated virtual environment (`.agent/tools/qr_venv`):
  - **Status**: `MATCH`
  - **Payload Scheme**: `upi://`
  - **Masked Account ID**: `mo***@***`

### 3.2 Unit & UI Test Suite (`tests/test_support_section.py`)
11 comprehensive test cases created and passing:

| Test Case | Description | Result |
| :--- | :--- | :--- |
| `test_support_card_builds_with_qr` | Verifies full widget structure when QR assets are present | **PASSED** |
| `test_support_card_builds_without_qr` | Verifies graceful fallback to Star & links when QR assets are absent | **PASSED** |
| `test_qr_pixmap_grab_and_decodes_at_scales` | Verifies vector QR rendering and OpenCV decoding at 100%, 125%, 150%, 200% DPR | **PASSED** |
| `test_white_tile_is_dark_on_light` | Verifies solid white tile (`#FFFFFF`) with dark-on-light pixels | **PASSED** |
| `test_star_and_report_bug_open_urls` | Verifies `QDesktopServices.openUrl` opens exact authoritative repo URLs | **PASSED** |
| `test_save_qr_image_writes_valid_file` | Verifies "Save QR image" copies valid decodable image | **PASSED** |
| `test_copy_repo_link_sets_clipboard` | Verifies "Copy repo link" sets system clipboard correctly | **PASSED** |
| `test_zero_network_access` | Patches socket connect; verifies 0 external network calls | **PASSED** |
| `test_zero_privacy_leaks_in_widget_tree` | Recursively inspects widget text, tooltips, and accessibility attributes for zero leaks | **PASSED** |
| `test_support_card_is_inert_no_timers_or_popups` | Verifies card remains completely inert after 5 seconds of event pumping | **PASSED** |
| `test_sidebar_support_link_navigates` | Verifies clicking sidebar footer link switches screen to Help and scrolls to card | **PASSED** |

### 3.3 Control Inventory & Layout Lint
- `tests/test_control_inventory.py`: **PASSED** (all required `objectName` identifiers verified in Help view).
- `tests/test_ui_lint.py`: **PASSED** (zero layout overflow, zero stylesheet warnings, minimum 12px text sizes compliant).
- Full regression suite: **510 tests passed** across entire test suite.

---

## 4. Real-Window Captures & Quoted Text Proof

Captures taken directly from running native PyQt6 application windows under an isolated test profile (`reports/run17/captures/`):

1. **`reports/run17/captures/app_help_support_card.png`** (87.1 KB):
   - **Readable Words Quoted**:
     - `"Support Ghostline"`
     - `"Star on GitHub"`
     - `"Buy me a coffee (UPI)"`
     - `"Scanning shows the payee name from my bank account."`
     - `"Only pay through this app or the official GitHub repository."`
     - `"Report a bug"`
     - `"Suggest a feature"`
     - `"Copy repo link"`

2. **`reports/run17/captures/app_help_support_card_zoom.png`** (54.8 KB):
   - **Readable Words Quoted**:
     - `"Ghostline is free and open-source"`
     - `"Star on GitHub"`
     - `"Scanning shows the payee name"`
     - `"Report a bug"`

3. **`reports/run17/captures/app_sidebar_support_link.png`** (22.6 KB):
   - **Readable Words Quoted**:
     - `"Ghostline v1.0.6"`
     - `"Star · Support"`

4. **`reports/run17/captures/app_support_modal_dialog.png`** (27.7 KB):
   - **Readable Words Quoted**:
     - `"Support Ghostline (UPI QR)"`
     - `"Scan with any UPI app"`
     - `"Save QR image"`
     - `"Close"`

- **Real-Window QR Pixel Decoding**:
  - `Real-window QR capture at 100% scale`: `MATCH` (Masked ID: `mo***@***`)
  - `Real-window QR capture at 150% scale`: `MATCH` (Masked ID: `mo***@***`)

---

## 5. Standalone Release Artifacts

All binaries compiled reproducibly using PyInstaller and Inno Setup 6, verified with `--self-test` in an isolated test profile:

| Artifact | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| **`release_dist/Ghostline-Portable.zip`** | 312.16 MB | `8ea7f67cbb0c8639fe9adf4056b32f68f68f028cb32c30db71e5b9a962068ee9` |
| **`release_dist/Ghostline-Setup.exe`** | 245.57 MB | `795e6e67ac63043061c1f3ce5610eee0e2a40c9c4b301064e7b5db8adc1cd6fd` |
| **`release_dist/Ghostline-v1.0.6-win64-portable.zip`** | 312.16 MB | `8ea7f67cbb0c8639fe9adf4056b32f68f68f028cb32c30db71e5b9a962068ee9` |

All checksums cryptographically recorded in `release_dist/SHA256SUMS.txt` and `release_dist/checksums.txt`.

---

## 6. Verification Checklist for the User

To verify the new release build on your PC:

1. **Launch the Application**:
   - Run `release_dist/Ghostline-Setup.exe` to install, or extract `release_dist/Ghostline-Portable.zip` and run `Run-Ghostline.bat`.
2. **Navigate to Support**:
   - Click the subtle **"Star · Support"** link in the sidebar footer (or click **Help** in the navigation bar and scroll to the bottom).
3. **Inspect the Support Section**:
   - Confirm the clean card title: *"Support Ghostline"*.
   - Confirm the primary **"Star on GitHub"** button with gold star icon. Clicking it opens `https://github.com/Mohammed-Ayyan/GhostLine` in your default browser.
   - Confirm the **UPI QR Code** is displayed on a crisp, solid white tile with generous margins, never inverted.
   - Confirm the disclosure notes:
     - *"Scanning shows the payee name from my bank account."*
     - *"Only pay through this app or the official GitHub repository."*
4. **Scan with Phone**:
   - Open your mobile UPI app (Google Pay, PhonePe, Paytm, BHIM, or your bank's app).
   - Scan the on-screen QR code: confirm the payee name matches your bank account details (`mo***@***`).
5. **Test Dialog & Actions**:
   - Click **[Show larger]**: confirm the 420px high-resolution QR modal appears. Press `Escape` or click `Close` to dismiss.
   - Click **[Save QR image]**: confirm a standard file dialog opens and saves `Ghostline-support-qr.png`.
   - Click **[Report a bug]**: confirm it opens the GitHub Issues page in your browser.
   - Click **[Copy repo link]**: confirm the button flashes *"Copied ✓"* and copies `https://github.com/Mohammed-Ayyan/GhostLine` to your clipboard.
