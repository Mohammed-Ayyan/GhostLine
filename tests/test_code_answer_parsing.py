import unittest
import sys
from pathlib import Path

# Add project root to path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.llm_client import (
    OllamaClient,
    AnswerResult,
    repair_json_escapes,
    extract_json_block,
    safe_parse_model_json,
    classify_question_type,
    normalize_code_newlines,
    extract_and_normalize_code
)
from ghostline.ui.presentation import (
    build_answer_presentation,
    PresentedAnswer,
    TYPE_CODE,
    TYPE_MCQ,
    TYPE_THEORY,
    TYPE_NUMERICAL
)
from ghostline.core.ocr_engine import ParsedQuestion


class TestCodeAnswerParsing(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient()

    def test_reproduce_and_fix_invalid_control_character_python(self):
        """
        Reproduce and verify the fix for 'Invalid control character' JSONDecodeError.
        The input contains literal unescaped linebreaks (\n) and tabs (\t) inside the string value.
        """
        raw_response = (
            '{\n'
            '  "answer": "Binary Search",\n'
            '  "language": "python",\n'
            '  "code": "def binary_search(arr, target):\n'
            '\tlow, high = 0, len(arr) - 1\n'
            '\twhile low <= high:\n'
            '\t\tmid = (low + high) // 2\n'
            '\t\tif arr[mid] == target:\n'
            '\t\t\treturn mid\n'
            '\t\telif arr[mid] < target:\n'
            '\t\t\tlow = mid + 1\n'
            '\t\telse:\n'
            '\t\t\thigh = mid - 1\n'
            '\treturn -1",\n'
            '  "explanation": "Standard binary search implementation running in O(log n) time."\n'
            '}'
        )

        # Standard json.loads(raw, strict=True) fails with Invalid control character
        # safe_parse_model_json must parse it cleanly
        parsed = safe_parse_model_json(raw_response)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["language"], "python")
        self.assertIn("def binary_search", parsed["code"])
        self.assertIn("\tlow, high", parsed["code"])

        # End-to-end pipeline parsing
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a function to perform binary search on a sorted array."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertEqual(result.tray_badge, "Code")
        self.assertEqual(result.code_language, "python")
        self.assertIn("def binary_search", result.code_snippet)

        # Presentation layer verification
        pres = build_answer_presentation(None, result)
        self.assertEqual(pres.question_type, TYPE_CODE)
        self.assertTrue(pres.has_code)
        self.assertEqual(pres.code_language, "python")
        self.assertIn("```python", pres.formatted_clipboard_text)

    def test_javascript_with_regex_escapes_and_quotes(self):
        """
        JavaScript code containing regex backslashes (\d, \w, \s) and quotes.
        Verifies repair_json_escapes preserves both valid and repairs invalid regex escapes.
        """
        raw_response = r"""{
  "answer": "Validate Email and Phone",
  "language": "javascript",
  "code": "function validate(str) {\n    const emailRegex = /^\\w+([.-]?\\w+)*@\\w+([.-]?\\w+)*(\\.\\w{2,3})+$/;\n    const phoneRegex = /^\\d{3}-\\d{3}-\\d{4}$/;\n    return emailRegex.test(str) || phoneRegex.test(str);\n}",
  "explanation": "Uses standard regex character classes \\w and \\d for pattern validation."
}"""
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a JavaScript function to validate emails and phone numbers."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertEqual(result.code_language, "javascript")
        self.assertIn("function validate", result.code_snippet)
        self.assertIn(r"\d", result.code_snippet)

    def test_cpp_with_templates_and_fenced_markdown(self):
        """
        C++ code with includes, templates, and markdown code fences inside or around JSON.
        """
        raw_response = """```json
{
  "answer": "Generic Max Function",
  "language": "cpp",
  "code": "```cpp\n#include <iostream>\n\ntemplate <typename T>\nT getMax(T a, T b) {\n    return (a > b) ? a : b;\n}\n\nint main() {\n    std::cout << getMax(10, 20) << std::endl;\n    return 0;\n}\n```",
  "explanation": "C++ template function that handles any comparable type."
}
```"""
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Implement a generic max function in C++ using templates."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertEqual(result.code_language, "cpp")
        self.assertIn("template <typename T>", result.code_snippet)
        self.assertIn("#include <iostream>", result.code_snippet)
        # Inner markdown fence must be cleanly unwrapped
        self.assertNotIn("```cpp", result.code_snippet)

    def test_java_with_unicode_and_annotations(self):
        """
        Java code with annotations and Unicode math symbols (e.g. π, ∑, √).
        """
        raw_response = """{
  "answer": "Circle Calculations",
  "language": "java",
  "code": "public class Circle {\n    private static final double PI_VAL = 3.1415926535; // π\n\n    @Override\n    public String toString() {\n        return \\"Circle [radius = \\" + 5 + \\", area ≈ \\" + (PI_VAL * 25) + \\"]\\";\n    }\n}",
  "explanation": "Java circle implementation with Unicode symbols (π, ≈) and @Override annotation."
}"""
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a Java class with circle area calculations and Unicode symbols."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertEqual(result.code_language, "java")
        self.assertIn("public class Circle", result.code_snippet)
        self.assertIn("π", result.code_snippet)

    def test_long_code_block_preservation(self):
        """
        Tests handling of long code blocks (50+ lines) to ensure no truncation or buffer crashes.
        """
        lines = ["def process_stream():", "    data = []"]
        for i in range(50):
            lines.append(f"    # Step {i}: accumulate telemetry")
            lines.append(f"    data.append({i} * 2)")
        lines.append("    return sum(data)")
        code_str = "\\n".join(lines)

        raw_response = f"""{{
  "answer": "Long Pipeline",
  "language": "python",
  "code": "{code_str}",
  "explanation": "A 100+ line data processing pipeline."
}}"""
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a stream processing pipeline."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertGreater(len(result.code_snippet.splitlines()), 50)

    def test_missing_optional_fields_does_not_crash(self):
        """
        Tests that missing optional fields (missing 'language', 'explanation', or 'answer')
        are handled gracefully with safe fallbacks and don't raise KeyError or AttributeError.
        """
        # 1. Missing language and explanation
        raw_1 = '{"code": "def hello():\\n    return \'world\'"}'
        res_1 = self.client._parse_and_validate_response(raw_1, options=None)
        self.assertTrue(res_1.is_validated)
        self.assertEqual(res_1.question_type, "code")
        self.assertEqual(res_1.code_language, "python")  # auto-detected from def
        self.assertIn("def hello", res_1.code_snippet)

        # 2. Missing code (theory answer in JSON)
        raw_2 = '{"answer": "ACID Properties", "explanation": "Atomicity, Consistency, Isolation, Durability"}'
        res_2 = self.client._parse_and_validate_response(raw_2, options=None, question_text="What are ACID properties?")
        self.assertTrue(res_2.is_validated)
        self.assertIn(res_2.question_type, ["theory", "mcq"])
        self.assertEqual(res_2.direct_answer, "ACID Properties")

        # 3. Presentation layer with all None/empty optional fields
        sparse_res = AnswerResult(
            source_option_label="Code",
            is_validated=True,
            code_snippet="console.log('hi');",
            code_language="",
            question_type="code"
        )
        pres = build_answer_presentation(None, sparse_res)
        self.assertEqual(pres.question_type, TYPE_CODE)
        self.assertEqual(pres.badge, "Code")

    def test_truncated_json_recovery(self):
        """
        Tests recovery from model output where tokens were cut off (missing closing quotes and braces).
        """
        truncated_response = '{\n  "answer": "QuickSort",\n  "language": "python",\n  "code": "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n'
        result = self.client._parse_and_validate_response(
            truncated_response,
            options=None,
            question_text="Implement quicksort in Python."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertIn("def quicksort", result.code_snippet)

    def test_regression_valid_mcq_unaffected(self):
        """
        Ensures MCQ pathway behaves exactly as before with 100% precision.
        """
        options = {
            "A": "O(n)",
            "B": "O(log n)",
            "C": "O(n^2)",
            "D": "O(1)"
        }
        raw_response = "ANSWER: B\nBinary search divides the search space in half each iteration."
        result = self.client._parse_and_validate_response(
            raw_response,
            options=options,
            question_text="What is the time complexity of binary search?"
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.source_option_label, "B")
        self.assertEqual(result.tray_badge, "B")
        self.assertEqual(result.option_text, "O(log n)")

    def test_regression_valid_theory_unaffected(self):
        """
        Ensures open-ended theory pathway behaves exactly as before.
        """
        raw_response = (
            "DNS resolves domain names to IP addresses.\n"
            "It acts as the phonebook of the internet, mapping human-readable hostnames to numeric IP addresses."
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="What is DNS?"
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "theory")
        self.assertEqual(result.tray_badge, "✓")
        self.assertIn("DNS resolves domain names", result.option_text)

    def test_raw_markdown_code_fallback(self):
        """
        Ensures that if the model returns plain markdown fences instead of JSON,
        the code extraction still succeeds flawlessly.
        """
        raw_response = (
            "Here is the solution:\n\n"
            "```python\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "```\n"
            "This function returns the sum of two numbers."
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a function to add two numbers."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertEqual(result.tray_badge, "Code")
        self.assertEqual(result.code_language, "python")
        self.assertIn("def add(a, b):", result.code_snippet)

    def test_valid_json_multiline_python_code(self):
        """
        Valid JSON containing multiline Python code with JSON-escaped newlines.
        Verifies real line breaks (ASCII 10) are present and no literal \\n remains.
        """
        raw_response = (
            '{\n'
            '  "code": "def fibonacci(n):\\n    if n <= 1:\\n        return n\\n    return fibonacci(n - 1) + fibonacci(n - 2)\\n\\nprint(fibonacci(10))",\n'
            '  "language": "python",\n'
            '  "answer": "Recursive Fibonacci",\n'
            '  "explanation": "Computes the nth Fibonacci number recursively."\n'
            '}'
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a function to compute Fibonacci numbers in Python."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertEqual(result.code_language, "python")
        self.assertIn("def fibonacci(n):", result.code_snippet)
        self.assertIn("\n    if n <= 1:\n", result.code_snippet)
        self.assertNotIn(r"\n", result.code_snippet)
        self.assertGreaterEqual(result.code_snippet.count("\n"), 4)

    def test_double_escaped_newlines_decoding(self):
        """
        Model response containing double-escaped newlines (\\\\n in wire format).
        Verifies that double-escaped sequences are normalized to real line breaks.
        """
        raw_response = (
            '{\n'
            '  "code": "def process_items(items):\\\\n    for item in items:\\\\n        print(item)\\\\n\\\\nprocess_items([1, 2, 3])",\n'
            '  "language": "python",\n'
            '  "answer": "Process Items",\n'
            '  "explanation": "Iterates and prints items."\n'
            '}'
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a function to print each item in a list."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        self.assertIn("def process_items(items):", result.code_snippet)
        self.assertIn("\n    for item in items:\n", result.code_snippet)
        self.assertNotIn(r"\n", result.code_snippet)
        self.assertNotIn(r"\\n", result.code_snippet)

    def test_windows_paths_and_regexes_not_corrupted(self):
        """
        Code containing Windows paths (e.g. C:\\notes\\test.txt) and regexes (r"\\n\\s*\\d+").
        Verifies legitimate escape sequences inside string literals are preserved without corrupting paths.
        """
        raw_response = (
            '{\n'
            '  "code": "import re\\n\\npath = \\"C:\\\\notes\\\\data.txt\\"\\npattern = r\\"\\\\n\\\\s*\\\\d+\\"\\nprint(path, pattern)",\n'
            '  "language": "python",\n'
            '  "answer": "Path and Regex Script",\n'
            '  "explanation": "Demonstrates file path reading and regex pattern matching."\n'
            '}'
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a Python script that loads a file path and compiles a regex."
        )
        self.assertTrue(result.is_validated)
        self.assertEqual(result.question_type, "code")
        lines = result.code_snippet.splitlines()
        self.assertIn("import re", lines[0])
        # Windows path must remain in one line without getting split at \notes
        path_line = [l for l in lines if "path = " in l][0]
        self.assertIn("notes", path_line)
        self.assertTrue("C:" in path_line)

    def test_quotes_unicode_indentation_and_blank_lines(self):
        """
        Code containing single/double quotes, Unicode math symbols (λ, π, ∑),
        multiline indentation, and blank lines.
        """
        raw_response = (
            '{\n'
            '  "code": "def math_constants():\\n    # Mathematical constants: π, λ, ∑\\n    pi = 3.14159\\n    lambda_val = 0.5\\n\\n    msg = \'Pi is approx \' + str(pi)\\n    return msg",\n'
            '  "language": "python",\n'
            '  "answer": "Math Constants",\n'
            '  "explanation": "Calculates math constants with Unicode symbols."\n'
            '}'
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Define math constants with Unicode symbols."
        )
        self.assertTrue(result.is_validated)
        self.assertIn("π", result.code_snippet)
        self.assertIn("lambda_val = 0.5", result.code_snippet)
        self.assertIn("\n\n    msg = ", result.code_snippet)
        self.assertNotIn(r"\n", result.code_snippet)

    def test_already_correctly_formatted_code(self):
        """
        Code string that already contains real line breaks and no escaped characters.
        Must pass through untouched without alteration.
        """
        pure_code = (
            "def add(a, b):\n"
            "    # Simple adder\n"
            "    return a + b\n"
        )
        clean_code, lang, exp = extract_and_normalize_code(pure_code, default_lang="python")
        self.assertEqual(clean_code, pure_code.strip())
        self.assertEqual(lang, "python")

    def test_missing_code_on_programming_question_returns_error_retry(self):
        """
        If a programming question response is malformed and contains no code,
        it should mark validation_status='error' and provide clear Retry guidance.
        """
        malformed_response = '{"answer": "No code provided here", "explanation": "Failed to generate"}'
        result = self.client._parse_and_validate_response(
            malformed_response,
            options=None,
            question_text="Write a Python script to sort a list using quicksort."
        )
        self.assertEqual(result.question_type, "error")
        self.assertEqual(result.validation_status, "error")
        self.assertEqual(result.tray_badge, "!")
        self.assertIn("Retry", result.explanation)

    def test_copy_code_returns_clean_source(self):
        """
        Verifies that presentation layer formatted_clipboard_text and code_snippet
        return pure normalized source code, never JSON wrappers or literal \\n sequences.
        """
        raw_response = (
            '{\n'
            '  "code": "def greet(name):\\n    return f\'Hello, {name}!\'",\n'
            '  "language": "python",\n'
            '  "answer": "Greeting Function",\n'
            '  "explanation": "Returns a friendly greeting string."\n'
            '}'
        )
        result = self.client._parse_and_validate_response(
            raw_response,
            options=None,
            question_text="Write a greeting function in Python."
        )
        pres = build_answer_presentation(None, result)
        self.assertEqual(pres.question_type, TYPE_CODE)
        self.assertTrue(pres.has_code)
        self.assertEqual(pres.code_snippet, "def greet(name):\n    return f'Hello, {name}!'")
        self.assertNotIn(r"\n", pres.code_snippet)
        self.assertIn("```python\ndef greet(name):\n    return f'Hello, {name}!'\n```", pres.formatted_clipboard_text)


if __name__ == "__main__":
    unittest.main()

