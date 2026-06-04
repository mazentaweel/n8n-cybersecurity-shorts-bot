#!/usr/bin/env python3
"""
comfyui_bg.py — Generate a thumbnail background image via the ComfyUI API.
Called by the n8n "Generate AI Background" SSH node on the GPU machine.

Usage:
  python3 comfyui_bg.py <scene_prompt> <output.png> [timestamp]

Arguments:
  scene_prompt  8-15 word Stable Diffusion prompt (no people, no text, no faces).
                Examples:
                  "server room red warning screens dark emergency lighting"
                  "broken padlock glowing red dark digital background"
                  "world map glowing threat lines dark cyber warfare"
  output.png    Destination path — typically /mnt/machine_a_tmp/aibg_<TS>.png
                so the file lands on Machine A via NFS without an extra SCP step.
  timestamp     Optional unique run ID used as client_id and filename prefix.
                Defaults to current Unix time.

Prerequisites:
  - ComfyUI running at http://localhost:8188 (comfyui.service)
  - Model: v1-5-pruned-emaonly.safetensors in ComfyUI's models/checkpoints/
  - NFS mount: Machine A exports ~/bgmusic or /tmp to GPU at /mnt/machine_a_tmp/

ComfyUI settings used in production:
  steps=15, cfg=8.5, sampler=dpm_2_ancestral, scheduler=karras
  size=512x512, negative=people/faces/text/bright/cartoon
  Output is upscaled to 1280x720 at thumbnail generation time (ImageMagick).
"""

import sys, json, time, random, urllib.request, urllib.parse

COMFY_URL = 'http://localhost:8188'
CHECKPOINT = 'v1-5-pruned-emaonly.safetensors'
NEGATIVE   = (
    'person, people, face, human, hands, body, cartoon, anime, '
    'blurry, low quality, watermark, text, bright daylight, '
    'cheerful, logo, painting, illustration, drawing'
)
STEPS      = 15
CFG        = 8.5
SAMPLER    = 'dpm_2_ancestral'
SCHEDULER  = 'karras'
WIDTH      = 512
HEIGHT     = 512
POLL_SECS  = 3
MAX_POLLS  = 200   # 10-minute timeout


def build_workflow(scene: str, ts: str) -> dict:
    """Return the ComfyUI prompt graph for a single txt2img pass."""
    positive = scene + ', cinematic, dramatic lighting, photorealistic, 4k, sharp focus, dark background'
    return {
        '4': {
            'class_type': 'CheckpointLoaderSimple',
            'inputs': {'ckpt_name': CHECKPOINT},
        },
        '5': {
            'class_type': 'EmptyLatentImage',
            'inputs': {'width': WIDTH, 'height': HEIGHT, 'batch_size': 1},
        },
        '6': {
            'class_type': 'CLIPTextEncode',
            'inputs': {'clip': ['4', 1], 'text': positive},
        },
        '7': {
            'class_type': 'CLIPTextEncode',
            'inputs': {'clip': ['4', 1], 'text': NEGATIVE},
        },
        '3': {
            'class_type': 'KSampler',
            'inputs': {
                'model':        ['4', 0],
                'positive':     ['6', 0],
                'negative':     ['7', 0],
                'latent_image': ['5', 0],
                'seed':         random.randint(0, 2**32),
                'steps':        STEPS,
                'cfg':          CFG,
                'sampler_name': SAMPLER,
                'scheduler':    SCHEDULER,
                'denoise':      1.0,
            },
        },
        '8': {
            'class_type': 'VAEDecode',
            'inputs': {'samples': ['3', 0], 'vae': ['4', 2]},
        },
        '9': {
            'class_type': 'SaveImage',
            'inputs': {'filename_prefix': f'n8n_{ts}', 'images': ['8', 0]},
        },
    }


def submit(workflow: dict, client_id: str) -> str:
    """Submit workflow to ComfyUI and return the prompt_id."""
    payload = json.dumps({'prompt': workflow, 'client_id': client_id}).encode()
    req = urllib.request.Request(
        COMFY_URL + '/prompt',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())['prompt_id']


def poll(prompt_id: str) -> dict | None:
    """Poll /history until the prompt is complete; return output images or None."""
    for _ in range(MAX_POLLS):
        time.sleep(POLL_SECS)
        try:
            url  = f'{COMFY_URL}/history/{prompt_id}'
            hist = json.loads(urllib.request.urlopen(url, timeout=10).read())
            if prompt_id in hist:
                for node_out in hist[prompt_id]['outputs'].values():
                    if 'images' in node_out:
                        return node_out['images']
        except Exception:
            pass
    return None


def download_image(img_meta: dict, dest: str) -> None:
    """Fetch the generated image from ComfyUI's /view endpoint and save it."""
    params = urllib.parse.urlencode({
        'filename': img_meta['filename'],
        'subfolder': img_meta.get('subfolder', ''),
        'type': 'output',
    })
    data = urllib.request.urlopen(f'{COMFY_URL}/view?{params}').read()
    with open(dest, 'wb') as f:
        f.write(data)


def main():
    if len(sys.argv) < 3:
        print('Usage: comfyui_bg.py <scene_prompt> <output.png> [timestamp]')
        sys.exit(1)

    scene  = sys.argv[1]
    outfile = sys.argv[2]
    ts     = sys.argv[3] if len(sys.argv) >= 4 else str(int(time.time()))

    client_id = f'n8n_{ts}'
    print(f'Scene: {scene}')
    print(f'Output: {outfile}')

    workflow   = build_workflow(scene, ts)
    prompt_id  = submit(workflow, client_id)
    print(f'Queued as prompt_id={prompt_id}, polling...')

    images = poll(prompt_id)
    if not images:
        print('AIBG_TIMEOUT')
        sys.exit(1)

    download_image(images[0], outfile)
    print('AIBG_DONE')
    print(f'Saved to {outfile}')


if __name__ == '__main__':
    main()
