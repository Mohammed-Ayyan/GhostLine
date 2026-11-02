# Phase B — Baseline Test Run Report

**Date & Time**: 2026-11-01 18:45:10  
**Test Command**: `python -m unittest discover -s tests -p "test_*.py"`  
**Full Raw Output Saved To**: `reports/baseline_tests.txt`  
**Total Tests Discovered & Executed**: 359 tests in 112.44s  

---

## 1. Baseline Summary

| Status | Count | Notes |
| :--- | :--- | :--- |
| **PASSED** | 356 | All core logic, OCR, BYOK providers, audio capture, HUD geometry, and pipeline tracers |
| **SKIPPED** | 2 | Gated environment tests (display / hardware tests requiring specific display adapters) |
| **FAILED** | 1 | Pre-existing lifecycle sub-process test (`test_startup_lifecycle.py`) |

---

## 2. Failure Details

### Failure 1: `test_repeat_launch_stability` (`test_startup_lifecycle.py:126`)
- **Failure**: `AssertionError: Iteration 1: Sink window not found in time! Poll: 1, stdout: , stderr:`
- **Root Cause**: `test_startup_lifecycle.py` invokes `subprocess.Popen([sys.executable, "ghostline/app.py"])` five times in a loop. When executed within the full test suite run, the sub-process terminates before the Win32 message loop window class `GhostlineSingleInstanceSink` can be polled within the test's hardcoded timeout window.
- **Classification**: Pre-existing baseline test failure.

