import sys
import unittest
import threading
import time
from pathlib import Path
from PIL import Image

# Ensure app root is on sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.ui.tray_indicator import TrayIndicator


class TestTrayIndicator(unittest.TestCase):
    """
    Unit and integration tests for the Windows system tray indicator.
    Verifies icon generation, interactive menu items, tooltips,
    toast notifications, graceful fallbacks, and thread lifecycles.
    """

    def test_tray_initialization(self):
        """Verify TrayIndicator initializes cleanly with callbacks."""
        triggered = []
        shown = []
        exited = []

        tray = TrayIndicator(
            on_trigger=lambda: triggered.append(True),
            on_show_hud=lambda: shown.append(True),
            on_exit=lambda: exited.append(True)
        )

        self.assertTrue(tray._has_pystray, "pystray should be available in active environment")
        self.assertFalse(tray.is_running)
        self.assertIsNone(tray.icon)

        # Test callback wrappers
        tray._on_menu_trigger()
        self.assertEqual(len(triggered), 1)

        tray._on_menu_show_hud()
        self.assertEqual(len(shown), 1)

    def test_create_image_badges(self):
        """Verify dynamic 32x32 RGBA icon generation for various badges and statuses."""
        tray = TrayIndicator()

        for status in ["ready", "thinking", "normal", "error"]:
            for badge in ["", "A", "B", "C", "D", "?", "!", "R", "G"]:
                img = tray.create_image(badge=badge, status=status)
                self.assertIsInstance(img, Image.Image)
                self.assertEqual(img.size, (32, 32))
                self.assertEqual(img.mode, "RGBA")

                # Verify image is not completely transparent
                extrema = img.getextrema()
                alpha_channel = extrema[3]  # Alpha min/max
                self.assertGreater(alpha_channel[1], 0, f"Icon for {badge}/{status} must have visible pixels")

    def test_menu_structure_and_defaults(self):
        """Verify menu items include Open Ghostline (default), Solve, Show/Hide HUD, Settings, and Quit."""
        tray = TrayIndicator()
        tray.start()

        try:
            self.assertIsNotNone(tray.icon, "Icon should be initialized after start()")
            menu = tray.icon.menu
            self.assertIsNotNone(menu, "Menu must be attached to tray icon")

            # Extract menu item texts
            menu_items = list(menu.items)
            item_texts = [getattr(item, "text", str(item)) for item in menu_items]

            self.assertTrue(any(t in item_texts for t in ["Open Ghostline"]))
            self.assertIn("Solve Under Cursor (Alt+/)", item_texts)
            self.assertIn("Show/Hide Mini HUD", item_texts)
            self.assertIn("Settings", item_texts)
            self.assertIn("Quit", item_texts)

            # Check that "Open Ghostline" is marked as default
            open_item = next(item for item in menu_items if getattr(item, "text", "") in ["Open Ghostline"])
            self.assertTrue(getattr(open_item, "default", False), "Open Ghostline should be the default action")
        finally:
            tray.stop()

    def test_update_badge_and_tooltip(self):
        """Verify badge update modifies HICON and updates tooltip hover title."""
        tray = TrayIndicator()
        tray.start()

        try:
            # Update to Option B validated
            tray.update_badge(
                badge="B",
                status="normal"
            )
            self.assertTrue(tray.icon.title in ["Ghostline — Answer B"])
            self.assertEqual(tray.current_badge, "B")

            # Update to Option D validated
            tray.update_badge(
                badge="D",
                status="normal"
            )
            self.assertTrue(tray.icon.title in ["Ghostline — Answer D"])
            self.assertEqual(tray.current_badge, "D")

            # Update to Uncertain
            tray.update_badge(
                badge="?",
                status="error"
            )
            self.assertTrue(tray.icon.title in ["Ghostline — Uncertain (?)"])

            # Update to Error
            tray.update_badge(
                badge="!",
                status="error"
            )
            self.assertTrue(tray.icon.title in ["Ghostline — Error (!)"])
        finally:
            tray.stop()

    def test_dynamic_hicon_replacement_without_recreating_tray(self):
        """Verify that updating the badge replaces the Win32 HICON handle without recreating icon."""
        tray = TrayIndicator()
        tray.start()

        # Wait for pystray background message loop to initialize the HICON handle
        initial_handle = None
        for _ in range(60):
            initial_handle = getattr(tray.icon, "_icon_handle", None)
            if initial_handle:
                break
            time.sleep(0.05)

        try:
            self.assertIsNotNone(initial_handle, "Initial HICON handle must exist")

            # Update to 'B'
            tray.update_badge("B", status="normal")
            b_handle = None
            for _ in range(60):
                b_handle = getattr(tray.icon, "_icon_handle", None)
                if b_handle and b_handle != initial_handle:
                    break
                time.sleep(0.05)

            self.assertIsNotNone(b_handle)
            self.assertNotEqual(initial_handle, b_handle, "Updating badge must replace HICON handle via NIM_MODIFY")

            # Update to 'D'
            tray.update_badge("D", status="normal")
            d_handle = None
            for _ in range(60):
                d_handle = getattr(tray.icon, "_icon_handle", None)
                if d_handle and d_handle != b_handle:
                    break
                time.sleep(0.05)

            self.assertIsNotNone(d_handle)
            self.assertNotEqual(b_handle, d_handle, "Updating to D must replace HICON handle again")
        finally:
            tray.stop()

    def test_toast_notification_execution(self):
        """Verify toast notification executes without throwing exceptions."""
        tray = TrayIndicator()
        tray.start()

        try:
            tray.notify("Test Notification: Option B", title="Ghostline Verification")
        finally:
            tray.stop()

    def test_graceful_fallback_without_pystray(self):
        """Verify indicator functions safely without crashing if pystray is disabled."""
        tray = TrayIndicator()
        tray._has_pystray = False
        tray._pystray = None

        # None of these should raise an exception
        tray.start()
        self.assertFalse(tray.is_running)
        tray.update_badge("A", "normal", tooltip="test")
        tray.notify("message", "title")
        tray.stop()

    def test_tray_lifecycle_and_clean_stop(self):
        """Verify start/stop thread lifecycle in Windows desktop environment."""
        tray = TrayIndicator()
        tray.start()
        time.sleep(0.3)

        self.assertTrue(tray.is_running)
        self.assertIsNotNone(tray._thread)
        self.assertTrue(tray._thread.is_alive())

        tray.stop()
        time.sleep(0.3)
        self.assertFalse(tray.is_running)


if __name__ == "__main__":
    unittest.main()
