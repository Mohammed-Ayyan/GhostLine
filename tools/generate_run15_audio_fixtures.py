"""
Generates synthetic audio test inputs for Ghostline Run 15 Part A:
(i) 30 s of low-level room-like noise (-50 dBFS)
(ii) 30 s of music-like tones (-30 dBFS)
(iii) 30 s of digital silence
(iv) A spoken English sentence in system audio + 20dB attenuated, 250ms delayed mic echo
(v) Synthesized quiet speech at -40 dBFS
All audio is 16kHz mono 16-bit PCM.
"""

import math
import wave
import struct
import subprocess
from pathlib import Path
import numpy as np

SAMPLE_RATE = 16000
FIXTURES_DIR = Path("tests/fixtures/run15_audio").resolve()
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

def save_wav_16k(path: Path, samples: np.ndarray):
    samples = np.clip(samples, -1.0, 1.0)
    int_samples = (samples * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(int_samples.tobytes())
    print(f"  [x] Saved {path.name}: {len(samples)/SAMPLE_RATE:.1f}s, Peak={np.max(np.abs(samples)):.4f}")

def generate_fixtures():
    print(f"[*] Generating Run 15 audio fixtures in {FIXTURES_DIR}...")

    # (i) 30 s low-level room-like noise (-50 dBFS = amplitude ~ 0.00316)
    dur = 30.0
    n = int(SAMPLE_RATE * dur)
    # Generate pink-like filtered noise
    white = np.random.uniform(-1.0, 1.0, n)
    # Simple lowpass filter to simulate room rumble
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    pink = np.convolve(white, [0.1, 0.2, 0.3, 0.2, 0.1], mode='same')
    # Scale to -50 dBFS
    amp_50db = 10.0 ** (-50.0 / 20.0)
    pink = (pink / (np.max(np.abs(pink)) + 1e-8)) * amp_50db
    save_wav_16k(FIXTURES_DIR / "noise_room_30s.wav", pink)

    # (ii) 30 s music-like tones (-30 dBFS = amplitude ~ 0.0316)
    amp_30db = 10.0 ** (-30.0 / 20.0)
    t = np.linspace(0, dur, n, endpoint=False)
    # Melodic chord sequence: C4 (261.6Hz), E4 (329.6Hz), G4 (392.0Hz), A4 (440.0Hz)
    tones = (
        0.3 * np.sin(2 * np.pi * 261.63 * t) +
        0.3 * np.sin(2 * np.pi * 329.63 * t) +
        0.2 * np.sin(2 * np.pi * 392.00 * t) +
        0.2 * np.sin(2 * np.pi * 440.00 * t * (1.0 + 0.05 * np.sin(2 * np.pi * 4 * t))) # vibrato
    )
    tones = (tones / np.max(np.abs(tones))) * amp_30db
    save_wav_16k(FIXTURES_DIR / "music_tones_30s.wav", tones)

    # (iii) 30 s digital silence
    silence = np.zeros(n, dtype=np.float32)
    save_wav_16k(FIXTURES_DIR / "digital_silence_30s.wav", silence)

    # (iv) Spoken English sentence with mic echo
    # Use PowerShell System.Speech to synthesize an authentic sentence
    temp_wav = FIXTURES_DIR / "_temp_speech.wav"
    ps_cmd = f"""
    Add-Type -AssemblyName System.Speech;
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
    $synth.SetOutputToWaveFile('{temp_wav}');
    $synth.Speak('We need to discuss the architecture for the database migration.');
    $synth.Dispose();
    """
    subprocess.run(["powershell", "-Command", ps_cmd], check=True, stdout=subprocess.DEVNULL)
    
    # Read temp speech and resample to 16k
    with wave.open(str(temp_wav), "rb") as wf:
        n_ch = wf.getnchannels()
        s_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    temp_wav.unlink(missing_ok=True)
    
    speech_data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_ch > 1:
        speech_data = speech_data.reshape(-1, n_ch)[:, 0]
    
    # Resample to 16000
    if s_rate != 16000:
        import scipy.signal
        num_target = int(len(speech_data) * 16000 / s_rate)
        speech_16k = scipy.signal.resample(speech_data, num_target)
    else:
        speech_16k = speech_data

    # Normalize clean system speech to -18 dBFS (amp ~ 0.125)
    clean_sys = (speech_16k / np.max(np.abs(speech_16k))) * (10.0 ** (-18.0 / 20.0))
    save_wav_16k(FIXTURES_DIR / "speech_clean_system.wav", clean_sys)

    # Mic echo: delayed by 250ms (4000 samples) and 20 dB lower (-38 dBFS)
    delay_samples = int(0.250 * SAMPLE_RATE)
    attenuation = 10.0 ** (-20.0 / 20.0) # 0.10x
    mic_echo = np.zeros(len(clean_sys) + delay_samples, dtype=np.float32)
    mic_echo[delay_samples:] = clean_sys * attenuation
    save_wav_16k(FIXTURES_DIR / "speech_mic_echo.wav", mic_echo)

    # (v) Synthesized quiet speech at -40 dBFS (amp = 0.010)
    quiet_speech = (speech_16k / np.max(np.abs(speech_16k))) * (10.0 ** (-40.0 / 20.0))
    save_wav_16k(FIXTURES_DIR / "speech_quiet_minus40db.wav", quiet_speech)

    print("[✓] All 6 audio fixtures generated successfully.")

if __name__ == "__main__":
    generate_fixtures()

