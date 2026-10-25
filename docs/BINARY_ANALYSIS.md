# Binary Analysis Report: Rubric-Setup.exe and rubric_win.exe

**Target Artifact:** `Rubric-Setup.exe`  
**Extracted Binary:** `rubric_win.exe`  
**Analysis Date:** 2026-10-23  
**Auditor:** Antigravity Autonomous Systems Agent  
**Environment:** Windows 11 (AMD64), NVIDIA RTX 4050 6GB VRAM, 16GB RAM  

---

## 1. Executive Summary

Static and architectural analysis of `Rubric-Setup.exe` reveals that the target application is **not** a conventional native C++ or .NET application, nor a heavyweight Electron package. It is a **Tauri v2** desktop application compiled in **Rust** (targeting `x86_64-pc-windows-msvc`), packaging a **React 18 / Vite / Tailwind CSS v4.3.1** single-page web frontend that renders using the system's **Microsoft Edge WebView2** runtime.

The application functions as a semi-automated academic or assessment exam-assistance utility (originally named `IconCheater` in developer build paths, later rebranded to `Rubric`). Its core premise is on-screen question capture triggered by user cursor placement, followed by streaming answer indicators displayed through a floating GUI HUD, system tray camouflage icons, screen flashes, or keyboard backlights.

Crucially, **the original binary contains no local AI inference engine, no local vision model, and no on-device OCR engine.** Every question recognition and answering attempt is strictly dependent on transmitting full-resolution screen captures over HTTPS to a remote Supabase Edge Function proxy (`https://uqdwhlwfxkiowslqudme.supabase.co/functions/v1/openai-proxy`) backed by commercial cloud LLM APIs (OpenAI / Google Gemini), gated by Google OAuth authentication and subscription quotas.

---

## 2. File Identification and Cryptographic Hashes

### 2.1 Installer Binary (`Rubric-Setup.exe`)
- **File Name:** `Rubric-Setup.exe`
- **File Size:** 17,990,029 bytes (~17.15 MiB)
- **SHA-256 Hash:** `E5B72D4B68E1AE201581EC4F1613EDB76B4EC0908413EFA34057F214EE95C0F9`
- **Packaging Container:** Nullsoft Scriptable Install System (NSIS-3 Unicode)
- **Compression Method:** LZMA:23 Solid
- **Headers Size:** 74,786 bytes
- **Embedded Stub Size:** 52,736 bytes
- **Digital Signature:** `NotSigned` (SignatureType: None, Status: Unsigned)

### 2.2 Payload Binary (`rubric_win.exe`)
- **File Name:** `rubric_win.exe`
- **File Size:** 21,872,640 bytes (~20.86 MiB)
- **PE Machine Type:** `0x8664` (AMD64 / x86_64)
- **Subsystem:** Windows GUI (`0x0002`)
- **TimeDateStamp:** `1792643648` (Sun Oct 25 2026 04:34:08 GMT)
- **Characteristics:** `0x0022` (EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE)
- **PE Format:** PE32+ (64-bit)

---

## 3. PE Section Layout & Metadata

| Section | Virtual Size | Virtual Address | Raw Size | Raw Offset | Characteristics / Entropy Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `.text` | `0x004AB256` (4.67 MB) | `0x00001000` | `0x004AB400` | `0x00000400` | Executable code (Rust standard library, runtime, Tauri v2 core, crates) |
| `.rdata` | `0x01003614` (16.01 MB) | `0x004AD000` | `0x01003800` | `0x004AB800` | Read-only data, string tables, Brotli-compressed embedded web assets |
| `.data` | `0x00003608` (13.5 KB) | `0x014B1000` | `0x00000C00` | `0x014AF000` | Read/write initialized global state and atomic pointers |
| `.pdata` | `0x0001878C` (98.0 KB) | `0x014B5000` | `0x00008800` | `0x014AFC00` | Exception handling and unwind function tables (x64 SEH) |
| `.tls` | `0x00000315` (789 B) | `0x014CE000` | `0x00000400` | `0x014C8400` | Thread-local storage structures |
| `_RDATA` | `0x000001F4` (500 B) | `0x014CF000` | `0x00000200` | `0x014C8800` | Read-only metadata references |
| `.rsrc` | `0x0000D1D0` (52.5 KB) | `0x014D0000` | `0x0000D200` | `0x014C8A00` | Resource section: application icon, version info, manifest |
| `.reloc` | `0x00006250` (24.5 KB) | `0x014DE000` | `0x00006400` | `0x014D5C00` | Base relocation table (ASLR support) |

---

## 4. Build Environment & Toolchain Forensics

Embedded debug and crate registry paths in `rubric_win.exe` leak developer workstation paths:
- **Developer Host:** macOS workstation (Darwin POSIX path layout)
- **Developer User:** `kimjaewon`
- **Original Project Path:**  
  `/Users/kimjaewon/Downloads/01_Work/02_SideProjects/05_VibeCoding/2026.06_23_IconCheater/2026.10_23_21_RubricWin/`
- **Build Methodology:** Cross-compiled targeting Windows (`x86_64-pc-windows-msvc`) using Cargo/Rust toolchain.
- **Rust Toolchain Details:**
  - Rust Standard Library (`library\std\src\...`)
  - Allocator: System CRT / mimalloc via Rust std
- **Key Rust Crates Identified:**
  - `tauri-2.11.2`
  - `tauri-runtime-wry-2.11.2`
  - `tauri-utils-2.9.2`
  - `tauri-plugin-autostart-2.5.1`
  - `tauri-plugin-deep-link-2.4.10`
  - `tauri-plugin-global-shortcut-2.3.2`
  - `tauri-plugin-opener-2.5.5`
  - `tauri-plugin-updater-2.12.0`
  - `windows-0.61.3`, `windows-core-0.61.2`, `windows-registry-0.5.3`
  - `image-0.25.10`, `image-webp-0.2.4`
  - `reqwest-0.12.28`, `tokio-1.52.3`, `tokio-rustls-0.26.4`
  - `serde-1.0.228`, `serde_json-1.0.150`

---

## 5. Decompressed Frontend Asset Inventory

Tauri v2 compresses all static web assets using the **Brotli** compression algorithm and packs them into the `.rdata` section within `EmbeddedAssets`. All assets were extracted and decompressed byte-for-byte:

| Extracted File | Decompressed Size | Description & Role |
| :--- | :--- | :--- |
| `index.html` | 402 B | Minimal entrypoint bootstrapping `/assets/index-BxP1xIfm.js` and styling |
| `index-BxP1xIfm.js` | 465,902 B | React 18 DOM runtime, Lucide icons, Tauri IPC bindings, custom command glue |
| `App-BL-PPmFs.js` | 143,827 B | Main application dashboard: modes, subscription, hotkeys, tray setup |
| `AnswerWindow-BPX5OkJO.js` | 3,261 B | Floating transparent HUD overlay ("Thinking" -> "Answer") |
| `account-q5tbbvX1.js` | 233,190 B | Supabase client library, authentication, session tokens, quota enforcement |
| `keys-BW5duKxF.js` | 3,866 B | Global accelerator keys parser and window drag/resize primitives |
| `index-CV1mDV-H.css` | 31,055 B | Compiled Tailwind CSS v4.3.1 design system (dark-mode first) |

---

## 6. Remote Network Infrastructure & Hardcoded Secrets

The binary embeds explicit network targets:

1. **AI Proxy Endpoint:**  
   `https://uqdwhlwfxkiowslqudme.supabase.co/functions/v1/openai-proxy`
2. **Supabase Publishable Client Key:**  
   `sb_publishable_OtnLhafRl1Olr7aehXg4Jg_Z2_Wc4Fw`
3. **Google OAuth Client ID:**  
   `com.googleusercontent.apps.117244165385-67ngsev3nspsi7bb5eq29cr0sr02lgd1`  
   Endpoint: `https://oauth2.googleapis.com/token`
4. **Update Server & Minisign Public Key:**  
   Endpoint: `https://gorubric.vercel.app/updates/windows/latest.json`  
   Minisign Public Key:  
   `dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEIxREY3Q0RGNTg1QjM5RUIKUldUck9WdFkzM3pmc1pCbXN4RTJ6c1QydDhwTEg3d0s5aXFHZDl0djNCaXp4dFRXY3UrR0xyQngK`

---

## 7. Forensic Verification of Question Recognition

Contrary to potential claims of localized optical character recognition or on-device language model processing:
1. **No Tesseract, Windows Media OCR, PaddleOCR, or ONNX runtimes** are linked in the binary.
2. The Rust backend registers `capture_and_answer(accessToken)`. When invoked:
   - It captures screen pixels using Win32 GDI (`GetDC`, `CreateCompatibleBitmap`, `BitBlt`) at the coordinate obtained from `GetCursorPos`.
   - The pixel buffer is encoded to **WebP** via crate `image-webp-0.2.4`.
   - The WebP payload is posted over HTTPS to `supabase.co/functions/v1/openai-proxy`.
   - The proxy receives system prompt directive: `target question nearest the saved pointer`.
   - Results stream back over HTTP Server-Sent Events (SSE) and are re-emitted locally via Tauri event `remote-view`.
3. If internet connection is absent, or if the user is unauthenticated or runs out of credits, the application refuses to operate.

---

## 8. Summary of Findings

- **Architecture:** Hybrid Rust + WebView2 (Tauri v2).
- **Legitimacy & Integrity:** Unsigned binary from indie developer `kimjaewon`.
- **Local Autonomy:** 0% (Pure cloud dependency).
- **Feasibility of Local Replacement:** 100% achievable. The desktop pipeline (screenshot near pointer -> local OCR -> local quantized LLM via Ollama -> modular HUD/tray indicators) can be completely reproduced offline without cloud subscriptions or telemetry.
