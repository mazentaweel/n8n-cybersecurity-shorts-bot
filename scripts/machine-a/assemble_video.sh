#!/usr/bin/env bash
# assemble_video.sh — Download B-roll clips, burn subtitles, mix voice + music.
# Called by the n8n "Assemble Video with FFmpeg" SSH node.
#
# Environment expected (set by n8n before calling):
#   TS         — millisecond timestamp (unique run ID)
#   MUSIC      — full path to background music MP3
#   Voice:     /tmp/voice_${TS}.mp3   (from GPU machine via SCP)
#   Subtitles: /tmp/subs_${TS}.vtt    (from GPU machine via SCP)
#   Downloads: /tmp/download_${TS}.sh (wget commands for Pexels clips)
#   Concat:    /tmp/list_${TS}.txt    (ffmpeg concat file)
#
# Output:      /tmp/final_${TS}.mp4

set -euo pipefail

TS="${TS:?TS not set}"
MUSIC="${MUSIC:?MUSIC not set}"

[ -f "/tmp/voice_${TS}.mp3" ] || { echo "FATAL: voice missing"; exit 1; }

# ── Resolve music file ────────────────────────────────────────────────────────
if [ ! -f "$MUSIC" ]; then
  echo "WARN: catalog music missing ($MUSIC), falling back to static"
  MUSIC=$(ls /home/YOUR_USER/bgmusic/*.mp3 2>/dev/null | shuf -n1)
  [ -z "$MUSIC" ] && { echo "FATAL: no fallback music found"; exit 1; }
  echo "FALLBACK_MUSIC=$MUSIC"
fi

# ── Download B-roll clips ─────────────────────────────────────────────────────
bash "/tmp/download_${TS}.sh"
CLIP_COUNT=$(ls "/tmp/clip"*"_${TS}.mp4" 2>/dev/null | wc -l)
echo "CLIPS_DOWNLOADED=$CLIP_COUNT"

# ── Measure voice duration ────────────────────────────────────────────────────
VOICE_DUR=$(/usr/bin/ffprobe -v error \
  -show_entries format=duration -of csv=p=0 \
  "/tmp/voice_${TS}.mp3")
FINAL_DUR=$(echo "$VOICE_DUR" | awk '{printf "%.1f", $1+0.5}')
BG_DUR=$(echo "$FINAL_DUR"  | awk '{printf "%.0f", $1+15}')
echo "VOICE_DUR=$VOICE_DUR  FINAL=$FINAL_DUR  BG=$BG_DUR"

# ── Build background video ────────────────────────────────────────────────────
# NOTE: fps=30 in the vf filter is mandatory — mixed-FPS Pexels clips cause the
# video to freeze while audio continues if fps is not locked here.
if [ "$CLIP_COUNT" -lt 2 ]; then
  echo "WARN: Only $CLIP_COUNT clips — using synthetic dark background"
  /usr/bin/ffmpeg -y \
    -f lavfi -i "color=c=0x0d1117:size=1080x1920:rate=30" \
    -t "$BG_DUR" \
    "/tmp/bg_${TS}.mp4" 2>"/tmp/ffmpeg_bg_${TS}.log"
else
  /usr/bin/ffmpeg -y \
    -stream_loop 5 -f concat -safe 0 -i "/tmp/list_${TS}.txt" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30" \
    -t "$BG_DUR" -an \
    "/tmp/bg_${TS}.mp4" 2>"/tmp/ffmpeg_bg_${TS}.log"
fi

[ -f "/tmp/bg_${TS}.mp4" ] || {
  echo "FATAL: background video failed"
  tail -5 "/tmp/ffmpeg_bg_${TS}.log"
  exit 1
}

# ── Convert VTT → ASS subtitles ───────────────────────────────────────────────
VFILTER="null"
if [ -f "/tmp/subs_${TS}.vtt" ]; then
  python3 /home/YOUR_USER/vtt2ass.py "/tmp/subs_${TS}.vtt" "/tmp/subs_${TS}.ass"
  if [ -f "/tmp/subs_${TS}.ass" ]; then
    VFILTER="subtitles=/tmp/subs_${TS}.ass:fontsdir=/usr/share/fonts"
    echo "Using ASS subtitles"
  else
    echo "WARN: ASS conversion failed — no subtitles"
  fi
else
  echo "WARN: no subtitle file found"
fi

# ── Final render: background + voice + music (sidechain compression) ──────────
# Audio chain:
#   voice → split (playback + sidechain source)
#   music → sidechain compress (ducks under voice)
#   voice + ducked music → amix for first stream, then dropout transition
# Video chain:
#   background → burn ASS subtitles → lock fps=30
/usr/bin/ffmpeg -y \
  -stream_loop -1 -i "/tmp/bg_${TS}.mp4" \
  -i "/tmp/voice_${TS}.mp3" \
  -stream_loop -1 -i "$MUSIC" \
  -filter_complex \
    "[1:a]volume=1.0,asplit=2[voice][voice_sc];
     [2:a]volume=0.8[music_in];
     [music_in][voice_sc]sidechaincompress=threshold=0.02:ratio=6:attack=200:release=800[music_ducked];
     [voice][music_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout];
     [0:v]${VFILTER},fps=30[vout]" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  -t "$FINAL_DUR" \
  "/tmp/final_${TS}.mp4" 2>"/tmp/ffmpeg_final_${TS}.log"

[ -f "/tmp/final_${TS}.mp4" ] || {
  echo "FATAL: final video failed"
  tail -10 "/tmp/ffmpeg_final_${TS}.log"
  exit 1
}

SIZE=$( stat -c%s "/tmp/final_${TS}.mp4")
ACT_DUR=$(/usr/bin/ffprobe -v error \
  -show_entries format=duration -of csv=p=0 \
  "/tmp/final_${TS}.mp4" 2>/dev/null)
echo "VIDEO_DONE"
echo "VIDEO_SIZE=$SIZE"
echo "ACTUAL_DURATION=$ACT_DUR"
ls -lh "/tmp/final_${TS}.mp4"
