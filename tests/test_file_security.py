import unittest
import tempfile
import os
from pathlib import Path
from ghostline.core.profile import extract_text_from_file, export_profile_json

class TestFileSecurity(unittest.TestCase):
    def test_nonexistent_and_directory_rejected(self):
        with self.assertRaises(FileNotFoundError):
            extract_text_from_file("non_existent_file_xyz_123.txt")

        # Directory instead of file
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                extract_text_from_file(td)

    def test_reserved_device_names(self):
        with self.assertRaises(ValueError):
            extract_text_from_file("CON.txt")
        with self.assertRaises(ValueError):
            extract_text_from_file("NUL.txt")

    def test_unsupported_extensions(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tf:
            tf.write(b"fake binary")
            path = tf.name
        try:
            with self.assertRaises(ValueError):
                extract_text_from_file(path)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_valid_txt_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write("Alice Smith\nPython Developer\nSkills: Python, Qt")
            path = tf.name
        try:
            content = extract_text_from_file(path)
            self.assertIn("Alice Smith", content)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_export_profile_json_extension_check(self):
        with tempfile.TemporaryDirectory() as td:
            bad_dest = os.path.join(td, "export.bat")
            ok = export_profile_json(bad_dest)
            self.assertFalse(ok)
            self.assertFalse(os.path.exists(bad_dest))

            good_dest = os.path.join(td, "export.json")
            ok_good = export_profile_json(good_dest)
            self.assertTrue(ok_good)
            self.assertTrue(os.path.exists(good_dest))

if __name__ == "__main__":
    unittest.main()

