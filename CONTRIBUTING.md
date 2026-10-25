# Contributing to Ghostline

Thank you for your interest in contributing to **Ghostline**! We welcome bug reports, documentation improvements, model prompt optimizations, and platform stability enhancements.

---

## Philosophy & Guiding Principles

1. **100% Offline Autonomy:** Under no circumstances may code introduce remote API calls, analytics, telemetry, or external network dependencies. The only permissible network socket is loopback (`127.0.0.1`) to the local Ollama daemon.
2. **Handle Hygiene & Thread Safety:** All Win32 resources (HWNDs, mutexes, hooks) must be cleanly unregistered and closed. Long-running or blocking work (HTTP calls, subprocesses, model downloads) must never block the main Tkinter thread.
3. **Deterministic Verification:** Mathematical reasoning, simple linear equations, and option label validation must maintain deterministic consistency without relying solely on generative token sampling.
4. **Restrained Minimalism:** UI additions must respect the minimalist design tokens (Zinc/Slate surfaces, subtle 1px borders, restrained Sky Cyan accent). Avoid visual clutter.

---

## Development Environment Setup

1. **Prerequisites:**
   - Windows 10 (20H2+) or Windows 11 (64-bit)
   - Python 3.10, 3.11, or 3.12
   - [Ollama](https://ollama.com) installed and serving locally (`ollama serve`)
   - Recommended model: `ollama pull phi3:mini`

2. **Clone and Install:**
   ```powershell
   git clone https://github.com/Mohammed-Ayyan/GhostLine.git
   cd GhostLine
   python -m pip install -r requirements.txt
   ```

3. **Verify OCR Binary:**
   Ensure `bin/win_ocr.exe` exists. If missing, compile it via:
   ```cmd
   C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:exe /out:bin\win_ocr.exe bin\src\WinOcr.cs
   ```

4. **Verify Test Suite:**
   Run the full verification suite before making changes:
   ```powershell
   python tests/run_all_tests.py
   ```

5. **Launch Application in Dev Mode:**
   ```powershell
   .\run_dev.bat
   ```

---

## Testing & Quality Assurance

All pull requests must pass the complete automated test suite (15 suites, 103 tests) without regressions:

```powershell
# Run all 103 automated tests across 15 test suites
python tests/run_all_tests.py

# Run accuracy benchmarks against dev and heldout sets
python evaluation/evaluator.py --dataset dev
python evaluation/evaluator.py --dataset heldout
```

### Writing New Tests
- Place tests under `tests/test_<feature>.py`.
- Ensure tests cleanly release all Win32 mutexes, sockets, and window handles in `tearDown()`.
- Never leave orphaned background processes running.

---

## Pull Request Guidelines

1. **Create a Topic Branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Keep Commits Focused:**
   Write clear, concise commit messages following standard conventions:
   `fix(ocr): improve option delimiter handling with leading whitespace`
3. **Document Changes:**
   Update relevant sections of `README.md` and `docs/` if changing user-facing settings, flags, or shortcuts.
4. **Submit PR:**
   Provide a detailed description of the problem solved, testing methodology, and any relevant logs.
