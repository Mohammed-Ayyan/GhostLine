"""
Comprehensive tests for Round 3:
1. Question extraction with reading order preservation on multi-line text (no lost lines/stems).
2. HudManager strict mutual exclusivity across SCREEN, AUDIO, and HISTORY modes.
3. SessionHistoryStore persistence across sessions.
4. Debug dump artifacts (04b_reading_order_lines.json and 06_chosen_region.png).
"""

import os
import json
import tempfile
import pytest
from pathlib import Path
from PIL import Image

from ghostline.core.ocr_engine import (
    sort_lines_in_reading_order,
    extract_target_question_lines,
    ParsedQuestion,
)
from ghostline.ui.presentation import TYPE_MCQ
from ghostline.ui.hud_manager import HudManager, HudMode
from ghostline.core.history_store import SessionHistoryStore
from ghostline.core.capture import save_stage_debug_dump


class DummyOverlay:
    """Mock overlay implementing show, hide, isVisible, launch."""
    def __init__(self, name: str):
        self.name = name
        self._visible = False

    def isVisible(self) -> bool:
        return self._visible

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def show_overlay(self):
        self._visible = True

    def hide_overlay(self):
        self._visible = False

    def show_panel(self):
        self._visible = True

    def hide_panel(self):
        self._visible = False


class TestQuestionExtractionReadingOrder:
    """Tests multi-line reading order preservation and stem completeness."""

    def test_two_line_wrapped_question(self):
        # Two lines making up the stem before options
        lines = [
            ("In Python, which built-in function returns the unique", (100, 100, 500, 25)),
            ("identity integer of an object in memory?", (100, 130, 420, 25)),
            ("A) id()", (100, 170, 150, 20)),
            ("B) hex()", (100, 195, 150, 20)),
            ("C) hash()", (100, 220, 150, 20)),
            ("D) bin()", (100, 245, 150, 20)),
        ]
        chosen, bbox = extract_target_question_lines(lines)
        chosen_texts = [t for t, _ in chosen]
        joined_q = " ".join(chosen_texts)

        assert "In Python, which built-in function returns the unique" in joined_q
        assert "identity integer of an object in memory?" in joined_q
        assert len(chosen) == 6
        assert bbox == (100, 100, 600, 265)

    def test_three_line_paragraph_question(self):
        # 3-line paragraph question
        lines = [
            ("Suppose you are developing a real-time multiplayer networking engine,", (50, 50, 550, 22)),
            ("and packets arrive out of order over an unreliable UDP stream.", (50, 75, 520, 22)),
            ("Which data structure is optimal for reordering jitter buffers?", (50, 100, 540, 22)),
            ("A. Min-Heap Priority Queue", (50, 135, 250, 20)),
            ("B. Circular Array", (50, 160, 200, 20)),
            ("C. Hash Map", (50, 185, 180, 20)),
            ("D. Doubly Linked List", (50, 210, 220, 20)),
        ]
        chosen, bbox = extract_target_question_lines(lines)
        chosen_texts = [t for t, _ in chosen]
        joined_q = " ".join(chosen_texts)

        assert "Suppose you are developing a real-time multiplayer" in joined_q
        assert "packets arrive out of order" in joined_q
        assert "Which data structure is optimal" in joined_q
        assert len(chosen) == 7
        assert bbox[0] == 50
        assert bbox[1] == 50

    def test_numbered_question_preserves_first_line(self):
        # Starts with "1. In Python..."
        lines = [
            ("1. In Python, what is the output of print(2 ** 3 ** 2)?", (80, 80, 480, 25)),
            ("A. 64", (80, 115, 100, 20)),
            ("B. 512", (80, 140, 100, 20)),
            ("C. 256", (80, 165, 100, 20)),
            ("D. SyntaxError", (80, 190, 120, 20)),
        ]
        chosen, bbox = extract_target_question_lines(lines)
        chosen_texts = [t for t, _ in chosen]
        joined_q = " ".join(chosen_texts)

        assert "1. In Python, what is the output of print(2 ** 3 ** 2)?" in joined_q
        assert len(chosen) == 5

    def test_reading_order_sorting(self):
        # Lines scattered slightly on X and Y within same line band
        raw = [
            ("Column B", (300, 50, 100, 20)),
            ("Column A", (50, 52, 100, 20)),
            ("Line 2", (50, 85, 150, 20)),
        ]
        sorted_lines = sort_lines_in_reading_order(raw, y_tolerance=8)
        texts = [t for t, _ in sorted_lines]
        assert texts == ["Column A", "Column B", "Line 2"]


class TestHudManagerMutualExclusivity:
    """Tests HudManager strict single-active-HUD guarantee."""

    def test_single_active_hud(self):
        screen = DummyOverlay("Screen")
        audio = DummyOverlay("Audio")
        history = DummyOverlay("History")

        mgr = HudManager(screen_hud=screen, audio_hud=audio, history_hud=history)
        assert mgr.active_mode == HudMode.HIDDEN
        assert not screen.isVisible()
        assert not audio.isVisible()
        assert not history.isVisible()

        # 1. Show Screen
        mgr.show_mode(HudMode.SCREEN)
        assert mgr.active_mode == HudMode.SCREEN
        assert screen.isVisible()
        assert not audio.isVisible()
        assert not history.isVisible()

        # 2. Show Audio - Screen MUST hide immediately
        mgr.show_mode(HudMode.AUDIO)
        assert mgr.active_mode == HudMode.AUDIO
        assert not screen.isVisible()
        assert audio.isVisible()
        assert not history.isVisible()

        # 3. Show History - Audio MUST hide immediately
        mgr.show_mode(HudMode.HISTORY)
        assert mgr.active_mode == HudMode.HISTORY
        assert not screen.isVisible()
        assert not audio.isVisible()
        assert history.isVisible()

        # 4. Hide All
        mgr.hide_all()
        assert mgr.active_mode == HudMode.HIDDEN
        assert not screen.isVisible()
        assert not audio.isVisible()
        assert not history.isVisible()

    def test_toggle_mode(self):
        screen = DummyOverlay("Screen")
        audio = DummyOverlay("Audio")
        history = DummyOverlay("History")

        mgr = HudManager(screen_hud=screen, audio_hud=audio, history_hud=history)

        # Toggle Screen on
        mgr.toggle_mode(HudMode.SCREEN)
        assert mgr.active_mode == HudMode.SCREEN
        assert screen.isVisible()

        # Toggle Screen off
        mgr.toggle_mode(HudMode.SCREEN)
        assert mgr.active_mode == HudMode.HIDDEN
        assert not screen.isVisible()

        # Toggle Audio on, then toggle History -> Audio hides, History opens
        mgr.toggle_mode(HudMode.AUDIO)
        assert mgr.active_mode == HudMode.AUDIO
        assert audio.isVisible()

        mgr.toggle_mode(HudMode.HISTORY)
        assert mgr.active_mode == HudMode.HISTORY
        assert history.isVisible()
        assert not audio.isVisible()

    def test_toggle_active_alt_t(self):
        screen = DummyOverlay("Screen")
        audio = DummyOverlay("Audio")
        history = DummyOverlay("History")

        mgr = HudManager(screen_hud=screen, audio_hud=audio, history_hud=history)

        # Open screen HUD
        mgr.show_mode(HudMode.SCREEN)
        assert mgr.active_mode == HudMode.SCREEN

        # Alt+T toggles active HUD off
        mgr.toggle_active()
        assert mgr.active_mode == HudMode.HIDDEN
        assert not screen.isVisible()

        # Alt+T again restores previous mode (SCREEN)
        mgr.toggle_active()
        assert mgr.active_mode == HudMode.SCREEN
        assert screen.isVisible()


class TestSessionHistoryStore:
    """Tests session history store and persistence across app restarts."""

    def test_persistence_across_reloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "test_sessions.jsonl"
            store1 = SessionHistoryStore(storage_path=jsonl_path)

            # Record entries
            store1.add_screen_solve(
                question="What is Python GIL?",
                answer_option="Global Interpreter Lock",
                explanation="Mutex preventing simultaneous thread execution.",
                question_type="conceptual",
                options={"A": "Global Interpreter Lock", "B": "General Interface Link"},
            )
            store1.add_audio_qa(
                question="Can you explain asyncio event loop?",
                answer="Asyncio uses a single-threaded cooperative event loop.",
                code_snippet="import asyncio\nasyncio.run(main())",
            )
            store1.add_transcript_segment(
                text="Hello team, welcome to the sprint demo.",
                source="call",
                speaker="Interviewer",
            )

            assert len(store1.get_entries()) == 3

            # Instantiate a second store instance from the same file (simulating app restart)
            store2 = SessionHistoryStore(storage_path=jsonl_path)
            loaded = store2.get_entries()
            assert len(loaded) == 3

            # Verify contents
            screen_entries = store2.get_entries(mode_filter="screen")
            assert len(screen_entries) == 1
            assert screen_entries[0]["question"] == "What is Python GIL?"
            assert screen_entries[0]["answer"] == "Global Interpreter Lock"

            audio_entries = store2.get_entries(mode_filter="audio")
            assert len(audio_entries) == 2
            # Find the audio_qa entry
            qa_entry = next(e for e in audio_entries if e["entry_type"] == "audio_qa")
            assert qa_entry["code_snippet"] == "import asyncio\nasyncio.run(main())"

            # Search filtering
            search_res = store2.get_entries(search_query="sprint demo")
            assert len(search_res) == 1
            assert "sprint demo" in search_res[0]["question"]


class TestDebugStageDumps:
    """Tests that stage debug dumps write 04b_reading_order_lines.json and 06_chosen_region.png."""

    def test_debug_dump_artifacts(self):
        img = Image.new("RGB", (300, 200), color=(30, 30, 30))
        parsed_q = ParsedQuestion(
            question_text="Sample Test Question?",
            options={"A": "Opt 1", "B": "Opt 2"},
            raw_text="Raw text",
            question_type=TYPE_MCQ,
            chosen_region_bbox=(20, 30, 200, 80),
            reading_order_lines=["Sample Test Question?", "Opt 1", "Opt 2"],
        )

        dump_path = save_stage_debug_dump(
            raw_img=img,
            crop_bbox=(0, 0, 300, 200),
            preprocessed_img=img,
            raw_ocr_data={},
            filtered_text="Sample Test Question?",
            parsed_question=parsed_q,
            prompt_sent="test prompt",
            raw_llm_response="test response"
        )

        # Check 04b_reading_order_lines.json
        ro_file = dump_path / "04b_reading_order_lines.json"
        assert ro_file.exists(), "04b_reading_order_lines.json was not created"
        with open(ro_file, "r", encoding="utf-8") as f:
            ro_data = json.load(f)
        assert ro_data["line_count"] == 3
        assert ro_data["chosen_region_bbox"] == [20, 30, 200, 80]
        assert ro_data["lines"] == ["Sample Test Question?", "Opt 1", "Opt 2"]

        # Check 06_chosen_region.png
        bbox_img_file = dump_path / "06_chosen_region.png"
        assert bbox_img_file.exists(), "06_chosen_region.png was not created"
        assert bbox_img_file.stat().st_size > 0
