# Ghostline — Run 15 External Changes Needed

Per Run 15 Part B instructions (Section 5), text statements referencing music, soundtrack, or music licensing located outside allowed paths must not be modified directly by the agent, but documented here for user action:

### 1. `website/changelog.html` (Line 41)
- **Current Content**:
  ```html
  <li><strong>Rebuilt Master Video Suite:</strong> 1080p Launch Film (92s), Setup Tutorial (140s), Usage Walkthrough (180s), and 5 Vertical Shorts (35s) with synthesized electronic soundtrack (-14.1 LUFS), WebVTT subtitles, and text transcripts.</li>
  ```
- **Recommended Update**:
  ```html
  <li><strong>Rebuilt Master Video Suite:</strong> 1080p Launch Film (92s), Setup Tutorial (140s), Usage Walkthrough (180s), and 5 Vertical Shorts (35s) with silent audio tracks (captions-first presentation), WebVTT subtitles, and text transcripts.</li>
  ```

### 2. `docs/VOICEOVER_SCRIPT_AND_SHOTLIST.md` (Lines 11, 23, 31, 32)
- **Current Content**:
  - Line 11: `* **Sound Design:** Subtle audio waveform hum; voiceover clearly normalized above music.`
  - Line 23: `* **Sound Design:** Final music beat hits with clean reverb tail fading out naturally at 60.0s.`
  - Line 31: `| **Music Track** | Restrained Modern Electronic (happy-beats-vol-12) | Restrained Modern Electronic (happy-beats-vol-12) |`
  - Line 32: `| **Music Ducking** | -18 dB during narration, 0 dB at intros/outros | -18 dB during narration, 0 dB at intros/outros |`
- **Recommended Update**: Update documentation table to reflect silent soundtrack / captions-first video structure.
