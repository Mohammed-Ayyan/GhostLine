import unittest
import sys
from pathlib import Path

# Add project root to sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from PyQt6.QtWidgets import QApplication
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestHudLayoutUsability(unittest.TestCase):
    """
    Automated tests for HUD Layout and Usability (DEF-06):
    - Default dimensions (640x560)
    - Minimum safe bounds (>= 540x440)
    - Maximum expansion capacity (>= 1400x950)
    - Safe geometry validation against off-screen positions
    - Mode toggle (compact 560x440 vs expanded 760x640)
    - Essential toolbar action visibility
    """

    def setUp(self):
        self.hud = QtGhostlineHudOverlay()

    def tearDown(self):
        if self.hud:
            self.hud.close()

    def test_default_dimensions(self):
        self.assertEqual(self.hud.width(), 640)
        self.assertEqual(self.hud.height(), 560)

    def test_safe_minimum_bounds(self):
        min_size = self.hud.minimumSize()
        self.assertGreaterEqual(min_size.width(), 540)
        self.assertGreaterEqual(min_size.height(), 440)

    def test_safe_maximum_bounds(self):
        max_size = self.hud.maximumSize()
        self.assertGreaterEqual(max_size.width(), 1400)
        self.assertGreaterEqual(max_size.height(), 950)

    def test_validate_and_apply_geometry_clamps_bounds(self):
        # Extremely small requested size must be clamped to safe minimum
        self.hud.validate_and_apply_geometry(w=200, h=150)
        self.assertGreaterEqual(self.hud.width(), 540)
        self.assertGreaterEqual(self.hud.height(), 440)

        # Off-screen negative coordinates must be clamped to visible desktop area
        self.hud.validate_and_apply_geometry(x=-5000, y=-5000, w=640, h=560)
        self.assertGreaterEqual(self.hud.x(), 0)
        self.assertGreaterEqual(self.hud.y(), 0)

    def test_toggle_compact_expanded_modes(self):
        # Initial: default
        self.assertFalse(self.hud.is_expanded)

        # Toggle to expanded
        self.hud._toggle_size_mode()
        self.assertTrue(self.hud.is_expanded)
        self.assertEqual(self.hud.width(), 760)
        self.assertEqual(self.hud.height(), 640)

        # Toggle to compact
        self.hud._toggle_size_mode()
        self.assertFalse(self.hud.is_expanded)
        self.assertEqual(self.hud.width(), 560)
        self.assertEqual(self.hud.height(), 440)

    def test_essential_toolbar_actions_exist(self):
        self.assertIsNotNone(self.hud.btn_ans)
        self.assertIsNotNone(self.hud.btn_shot)
        self.assertIsNotNone(self.hud.btn_chat)
        self.assertIsNotNone(self.hud.btn_size_mode)


if __name__ == "__main__":
    unittest.main()
