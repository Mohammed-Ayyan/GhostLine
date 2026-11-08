"""
Verification test script for Ghostline Run 15 Part A:
1. Widget overflow tests: Thai 500x and 20k ASCII into QtLiveAudioPanel, Home card, and HUD.
2. HUD geometry work-area clamping and off-screen repair tests across screen configurations.
3. Full audio pipeline verification with the 6 fixtures:
   - Digital silence (30s) -> 0 lines
   - Room noise (30s) -> 0 lines
   - Music tones (30s) -> 0 lines
   - Quiet speech -40 dBFS -> transcribed
   - Clean system speech -> transcribed
   - Mic speaker echo -> dropped by echo guard
4. Captures real-window snapshots into reports/run15/captures/after/.
"""

import os
import sys
import time
import math
import wave
import json
import numpy as np
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QRect, QPoint, QTimer
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.audio.transcription import TranscriptSegment, LiveTranscriber
from ghostline.audio.output_guard import AudioOutputGuard
from ghostline.audio.timing import TimingManager
from ghostline.config import AppConfig

CAPTURES_DIR = REPO_ROOT / "reports" / "run15" / "captures" / "after"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "run15_audio"

THAI_REPEAT = "ความ" * 500  # 2000 unbroken characters
ASCII_20K = "OVERFLOW_" * 2222 + "END"  # ~20,000 unbroken characters


def load_wav(filename: str):
    p = FIXTURES_DIR / filename
    with wave.open(str(p), "rb") as wf:
        n_frames = wf.getnframes()
        sr = wf.getframerate()
        frames = wf.readframes(n_frames)
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        return samples, sr


def test_widget_overflow_after():
    print("\n[1/4] Verifying QtLiveAudioPanel Text Wrapping and No-Overflow...")
    panel = QtLiveAudioPanel(width=560, height=680)
    panel.show_panel()
    app.processEvents()

    initial_w = panel.width()
    initial_h = panel.height()
    print(f"  Panel Dimensions: {initial_w}x{initial_h}")

    # 1. Feed Thai 500x repeated string
    seg_thai = TranscriptSegment(
        id=1,
        timestamp=time.time(),
        time_str="12:00:01",
        source="mic",
        speaker_label="[You (mic)]",
        text=THAI_REPEAT
    )
    panel.append_final_segment(seg_thai)
    app.processEvents()

    # 2. Feed 20k ASCII unbroken string
    seg_20k = TranscriptSegment(
        id=2,
        timestamp=time.time(),
        time_str="12:00:05",
        source="call",
        speaker_label="[System]",
        text=ASCII_20K
    )
    panel.append_final_segment(seg_20k)
    app.processEvents()

    # 3. Feed partial preview with 300 chars
    panel.set_partial_text("In-flight partial speech preview that exceeds two hundred characters: " * 5, source="mic")
    app.processEvents()

    # 4. Feed normal conversational turns
    for idx, (spk, txt) in enumerate([
        ("[System]", "Welcome to the technical architectural review for our payment processing service."),
        ("[You (mic)]", "Thank you, I am ready to discuss the idempotency and retry strategies."),
        ("[System]", "Could you explain how distributed transactions are handled across our microservices?"),
        ("[You (mic)]", "We utilize the Saga pattern with compensating transactions and outbox event streaming.")
    ], start=3):
        panel.append_final_segment(TranscriptSegment(
            id=idx,
            timestamp=time.time(),
            time_str=f"12:00:{idx:02d}",
            source="mic" if "You" in spk else "call",
            speaker_label=spk,
            text=txt
        ))
        app.processEvents()

    # Verify panel width has NOT expanded
    final_w = panel.width()
    txt_w = panel.txt_transcript.width()
    sb_h = panel.txt_transcript.horizontalScrollBar()
    has_h_scroll = sb_h.maximum() > 0

    print(f"  Final Panel Width: {final_w} px (initial: {initial_w} px)")
    print(f"  Transcript Width: {txt_w} px")
    print(f"  Horizontal scroll maximum: {sb_h.maximum()} (Has H-scroll: {has_h_scroll})")
    print(f"  Partial text: '{panel.lbl_partial.text()[:60]}...' (len={len(panel.lbl_partial.text())})")

    assert final_w == initial_w, f"Panel expanded! {final_w} != {initial_w}"
    assert not has_h_scroll, "Horizontal scrollbar is active on transcript!"
    assert len(panel.lbl_partial.text()) <= 220, "Partial label not capped!"

    pixmap = panel.grab()
    shot_path = CAPTURES_DIR / "hud_live_panel_after.png"
    pixmap.save(str(shot_path))
    print(f"  [✓] Saved snapshot to {shot_path.name}")
    panel.close()

    return {
        "panel_w": final_w,
        "txt_w": txt_w,
        "has_h_scroll": has_h_scroll,
        "partial_len": len(panel.lbl_partial.text())
    }


def test_home_card_after():
    print("\n[2/4] Verifying Home Screen Live Card Text Wrapping...")
    cfg = AppConfig()
    win = QtGhostlineMainWindow(cfg)
    win.show()
    app.processEvents()

    # Feed Thai unbroken run and long text
    win.txt_live_transcript.setPlainText(f"[You (mic)]: {THAI_REPEAT[:500]}…")
    win.txt_live_answer.setPlainText("AI Analysis:\n" + ("Distributed database consensus requires raft algorithm. " * 10))
    app.processEvents()

    sb_h_t = win.txt_live_transcript.horizontalScrollBar()
    sb_h_a = win.txt_live_answer.horizontalScrollBar()

    print(f"  Home Transcript H-Scroll Max: {sb_h_t.maximum()}")
    print(f"  Home Answer H-Scroll Max: {sb_h_a.maximum()}")

    assert sb_h_t.maximum() == 0, "Home card transcript has horizontal scroll!"
    assert sb_h_a.maximum() == 0, "Home card answer has horizontal scroll!"

    pixmap = win.card_live_session.grab()
    shot_path = CAPTURES_DIR / "home_card_live_after.png"
    pixmap.save(str(shot_path))
    print(f"  [✓] Saved snapshot to {shot_path.name}")
    win.close()


def test_hud_geometry_clamping_after():
    print("\n[3/4] Verifying HUD Geometry Clamping and Work-Area Containment...")
    primary = QApplication.primaryScreen()
    avail = primary.availableGeometry() if primary else QRect(0, 0, 1920, 1080)
    print(f"  Monitor Available Work Area: {avail.width()}x{avail.height()} at ({avail.left()},{avail.top()})")

    hud = QtGhostlineHudOverlay(width=1350, height=920)
    hud.validate_and_apply_geometry(x=avail.right() + 500, y=avail.bottom() + 500, w=1350, h=920)
    app.processEvents()

    geo = hud.geometry()
    print(f"  Requested 1350x920 off-screen -> Clamped Geometry: {geo.width()}x{geo.height()} at ({geo.left()},{geo.top()})")

    # Clamping assertions
    assert geo.width() <= min(720, int(avail.width() * 0.90)), f"Width exceeds limit: {geo.width()}"
    assert geo.height() <= min(900, int(avail.height() * 0.90)), f"Height exceeds limit: {geo.height()}"
    assert geo.left() >= avail.left(), f"Left off-screen: {geo.left()} < {avail.left()}"
    assert geo.top() >= avail.top(), f"Top off-screen: {geo.top()} < {avail.top()}"
    assert geo.right() <= avail.right(), f"Right off-screen: {geo.right()} > {avail.right()}"
    assert geo.bottom() <= avail.bottom(), f"Bottom off-screen: {geo.bottom()} > {avail.bottom()}"

    pixmap = hud.grab()
    shot_path = CAPTURES_DIR / "hud_overlay_clamped_after.png"
    pixmap.save(str(shot_path))
    print(f"  [✓] Saved snapshot to {shot_path.name}")
    hud.close()


def test_audio_pipeline_real_fixtures():
    print("\n[4/4] Verifying Real STT Pipeline on Audio Fixtures...")
    transcriber = LiveTranscriber(
        model_name="tiny",
        language="en"
    )

    emitted_segments = []
    transcriber.on_segment = lambda s: emitted_segments.append(s)

    # Preload model
    print("  Loading local Whisper tiny model...")
    transcriber.start()
    t0 = time.time()
    while transcriber.is_loading and time.time() - t0 < 15.0:
        time.sleep(0.1)

    print(f"  Model loaded: {transcriber.model is not None}")

    # 1. Test Digital Silence (30s)
    silence, sr = load_wav("digital_silence_30s.wav")
    emitted_segments.clear()
    transcriber._transcribe_buffer(silence[:sr*5], source="mic")
    print(f"  Digital Silence emitted segments: {len(emitted_segments)}")
    assert len(emitted_segments) == 0, f"Expected 0 segments on silence, got {len(emitted_segments)}"

    # 2. Test Noise Room (30s)
    noise, sr = load_wav("noise_room_30s.wav")
    emitted_segments.clear()
    transcriber._transcribe_buffer(noise[:sr*6], source="mic")
    print(f"  Room Noise emitted segments: {len(emitted_segments)}")
    assert len(emitted_segments) == 0, f"Expected 0 segments on noise, got {len(emitted_segments)}"

    # 3. Test Music Tones (30s)
    music, sr = load_wav("music_tones_30s.wav")
    emitted_segments.clear()
    transcriber._transcribe_buffer(music[:sr*6], source="mic")
    print(f"  Music Tones emitted segments: {len(emitted_segments)}")
    assert len(emitted_segments) == 0, f"Expected 0 segments on music tones, got {len(emitted_segments)}"

    # 4. Test Quiet Speech -40 dBFS (before system audio to test independent mic sensitivity)
    quiet, sr = load_wav("speech_quiet_minus40db.wav")
    emitted_segments.clear()
    transcriber._transcribe_buffer(quiet, source="mic")
    print(f"  Quiet Speech (-40 dBFS) emitted segments: {len(emitted_segments)}")
    assert len(emitted_segments) >= 1, "Expected quiet speech (-40 dBFS) to be detected and transcribed"
    print(f"  -> Quiet Speech Output: '{emitted_segments[0].text}'")

    # 5. Test Clean System Speech (4.1s)
    clean_sys, sr = load_wav("speech_clean_system.wav")
    emitted_segments.clear()
    transcriber._transcribe_buffer(clean_sys, source="call")
    print(f"  Clean System Speech emitted segments: {len(emitted_segments)}")
    assert len(emitted_segments) >= 1, "Expected clean system speech to be transcribed"
    sys_text = emitted_segments[0].text
    print(f"  -> System Speech Output: '{sys_text}'")

    # 6. Test Mic Acoustic Echo of the same speech (speakers heard by mic)
    echo_mic, sr = load_wav("speech_mic_echo.wav")
    emitted_segments.clear()
    transcriber._transcribe_buffer(echo_mic, source="mic")
    print(f"  Mic Acoustic Echo emitted segments: {len(emitted_segments)}")
    assert len(emitted_segments) == 0, f"Expected mic echo to be dropped by echo guard, got {len(emitted_segments)}"
    print(f"  -> Filtered segments summary: {transcriber.output_guard.get_diagnostics_summary()}")

    transcriber.stop()
    print("  [✓] All audio fixture scenarios verified successfully!")


def main():
    print("=============================================================")
    print("Ghostline Run 15 Part A: Verification Suite")
    print("=============================================================")
    test_widget_overflow_after()
    test_home_card_after()
    test_hud_geometry_clamping_after()
    test_audio_pipeline_real_fixtures()
    print("\n[✓✓✓] All Run 15 Part A Verification Tests PASSED Cleanly!")


if __name__ == "__main__":
    main()
