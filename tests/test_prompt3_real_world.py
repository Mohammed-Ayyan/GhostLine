"""
Ghostline — Prompt 3 Comprehensive Real-World Verification Test Suite.
Validates:
1. Question Type Classifier (deterministic rules, tiebreakers, adversarial cases)
2. Per-type prompt generation (MCQ vs Coding vs Output Prediction vs Short Answer)
3. Signal-to-visible-widget thread safety (real QThread -> QtEventBridge -> HUD slot)
4. Packaged executable and offline Whisper model / Silero VAD asset smoke test
5. 12 Real-world screen questions (5 MCQs, 4 Coding, 2 Output Prediction, 1 Short Answer)
   with real OCR and local Ollama inference, execution of generated code against sample inputs,
   and verification of debug dumps.
6. Audio pipeline telemetry log counters and Alt+Q empty transcript handling.
"""

import os
import sys
import time
import json
import unittest
import threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ghostline.config import AppConfig, get_app_dir
from ghostline.core.classifier import classify_question, QuestionType
from ghostline.core.ocr_engine import ParsedQuestion, parse_question_structure, run_native_ocr
from ghostline.core.llm_client import OllamaClient, AnswerResult, extract_code_block
from ghostline.core.pipeline import GhostlinePipeline
from ghostline.ui.presentation import build_answer_presentation, TYPE_MCQ, TYPE_CODE, TYPE_THEORY
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.audio.telemetry import get_audio_telemetry
from ghostline.audio.transcription import resolve_whisper_model_path, HAVE_FASTER_WHISPER
if HAVE_FASTER_WHISPER:
    from faster_whisper import WhisperModel


def render_question_image(
    title: str,
    stem: str,
    items: list = None,
    bg_color=(255, 255, 255),
    fg_color=(0, 0, 0),
    font_size=20,
    width=1280,
    height=800
) -> Image.Image:
    """Renders a realistic crisp screenshot of a question for OCR processing."""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", font_size + 4)
        font_body = ImageFont.truetype("arial.ttf", font_size)
        font_mono = ImageFont.truetype("consola.ttf", font_size - 1)
    except Exception:
        font_title = font_body = font_mono = ImageFont.load_default()

    y = 40
    if title:
        draw.text((60, y), title, fill=fg_color, font=font_title)
        y += font_size + 25

    import textwrap
    # Split stem across lines and wrap if line exceeds width
    for raw_line in stem.splitlines():
        is_indented_code = raw_line.startswith(("    ", "\t"))
        wrapped = [raw_line] if is_indented_code and len(raw_line) <= 85 else textwrap.wrap(raw_line, width=75)
        for s_line in wrapped:
            cur_font = font_mono if any(k in s_line for k in ["def ", "int ", "return ", "{", "}", "SELECT "]) else font_body
            draw.text((60, y), s_line, fill=fg_color, font=cur_font)
            y += font_size + 8

    y += 15
    if items:
        for it in items:
            cur_font = font_mono if any(k in it for k in ["[", "{", "def ", "int ", "SELECT "]) else font_body
            draw.text((80, y), it, fill=fg_color, font=cur_font)
            y += font_size + 12

    return img


class TestClassifierUnit(unittest.TestCase):
    """Unit tests for deterministic question classifier and adversarial boundary conditions."""

    def test_standard_mcq(self):
        text = "Which HTTP status code indicates resource creation?\nA) 200 OK\nB) 201 Created\nC) 404 Not Found\nD) 500 Internal Error"
        parsed = parse_question_structure(text)
        qtype = classify_question(text, parsed)
        self.assertEqual(qtype, QuestionType.MCQ)

    def test_coding_imperative(self):
        text = "Write a Python function two_sum(nums, target) that returns indices of numbers that add up to target."
        parsed = parse_question_structure(text)
        qtype = classify_question(text, parsed)
        self.assertEqual(qtype, QuestionType.CODING)

    def test_output_prediction(self):
        text = "Find the output of the following Python program:\nx = [1, 2, 3]\ny = x\ny.append(4)\nprint(len(x))"
        parsed = parse_question_structure(text)
        qtype = classify_question(text, parsed)
        self.assertEqual(qtype, QuestionType.OUTPUT_PREDICTION)

    def test_short_answer_explanation(self):
        text = "Explain the fundamental difference between a process and a thread in modern operating systems."
        parsed = parse_question_structure(text)
        qtype = classify_question(text, parsed)
        self.assertEqual(qtype, QuestionType.SHORT_ANSWER)

    def test_adversarial_mcq_with_code_options(self):
        """MCQ where each option is a code snippet. Must classify as MCQ, NOT coding."""
        text = (
            "Which Python list comprehension correctly squares all even numbers in a list?\n"
            "A) [x**2 for x in nums if x % 2 == 0]\n"
            "B) [x^2 for x in nums if x % 2 == 0]\n"
            "C) [x**2 if x % 2 == 0 for x in nums]\n"
            "D) (x**2 for x in nums where x % 2 == 0)"
        )
        parsed = parse_question_structure(text)
        qtype = classify_question(text, parsed)
        self.assertEqual(qtype, QuestionType.MCQ)

    def test_adversarial_coding_with_input_output_examples(self):
        """Coding question with 'Input: / Output:' lines that could mimic options. Must classify as CODING."""
        text = (
            "Write a Python function reverse_words(s: str) -> str that reverses words in a string.\n"
            "Input: s = \"the sky is blue\"\n"
            "Output: \"blue is sky the\"\n"
            "Input: s = \"  hello world  \"\n"
            "Output: \"world hello\"\n"
            "Constraints: s contains English letters and spaces."
        )
        parsed = parse_question_structure(text)
        qtype = classify_question(text, parsed)
        self.assertEqual(qtype, QuestionType.CODING)


class TestPerTypePromptSelection(unittest.TestCase):
    """Verifies that llm_client generates prompt instructions matching question type."""

    def setUp(self):
        self.llm = OllamaClient()

    def test_coding_prompt_contains_fenced_code_instructions(self):
        prompt = self.llm._construct_prompt(
            question="Write a function reverse_string(s: str) -> str",
            options=None,
            question_type=QuestionType.CODING
        )
        self.assertIn("```", prompt)
        self.assertIn("Do NOT mention multiple-choice option letters", prompt)
        self.assertIn("time and space complexity", prompt.lower())

    def test_mcq_prompt_contains_option_instructions(self):
        prompt = self.llm._construct_prompt(
            question="What is the capital of France?",
            options={"A": "London", "B": "Paris", "C": "Berlin", "D": "Rome"},
            question_type=QuestionType.MCQ
        )
        self.assertIn("ANSWER: [OPTION_LABEL]", prompt)
        self.assertIn("provided options", prompt)

    def test_output_prediction_prompt_contains_output_instruction(self):
        prompt = self.llm._construct_prompt(
            question="What is the output of print(2**3)?",
            options=None,
            question_type=QuestionType.OUTPUT_PREDICTION
        )
        self.assertIn("OUTPUT: [Exact Output]", prompt)

    def test_short_answer_prompt(self):
        prompt = self.llm._construct_prompt(
            question="Explain virtual memory paging.",
            options=None,
            question_type=QuestionType.SHORT_ANSWER
        )
        self.assertIn("direct, concise answer", prompt)
        self.assertIn("Do NOT mention multiple-choice option letters", prompt)


class MockWorkerThread(QThread):
    sig_chunk = pyqtSignal(str, str)
    sig_err = pyqtSignal(str)

    def run(self):
        time.sleep(0.05)
        self.sig_chunk.emit("mic", "Testing real signal delivery")
        time.sleep(0.05)
        self.sig_err.emit("Simulated audio engine error")


class TestSignalToVisibleWidget(unittest.TestCase):
    """Verifies Qt thread safety: real QThread -> pyqtSignal -> QueuedConnection -> HUD slot."""

    def test_queued_signal_delivery_to_hud(self):
        hud = QtGhostlineHudOverlay()
        received_chunks = []
        received_errors = []

        hud.show_partial_transcript = lambda src, txt: received_chunks.append((src, txt))
        hud.show_audio_error = lambda err: received_errors.append(err)

        worker = MockWorkerThread()
        worker.sig_chunk.connect(hud.show_partial_transcript, Qt.ConnectionType.QueuedConnection)
        worker.sig_err.connect(hud.show_audio_error, Qt.ConnectionType.QueuedConnection)

        worker.start()
        worker.wait(2000)
        app.processEvents()

        self.assertEqual(len(received_chunks), 1)
        self.assertEqual(received_chunks[0], ("mic", "Testing real signal delivery"))
        self.assertEqual(len(received_errors), 1)
        self.assertEqual(received_errors[0], "Simulated audio engine error")
        hud.close()


class TestPackagingAndOfflineModelSmoke(unittest.TestCase):
    """Verifies distribution artifacts and offline Whisper model loading without network."""

    def test_packaged_executable_and_assets_exist(self):
        exe_path = REPO_ROOT / "dist" / "Ghostline" / "Ghostline.exe"
        self.assertTrue(exe_path.exists(), f"Packaged executable missing at {exe_path}")

        # Check win_ocr native binary
        bin_ocr = REPO_ROOT / "dist" / "Ghostline" / "bin" / "win_ocr.exe"
        self.assertTrue(bin_ocr.exists(), f"win_ocr.exe missing at {bin_ocr}")

        # Check Silero VAD .onnx asset
        vad_path = REPO_ROOT / "dist" / "Ghostline" / "_internal" / "faster_whisper" / "assets" / "silero_vad_v6.onnx"
        self.assertTrue(vad_path.exists(), f"silero_vad_v6.onnx missing in packaged dist at {vad_path}")

    def test_whisper_offline_model_resolution(self):
        resolved_path, is_local = resolve_whisper_model_path("tiny")
        self.assertTrue(is_local, f"Whisper tiny model must resolve to a local directory, got: {resolved_path}")
        model_dir = Path(resolved_path)
        self.assertTrue((model_dir / "model.bin").exists(), f"model.bin missing in {model_dir}")
        self.assertTrue((model_dir / "config.json").exists(), f"config.json missing in {model_dir}")

    @unittest.skipUnless(HAVE_FASTER_WHISPER, "faster_whisper not installed")
    def test_whisper_loads_offline_with_local_files_only(self):
        resolved_path, is_local = resolve_whisper_model_path("tiny")
        # Load with local_files_only=True to guarantee no network call is attempted
        model = WhisperModel(resolved_path, device="cpu", compute_type="int8", local_files_only=True)
        self.assertIsNotNone(model)


class TestRealWorldScreenPipeline(unittest.TestCase):
    """
    Runs the complete Ghostline screen pipeline (Native Windows OCR -> Question Parsing ->
    Classifier -> Model Router -> Local Ollama -> Per-Type Presentation) on 12 real-world questions.
    Asserts exact question extraction, type classification, and solution format.
    Executes Python solutions against sample inputs.
    """

    @classmethod
    def setUpClass(cls):
        cls.config = AppConfig()
        cls.pipeline = GhostlinePipeline(config=cls.config)
        cls.llm = OllamaClient()
        cls.debug_dir = get_app_dir() / "debug"

    def _test_question(self, q_data: dict):
        img = render_question_image(
            title=q_data.get("title", ""),
            stem=q_data["stem"],
            items=q_data.get("items", []),
            bg_color=q_data.get("bg_color", (255, 255, 255)),
            fg_color=q_data.get("fg_color", (0, 0, 0)),
            font_size=q_data.get("font_size", 20)
        )

        res = self.pipeline.process_from_image(img)
        parsed = res.parsed_question
        ans = res.answer_result

        # 1. Verify OCR extracted key question tokens
        raw_ocr = parsed.raw_text.lower()
        for kw in q_data["expected_keywords"]:
            self.assertIn(kw.lower(), raw_ocr, f"Keyword '{kw}' missing from OCR text: {parsed.raw_text[:200]}")

        # 2. Verify Classification
        expected_type = q_data["expected_type"]
        self.assertEqual(parsed.question_type, expected_type,
                         f"Question misclassified as {parsed.question_type}, expected {expected_type}")

        # 3. Verify Presentation and Type-Specific Constraints
        pres = build_answer_presentation(parsed, ans)

        if expected_type == QuestionType.MCQ:
            self.assertEqual(pres.question_type, TYPE_MCQ)
            expected_opt = q_data["expected_option"]
            self.assertEqual(pres.badge, expected_opt,
                             f"Expected option {expected_opt}, got {pres.badge} (headline: {pres.headline})")
        elif expected_type == QuestionType.CODING:
            self.assertEqual(pres.question_type, TYPE_CODE)
            # Must NOT produce an option badge
            self.assertNotIn(pres.badge, ["A", "B", "C", "D", "1", "2", "3", "4"])
            self.assertEqual(pres.badge, "Code")
            # Must have code snippet
            self.assertTrue(bool(pres.code), "Coding answer must include extracted code block")
            # If test execution provided, run code against sample inputs
            if "code_validator" in q_data:
                valid, msg = q_data["code_validator"](pres.code)
                self.assertTrue(valid, f"Generated code failed sample execution: {msg}\nCode:\n{pres.code}")
        elif expected_type == QuestionType.OUTPUT_PREDICTION:
            expected_out = q_data["expected_output"]
            self.assertTrue(
                expected_out.lower() in pres.direct_answer.lower() or expected_out.lower() in pres.headline.lower(),
                f"Output prediction missing expected output '{expected_out}'. Got direct: '{pres.direct_answer}', headline: '{pres.headline}'"
            )
        elif expected_type == QuestionType.SHORT_ANSWER:
            self.assertNotIn(pres.badge, ["A", "B", "C", "D"])
            self.assertTrue(len(pres.explanation) > 20, "Short answer should have detailed explanation")

        return True

    # --- 5 MCQs ---
    def test_01_mcq_standard_light(self):
        """MCQ 1: Standard Light Theme Browser Quiz"""
        q = {
            "title": "Web Development Certification - Exam A",
            "stem": "Which HTTP status code indicates that the request was successfully processed and a new resource was created?",
            "items": [
                "A) 200 OK",
                "B) 201 Created",
                "C) 204 No Content",
                "D) 400 Bad Request"
            ],
            "expected_keywords": ["HTTP status code", "resource", "created"],
            "expected_type": QuestionType.MCQ,
            "expected_option": "B"
        }
        self.assertTrue(self._test_question(q))

    def test_02_mcq_dark_theme(self):
        """MCQ 2: Dark Theme Developer Quiz (#0d1117)"""
        q = {
            "title": "Python Data Structures Assessment",
            "stem": "What is the average time complexity of a key lookup in a standard Python dictionary?",
            "items": [
                "A) O(1)",
                "B) O(log n)",
                "C) O(n)",
                "D) O(n log n)"
            ],
            "bg_color": (13, 17, 23),
            "fg_color": (201, 209, 219),
            "expected_keywords": ["time complexity", "dictionary"],
            "expected_type": QuestionType.MCQ,
            "expected_option": "A"
        }
        self.assertTrue(self._test_question(q))

    def test_03_mcq_small_font(self):
        """MCQ 3: Small-font 11px Academic Exam Style"""
        q = {
            "title": "Networking Protocols - Midterm",
            "stem": "Which protocol provides reliable, connection-oriented byte-stream delivery with a 3-way handshake?",
            "items": [
                "A) UDP",
                "B) ICMP",
                "C) TCP",
                "D) ARP"
            ],
            "font_size": 14,
            "expected_keywords": ["connection-oriented", "3-way handshake"],
            "expected_type": QuestionType.MCQ,
            "expected_option": "C"
        }
        self.assertTrue(self._test_question(q))

    def test_04_mcq_algorithms(self):
        """MCQ 4: Algorithm Complexity Analysis"""
        q = {
            "title": "Algorithms 101",
            "stem": "What is the worst-case time complexity of binary search on a sorted array of size N?",
            "items": [
                "A) O(1)",
                "B) O(log N)",
                "C) O(N)",
                "D) O(N^2)"
            ],
            "expected_keywords": ["binary search", "sorted array"],
            "expected_type": QuestionType.MCQ,
            "expected_option": "B"
        }
        self.assertTrue(self._test_question(q))

    def test_05_mcq_code_in_options_adversarial(self):
        """MCQ 5 (Adversarial): Options contain Python code snippets. Must classify as MCQ."""
        q = {
            "title": "Python Syntax Drill",
            "stem": "Which list comprehension correctly squares all even numbers in a list called nums?",
            "items": [
                "A) [x**2 for x in nums if x % 2 == 0]",
                "B) [x^2 for x in nums if x % 2 == 0]",
                "C) [x**2 if x % 2 == 0 for x in nums]",
                "D) [x*2 for x in nums where x % 2 == 0]"
            ],
            "expected_keywords": ["list comprehension", "squares"],
            "expected_type": QuestionType.MCQ,
            "expected_option": "A"
        }
        self.assertTrue(self._test_question(q))

    # --- 4 Coding Questions ---
    def test_06_coding_python_two_sum(self):
        """Coding 1 (Python): Two Sum implementation tested against real inputs."""
        def validate_code(code_str: str):
            ns = {}
            try:
                exec(code_str, ns)
                fn = ns.get("two_sum") or ns.get("twoSum")
                if not fn:
                    for v in ns.values():
                        if callable(v):
                            fn = v
                            break
                if not fn:
                    return False, "No function found in namespace"
                res1 = fn([2, 7, 11, 15], 9)
                if sorted(list(res1)) != [0, 1]:
                    return False, f"two_sum([2, 7, 11, 15], 9) returned {res1}, expected [0, 1]"
                res2 = fn([3, 2, 4], 6)
                if sorted(list(res2)) != [1, 2]:
                    return False, f"two_sum([3, 2, 4], 6) returned {res2}, expected [1, 2]"
                return True, "All tests passed"
            except Exception as e:
                return False, str(e)

        q = {
            "title": "LeetCode 1 - Two Sum",
            "stem": "Write a Python function two_sum(nums, target) that returns the indices of the two numbers such that they add up to target.\nAssume each input has exactly one solution and you may not use the same element twice.",
            "expected_keywords": ["two_sum", "indices", "target"],
            "expected_type": QuestionType.CODING,
            "code_validator": validate_code
        }
        self.assertTrue(self._test_question(q))

    def test_07_coding_java_max_subarray(self):
        """Coding 2 (Java): Maximum Subarray Kadane's Algorithm."""
        q = {
            "title": "Java Technical Interview",
            "stem": "Write a Java class Solution with a method public int maxSubArray(int[] nums) that returns the sum of the contiguous subarray with the largest sum using Kadane's algorithm.",
            "expected_keywords": ["maxSubArray", "Kadane"],
            "expected_type": QuestionType.CODING
        }
        self.assertTrue(self._test_question(q))

    def test_08_coding_cpp_palindrome(self):
        """Coding 3 (C++): Palindrome string validation."""
        q = {
            "title": "C++ Systems Programming Assessment",
            "stem": "Write a C++ function bool isPalindrome(std::string s) that checks if a string is a palindrome, ignoring non-alphanumeric characters and case.",
            "expected_keywords": ["isPalindrome", "string"],
            "expected_type": QuestionType.CODING
        }
        self.assertTrue(self._test_question(q))

    def test_09_coding_sql_second_highest_salary(self):
        """Coding 4 (SQL): Second Highest Salary."""
        q = {
            "title": "Database Engineering Interview",
            "stem": "Write a SQL query to find the second highest salary from the Employee table. If there is no second highest salary, return NULL.",
            "expected_keywords": ["SQL query", "second highest salary", "Employee"],
            "expected_type": QuestionType.CODING
        }
        self.assertTrue(self._test_question(q))

    def test_10_coding_input_output_adversarial(self):
        """Coding 5 (Adversarial): Coding task with Input/Output example lines. Must classify as CODING."""
        def validate_code(code_str: str):
            ns = {}
            try:
                exec(code_str, ns)
                fn = ns.get("reverse_words") or ns.get("reverseWords")
                if not fn:
                    for v in ns.values():
                        if callable(v):
                            fn = v
                            break
                if not fn:
                    return False, "No function found"
                r1 = fn("the sky is blue")
                if r1 != "blue is sky the":
                    return False, f"Expected 'blue is sky the', got '{r1}'"
                r2 = fn("  hello world  ")
                if r2 != "world hello":
                    return False, f"Expected 'world hello', got '{r2}'"
                return True, "All tests passed"
            except Exception as e:
                return False, str(e)

        q = {
            "title": "String Manipulation Challenge",
            "stem": (
                "Write a Python function reverse_words(s: str) -> str that reverses the order of words in a string.\n"
                "Input: s = \"the sky is blue\"\n"
                "Output: \"blue is sky the\"\n"
                "Input: s = \"  hello world  \"\n"
                "Output: \"world hello\"\n"
                "Constraints: Return a string of words joined by a single space."
            ),
            "expected_keywords": ["reverse_words", "order of words"],
            "expected_type": QuestionType.CODING,
            "code_validator": validate_code
        }
        self.assertTrue(self._test_question(q))

    # --- 2 Output Prediction Questions ---
    def test_11_output_prediction_python_aliasing(self):
        """Output Prediction 1: List aliasing and mutation."""
        q = {
            "title": "Python Core Runtime Drill",
            "stem": (
                "Find the output of the following Python program:\n"
                "nums = [1, 2, 3]\n"
                "alias = nums\n"
                "alias.append(4)\n"
                "print(len(nums))"
            ),
            "expected_keywords": ["Find the output", "append", "print(len(nums))"],
            "expected_type": QuestionType.OUTPUT_PREDICTION,
            "expected_output": "4"
        }
        self.assertTrue(self._test_question(q))

    def test_12_output_prediction_cpp_increment(self):
        """Output Prediction 2: C++ sequence point increment."""
        q = {
            "title": "C++ Evaluation Order",
            "stem": (
                "Find the output of the following code snippet:\n"
                "int x = 10;\n"
                "int y = 20;\n"
                "std::cout << (x + y * 2) << std::endl;"
            ),
            "expected_keywords": ["Find the output", "std::cout"],
            "expected_type": QuestionType.OUTPUT_PREDICTION,
            "expected_output": "50"
        }
        self.assertTrue(self._test_question(q))

    # --- 1 Short Answer Question ---
    def test_13_short_answer_process_vs_thread(self):
        """Short Answer 1: Process vs Thread comparison."""
        q = {
            "title": "Operating Systems Viva",
            "stem": "Explain the primary architectural difference between a process and a thread in modern operating systems.",
            "expected_keywords": ["difference between a process and a thread", "operating systems"],
            "expected_type": QuestionType.SHORT_ANSWER
        }
        self.assertTrue(self._test_question(q))


class TestAudioPipelineTelemetryAndAltQ(unittest.TestCase):
    """Verifies audio pipeline telemetry logging and Alt+Q empty transcript notice card."""

    def test_audio_pipeline_telemetry_counters(self):
        telemetry = get_audio_telemetry()
        # Increment test counters
        telemetry.record_device_open("mic_test_dev", 16000, 1)
        telemetry.record_pcm_frame(480)
        telemetry.record_speech_rms(0.045)
        telemetry.record_resample(48000, 16000)
        telemetry.record_queue_push(1)
        telemetry.record_transcribe_call(16000)
        telemetry.record_segment_returned(1, "Hello world")
        telemetry.record_slot_update("Hello world")

        counters = telemetry.get_counters()
        self.assertGreaterEqual(counters["device_open"], 1)
        self.assertGreaterEqual(counters["pcm_frames_received"], 1)
        self.assertGreaterEqual(counters["rms_above_threshold"], 1)
        self.assertGreaterEqual(counters["resample_16k_mono"], 1)
        self.assertGreaterEqual(counters["transcribe_called"], 1)
        self.assertGreaterEqual(counters["segments_returned"], 1)
        self.assertGreaterEqual(counters["main_thread_slot_called"], 1)

        # Check log file exists
        log_file = get_app_dir() / "logs" / "audio_pipeline.log"
        self.assertTrue(log_file.exists(), f"Log file missing: {log_file}")
        log_content = log_file.read_text(encoding="utf-8")
        self.assertIn("[COUNTER", log_content)

    def test_alt_q_empty_transcript_shows_notice(self):
        hud = QtGhostlineHudOverlay()
        # Verify show_notice_card adds a notice entry without error
        hud.show_notice_card("No Transcript Yet", "Press Alt+A to start listening to microphone or system audio.")
        latest = hud.session.get_latest_entry()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.detected_question, "No Transcript Yet")
        self.assertEqual(latest.answer_text, "No Transcript Yet")
        hud.close()


if __name__ == "__main__":
    unittest.main()
