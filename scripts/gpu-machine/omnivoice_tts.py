#!/usr/bin/env python3
"""
omnivoice_tts.py — Zero-shot TTS wrapper for OmniVoice on the GPU machine.
Usage: python3 omnivoice_tts.py input.txt output.mp3 output.vtt [subtitle.txt]

  input.txt     — TTS text (may contain em-dashes / ellipses for rhythm)
  output.mp3    — Generated audio
  output.vtt    — WebVTT subtitles aligned to the audio
  subtitle.txt  — (Optional) Clean subtitle text (contractions restored, no "...")
                   Displayed in VTT while TTS uses the main text.

Prerequisites:
  - OmniVoice repo cloned at ~/new/OmniVoice/OmniVoice
  - Python venv at ~/new/OmniVoice/venv with OmniVoice installed
  - Model: k2-fsa/OmniVoice (auto-downloaded on first run)
  - GPU with >=4 GB VRAM (GTX 1050 Ti minimum)

Settings used in production:
  NUM_STEPS = 24
  SPEED     = 1.1
  PAUSE_MS  = 250
  VOICE     = 'Male, Young Adult, American Accent'
"""
import sys, os, subprocess, tempfile, json, re
from pathlib import Path

VENV_PYTHON  = os.path.expanduser('~/new/OmniVoice/venv/bin/python3')
OMNI_REPO    = os.path.expanduser('~/new/OmniVoice/OmniVoice')
MODEL_ID     = 'k2-fsa/OmniVoice'
NUM_STEPS    = 24
SPEED        = 1.1
PAUSE_MS     = 250
VOICE        = 'Male, Young Adult, American Accent'


def run_omnivoice(text_file: str, audio_out: str, vtt_out: str,
                  subtitle_file: str | None = None) -> None:
    """Call OmniVoice inference and produce MP3 + VTT."""
    script = f"""
import sys, torch, soundfile as sf, numpy as np
sys.path.insert(0, {repr(OMNI_REPO)})
from omnivoice import OmniVoice  # adjust import to match actual OmniVoice API

with open({repr(text_file)}) as f:
    text = f.read().strip()

sub_text = text
if {repr(subtitle_file)} and open({repr(subtitle_file or '')}).read().strip():
    with open({repr(subtitle_file)}) as f:
        sub_text = f.read().strip()

model = OmniVoice.from_pretrained({repr(MODEL_ID)})
model.eval()

result = model.synthesize(
    text=text,
    voice={repr(VOICE)},
    num_steps={NUM_STEPS},
    speed={SPEED},
    pause_ms={PAUSE_MS},
)

# result.audio: numpy float32 array, result.sample_rate: int
# result.word_timestamps: list of (word, start_s, end_s)
sf.write({repr(audio_out)}.replace('.mp3', '.wav'), result.audio, result.sample_rate)

# Convert WAV → MP3
import subprocess
subprocess.run(['ffmpeg', '-y', '-i', {repr(audio_out)}.replace('.mp3','.wav'),
                '-codec:a', 'libmp3lame', '-q:a', '2', {repr(audio_out)}], check=True)

# Build WebVTT
words = result.word_timestamps  # [(word, start, end), ...]
CHUNK = 7  # words per subtitle line
def ts(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{{h:02d}}:{{m:02d}}:{{sec:06.3f}}"

sub_words = sub_text.split()
vtt_lines = ["WEBVTT", ""]
for i in range(0, len(words), CHUNK):
    chunk = words[i:i+CHUNK]
    start = chunk[0][1]
    end   = chunk[-1][2]
    # map to subtitle text words (best-effort alignment)
    sw = sub_words[i:i+CHUNK]
    line = " ".join(sw)
    vtt_lines += [f"{{ts(start)}} --> {{ts(end)}}", line, ""]

with open({repr(vtt_out)}, 'w') as f:
    f.write("\\n".join(vtt_lines))

print(f"TTS complete: {{result.audio.shape[0] / result.sample_rate:.1f}}s")
"""
    tmp = tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w')
    tmp.write(script)
    tmp.close()
    try:
        subprocess.run([VENV_PYTHON, tmp.name], check=True)
    finally:
        os.unlink(tmp.name)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: omnivoice_tts.py input.txt output.mp3 output.vtt [subtitle.txt]')
        sys.exit(1)
    subtitle = sys.argv[4] if len(sys.argv) >= 5 else None
    run_omnivoice(sys.argv[1], sys.argv[2], sys.argv[3], subtitle)
