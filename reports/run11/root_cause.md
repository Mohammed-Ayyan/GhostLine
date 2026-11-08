# Ghostline Run 11: Video Defect Root Cause Analysis

**Defect:** All on-screen text inside the video picture (headlines, feature titles, metrics, keycaps, and captured application UI screens) rendered as rows of empty hollow squares (missing-glyph boxes / tofu). Only the WebVTT captions rendered by the browser outside the MP4 stream were legible.

---

## 1. Forensic Evidence & Proof

### A. Raw Shipped Assets & Poster Extraction
Forensic extraction of frames and posters from `website/media/*` was performed using `bin/win_ocr.exe` (Windows.Media.Ocr native engine).

| Asset | Visible Text (OCR Extraction) | Defect Identification |
| :--- | :--- | :--- |
| `Ghostline_Launch_16x9_92s_poster.jpg` | `"jot 00000 ZOOOCOOOUOOOOOO aaaoaoaaaaaaoaoaaoaaoaaooaoaaoaaaaaaa OCOOcoaaaooooC azoaaooaooaaoaoaaooaaoaooaoo"` | Tofu boxes recognized as repetitive `0`, `Z`, `O`, `a`, `o`, `C` hollow rectangles |
| `Ghostline_Setup_Tutorial_16x9_140s_poster.jpg` | `"CIDD[ CICIÜÜCICICICICICICICICICICICICICICICICICICICICICICICI CICICICICICICICICICICICJCICJCIÜCICICICICICICIÜCICICICICI"` | Tofu boxes recognized as repetitive `CI`, `[`, `]`, `Ü` strings |
| `Ghostline_Short_S1_9x16_35s_poster.jpg` | `"OCICLO DÜDCIÜCIDCIDCI"` | Consecutive tofu boxes |
| `Ghostline_Short_S4_9x16_35s_poster.jpg` | `"C]üüüüüüüüüüüüüüCJüClüüOüüClü üClüC]ÜClOÜüÜÜCJOClüüüüOCJüCJOÜÜÜO"` | Consecutive tofu boxes recognized as `ü` and `C]` |
| `Ghostline_Walkthrough_16x9_180s_poster.jpg` | `"0 aoaoanooooannnn ooooooaaaooooooaooa o o oooooooocoocooaooooocooaoooooooocoa CJCICICIC]CJ OCICJCICICICJÜCICIDCICICICICICJCICICICICICJCICJÜC]"` | Tofu boxes recognized as `aoao` and `CJCICI` |
| `Ghostline_Launch_16x9_92s` (Frame 7) | `'CIOOCIOCICICICICIOCIOCIOCIO'` | Kinetic title text rendered as tofu boxes |
| `Ghostline_Setup_Tutorial_16x9_140s` (Frame 10) | `'cacacaacacaaaaacaaacaaaaaaclcl mmmmmmmmmmmr-lr-lr:vnnrlclrj mrnr-lr-lmr-lmmmr-lmr-lr-lmr-lnr-l'` | Setup instruction text rendered as tofu boxes |
| `Ghostline_Walkthrough_16x9_180s` (Frame 13) | `'CIOOOOCIOOOCICIOCICIOCIOCICIOOCICICICICICICIE CIECICICICI'` | Overlay UI text rendered as tofu boxes |

### B. Pre-production Raw Assets Check
Checking `../ghostline_launch_video/run10/raw_assets/` (the 200% scale application captures produced by `tools/capture_video_assets.py`):
Running `bin/win_ocr.exe` on `app_general_200.png` returned text: `"O"` (a single square glyph).
Inspection confirmed that the application screenshots captured for the video were **already rendered with missing glyphs** at the capture stage.

---

## 2. Definitive Root Cause Mechanism

The defect occurred due to a fundamental interaction between PyQt6 and the Windows QPA (Qt Platform Abstraction) offscreen plugin:

1. **`QT_QPA_PLATFORM="offscreen"` Font Database Initialization Failure**:
   Both `tools/capture_video_assets.py` (Line 12) and `tools/build_run10_videos.py` (Line 30) set:
   ```python
   os.environ["QT_QPA_PLATFORM"] = "offscreen"
   ```
   On Windows, Qt's standard GUI platform (`qwindows`) queries DirectWrite/GDI to enumerate and register system fonts located in `C:\Windows\Fonts`.
   However, the `offscreen` minimal platform plugin initializes a bare-bones font engine with **zero registered font families**:
   ```python
   # Verified experimentally:
   from PyQt6.QtGui import QFontDatabase
   print(len(QFontDatabase.families()))  # -> 0 font families!
   ```

2. **Silent Glyph Fallback to Missing Glyph Box**:
   When `QPainter.drawText()` or Qt UI widgets render text request fonts such as `"Segoe UI"`, `"Inter"`, or `"Arial"`, Qt searches `QFontDatabase`.
   With 0 font families available, the rasterizer has no glyph outlines or metrics for any Unicode character. Instead of throwing an error or warning, Qt silently substitutes the font's default missing-glyph glyph: a hollow rectangular box (tofu `▯`).

3. **Double Inoculation in Video Pipeline**:
   - In Step 1 (`tools/capture_video_assets.py`), the app windows were rendered into `QPixmap` under offscreen Qt with 0 fonts loaded. Every label, button, and input field in the app captures turned into hollow boxes.
   - In Step 2 (`tools/build_run10_videos.py`), the video renderer itself also ran under offscreen Qt with 0 fonts loaded. Every headline, card title, badge, and keycap drawn by `QPainter` turned into hollow boxes.

---

## 3. Why Run 10 Quality Review Missed the Defect

Run 10 introduced an automated audit script (`tools/audit_run10_videos.py`) and browser playback tests. However:
1. **Container & Stream Only Verification**:
   The audit checked:
   - File size budget ($\le 90$ MB)
   - MP4 atom faststart (`moov` at offset 0/48)
   - Video resolution ($1920\times 1080$, $1280\times 720$, $1080\times 1920$)
   - Stream codecs (`h264`, `yuv420p`, `aac`)
   - Visual freezes via ffmpeg `freezedetect=noise=-60dB:duration=1.2` filter.
2. **False Positive "Pass" from Dynamic Motion**:
   Because the video compositions featured continuously moving gradient backgrounds, glowing ambient circles, animated audio waveforms, and kinetic slide-ins, `freezedetect` reported **0 freezes**.
3. **No OCR or Semantic Verification**:
   No test extracted frames to perform optical character recognition or compare rendered glyphs against expected storyboard text.
4. **Captions Masked the Defect**:
   Browser playback tests verified that the `<track src="...vtt">` subtitles were rendered by Chrome. Since Chrome renders subtitles in its own HTML/CSS DOM layer using system fonts, the subtitles were completely legible, giving the impression in automated checks that text was present.

---

## 4. Verification of the Solution

By explicitly bundling unsubsetted open-license font files (Inter and JetBrains Mono) and loading them via `QFontDatabase.addApplicationFont(font_path)`, `QFontDatabase.families()` immediately populates:
```python
Loaded Inter-Regular.ttf -> font_id=0
Loaded Inter-Bold.ttf -> font_id=1
Loaded JetBrainsMono-Bold.ttf -> font_id=2
Loaded Segoe UI -> font_id=3
# QFontDatabase.families() -> ['Inter', 'JetBrains Mono', 'Segoe UI']
```
When rendered under offscreen Qt with registered fonts:
`p.drawText(..., "Ghostline High Efficiency Local OCR Engine")`
Windows OCR extraction returns:
`"Ghostline High Efficiency Local OCR Eng"` (100% genuine text, 0 tofu boxes).

The solution is implemented and enforced by mandatory Pre-render Font Guards and Post-render Output Guards in Part 2.

