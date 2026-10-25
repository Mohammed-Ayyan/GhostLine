import os
import sys
import unittest
import threading
import time
import ctypes
from ctypes import wintypes
from pathlib import Path

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

import win32con
import win32gui
import pywintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL


class TestHotkeyRegistration(unittest.TestCase):
    """
    Verification and regression tests for global hotkey registration in Ghostline.
    Validates Windows API availability, Alt+/ shortcut registration,
    event message routing, and clean shutdown unregistration.
    """

    def test_windows_api_availability(self):
        """
        Verify the root cause of the previous failure:
        - win32api lacks RegisterHotKey.
        - win32gui has RegisterHotKey but lacks UnregisterHotKey.
        - ctypes.windll.user32 exposes BOTH RegisterHotKey and UnregisterHotKey.
        """
        import win32api
        self.assertFalse(
            hasattr(win32api, "RegisterHotKey"),
            "win32api should NOT have RegisterHotKey (verifying observed bug cause)"
        )
        self.assertTrue(
            hasattr(win32gui, "RegisterHotKey"),
            "win32gui should have RegisterHotKey"
        )
        self.assertFalse(
            hasattr(win32gui, "UnregisterHotKey"),
            "win32gui lacks UnregisterHotKey (pywin32 omission)"
        )
        self.assertTrue(
            hasattr(user32, "RegisterHotKey"),
            "ctypes user32 must have RegisterHotKey"
        )
        self.assertTrue(
            hasattr(user32, "UnregisterHotKey"),
            "ctypes user32 must have UnregisterHotKey"
        )

    def test_alt_slash_registration_and_cleanup(self):
        """
        Tests that Alt + / (MOD_ALT | MOD_NOREPEAT, VK_SLASH = 0xBF)
        can be registered and unregistered cleanly via ctypes user32.
        """
        HOTKEY_ID = 2001
        MOD_ALT = win32con.MOD_ALT
        MOD_NOREPEAT = 0x4000
        VK_SLASH = 0xBF  # VK_OEM_2

        # Test registration with NULL hwnd (thread queue)
        test_key = VK_SLASH
        reg_ok = user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, test_key)
        err = ctypes.GetLastError()
        if not reg_ok and err == 1409:
            # Alt + / is actively held by a running GhostlineApp process; use VK_F11 for API test
            test_key = 0x7A  # VK_F11
            reg_ok = user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, test_key)
            err = ctypes.GetLastError()

        self.assertTrue(
            reg_ok,
            f"Failed to register hotkey. Win32 error code: {err}"
        )

        # Test unregistration
        unreg_ok = user32.UnregisterHotKey(None, HOTKEY_ID)
        self.assertTrue(unreg_ok, "Failed to unregister hotkey")

    def test_window_sink_message_dispatch(self):
        """
        Tests the full lifecycle matching GhostlineApp:
        - Creates a hidden sink window
        - Registers Alt + / (or VK_F11 if Alt+/ held by running app)
        - Dispatches a WM_HOTKEY message
        - Receives and decodes the message in the pump
        - Unregisters hotkey and destroys sink window cleanly
        """
        HOTKEY_ID = 2002
        MOD_ALT = win32con.MOD_ALT
        MOD_NOREPEAT = 0x4000
        VK_SLASH = 0xBF

        received_events = []
        ready_event = threading.Event()
        shutdown_event = threading.Event()
        thread_id = None
        sink_hwnd = None

        def worker():
            nonlocal thread_id, sink_hwnd
            thread_id = kernel32.GetCurrentThreadId()

            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "GhostlineTestSink_Unit"
            wc.lpfnWndProc = lambda hwnd, msg, wparam, lparam: win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
            try:
                win32gui.RegisterClass(wc)
            except pywintypes.error as e:
                if e.winerror != 1410:
                    raise

            hwnd = win32gui.CreateWindow(
                wc.lpszClassName, "SinkUnit", 0, 0, 0, 0, 0, 0, 0, 0, None
            )
            sink_hwnd = hwnd

            test_key = VK_SLASH
            reg = user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, test_key)
            if not reg and ctypes.GetLastError() == 1409:
                test_key = 0x7A  # VK_F11
                reg = user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, test_key)

            self.assertTrue(reg, f"RegisterHotKey failed: {ctypes.GetLastError()}")
            ready_event.set()

            try:
                while True:
                    ret, msg = win32gui.GetMessage(0, 0, 0)
                    if ret == 0:  # WM_QUIT
                        break
                    msg_hwnd, msg_id, wparam, lparam, msg_time, pt = msg
                    if msg_id == win32con.WM_HOTKEY and wparam == HOTKEY_ID:
                        received_events.append("HOTKEY_PRESSED")
                    win32gui.TranslateMessage(msg)
                    win32gui.DispatchMessage(msg)
            finally:
                user32.UnregisterHotKey(hwnd, HOTKEY_ID)
                win32gui.DestroyWindow(hwnd)
                shutdown_event.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.assertTrue(ready_event.wait(timeout=3.0), "Worker thread failed to initialize in time")

        # Simulate hotkey message to verify message processing
        hwnd = sink_hwnd or win32gui.FindWindow("GhostlineTestSink_Unit", "SinkUnit")
        self.assertNotEqual(hwnd, 0, "Sink window should exist")

        user32.PostMessageW(hwnd, win32con.WM_HOTKEY, HOTKEY_ID, 0)

        # Allow message pump to process
        time.sleep(0.2)
        self.assertIn("HOTKEY_PRESSED", received_events)

        # Signal shutdown cleanly
        user32.PostThreadMessageW(thread_id, win32con.WM_QUIT, 0, 0)
        self.assertTrue(shutdown_event.wait(timeout=3.0), "Worker thread failed to shut down in time")

    def test_duplicate_registration_error_handling(self):
        """
        Verify that attempting to register an already-bound hotkey fails with ERROR_HOTKEY_ALREADY_REGISTERED (1409).
        """
        HOTKEY_ID_1 = 2003
        HOTKEY_ID_2 = 2004
        MOD_ALT = win32con.MOD_ALT
        MOD_NOREPEAT = 0x4000
        VK_SLASH = 0xBF

        test_key = VK_SLASH
        # First registration
        ok1 = user32.RegisterHotKey(None, HOTKEY_ID_1, MOD_ALT | MOD_NOREPEAT, test_key)
        if not ok1 and ctypes.GetLastError() == 1409:
            test_key = 0x7A  # VK_F11
            ok1 = user32.RegisterHotKey(None, HOTKEY_ID_1, MOD_ALT | MOD_NOREPEAT, test_key)

        self.assertTrue(ok1)

        try:
            # Second registration of the same key combination
            ok2 = user32.RegisterHotKey(None, HOTKEY_ID_2, MOD_ALT | MOD_NOREPEAT, test_key)
            err = ctypes.GetLastError()
            self.assertFalse(ok2, "Second registration of identical hotkey must fail")
            self.assertEqual(err, 1409, f"Expected error 1409 (ERROR_HOTKEY_ALREADY_REGISTERED), got {err}")
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID_1)


if __name__ == "__main__":
    unittest.main()
