import os
import sys
import unittest
from pathlib import Path

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from PIL import Image, ImageDraw, ImageFont
from ghostline.core.ocr_engine import run_native_ocr, parse_question_structure

class TestOcrEngine(unittest.TestCase):
    def setUp(self):
        self.test_img_path = "test_ocr_temp.png"
        img = Image.new("RGB", (900, 350), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        
        # Try to use a standard scalable Windows font
        font = None
        for font_name in ["arial.ttf", "segoeui.ttf", "tahoma.ttf", "calibri.ttf"]:
            try:
                font = ImageFont.truetype(font_name, 22)
                break
            except Exception:
                pass
                
        text = (
            "Question 12: Which planet is known as the Red Planet?\n\n"
            "A) Venus\n"
            "B) Mars\n"
            "C) Jupiter\n"
            "D) Saturn"
        )
        d.text((30, 30), text, fill=(0, 0, 0), font=font)
        img.save(self.test_img_path)

    def tearDown(self):
        if os.path.exists(self.test_img_path):
            os.remove(self.test_img_path)

    def test_native_ocr_extraction(self):
        img = Image.open(self.test_img_path)
        ocr_data = run_native_ocr(img)
        self.assertIn("text", ocr_data)
        self.assertIn("lines", ocr_data)
        self.assertTrue(len(ocr_data["text"]) > 10)

    def test_question_parsing(self):
        img = Image.open(self.test_img_path)
        ocr_data = run_native_ocr(img)
        parsed = parse_question_structure(ocr_data)
        
        self.assertTrue(parsed.is_multiple_choice)
        self.assertIn("B", parsed.options)
        self.assertIn("Mars", parsed.options["B"])
        self.assertIn("Red Planet", parsed.question_text)

if __name__ == "__main__":
    unittest.main()
