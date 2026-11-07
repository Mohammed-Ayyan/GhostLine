"""
Win32 GUI Automation & Inspection Harness for Ghostline E2E Tests.
Drives native Windows HWNDs, injects hotkeys via SendInput and Win32 PostMessage IPC,
samples overlay visibility, and guards foreground window focus.
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import subprocess

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Virtual key codes
VK_MENU = 0x12       # Alt key
VK_SHIFT = 0x10      # Shift key
VK_CONTROL = 0x11    # Ctrl key
VK_OEM_2 = 0xBF      # '/' key
VK_OEM_5 = 0xDC      # '\' key

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
SW_SHOWNOACTIVATE = 4

user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT

WM_GHOSTLINE_WAKEUP = user32.RegisterWindowMessageW("GhostlineWakeUpMsg")
WM_GHOSTLINE_SOLVE = user32.RegisterWindowMessageW("GhostlineSolveMsg")
WM_GHOSTLINE_RELOAD_HOTKEYS = user32.RegisterWindowMessageW("GhostlineReloadHotkeysMsg")
WM_GHOSTLINE_AUDIO_TOGGLE = user32.RegisterWindowMessageW("GhostlineAudioToggleMsg")


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


def send_key_event(vk_code: int, is_up: bool = False):
    """Synthesizes a single key press or release event via SendInput."""
    flags = KEYEVENTF_KEYUP if is_up else 0
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk_code
    inp.union.ki.wScan = 0
    inp.union.ki.dwFlags = flags
    inp.union.ki.time = 0
    inp.union.ki.dwExtraInfo = 0
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def send_hotkey_chord(keys: List[int], hold_duration_sec: float = 0.08):
    """Sends a hotkey combination (e.g. [VK_MENU, VK_OEM_2]) via SendInput."""
    for k in keys:
        send_key_event(k, is_up=False)
        time.sleep(0.01)
    time.sleep(hold_duration_sec)
    for k in reversed(keys):
        send_key_event(k, is_up=True)
        time.sleep(0.01)


def get_foreground_hwnd() -> int:
    """Returns the HWND of the current active foreground window."""
    return user32.GetForegroundWindow()


def is_window_visible(hwnd: Optional[int]) -> bool:
    """Checks if the given HWND exists and is currently visible."""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    return bool(user32.IsWindowVisible(hwnd))


def find_windows_for_pid(pid: int) -> List[Tuple[int, str, str]]:
    """Returns list of (hwnd, title, class_name) for given process ID."""
    results = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_proc(hwnd, lparam):
        if not user32.IsWindow(hwnd):
            return True
        w_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(w_pid))
        if w_pid.value == pid:
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value

            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            cls_name = class_buf.value
            results.append((hwnd, title, cls_name))
        return True

    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
    return results


def find_ghostline_hwnds(pid: Optional[int] = None) -> Dict[str, Optional[int]]:
    """Identifies Main Window, HUD Window, Live Panel, and Sink HWNDs."""
    mapping = {"main": None, "hud": None, "live": None, "sink": None}

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_proc(hwnd, lparam):
        if not user32.IsWindow(hwnd):
            return True
        len_t = user32.GetWindowTextLengthW(hwnd)
        buf_t = ctypes.create_unicode_buffer(len_t + 1)
        user32.GetWindowTextW(hwnd, buf_t, len_t + 1)
        buf_c = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf_c, 256)
        t = buf_t.value.lower()
        c = buf_c.value.lower()

        if pid is not None:
            w_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(w_pid))
            if w_pid.value != pid and "ghostline" not in t and "ghostlinesingleinstancesink" not in c:
                return True

        if "ghostline hud" in t:
            mapping["hud"] = hwnd
        elif "ghostline live" in t:
            mapping["live"] = hwnd
        elif "ghostline" in t and "sink" not in t and "hud" not in t and "live" not in t:
            mapping["main"] = hwnd
        elif "ghostlinesingleinstancesink" in c or ("sink" in t and "ghostline" in t):
            mapping["sink"] = hwnd
        return True

    cb = WNDENUMPROC(enum_proc)
    user32.EnumWindows(cb, 0)
    return mapping


def sample_hud_visibility_log(
    pid: int,
    duration_sec: float = 3.5,
    interval_sec: float = 0.05
) -> List[Tuple[float, bool, int]]:
    """Samples HUD visibility and foreground window at high frequency."""
    hwnds = find_ghostline_hwnds(pid)
    hud_hwnd = hwnds.get("hud")
    samples = []
    start_t = time.time()

    while time.time() - start_t < duration_sec:
        cur_t = time.time() - start_t
        vis = is_window_visible(hud_hwnd)
        fg = get_foreground_hwnd()
        samples.append((cur_t, vis, fg))
        time.sleep(interval_sec)

    return samples


def trigger_ghostline_solve(pid: int, timeout_sec: float = 4.0):
    """Triggers screen solve via Win32 IPC or hotkey fallback."""
    start_t = time.time()
    sink = None
    while time.time() - start_t < timeout_sec:
        hwnds = find_ghostline_hwnds(pid)
        sink = hwnds.get("sink")
        if sink and user32.IsWindow(sink):
            break
        time.sleep(0.1)

    if sink and user32.IsWindow(sink):
        user32.PostMessageW(sink, WM_GHOSTLINE_SOLVE, 0, 0)
    else:
        send_hotkey_chord([VK_MENU, VK_OEM_2])


def trigger_ghostline_audio_toggle(pid: int, timeout_sec: float = 4.0):
    """Triggers live audio toggle via Win32 IPC or hotkey fallback."""
    start_t = time.time()
    sink = None
    while time.time() - start_t < timeout_sec:
        hwnds = find_ghostline_hwnds(pid)
        sink = hwnds.get("sink")
        if sink and user32.IsWindow(sink):
            break
        time.sleep(0.1)

    if sink and user32.IsWindow(sink):
        user32.PostMessageW(sink, WM_GHOSTLINE_AUDIO_TOGGLE, 0, 0)
    else:
        send_hotkey_chord([VK_MENU, ord('L')])


class GhostlineProcess:
    """Manages test subprocess lifecycle with cleanup."""
    def __init__(self, proc: subprocess.Popen, test_dir: Path, stdout_file=None, stderr_file=None):
        self.proc = proc
        self.test_dir = test_dir
        self.pid = proc.pid
        self.stdout_file = stdout_file
        self.stderr_file = stderr_file

    def poll(self):
        return self.proc.poll()

    def terminate(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3.0)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        finally:
            if self.stdout_file:
                try:
                    self.stdout_file.close()
                except Exception:
                    pass
            if self.stderr_file:
                try:
                    self.stderr_file.close()
                except Exception:
                    pass


def launch_ghostline_test(
    test_dir: Path,
    config_overrides: Optional[Dict[str, Any]] = None,
    extra_env: Optional[Dict[str, str]] = None,
    wait_visible_sec: float = 8.0,
    exe_path: Optional[str] = None
) -> GhostlineProcess:
    """Launches Ghostline with an isolated test profile and fake provider."""
    test_dir.mkdir(parents=True, exist_ok=True)

    # Write initial config.json in test AppData directory
    config_data = {
        "provider": "ollama",
        "model_name": "phi3:mini",
        "ollama_base_url": "http://127.0.0.1:11434",
        "show_hud_on_solve": True,
        "show_tray_icon": True,
        "minimize_to_tray": True,
        "start_minimized": False,
        "first_run_complete": True
    }
    if config_overrides:
        config_data.update(config_overrides)

    import json
    with open(test_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    ghost_app_dir = test_dir / "Ghostline"
    ghost_app_dir.mkdir(parents=True, exist_ok=True)
    with open(ghost_app_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    env = dict(os.environ)
    env["APPDATA"] = str(test_dir.resolve())
    env["GHOSTLINE_E2E"] = "1"
    env["GHOSTLINE_TEST_DIR"] = str(test_dir.resolve())
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)

    exe_path = exe_path or os.environ.get("GHOSTLINE_EXE_PATH")
    if exe_path and os.path.exists(exe_path):
        cmd = [exe_path]
    else:
        cmd = [sys.executable, "-u", "-m", "ghostline.app"]

    stdout_path = test_dir / "stdout.log"
    stderr_path = test_dir / "stderr.log"
    stdout_f = open(stdout_path, "w", encoding="utf-8")
    stderr_f = open(stderr_path, "w", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        cwd=str(Path(".").resolve()),
        env=env,
        stdout=stdout_f,
        stderr=stderr_f,
        text=True
    )

    ghost_proc = GhostlineProcess(proc, test_dir, stdout_file=stdout_f, stderr_file=stderr_f)

    # Wait for process initialization and readiness (wait until sink and windows exist)
    start_wait = time.time()
    max_wait = max(wait_visible_sec, 25.0)
    while time.time() - start_wait < max_wait:
        if proc.poll() is not None:
            err_content = stderr_path.read_text(encoding="utf-8", errors="ignore") if stderr_path.exists() else ""
            raise RuntimeError(f"Ghostline terminated prematurely (code {proc.returncode}):\n{err_content}")
        hw = find_ghostline_hwnds(proc.pid)
        if hw.get("sink") and (hw.get("main") or hw.get("hud")):
            time.sleep(0.4)
            break
        time.sleep(0.2)

    return ghost_proc
