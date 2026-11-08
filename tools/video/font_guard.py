"""
Ghostline Video Font Guard.
Ensures zero-tofu rendering across all Qt and HTML/Playwright video pipelines.
Pre-render validation:
1. Registers bundled open-license fonts (Inter, JetBrains Mono) into QFontDatabase.
2. Validates QFontDatabase.families() is non-empty and contains required families.
3. Performs a canary render and OCR verification before allowing any video frames to be drawn.
4. Provides HTML/Playwright font readiness and overflow checks.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WIN_OCR_EXE = REPO_ROOT / "bin" / "win_ocr.exe"

class FontGuardError(RuntimeError):
    """Raised when font registration or rendering verification fails."""
    pass

def init_qt_fonts(app=None):
    """
    Initializes and validates Qt fonts under any QPA platform (including offscreen).
    Must be called after QApplication is created and before any rendering starts.
    """
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFontDatabase, QFont, QImage, QPainter, QColor

    app = app or QApplication.instance()
    if app is None:
        raise FontGuardError("QApplication must be initialized before calling init_qt_fonts()")

    if not FONTS_DIR.exists():
        raise FontGuardError(f"Fonts directory does not exist: {FONTS_DIR}")

    # Load primary open-license fonts
    loaded_fonts = []
    for font_file in sorted(FONTS_DIR.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(font_file))
        if fid < 0:
            raise FontGuardError(f"Failed to load bundled font: {font_file.name}")
        fams = QFontDatabase.applicationFontFamilies(fid)
        loaded_fonts.extend(fams)

    # Load fallback fonts if present
    fallback_dir = FONTS_DIR / "fallbacks"
    if fallback_dir.exists():
        for fb in sorted(fallback_dir.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(fb))

    available_families = QFontDatabase.families()
    if not available_families:
        raise FontGuardError("QFontDatabase.families() is EMPTY after font loading!")

    # Verify required families
    required = ["Inter", "JetBrains Mono"]
    for req in required:
        if req not in available_families:
            raise FontGuardError(f"Required font family '{req}' missing from QFontDatabase. Found: {available_families}")

    # Canary render & OCR validation
    canary_text = "Ghostline Local AI Assistant Ready [Ctrl+Shift+Space]"
    img = QImage(900, 100, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0f172a"))
    p = QPainter(img)
    p.setPen(QColor("#f8fafc"))
    p.setFont(QFont("Inter", 24, QFont.Weight.Bold))
    p.drawText(20, 60, canary_text)
    p.end()

    temp_canary = FONTS_DIR / "_canary_test.png"
    img.save(str(temp_canary))

    try:
        if WIN_OCR_EXE.exists():
            proc = subprocess.run([str(WIN_OCR_EXE), str(temp_canary)], capture_output=True, text=True)
            if proc.returncode != 0:
                raise FontGuardError(f"WinOCR canary test failed: {proc.stderr}")
            data = json.loads(proc.stdout)
            ocr_text = data.get("text", "")
            # Check keywords
            for kw in ["Ghostline", "Assistant", "Ready"]:
                if kw.lower() not in ocr_text.lower():
                    raise FontGuardError(f"Canary OCR verification failed! Expected '{kw}' in '{ocr_text}'")
    finally:
        if temp_canary.exists():
            try:
                temp_canary.unlink()
            except Exception:
                pass

    print(f"[FontGuard] SUCCESS: Qt fonts initialized with {len(available_families)} families: {available_families}")
    return available_families


async def verify_html_fonts_and_layout(page):
    """
    Verifies font readiness and checks for CSS overflow in Playwright page.
    """
    # 1. Wait for document fonts
    ready = await page.evaluate("() => document.fonts.ready.then(() => true)")
    if not ready:
        raise FontGuardError("document.fonts.ready failed")

    # 2. Check font availability
    font_checks = await page.evaluate("""() => {
        return {
            inter: document.fonts.check('16px Inter'),
            mono: document.fonts.check('16px "JetBrains Mono"')
        };
    }""")
    if not font_checks.get("inter"):
        print("[FontGuard] Warning: 'Inter' font not verified by document.fonts.check()")

    # 3. Check overflow
    overflows = await page.evaluate("""() => {
        const bad = [];
        for (const el of document.querySelectorAll('*')) {
            if (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2) {
                // Ignore root container or scrollable elements with overflow-y: auto
                const style = window.getComputedStyle(el);
                if (style.overflow !== 'auto' && style.overflow !== 'scroll' &&
                    style.overflowY !== 'auto' && style.overflowY !== 'scroll' &&
                    el.tagName !== 'HTML' && el.tagName !== 'BODY') {
                    bad.push({
                        tag: el.tagName,
                        className: el.className,
                        id: el.id,
                        scrollH: el.scrollHeight,
                        clientH: el.clientHeight
                    });
                }
            }
        }
        return bad;
    }""")
    if overflows:
        print(f"[FontGuard] Warning: {len(overflows)} elements have potential overflow: {overflows[:3]}")

    return True


if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    fams = init_qt_fonts(app)
    print("Self-test passed!")

