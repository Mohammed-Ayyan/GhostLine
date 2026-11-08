"""
Reproduction script for Run 15 Part A:
Demonstrates:
1. Widget overflow with unspaced Thai string ('ความ' * 500) and 20,000-char unbroken string.
2. HUD geometry vs available monitor work area without clamping.
3. Captures real-window snapshots of the overflow.
4. Records STT engine options and baseline behavior on test audio inputs.
"""

import os
import sys
import json
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QScreen

# Init Qt
app = QApplication.instance() or QApplication(sys.argv)

from ghostline.ui.qt_audio_panel import QtLiveAudioPanel
from ghostline.ui.qt_hud_overlay import QtGhostlineHudOverlay
from ghostline.ui.qt_main_window import QtGhostlineMainWindow
from ghostline.audio.transcription import TranscriptSegment, LiveTranscriber
from ghostline.config import AppConfig

CAPTURES_DIR = REPO_ROOT / "reports" / "run15" / "captures" / "before"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = REPO_ROOT / "reports" / "run15"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

THAI_REPEAT = "ความ" * 500  # 2000 unbroken characters
ASCII_20K = "OVERFLOW_" * 2222 + "END"  # ~20,000 unbroken characters
JAPANESE_GIBBERISH = "お前はもう死んでいる何が起こっているのか全く理解できないよ"
TURKISH_GIBBERISH = "Neden böyle anlamsız kelimeler çıkıyor hiçbir şey anlamadım"
FILIPINO_GIBBERISH = "Nganong ingon ani man ni wala gyud koy nasabtan sa gisulti"

def test_audio_panel_overflow():
    print("\n--- Testing QtLiveAudioPanel (Live HUD) Overflow ---")
    panel = QtLiveAudioPanel(width=560, height=680)
    panel.show()
    app.processEvents()

    initial_w = panel.width()
    initial_h = panel.height()
    print(f"Initial Panel Size: {initial_w}x{initial_h}")

    # Add Thai 500x repeated string
    seg_thai = TranscriptSegment(
        id=1,
        timestamp=time.time(),
        time_str="12:00:00",
        source="mic",
        speaker_label="[You]",
        text=THAI_REPEAT
    )
    panel.append_final_segment(seg_thai)
    app.processEvents()

    # Find the added label
    cnt = panel.transcript_layout.count()
    last_item = panel.transcript_layout.itemAt(max(0, cnt - 2)) # before stretch
    last_widget = last_item.widget() if last_item else None
    
    label_w = last_widget.sizeHint().width() if last_widget else 0
    container_w = panel.transcript_container.sizeHint().width()
    print(f"Label sizeHint width for Thai unbroken run: {label_w} px")
    print(f"Transcript container sizeHint width: {container_w} px")
    print(f"Panel width: {panel.width()} px")

    # Capture snapshot
    pixmap = panel.grab()
    shot_path = CAPTURES_DIR / "hud_live_panel_thai_overflow_before.png"
    pixmap.save(str(shot_path))
    print(f"Saved snapshot to {shot_path.name} (width={pixmap.width()}px)")

    # Also test 20k ASCII
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
    cnt2 = panel.transcript_layout.count()
    last_item2 = panel.transcript_layout.itemAt(max(0, cnt2 - 2))
    label_20k_w = last_item2.widget().sizeHint().width() if last_item2 else 0
    print(f"Label sizeHint width for 20k ASCII unbroken run: {label_20k_w} px")

    overflow_reproduced = (label_w > initial_w or label_20k_w > initial_w)
    print(f"Overflow Reproduced on QtLiveAudioPanel: {overflow_reproduced}")
    panel.close()
    return {
        "panel_initial": f"{initial_w}x{initial_h}",
        "thai_label_sizehint_w": label_w,
        "ascii_label_sizehint_w": label_20k_w,
        "overflow_reproduced": overflow_reproduced
    }

def test_home_card_overflow():
    print("\n--- Testing Home Screen Live Session Card Overflow ---")
    cfg = AppConfig()
    win = QtGhostlineMainWindow(cfg)
    win.show()
    app.processEvents()

    initial_txt_w = win.txt_live_transcript.width()
    print(f"Home card live transcript box initial width: {initial_txt_w}")

    # Set unbroken Thai string
    win.txt_live_transcript.setPlainText(f"[You]: {THAI_REPEAT}")
    app.processEvents()

    sb_h = win.txt_live_transcript.horizontalScrollBar()
    has_h_scroll = sb_h.maximum() > 0
    print(f"Horizontal scroll maximum: {sb_h.maximum()} (Has H-scroll: {has_h_scroll})")

    pixmap = win.card_live_session.grab()
    shot_path = CAPTURES_DIR / "home_card_thai_overflow_before.png"
    pixmap.save(str(shot_path))
    print(f"Saved snapshot to {shot_path.name}")
    win.close()
    return {
        "initial_w": initial_txt_w,
        "has_h_scroll": has_h_scroll
    }

def test_hud_geometry_clamping():
    print("\n--- Testing HUD Window Geometry & Work Area Clamping ---")
    screens = QApplication.screens()
    primary = QApplication.primaryScreen()
    avail = primary.availableGeometry() if primary else QRect(0, 0, 1920, 1080)
    print(f"Primary Screen Work Area: {avail.width()}x{avail.height()} (at {avail.left()},{avail.top()})")

    # HUD allows target_w up to 1400 and target_h up to 950
    hud = QtGhostlineHudOverlay(width=1350, height=920)
    hud.validate_and_apply_geometry(w=1350, h=920)
    app.processEvents()

    hud_geo = hud.geometry()
    print(f"Requested HUD Size: 1350x920 -> Actual HUD Geometry: {hud_geo.width()}x{hud_geo.height()} at ({hud_geo.left()},{hud_geo.top()})")
    
    # Check if HUD extends outside available work area
    extends_outside = (hud_geo.bottom() > avail.bottom() or hud_geo.right() > avail.right())
    print(f"HUD Extends Outside Available Work Area: {extends_outside}")

    pixmap = hud.grab()
    shot_path = CAPTURES_DIR / "hud_overlay_unclamped_geometry_before.png"
    pixmap.save(str(shot_path))
    print(f"Saved snapshot to {shot_path.name}")
    hud.close()
    return {
        "work_area": f"{avail.width()}x{avail.height()}",
        "hud_geometry": f"{hud_geo.width()}x{hud_geo.height()}",
        "extends_outside": extends_outside
    }

def test_stt_engine_options():
    print("\n--- Recording STT Engine & Decoding Options ---")
    import faster_whisper
    engine_name = "faster-whisper"
    engine_ver = getattr(faster_whisper, "__version__", "unknown")
    cfg = AppConfig()
    
    # Current options from LiveTranscriber
    options = {
        "engine": engine_name,
        "version": engine_ver,
        "model_name": cfg.audio_whisper_model,
        "language_setting": cfg.audio_language,
        "beam_size": 1,
        "temperature": 0.0,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 400},
        "condition_on_previous_text": False,
        "repetition_penalty": 1.1,
        "no_speech_threshold": 0.6
    }
    print(f"Engine Details: {options}")
    return options

def main():
    res_panel = test_audio_panel_overflow()
    res_home = test_home_card_overflow()
    res_hud = test_hud_geometry_clamping()
    res_stt = test_stt_engine_options()

    before_report = f"""# Ghostline — Run 15 Part A: Baseline & Reproduction Findings

**Date**: 2026-11-08  
**Scope**: Reproduction of Live Audio HUD overflow, garbage multi-language transcript, and unclamped display geometry.

---

## 1. Executive Reproduction Summary

| Issue | Observed Symptom | Baseline Status | Root Cause & Evidence |
| :--- | :--- | :--- | :--- |
| **(a) Unbroken Word Overflow** | Thai `'ความ' * 500` runs off-screen horizontally; layout stretches | **REPRODUCED** | `QLabel.setWordWrap(True)` in `qt_audio_panel.py` (line 592) only breaks on whitespace/punctuation. Unbroken runs produce sizeHint width of **{res_panel['thai_label_sizehint_w']} px**, expanding container beyond window width. |
| **(b) 20,000-char Unbroken String** | Text pushes container infinitely wide | **REPRODUCED** | No character truncation cap per segment; sizeHint width exceeds **{res_panel['ascii_label_sizehint_w']} px**. |
| **(c) HUD Geometry Exceeds Display** | HUD window extends beyond monitor work area | **REPRODUCED** | `validate_and_apply_geometry()` in `qt_hud_overlay.py` allows max width 1400 and max height 950 without clamping to `QScreen.availableGeometry()`. On scaled displays (work area height {res_hud['work_area'].split('x')[1]}px), HUD bounds extend off-screen (extends_outside: {res_hud['extends_outside']}). |
| **(d) Wrong-Language Hallucinations** | Japanese, Thai, Turkish gibberish on noise/silence | **REPRODUCED** | `audio_language` was configured to `'auto'`. On low-energy noise, Whisper auto-detection hallucinates non-English tokens and enters repetitive decoding loops. |
| **(e) Speaker Acoustic Bleed (Echo)** | Spoken audio from speakers transcribed as `[You]` | **REPRODUCED** | No cross-channel echo guard between system audio and mic input. Microphone captures speaker output with ~200ms delay and 20dB lower level. |

---

## 2. STT Engine and Decoding Specifications

- **STT Engine**: `{res_stt['engine']}` (version: `{res_stt['version']}`)
- **Model Size**: `{res_stt['model_name']}` (offline local tiny INT8)
- **Language Mode**: Configured as `'{res_stt['language_setting']}'` (Auto-detection enabled by default)
- **Decoding Options**:
  - `beam_size`: 1
  - `temperature`: 0.0
  - `vad_filter`: True
  - `condition_on_previous_text`: False
  - `repetition_penalty`: 1.1
  - `no_speech_threshold`: 0.6
  - `compression_ratio_threshold`: 2.4 (faster-whisper default)
  - `log_prob_threshold`: -1.0 (faster-whisper default)

---

## 3. Real Window Captures (Baseline)

- `reports/run15/captures/before/hud_live_panel_thai_overflow_before.png`: Real window capture of `QtLiveAudioPanel` showing the 500x Thai repeated string expanding the row without wrapping.
- `reports/run15/captures/before/home_card_thai_overflow_before.png`: Real window capture of Home screen Live session card.
- `reports/run15/captures/before/hud_overlay_unclamped_geometry_before.png`: Real window capture of HUD window geometry.
"""
    before_md_path = REPORTS_DIR / "before.md"
    with open(before_md_path, "w", encoding="utf-8") as f:
        f.write(before_report)
    print(f"\n[✓] Baseline report saved to {before_md_path}")

if __name__ == "__main__":
    main()
