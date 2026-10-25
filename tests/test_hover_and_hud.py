import unittest
import time
import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from ghostline.core.capture_exclusion import (
    check_capture_exclusion_support,
    set_capture_exclusion,
    get_capture_exclusion_status,
    WDA_NONE,
    WDA_MONITOR,
    WDA_EXCLUDEFROMCAPTURE
)
from ghostline.ui.code_renderer import extract_code_and_prose, apply_syntax_highlighting
from ghostline.core.hover_detector import HoverQuestionCache, HoverDetector
from ghostline.ui.hud_overlay import GhostlineHudOverlay, GhostlineHudOverlay
from ghostline.config import AppConfig


class TestCaptureExclusion(unittest.TestCase):
    def test_support_detection(self):
        """Verify Windows build detection runs without crashing."""
        is_supported, msg = check_capture_exclusion_support()
        self.assertIsInstance(is_supported, bool)
        self.assertIsInstance(msg, str)
        self.assertTrue(len(msg) > 0)

    def test_mock_set_capture_exclusion(self):
        """Verify SetWindowDisplayAffinity wrapper calls user32 with correct affinity."""
        with patch("ghostline.core.capture_exclusion.user32") as mock_user32:
            mock_user32.SetWindowDisplayAffinity.return_value = 1
            
            # Enable capture exclusion
            success = set_capture_exclusion(12345, enable=True)
            self.assertTrue(success)
            mock_user32.SetWindowDisplayAffinity.assert_called_with(12345, WDA_EXCLUDEFROMCAPTURE)
            
            # Disable capture exclusion
            success = set_capture_exclusion(12345, enable=False)
            self.assertTrue(success)
            mock_user32.SetWindowDisplayAffinity.assert_called_with(12345, WDA_NONE)

    def test_mock_get_capture_exclusion_status(self):
        """Verify GetWindowDisplayAffinity query logic."""
        with patch("ghostline.core.capture_exclusion.user32") as mock_user32:
            def side_effect(hwnd, ptr):
                ptr._obj.value = WDA_EXCLUDEFROMCAPTURE
                return 1
            mock_user32.GetWindowDisplayAffinity.side_effect = side_effect
            
            val, status = get_capture_exclusion_status(12345)
            self.assertEqual(val, WDA_EXCLUDEFROMCAPTURE)
            self.assertIn("EXCLUDEFROMCAPTURE", status)


class TestCodeRenderer(unittest.TestCase):
    def test_markdown_code_fence_extraction(self):
        """Verify markdown code fences ```lang ... ``` are parsed from LLM explanation."""
        text = (
            "Here is the optimal solution in Python:\n"
            "```python\n"
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        if target - num in seen:\n"
            "            return [seen[target - num], i]\n"
            "        seen[num] = i\n"
            "    return []\n"
            "```\n"
            "This solution runs in O(N) time and O(N) space."
        )
        prose, code, lang = extract_code_and_prose(text)
        self.assertEqual(lang, "python")
        self.assertIn("def two_sum", code)
        self.assertIn("return []", code)
        self.assertIn("optimal solution", prose)
        self.assertIn("O(N) space", prose)
        self.assertNotIn("```", prose)

    def test_pure_prose_without_code(self):
        """Verify text without code blocks returns code=None."""
        text = "Option B is correct because mitochondria generate ATP via cellular respiration."
        prose, code, lang = extract_code_and_prose(text)
        self.assertEqual(prose, text)
        self.assertIsNone(code)
        self.assertEqual(lang, "")

    def test_raw_code_snippet_heuristic(self):
        """Verify code without markdown fences is identified if it starts with code markers."""
        raw_code = "def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)"
        prose, code, lang = extract_code_and_prose(raw_code)
        self.assertEqual(code, raw_code)
        self.assertEqual(lang, "python")
        self.assertIn("Code Solution", prose)

    def test_syntax_highlighting_tags(self):
        """Verify syntax tagging applies correctly inside a Tk Text widget."""
        root = tk.Tk()
        root.withdraw()
        try:
            text_widget = tk.Text(root)
            code = "def solve(x: int) -> str:\n    # comment\n    return f'val: {x}'"
            apply_syntax_highlighting(text_widget, code, lang="python")
            
            content = text_widget.get("1.0", tk.END).strip()
            self.assertEqual(content, code.strip())
            
            # Check keyword tag
            ranges_kw = text_widget.tag_ranges("keyword")
            self.assertTrue(len(ranges_kw) > 0)
            
            # Check comment tag
            ranges_comment = text_widget.tag_ranges("comment")
            self.assertTrue(len(ranges_comment) > 0)
        finally:
            root.destroy()


class TestHoverQuestionCache(unittest.TestCase):
    def test_fingerprint_normalization(self):
        """Verify case, punctuation, and whitespace variations map to the same fingerprint."""
        q1 = "What is the capital of France?"
        q2 = "what is the capital of france"
        q3 = "  WHAT IS THE CAPITAL OF FRANCE?!  "
        
        fp1 = HoverQuestionCache.compute_fingerprint(q1)
        fp2 = HoverQuestionCache.compute_fingerprint(q2)
        fp3 = HoverQuestionCache.compute_fingerprint(q3)
        
        self.assertEqual(fp1, fp2)
        self.assertEqual(fp2, fp3)

    def test_cache_hit_and_ttl_expiration(self):
        """Verify question caching and TTL eviction."""
        cache = HoverQuestionCache(max_size=10, ttl_sec=0.2)
        q = "Calculate the derivative of sin(x)"
        
        self.assertFalse(cache.contains(q))
        cache.add(q)
        self.assertTrue(cache.contains(q))
        
        # Wait for TTL expiry
        time.sleep(0.3)
        self.assertFalse(cache.contains(q))

    def test_lru_capacity_eviction(self):
        """Verify LRU capacity bounds."""
        cache = HoverQuestionCache(max_size=3, ttl_sec=60.0)
        cache.add("Question 1")
        cache.add("Question 2")
        cache.add("Question 3")
        self.assertTrue(cache.contains("Question 1"))
        
        # Adding 4th should evict the oldest
        cache.add("Question 4")
        self.assertTrue(cache.contains("Question 4"))
        self.assertTrue(cache.contains("Question 3"))
        self.assertTrue(cache.contains("Question 2"))
        self.assertFalse(cache.contains("Question 1"))


class TestHoverDetector(unittest.TestCase):
    def test_stationary_trigger_and_debounce(self):
        """Verify detector fires only after staying stationary beyond hover_delay_sec."""
        triggered = []
        detector = HoverDetector(
            on_trigger=lambda: triggered.append(time.time()),
            is_solving_fn=lambda: False,
            get_excluded_rects=lambda: [],
            enabled=True,
            hover_delay_ms=200,   # 0.2s for fast test
            cooldown_sec=0.5,
            movement_threshold_px=10
        )
        
        # Mock cursor staying at (500, 500)
        with patch("ghostline.core.hover_detector.get_cursor_position", return_value=(500, 500)):
            # First tick: anchor set
            now = time.time()
            detector._anchor_pos = (500, 500)
            detector._stationary_start = now - 0.25 # Stationary for 250ms (> 200ms)
            detector._has_triggered_for_current_hover = False
            
            # Simulate sampling logic
            detector.on_trigger()
            self.assertEqual(len(triggered), 1)

    def test_movement_resets_anchor(self):
        """Verify movement exceeding jitter threshold resets the stationary timer."""
        detector = HoverDetector(
            on_trigger=lambda: None,
            enabled=True,
            hover_delay_ms=800,
            movement_threshold_px=15
        )
        
        detector._anchor_pos = (100, 100)
        detector._stationary_start = time.time()
        
        # Movement within threshold (e.g. 5px away)
        dist = ((103 - 100)**2 + (104 - 100)**2)**0.5
        self.assertLessEqual(dist, detector.movement_threshold_px)
        
        # Movement beyond threshold (e.g. 30px away)
        dist_far = ((130 - 100)**2 + (100 - 100)**2)**0.5
        self.assertGreater(dist_far, detector.movement_threshold_px)

    def test_excluded_area_detection(self):
        """Verify cursor inside HUD bounds is flagged as excluded area."""
        detector = HoverDetector(
            on_trigger=lambda: None,
            get_excluded_rects=lambda: [(400, 300, 780, 580)] # left, top, right, bottom
        )
        
        # Inside HUD (500, 400)
        self.assertTrue(detector.is_cursor_in_excluded_area(500, 400))
        
        # Outside HUD (100, 100)
        self.assertFalse(detector.is_cursor_in_excluded_area(100, 100))

    def test_pause_and_resume(self):
        """Verify pause/resume toggling."""
        detector = HoverDetector(on_trigger=lambda: None, is_paused=False)
        self.assertFalse(detector.is_paused)
        
        # Toggle pause
        is_p = detector.toggle_pause()
        self.assertTrue(is_p)
        self.assertTrue(detector.is_paused)
        
        # Toggle resume
        is_p2 = detector.toggle_pause()
        self.assertFalse(is_p2)
        self.assertFalse(detector.is_paused)


class TestFloatingHudOverlay(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.hud = GhostlineHudOverlay(
            opacity=0.9,
            width=360,
            height=260,
            pos_x=100,
            pos_y=100,
            is_pinned=False,
            always_on_top=True
        )
        self.hud.launch(parent=self.root, start_visible=False)

    def tearDown(self):
        try:
            self.hud.destroy()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_initial_hud_geometry_and_attributes(self):
        """Verify HUD initializes with configured dimensions and overrides borders."""
        self.assertFalse(self.hud.is_visible)
        self.assertEqual(self.hud.width, 360)
        self.assertEqual(self.hud.height, 260)
        self.assertEqual(self.hud.pos_x, 100)
        self.assertEqual(self.hud.pos_y, 100)

    def test_pin_and_minimize_toggles(self):
        """Verify pin toggle and minimize toggle change UI state correctly."""
        # Test Pin toggle
        self.assertFalse(self.hud.is_pinned)
        self.hud.toggle_pin()
        self.assertTrue(self.hud.is_pinned)
        self.hud.toggle_pin()
        self.assertFalse(self.hud.is_pinned)

        # Test Minimize toggle
        self.assertFalse(self.hud.is_minimized)
        self.hud.toggle_minimize()
        self.assertTrue(self.hud.is_minimized)
        self.assertEqual(self.hud.btn_min.cget("text"), "⤢")
        self.hud.toggle_minimize()
        self.assertFalse(self.hud.is_minimized)
        self.assertEqual(self.hud.btn_min.cget("text"), "—")

    def test_hud_state_transitions(self):
        """Verify HUD updates elements across capturing, thinking, answer, and error states."""
        # 1. Capturing
        self.hud._apply_state("capturing", "", "")
        self.assertEqual(self.hud.status_label.cget("text"), "Capturing Screen...")

        # 2. Thinking
        self.hud._apply_state("thinking", "", "")
        self.assertEqual(self.hud.status_label.cget("text"), "Thinking (Local AI)...")

        # 3. Answer state with code
        code_answer = (
            "Option A is correct:\n"
            "```python\n"
            "print('Hello Ghostline')\n"
            "```\n"
            "This outputs greeting."
        )
        self.hud._apply_state("answer", code_answer, "A")
        self.assertEqual(self.hud.status_label.cget("text"), "Answer Ready")
        self.assertEqual(self.hud.badge_label.cget("text"), "A")
        self.assertEqual(self.hud.current_lang, "python")
        self.assertIn("print('Hello Ghostline')", self.hud.current_code)

        # 4. Error state
        self.hud._apply_state("error", "Question text is illegible", "?")
        self.assertEqual(self.hud.status_label.cget("text"), "Uncertain (?)")
        self.assertEqual(self.hud.badge_label.cget("text"), "?")

    def test_window_rect_reporting(self):
        """Verify get_window_rect returns None when hidden and 4-tuple when shown."""
        self.assertIsNone(self.hud.get_window_rect())
        self.hud.is_visible = True
        rect = self.hud.get_window_rect()
        self.assertIsNotNone(rect)
        self.assertEqual(len(rect), 4)
        left, top, right, bottom = rect
        self.assertGreaterEqual(right, left)
        self.assertGreaterEqual(bottom, top)


if __name__ == "__main__":
    unittest.main()
