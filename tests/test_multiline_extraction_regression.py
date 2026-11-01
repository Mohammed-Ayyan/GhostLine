"""
Regression test suite for Ghostline Multiline MCQ Question Extraction.
Verifies Tests A through H covering:
- Test A: 2-line wrapped question (first line ends mid-sentence, second with ?).
- Test B: 4-line question spanning across multiple lines before options.
- Test C: Question without a question mark (imperative/declarative stem).
- Test D: Cursor placed on the last line or on an answer option.
- Test E: Options separated by an 'Options:' header (header must not leak into stem).
- Test F: Two questions displayed simultaneously (isolates target card without bleeding).
- Test G: Coding question with indentation, code blocks, and braces.
- Test H: Incomplete capture where top line touches crop boundary (truncation detection).
"""

import unittest
from ghostline.core.ocr_engine import (
    parse_question_structure,
    extract_target_question_lines,
    sort_lines_in_reading_order,
    _is_option_header,
    is_option_marker
)


class TestMultilineExtractionRegression(unittest.TestCase):

    def test_a_two_line_wrapped_question(self):
        """
        Test A: A 2-line wrapped question where the first line ends mid-sentence
        and the second line ends with a question mark.
        Both lines must be preserved in question_text in correct reading order.
        """
        line_boxes = [
            {"text": "Which of the following data structures is most suitable for implementing a priority queue when elements", "x": 60, "y": 80, "width": 800, "height": 24},
            {"text": "need to be inserted and removed according to their priority?", "x": 60, "y": 115, "width": 550, "height": 24},
            {"text": "A. Stack", "x": 60, "y": 160, "width": 120, "height": 22},
            {"text": "B. Queue", "x": 60, "y": 195, "width": 120, "height": 22},
            {"text": "C. Binary Heap", "x": 60, "y": 230, "width": 160, "height": 22},
            {"text": "D. Linked List", "x": 60, "y": 265, "width": 150, "height": 22},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        parsed = parse_question_structure(ocr_data, cursor_pos=(400, 200))

        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertIn("Which of the following data structures is most suitable", parsed.question_text)
        self.assertIn("removed according to their priority?", parsed.question_text)
        self.assertTrue(parsed.question_text.startswith("Which of the following"))
        self.assertTrue(parsed.question_text.endswith("priority?"))
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["A"], "Stack")
        self.assertEqual(parsed.options["C"], "Binary Heap")

    def test_b_four_line_question_spanning_multiple_lines(self):
        """
        Test B: A 4-line question spanning across multiple lines before options appear.
        All 4 lines must be combined in chronological top-to-bottom reading order.
        """
        line_boxes = [
            {"text": "A distributed system uses the Raft consensus algorithm", "x": 50, "y": 60, "width": 600, "height": 22},
            {"text": "to maintain a replicated state machine across five nodes.", "x": 50, "y": 90, "width": 620, "height": 22},
            {"text": "If a network partition isolates the leader with only one follower,", "x": 50, "y": 120, "width": 650, "height": 22},
            {"text": "how many nodes are required in the other partition to achieve majority quorum?", "x": 50, "y": 150, "width": 700, "height": 22},
            {"text": "A) 2 nodes", "x": 50, "y": 195, "width": 130, "height": 20},
            {"text": "B) 3 nodes", "x": 50, "y": 225, "width": 130, "height": 20},
            {"text": "C) 4 nodes", "x": 50, "y": 255, "width": 130, "height": 20},
            {"text": "D) 5 nodes", "x": 50, "y": 285, "width": 130, "height": 20},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        parsed = parse_question_structure(ocr_data, cursor_pos=(200, 150))

        self.assertTrue(parsed.is_valid_question)
        self.assertIn("Raft consensus algorithm", parsed.question_text)
        self.assertIn("replicated state machine", parsed.question_text)
        self.assertIn("network partition isolates", parsed.question_text)
        self.assertIn("majority quorum?", parsed.question_text)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["B"], "3 nodes")

    def test_c_question_without_question_mark(self):
        """
        Test C: A question without a question mark (imperative/declarative stem).
        Must extract full multiline stem without requiring a '?'.
        """
        line_boxes = [
            {"text": "Consider the operational properties of balanced binary search trees.", "x": 70, "y": 100, "width": 720, "height": 24},
            {"text": "Select the correct statement regarding the time complexity of AVL tree rotation operations.", "x": 70, "y": 135, "width": 820, "height": 24},
            {"text": "1. Rotation requires O(1) constant time.", "x": 70, "y": 180, "width": 350, "height": 22},
            {"text": "2. Rotation requires O(log n) logarithmic time.", "x": 70, "y": 215, "width": 390, "height": 22},
            {"text": "3. Rotation requires O(n) linear time.", "x": 70, "y": 250, "width": 330, "height": 22},
            {"text": "4. Rotation is not supported in AVL trees.", "x": 70, "y": 285, "width": 380, "height": 22},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        parsed = parse_question_structure(ocr_data, cursor_pos=(300, 120))

        self.assertTrue(parsed.is_valid_question)
        self.assertTrue(parsed.is_multiple_choice)
        self.assertIn("balanced binary search trees", parsed.question_text)
        self.assertIn("AVL tree rotation operations", parsed.question_text)
        self.assertEqual(len(parsed.options), 4)

    def test_d_cursor_placed_on_last_line_or_option(self):
        """
        Test D: Cursor placed on the last line or on an answer option.
        Preceding lines above the cursor must NOT be dropped.
        """
        line_boxes = [
            {"text": "Which of the following sorting algorithms provides guaranteed O(n log n) time complexity", "x": 80, "y": 100, "width": 750, "height": 24},
            {"text": "in all cases while requiring O(1) auxiliary space?", "x": 80, "y": 135, "width": 500, "height": 24},
            {"text": "A. Merge Sort", "x": 80, "y": 180, "width": 140, "height": 22},
            {"text": "B. Quick Sort", "x": 80, "y": 215, "width": 140, "height": 22},
            {"text": "C. Heap Sort", "x": 80, "y": 250, "width": 130, "height": 22},
            {"text": "D. Bubble Sort", "x": 80, "y": 285, "width": 150, "height": 22},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        # Cursor sits right on Option D (y=285)
        parsed = parse_question_structure(ocr_data, cursor_pos=(120, 285))

        self.assertTrue(parsed.is_valid_question)
        self.assertIn("Which of the following sorting algorithms", parsed.question_text)
        self.assertIn("auxiliary space?", parsed.question_text)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["C"], "Heap Sort")

    def test_e_options_with_header_and_blank_lines(self):
        """
        Test E: A question with answer options preceded by an 'Options:' or 'Select one:' header.
        The header must NOT leak into the question stem or options.
        """
        line_boxes = [
            {"text": "Which SQL clause is used to filter groups of rows after an aggregation function has been applied?", "x": 50, "y": 80, "width": 850, "height": 24},
            {"text": "Options:", "x": 50, "y": 125, "width": 80, "height": 20},
            {"text": "A. WHERE", "x": 50, "y": 160, "width": 120, "height": 22},
            {"text": "B. HAVING", "x": 50, "y": 195, "width": 120, "height": 22},
            {"text": "C. GROUP BY", "x": 50, "y": 230, "width": 140, "height": 22},
            {"text": "D. ORDER BY", "x": 50, "y": 265, "width": 140, "height": 22},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        parsed = parse_question_structure(ocr_data, cursor_pos=(200, 100))

        self.assertTrue(parsed.is_valid_question)
        self.assertNotIn("Options:", parsed.question_text)
        self.assertTrue(parsed.question_text.endswith("applied?"))
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["B"], "HAVING")

    def test_f_two_questions_on_screen_isolation(self):
        """
        Test F: Two questions displayed simultaneously on screen.
        Target question containing the cursor must be isolated without bleeding into or from the other.
        """
        line_boxes = [
            # Question 1 (y=50..220)
            {"text": "Question 1: What is the worst-case search complexity in an unsorted array?", "x": 50, "y": 50, "width": 650, "height": 22},
            {"text": "A. O(1)", "x": 50, "y": 90, "width": 100, "height": 20},
            {"text": "B. O(n)", "x": 50, "y": 120, "width": 100, "height": 20},
            {"text": "C. O(log n)", "x": 50, "y": 150, "width": 120, "height": 20},
            {"text": "D. O(n^2)", "x": 50, "y": 180, "width": 110, "height": 20},
            # Question 2 (y=300..500)
            {"text": "Question 2: Which protocol operates at the Transport Layer of the OSI model", "x": 50, "y": 300, "width": 680, "height": 22},
            {"text": "and provides connection-oriented, reliable byte stream delivery?", "x": 50, "y": 330, "width": 620, "height": 22},
            {"text": "A. UDP", "x": 50, "y": 370, "width": 100, "height": 20},
            {"text": "B. TCP", "x": 50, "y": 400, "width": 100, "height": 20},
            {"text": "C. IP", "x": 50, "y": 430, "width": 90, "height": 20},
            {"text": "D. ICMP", "x": 50, "y": 460, "width": 100, "height": 20},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 900]
        }

        # Cursor is positioned inside Question 2
        parsed_q2 = parse_question_structure(ocr_data, cursor_pos=(200, 350))

        self.assertTrue(parsed_q2.is_valid_question)
        self.assertTrue(parsed_q2.multiple_questions_detected)
        self.assertIn("Transport Layer", parsed_q2.question_text)
        self.assertIn("reliable byte stream delivery?", parsed_q2.question_text)
        self.assertNotIn("unsorted array", parsed_q2.question_text)
        self.assertEqual(len(parsed_q2.options), 4)
        self.assertEqual(parsed_q2.options["B"], "TCP")

    def test_g_coding_question_with_indentation(self):
        """
        Test G: Coding question with indentation and braces.
        Code lines must be preserved formatted with newlines in supporting_passage or stem.
        """
        line_boxes = [
            {"text": "What will be the output of the following Python snippet?", "x": 50, "y": 50, "width": 550, "height": 24},
            {"text": "def compute(vals):", "x": 50, "y": 90, "width": 220, "height": 20},
            {"text": "    total = sum(x for x in vals if x % 2 == 0)", "x": 50, "y": 120, "width": 450, "height": 20},
            {"text": "    return total * 2", "x": 50, "y": 150, "width": 200, "height": 20},
            {"text": "print(compute([1, 2, 3, 4, 5]))", "x": 50, "y": 180, "width": 320, "height": 20},
            {"text": "A. 12", "x": 50, "y": 220, "width": 80, "height": 20},
            {"text": "B. 24", "x": 50, "y": 250, "width": 80, "height": 20},
            {"text": "C. 30", "x": 50, "y": 280, "width": 80, "height": 20},
            {"text": "D. 6", "x": 50, "y": 310, "width": 70, "height": 20},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        parsed = parse_question_structure(ocr_data, cursor_pos=(200, 100))

        self.assertTrue(parsed.is_valid_question)
        self.assertIn("output of the following Python snippet?", parsed.question_text)
        self.assertIn("def compute", parsed.supporting_passage)
        self.assertIn("return total", parsed.supporting_passage)
        self.assertEqual(len(parsed.options), 4)
        self.assertEqual(parsed.options["A"], "12")

    def test_h_incomplete_capture_truncation_detection(self):
        """
        Test H: Incomplete capture where the top line is near the crop boundary (y <= 20).
        The parser must detect boundary proximity and set is_truncated = True with warnings.
        """
        line_boxes = [
            {"text": "elements need to be inserted and removed according to their priority?", "x": 50, "y": 10, "width": 600, "height": 24},
            {"text": "A. Stack", "x": 50, "y": 60, "width": 120, "height": 22},
            {"text": "B. Queue", "x": 50, "y": 95, "width": 120, "height": 22},
            {"text": "C. Binary Heap", "x": 50, "y": 130, "width": 160, "height": 22},
            {"text": "D. Linked List", "x": 50, "y": 165, "width": 150, "height": 22},
        ]
        ocr_data = {
            "text": "\n".join(b["text"] for b in line_boxes),
            "lines": [b["text"] for b in line_boxes],
            "line_boxes": line_boxes,
            "image_size": [1200, 800]
        }

        parsed = parse_question_structure(ocr_data, cursor_pos=(200, 50))

        self.assertTrue(parsed.is_truncated)
        self.assertTrue(any("top edge" in w.lower() or "boundary" in w.lower() for w in parsed.warnings))


if __name__ == "__main__":
    unittest.main()

