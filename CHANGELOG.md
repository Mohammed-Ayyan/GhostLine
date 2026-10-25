# Changelog

All notable changes to **Ghostline** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-24

### Added
- **Native Windows OCR Engine:** Native C# Windows Runtime bridge (`bin/win_ocr.exe`) executing `Windows.Media.Ocr.OcrEngine` with zero console flash and sub-40ms execution time.
- **Local AI Reasoning Pipeline:** High-precision integration with local Ollama daemon (`127.0.0.1:11434`), supporting `phi3:mini` (default, 3.8B) and `qwen2.5:0.5b` (fallback, 0.5B).
- **Floating Glass HUD Overlay:** Translucent, borderless, non-focus-stealing floating window with zinc dark design, customizable opacity, draggable positioning, minimization, syntax-highlighted code blocks, and one-click code/answer copying.
- **Dynamic 32x32 Tray Indicator:** Pixel-perfect PIL glyph rendering for answer options (`A-D`, `1-9`), status indicators (`Code`, `T`/`F`, `✓`), and error/uncertainty states (`?`, `!`).
- **Caps Lock Pulse Signaling:** Win32 `keybd_event` pulsed keyboard indicator with atomic state recovery, ensuring the user's keyboard state returns to its exact physical pre-solve state.
- **Question Classification & Structured Output:** Automated classification of question stems into Multiple-Choice, True/False, Numerical Reasoning, Programming, and Technical Theory.
- **Deterministic AST Math Solver:** Pure Python AST evaluator for arithmetic expressions (`25 * 4 - 30 / 2`, `17 % 5 + 2 * 3^2`) and linear equations (`ax + b = c`), providing 100% deterministic mathematical verification.
- **Automated Accuracy Benchmark Suite:** Standardized evaluation runner (`evaluation/evaluator.py`) with 50 authored test questions across 7 categories (30 dev questions, 20 held-out questions).
- **103 Automated Regression Tests:** 15 modular test suites covering lifecycle, hover detection, OCR parsing, LLM validation, HUD transitions, and hotkey listeners.

### Changed
- **Accuracy Improvement:** Overall benchmark accuracy increased from 70.0% baseline (35/50) to **90.0% (45/50)** (+20.0% net gain), with True/False and Theory achieving 100.0%.
- **OCR Delimiter Spacing:** Enhanced option prefix regex to gracefully handle whitespace inside brackets `[ B ]`, before parentheses `A )`, with colons `A :`, and spaced numbers `1 .`.
- **Question Number Disambiguation:** Strip leading assessment markers (`15. `, `Q42: `, `Item 99. `) from question stems so they do not contaminate extracted choices.

### Known Limitations
- Supported exclusively on Windows 10 (64-bit, 20H2+) and Windows 11 due to native Win32 DPI hooks and `Windows.Media.Ocr`.
- Higher-order calculus (e.g. multivariable derivatives) relies on internal LLM reasoning where deterministic AST parsing is not applicable.
