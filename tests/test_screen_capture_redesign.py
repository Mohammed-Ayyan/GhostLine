import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from ghostline.core.capture import (
    capture_screen,
    get_monitor_bounds_for_point,
    CAPTURE_MODE_CURSOR,
    CAPTURE_MODE_FULL_SCREEN
)
from ghostline.core.ocr_engine import (
    _is_ui_noise,
    _is_meaningful_question,
    parse_question_structure,
    ParsedQuestion
)
from ghostline.core.pipeline import GhostlinePipeline, QuestionExtractionError


class TestScreenCaptureRedesign:
    """
    Focused regression tests for screen capture redesign:
    - Alt + / cursor-centered mode vs Alt + Shift + / full-screen mode
    - Cursor bounding box clamping to monitor boundaries (including multi-monitor / negative offsets)
    - Removal of silent synthetic white image fallback
    - OCR browser UI clutter rejection
    - MCQ option format recognition
    - Support for questions without literal '?'
    - Actionable error on insufficient text near cursor
    """

    def test_cursor_capture_region_clamped_to_monitor_boundaries(self):
        # Mock monitor bounds to 0, 0, 1920, 1080
        with patch("ghostline.core.capture.get_cursor_position", return_value=(1910, 1070)), \
             patch("ghostline.core.capture.get_monitor_bounds_for_point", return_value=(0, 0, 1920, 1080)), \
             patch("ghostline.core.capture.ImageGrab.grab", return_value=Image.new("RGB", (900, 600), (40, 40, 40))):

            _, bbox, diag = capture_screen(mode="cursor", width=900, height=600)

            # Must be strictly clamped within (0, 0, 1920, 1080)
            assert bbox[0] >= 0
            assert bbox[1] >= 0
            assert bbox[2] <= 1920
            assert bbox[3] <= 1080
            assert (bbox[2] - bbox[0]) == 900
            assert (bbox[3] - bbox[1]) == 600

    def test_multi_monitor_negative_coordinates_clamped_correctly(self):
        # Secondary monitor located to the left: (-1920, -200, 0, 880)
        with patch("ghostline.core.capture.get_cursor_position", return_value=(-1900, -150)), \
             patch("ghostline.core.capture.get_monitor_bounds_for_point", return_value=(-1920, -200, 0, 880)), \
             patch("ghostline.core.capture.ImageGrab.grab", return_value=Image.new("RGB", (900, 600), (30, 30, 30))):

            _, bbox, _ = capture_screen(mode="cursor", width=900, height=600)

            # Must stay inside secondary monitor
            assert bbox[0] >= -1920
            assert bbox[1] >= -200
            assert bbox[2] <= 0
            assert bbox[3] <= 880
            assert (bbox[2] - bbox[0]) == 900
            assert (bbox[3] - bbox[1]) == 600

    def test_capture_failure_never_returns_silent_white_image(self):
        # When all capture mechanisms (ImageGrab and GDI) fail, must raise RuntimeError
        with patch("ghostline.core.capture.ImageGrab.grab", side_effect=OSError("screen grab failed")), \
             patch("ghostline.core.capture._gdi_screen_capture", return_value=None):

            with pytest.raises(RuntimeError) as exc_info:
                capture_screen(mode="cursor", width=900, height=600)

            assert "Screen capture failed" in str(exc_info.value)

    def test_ocr_filters_browser_ui_and_taskbar_clutter(self):
        # Browser chrome and taskbar noise
        noise_lines = [
            "https://leetcode.com/problems/two-sum/",
            "chrome://settings",
            "Bookmarks",
            "New Tab",
            "10/26/2026",
            "26-10-2026",
            "11:45 PM",
            "ENG IN",
            "Submit Answer",
            "Next Question",
            "Ghostline",
            "Ask Gemini",
            "Type here to search"
        ]
        for line in noise_lines:
            assert _is_ui_noise(line) is True, f"Failed to filter UI noise: '{line}'"

        # Legitimate questions must NOT be filtered
        valid_lines = [
            "What is the time complexity of quicksort?",
            "Solve for x in 2x + 7 = 21",
            "Given an array of integers nums, return indices of the two numbers.",
            "A. 15",
            "B. 30"
        ]
        for line in valid_lines:
            assert _is_ui_noise(line) is False, f"Valid line falsely marked as noise: '{line}'"

    def test_ocr_recognizes_common_mcq_option_formats(self):
        ocr_text = (
            "What is the output of print(2 ** 3)?\n"
            "A. 6\n"
            "B) 8\n"
            "(C) 9\n"
            "D: 16"
        )
        parsed = parse_question_structure(ocr_text)
        assert parsed.is_valid_question is True
        assert parsed.is_multiple_choice is True
        assert len(parsed.options) == 4
        assert "A" in parsed.options
        assert "B" in parsed.options
        assert "C" in parsed.options
        assert "D" in parsed.options
        assert parsed.options["B"] == "8"

    def test_questions_without_question_mark_supported(self):
        # Coding question without literal '?'
        q1 = "Given an integer array nums, return true if any value appears at least twice in the array."
        is_val, reason = _is_meaningful_question(q1, options={})
        assert is_val is True

        # Imperative math/theory stem without '?'
        q2 = "Solve for x when 3x - 12 = 0:"
        is_val, reason = _is_meaningful_question(q2, options={})
        assert is_val is True

        # Theory explanation without '?'
        q3 = "Explain the fundamental difference between TCP and UDP protocols in modern networking."
        is_val, reason = _is_meaningful_question(q3, options={})
        assert is_val is True

    def test_insufficient_text_near_cursor_shows_actionable_guidance(self):
        mock_llm = MagicMock()
        pipeline = GhostlinePipeline(ollama_client=mock_llm)

        # Blank/empty OCR result
        empty_ocr_img = Image.new("RGB", (900, 600), (255, 255, 255))
        with patch("ghostline.core.pipeline.capture_screen", return_value=(empty_ocr_img, (0, 0, 900, 600), {})), \
             patch("ghostline.core.pipeline.run_native_ocr", return_value={"text": "", "lines": [], "line_boxes": []}):

            with pytest.raises(QuestionExtractionError) as exc_info:
                pipeline.process_from_cursor(capture_mode="cursor")

            err_msg = str(exc_info.value)
            assert "No question text found near cursor" in err_msg
            assert "Alt+Shift+/" in err_msg
