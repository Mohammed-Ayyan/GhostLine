# Ghostline — Run 15 Out of Scope Findings

Per Run 15 strict scope boundaries, the following components are strictly OUT OF SCOPE and must NOT be modified:
1. **Website HTML/CSS/JS**: `website/*.html`, `website/*.css`, `website/*.js`, `website/vercel.json` (user handles website deployments).
2. **UI Redesign**: No visual restyling beyond the specified text widget wrapping, caps, and HUD geometry clamping.
3. **Hotkeys**: No hotkey definitions may change (`Alt + /` remains silent screen scan; `Alt + Q` starts live listening).
4. **HUD Window Flags**: Frameless, topmost, no-activate, click-through behavior, and display-capture exclusion flags remain strictly untouched.
5. **AI Answer / Provider Logic**: AI inference models, router logic, and provider implementations remain untouched.
6. **Hardware / LED / Tray**: No changes to hardware controls or system tray implementation.
7. **Installer Logic**: `installer.iss` and installer setup GUI logic remain unchanged except for standard version bump.
8. **README & Third-Party Notices**: Readme and third-party notices outside allowed paths remain untouched.
