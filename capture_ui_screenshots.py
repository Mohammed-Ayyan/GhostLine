"""
High-fidelity PyQt6 screenshot capture script for Ghostline redesign:
1. main_dashboard.png - Dashboard view with system status, action cards, recent results
2. main_settings.png  - General settings matching Reference 3 (media_1792937359451.png)
3. main_mode.png      - Mode settings matching Reference 4 (media_1792937364076.png)
4. hud_standard_answer.png - Floating HUD matching Reference 2 (media_1792937340274.png)
5. hud_live_audio.png - Live-Audio HUD with distinct transcript & AI response areas
"""

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.ui.presentation import PresentedAnswer, TYPE_CODE, TYPE_MCQ
from ghostline.audio.transcription import TranscriptSegment

output_dir = Path(r"C:\Users\sumiy\.gemini\antigravity-ide\brain\2b1b3398-9e18-420f-a8e4-008427a2b9a7")
output_dir.mkdir(parents=True, exist_ok=True)


def capture_widget(widget, filename):
    widget.show()
    widget.raise_()
    QApplication.processEvents()
    time.sleep(0.15)
    QApplication.processEvents()
    
    pixmap = widget.grab()
    save_path = output_dir / filename
    pixmap.save(str(save_path), "PNG")
    print(f"[+] Saved screenshot to: {save_path} (size: {pixmap.width()}x{pixmap.height()})")
    return save_path


def main():
    print("[*] Launching PyQt6 UI capture engine...")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    from ghostline.ui.qt_theme import QT_MAIN_STYLESHEET
    app.setStyleSheet(QT_MAIN_STYLESHEET)

    cfg = AppConfig()

    # 1. Main Desktop Window
    main_win = QtGhostlineMainWindow(config=cfg)
    main_win.resize(960, 680)

    # Populate Sample Results
    class MockRes:
        class parsed_question:
            question_text = "Which algorithm computes single-source shortest paths on weighted graphs with non-negative weights in O((V + E) log V) time?"
        class answer_result:
            answer_option = "B"
            proposed_option = "B"
            direct_answer = "Option B — Dijkstra's Algorithm with Min-Heap"
            explanation = "Dijkstra's algorithm with an indexed min-priority queue achieves O((V + E) log V) time complexity and optimal path calculation."
            code_snippet = "import heapq\n\ndef dijkstra(graph, start):\n    dist = {start: 0}\n    pq = [(0, start)]\n    while pq:\n        d, u = heapq.heappop(pq)\n        for v, w in graph[u]:\n            if d + w < dist.get(v, float('inf')):\n                dist[v] = d + w\n                heapq.heappush(pq, (dist[v], v))\n    return dist"
            confidence = 0.99

    main_win.on_solve_completed(MockRes())

    # 1. Capture Dashboard
    main_win.show_screen("dashboard")
    capture_widget(main_win, "main_dashboard.png")

    # 2. Capture General Settings (Matching Reference 3)
    main_win.show_screen("general")
    capture_widget(main_win, "main_settings.png")

    # 3. Capture Mode Settings (Matching Reference 4)
    main_win.show_screen("mode")
    capture_widget(main_win, "main_mode.png")

    # 4. Floating HUD (Matching Reference 2)
    hud = QtGhostlineHudOverlay(
        width=560,
        height=520,
        opacity=0.96,
        is_pinned=True,
        always_on_top=True
    )
    hud.resize(560, 520)

    sample_pres = PresentedAnswer(
        question_type=TYPE_CODE,
        badge="B",
        headline="Implement two-tier Redis Cache with fallback circuit breaker",
        direct_answer="Option B: Redis + Circuit Breaker",
        explanation="Maintains read consistency while isolating the primary database from sudden connection spikes under heavy load.",
        code="""class ResilientCache:
    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client
        self.breaker = CircuitBreaker(fail_max=5, reset_timeout=30)

    def get_user_session(self, user_id: str):
        try:
            cached = self.redis.get(f"session:{user_id}")
            if cached:
                return json.loads(cached)
        except RedisConnectionError:
            self.breaker.record_failure()
        return self.db.query_session(user_id)""",
        code_language="python",
        is_validated=True,
        confidence=0.98,
        question_text="Design a distributed caching layer using Redis with write-through cache and circuit breaker pattern."
    )
    hud.update_answer(sample_pres)
    capture_widget(hud, "hud_standard_answer.png")

    # 5. Live-Audio HUD
    audio_panel = QtLiveAudioPanel(
        width=560,
        height=660,
        opacity=0.96
    )
    audio_panel.resize(560, 660)

    # Populate audio segments
    audio_panel.append_final_segment(TranscriptSegment(
        id=1,
        timestamp=time.time(),
        time_str="12:34:50",
        source="call",
        speaker_label="[Call]",
        text="Could you explain how consensus is reached during partition in Raft?"
    ))
    audio_panel.append_final_segment(TranscriptSegment(
        id=2,
        timestamp=time.time() + 4.0,
        time_str="12:34:55",
        source="mic",
        speaker_label="[You]",
        text="In Raft, a leader requires a majority quorum of nodes to commit log entries. If partitioned without a quorum, entries cannot be committed."
    ))
    audio_panel.set_ai_answer(
        question="Consensus during network partition in Raft consensus protocol",
        answer="In Raft, consensus requires a strict majority (N/2 + 1) quorum. When a network partition divides a 5-node cluster into 3 nodes and 2 nodes, only the 3-node partition can elect a leader and commit log entries. The 2-node minority partition rejects writes, preventing split-brain.",
        code="""# Raft Quorum Check
def has_quorum(active_nodes: int, total_nodes: int) -> bool:
    required = (total_nodes // 2) + 1
    return active_nodes >= required

# Example: 5 nodes -> required quorum is 3
assert has_quorum(3, 5) == True
assert has_quorum(2, 5) == False"""
    )
    audio_panel.update_level("mic", 0.45, 0.8)
    audio_panel.update_level("call", 0.65, 0.9)
    capture_widget(audio_panel, "hud_live_audio.png")

    print("[*] All 5 high-fidelity screenshots successfully captured and saved!")


if __name__ == "__main__":
    main()
