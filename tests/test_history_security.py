import unittest
import tempfile
import time
import json
from pathlib import Path
from ghostline.core.history_store import SessionHistoryStore
from ghostline.config import AppConfig

class TestHistorySecurity(unittest.TestCase):
    def test_purge_retention(self):
        with tempfile.TemporaryDirectory() as td:
            storage_file = Path(td) / "test_sessions.jsonl"
            store = SessionHistoryStore(storage_path=storage_file)

            now = time.time()
            # Entry 1: 5 days old
            store._entries.append({
                "id": "entry_recent",
                "timestamp": now - (5 * 86400),
                "question": "Recent question",
                "answer": "Answer 1"
            })
            # Entry 2: 45 days old (expired under 30 days retention)
            store._entries.append({
                "id": "entry_old",
                "timestamp": now - (45 * 86400),
                "question": "Old question",
                "answer": "Answer 2"
            })
            store._rewrite_disk_file()
            self.assertEqual(len(store.get_entries()), 2)

            # Purge with 30-day retention
            purged = store.purge_retention(30)
            self.assertEqual(purged, 1)
            entries = store.get_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["id"], "entry_recent")

    def test_clear_wipes_all(self):
        with tempfile.TemporaryDirectory() as td:
            storage_file = Path(td) / "sessions.jsonl"
            store = SessionHistoryStore(storage_path=storage_file)
            store.add_screen_solve(question_text="Q1", answer_text="A1")
            self.assertTrue(len(store.get_entries()) >= 1)
            self.assertTrue(storage_file.exists())

            store.clear()
            self.assertEqual(len(store.get_entries()), 0)
            content = storage_file.read_text(encoding="utf-8")
            self.assertEqual(content.strip(), "")

if __name__ == "__main__":
    unittest.main()

