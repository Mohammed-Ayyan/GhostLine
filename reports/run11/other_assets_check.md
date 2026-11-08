# Part 6: Non-Media Asset Inspection (Read-Only)

**Date**: 2026-11-08  
**Scope**: All static images, documentation figures, and screenshots outside `website/media/*`.  
**Constraint**: Read-only inspection; no forbidden website HTML/CSS or documentation files were modified.

---

## 1. Inventory of Inspected Assets

The repository was searched for all static images (`.png`, `.jpg`, `.webp`) used in documentation and website presentation:

| Asset Path | Resolution / Size | Purpose |
| :--- | :--- | :--- |
| `docs/images/dashboard_fluent2.png` | 1344x896 (62.1 KB) | README Fluent 2 Dashboard screenshot |
| `docs/images/hud_fluent2.png` | 1344x896 (55.2 KB) | README Floating HUD overlay screenshot |
| `docs/images/audio_fluent2.png` | 1344x896 (60.6 KB) | README Live Audio Assistant screenshot |
| `docs/images/model_fluent2.png` | 1344x896 (64.3 KB) | README Model & Provider settings screenshot |
| `website/screenshots/website_1440px.png` | 1440x900 (874.0 KB) | Website desktop presentation screenshot |
| `website/screenshots/website_768px.png` | 768x1024 (850.5 KB) | Website tablet presentation screenshot |
| `website/screenshots/website_390px.png` | 390x844 (770.9 KB) | Website mobile presentation screenshot |
| `website/icon.png` | 256x256 (8.0 KB) | Favicon / App branding icon |

---

## 2. OCR & Missing Glyph (Tofu) Forensic Audit

Each asset was scanned with the Windows Native OCR engine (`bin/win_ocr.exe`) and passed through the missing-glyph regex detector (`r'(\b[oO0QUD]{4,}\b|[\u25A0-\u25FF\uFFFD\u25AF\u25AD\u25A1]{2,})'`).

### Results:

1. **`docs/images/dashboard_fluent2.png`**:
   - **OCR Word Count**: 1,991 characters / ~260 words.
   - **Sample Legible Text**: `"Ghostline v1.0.2 • Ollama Ready Dashboard Screen Assistance Captures question under your cursor..."`
   - **Tofu Detected**: **0** (Clean, native system font rendering).

2. **`docs/images/hud_fluent2.png`**:
   - **OCR Word Count**: 1,938 characters / ~250 words.
   - **Sample Legible Text**: `"Live Call Captions System: Active AI Ready • You: Which data structure guarantees..."`
   - **Tofu Detected**: **0** (Clean, native system font rendering).

3. **`docs/images/audio_fluent2.png`**:
   - **OCR Word Count**: 1,912 characters / ~250 words.
   - **Sample Legible Text**: `"Ghostline v1.0.2 • Ollama Ready Audio Assistance Configure real-time microphone dictation..."`
   - **Tofu Detected**: **0** (Clean, native system font rendering).

4. **`docs/images/model_fluent2.png`**:
   - **OCR Word Count**: 1,954 characters / ~255 words.
   - **Sample Legible Text**: `"Ghostline v1.0.2 • Ollama Ready AI Inference & Providers (BYOK) Choose between Local Ollama and Cloud APIs..."`
   - **Tofu Detected**: **0** (Clean, native system font rendering).

5. **`website/screenshots/website_1440px.png`**:
   - **OCR Word Count**: 17,085 characters / ~2,200 words.
   - **Sample Legible Text**: `"Ghostline v1.0.3 Videos Features Demo Install Guide Model Picker User Guide Privacy Download..."`
   - **Tofu Detected**: **0** (Clean, browser-rendered Inter font).

6. **`website/screenshots/website_768px.png` & `website/screenshots/website_390px.png`**:
   - **Tofu Detected**: **0** (Clean layout rendering).

---

## 3. Conclusion & Recommendation

None of the static images in `docs/images/` or `website/screenshots/` exhibit the missing-glyph (tofu) defect. The tofu defect was strictly isolated to headless video rendering where `QT_QPA_PLATFORM="offscreen"` was invoked without bundled fonts.

No changes were made or required for non-media assets.

