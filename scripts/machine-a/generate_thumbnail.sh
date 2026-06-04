#!/usr/bin/env bash
# generate_thumbnail.sh — Create the YouTube Shorts thumbnail on Machine A.
# Called by the n8n "Generate Thumbnail" SSH node.
#
# Environment expected (set by n8n before calling):
#   TS          — millisecond timestamp (unique run ID)
#   THUMB_TEXT  — 3-word ALL-CAPS thumbnail text (plain, not base64)
#   HASHTAGS    — first 3 hashtags for bottom label
#
# Optional input:
#   /tmp/aibg_${TS}.png  — AI-generated scene (from ComfyUI on GPU machine,
#                          written via NFS mount at /mnt/machine_a_tmp/).
#                          If absent, fallback gradient design is used.
#
# Output: /tmp/thumb_${TS}.jpg

set -euo pipefail

TS="${TS:?TS not set}"
THUMB_TEXT="${THUMB_TEXT:?THUMB_TEXT not set}"
HASHTAGS="${HASHTAGS:-}"
AIBG="/tmp/aibg_${TS}.png"

FONT_BLACK='/usr/share/fonts/truetype/lato/Lato-Black.ttf'
FONT_BOLD='/usr/share/fonts/truetype/lato/Lato-Bold.ttf'
FONT_FALLBACK='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

[ -f "$FONT_BLACK" ] || FONT_BLACK="$FONT_FALLBACK"
[ -f "$FONT_BOLD"  ] || FONT_BOLD="$FONT_FALLBACK"

if [ -f "$AIBG" ]; then
  # ── Split-panel design ────────────────────────────────────────────────────
  # Left 55% (704 px): AI scene | Right 45% (576 px): dark text panel
  LINE1=$(echo "$THUMB_TEXT" | awk '{print $1" "$2}')
  LINE2=$(echo "$THUMB_TEXT" | awk '{print $3}')
  [ -z "$LINE2" ] && LINE2="$LINE1" && LINE1="CYBER"

  convert \
    \( -size 1280x720 xc:'#0d1117' \) \
    \( "$AIBG" -resize 704x720^ -gravity Center -extent 704x720 \) \
      -gravity NorthWest -composite \
    -fill '#FF2200' -draw 'rectangle 704,0 707,720' \
    -fill '#CC1A00' -draw 'roundRectangle 726,25 868,57 8,8' \
    -font "$FONT_BLACK" \
    -fill white    -pointsize 19 -gravity NorthWest -annotate +737+38 'BREAKING NEWS' \
    -fill '#111111' -pointsize 90 -gravity NorthWest -annotate +733+97  "$LINE1" \
    -fill white     -pointsize 90 -gravity NorthWest -annotate +730+94  "$LINE1" \
    -fill '#111111' -pointsize 90 -gravity NorthWest -annotate +733+198 "$LINE2" \
    -fill '#FF2200' -pointsize 90 -gravity NorthWest -annotate +730+195 "$LINE2" \
    -fill '#FF2200' -draw 'rectangle 730,315 1240,319' \
    -font "$FONT_BOLD" \
    -fill '#AAAAAA' -pointsize 25 -gravity NorthWest -annotate +730+340 "$HASHTAGS" \
    -fill '#444444' -pointsize 19 -gravity NorthWest -annotate +730+700 '#CyberSecurity #InfoSec #Hacking #Shorts' \
    "/tmp/thumb_${TS}.jpg"
  rm -f "$AIBG"
else
  # ── Fallback: gradient design ─────────────────────────────────────────────
  convert -size 1280x720 \
    -define gradient:angle=135 \
    gradient:'#0f0c29-#302b63' \
    -font "$FONT_FALLBACK" \
    -pointsize 80 -fill '#FF0000' -stroke '#000000' -strokewidth 3 \
    -gravity North -annotate +0+80 'ALERT' \
    -fill white -stroke '#000000' -strokewidth 2 \
    -pointsize 58 -gravity Center -annotate 0 "$THUMB_TEXT" \
    -fill '#FFD700' -pointsize 32 \
    -gravity South -annotate +0+60 "$HASHTAGS" \
    "/tmp/thumb_${TS}.jpg"
fi

echo "THUMB_DONE"
ls -lh "/tmp/thumb_${TS}.jpg"
