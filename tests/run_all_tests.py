import os
import sys
import glob
import time
import subprocess
from pathlib import Path

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

def run_tests():
    print("=" * 65)
    print("  Ghostline Automated Verification & Regression Suite")
    print("=" * 65)

    test_files = sorted(glob.glob(str(app_root / "tests" / "test_*.py")))
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    start_time = time.time()
    
    for test_file in test_files:
        name = Path(test_file).name
        print(f"\n[RUNNING SUITE] {name}...")
        
        # Run each test suite in an isolated Python process to preserve clean Win32/GUI handles
        cmd = [sys.executable, "-m", "unittest", f"tests.{Path(test_file).stem}"]
        res = subprocess.run(
            cmd,
            cwd=str(app_root),
            capture_output=True,
            text=True
        )
        
        output = res.stderr or res.stdout
        # Parse test counts
        # e.g., "Ran 4 tests in 3.123s"
        lines = output.strip().splitlines()
        suite_tests = 0
        for line in lines:
            if line.startswith("Ran ") and " test" in line:
                try:
                    suite_tests = int(line.split()[1])
                except Exception:
                    suite_tests = 1
        
        total_tests += suite_tests
        
        if res.returncode == 0:
            print(f"  [+] {name} PASSED ({suite_tests} tests)")
        else:
            print(f"  [!] {name} FAILED (Exit {res.returncode})")
            print("-" * 50)
            print(output.strip())
            print("-" * 50)
            if "FAILED (failures=" in output:
                total_failures += 1
            if "FAILED (errors=" in output:
                total_errors += 1
            if total_failures == 0 and total_errors == 0:
                total_failures += 1

    duration = time.time() - start_time
    is_success = (total_failures == 0 and total_errors == 0)
    
    print("\n" + "=" * 65)
    print(f"Suites Executed: {len(test_files)}")
    print(f"Total Tests:    {total_tests}")
    print(f"Failures:       {total_failures}")
    print(f"Errors:         {total_errors}")
    print(f"Elapsed Time:   {duration:.2f}s")
    print(f"Status:         {'PASSED (100% Offline Autonomy Verified)' if is_success else 'FAILED'}")
    print("=" * 65)
    
    return 0 if is_success else 1

if __name__ == "__main__":
    sys.exit(run_tests())
