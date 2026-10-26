"""
Master Audio Pipeline for Ghostline 60-Second Product Launch Videos.
Synthesizes professional voiceover, places each line at precise storyboard timestamps,
mixes with modern electronic backing track (ducked during speech),
and integrates subtle UI sound effects.
Output: master_audio_60s.wav (60.00s, 48kHz, 2-channel stereo).
"""

import os
import sys
import subprocess
from pathlib import Path
import pyttsx3
import wave
import numpy as np

root_dir = Path(__file__).resolve().parent.parent
OUTPUT_DIR = root_dir / "recordings" / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_VOICEOVER_WAV = OUTPUT_DIR / "voiceover_master_60s.wav"
MASTER_AUDIO_WAV = OUTPUT_DIR / "master_audio_60s.wav"
MUSIC_SRC = root_dir / ".agents" / "skills" / "brag" / "assets" / "music" / "happy-beats-business-moves-vol-12-by-ende-dot-app.mp3"
SFX_DIR = root_dir / "brag-output-2026-10-26-021000" / "composition" / "assets" / "sfx"

SAMPLE_RATE = 48000
TOTAL_DURATION = 60.0
TOTAL_SAMPLES = int(SAMPLE_RATE * TOTAL_DURATION)

VOICEOVER_LINES = [
    {
        "start_sec": 1.2,
        "text": "Meet Ghostline. An ultra-fast, local AI assistant built directly into the Windows desktop."
    },
    {
        "start_sec": 7.5,
        "text": "Hit Alt plus slash. Ghostline scans the question on your screen, parses every option with local OCR, and delivers the exact verified answer inside a floating HUD in milliseconds."
    },
    {
        "start_sec": 20.5,
        "text": "It lives in your system tray. Need zero visual footprint? Ghostline signals answers discreetly through your keyboard's Caps Lock indicator and tray badge."
    },
    {
        "start_sec": 32.5,
        "text": "During live video calls, Ghostline captures both your mic and system audio loopback. It filters out casual acknowledgements, streams structured answers in real time, and keeps your full conversation history."
    },
    {
        "start_sec": 48.0,
        "text": "Copy solutions with a single click. Every extraction and inference runs entirely on your local machine—fast, private, and dependable."
    },
    {
        "start_sec": 55.5,
        "text": "Ghostline. Your screen. Your context. Your local AI."
    }
]


def generate_speech_clips():
    """Synthesize each voiceover line to WAV using pyttsx3."""
    engine = pyttsx3.init()
    engine.setProperty("rate", 182)  # Energetic, crisp, natural conversational pace
    engine.setProperty("volume", 1.0)
    
    # Try selecting a clear English voice (David or Zira)
    voices = engine.getProperty("voices")
    david_voice = next((v.id for v in voices if "David" in v.name), voices[0].id)
    engine.setProperty("voice", david_voice)

    clips = []
    for i, line in enumerate(VOICEOVER_LINES):
        clip_path = OUTPUT_DIR / f"vo_line_{i+1}.wav"
        engine.save_to_file(line["text"], str(clip_path))
        engine.runAndWait()
        
        # Read clip info via ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(clip_path)
        ]
        dur = float(subprocess.check_output(probe_cmd).decode().strip())
        print(f"  [+] Line {i+1} generated ({dur:.2f}s): \"{line['text'][:40]}...\"")
        clips.append({
            "path": clip_path,
            "start_sec": line["start_sec"],
            "duration": dur
        })
    return clips


def assemble_voiceover_track(clips):
    """Combine voiceover clips into exact 60.0s 48kHz stereo master WAV."""
    print("[*] Assembling 60.0s master voiceover track...")
    master_vo = np.zeros((TOTAL_SAMPLES, 2), dtype=np.float32)

    for i, clip in enumerate(clips):
        # Convert clip to 48kHz float32 stereo via ffmpeg
        resampled_clip = OUTPUT_DIR / f"vo_line_{i+1}_48k.raw"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip["path"]),
            "-ar", "48000",
            "-ac", "2",
            "-f", "f32le",
            str(resampled_clip)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        data = np.fromfile(str(resampled_clip), dtype=np.float32).reshape(-1, 2)
        start_sample = int(clip["start_sec"] * SAMPLE_RATE)
        end_sample = min(start_sample + len(data), TOTAL_SAMPLES)
        length = end_sample - start_sample
        master_vo[start_sample:end_sample] += data[:length]

    # Normalize voiceover to peak at -1 dBFS (0.89)
    peak = np.max(np.abs(master_vo))
    if peak > 0:
        master_vo = master_vo * (0.89 / peak)

    # Convert to 16-bit PCM and write WAV
    master_pcm = (master_vo * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(MASTER_VOICEOVER_WAV), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(master_pcm.tobytes())
    print(f"[+] Master voiceover track ready: {MASTER_VOICEOVER_WAV}")


def mix_final_soundtrack():
    """Mix voiceover, background music (ducked during speech), and sound effects."""
    print("[*] Mixing master audio with ducked music and SFX...")
    
    # Generate synthesized SFX cues (hotkey click, lock chime, tray click, copy ping)
    # Using ffmpeg's lavfi audio synth for crisp digital UI feedback cues
    sfx_hotkey = OUTPUT_DIR / "sfx_hotkey.wav"
    sfx_ping = OUTPUT_DIR / "sfx_ping.wav"
    sfx_copy = OUTPUT_DIR / "sfx_copy.wav"

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=1200:duration=0.08",
        "-af", "afade=t=out:st=0.02:d=0.06,volume=0.3",
        str(sfx_hotkey)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=1800:duration=0.15",
        "-af", "afade=t=out:st=0.04:d=0.11,volume=0.25",
        str(sfx_ping)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=1500:duration=0.12",
        "-af", "afade=t=out:st=0.03:d=0.09,volume=0.3",
        str(sfx_copy)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Build ffmpeg filter_complex to duck music under voiceover and insert SFX
    # Music: volume -14dB generally, sidechain ducked by voiceover to -22dB
    filter_complex = (
        # [0:a] is voiceover
        # [1:a] is music
        "[1:a]aloop=loop=-1:size=2e+09,atrim=0:60,afade=t=in:st=0:d=1.0,afade=t=out:st=58.0:d=2.0,volume=0.22[bg_music];"
        # Delay and volume for SFX
        "[2:a]adelay=11200|11200,volume=0.6[sfx1];"  # Hotkey at 11.2s
        "[3:a]adelay=14800|14800,volume=0.7[sfx2];"  # Answer lock at 14.8s
        "[4:a]adelay=52000|52000,volume=0.7[sfx3];"  # Copy answer at 52.0s
        # Sidechain ducking of background music against voiceover
        "[bg_music][0:a]sidechaincompress=threshold=0.08:ratio=6:attack=30:release=350[ducked_music];"
        # Mix everything together
        "[ducked_music][0:a][sfx1][sfx2][sfx3]amix=inputs=5:duration=first:dropout_transition=2,volume=1.2[out_a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(MASTER_VOICEOVER_WAV),
        "-i", str(MUSIC_SRC),
        "-i", str(sfx_hotkey),
        "-i", str(sfx_ping),
        "-i", str(sfx_copy),
        "-filter_complex", filter_complex,
        "-map", "[out_a]",
        "-ar", "48000",
        "-ac", "2",
        "-t", "60.0",
        str(MASTER_AUDIO_WAV)
    ]
    subprocess.run(cmd, check=True)
    print(f"[+] Master mixed soundtrack generated: {MASTER_AUDIO_WAV}")


def main():
    print("[*] Starting Audio Production Pipeline...")
    clips = generate_speech_clips()
    assemble_voiceover_track(clips)
    mix_final_soundtrack()
    print("[+] Audio Production Complete!")


if __name__ == "__main__":
    main()
