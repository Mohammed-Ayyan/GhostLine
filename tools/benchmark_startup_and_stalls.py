"""
Benchmark Startup Timeline, Idle CPU/Memory, and UI Thread Stall Watchdog.
Captures baseline metrics BEFORE Run 19 optimizations, and compares Normal vs Weak-PC simulation.
"""

import os
import sys
import time
import threading
import psutil
from pathlib import Path

# Run in test mode without opening audio hardware
os.environ["GHOSTLINE_TEST_MODE"] = "1"
os.environ["GHOSTLINE_E2E"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
from ghostline.config import AppConfig


class UIStallWatchdog:
    """Watchdog that detects UI thread event loop stalls > 100ms."""
    def __init__(self, threshold_ms=100):
        self.threshold_s = threshold_ms / 1000.0
        self.timer = None
        self.last_tick = time.perf_counter()
        self.delays = []
        self.stalls = []
        self.running = False
        self.ui_thread_id = None
        self.watchdog_thread = None

    def start(self, app):
        self.running = True
        self.ui_thread_id = threading.get_ident()
        self.last_tick = time.perf_counter()

        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

    def _on_tick(self):
        now = time.perf_counter()
        delay = (now - self.last_tick) - 0.010
        self.delays.append(max(0.0, delay))
        self.last_tick = now

    def _watchdog_loop(self):
        while self.running:
            time.sleep(0.050)
            now = time.perf_counter()
            elapsed = now - self.last_tick
            if elapsed > self.threshold_s:
                frames = sys._current_frames()
                ui_frame = frames.get(self.ui_thread_id)
                stack_summary = []
                f = ui_frame
                depth = 0
                while f and depth < 6:
                    stack_summary.append(f"{f.f_code.co_filename}:{f.f_lineno} in {f.f_code.co_name}")
                    f = f.f_back
                    depth += 1
                self.stalls.append({
                    "duration_ms": elapsed * 1000,
                    "stack": stack_summary
                })

    def stop(self):
        self.running = False
        if self.timer:
            self.timer.stop()


def measure_startup():
    """Measures startup timeline: import -> window painted -> interactive."""
    t_start = time.perf_counter()

    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    t_import_done = time.perf_counter()

    cfg = AppConfig()
    cfg.first_run_complete = True
    win = QtGhostlineMainWindow(cfg)
    t_constructed = time.perf_counter()

    win.show()
    t_shown = time.perf_counter()

    QApplication.processEvents()
    t_interactive = time.perf_counter()

    win.close()
    return {
        "import_ms": (t_import_done - t_start) * 1000,
        "construct_ms": (t_constructed - t_import_done) * 1000,
        "show_paint_ms": (t_shown - t_constructed) * 1000,
        "interactive_ms": (t_interactive - t_shown) * 1000,
        "total_startup_ms": (t_interactive - t_start) * 1000,
    }


def run_workload_simulation(win, watchdog, duration_s=60):
    """Simulates active user scenario: navigation, resize, live streaming updates."""
    screens = ["dashboard", "model", "audio", "profile", "history", "help", "general"]
    start_t = time.perf_counter()
    step = 0

    while (time.perf_counter() - start_t) < duration_s:
        screen_id = screens[step % len(screens)]
        win.show_screen(screen_id)

        # Simulate resize
        target_w = 960 if (step % 2 == 0) else 1120
        target_h = 680 if (step % 2 == 0) else 780
        win.resize(target_w, target_h)

        # Simulate live thinking ticker update
        if hasattr(win, "_update_live_thinking_ticker"):
            win._update_live_thinking_ticker()

        QApplication.processEvents()
        time.sleep(0.08)
        step += 1


def run_benchmark():
    from ghostline.ui.qt_main_window import QtGhostlineMainWindow
    app = QApplication.instance() or QApplication(sys.argv)
    proc = psutil.Process()

    print("[*] Benchmarking Startup Timeline (Normal Mode)...")
    st_normal = measure_startup()
    print(f"    - Import Time:        {st_normal['import_ms']:.1f} ms")
    print(f"    - Window Construct:   {st_normal['construct_ms']:.1f} ms")
    print(f"    - Show & Paint:       {st_normal['show_paint_ms']:.1f} ms")
    print(f"    - UI Interactive:     {st_normal['interactive_ms']:.1f} ms")
    print(f"    - Total Startup Time: {st_normal['total_startup_ms']:.1f} ms")

    # Measure Idle Baseline
    print("\n[*] Benchmarking Idle (Window Visible, 5 seconds)...")
    cfg = AppConfig()
    cfg.first_run_complete = True
    win = QtGhostlineMainWindow(cfg)
    win.show()
    QApplication.processEvents()

    # Warm-up
    time.sleep(0.5)
    cpu_samples = []
    for _ in range(5):
        QApplication.processEvents()
        time.sleep(1.0)
        cpu_samples.append(proc.cpu_percent(interval=None))

    rss_mb = proc.memory_info().rss / (1024 * 1024)
    avg_cpu = sum(cpu_samples) / len(cpu_samples)
    peak_cpu = max(cpu_samples)
    print(f"    - Idle Avg CPU: {avg_cpu:.2f}% (Peak: {peak_cpu:.2f}%)")
    print(f"    - Working Set (RAM): {rss_mb:.2f} MB")

    # Measure UI Stall Watchdog (Normal Mode)
    print("\n[*] Running UI Stall Watchdog (Normal Mode, 10s scenario)...")
    watchdog = UIStallWatchdog(threshold_ms=100)
    watchdog.start(app)
    run_workload_simulation(win, watchdog, duration_s=10)
    watchdog.stop()

    delays_ms = [d * 1000 for d in watchdog.delays]
    delays_ms.sort()
    p50 = delays_ms[int(len(delays_ms) * 0.50)] if delays_ms else 0.0
    p95 = delays_ms[int(len(delays_ms) * 0.95)] if delays_ms else 0.0
    max_d = max(delays_ms) if delays_ms else 0.0

    print(f"    - Scheduling Delay p50: {p50:.1f} ms | p95: {p95:.1f} ms | max: {max_d:.1f} ms")
    print(f"    - Stalls > 100ms detected: {len(watchdog.stalls)}")
    for s in watchdog.stalls[:5]:
        print(f"      * Stall {s['duration_ms']:.1f} ms at {s['stack'][0] if s['stack'] else 'unknown'}")

    win.close()

    # Weak-PC Simulation
    print("\n[*] Benchmarking Weak-PC Simulation (Affinity: 2 Cores, BELOW_NORMAL priority)...")
    try:
        proc.cpu_affinity([0, 1])
        proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as e:
        print(f"    [!] Could not set affinity/priority: {e}")

    # Launch 2 background CPU burners (~50% load on those 2 cores)
    burner_stop = False
    def _burner():
        while not burner_stop:
            for _ in range(500000):
                pass
            time.sleep(0.010)

    t_b1 = threading.Thread(target=_burner, daemon=True)
    t_b2 = threading.Thread(target=_burner, daemon=True)
    t_b1.start()
    t_b2.start()

    st_weak = measure_startup()
    print(f"    - Weak PC Total Startup: {st_weak['total_startup_ms']:.1f} ms")

    win_weak = QtGhostlineMainWindow(cfg)
    win_weak.show()
    QApplication.processEvents()

    watchdog_weak = UIStallWatchdog(threshold_ms=100)
    watchdog_weak.start(app)
    run_workload_simulation(win_weak, watchdog_weak, duration_s=10)
    watchdog_weak.stop()

    burner_stop = True
    win_weak.close()

    delays_weak = [d * 1000 for d in watchdog_weak.delays]
    delays_weak.sort()
    p50_w = delays_weak[int(len(delays_weak) * 0.50)] if delays_weak else 0.0
    p95_w = delays_weak[int(len(delays_weak) * 0.95)] if delays_weak else 0.0
    max_d_w = max(delays_weak) if delays_weak else 0.0

    print(f"    - Weak PC Delay p50: {p50_w:.1f} ms | p95: {p95_w:.1f} ms | max: {max_d_w:.1f} ms")
    print(f"    - Weak PC Stalls > 100ms: {len(watchdog_weak.stalls)}")

    # Reset affinity
    try:
        proc.cpu_affinity(list(range(psutil.cpu_count(logical=True))))
        proc.nice(psutil.NORMAL_PRIORITY_CLASS)
    except Exception:
        pass

    # Save results
    import json
    target_filename = "after_perf.json" if "--after" in sys.argv else "baseline_perf.json"
    data = {
        "startup_normal": st_normal,
        "startup_weak": st_weak,
        "idle_cpu_avg": avg_cpu,
        "idle_cpu_peak": peak_cpu,
        "working_set_mb": rss_mb,
        "delays_normal": {"p50": p50, "p95": p95, "max": max_d, "stalls_count": len(watchdog.stalls)},
        "delays_weak": {"p50": p50_w, "p95": p95_w, "max": max_d_w, "stalls_count": len(watchdog_weak.stalls)},
        "sample_stalls": watchdog.stalls[:10] + watchdog_weak.stalls[:10]
    }
    (ROOT / "reports" / "run19" / target_filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\n[+] Benchmark completed and written to reports/run19/{target_filename}")


if __name__ == "__main__":
    run_benchmark()
