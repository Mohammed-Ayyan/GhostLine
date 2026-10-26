import unittest
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import win32con
import win32gui
from PyQt6.QtWidgets import QApplication
from ghostline.config import AppConfig, load_config, save_config
from ghostline.app import (
    validate_hotkey_string,
    parse_hotkey_string,
    WM_GHOSTLINE_RELOAD_HOTKEYS,
    VK_MAP
)
from ghostline.ui.qt_main_window import QtShortcutDialog

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestCustomShortcutsRegression(unittest.TestCase):
    """
    Automated regression tests for Custom Keyboard Shortcuts (DEF-02):
    - Input parsing and validation
    - Modifiers and special virtual keys
    - Conflict detection with internal shortcuts
    - Configuration persistence across restarts
    - Runtime reload message contract
    """

    def test_empty_and_whitespace_shortcuts_rejected(self):
        is_valid, norm, mod, vk, err = validate_hotkey_string("")
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", err)

        is_valid, norm, mod, vk, err = validate_hotkey_string("   ")
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", err)

    def test_missing_modifiers_rejected(self):
        # Bare keys without Ctrl/Alt/Shift/Win must be rejected
        for key in ["A", "1", "/", "Space", "F5"]:
            is_valid, norm, mod, vk, err = validate_hotkey_string(key)
            self.assertFalse(is_valid, f"Bare key '{key}' should require a modifier.")
            self.assertIn("modifier", err.lower())

    def test_missing_key_rejected(self):
        # Modifiers without a key must be rejected
        for mod_str in ["Ctrl", "Alt", "Ctrl+Alt", "Win+Shift"]:
            is_valid, norm, mod, vk, err = validate_hotkey_string(mod_str)
            self.assertFalse(is_valid, f"Modifier-only '{mod_str}' should require a key.")
            self.assertIn("valid key", err.lower())

    def test_valid_shortcuts_normalized_and_mapped(self):
        # Default Alt + /
        is_valid, norm, mod, vk, err = validate_hotkey_string("alt+/")
        self.assertTrue(is_valid)
        self.assertEqual(norm, "Alt + /")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, 0xBF)

        # Multi-modifier Ctrl + Alt + K
        is_valid, norm, mod, vk, err = validate_hotkey_string("ctrl+alt+k")
        self.assertTrue(is_valid)
        self.assertEqual(norm, "Ctrl + Alt + K")
        self.assertEqual(mod, win32con.MOD_CONTROL | win32con.MOD_ALT)
        self.assertEqual(vk, ord("K"))

        # Function keys: Win + Shift + F12
        is_valid, norm, mod, vk, err = validate_hotkey_string("win + shift + f12")
        self.assertTrue(is_valid)
        self.assertEqual(norm, "Win + Shift + F12")
        self.assertEqual(mod, win32con.MOD_WIN | win32con.MOD_SHIFT)
        self.assertEqual(vk, win32con.VK_F1 + 11)

        # Navigation key: Alt + Enter
        is_valid, norm, mod, vk, err = validate_hotkey_string("alt + enter")
        self.assertTrue(is_valid)
        self.assertEqual(norm, "Alt + Enter")
        self.assertEqual(mod, win32con.MOD_ALT)
        self.assertEqual(vk, win32con.VK_RETURN)

    def test_shortcut_persistence_across_restarts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "config.json"
            cfg = AppConfig(hotkey="Alt + /")
            save_config(cfg, path=tmp_path)

            # Update to custom shortcut
            cfg.hotkey = "Ctrl + Alt + S"
            save_config(cfg, path=tmp_path)

            # Reload from disk
            reloaded = load_config(path=tmp_path)
            self.assertEqual(reloaded.hotkey, "Ctrl + Alt + S")

    def test_shortcut_dialog_validation_and_conflict_check(self):
        dlg = QtShortcutDialog(current_hotkey="Alt + /")

        # Test valid input
        dlg._validate_input("Ctrl + Alt + M")
        self.assertTrue(dlg.btn_save.isEnabled())
        self.assertIn("Valid", dlg.lbl_feedback.text())

        # Test invalid input
        dlg._validate_input("InvalidKeyOnly")
        self.assertFalse(dlg.btn_save.isEnabled())
        self.assertIn("❌", dlg.lbl_feedback.text())

        # Test conflict with built-in hotkey Alt+A (Live Audio Assistant)
        dlg._validate_input("Alt + A")
        self.assertFalse(dlg.btn_save.isEnabled())
        self.assertIn("Conflict", dlg.lbl_feedback.text())

        # Test conflict with built-in hotkey Alt+L (Audio Toggle)
        dlg._validate_input("Alt + L")
        self.assertFalse(dlg.btn_save.isEnabled())
        self.assertIn("Conflict", dlg.lbl_feedback.text())

    def test_reload_hotkey_win32_message_registered(self):
        # Verify WM_GHOSTLINE_RELOAD_HOTKEYS is properly registered in OS
        self.assertIsNotNone(WM_GHOSTLINE_RELOAD_HOTKEYS)
        self.assertGreater(WM_GHOSTLINE_RELOAD_HOTKEYS, 0xC000)


if __name__ == "__main__":
    unittest.main()
