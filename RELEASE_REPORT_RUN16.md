# Ghostline — Run 16 Release Report
**Support Experience (UPI QR / "Buy Me a Coffee") & "Star on GitHub" CTA Integration**

---

## 1. Executive Summary
Run 16 implemented an open-source support ecosystem and community engagement flow for Ghostline across the official documentation and distribution website (`website/`):
1. **Dedicated Support Page (`/support`)**:
   - Clean, lightweight, responsive page highlighting that Ghostline is 100% free, open source, and built by a single developer. Support is clearly presented as entirely optional.
   - Two side-by-side primary cards:
     - **Star on GitHub**: Prominently features a direct link to the repository (`https://github.com/Mohammed-Ayyan/GhostLine`) with live repository stargazer count badge.
     - **Buy Me a Coffee**: Displays a crisp, vector UPI QR code on a solid white tile (retaining dark-on-light contrast across dark/light themes), click-to-enlarge modal with full accessibility/focus trapping, a "Save QR image" button for mobile gallery scanners, bank account payee disclosure, and fraud-safety guidance.
   - **Other Ways to Help**: Provides actionable links to report bugs/issues, share the project via Web Share API / clipboard copy, contribute code (`CONTRIBUTING.md`), and adheres to ethical AI usage guidelines.
2. **Homepage Engagement Section**:
   - Slim, non-intrusive "Enjoying Ghostline?" CTA section positioned right above the footer with direct "Star on GitHub" (with star count) and "Support" buttons.
3. **Install Page Post-Download Card**:
   - An inline dismissible card below the download options on `/install.html` that appears only after a user initiates an installer download. It remembers user dismissal in `sessionStorage` and never blocks, delays, or alters the download links.
4. **Site-Wide Navigation & Footer Alignment**:
   - Added a "Support" nav item with an inline SVG heart icon and integrated a "Community & Support" column into the footer across all site pages (`index.html`, `install.html`, `models.html`, `use.html`, `privacy.html`, `faq.html`, `changelog.html`, `responsible-use.html`, `404.html`).
5. **Strict Scope Discipline**:
   - Desktop application source code (`ghostline/**`), installers, packaging scripts, and video pipelines were completely untouched.

---

## 2. Privacy & Security Audit
Ghostline adheres to a strict zero-leak privacy mandate. A user-provided screenshot containing a payment QR code was sanitized:

### 2.1 What Was Cropped & Redacted
- **Input Image**: `support_inputs/WhatsApp Image 2026-11-08 at 17.15.47.jpeg` (1152×1600 px screenshot).
- **Elements Cropped Out & Destroyed**:
  - Android system status bar (time, battery percentage, signal icons).
  - Banking app navigation bar and user avatar image.
  - Payee legal full name printed as text in the top card.
  - Raw UPI ID address string printed as text at the bottom.
  - Bank affiliation notes and application action buttons.
  - All EXIF metadata, camera tags, device identifiers, and timestamps.
- **Payload Scheme & Masked Identity**:
  - Decoded Scheme: `upi://`
  - Payee Address: **`mo***@***`** (masked strictly per privacy directive).
  - The unmasked payee string and raw UPI ID reside **only** inside the matrix barcode pixels; no text traces exist anywhere on the website, markup, stylesheets, script files, or committed reports.

### 2.2 Proof of Zero Unmasked Data Leaks
Automated pre-ship audit script `tools/web_tests/audit_run16_security.py` scanned all files across `website/`, `tools/`, and `reports/`:
```text
[*] Decoded reference payload (76 chars, scheme: upi://)
[*] Payee ID (masked): mo***@***
[*] Scanning codebase for unmasked tokens (2 sensitive strings)...
[+] ZERO unmasked payee names or raw UPI IDs found anywhere in website/, tools/, or reports/!
```

---

## 3. Shipped Assets & Verification

| Asset | File Path | Format | Size | Geometry / Specs | Quiet Zone | Payload Match |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vector QR** | `website/assets/support/Ghostline-support-qr.svg` | SVG | 2.6 KB | Responsive `viewBox="0 0 450 450"`, `shape-rendering="crispEdges"` | 4 modules | 100% byte-identical |
| **High-Res PNG** | `website/assets/support/Ghostline-support-qr.png` | PNG | 1.01 KB | 600×600 px, 8-bit grayscale | 4 modules | 100% byte-identical |
| **Cropped Backup** | `website/assets/support/Ghostline-support-qr-original-cropped.png` | PNG | 80.6 KB | 600×600 px, EXIF stripped | Cropped quiet zone | 100% byte-identical |

### Payload In-Memory Verification Proof
Both generated vector SVG and high-resolution PNG were rendered in headless Chromium and decoded using OpenCV's `QRCodeDetector`. The decoded payload byte sequence was verified in memory against the raw payload from the user's original image:
```text
[+] Shipped Ghostline-support-qr.png decodes 100% byte-identically to original.
[+] Shipped Ghostline-support-qr-original-cropped.png decodes 100% byte-identically to original.
[+] Decoded enlarged modal QR matches reference 100% byte-identically.
```

---

## 4. Playwright Test Suite & Visual Verification

Automated test suite `tools/web_tests/test_support_and_star.py` validated the entire support experience:

1. **Desktop Rendering (`1440x900`)**:
   - Zero horizontal overflow (`document.documentElement.scrollWidth <= clientWidth`).
   - All sections rendered and visible: navigation header, support cards grid, QR tile with white background, "Other Ways to Help" grid, and footer.
2. **Mobile Rendering (`390x844` - iPhone Viewport)**:
   - Full responsiveness with single-column stacked layout; zero horizontal overflow or clipping.
3. **Accessible Modal Dialog**:
   - Triggered by clicking the QR tile.
   - Focus trapped inside dialog (`#qr-modal`).
   - Enlarged QR renders crisply and decodes byte-identically.
   - Closed cleanly with `Escape` key; focus restored to `#support-qr-tile`.
4. **GitHub Star API Scenarios**:
   - **Scenario A (200 OK, 1234 stars)**: Badge properly displays formatted count `1.2k`.
   - **Scenario B (403 Rate Limit)**: Silently falls back to standard button without star count, zero console errors.
   - **Scenario C (Network Failure / Offline)**: Silently falls back, zero console errors.
   - Link attributes verified: `target="_blank"` and `rel="noopener noreferrer"`.
5. **Install Page Post-Download Card**:
   - Card is initially hidden on `/install.html`.
   - Clicking a download link (`Ghostline-Setup.exe` or `Ghostline-Portable.zip`) makes the card appear.
   - Clicking the dismiss `×` button hides the card and writes to `sessionStorage`.
   - Subsequent page reloads keep the card dismissed.
   - Download link `href` attributes verified untouched.
6. **Console Cleanliness**:
   - **Zero** unhandled exceptions or console errors across all pages visited.

### Captured Visual Screenshots & Inspection
All test screenshots are preserved in `reports/run16/captures/`:

1. `support_desktop_1440.png`:
   - *"Ghostline is free, open source"* (5 words)
   - *"Scan with any UPI app"* (5 words)
   - *"Scanning shows the payee name"* (5 words)
2. `support_mobile_390.png`:
   - *"Star Ghostline on GitHub"* (4 words)
   - *"Scan with any UPI app"* (5 words)
   - *"Only pay through this page"* (5 words)
3. `support_modal_desktop.png`:
   - *"Scan using any UPI app"* (5 words)
   - *"payee name from my bank"* (5 words)
   - *"official GitHub repository"* (3 words)
4. `home_support_cta.png`:
   - *"Enjoying Ghostline? Ghostline is free"* (5 words)
   - *"supporting development. Star on GitHub"* (5 words)
5. `install_post_download_card.png`:
   - *"Enjoying Ghostline? Star it on"* (5 words)
   - *"buy the developer a coffee"* (5 words)

---

## 5. Summary of Files Modified or Created

| File | Status | Description |
| :--- | :--- | :--- |
| `website/support.html` | Created | Dedicated support page with Star CTA, UPI QR card, modal dialog, and non-financial contribution options. |
| `website/assets/support/Ghostline-support-qr.svg` | Created | Vector UPI QR code with responsive viewBox, crispEdges, and 4-module quiet zone. |
| `website/assets/support/Ghostline-support-qr.png` | Created | High-resolution 600×600 px standalone PNG for direct download. |
| `website/assets/support/Ghostline-support-qr-original-cropped.png` | Created | Sanitized and cropped PNG extracted directly from the user's input image. |
| `website/style.css` | Modified | Added styling for support cards, QR tiles, modal dialog, home CTA banner, and post-download card. |
| `website/app.js` | Modified | Implemented GitHub star count fetching with 10-minute caching, modal accessibility, and post-download dismiss logic. |
| `website/index.html` | Modified | Added "Support" link to header navigation, slim "Enjoying Ghostline?" CTA section, and footer support links. |
| `website/install.html` | Modified | Added `#post-download-card` below installer links, updated header nav and footer. |
| `website/privacy.html` | Modified | Added "Website Network Requests & Third-Party APIs" disclosure section, updated header nav and footer. |
| `website/models.html` | Modified | Added "Support" to header navigation and updated footer with Community & Support links. |
| `website/use.html` | Modified | Added "Support" to header navigation and updated footer with Community & Support links. |
| `website/faq.html` | Modified | Added "Support" to header navigation and updated footer with Community & Support links. |
| `website/changelog.html` | Modified | Added "Support" to header navigation and updated footer with Community & Support links. |
| `website/responsible-use.html` | Modified | Added "Support" to header navigation and updated footer with Community & Support links. |
| `website/404.html` | Modified | Added "Support" to header navigation. |
| `website/sitemap.xml` | Modified | Registered `https://ghostline.vercel.app/support` with weekly/monthly crawl priority. |
| `tools/prepare_support_qr.py` | Created | Tool to safely decode, crop, and generate vector SVG and PNG assets. |
| `tools/verify_svg_rendering_and_decoding.py` | Created | Verification tool to render SVG in Chromium and decode in OpenCV. |
| `tools/web_tests/test_support_and_star.py` | Created | Automated Playwright test suite for all Run 16 requirements. |
| `tools/web_tests/audit_run16_security.py` | Created | Pre-ship security and privacy audit script scanning repo for leaks. |
| `.gitignore` | Modified | Added `support_inputs/` to ensure private source photos are never committed. |

---

## 6. Privacy Architecture Disclosure
The following disclosure was added directly to `website/privacy.html` under the section **"Website Network Requests & Third-Party APIs"**:
```html
      <!-- Website Network Requests -->
      <section class="info-card mb-5">
        <h2>Website Network Requests &amp; Third-Party APIs</h2>
        <p class="text-secondary mb-3">
          This website is static and does not use tracking cookies, analytics scripts, or third-party ad beacons. When browsing the site:
        </p>
        <ul class="feature-checklist">
          <li><strong>GitHub Releases API:</strong> To display the latest release version, the site queries the public GitHub Releases API (<code>https://api.github.com/repos/Mohammed-Ayyan/GhostLine/releases/latest</code>).</li>
          <li><strong>GitHub Stargazers Count:</strong> To display current stargazer counts on the Star buttons, the site queries public repository metadata (<code>https://api.github.com/repos/Mohammed-Ayyan/GhostLine</code>). Responses are cached in your browser's <code>sessionStorage</code> for 10 minutes to minimize requests.</li>
          <li><strong>Data Transmitted:</strong> Only standard HTTP request headers sent by your browser. No personal data, tracking identifiers, or cookies are transmitted or stored by Ghostline.</li>
        </ul>
      </section>
```

---

## 7. User Verification Checklist
To verify the live QR code in production with your own mobile device:
1. **Open Mobile UPI App**: Open Google Pay, PhonePe, Paytm, BHIM, or your mobile banking app.
2. **Scan the QR Code**: Point the camera scanner at the QR code displayed on `https://ghostline.vercel.app/support` or in the enlarged modal.
3. **Verify Payee Confirmation**: Confirm that your UPI app displays the expected account holder name associated with your bank account (`mo***@***`), enter a nominal test amount (e.g. ₹1), and verify that payment completes smoothly.
