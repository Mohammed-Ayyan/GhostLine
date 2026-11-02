# Third-Party Software Notices & Licenses

Ghostline incorporates and depends upon several open-source libraries and assets. This document outlines the third-party components, their licensing terms, and licensing obligations.

---

## 1. Project License
Ghostline is licensed under the **MIT License**:
```
MIT License
Copyright (c) 2026 Ghostline Contributors
```

---

## 2. Qt Binding License Analysis: PyQt6 vs. PySide6

Ghostline currently uses **PyQt6** for its GUI framework.

### PyQt6 Licensing (GPLv3 / Commercial)
- **Upstream Author**: Riverbank Computing Limited.
- **License**: GNU General Public License version 3 (GPLv3), with exceptions for certain free software licenses, or a commercial license.
- **Distribution Implication**:
  - Under GPLv3, distributing compiled standalone binaries of Ghostline that statically or dynamically bundle PyQt6 requires the entire binary distribution and source code to be made available under the GPLv3.
  - While Ghostline's source files may be permissive MIT, the resulting binary package distributed to end-users is subject to GPLv3 obligations.
  - If a proprietary, closed-source distribution is desired, a commercial license must be purchased from Riverbank Computing.

### PySide6 Alternative (LGPLv3)
- **Upstream Author**: The Qt Company.
- **License**: GNU Lesser General Public License version 3 (LGPLv3) / Commercial.
- **Distribution Implication**:
  - PySide6 is the official Qt for Python binding.
  - Under LGPLv3, dynamic linking allows Ghostline to be distributed under permissive terms (such as MIT or proprietary) without forcing GPL copyleft on Ghostline's original codebase, provided users are given the ability to swap or relink the LGPL library components.
- **Recommendation**: For future proprietary distribution without GPL requirements, migration from PyQt6 to PySide6 is recommended.

---

## 3. Dependency Inventory & Licenses

| Package | Version Range | Upstream License | Usage in Ghostline |
| :--- | :--- | :--- | :--- |
| **PyQt6** | `>=6.6.0` | GPLv3 / Commercial | Desktop GUI, Fluent 2 widgets, system tray, event loops |
| **Pillow (PIL)** | `>=10.3.0` | Historical Permission Notice (HPND) | Image processing, contrast enhancement, crop |
| **faster-whisper** | `>=1.0.0` | MIT License | Local offline speech transcription engine |
| **CTranslate2** | `>=4.0.0` | MIT License | Fast inference engine for Whisper transformer models |
| **pystray** | `>=0.19.5` | GPLv3 / LGPLv3 | Native Windows system tray icon integration |
| **pywin32** | `>=306` | PSF License | Win32 API calls, DPAPI CryptProtectData, HWND management |
| **pydantic** | `>=2.7.0` | MIT License | Configuration validation and data schemas |
| **requests** | `>=2.31.0` | Apache License 2.0 | HTTP client for local Ollama and BYOK cloud providers |
| **rich** | `>=13.0.0` | MIT License | Terminal diagnostics formatting |
| **pyaudiowpatch** | `>=0.2.12.9` | MIT License | Windows WASAPI loopback audio capture |
| **numpy** | `>=1.24.0` | BSD 3-Clause | Audio signal processing arrays |
| **scipy** | `>=1.10.0` | BSD 3-Clause | Audio resampling and filter functions |
| **mss** | `>=10.0.0` | MIT License | High-speed multi-monitor screen capture |
| **pyqtdarktheme** | `>=2.1.0` | MIT License | Base dark theme palettes and controls |
| **defusedxml** | `>=0.7.1` | Python Software Foundation | Defused XML parsing against XML entity attacks |

---

## 4. Design & Asset Credits

### Microsoft Fluent System Icons
- **Source**: [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons)
- **License**: MIT License (Copyright (c) Microsoft Corporation)
- **Usage**: SVG icons used in Ghostline sidebar navigation, HUD controls, and dialog action buttons.
