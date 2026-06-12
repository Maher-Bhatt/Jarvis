"""
KALKI YouTube / video downloader via yt-dlp.
"""

import os
import subprocess
import sys


def _yt_dlp_path():
    """Locate yt-dlp executable or fall back to `python -m yt_dlp`."""
    for cand in ("yt-dlp.exe", "yt-dlp"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            p = os.path.join(d, cand)
            if os.path.exists(p):
                return [p]
    return [sys.executable, "-m", "yt_dlp"]


def download(url, audio_only=False, out_dir=None):
    if not url:
        return {"ok": False, "error": "URL required"}
    if not out_dir:
        out_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(out_dir, exist_ok=True)

    out_template = os.path.join(out_dir, "%(title)s.%(ext)s")
    cmd = _yt_dlp_path() + ["-o", out_template]
    if audio_only:
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        cmd += ["-f", "bv*+ba/b"]   # best video+audio merged, or best
    cmd += [url]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            return {"ok": False, "error": (p.stderr or p.stdout)[-400:]}
        # Try to parse the final filename from stdout
        last_dest = None
        for line in p.stdout.splitlines():
            if "[download] Destination:" in line:
                last_dest = line.split("Destination:", 1)[1].strip()
            elif "[ExtractAudio] Destination:" in line:
                last_dest = line.split("Destination:", 1)[1].strip()
        return {"ok": True, "path": last_dest or out_dir, "dir": out_dir}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "yt-dlp timed out"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
