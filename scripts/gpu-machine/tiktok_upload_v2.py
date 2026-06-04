#!/usr/bin/env python3
"""
tiktok_upload_v2.py — Upload a video to TikTok via browser automation.
Called by the n8n "Upload to TikTok" SSH node on the GPU machine.

Usage:
  python3 tiktok_upload_v2.py <video_path> <caption> <cookies_json>

Arguments:
  video_path    Path to the MP4 file to upload (9:16, ≤ 60 s for Shorts).
  caption       Post caption including hashtags (plain text, newlines allowed).
  cookies_json  Path to exported browser cookies in JSON format (see below).

Exit codes:
  0  — uploaded (prints TIKTOK_SUCCESS)
  1  — upload failed or timed out

Tool: tiktok-uploader (https://github.com/wkaisertexas/tiktok-uploader)
  - Uses Playwright to drive a real Chromium browser session.
  - Logs in via exported session cookies — no password required at runtime.
  - Headless by default; set TIKTOK_HEADFUL=1 to watch the browser.

Prerequisites (GPU machine):
  pip install tiktok-uploader playwright
  playwright install chromium

--- Exporting your TikTok session cookies ---

Option A — browser extension (easiest):
  1. Log in to TikTok in Chrome or Firefox.
  2. Install the "Cookie-Editor" extension.
  3. On tiktok.com, open Cookie-Editor → Export → Export as JSON.
  4. Save the file as tiktok_cookies.json on the GPU machine.
     Keep this file private — it grants full account access.

Option B — tiktok-uploader's built-in helper:
  python3 -c "
  from tiktok_uploader.auth import AuthBackend
  AuthBackend().save_cookies('tiktok_cookies.json')
  "
  A browser window will open; log in manually, then close it.

Cookie file format (array of objects):
  [
    {"name": "sessionid", "value": "...", "domain": ".tiktok.com", ...},
    ...
  ]

--- Security note ---
  tiktok_cookies.json grants full access to your TikTok account.
  Never commit it to version control. Add it to .gitignore.
  Rotate by logging out of TikTok on the device that exported the cookies.
"""

import sys, os, time

def upload(video_path: str, caption: str, cookies_path: str) -> bool:
    """
    Upload video to TikTok. Returns True on success.
    Uses tiktok-uploader which drives Playwright under the hood.
    """
    try:
        from tiktok_uploader.upload import upload_video
    except ImportError:
        print('ERROR: tiktok-uploader not installed.')
        print('  pip install tiktok-uploader playwright')
        print('  playwright install chromium')
        return False

    if not os.path.exists(video_path):
        print(f'ERROR: video not found: {video_path}')
        return False

    if not os.path.exists(cookies_path):
        print(f'ERROR: cookies file not found: {cookies_path}')
        print('  See script docstring for how to export TikTok cookies.')
        return False

    headless = os.environ.get('TIKTOK_HEADFUL', '0') != '1'

    print(f'Uploading: {video_path}')
    print(f'Caption:   {caption[:80]}{"..." if len(caption) > 80 else ""}')
    print(f'Headless:  {headless}')

    try:
        upload_video(
            filename=video_path,
            description=caption,
            cookies=cookies_path,
            headless=headless,
            # schedule=None means post immediately
        )
        return True
    except Exception as e:
        print(f'Upload exception: {e}')
        return False


def main():
    if len(sys.argv) != 4:
        print('Usage: tiktok_upload_v2.py <video_path> <caption> <cookies_json>')
        sys.exit(1)

    video_path   = sys.argv[1]
    caption      = sys.argv[2]
    cookies_path = sys.argv[3]

    success = upload(video_path, caption, cookies_path)

    if success:
        print('TIKTOK_SUCCESS')
        sys.exit(0)
    else:
        print('TIKTOK_FAILED')
        sys.exit(1)


if __name__ == '__main__':
    main()
