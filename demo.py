"""
KALKI Demo Runner — LinkedIn / OBS edition
============================================
Opens Chrome to the KALKI HUD, pre-launches Spotify, waits for the
boot animation to finish, then runs through a 90-120 second showcase
that covers EVERY major feature in order.

Each command waits for KALKI to finish speaking before the next fires.

Usage:
    py -3.11 demo.py            # full ~110 sec demo (DEFAULT)
    py -3.11 demo.py --short    # quick ~60 sec highlight reel
    py -3.11 demo.py --cyber    # cybersec-focused
"""

import sys
import os
import json
import time
import glob
import subprocess
import urllib.request

BASE = "http://localhost:8888"

# ── ANSI colours ─────────────────────────────────────────
os.system("")
C = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "white": "\033[97m", "cyan": "\033[96m", "magenta": "\033[95m",
    "green": "\033[92m", "orange": "\033[93m", "red": "\033[91m",
    "gray": "\033[90m",
}


def http(method, path, body=None, timeout=60):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def status():
    try: return http("GET", "/api/status", timeout=4)
    except: return {}


def chat(text):
    return http("POST", "/api/chat", {
        "messages": [{"role": "user", "content": text}],
        "source": "voice",
    }, timeout=90)


def wait_for_speak_end(max_wait=60):
    """Block while KALKI is speaking."""
    deadline = time.time() + 4
    while time.time() < deadline:
        if status().get("speaking"): break
        time.sleep(0.12)
    spinner = ["⢿","⣻","⣽","⣾","⣷","⣯","⣟","⡿"]
    i = 0
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if not status().get("speaking"):
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            return True
        sys.stdout.write(f"\r{C['gray']}  {spinner[i % len(spinner)]} KALKI speaking…{C['reset']}")
        sys.stdout.flush()
        i += 1
        time.sleep(0.13)
    sys.stdout.write("\r" + " " * 50 + "\r"); sys.stdout.flush()
    return False


# ── Launchers ─────────────────────────────────────────
def launch_chrome():
    """Open Chrome to KALKI HUD."""
    url = "http://localhost:8888"
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            subprocess.Popen([p, url])
            return True
    # fallback to webbrowser
    import webbrowser
    return webbrowser.open(url)


def launch_spotify():
    """Pre-launch Spotify so it's ready when 'play lo-fi' fires."""
    spotify_paths = [
        os.path.expanduser(r"~\AppData\Roaming\Spotify\Spotify.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WindowsApps\Spotify.exe"),
        r"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic_*\Spotify.exe",
    ]
    for pat in spotify_paths:
        for p in (glob.glob(pat) if "*" in pat else [pat]):
            if p and os.path.exists(p):
                try:
                    subprocess.Popen([p],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL,
                                     creationflags=0x00000008)
                    return True
                except Exception:
                    continue
    return False


# ── Pretty printing ─────────────────────────────────────
def banner():
    print(C["bold"] + C["magenta"])
    print("═" * 72)
    print("           T . O . M . M . Y .   —   DEMO RUNNER")
    print("═" * 72)
    print(C["reset"])


def section(idx, total, title):
    print()
    print(f"{C['bold']}{C['magenta']}╭{'─'*70}╮{C['reset']}")
    print(f"{C['bold']}{C['magenta']}│  STEP {idx:>2}/{total}  {C['white']}{title:<54}{C['magenta']}│{C['reset']}")
    print(f"{C['bold']}{C['magenta']}╰{'─'*70}╯{C['reset']}")


def narrate(text):
    print(f"{C['gray']}  ▸ {text}{C['reset']}")


def run(text, show_reply=True, max_wait=60):
    print(f"  {C['cyan']}{C['bold']}YOU   →{C['reset']}  {text}")
    try:
        r = chat(text)
    except Exception as e:
        print(f"  {C['red']}✗ {e}{C['reset']}")
        return
    if show_reply:
        src = r.get("source", "?")
        reply = " ".join((r.get("reply", "") or "").split())[:280]
        tag = "ai" if src == "ai" else "loc"
        tag_col = C["orange"] if src == "ai" else C["green"]
        print(f"  {tag_col}{C['bold']}KALKI← [{tag}]{C['reset']}  {reply}")
    wait_for_speak_end(max_wait=max_wait)


# ══════════════════════════════════════════════════════════
# DEMO SEQUENCES — packed into ~90-110 seconds
# ══════════════════════════════════════════════════════════
SEQUENCES = {
    "full": [
        # 1. wake greeting (humanized, varied)
        ("INTRO",
         "KALKI introduces itself — humanized, no robotic templates",
         ["hi"]),

        # 2. real Google Calendar
        ("GOOGLE CALENDAR",
         "Real OAuth — events spoken from your actual calendar",
         ["what is on my calendar"]),

        # 3. real Gmail Primary
        ("GMAIL (PRIMARY INBOX ONLY)",
         "Important unread filtered from promotions and social",
         ["check gmail"]),

        # 4. Spotify
        ("SPOTIFY CONTROL",
         "Voice-driven music — auto-launches if not running",
         ["play lo-fi"]),

        # 5. Cyber: hash
        ("CYBERSEC — HASH TOOLS",
         "Local MD5 computation, zero API cost",
         ["md5 of admin123"]),

        # 6. Cyber: reverse shell
        ("CYBERSEC — REVERSE SHELL PAYLOAD",
         "10-language arsenal — payload returned as a copyable code block",
         ["reverse shell python 10.10.14.5 4444"]),

        # 7. Cyber: CVE
        ("CYBERSEC — LIVE CVE FEED",
         "NVD API — recent critical vulnerabilities",
         ["recent critical cves"]),

        # 8. Vault save
        ("DPAPI VAULT — SAVE",
         "Encrypted with your Windows user account",
         ["save my linkedin password as DemoPwd2026"]),

        # 9. Vault retrieve
        ("DPAPI VAULT — RETRIEVE",
         "Decrypted on demand",
         ["what is my linkedin password"]),

        # 10. Workflow mode
        ("WORKFLOW MODE",
         "Single phrase triggers a multi-step action chain",
         ["ctf mode"]),

        # 11. Pause music for clean close
        ("MUSIC PAUSE",
         "Spotify control again, this time pause",
         ["pause"]),

        # 12. Notes
        ("NOTES",
         "Persistent journal with tag parsing",
         ["take a note KALKI demo recorded for LinkedIn"]),

        # 13. Outro
        ("OUTRO",
         "Humanized closing",
         ["thanks KALKI"]),
    ],

    "short": [
        ("INTRO", "Greeting", ["hi"]),
        ("CALENDAR", "Real Google Calendar", ["what is on my calendar"]),
        ("SPOTIFY", "Voice music control", ["play lo-fi"]),
        ("CYBER", "Hash + reverse shell", [
            "md5 of admin123",
            "reverse shell python 10.10.14.5 4444"]),
        ("VAULT", "Encrypted password store", [
            "save my linkedin password as DemoPwd2026",
            "what is my linkedin password"]),
        ("WORKFLOW", "CTF mode chain", ["ctf mode"]),
        ("PAUSE", "Stop music", ["pause"]),
        ("OUTRO", "Close", ["take a note KALKI demo recorded"]),
    ],

    "cyber": [
        ("INTRO", "Greeting", ["hi"]),
        ("HASH ID", "MD5/identify/NTLM", [
            "md5 of admin123",
            "identify hash 5f4dcc3b5aa765d61d8327deb882cf99",
            "ntlm of password123"]),
        ("ENCODING", "Codecs", [
            "base64 encode the eagle has landed",
            "rot13 plaintext"]),
        ("CVE INTEL", "Live NVD", [
            "lookup CVE-2024-3094",
            "recent critical cves"]),
        ("RECON", "Network", [
            "what is my ip",
            "dns google.com"]),
        ("PAYLOADS", "Reverse shells in 3 languages", [
            "reverse shell python 10.10.14.5 4444",
            "reverse shell powershell 10.10.14.5 4444",
            "reverse shell bash 10.10.14.5 4444"]),
        ("CLOSE", "Vault save", ["save my htb password as RootIsB3st"]),
    ],
}


def main():
    mode = "full"
    if "--short" in sys.argv: mode = "short"
    if "--cyber" in sys.argv: mode = "cyber"

    seq = SEQUENCES[mode]
    total_cmds = sum(len(items) for _, _, items in seq)

    banner()
    print(f"  Mode: {C['bold']}{mode.upper()}{C['reset']}    "
          f"Commands: {C['bold']}{total_cmds}{C['reset']}")
    print()

    # ── Server alive check ───────────────────────────
    s = status()
    if not s.get("online"):
        print(f"  {C['red']}✗ KALKI server unreachable at {BASE}{C['reset']}")
        print(f"  {C['red']}  Run START.bat first.{C['reset']}")
        sys.exit(1)

    # ── 3-second countdown ──────────────────────────
    print(f"  {C['orange']}↪ Recording? Starting Chrome + Spotify in 3 seconds…{C['reset']}")
    for i in range(3, 0, -1):
        print(f"  {C['gray']}  {i}…{C['reset']}", end="\r", flush=True)
        time.sleep(1)
    print(" " * 30)

    # ── Open Chrome + Spotify ───────────────────────
    print(f"  {C['cyan']}▸ Opening Chrome to KALKI HUD…{C['reset']}")
    launch_chrome()
    print(f"  {C['cyan']}▸ Pre-launching Spotify (so 'play lo-fi' is instant)…{C['reset']}")
    launch_spotify()

    # ── Wait for Chrome boot animation to complete ──
    print(f"  {C['gray']}▸ Waiting 7s for the HUD boot sequence to finish…{C['reset']}")
    for i in range(7, 0, -1):
        print(f"  {C['gray']}  {i}…{C['reset']}", end="\r", flush=True)
        time.sleep(1)
    print(" " * 30)

    # ── Run the sequence ────────────────────────────
    idx = 0
    try:
        for sec_idx, (title, narration, items) in enumerate(seq, 1):
            section(sec_idx, len(seq), title)
            narrate(narration)
            time.sleep(0.6)
            for cmd in items:
                idx += 1
                run(cmd)
                time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n  {C['orange']}Aborted.{C['reset']}")
        return

    print()
    print(f"  {C['bold']}{C['green']}✓ DEMO COMPLETE — {idx} commands executed.{C['reset']}")
    print(f"  {C['gray']}Stop your OBS recording now.{C['reset']}")
    print()


if __name__ == "__main__":
    main()
