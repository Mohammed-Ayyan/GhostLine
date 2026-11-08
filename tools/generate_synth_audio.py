"""
Ghostline Original Synthesizer Audio Generator.
Generates an original electronic music bed with synchronized UI sound effects
using mathematical wave synthesis in numpy, rendered to 48kHz 16-bit stereo WAV.
Processed through ffmpeg loudnorm to hit -14.0 LUFS and <= -1.0 dBTP.
"""

import os
import sys
import math
import wave
import struct
import subprocess
from pathlib import Path
import numpy as np

SAMPLE_RATE = 48000
BPM = 120.0
BEAT_DUR = 60.0 / BPM  # 0.5 seconds per beat
BAR_DUR = BEAT_DUR * 4.0  # 2.0 seconds per bar

OUTPUT_DIR = Path("../ghostline_launch_video/run10/audio").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_tone(freq, duration, sample_rate=SAMPLE_RATE, wave_type="sine", attack=0.01, decay=0.05, sustain=0.7, release=0.05):
    """Generates an enveloped musical tone."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    if wave_type == "sine":
        samples = np.sin(2 * np.pi * freq * t)
    elif wave_type == "triangle":
        samples = 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
    elif wave_type == "sawtooth":
        samples = 2 * (t * freq - np.floor(t * freq + 0.5))
    elif wave_type == "pulse":
        samples = np.where(np.sin(2 * np.pi * freq * t) > 0, 0.8, -0.8)
    else:
        samples = np.sin(2 * np.pi * freq * t)

    # ADSR Envelope
    n_samples = len(t)
    n_att = int(sample_rate * attack)
    n_dec = int(sample_rate * decay)
    n_rel = int(sample_rate * release)
    n_sus = max(0, n_samples - (n_att + n_dec + n_rel))

    env = np.ones(n_samples)
    if n_att > 0 and n_att <= n_samples:
        env[:n_att] = np.linspace(0, 1, n_att)
    if n_dec > 0 and (n_att + n_dec) <= n_samples:
        env[n_att:n_att + n_dec] = np.linspace(1, sustain, n_dec)
    if n_sus > 0 and (n_att + n_dec + n_sus) <= n_samples:
        env[n_att + n_dec:n_att + n_dec + n_sus] = sustain
    if n_rel > 0 and n_rel <= n_samples:
        env[-n_rel:] = np.linspace(env[-n_rel], 0, n_rel)

    return samples * env

def generate_noise(duration, sample_rate=SAMPLE_RATE):
    """Generates white noise."""
    return np.random.uniform(-1, 1, int(sample_rate * duration))

def generate_sfx(name, duration=0.3):
    """Synthesizes discrete UI sound effects."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    if name == "keycap_click":
        # Mechanical keyboard transient click: high band burst + low thump
        click = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 85)
        thump = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 40)
        noise = generate_noise(duration) * np.exp(-t * 120) * 0.4
        sfx = (click * 0.5 + thump * 0.4 + noise * 0.2)
    elif name == "whoosh":
        # Frequency swept noise filter
        noise = generate_noise(duration)
        sweep = np.sin(np.pi * t / duration) ** 2
        sfx = noise * sweep * 0.4
    elif name == "success_chime":
        # Two-tone bell harmonic (C6 + E6)
        chime1 = np.sin(2 * np.pi * 1046.5 * t) * np.exp(-t * 8)
        chime2 = np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 9)
        sfx = (chime1 * 0.6 + chime2 * 0.4)
    elif name == "sub_drop":
        # Pitch-falling sub bass
        freqs = np.linspace(120, 35, len(t))
        phase = 2 * np.pi * np.cumsum(freqs) / SAMPLE_RATE
        sfx = np.sin(phase) * np.exp(-t * 4) * 0.8
    else:
        sfx = np.zeros(len(t))
    return sfx

def compose_track(total_duration_sec=92.0, is_hero=True):
    """Composes a complete multi-track electronic piece synced to 120 BPM."""
    n_total = int(SAMPLE_RATE * total_duration_sec)
    left = np.zeros(n_total)
    right = np.zeros(n_total)

    # Chord progression: Dm (D-F-A), Bb (Bb-D-F), F (F-A-C), C (C-E-G)
    progression = [
        {"root": 146.83, "chord": [293.66, 349.23, 440.00]},  # D3 / D4-F4-A4
        {"root": 116.54, "chord": [233.08, 293.66, 349.23]},  # Bb2 / Bb3-D4-F4
        {"root": 87.31,  "chord": [174.61, 220.00, 261.63]},  # F2 / F3-A3-C4
        {"root": 130.81, "chord": [261.63, 329.63, 392.00]}   # C3 / C4-E4-G4
    ]

    total_bars = int(math.ceil(total_duration_sec / BAR_DUR))

    # 1. Pads and Bassline
    for bar_idx in range(total_bars):
        chord_info = progression[bar_idx % len(progression)]
        start_sec = bar_idx * BAR_DUR
        start_sample = int(start_sec * SAMPLE_RATE)
        if start_sample >= n_total:
            break

        dur = min(BAR_DUR, total_duration_sec - start_sec)
        n_bar = int(dur * SAMPLE_RATE)

        # Pad notes
        for note_freq in chord_info["chord"]:
            pad_left = generate_tone(note_freq, dur, wave_type="triangle", attack=0.25, decay=0.1, sustain=0.6, release=0.3)
            pad_right = generate_tone(note_freq * 1.003, dur, wave_type="triangle", attack=0.25, decay=0.1, sustain=0.6, release=0.3)
            left[start_sample:start_sample + n_bar] += pad_left[:n_bar] * 0.12
            right[start_sample:start_sample + n_bar] += pad_right[:n_bar] * 0.12

        # Bass pulse on beat 1 and beat 3
        bass_note = chord_info["root"]
        for b in [0, 2]:
            b_sec = start_sec + b * BEAT_DUR
            b_sample = int(b_sec * SAMPLE_RATE)
            if b_sample < n_total:
                b_dur = min(BEAT_DUR * 1.5, total_duration_sec - b_sec)
                bass = generate_tone(bass_note, b_dur, wave_type="sine", attack=0.02, decay=0.15, sustain=0.5, release=0.1)
                n_b = len(bass)
                left[b_sample:min(n_total, b_sample + n_b)] += bass[:max(0, min(n_b, n_total - b_sample))] * 0.28
                right[b_sample:min(n_total, b_sample + n_b)] += bass[:max(0, min(n_b, n_total - b_sample))] * 0.28

    # 2. Arpeggiator / Pluck rhythm (16th notes)
    arp_scale = [440.0, 523.25, 587.33, 659.25, 783.99, 880.0]
    sixteenth_dur = BEAT_DUR / 4.0  # 0.125s
    n_sixteenths = int(total_duration_sec / sixteenth_dur)

    for i in range(n_sixteenths):
        t_sec = i * sixteenth_dur
        idx = int(t_sec * SAMPLE_RATE)
        if idx >= n_total:
            break
        note_freq = arp_scale[i % len(arp_scale)]
        pluck = generate_tone(note_freq, sixteenth_dur * 1.8, wave_type="sine", attack=0.005, decay=0.06, sustain=0.1, release=0.04)
        n_p = len(pluck)
        pan = 0.5 + 0.3 * math.sin(i * 0.8)  # ping-pong pan
        left[idx:min(n_total, idx + n_p)] += pluck[:min(n_p, n_total - idx)] * (1.0 - pan) * 0.08
        right[idx:min(n_total, idx + n_p)] += pluck[:min(n_p, n_total - idx)] * pan * 0.08

    # 3. Drums: Kick & Snare / Rim Pulse
    total_beats = int(total_duration_sec / BEAT_DUR)
    for b in range(total_beats):
        t_sec = b * BEAT_DUR
        idx = int(t_sec * SAMPLE_RATE)
        if idx >= n_total:
            break

        # Kick on beat 1 and 3
        if b % 2 == 0:
            k_t = np.linspace(0, 0.25, int(SAMPLE_RATE * 0.25), endpoint=False)
            k_freqs = np.linspace(140, 45, len(k_t))
            k_phase = 2 * np.pi * np.cumsum(k_freqs) / SAMPLE_RATE
            kick = np.sin(k_phase) * np.exp(-k_t * 22) * 0.45
            n_k = len(kick)
            left[idx:min(n_total, idx + n_k)] += kick[:min(n_k, n_total - idx)]
            right[idx:min(n_total, idx + n_k)] += kick[:min(n_k, n_total - idx)]

        # Soft Rim / Clap on beat 2 and 4
        if b % 2 == 1:
            snare_dur = 0.15
            snare_t = np.linspace(0, snare_dur, int(SAMPLE_RATE * snare_dur), endpoint=False)
            snare_noise = generate_noise(snare_dur) * np.exp(-snare_t * 30) * 0.22
            snare_body = np.sin(2 * np.pi * 220 * snare_t) * np.exp(-snare_t * 40) * 0.18
            snare = snare_noise + snare_body
            n_s = len(snare)
            left[idx:min(n_total, idx + n_s)] += snare[:min(n_s, n_total - idx)]
            right[idx:min(n_total, idx + n_s)] += snare[:min(n_s, n_total - idx)]

    # 4. Synthesized SFX at Key Milestones
    sfx_milestones = [
        (5.0, "keycap_click"),
        (5.1, "whoosh"),
        (6.5, "success_chime"),
        (14.0, "whoosh"),
        (28.0, "whoosh"),
        (40.0, "sub_drop"),
        (54.0, "whoosh"),
        (64.0, "keycap_click"),
        (82.0, "success_chime")
    ]

    for s_time, s_name in sfx_milestones:
        if s_time < total_duration_sec:
            s_sfx = generate_sfx(s_name)
            s_idx = int(s_time * SAMPLE_RATE)
            s_len = len(s_sfx)
            if s_idx < n_total:
                end_idx = min(n_total, s_idx + s_len)
                clip_len = end_idx - s_idx
                left[s_idx:end_idx] += s_sfx[:clip_len] * 0.6
                right[s_idx:end_idx] += s_sfx[:clip_len] * 0.6

    # Normalize to prevent digital clipping before mastering
    max_val = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-6)
    left = (left / max_val) * 0.85
    right = (right / max_val) * 0.85

    return left, right

def save_wav(filename, left, right, sample_rate=SAMPLE_RATE):
    """Saves float numpy arrays to 16-bit PCM WAV."""
    left_16 = np.int16(np.clip(left * 32767.0, -32768, 32767))
    right_16 = np.int16(np.clip(right * 32767.0, -32768, 32767))
    stereo = np.empty((left_16.size + right_16.size,), dtype=np.int16)
    stereo[0::2] = left_16
    stereo[1::2] = right_16

    with wave.open(str(filename), 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())

def master_with_loudnorm(raw_wav_path, mastered_wav_path, target_lufs=-14.0):
    """Mastering filter using ffmpeg loudnorm to achieve exact -14 LUFS standard."""
    cmd = [
        "ffmpeg", "-y", "-i", str(raw_wav_path),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-ar", "48000",
        "-c:a", "pcm_s16le",
        str(mastered_wav_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_suite():
    print("[*] Generating original synthesizer audio suite...")
    
    # 1. H1 Launch Film: 92s
    print("  -> Composing 92s Launch Film track (120 BPM)...")
    l_92, r_92 = compose_track(92.0, is_hero=True)
    raw_92 = OUTPUT_DIR / "h1_raw_92s.wav"
    master_92 = OUTPUT_DIR / "h1_audio_92s.wav"
    save_wav(raw_92, l_92, r_92)
    master_with_loudnorm(raw_92, master_92, target_lufs=-14.0)
    print(f"  [OK] H1 Master Audio: {master_92}")

    # 2. V1 Setup Tutorial: 140s
    print("  -> Composing 140s Setup Tutorial track...")
    l_140, r_140 = compose_track(140.0, is_hero=False)
    raw_140 = OUTPUT_DIR / "v1_raw_140s.wav"
    master_140 = OUTPUT_DIR / "v1_audio_140s.wav"
    save_wav(raw_140, l_140, r_140)
    master_with_loudnorm(raw_140, master_140, target_lufs=-14.0)
    print(f"  [OK] V1 Master Audio: {master_140}")

    # 3. V2 Walkthrough: 180s
    print("  -> Composing 180s Walkthrough track...")
    l_180, r_180 = compose_track(180.0, is_hero=False)
    raw_180 = OUTPUT_DIR / "v2_raw_180s.wav"
    master_180 = OUTPUT_DIR / "v2_audio_180s.wav"
    save_wav(raw_180, l_180, r_180)
    master_with_loudnorm(raw_180, master_180, target_lufs=-14.0)
    print(f"  [OK] V2 Master Audio: {master_180}")

    # 4. Vertical Shorts S1-S5: 35s each
    for s_idx in range(1, 6):
        print(f"  -> Composing 35s Short S{s_idx} track...")
        l_35, r_35 = compose_track(35.0, is_hero=True)
        raw_35 = OUTPUT_DIR / f"s{s_idx}_raw_35s.wav"
        master_35 = OUTPUT_DIR / f"s{s_idx}_audio_35s.wav"
        save_wav(raw_35, l_35, r_35)
        master_with_loudnorm(raw_35, master_35, target_lufs=-14.0)
        print(f"  [OK] S{s_idx} Master Audio: {master_35}")

if __name__ == "__main__":
    generate_suite()
