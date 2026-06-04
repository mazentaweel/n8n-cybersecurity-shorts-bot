# n8n Cybersecurity Shorts Bot

Fully automated YouTube Shorts pipeline that reads cybersecurity news from RSS
feeds, generates a narration script with Groq (llama-3.3-70b-versatile), produces
voice + subtitles with OmniVoice TTS, assembles a 9:16 video with FFmpeg, and
uploads directly to YouTube — all orchestrated by n8n.

---

## Pipeline Overview

```
Schedule (00:00 / 08:00 / 16:00)
  │
  ├─► RSS: The Hacker News, Bleeping Computer, Krebs on Security, CISA
  │
  ▼
Parse Articles → Select Unprocessed Article
  │
  ▼
Fetch Article Body → Prepare Article Data → Mark URL Early
  │
  ▼
Build Script Prompt → Call Groq API → Parse Script Response
  │
  ├─► Script Preview (Telegram)       ← kill execution here if script looks wrong
  │
  ▼
Calculate B-Roll Needs → Rewrite Script for TTS
  │
  ├──────────────────────────────────────────────────────────┐
  │                                                          │
  ▼                                                          ▼
Generate Voice & Subtitles (GPU)              Fetch Pexels B-Roll
  │                                                          │
  ▼                                                          ▼
Transfer Voice → Validate Voice           Build Download Commands
  │                                                          │
  └────────────────────┐                 Read Music Catalog  │
                       │                       │             │
                       │                       ▼             │
                       │                 Pick Random Music   │
                       │                       │             │
                       │                       ▼             │
                       │              Write Download Script  │
                       │                       │             │
                       │              ┌────────┘             │
                       ▼              ▼                      │
               Generate AI Background ←──── Sync AI + B-Roll ┘
                       │
                       ▼
           Assemble Video (FFmpeg) → Check Video Ready
                       │
                       ▼
           Generate Thumbnail
                       │
                       ▼
           Read Video as Base64 ─┐
           Read Thumbnail as Base64 ─┘
                       │
                       ▼
           Prepare Upload Data → Upload to YouTube
                       │
                       ▼
           Set YouTube Metadata → Set Video Public
                       │
                       ▼
           Mark URL as Processed → Clear Override Topic
                       │
                       ▼
           Build Telegram Message → Telegram Notification
                       │
                       ▼
           Cleanup Temp Files
```

---

## Prerequisites

### Accounts & API Keys

| Service    | Usage                       | Where to get                             |
|------------|-----------------------------|------------------------------------------|
| Groq       | LLM script generation       | https://console.groq.com                 |
| Pexels     | B-roll video stock          | https://www.pexels.com/api/              |
| YouTube    | Video upload (OAuth2)       | Google Cloud Console → YouTube Data API v3 |
| Telegram   | Notifications & preview     | @BotFather → new bot                     |

### Infrastructure

| Machine      | Role                                              |
|--------------|---------------------------------------------------|
| n8n server   | Workflow orchestration (TrueNAS / any Docker host)|
| Machine A    | FFmpeg, ImageMagick, video assembly, NFS server   |
| GPU Machine  | OmniVoice TTS, ComfyUI image generation           |

### Software on Machine A

```bash
sudo apt install ffmpeg imagemagick python3
# Copy scripts/machine-a/vtt2ass.py to ~/vtt2ass.py
```

### Software on GPU Machine

```bash
# OmniVoice TTS
git clone https://github.com/... ~/new/OmniVoice/OmniVoice
cd ~/new/OmniVoice/OmniVoice && python3 -m venv ../venv
source ../venv/bin/activate && pip install -e .

# Copy scripts/gpu-machine/omnivoice_tts.py to ~/omnivoice_tts.py
# Copy scripts/gpu-machine/kokoro_tts.py   to ~/kokoro_tts.py

# Kokoro fallback (optional)
pip install kokoro-onnx soundfile

# Edge TTS fallback (optional)
pip install edge-tts
```

### NFS Share (optional — for AI background thumbnails)

Machine A should export `/tmp` or a dedicated folder as NFS and mount it on the
GPU machine at `/mnt/machine_a_tmp/` so the ComfyUI-generated background image
can be written directly to Machine A without an extra SCP step.

---

## n8n Setup

### 1. Import the workflow

1. Open n8n → Workflows → Import from file
2. Select `workflow/cybersecurity-shorts-bot.json`
3. The workflow imports as **inactive** — configure credentials first.

### 2. Create credentials

| n8n Credential Type    | Used by nodes                                      |
|------------------------|----------------------------------------------------|
| SSH Private Key        | All `ssh` nodes that connect to Machine A          |
| SSH Password           | `Generate Voice and Subtitles`, `Generate AI Background` (GPU machine) |
| YouTube OAuth2 API     | `Upload to YouTube`, `Set YouTube Metadata`, `Set Video Public` |
| Telegram API           | `Script Preview`, `Telegram Notification`          |

After creating each credential in n8n, open the workflow and update the
credential reference in each affected node to point to your new credential.

### 3. Set your API keys

- **Groq**: open `Call Groq API` node → Headers → replace `YOUR_GROQ_API_KEY`
- **Pexels**: open `Fetch Pexels B-Roll` node → Headers → replace `YOUR_PEXELS_API_KEY`
- **Telegram chat ID**: open `Script Preview` and `Telegram Notification` nodes →
  replace `YOUR_TELEGRAM_CHAT_ID`

### 4. Update paths

All shell commands in SSH nodes use `/home/YOUR_USER/`. Do a global search for
`YOUR_USER` in the workflow JSON and replace with your actual username on each
machine before importing (or edit node-by-node after import).

### 5. Background music

Place MP3 files in `/home/YOUR_USER/bgmusic/` on Machine A with these names:

```
dark1.mp3  dark2.mp3  dark3.mp3
tense1.mp3 tense2.mp3 tense3.mp3
dramatic1.mp3 dramatic2.mp3
cinematic1.mp3
energetic1.mp3 energetic2.mp3
mysterious1.mp3
```

The workflow also supports a generated music catalog at
`/home/YOUR_USER/bgmusic/generated/catalog.json` (nightly MusicGen pipeline —
optional).

### 6. Processed URLs file

The bot tracks which articles it has already covered to avoid repeats:

```bash
touch /home/YOUR_USER/.yt_processed_urls.txt
```

### 7. Activate

Once all credentials and paths are set, toggle the workflow Active in n8n.

---

## Override Topic

To force the next run to cover a specific topic, write a keyword to a file on
Machine A:

```bash
echo "CVE-2024-1234" > /home/YOUR_USER/.yt_override_topic.txt
```

The `Check Override Topic` node reads this file at runtime and clears it after use.

---

## Prompt Architecture

The script prompt is structured as exactly **12 sentences**:

| Section   | Count | Purpose                                          |
|-----------|-------|--------------------------------------------------|
| HOOK      | 1     | Open with consequence/stakes — name actor/victim |
| MECHANISM | 3     | Delivery → Flaw/Technique → Privilege gained     |
| IMPACT    | 3     | Sectors targeted, versions/scale, geography      |
| SCOPE     | 2     | Attribution detail, timeline                     |
| ACTION    | 2     | Patch/hardening action + specific IOC/detection  |
| CTA       | 1     | "Subscribe for daily cybersecurity updates…"     |

**Model**: `llama-3.3-70b-versatile` via Groq
**Parameters**: `temperature=0.7`, `frequency_penalty=1.5`, `max_tokens=900`

---

## Scripts

| Script                                        | Deploy to | Purpose                                      |
|-----------------------------------------------|-----------|----------------------------------------------|
| `scripts/machine-a/vtt2ass.py`                | Machine A | WebVTT → ASS subtitle conversion (PlayResY=1920) |
| `scripts/machine-a/assemble_video.sh`         | Machine A | FFmpeg: download clips, burn subs, mix audio |
| `scripts/machine-a/generate_thumbnail.sh`     | Machine A | ImageMagick: split-panel or gradient thumbnail |
| `scripts/gpu-machine/omnivoice_tts.py`        | GPU       | OmniVoice zero-shot TTS wrapper              |
| `scripts/gpu-machine/kokoro_tts.py`           | GPU       | Kokoro ONNX TTS fallback                     |
| `scripts/gpu-machine/musicgen_nightly.py`     | GPU       | Nightly MusicGen music generation pipeline   |
| `scripts/gpu-machine/comfyui_bg.py`            | GPU       | ComfyUI txt2img for thumbnail backgrounds    |

### Deploying the scripts

Copy each script to the `~` home directory of the relevant machine:

```bash
# Machine A
scp scripts/machine-a/vtt2ass.py          user@machine-a:~/vtt2ass.py
scp scripts/machine-a/assemble_video.sh   user@machine-a:~/assemble_video.sh
scp scripts/machine-a/generate_thumbnail.sh user@machine-a:~/generate_thumbnail.sh
chmod +x ~/assemble_video.sh ~/generate_thumbnail.sh   # on Machine A

# GPU machine
scp scripts/gpu-machine/omnivoice_tts.py     user@gpu:~/omnivoice_tts.py
scp scripts/gpu-machine/kokoro_tts.py        user@gpu:~/kokoro_tts.py
scp scripts/gpu-machine/musicgen_nightly.py  user@gpu:~/musicgen_nightly.py
```

### MusicGen nightly cron (GPU machine)

```bash
# Run at 03:00 every night
0 3 * * * /home/YOUR_USER/new/OmniVoice/venv/bin/python3 /home/YOUR_USER/musicgen_nightly.py   --output-dir /mnt/machine_a_tmp/generated >> /home/YOUR_USER/musicgen.log 2>&1
```

Or as a systemd service with `Restart=always` — see the `[Service]` unit:

```ini
[Unit]
Description=MusicGen nightly music generation

[Service]
Type=oneshot
ExecStart=/home/YOUR_USER/new/OmniVoice/venv/bin/python3           /home/YOUR_USER/musicgen_nightly.py           --output-dir /mnt/machine_a_tmp/generated
User=YOUR_USER

[Install]
WantedBy=multi-user.target
```

Pair with a `.timer` unit to trigger at 03:00.

---

## License

MIT
