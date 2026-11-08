# Ghostline — Run 14 Out of Scope Manifest

The following domains and components are explicitly OUT OF SCOPE for Run 14 and must NOT be modified:

1. **Website & Videos**:
   - `website/*` (HTML, CSS, JS, media files, vercel.json, site-config.js)
   - Video generation pipeline and assets in `website/media/` and `tools/video/`
2. **Scan / MCQ Question Solving**:
   - Screen question capture, OCR solve pipelines, and MCQ answers (`Alt + /`).
   - The HUD must strictly NEVER auto-show on `Alt + /`.
3. **Hotkeys & Shortcuts**:
   - Global hotkey matrix must remain unchanged (`Alt + /`, `Alt + A`, `Alt + T`, `Alt + Shift + C`, `Ctrl + Alt + Q`).
4. **Hardware & Tray Controls**:
   - Keyboard LED signalling / hardware controls.
   - System tray menu, notification icon, taskbar behavior.
5. **Installer & Build Scripts**:
   - Inno Setup installer logic (`installer.iss`).
   - README and other general documentation files.
6. **Other Providers Internals**:
   - Internal cloud provider client implementations outside of the live routing interface.

