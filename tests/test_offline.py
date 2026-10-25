import os
import sys
import unittest
from pathlib import Path

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

import psutil
from PIL import Image, ImageDraw
from ghostline.core.pipeline import GhostlinePipeline

class TestOfflineIsolation(unittest.TestCase):
    def setUp(self):
        self.test_img_path = "test_offline_temp.png"
        img = Image.new("RGB", (700, 250), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        text = (
            "What is 15 + 27?\n"
            "A) 32\n"
            "B) 40\n"
            "C) 42\n"
            "D) 52"
        )
        d.text((20, 20), text, fill=(0, 0, 0))
        img.save(self.test_img_path)

    def tearDown(self):
        if os.path.exists(self.test_img_path):
            os.remove(self.test_img_path)

    def test_zero_external_network_connections(self):
        """Verifies that running pipeline creates only localhost connections to Ollama."""
        current_pid = os.getpid()
        proc = psutil.Process(current_pid)

        pipeline = GhostlinePipeline(model_name="phi3:mini")
        img = Image.open(self.test_img_path)
        res = pipeline.process_from_image(img)

        # Check socket connections owned by this process
        connections = proc.net_connections()
        for conn in connections:
            if conn.raddr:
                remote_ip = conn.raddr.ip
                self.assertIn(
                    remote_ip,
                    ["127.0.0.1", "::1"],
                    f"Violation of offline guarantee: outbound connection detected to {remote_ip}:{conn.raddr.port}"
                )

        self.assertEqual(res.answer_result.answer_option.upper(), "C")

if __name__ == "__main__":
    unittest.main()
