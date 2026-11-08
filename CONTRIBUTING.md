# Contributing to Ghostline

Thank you for your interest in contributing to Ghostline! As an open-source, local-first assistive intelligence tool, community contributions help keep Ghostline fast, private, and reliable.

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free experience for everyone. Please be respectful and constructive in all discussions, pull requests, and issue reports.

---

## Getting Started

1. **Fork the Repository:** Fork `Mohammed-Ayyan/GhostLine` to your personal GitHub account.
2. **Clone Your Fork:**
   ```bash
   git clone https://github.com/<your-username>/GhostLine.git
   cd GhostLine
   ```
3. **Set Up Python Environment:**
   Ghostline requires Python 3.10, 3.11, or 3.12 on 64-bit Windows:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install pytest pytest-mock
   ```
4. **Run the App in Development Mode:**
   ```powershell
   python ghostline/app.py --dev
   ```

---

## Architectural & Design Guidelines

- **Zero-Telemetry Rule:** Ghostline must never include telemetry beacons, tracking pixels, or non-consensual network calls. Local inference with Ollama must remain 100% functional with zero internet access.
- **Fluent 2 Dark Tokens:** All UI components must use the design tokens defined in `ghostline/ui/theme/tokens.py`. Avoid hardcoded colors or off-theme fonts.
- **Windows DPAPI Security:** Never store cloud provider credentials in plaintext. Use `ghostline.core.credentials.save_api_key()` to protect tokens using Windows DPAPI.
- **Thread Safety:** Audio streaming, OCR capture, and LLM reasoning must run in background threads, communicating with Qt GUI widgets exclusively via Qt Signals and Slots.

---

## Testing Your Changes

Before submitting a Pull Request, ensure that all automated checks pass:

```powershell
# 1. Run unit and regression tests
python -m pytest tests -q

# 2. Run UI lint checks
python tools/ui_lint.py

# 3. Verify headless self-test
python ghostline/app.py --self-test
```

---

## Submitting a Pull Request

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Commit your changes with clear, descriptive messages:
   ```bash
   git commit -m "Fix(audio): handle WASAPI device disconnect gracefully"
   ```
3. Push to your fork: `git push origin feature/your-feature-name`
4. Open a Pull Request against the `main` branch. Describe the problem your PR solves, how you tested it, and include screenshots if changing UI.
