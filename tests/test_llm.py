import sys
import unittest
from pathlib import Path

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.llm_client import OllamaClient, AnswerResult

class TestLlmClient(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient(base_url="http://127.0.0.1:11434")

    def test_ollama_connectivity(self):
        self.assertTrue(self.client.is_available(), "Local Ollama daemon must be running")

    def test_phi3_solve_mcq(self):
        q = "In computer programming, what does SQL stand for?"
        opts = {
            "A": "Simple Query Language",
            "B": "Structured Query Language",
            "C": "Standard Quick Logic",
            "D": "System Queue Link"
        }
        res = self.client.solve_question(q, opts, model="phi3:mini")
        self.assertIsInstance(res, AnswerResult)
        self.assertEqual(res.answer_option.upper(), "B")
        self.assertIn("Structured Query Language", res.explanation)

    def test_qwen_solve_mcq(self):
        q = "Which element has the chemical symbol 'O'?"
        opts = {
            "A": "Gold",
            "B": "Oxygen",
            "C": "Osmium",
            "D": "Iron"
        }
        res = self.client.solve_question(q, opts, model="qwen2.5:0.5b")
        self.assertIsInstance(res, AnswerResult)
        self.assertEqual(res.answer_option.upper(), "B")

if __name__ == "__main__":
    unittest.main()
