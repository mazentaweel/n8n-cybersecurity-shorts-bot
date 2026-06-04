#!/usr/bin/env python3
"""
kokoro_tts.py — Kokoro ONNX TTS fallback for the GPU machine.
Usage: python3 kokoro_tts.py input.txt output.mp3 output.vtt

Called automatically by generate_voice.sh when OmniVoice fails.

Prerequisites:
  pip install kokoro-onnx soundfile numpy
  # or from the OmniVoice venv which includes it as a dependency
"""
import sys, os, subprocess, tempfile

VOICE  = 'af_sarah'   # American female — swap to 'am_adam' for male
SPEED  = 1.1
LANG   = 'en-us'


def run_kokoro(text_file: str, audio_out: str, vtt_out: str) -> None:
    from kokoro_onnx import Kokoro
    import numpy as np, soundfile as sf

    with open(text_file) as f:
        text = f.read().strip()

    kokoro = Kokoro('kokoro-v0_19.onnx', 'voices.bin')
    samples, sample_rate = kokoro.create(text, voice=VOICE, speed=SPEED, lang=LANG)

    wav = audio_out.replace('.mp3', '.wav')
    sf.write(wav, samples, sample_rate)
    subprocess.run(['ffmpeg', '-y', '-i', wav, '-codec:a', 'libmp3lame',
                    '-q:a', '2', audio_out], check=True)
    os.unlink(wav)

    # Minimal VTT (no word-level timestamps — whole text as one cue)
    duration = len(samples) / sample_rate
    def ts(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f'{h:02d}:{m:02d}:{sec:06.3f}'

    with open(vtt_out, 'w') as f:
        f.write('WEBVTT\n\n')
        f.write(f'{ts(0.0)} --> {ts(duration)}\n')
        f.write(text + '\n')

    print(f'Kokoro TTS complete: {duration:.1f}s')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: kokoro_tts.py input.txt output.mp3 output.vtt')
        sys.exit(1)
    run_kokoro(sys.argv[1], sys.argv[2], sys.argv[3])
