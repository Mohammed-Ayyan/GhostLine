import os
import sys
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.capture import (
    capture_screen,
    get_display_topology,
    get_cursor_position,
    get_monitor_bounds_for_point,
    inspect_capture_environment,
    save_diagnostic_artifacts,
    CAPTURE_MODE_FULL_SCREEN,
    CAPTURE_MODE_ACTIVE_WINDOW,
    CAPTURE_MODE_CURSOR_MONITOR,
    CAPTURE_MODE_PRIMARY_MONITOR,
    CAPTURE_MODE_CURSOR
)
from ghostline.core.ocr_engine import (
    parse_question_structure,
    preprocess_image_for_ocr,
    _detect_multi_column_order,
    _check_boundary_truncation,
    _is_ui_noise,
    ParsedQuestion
)
from ghostline.core.llm_client import (
    validate_code_syntax,
    extract_and_normalize_code,
    AnswerResult,
    OllamaClient
)
from ghostline.ui.presentation import (
    build_answer_presentation,
    PresentedAnswer,
    TYPE_MCQ,
    TYPE_CODE,
    TYPE_UNCERTAIN
)
from ghostline.ui.hud_overlay import GhostlineHudOverlay, GhostlineHudOverlay
from ghostline.core.pipeline import GhostlinePipeline, GhostlinePipeline

class TestCaptureModesAndTopology(unittest.TestCase):
    def test_display_topology_detection(self):
        """Verifies multi-monitor topology, virtual screen metrics, and DPI scale queries."""
        topology = get_display_topology()
        self.assertIn("monitor_count", topology)
        self.assertIn("primary_screen", topology)
        self.assertIn("virtual_screen", topology)
        self.assertIn("dpi_scaling", topology)
        self.assertGreaterEqual(topology["monitor_count"], 1)
        self.assertGreaterEqual(topology["dpi_scaling"], 0.5)

        vx, vy, vr, vb = topology["virtual_screen"]
        self.assertGreater(vr, vx)
        self.assertGreater(vb, vy)

    def test_cursor_position_and_monitor_lookup(self):
        """Verifies cursor coordinates and corresponding monitor bounding bounds."""
        cx, cy = get_cursor_position()
        self.assertIsInstance(cx, int)
        self.assertIsInstance(cy, int)

        mon_rect = get_monitor_bounds_for_point(cx, cy)
        self.assertEqual(len(mon_rect), 4)
        ml, mt, mr, mb = mon_rect
        self.assertGreater(mr, ml)
        self.assertGreater(mb, mt)

    def test_capture_mode_full_screen(self):
        """Tests full-screen virtual desktop capture mode."""
        img, bbox, diag = capture_screen(mode=CAPTURE_MODE_FULL_SCREEN)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(diag["effective_mode"], CAPTURE_MODE_FULL_SCREEN)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)
        self.assertEqual(bbox[2] - bbox[0], img.width)
        self.assertEqual(bbox[3] - bbox[1], img.height)

    def test_capture_mode_cursor_and_active_window(self):
        """Tests cursor region capture and active window fallback."""
        img_cursor, bbox_c, diag_c = capture_screen(mode=CAPTURE_MODE_CURSOR, width=400, height=300)
        self.assertEqual(img_cursor.size, (400, 300))
        self.assertEqual(diag_c["effective_mode"], CAPTURE_MODE_CURSOR)

        img_win, bbox_w, diag_w = capture_screen(mode=CAPTURE_MODE_ACTIVE_WINDOW)
        self.assertIsInstance(img_win, Image.Image)
        self.assertIn(diag_w["effective_mode"], [CAPTURE_MODE_ACTIVE_WINDOW, "cursor_monitor_fallback"])

    def test_multi_monitor_negative_coordinates(self):
        """Simulates virtual screen with secondary monitor to the left (negative X)."""
        custom_bbox = (-1920, 0, 0, 1080)
        img, bbox, diag = capture_screen(custom_bbox=custom_bbox)
        self.assertEqual(bbox, custom_bbox)
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(diag["effective_mode"], "custom_bbox")

    def test_blank_frame_and_diagnostic_artifacts(self):
        """Verifies uniform pixel extrema detection and diagnostic artifact dumping."""
        blank_img = Image.new("RGB", (200, 200), (0, 0, 0))
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "test_diagnostics_out"
        out_dir = save_diagnostic_artifacts(
            screenshot=blank_img,
            ocr_data={"text": "Diagnostic test", "lines": ["Diagnostic test"]},
            diag_info={"is_blank_frame": True},
            directory=temp_dir
        )
        self.assertTrue((out_dir / "latest_capture.png").exists())
        self.assertTrue((out_dir / "latest_ocr.json").exists())
        self.assertTrue((out_dir / "latest_metadata.json").exists())

        # Cleanup
        for f in out_dir.iterdir():
            f.unlink()
        out_dir.rmdir()


class TestDocumentStructureAndOcr(unittest.TestCase):
    def test_ui_noise_filtering(self):
        """Verifies that timers, exam headers, and buttons are filtered from questions."""
        self.assertTrue(_is_ui_noise("Time Remaining: 14:22"))
        self.assertTrue(_is_ui_noise("00:45:10"))
        self.assertTrue(_is_ui_noise("Timer: 12:00"))
        self.assertTrue(_is_ui_noise("Submit Answer"))
        self.assertTrue(_is_ui_noise("Next Question >"))
        self.assertTrue(_is_ui_noise("Question 4 of 50"))
        self.assertTrue(_is_ui_noise("Clear Selection"))
        self.assertTrue(_is_ui_noise("Proctored Exam - Webcam Active"))
        self.assertTrue(_is_ui_noise("Section A : Quantitative"))

        # Legitimate questions are NOT noise
        self.assertFalse(_is_ui_noise("Which algorithm has O(n log n) average time complexity?"))
        self.assertFalse(_is_ui_noise("A) Quicksort"))
        self.assertFalse(_is_ui_noise("def count_vowels(s):"))

    def test_multi_column_spatial_layout_order(self):
        """
        Verifies that a 2-column document (left column: question, right column: choices)
        is ordered column-by-column rather than interlaced horizontally.
        """
        # Left column (x=50..400)
        box_left1 = {"text": "Question 1: What is polymorphism?", "x": 50, "y": 100, "width": 300, "height": 20}
        box_left2 = {"text": "In object oriented programming...", "x": 50, "y": 140, "width": 280, "height": 20}
        # Right column (x=600..900)
        box_right1 = {"text": "A) Many forms", "x": 600, "y": 100, "width": 150, "height": 20}
        box_right2 = {"text": "B) Single inheritance", "x": 600, "y": 140, "width": 180, "height": 20}

        unordered_boxes = [box_left1, box_right1, box_left2, box_right2]
        ordered = _detect_multi_column_order(unordered_boxes, image_width=1000)
        ordered_texts = [b["text"] for b in ordered]

        # Column 1 should precede Column 2
        self.assertEqual(ordered_texts[0], "Question 1: What is polymorphism?")
        self.assertEqual(ordered_texts[1], "In object oriented programming...")
        self.assertEqual(ordered_texts[2], "A) Many forms")
        self.assertEqual(ordered_texts[3], "B) Single inheritance")

    def test_boundary_truncation_detection(self):
        """Verifies warning when text directly touches or extends to capture borders."""
        # Box touching bottom boundary (y + h = 598 in 600h image)
        boxes_touching = [
            {"text": "What is the capital of...", "x": 50, "y": 100, "width": 300, "height": 20},
            {"text": "A) Paris", "x": 50, "y": 580, "width": 100, "height": 20}
        ]
        is_trunc, warnings = _check_boundary_truncation(boxes_touching, [800, 600])
        self.assertTrue(is_trunc)
        self.assertTrue(any("bottom boundary" in w for w in warnings))

        # Safe boxes away from borders
        boxes_safe = [
            {"text": "What is the capital of...", "x": 50, "y": 50, "width": 300, "height": 20},
            {"text": "A) Paris", "x": 50, "y": 100, "width": 100, "height": 20}
        ]
        is_trunc_safe, warnings_safe = _check_boundary_truncation(boxes_safe, [800, 600])
        self.assertFalse(is_trunc_safe)
        self.assertEqual(len(warnings_safe), 0)

    def test_contrast_preprocessing(self):
        """Verifies adaptive contrast enhancement on low-contrast captures."""
        # Low contrast image (narrow range between 180 and 210)
        low_contrast_img = Image.new("RGB", (300, 100), color=(190, 190, 190))
        d = ImageDraw.Draw(low_contrast_img)
        d.text((20, 20), "Low contrast test text", fill=(210, 210, 210))

        processed, diag = preprocess_image_for_ocr(low_contrast_img, enhance_contrast=True)
        self.assertTrue(diag["contrast_enhanced"])


class TestRobustQuestionParser(unittest.TestCase):
    def test_unlabelled_options_with_large_gaps_and_intervening_content(self):
        """
        Verifies unlabelled choices separated by intervening instructions and gaps.
        """
        raw_ocr = {
            "text": (
                "Time Remaining: 24:15\n"
                "Question 8: Which cloud architecture pattern ensures high availability across regions?\n"
                "Note: Consider active-active database replication and automated failover.\n"
                "Please choose the best architecture:\n"
                "Multi-region Active-Active Deployment\n"
                "Single Zone Monolithic Server\n"
                "Cold Standby in Secondary Region\n"
                "Nightly Backup to Object Storage\n"
                "Submit Answer"
            ),
            "lines": [
                "Time Remaining: 24:15",
                "Question 8: Which cloud architecture pattern ensures high availability across regions?",
                "Note: Consider active-active database replication and automated failover.",
                "Please choose the best architecture:",
                "Multi-region Active-Active Deployment",
                "Single Zone Monolithic Server",
                "Cold Standby in Secondary Region",
                "Nightly Backup to Object Storage",
                "Submit Answer"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertTrue(parsed.is_unlabelled_mcq)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["1"], "Multi-region Active-Active Deployment")
        self.assertEqual(parsed.options["2"], "Single Zone Monolithic Server")
        self.assertEqual(parsed.options["3"], "Cold Standby in Secondary Region")
        self.assertEqual(parsed.options["4"], "Nightly Backup to Object Storage")
        # Ensure timers and submit button are excluded
        self.assertNotIn("24:15", parsed.question_text)
        self.assertNotIn("Submit", parsed.options.values())

    def test_disambiguate_question_number_from_options(self):
        """
        Verifies that '3. What is...' is recognized as question number and not Option 3.
        """
        raw_ocr = {
            "text": (
                "3. Which data structure implements LIFO ordering?\n"
                "1) Queue\n"
                "2) Stack\n"
                "3) Array\n"
                "4) Tree"
            ),
            "lines": [
                "3. Which data structure implements LIFO ordering?",
                "1) Queue",
                "2) Stack",
                "3) Array",
                "4) Tree"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["1"], "Queue")
        self.assertEqual(parsed.options["2"], "Stack")
        self.assertEqual(parsed.options["3"], "Array")
        self.assertEqual(parsed.options["4"], "Tree")
        self.assertIn("LIFO ordering", parsed.question_text)

    def test_roman_numeral_and_bracket_labels(self):
        """Verifies (i), (ii), (iii), (iv) and [A], [B] option labeling formats."""
        raw_ocr = {
            "text": (
                "Identify the correct CPU scheduling algorithm designed for time-sharing systems:\n"
                "(i) First-Come First-Served\n"
                "(ii) Shortest Job Next\n"
                "(iii) Round Robin\n"
                "(iv) Priority Scheduling"
            ),
            "lines": [
                "Identify the correct CPU scheduling algorithm designed for time-sharing systems:",
                "(i) First-Come First-Served",
                "(ii) Shortest Job Next",
                "(iii) Round Robin",
                "(iv) Priority Scheduling"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertIn("(iii)", parsed.options)
        self.assertEqual(parsed.options["(iii)"], "Round Robin")

    def test_multiple_questions_screen_isolation(self):
        """
        Verifies that multiple questions on the same screen are NOT silently merged into one.
        """
        raw_ocr = {
            "text": (
                "1. What is the complexity of binary search?\n"
                "A) O(1)\n"
                "B) O(log n)\n"
                "C) O(n)\n\n"
                "2. Which protocol operates at the transport layer?\n"
                "A) TCP\n"
                "B) IP\n"
                "C) HTTP"
            ),
            "lines": [
                "1. What is the complexity of binary search?",
                "A) O(1)",
                "B) O(log n)",
                "C) O(n)",
                "2. Which protocol operates at the transport layer?",
                "A) TCP",
                "B) IP",
                "C) HTTP"
            ]
        }
        parsed = parse_question_structure(raw_ocr)
        self.assertTrue(parsed.multiple_questions_detected)
        self.assertEqual(len(parsed.detected_questions), 2)
        # Should focus cleanly on primary question 1 without merging question 2
        self.assertIn("binary search", parsed.question_text)
        self.assertNotIn("transport layer", parsed.question_text)
        self.assertIn("B", parsed.options)
        self.assertEqual(parsed.options["B"], "O(log n)")


class TestProgrammingQuestionProcessing(unittest.TestCase):
    def test_structured_coding_problem_extraction(self):
        """
        Verifies parsing of a programming question into separate structured fields:
        title, statement, constraints, examples, starter code, and requested language.
        """
        coding_text = (
            "Problem: Reverse Words in String\n"
            "Given an input string s, reverse the order of the words.\n"
            "Constraints:\n"
            "• 1 <= s.length <= 10^4\n"
            "• s contains English letters, digits, and spaces\n"
            "Example 1:\n"
            "Input: s = \"the sky is blue\"\n"
            "Output: \"blue is sky the\"\n"
            "Starter Code:\n"
            "def reverseWords(s: str) -> str:\n"
            "    pass"
        )
        raw_ocr = {"text": coding_text, "lines": coding_text.splitlines()}
        parsed = parse_question_structure(raw_ocr)

        self.assertEqual(parsed.question_type, "programming")
        self.assertEqual(parsed.title, "Reverse Words in String")
        self.assertIn("reverse the order of the words", parsed.problem_statement)
        self.assertEqual(len(parsed.constraints), 2)
        self.assertIn("1 <= s.length <= 10^4", parsed.constraints[0])
        self.assertEqual(len(parsed.examples), 1)
        self.assertIn("the sky is blue", parsed.examples[0]["input"])
        self.assertIn("blue is sky the", parsed.examples[0]["output"])
        self.assertIn("def reverseWords", parsed.starter_code)
        self.assertEqual(parsed.requested_language, "python")

    def test_python_code_syntax_validation(self):
        """Tests that valid Python code passes syntax check and syntax errors are detected."""
        valid_python = (
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        diff = target - num\n"
            "        if diff in seen:\n"
            "            return [seen[diff], i]\n"
            "        seen[num] = i\n"
            "    return []"
        )
        is_valid, err = validate_code_syntax(valid_python, "python")
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        # Invalid Python (missing colon and bad indentation)
        invalid_python = "def broken_func(x)\nreturn x + 1"
        is_invalid, err_msg = validate_code_syntax(invalid_python, "python")
        self.assertFalse(is_invalid)
        self.assertIn("SyntaxError", err_msg)

    def test_non_python_bracket_balancing(self):
        """Tests bracket and string literal balancing for JavaScript / C++ / Java code."""
        valid_js = (
            "function binarySearch(arr, x) {\n"
            "    let l = 0, r = arr.length - 1;\n"
            "    while (l <= r) {\n"
            "        let m = Math.floor((l + r) / 2);\n"
            "        if (arr[m] === x) return m;\n"
            "        else if (arr[m] < x) l = m + 1;\n"
            "        else r = m - 1;\n"
            "    }\n"
            "    return -1;\n"
            "}"
        )
        is_valid_js, _ = validate_code_syntax(valid_js, "javascript")
        self.assertTrue(is_valid_js)

        # Mismatched bracket
        broken_js = "function test() { return (arr[0]; }"
        is_broken, err_js = validate_code_syntax(broken_js, "javascript")
        self.assertFalse(is_broken)
        self.assertIn("bracket", err_js.lower())

    def test_real_newlines_and_indentation_preservation(self):
        """Verifies that escaped newlines are converted to real ASCII newlines preserving indentation."""
        escaped_payload = "def solution():\\n    x = 10\\n    y = 20\\n    return x + y"
        code, lang, _ = extract_and_normalize_code(escaped_payload, "python")
        self.assertNotIn(r"\n", code)
        self.assertIn("\n    x = 10\n", code)
        self.assertEqual(code.count("\n"), 3)


class TestHudPresentationAndStaleProtection(unittest.TestCase):
    def test_mcq_presentation_headline_and_clipboard(self):
        """Verifies clean option selection formatting ('Option B: Mars') and clipboard text."""
        parsed_q = ParsedQuestion(
            question_text="Which planet is known as the Red Planet?",
            options={"A": "Venus", "B": "Mars", "C": "Jupiter"},
            is_multiple_choice=True
        )
        ans = AnswerResult(
            source_option_label="B",
            option_text="Mars",
            explanation="Mars appears red due to iron oxide on its surface.",
            is_validated=True,
            is_multiple_choice=True
        )
        pres = build_answer_presentation(parsed_q, ans)
        self.assertEqual(pres.badge, "B")
        self.assertEqual(pres.headline, "Option B: Mars")
        self.assertIn("Option B: Mars", pres.formatted_clipboard_text)
        self.assertIn("iron oxide", pres.formatted_clipboard_text)

    def test_code_presentation_and_clipboard(self):
        """Verifies code presentation format, language badge, and clipboard fences."""
        ans = AnswerResult(
            source_option_label="Code",
            option_text="def solve(): pass",
            explanation="Greedy approach in O(n) time.",
            is_validated=True,
            code_snippet="def solve():\n    return 42",
            code_language="python",
            question_type="code"
        )
        pres = build_answer_presentation(None, ans)
        self.assertEqual(pres.question_type, TYPE_CODE)
        self.assertEqual(pres.badge, "Code")
        self.assertTrue(pres.has_code)
        self.assertIn("```python\ndef solve():\n    return 42\n```", pres.formatted_clipboard_text)

    def test_hud_stale_solve_id_protection(self):
        """Verifies that older solve IDs cannot overwrite newer HUD state."""
        hud = GhostlineHudOverlay()
        s1 = hud.start_solve()
        s2 = hud.start_solve()
        self.assertEqual(s1, 1)
        self.assertEqual(s2, 2)

        # Mock root for after method
        class MockRoot:
            def __init__(self):
                self.calls = []
            def after(self, ms, func, *args):
                self.calls.append((func, args))

        hud.root = MockRoot()
        # Outdated state update from solve 1 should be ignored
        hud.set_state("answer", text="Stale Answer", solve_id=s1)
        self.assertEqual(len(hud.root.calls), 0)

        # Current state update from solve 2 should be accepted
        hud.set_state("answer", text="Fresh Answer", solve_id=s2)
        self.assertEqual(len(hud.root.calls), 1)

if __name__ == "__main__":
    unittest.main()
