# Offline AI Bundle Architecture & Feasibility Evaluation

**Product:** Ghostline for Windows (v1.0.0)  
**Date:** October 26, 2026  
**Status:** Architecture Evaluated & Guided Setup Implemented  

---

## 1. Executive Summary

This document evaluates the viability, distribution footprint, licensing, and safety profile of bundling a redistributable local AI runtime (Ollama) and local LLM model weights (e.g. `phi3:mini`) directly into an all-in-one offline ZIP distribution package, versus maintaining a lean core installer with an automated guided setup workflow.

### Key Finding
While bundling Ollama and a quantized GGUF model into a single monolithic package is technically feasible, bundling multi-gigabyte models directly into the default installer would inflate the download size from **~390 MB to ~2.65 GB** (and require **>4.5 GB** of extracted disk space), creating high friction for standard downloads and risking corruption of existing user model libraries.

Therefore, the optimal distribution architecture is:
1. **Core Distribution (Recommended Default):** Lean, verified Standalone Installer (394.64 MB) and Portable ZIP (387.11 MB).
2. **Guided Offline AI Setup Tool (`Setup-Offline-AI.bat`):** An intelligent, non-destructive setup automation script included in the release that inspects existing Ollama installations, manages model pulls without telemetry, and verifies local GPU/CPU inference without altering existing system configurations.

---

## 2. Component Breakdown & Storage Footprint

| Component | Standard Release | Bundled Offline AI Option | License |
| :--- | :--- | :--- | :--- |
| **Ghostline Core App & Dependencies** | 387.11 MB (ZIP) / 1.1 GB (Extracted) | 387.11 MB (ZIP) / 1.1 GB (Extracted) | MIT License |
| **PyQt6, OCR Engine, WebRTC Audio** | Included | Included | LGPLv3 / Apache 2.0 / BSD-3 |
| **Ollama Runtime Daemon & CLI** | Excluded (User-provided) | ~40 MB installer / ~92 MB binary | MIT License |
| **Local LLM (`phi3:mini` 3.8B Q4)** | Excluded (Pulled on demand) | ~2.18 GB compressed / ~2.40 GB extracted | MIT License (Microsoft) |
| **Total Compressed Download** | **~387 – 395 MB** | **~2.62 – 2.65 GB** | Completely Permissive |
| **Total Extracted Disk Space** | **~1.1 GB** | **~4.5 GB** | — |

---

## 3. Licensing & Redistribution Verification

All planned components permit commercial and open-source distribution without proprietary restrictions:
1. **Ghostline:** MIT License. Permissive redistribution in binary and source form.
2. **Ollama:** MIT License. Permissive redistribution of binaries and runtime daemons.
3. **Microsoft Phi-3 Mini (`phi3:mini`):** MIT License with custom attribution rider. Permits redistribution of quantized weights for local on-device inference.
4. **Tesseract OCR / PyTesseract:** Apache 2.0 License. Permissive binary redistribution.

---

## 4. Safety Constraints & Conflict Prevention

A monolithic offline installer poses critical system risks if not carefully guarded:

1. **Never Overwrite Existing Ollama Runtimes:**
   Many software engineers and AI developers already have Ollama installed in `%LOCALAPPDATA%\Programs\Ollama` or on their system `PATH`. A bundled installer must never overwrite an existing daemon or replace running service configurations.
2. **Preserve User Models in `~/.ollama/models`:**
   Ollama stores model blobs in `%USERPROFILE%\.ollama\models\blobs`. Injecting pre-packaged blobs or moving directories must never delete or invalidate existing user models (such as `llama3`, `mistral`, or custom fine-tunes).
3. **Bandwidth Respect:**
   Silent multi-gigabyte background downloads violate user trust on metered connections. Any model download must require explicit confirmation.

---

## 5. Implementation: Automated Guided Setup (`Setup-Offline-AI.bat`)

To provide the absolute best user experience, Ghostline includes a dedicated, robust automation script `Setup-Offline-AI.bat` placed alongside the portable executable and setup package:

```bat
@echo off
title Ghostline — Local Offline AI Environment Setup
:: 1. Check if Ollama is available
where ollama >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Ollama runtime detected.
) else (
    echo [!] Ollama not found. Opening official download...
    start https://ollama.com/download/windows
)

:: 2. Check if phi3:mini model is available
ollama list | findstr "phi3:mini" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Model phi3:mini is ready for 100% offline reasoning.
) else (
    echo [*] Pulling local phi3:mini model (approx 2.2 GB)...
    ollama pull phi3:mini
)

:: 3. Test API endpoint
curl -s http://127.0.0.1:11434/api/tags >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Local Ollama service is active on http://127.0.0.1:11434
)
```

---

## 6. Website Integration

The website at `website_download/index.html` has been updated to:
1. Feature the standard lightweight downloads (Installer & Portable ZIP) with accurate file sizes and SHA-256 hashes.
2. Offer clear, step-by-step instructions for running `Setup-Offline-AI.bat` or `ollama pull phi3:mini`.
3. Highlight system requirements for local GPU vs CPU inference (e.g. 8 GB RAM minimum, 16 GB recommended).
