"""
Capture crisp 200% scale application UI assets for Ghostline Run 10 launch videos.
Outputs PNGs to ../ghostline_launch_video/run10/raw_assets/ (outside repo).
Uses dummy test data only (zero personal info, zero API keys).
"""

import os
import sys
from pathlib import Path

# Ensure offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QFont
from PyQt6.QtWidgets import QApplication

from ghostline.config import AppConfig
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.presentation import PresentedAnswer

OUT_DIR = Path("../ghostline_launch_video/run10/raw_assets").resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)

def capture_ui():
    print(f"[*] Capturing 200% scale UI assets into {OUT_DIR}...")
    app = QApplication.instance() or QApplication(sys.argv)
    
    from ghostline.core.profile import save_profile_data
    save_profile_data({
        "name": "Alex Morgan",
        "role": "Senior Systems Engineer",
        "target_role": "Staff Infrastructure Architect",
        "bio": "Experienced systems software engineer specializing in distributed memory pipelines, Linux kernel internals, and high-throughput real-time streaming.",
        "skills": ["Python", "Rust", "C++", "Linux eBPF", "Docker", "Distributed Consensus", "Redis"],
        "education": [{"institution": "University of Washington", "degree": "B.S. Computer Science", "year": "2019"}],
        "experience": [
            {"company": "Apex Distributed Networks", "title": "Senior Systems Engineer", "duration": "2021-Present", "description": "Led low-latency memory pipeline processing 2M ops/sec."}
        ],
        "projects": [
            {"name": "Ghostline", "description": "High-efficiency native desktop assistive engine with sub-millisecond local OCR."}
        ],
        "never_claim": ["Proprietary trading secrets", "Unverified hardware benchmarks"],
        "use_profile": True,
        "allow_cloud": True,
        "use_in_screen": True
    })

    cfg = AppConfig()

    # 1. Main Window Pages at 200% (scale 2.0 -> 2200 x 1440)
    main_win = QtGhostlineMainWindow(config=cfg)
    main_win.resize(1100, 720)
    main_win.show()
    app.processEvents()

    # Capture each page
    pages = [
        ("general", "general"),
        ("ai_provider", "model"),
        ("profile", "profile"),
        ("audio", "audio"),
        ("diagnostics_help", "help")
    ]
    for file_name, screen_name in pages:
        main_win.show_screen(screen_name)
        app.processEvents()
        
        pix = QPixmap(main_win.size() * 2)
        pix.setDevicePixelRatio(2.0)
        main_win.render(pix)
        out_file = OUT_DIR / f"app_{file_name}_200.png"
        pix.save(str(out_file), "PNG")
        print(f"  [+] Saved {out_file.name} ({pix.width()}x{pix.height()})")

    # 2. HUD Overlay in Answer state at 200%
    hud = QtGhostlineHudOverlay(is_pinned=True, width=540, height=380)
    pres = PresentedAnswer(
        headline="Option C is correct",
        direct_answer="Option C: Min-Heap with O(log n) insertions",
        explanation="A binary min-heap guarantees that the root element is always the minimum. Inserting n elements requires O(n log n) total time.",
        badge="C",
        question_type="multiple_choice",
        is_validated=True
    )
    hud.update_answer(pres)
    hud.show()
    app.processEvents()

    hud_pix = QPixmap(hud.size() * 2)
    hud_pix.setDevicePixelRatio(2.0)
    hud.render(hud_pix)
    hud_out = OUT_DIR / "hud_answer_200.png"
    hud_pix.save(str(hud_out), "PNG")
    print(f"  [+] Saved {hud_out.name} ({hud_pix.width()}x{hud_pix.height()})")

    # 3. HUD Overlay in Live Audio / Meeting state at 200%
    from ghostline.core.conversation import ConversationEntry
    audio_entry = ConversationEntry(
        source="call",
        speaker_label="[Call]",
        detected_question="How do you handle tail latency in distributed microservices?",
        answer_text="In my work on high-throughput distributed systems, we minimize tail latency using zero-copy serialization, bounded thread pools, and hedged requests to bypass outlier nodes.",
        status="answered"
    )
    hud.add_or_update_card(audio_entry)
    app.processEvents()
    hud_audio_pix = QPixmap(hud.size() * 2)
    hud_audio_pix.setDevicePixelRatio(2.0)
    hud.render(hud_audio_pix)
    hud_audio_out = OUT_DIR / "hud_audio_200.png"
    hud_audio_pix.save(str(hud_audio_out), "PNG")
    print(f"  [+] Saved {hud_audio_out.name} ({hud_audio_pix.width()}x{hud_audio_pix.height()})")

    main_win.close()
    hud.close()
    print("[+] All 200% UI assets captured successfully.")

if __name__ == "__main__":
    capture_ui()
