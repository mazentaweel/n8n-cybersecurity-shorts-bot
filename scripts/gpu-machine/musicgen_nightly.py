#!/usr/bin/env python3
"""
musicgen_nightly.py — Nightly background music generation for the Shorts bot.

Runs on the GPU machine (cron or systemd timer, default 03:00).
Generates 10 mood-tagged music tracks using MusicGen and writes them to the
NFS share at /mnt/machine_a_tmp/ (or directly to ~/bgmusic/generated/ if NFS
is not configured), then appends entries to catalog.json on Machine A.

Prerequisites (GPU machine):
  pip install audiocraft  # Meta's MusicGen — requires PyTorch + CUDA
  # NFS mount (optional): Machine A exports ~/bgmusic/generated/ at /mnt/machine_a_tmp/generated/

Catalog format (~/bgmusic/generated/catalog.json on Machine A):
  [{"file": "gen_dark_1748834400.mp3", "mood": "dark", "generated_at": 1748834400}, ...]

Usage:
  python3 musicgen_nightly.py [--output-dir /path/to/bgmusic/generated]
"""

import os, sys, json, time, argparse, hashlib
from pathlib import Path

# MusicGen prompts per mood — tuned for cybersecurity-themed visuals
MOOD_PROMPTS = {
    'dark':       'dark ambient electronic music, tense, slow bass drone, minor key, no drums, cinematic',
    'tense':      'tense electronic thriller music, pulsing synth, high tension, suspenseful, film score style',
    'dramatic':   'dramatic orchestral hybrid, powerful percussion, dark strings, cinematic climax, intense',
    'mysterious': 'mysterious ambient music, ethereal pads, slow evolving textures, sparse, eerie, atmospheric',
    'cinematic':  'cinematic electronic score, epic atmosphere, subtle bass, evolving dynamics, film trailer style',
    'energetic':  'energetic dark electronic, driving beat, aggressive synth, hacker vibes, fast paced, intense',
}

DURATION_SECS = 60    # each track — long enough for a 65-second Short
MODEL_NAME    = 'facebook/musicgen-medium'  # swap to -small for less VRAM
CATALOG_MAX   = 30    # keep last N entries in catalog (prevents unbounded growth)


def generate_track(model, prompt: str, duration: int) -> 'np.ndarray':
    """Run MusicGen inference and return a float32 numpy array."""
    from audiocraft.models import MusicGen
    model.set_generation_params(duration=duration)
    wav = model.generate([prompt])          # returns (batch, channels, samples)
    return wav[0].cpu().numpy()             # (channels, samples)


def save_mp3(audio: 'np.ndarray', sample_rate: int, path: str) -> None:
    import numpy as np, soundfile as sf, subprocess, tempfile
    # audiocraft returns (channels, samples); soundfile wants (samples, channels)
    wav_path = path.replace('.mp3', '.wav')
    sf.write(wav_path, audio.T, sample_rate)
    subprocess.run(
        ['ffmpeg', '-y', '-i', wav_path,
         '-codec:a', 'libmp3lame', '-q:a', '2', path],
        check=True, capture_output=True
    )
    os.unlink(wav_path)


def update_catalog(catalog_path: str, new_entries: list) -> None:
    existing = []
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path) as f:
                existing = json.load(f)
        except Exception:
            existing = []
    combined = existing + new_entries
    # Keep only the most recent CATALOG_MAX entries
    combined = combined[-CATALOG_MAX:]
    with open(catalog_path, 'w') as f:
        json.dump(combined, f, indent=2)
    print(f'Catalog updated: {len(combined)} entries at {catalog_path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default=os.path.expanduser('~/bgmusic/generated'),
                        help='Directory to write MP3 files and catalog.json')
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = str(out_dir / 'catalog.json')

    print(f'Loading MusicGen model: {MODEL_NAME}')
    try:
        from audiocraft.models import MusicGen
        model = MusicGen.get_pretrained(MODEL_NAME)
        sample_rate = model.sample_rate
    except ImportError:
        print('ERROR: audiocraft not installed. Run: pip install audiocraft')
        sys.exit(1)

    new_entries = []
    ts = int(time.time())

    for mood, prompt in MOOD_PROMPTS.items():
        filename = f'gen_{mood}_{ts}.mp3'
        out_path = str(out_dir / filename)
        print(f'Generating: {mood} — {prompt[:60]}...')
        try:
            start = time.time()
            audio = generate_track(model, prompt, DURATION_SECS)
            save_mp3(audio, sample_rate, out_path)
            elapsed = time.time() - start
            size_kb = os.path.getsize(out_path) // 1024
            print(f'  -> {filename} ({size_kb} KB, {elapsed:.1f}s)')
            new_entries.append({
                'file':         filename,
                'mood':         mood,
                'generated_at': ts,
                'duration':     DURATION_SECS,
            })
            ts += 1   # ensure unique timestamps if loop is fast
        except Exception as e:
            print(f'  WARN: failed to generate {mood}: {e}')

    if new_entries:
        update_catalog(catalog_path, new_entries)
    else:
        print('No tracks generated — catalog unchanged.')

    print('Done.')


if __name__ == '__main__':
    main()
