# Dependency Audit & Security Assessment

**Target:** `Rubric-Setup.exe` / `rubric_win.exe` vs. `Ghostline`  
**Date:** 2026-10-23  
**Status:** Complete Audit  

---

## 1. Original Binary (`rubric_win.exe`) Dependency Inventory

### 1.1 Native Executable & Rust Crates

| Dependency / Crate | Version | Role in Binary | License | Security / Privacy Implication |
| :--- | :--- | :--- | :--- | :--- |
| `tauri` | `2.11.2` | Core application lifecycle, IPC, webview management | MIT / Apache-2.0 | Embeds web assets in `.rdata` via Brotli compression |
| `tauri-runtime-wry` | `2.11.2` | Platform webview abstraction binding to Microsoft Edge WebView2 | MIT / Apache-2.0 | Spawns external Edge WebView2 child processes |
| `tauri-plugin-updater` | `2.12.0` | In-app auto-updater | MIT / Apache-2.0 | Polls `gorubric.vercel.app/updates/windows/latest.json`; verifies Minisign signatures |
| `tauri-plugin-global-shortcut`| `2.3.2` | System-wide keypress capture | MIT / Apache-2.0 | Low-level keyboard hook monitoring keystrokes across applications |
| `tauri-plugin-autostart` | `2.5.1` | Run at Windows logon | MIT / Apache-2.0 | Writes to Windows registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| `tauri-plugin-deep-link` | `2.4.10` | Custom protocol handler (`rubric://`) | MIT / Apache-2.0 | Protocol registration for OAuth callback redirection |
| `tauri-plugin-opener` | `2.5.5` | Shell execution for external URLs | MIT / Apache-2.0 | Launches default browser for payment/support links |
| `windows` / `windows-core` | `0.61.3` | Win32 API bindings (GDI, user32, registry) | MIT / Apache-2.0 | Used for `GetCursorPos`, `BitBlt`, `GetDC`, taskbar visibility control |
| `image` / `image-webp` | `0.25.10` / `0.2.4` | Pixel manipulation & WebP compression | MIT / Apache-2.0 | Compresses screen capture bitmaps to send over network |
| `reqwest` / `tokio` / `rustls`| `0.12.28` / `1.52.3` / `0.26.4` | Async HTTP client & TLS stack | MIT / Apache-2.0 | Sends HTTPS POST requests with screen images to Supabase proxy |
| `serde` / `serde_json` | `1.0.228` / `1.0.150` | Serialization & Deserialization | MIT / Apache-2.0 | Serializes IPC and API payloads |

### 1.2 Extracted Frontend Dependencies (NPM Package Inventory)

Extracted from decompressed web chunks (`index-BxP1xIfm.js`, `account-q5tbbvX1.js`):
- `@supabase/supabase-js` v2.x (Auth client, session storage, REST client)
- `lucide-react` v0.469.0 (UI icons)
- `react` / `react-dom` v18.3.1 (Virtual DOM rendering)
- `tailwindcss` v4.3.1 (CSS utility framework)
- `@tauri-apps/api` v2.x (IPC bridge to Rust backend)

### 1.3 Remote Cloud Infrastructure & Third-Party Services

| Service | Endpoint | Function | Telemetry & Privacy Risk |
| :--- | :--- | :--- | :--- |
| **Supabase Edge Functions** | `https://uqdwhlwfxkiowslqudme.supabase.co` | API proxy (`/functions/v1/openai-proxy`) | **High:** Transmits full user screen captures to external servers |
| **Google Identity** | `https://oauth2.googleapis.com` | OAuth 2.0 user authentication | **Medium:** Tracks user email and identity |
| **Vercel** | `https://gorubric.vercel.app` | Auto-updater check | **Medium:** Leaks IP address and client version |
| **Commercial LLM API** | Third-party cloud (OpenAI / Gemini) | Text & vision inference | **High:** Third-party cloud model retention |

---

## 2. Re-Engineered Local-First Application Dependency Audit

The local-first replacement (`Ghostline`) uses only existing local workstation capabilities:

| Component / Library | Local Version | Purpose in Local Architecture | Remote Network Needs |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11.9 (System) | Application runtime, coordinator, pipeline orchestration | **None (0 B)** |
| **Ollama** | Local daemon | Local GPU model serving and inference engine | **None (Localhost only)** |
| **Windows.Media.Ocr** | Built-in Windows 11 API | Hardware-accelerated local optical character recognition | **None (0 B, native OS engine)** |
| **Pillow (`PIL`)** | 10.3.0 | In-memory bitmap handling, cropping, format translation | **None (0 B)** |
| **OpenCV (`cv2`)** | 4.10.0.84 | Image binarization, contrast enhancement for OCR | **None (0 B)** |
| **PyWin32 (`win32gui`, etc.)**| 306 | Win32 hooks (`GetCursorPos`, window transparency, taskbar) | **None (0 B)** |
| **Pydantic** | 2.13.4 | Schema validation for structured AI outputs | **None (0 B)** |
| **Requests / Urllib3** | 2.34.2 | Local communication with `http://127.0.0.1:11434` | **None (Strictly 127.0.0.1)** |

### 2.1 License Compliance Matrix
All components used in `Ghostline` adhere to permissive open-source licenses:
- Python: PSF License (Permissive)
- Windows.Media.Ocr: Windows OS Platform Feature
- Ollama: MIT License
- Pillow: HPND License (Permissive)
- OpenCV: Apache-2.0 License
- PyWin32: PSF License
- Pydantic: MIT License

### 2.2 Security Comparison
1. **Network Attack Surface:** Reduced from multi-endpoint WAN communication to complete local isolation (0 external listening or outbound ports).
2. **Credential Risk:** Eliminated entirely. No tokens, passwords, or OAuth credentials exist or are stored.
3. **Data Exfiltration:** Screen captures never touch disk or external networks; processed transiently in volatile RAM and immediately discarded after recognition.
