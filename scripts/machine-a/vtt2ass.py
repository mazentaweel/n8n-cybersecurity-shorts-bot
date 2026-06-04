#!/usr/bin/env python3
"""
vtt2ass.py — Convert WebVTT subtitles to ASS for 9:16 (1080x1920) YouTube Shorts.
Usage: python3 vtt2ass.py input.vtt output.ass

Style: DejaVu Sans Bold, 52pt, white, centred, MarginV=322 (lower-third position).
The output is intended for use with ffmpeg's `subtitles=` filter.
"""
import sys, re

PLAY_RES_Y = 1920
PLAY_RES_X = 1080
MARGIN_V   = 322
FONT_NAME  = 'DejaVu Sans'
FONT_SIZE  = 52
OUTLINE    = 3
SHADOW     = 1

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{OUTLINE},{SHADOW},2,60,60,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def vtt_ts_to_ass(ts: str) -> str:
    """Convert VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to ASS (H:MM:SS.cc)."""
    ts = ts.strip()
    if ts.count(':') == 1:
        ts = '00:' + ts
    parts = ts.split(':')
    h, m = int(parts[0]), int(parts[1])
    s_ms = parts[2].replace(',', '.')
    s, ms = s_ms.split('.')
    s, ms = int(s), int(ms)
    cc = ms // 10
    return f'{h}:{m:02d}:{s:02d}.{cc:02d}'


def clean_text(t: str) -> str:
    """Strip VTT tags and normalise whitespace."""
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def convert(vtt_path: str, ass_path: str) -> None:
    with open(vtt_path, encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'\n{2,}', content.strip())
    events = []

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        # Find the timing line
        timing_idx = None
        for i, line in enumerate(lines):
            if '-->' in line:
                timing_idx = i
                break
        if timing_idx is None:
            continue
        timing = lines[timing_idx]
        m = re.match(r'([\d:,.]+)\s*-->\s*([\d:,.]+)', timing)
        if not m:
            continue
        start = vtt_ts_to_ass(m.group(1))
        end   = vtt_ts_to_ass(m.group(2))
        text_lines = lines[timing_idx + 1:]
        text = ' '.join(clean_text(l) for l in text_lines if l.strip())
        if text:
            events.append(f'Dialogue: 0,{start},{end},Default,,0,0,0,,{text}')

    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(ASS_HEADER)
        f.write('\n'.join(events) + '\n')

    print(f'Converted {len(events)} cues → {ass_path}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: vtt2ass.py input.vtt output.ass')
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
