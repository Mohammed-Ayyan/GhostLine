import unittest
import os
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path

# Add project root to path
pkg_dir = Path(__file__).resolve().parent.parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import installer.setup_gui as setup_gui


class TestInstallerAndLaunchRecovery(unittest.TestCase):
    """
    Regression protection tests for emergency recovery:
    1. primary_exe resolution and existence validation
    2. Missing payload / corrupted payload error handling (no NameError)
    3. Uninstaller creation with correct primary_exe path
    4. Payload discovery in release directories
    5. Batch launcher script integrity
    """

    def setUp(self):
        os.environ["GHOSTLINE_NO_REGISTRY"] = "1"
        self.temp_dir = tempfile.mkdtemp()
        self.install_dir = Path(self.temp_dir) / "InstallDir"
        self.install_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        os.environ.pop("GHOSTLINE_NO_REGISTRY", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_payload_zip_locates_release_dist(self):
        """Verify installer can discover packaged zip payload in release_dist or website_download."""
        payload = setup_gui.find_payload_zip()
        self.assertIsNotNone(payload, "Payload zip was not located in release_dist or website_download!")
        self.assertTrue(payload.is_file(), f"Located payload {payload} is not a valid file!")
        self.assertTrue(payload.suffix == ".zip")

    def test_perform_installation_resolves_primary_exe_cleanly(self):
        """
        Verify perform_installation successfully installs and resolves primary_exe
        without throwing NameError: name 'primary_exe' is not defined.
        """
        # Create a mock valid payload zip containing Ghostline.exe
        mock_zip = Path(self.temp_dir) / "mock_release.zip"
        with zipfile.ZipFile(mock_zip, "w") as zf:
            zf.writestr("Ghostline.exe", b"MOCK_EXE_DATA_FOR_TESTING")
            zf.writestr("ghostline.ico", b"MOCK_ICO")

        progress_calls = []
        def progress_cb(pct, status):
            progress_calls.append((pct, status))

        success, msg = setup_gui.perform_installation(
            install_dir=self.install_dir,
            create_desktop=False,
            create_startmenu=False,
            payload_override=mock_zip,
            progress_callback=progress_cb,
        )

        self.assertTrue(success, f"perform_installation failed: {msg}")
        self.assertIn("succeeded", msg.lower())

        # Verify primary_exe exists and is named Ghostline.exe
        expected_exe = self.install_dir / "Ghostline.exe"
        self.assertTrue(expected_exe.is_file(), f"primary_exe does not exist at {expected_exe}")

        # Verify uninstaller was created referencing Ghostline
        uninstaller = self.install_dir / "uninstall.bat"
        self.assertTrue(uninstaller.is_file(), "uninstall.bat was not created!")
        uninstaller_content = uninstaller.read_text(encoding="utf-8")
        self.assertIn("Ghostline", uninstaller_content)

    def test_perform_installation_fails_safely_if_exe_missing(self):
        """
        If the extracted payload does not contain Ghostline.exe, the installer
        must fail with an informative message rather than crashing with NameError.
        """
        bad_zip = Path(self.temp_dir) / "bad_release.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("some_other_file.txt", b"hello world")

        success, msg = setup_gui.perform_installation(
            install_dir=self.install_dir,
            create_desktop=False,
            create_startmenu=False,
            payload_override=bad_zip,
        )

        self.assertFalse(success, "Installation should have failed when Ghostline.exe was missing!")
        self.assertIn("was not found", msg)

    def test_launcher_scripts_exist_and_use_relative_paths(self):
        """
        Verify run.bat and run_dev.bat exist, use relative directory anchoring (%~dp0),
        and do not silently vanish without reporting errors.
        """
        run_bat = pkg_dir / "run.bat"
        run_dev_bat = pkg_dir / "run_dev.bat"

        self.assertTrue(run_bat.is_file(), "run.bat is missing!")
        self.assertTrue(run_dev_bat.is_file(), "run_dev.bat is missing!")

        run_bat_content = run_bat.read_text(encoding="utf-8")
        run_dev_content = run_dev_bat.read_text(encoding="utf-8")

        # Must anchor to script dir
        self.assertIn("%~dp0", run_bat_content)
        self.assertIn("%~dp0", run_dev_content)

        # Must use python / pythonw with proper error check or pause
        self.assertTrue("pause" in run_bat_content.lower() or "errorlevel" in run_bat_content.lower())
        self.assertTrue("pause" in run_dev_content.lower() or "errorlevel" in run_dev_content.lower())

    def test_uninstaller_script_preserves_user_data_by_default(self):
        """
        Verify the generated uninstall.bat includes user data preservation warnings
        and does not delete %APPDATA%\\Ghostline unless --purge-data is passed.
        """
        mock_zip = Path(self.temp_dir) / "mock_release.zip"
        with zipfile.ZipFile(mock_zip, "w") as zf:
            zf.writestr("Ghostline.exe", b"MOCK_DATA")
            zf.writestr("ghostline.ico", b"MOCK_ICO")

        success, msg = setup_gui.perform_installation(
            install_dir=self.install_dir,
            create_desktop=False,
            create_startmenu=False,
            payload_override=mock_zip,
            register_registry=False
        )
        self.assertTrue(success)

        uninstaller = self.install_dir / "uninstall.bat"
        self.assertTrue(uninstaller.is_file())
        content = uninstaller.read_text(encoding="utf-8")

        # Must mention data preservation
        self.assertIn("preserved", content.lower())
        self.assertIn("--purge-data", content.lower())
        # Must target the exact install directory
        self.assertIn(str(self.install_dir.resolve()), content)
        # Must clean registry and kill processes
        self.assertIn("taskkill", content.lower())
        self.assertIn("reg delete", content.lower())

    def test_register_uninstaller_skips_temp_and_testing_dirs(self):
        """
        Verify register_uninstaller does not write to the registry when given a temporary directory.
        """
        # Ensure registry registration is safely skipped for temp directories
        mock_exe = self.install_dir / "Ghostline.exe"
        mock_exe.touch()
        # Should not raise any exception and should safely skip
        setup_gui.register_uninstaller(self.install_dir, mock_exe)

    def test_startup_mode_detection_and_resolution(self):
        """
        Regression test: Verify get_running_mode() accurately identifies
        DEVELOPMENT mode versus INSTALLED/PACKAGED mode without crashing.
        """
        from ghostline import get_running_mode

        # Case 1: Default source tree execution (frozen is False)
        old_frozen = getattr(sys, "frozen", False)
        try:
            sys.frozen = False
            os.environ.pop("GHOSTLINE_MODE", None)
            self.assertEqual(get_running_mode(), "DEVELOPMENT (Source Tree)")

            # Case 2: Explicit environment override
            os.environ["GHOSTLINE_MODE"] = "DEVELOPMENT"
            self.assertEqual(get_running_mode(), "DEVELOPMENT (Source Tree)")

            # Case 3: Packaged binary simulation (sys.frozen = True)
            os.environ.pop("GHOSTLINE_MODE", None)
            sys.frozen = True
            self.assertEqual(get_running_mode(), "INSTALLED / PACKAGED BUILD")
        finally:
            os.environ.pop("GHOSTLINE_MODE", None)
            if old_frozen:
                sys.frozen = old_frozen
            else:
                if hasattr(sys, "frozen"):
                    del sys.frozen

    def test_main_window_instantiation_without_mode_name_error(self):
        """
        Regression test: Verify QtGhostlineMainWindow initializes cleanly without
        raising NameError: name 'mode' is not defined or AttributeError on screen_frames.
        """
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        qapp = QApplication.instance() or QApplication(sys.argv)

        from ghostline.config import AppConfig
        from ghostline.ui.qt_main_window import QtGhostlineMainWindow
        from ghostline import __version__, BUILD_ID

        cfg = AppConfig()
        # Test in DEVELOPMENT mode
        w = QtGhostlineMainWindow(cfg)
        self.assertIsNotNone(w)
        self.assertTrue(hasattr(w, "running_mode"))
        self.assertIn("DEVELOPMENT", w.running_mode.upper())
        self.assertIn("[DEV MODE]", w.windowTitle())
        self.assertTrue(hasattr(w, "screen_frames"))
        self.assertIn("general", w.screen_frames)
        self.assertIn("dashboard", w.screen_frames)
        w.close()


if __name__ == "__main__":
    unittest.main()

