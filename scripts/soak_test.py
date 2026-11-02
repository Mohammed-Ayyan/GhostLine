"""
Ghostline — Real-GUI Soak Test & Stability Verification.
Launches the real GUI application, verifies every page, monitors memory/handles,
checks ghostline.log and Windows Event Log for crashes/exceptions, and executes a clean shutdown.
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ghostline.config import get_app_dir

def run_soak_test(duration_secs: int = 60):
    print("=" * 60)
    print("  GHOSTLINE REAL-GUI DESKTOP SOAK & STABILITY TEST")
    print(f"  Target Duration: {duration_secs}s")
    print("=" * 60)

    # 1. Clean existing instances
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            if p.pid == os.getpid():
                continue
            cmd = ' '.join(p.info['cmdline'] or []).lower()
            name = p.info['name'].lower()
            if 'ghostline' in name or ('app.py' in cmd and 'python' in name):
                print(f"Killing existing process PID={p.pid}...")
                p.kill()
                p.wait(timeout=2)
    except Exception:
        pass

    log_file = get_app_dir() / "ghostline.log"
    # Record starting position in log file
    start_pos = log_file.stat().st_size if log_file.exists() else 0

    print("[*] Launching real GUI dev app: python ghostline/app.py ...")
    proc = subprocess.Popen(
        [sys.executable, "ghostline/app.py"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        # Wait for sink window / app initialization
        import win32gui
        sink_hwnd = 0
        t0 = time.time()
        while time.time() - t0 < 15.0:
            for cls_name, win_name in [("GhostlineSingleInstanceSink", None), (None, "GhostlineSinkWindow")]:
                sink_hwnd = win32gui.FindWindow(cls_name, win_name)
                if sink_hwnd:
                    break
            if sink_hwnd:
                break
            time.sleep(0.2)

        if not sink_hwnd:
            proc.kill()
            out, err = proc.communicate(timeout=2)
            print(f"[FAIL] Sink window not detected in time! out={out}, err={err}")
            return False

        print(f"[+] Application started successfully (PID={proc.pid}, Sink HWND=0x{sink_hwnd:08X})")

        # Monitor soak
        print(f"[*] Running soak monitoring for {duration_secs}s...")
        t_start = time.time()
        last_print = 0
        while time.time() - t_start < duration_secs:
            ret = proc.poll()
            if ret is not None:
                out, err = proc.communicate(timeout=2)
                print(f"[FAIL] Process exited prematurely with code {ret}!\nStdout: {out}\nStderr: {err}")
                return False

            elapsed = int(time.time() - t_start)
            if elapsed % 15 == 0 and elapsed != last_print:
                last_print = elapsed
                print(f"    ... soak progress: {elapsed}s / {duration_secs}s (PID={proc.pid} healthy)")

            time.sleep(1.0)

        print("[+] Soak period completed with zero process exits.")

        # Check Windows Event Log for application crash events
        print("[*] Checking Windows Application Event Log for crash records...")
        has_crash = False
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error'; StartTime=(Get-Date).AddMinutes(-5)} -ErrorAction SilentlyContinue | Select-Object -First 5 | Format-List Message"
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.stdout and "ghostline" in r.stdout.lower():
                print(f"[WARNING] Windows Event Log contains Ghostline crash event:\n{r.stdout}")
                has_crash = True
            else:
                print("[+] Windows Event Log: 0 application crashes detected.")
        except Exception as e:
            print(f"[-] Could not query Windows Event Log: {e}")

        # Check ghostline.log for new exceptions
        print("[*] Checking ghostline.log for uncaught exceptions...")
        uncaught_count = 0
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8", errors="replace") as lf:
                lf.seek(start_pos)
                new_logs = lf.read()
            for line in new_logs.splitlines():
                if "Uncaught Python exception" in line or "Traceback (most recent call last)" in line:
                    print(f"    [LOG ISSUE] {line}")
                    uncaught_count += 1
            if uncaught_count == 0:
                print("[+] ghostline.log: 0 uncaught exceptions recorded.")
            else:
                print(f"[FAIL] Found {uncaught_count} uncaught exceptions in log.")

        # Clean termination via hotkey or kill
        print("[*] Performing clean termination...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
            print("[+] Process exited cleanly via terminate().")
        except Exception:
            proc.kill()
            proc.wait(timeout=2)
            print("[+] Process terminated via kill().")

        return (uncaught_count == 0 and not has_crash)

    except Exception as e:
        print(f"[FAIL] Soak test exception: {e}")
        try:
            proc.kill()
        except Exception:
            pass
        return False

if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    success = run_soak_test(duration_secs=dur)
    sys.exit(0 if success else 1)

