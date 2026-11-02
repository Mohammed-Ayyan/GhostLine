# Ghostline — Run 3 Part 2: Interactive Website Verification Report

**Date**: 2026-11-02  
**Branch**: `feature/hardware-controls-and-release`  
**Status**: **VERIFIED-AUTOMATED & VERIFIED-VISUAL**

---

## 1. Overview & Architecture
- **Location**: `website/` (ready for zero-configuration GitHub Pages hosting).
- **Stack**: 100% Vanilla HTML5, CSS3, JavaScript. Zero frameworks, zero build steps, zero external CDNs, fonts, or tracking scripts.
- **Design Language**: Microsoft Fluent 2 Dark theme tokens exported directly from `ghostline/ui/theme/tokens.py`.
- **Typography**: Native Windows typography stack (`Segoe UI Variable Text`, `Segoe UI Variable`, `Segoe UI`, system fallbacks) + `Cascadia Code` / `Consolas` for code blocks and keycaps.

---

## 2. Page Structure & Features
1. **Header**: Sticky navigation with translucent blur backdrop (`#1F1F1F` at 85% opacity), logo, `v1.0.2` brand badge, anchors to sections, and direct "Download" CTA.
2. **Hero**: Headline, one-sentence value proposition, primary download link (`https://github.com/Mohammed-Ayyan/GhostLine/releases/latest`), GitHub source button, and 4 trust indicators ("Windows 10 & 11 Native", "100% Offline with Ollama", "Windows DPAPI Encryption", "Zero Telemetry").
3. **Ethical Use Notice**: Framed info callout emphasizing ethical study and mock interview use, with explicit guidance to follow school/employer/interviewer rules.
4. **Interactive Sandbox (Client-Side Only, No AI Called)**:
   - **Screen Solve**: 3 selectable questions (Networking MCQ, Python Output, System Design), animated reticle sweep, answer chip, and technical explanation.
   - **Live Meeting**: Scripted dialogue simulation between `[Call]` and `[You]`, dynamic scrolling transcript box, and grounded bulleted technical suggestion.
   - **Profile Grounding**: Interactive form fields (Role, Technologies, Experience) that dynamically re-render a grounded behavioral interview answer without fabrication.
   - **Data Boundary**: Real-time switcher between Local Ollama (Loopback 127.0.0.1:11434, zero network) and Cloud BYOK providers (OpenAI, Gemini, Groq) with hardware-level DPAPI encryption details.
5. **How It Works**: 3-step numbered journey (Capture & Recognize, Ground & Route, Solve & Overlay).
6. **3-Minute Setup**: Parallel cards for Path A (100% Offline with Ollama) and Path B (Cloud BYOK).
7. **Where Your Data Goes**: Comprehensive data destination table across all 6 supported provider paths.
8. **Hotkeys Reference**: 2x2 grid displaying `Alt + /`, `Alt + Shift + /`, `Alt + Q`, and `Alt + Shift + X`.
9. **FAQ Accordion**: 4 interactive expandable items covering offline mode, key protection, profile grounding, and telemetry.
10. **Footer**: MIT License notice, GitHub repository link, security policy, and third-party notices.

---

## 3. Playwright Verification (Microsoft Edge Headless)
- **Tool**: `tools/verify_website.py`
- **Engine**: Native Windows Microsoft Edge (`channel="msedge"`).
- **Console Errors**: **0 errors**.
- **Page Errors**: **0 errors**.
- **Interactive Keyboard Walkthrough**:
  - `#tab-btn-solve` focused via keyboard.
  - ArrowRight switched to `#tab-btn-audio` and `#tab-btn-profile`.
  - ArrowLeft navigated back to Screen Solve tab.
  - Question option 2 selected and simulated solve clicked; verified `[0, 4]` badge.
  - FAQ accordion expanded on click/focus.
  - All 17 links validated.
- **Responsive Viewport Renders**:
  - `website/screenshots/website_1440px.png` (1440x900 desktop, 445 KB) — **VERIFIED-VISUAL**.
  - `website/screenshots/website_768px.png` (768x1024 tablet, 440 KB) — **VERIFIED-VISUAL**.
  - `website/screenshots/website_390px.png` (390x844 mobile, 394 KB) — **VERIFIED-VISUAL**.

