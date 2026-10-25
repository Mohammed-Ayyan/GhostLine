import sys
import unittest
from pathlib import Path

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.capture import get_cursor_position, capture_screen_around_cursor

class TestCapture(unittest.TestCase):
    def test_cursor_position(self):
        pos = get_cursor_position()
        self.assertIsInstance(pos, tuple)
        self.assertEqual(len(pos), 2)
        self.assertIsInstance(pos[0], int)
        self.assertIsInstance(pos[1], int)

    def test_capture_screen_region(self):
        img, bbox = capture_screen_around_cursor(width=600, height=400)
        self.assertIsNotNone(img)
        self.assertEqual(len(bbox), 4)
        left, top, right, bottom = bbox
        self.assertTrue(right > left)
        self.assertTrue(bottom > top)
        self.assertEqual(img.size, (right - left, bottom - top))

if __name__ == "__main__":
    unittest.main()
