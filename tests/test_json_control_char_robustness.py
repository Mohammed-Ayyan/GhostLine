import unittest
from unittest.mock import MagicMock, patch
import json
import re

from ghostline.core.llm_client import (
    safe_parse_model_json,
    sanitize_control_characters,
    repair_json_escapes,
    decode_json_field,
    normalize_parsed_json_fields,
    extract_and_normalize_code,
    OllamaClient,
    AnswerResult,
)
from ghostline.core.ocr_engine import safe_parse_ocr_json
from ghostline.ui.presentation import build_answer_presentation, TYPE_CODE, TYPE_MCQ, TYPE_UNCERTAIN


class TestJsonControlCharRobustness(unittest.TestCase):
    """
    Comprehensive regression tests for Ghostline JSON parsing and control-character handling.
    Covers the 9 specified test categories.
    """

    # 1. Normal JSON responses
    def test_01_normal_json_response(self):
        raw = '{"code": "def add(a, b):\\n    return a + b\\n", "language": "python", "answer": "def add(a, b):", "explanation": "Adds two numbers."}'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("def add(a, b):", parsed["code"])
        self.assertEqual(parsed["language"], "python")
        self.assertEqual(parsed["answer"], "def add(a, b):")
        self.assertEqual(parsed["explanation"], "Adds two numbers.")

    # 2. JSON strings containing escaped newlines (\n, \r\n)
    def test_02_json_with_escaped_newlines(self):
        raw = '{\n  "code": "line1\\r\\nline2\\nline3\\n",\n  "language": "python",\n  "answer": "line1",\n  "explanation": "Multiline\\nexplanation"\n}'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("line1\r\nline2\nline3", parsed["code"])
        self.assertIn("Multiline\nexplanation", parsed["explanation"])

    # 3. Multiline Python, Java, and JavaScript code
    def test_03a_multiline_python_code(self):
        raw = """{
            "code": "def binary_search(arr, target):\\n    low, high = 0, len(arr) - 1\\n    while low <= high:\\n        mid = (low + high) // 2\\n        if arr[mid] == target:\\n            return mid\\n        elif arr[mid] < target:\\n            low = mid + 1\\n        else:\\n            high = mid - 1\\n    return -1",
            "language": "python",
            "answer": "binary_search",
            "explanation": "Standard binary search implementation."
        }"""
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        code, lang, _ = extract_and_normalize_code(parsed["code"], parsed["language"])
        self.assertEqual(lang, "python")
        self.assertIn("def binary_search", code)
        self.assertIn("while low <= high:", code)

    def test_03b_multiline_java_code(self):
        raw = """{
            "code": "public class Solution {\\n    public int maxSubArray(int[] nums) {\\n        int maxSoFar = nums[0], currMax = nums[0];\\n        for (int i = 1; i < nums.length; i++) {\\n            currMax = Math.max(nums[i], currMax + nums[i]);\\n            maxSoFar = Math.max(maxSoFar, currMax);\\n        }\\n        return maxSoFar;\\n    }\\n}",
            "language": "java",
            "answer": "maxSubArray",
            "explanation": "Kadane's algorithm in Java."
        }"""
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        code, lang, _ = extract_and_normalize_code(parsed["code"], parsed["language"])
        self.assertEqual(lang, "java")
        self.assertIn("public class Solution", code)

    def test_03c_multiline_javascript_code(self):
        raw = """{
            "code": "const debounce = (fn, delay) => {\\n    let timer = null;\\n    return (...args) => {\\n        clearTimeout(timer);\\n        timer = setTimeout(() => fn(...args), delay);\\n    };\\n};",
            "language": "javascript",
            "answer": "debounce",
            "explanation": "Debounce function in JavaScript."
        }"""
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        code, lang, _ = extract_and_normalize_code(parsed["code"], parsed["language"])
        self.assertEqual(lang, "javascript")
        self.assertIn("const debounce", code)

    # 4. Quotes, backslashes, Unicode, and tabs
    def test_04_quotes_backslashes_unicode_tabs(self):
        # Code containing regexes with backslashes (\d+, \s*), unicode bullet (\u2022), tabs (\t), and quotes
        raw = """{
            "code": "# Tabbed code\\n\\tpattern = re.compile(r\\"\\d+\\s*•\\")\\n\\tmessage = \\"Hello 'world' and \\\\ escaped backslash\\"",
            "language": "python",
            "answer": "Regex pattern",
            "explanation": "Testing \\t tabs, \\" quotes, and unicode \\u2022 bullet."
        }"""
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("pattern = re.compile", parsed["code"])
        self.assertIn("tabs", parsed["explanation"])

    # 5. Literal unescaped control characters inside JSON strings
    def test_05a_literal_unescaped_control_characters(self):
        # Construct raw string with literal ASCII 0x07 (Bell), 0x00 (Nul), 0x08 (Backspace), 0x0b, 0x0c, 0x1b
        ctrl_chars = "\x07\x00\x08\x0b\x0c\x1b"
        raw = '{"code": "def test():\n\t# Bel:' + ctrl_chars + '\n\treturn True", "language": "python", "answer": "True", "explanation": "Contains ' + ctrl_chars + ' control chars"}'
        # Must parse without throwing Invalid control character
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("def test():", parsed["code"])
        self.assertEqual(parsed["language"], "python")

    def test_05b_ocr_json_with_bell_character(self):
        # Simulate WinOcr stdout where bullet point 0x2022 was emitted as OEM-437 byte 0x07
        raw_ocr = '{"lines": [{"text": "\x07 First Option: A", "confidence": 0.95}], "width": 1920, "height": 1080}'
        parsed = safe_parse_ocr_json(raw_ocr)
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed["lines"]), 1)
        self.assertIn("First Option: A", parsed["lines"][0]["text"])

    # 6. Truncated or incomplete model output
    def test_06_truncated_model_output(self):
        # JSON cut off mid-code without closing quote or brace
        raw = '{"code": "def solve():\\n    print(\\"partially generated code\\")'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("partially generated code", parsed["code"])

    # 7. Missing fields and unexpected response types
    def test_07a_code_as_list_of_strings(self):
        raw = '{"code": ["def hello():", "    return \\"world\\""], "language": "python", "answer": "hello"}'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIsInstance(parsed["code"], str)
        self.assertEqual(parsed["code"], 'def hello():\n    return "world"')

    def test_07b_code_promoted_from_answer(self):
        raw = '{"code": "", "language": "python", "answer": "def factor(n):\\n    return 1 if n <= 1 else n * factor(n-1)", "explanation": "Recursive factorial"}'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("def factor(n):", parsed["code"])

    def test_07c_missing_optional_fields(self):
        raw = '{"code": "def foo(): pass"}'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["code"], "def foo(): pass")

    # 8. Valid and malformed Ollama responses
    def test_08a_markdown_fenced_json(self):
        raw = 'Here is your solution:\n```json\n{\n  "code": "x = 42",\n  "language": "python",\n  "answer": "42",\n  "explanation": "Answer"\n}\n```\nHope this helps!'
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["code"], "x = 42")
        self.assertEqual(parsed["language"], "python")

    def test_08b_python_single_quoted_dict(self):
        raw = "{'code': 'def greet(): return \"hi\"', 'language': 'python', 'answer': 'greet', 'explanation': 'Greeting function'}"
        parsed = safe_parse_model_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["code"], 'def greet(): return "hi"')
        self.assertEqual(parsed["language"], "python")

    # 9. End-to-end inference with mocked model responses
    @patch("requests.post")
    def test_09a_e2e_mcq_streaming_with_control_chars(self, mock_post):
        # Mock streaming response with tokens containing control characters and raw newlines
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Line-delimited JSON chunks from Ollama streaming
        mock_response.iter_lines.return_value = [
            b'{"response": "ANSWER: 2\\n"}',
            b'{"response": "Explanation: Option 2 is correct because \x07 it matches \x0b the criteria."}'
        ]
        mock_post.return_value = mock_response

        client = OllamaClient(base_url="http://127.0.0.1:11434")
        streamed_tokens = []

        result = client.solve_question(
            question_text="What is the output?",
            options={"1": "Foo", "2": "Bar", "3": "Baz"},
            model="test-model",
            stream_callback=lambda tok: streamed_tokens.append(tok)
        )

        self.assertEqual(result.proposed_option, "2")
        self.assertEqual(result.answer_option, "2")
        self.assertTrue(result.is_validated)
        self.assertEqual(result.tray_badge, "2")

        # Test HUD presentation
        presentation = build_answer_presentation(None, result)
        self.assertEqual(presentation.question_type, TYPE_MCQ)
        self.assertEqual(presentation.badge, "2")
        self.assertTrue(presentation.is_validated)

    @patch("requests.post")
    def test_09b_e2e_programming_json_with_control_chars(self, mock_post):
        # Mock non-streaming response containing JSON with literal unescaped control chars in code
        code_body = "def calculate_sum(nums):\n\ttotal = 0\n\tfor n in nums:\n\t\ttotal += n\n\treturn total"
        json_payload = {
            "response": '{\n  "code": "' + code_body.replace('\n', '\\n').replace('\t', '\\t') + '",\n  "language": "python",\n  "answer": "calculate_sum",\n  "explanation": "Iterates and sums \\x07 numbers."\n}'
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(json_payload)
        mock_post.return_value = mock_response

        client = OllamaClient(base_url="http://127.0.0.1:11434")
        result = client.solve_question(
            question_text="Write a function to sum a list of numbers.",
            options=None,
            model="test-model",
            question_type="programming",
            requested_language="python"
        )

        self.assertIsNotNone(result.code_snippet)
        self.assertIn("def calculate_sum", result.code_snippet)
        self.assertEqual(result.code_language, "python")
        self.assertTrue(result.is_validated)
        self.assertEqual(result.tray_badge, "Code")

        # Verify HUD presentation receives valid code
        presentation = build_answer_presentation(None, result)
        self.assertEqual(presentation.question_type, TYPE_CODE)
        self.assertEqual(presentation.badge, "Code")
        self.assertIsNotNone(presentation.code_snippet)

    @patch("requests.post")
    def test_09c_e2e_malformed_response_safe_recovery_and_presentation(self, mock_post):
        # Completely garbled model response that cannot be parsed into code
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"response": "I cannot answer this programming question because of an internal error."})
        mock_post.return_value = mock_response

        client = OllamaClient(base_url="http://127.0.0.1:11434")
        # Must not raise an unhandled exception or crash
        result = client.solve_question(
            question_text="Write a quicksort in C++.",
            options=None,
            model="test-model",
            question_type="programming",
            requested_language="cpp"
        )

        self.assertIsNotNone(result)
        self.assertFalse(result.is_validated)
        self.assertEqual(result.validation_status, "error")
        self.assertEqual(result.tray_badge, "!")

        # Verify HUD presentation presents a graceful diagnostic instead of crashing
        presentation = build_answer_presentation(None, result)
        self.assertEqual(presentation.badge, "!")
        self.assertFalse(presentation.is_validated)
        self.assertIn("Model did not provide a valid source code solution", presentation.explanation)


if __name__ == "__main__":
    unittest.main()
