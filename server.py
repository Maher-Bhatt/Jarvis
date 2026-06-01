"""
JARVIS v5 — Server
Web server + AI + TTS + system commands
Uses Python stdlib http.server only (no Flask, no FastAPI)
"""

import os
import sys
import json
import time
import glob
import socket
import threading
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
import tempfile
import asyncio
import ctypes
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Ensure local imports resolve when launched from any cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# Force UTF-8 stdout/stderr (pythonw.exe uses cp1252 by default — breaks on emoji/arrows)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import config
import vault
import vision
import coder
import cybertools
import tasks as taskmod
import mail as mailmod
import gcal
import spotify_mod
import whatsapp_mod
import notes as notesmod
import ytdl
import workflows

# ─────────────────────────────────────────────────────────────
# Optional dependencies — degrade gracefully if missing
# ─────────────────────────────────────────────────────────────
try:
    import edge_tts
except Exception:
    edge_tts = None

try:
    import pygame
    pygame.mixer.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

try:
    import psutil
except Exception:
    psutil = None

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_OK = True
except Exception:
    PYCAW_OK = False


# ─────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

MEMORY_PATH  = os.path.join(BASE_DIR, config.MEMORY_FILE)
HISTORY_PATH = os.path.join(BASE_DIR, config.HISTORY_FILE)
VAULT_PATH   = os.path.join(BASE_DIR, "data", "vault.json")
SCRIPTS_DIR  = os.path.join(BASE_DIR, "data", "scripts")
TASKS_PATH   = os.path.join(BASE_DIR, "data", "tasks.json")
REMINDERS_PATH = os.path.join(BASE_DIR, "data", "reminders.json")
LOG_PATH     = os.path.join(BASE_DIR, "data", "jarvis.log")
os.makedirs(SCRIPTS_DIR, exist_ok=True)
vault.VAULT_PATH = VAULT_PATH
coder.SCRIPTS_DIR = SCRIPTS_DIR
taskmod.TASKS_PATH = TASKS_PATH
taskmod.REMINDERS_PATH = REMINDERS_PATH
gcal.CRED_PATH  = os.path.join(BASE_DIR, "data", "google_credentials.json")
gcal.TOKEN_PATH = os.path.join(BASE_DIR, "data", "google_token.pickle")
spotify_mod.CACHE_PATH = os.path.join(BASE_DIR, "data", "spotify_token.json")
whatsapp_mod.CONTACTS_PATH = os.path.join(BASE_DIR, "data", "contacts.json")
notesmod.NOTES_PATH = os.path.join(BASE_DIR, "data", "notes.json")


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass

STATE = {
    "speaking": False,
    "model": config.GROQ_MODEL,
    "started_at": time.time(),
    # ── UI presence + voice-driven exchange tracking ──
    "ui_last_ping": 0.0,         # last time /api/status was hit by a UI
    "wake_pending": False,        # set when /api/wake fires → UI engages listening
    "conversation_seq": 0,        # bumped on every voice-driven exchange
    "recent_exchange": None,      # {seq, user, reply, ts}
    "listener_paused": False,     # toggled to release the mic for other apps
}

UI_ALIVE_GRACE = 8.0  # seconds — if no /api/status in this long, UI is "dead"


def is_ui_alive():
    return (time.time() - STATE.get("ui_last_ping", 0.0)) < UI_ALIVE_GRACE

# ─────────────────────────────────────────────────────────────
# APP MAP
# ─────────────────────────────────────────────────────────────
APP_MAP = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "vs code": "code.exe",
    "code": "code.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "powershell": "powershell.exe",
    "cmd": "cmd.exe",
    "task manager": "taskmgr.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "teams": "teams.exe",
    "telegram": "telegram.exe",
    "vlc": "vlc.exe",
    "obs": "obs64.exe",
}

WEB_APPS = {
    "youtube":   "https://www.youtube.com",
    "google":    "https://www.google.com",
    "gmail":     "https://mail.google.com",
    "mail":      "https://mail.google.com",
    "drive":     "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs":      "https://docs.google.com",
    "google docs": "https://docs.google.com",
    "maps":      "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "calendar":  "https://calendar.google.com",
    "instagram": "https://www.instagram.com",
    "insta":     "https://www.instagram.com",
    "facebook":  "https://www.facebook.com",
    "fb":        "https://www.facebook.com",
    "twitter":   "https://twitter.com",
    "x":         "https://x.com",
    "reddit":    "https://www.reddit.com",
    "linkedin":  "https://www.linkedin.com",
    "github":    "https://github.com",
    "stackoverflow":"https://stackoverflow.com",
    "stack overflow":"https://stackoverflow.com",
    "whatsapp":  "https://web.whatsapp.com",
    "whatsapp web":"https://web.whatsapp.com",
    "telegram web":"https://web.telegram.org",
    "chatgpt":   "https://chat.openai.com",
    "openai":    "https://chat.openai.com",
    "claude":    "https://claude.ai",
    "gemini":    "https://gemini.google.com",
    "netflix":   "https://www.netflix.com",
    "amazon":    "https://www.amazon.in",
    "flipkart":  "https://www.flipkart.com",
    "spotify web":"https://open.spotify.com",
    "leetcode":  "https://leetcode.com",
    "hackerone": "https://hackerone.com",
    "tryhackme": "https://tryhackme.com",
    "hackthebox":"https://www.hackthebox.com",
    "htb":       "https://www.hackthebox.com",
    "shodan":    "https://www.shodan.io",
    "virustotal":"https://www.virustotal.com",
    "exploit db":"https://www.exploit-db.com",
    "exploitdb": "https://www.exploit-db.com",
    "cve":       "https://cve.mitre.org",
    "mdn":       "https://developer.mozilla.org",
    "groq":      "https://console.groq.com",
}

MEMORY_TRIGGERS = ["remember", "don't forget", "keep in mind", "note that", "save this"]

SEARCH_TRIGGERS = [
    "latest", "current", "today's", "today ", " news", "recent", "trending",
    "search the web", "look up", "search for", "find online", "google",
    "who won", "what happened", "this week", "this year", "right now",
    "live ", " stock", " price of", " score", " happening",
    "wikipedia", "who is", "what is the", "tell me about", "explain ",
]

NEWS_TRIGGERS = ["news", "headlines", "top stories", "what's happening"]


# ─────────────────────────────────────────────────────────────
# Memory / History
# ─────────────────────────────────────────────────────────────
def load_memory():
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_memory(mems):
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(mems, f, indent=2, ensure_ascii=False)

def add_memory(fact):
    mems = load_memory()
    mems.append({"fact": fact, "date": datetime.now().strftime("%Y-%m-%d")})
    save_memory(mems)
    return len(mems)

def get_memory_prompt():
    mems = load_memory()
    if not mems:
        return ""
    lines = "\n".join(f"- {m['fact']}" for m in mems[-30:])
    return f"\n\nMEMORY BANK - facts about Sir:\n{lines}"

def load_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history(hist):
    hist = hist[-config.MAX_HISTORY:]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# TTS — edge-tts (non-blocking)
# ─────────────────────────────────────────────────────────────
async def _speak_async(text, voice, rate, volume):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(tmp)
    return tmp

import re as _re_speech

# Strip markdown so edge-tts doesn't pronounce "asterisk asterisk"
_SPEECH_FILTERS = [
    (_re_speech.compile(r"```[\s\S]*?```"), " "),                    # code blocks: skip entirely
    (_re_speech.compile(r"`([^`]+)`"), r"\1"),                       # `inline code`
    (_re_speech.compile(r"\*\*([^*]+)\*\*"), r"\1"),                 # **bold**
    (_re_speech.compile(r"(?<!\w)\*([^*]+)\*(?!\w)"), r"\1"),        # *italic*
    (_re_speech.compile(r"__([^_]+)__"), r"\1"),                     # __bold__
    (_re_speech.compile(r"(?<!\w)_([^_]+)_(?!\w)"), r"\1"),          # _italic_
    (_re_speech.compile(r"^\s*#{1,6}\s+", _re_speech.M), ""),        # # headers
    (_re_speech.compile(r"^\s*[-•*]\s+", _re_speech.M), ""),         # bullet markers
    (_re_speech.compile(r"^\s*\d+\.\s+", _re_speech.M), ""),         # 1. 2. list markers
    (_re_speech.compile(r"^\s*>\s*", _re_speech.M), ""),             # > quotes
    (_re_speech.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),           # [text](url)
    (_re_speech.compile(r"~~([^~]+)~~"), r"\1"),                     # ~~strike~~
]


def clean_for_speech(text):
    """Strip markdown / code / list noise so TTS speaks naturally."""
    if not text:
        return ""
    out = text
    for pat, repl in _SPEECH_FILTERS:
        out = pat.sub(repl, out)
    # Collapse whitespace
    out = _re_speech.sub(r"\s+", " ", out).strip()
    return out


def stop_speaking():
    """Hard-cut whatever JARVIS is currently saying."""
    try:
        if PYGAME_OK:
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
        STATE["speaking"] = False
        return True
    except Exception as e:
        log(f"stop_speaking error: {e}")
        return False


def speak(text):
    """Non-blocking TTS using edge-tts neural voice. Markdown stripped first."""
    text = clean_for_speech(text)
    if not text:
        return
    if edge_tts is None or not PYGAME_OK:
        print(f"[TTS missing] {text}")
        return

    def _run():
        try:
            STATE["speaking"] = True
            tmp = asyncio.run(_speak_async(
                text,
                config.TTS_VOICE,
                config.TTS_RATE,
                config.TTS_VOLUME,
            ))
            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            try:
                os.unlink(tmp)
            except Exception:
                pass
        except Exception as e:
            print(f"TTS error: {e}")
        finally:
            STATE["speaking"] = False

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────
# Greeting (NO API CALL)
# ─────────────────────────────────────────────────────────────
import random as _rnd


def build_greeting():
    hour = datetime.now().hour
    day  = datetime.now().strftime("%A")
    title = config.OWNER_TITLE

    # Opener — varies by time of day, randomized each boot
    if 5 <= hour < 12:
        opener = _rnd.choice([
            f"Morning, {title}.",
            f"Good morning, {title}.",
            f"Up and at it, {title}.",
            f"Rise and shine, {title}.",
        ])
    elif 12 <= hour < 17:
        opener = _rnd.choice([
            f"Afternoon, {title}.",
            f"Good afternoon, {title}.",
            f"Welcome back, {title}.",
            f"There you are, {title}.",
        ])
    elif 17 <= hour < 21:
        opener = _rnd.choice([
            f"Evening, {title}.",
            f"Good evening, {title}.",
            f"Hello again, {title}.",
        ])
    else:
        opener = _rnd.choice([
            f"Burning the midnight oil, {title}?",
            f"Still up, {title}.",
            f"Late night, {title}.",
            f"At this hour, {title}?",
        ])

    # Day mention — sometimes skipped, sometimes called out for Mon/Fri
    if day == "Monday":
        day_phrase = _rnd.choice(["Monday already.", "Fresh week.", "It's Monday.", ""])
    elif day == "Friday":
        day_phrase = _rnd.choice(["Friday at last.", "It's Friday.", "End of week.", ""])
    elif day in ("Saturday", "Sunday"):
        day_phrase = _rnd.choice([f"Happy {day}.", "Weekend.", ""])
    else:
        day_phrase = _rnd.choice([f"It's {day}.", "", ""])

    # Weather phrasing — natural
    weather_part = ""
    try:
        w = urllib.request.urlopen(
            f"https://wttr.in/{config.OWNER_CITY}?format=%C+%t",
            timeout=4,
        ).read().decode().strip()
        weather_part = _rnd.choice([
            f"It's {w} out there.",
            f"Looking like {w} in {config.OWNER_CITY}.",
            f"{w} outside.",
            f"Weather is {w} today.",
        ])
    except Exception:
        pass

    # Calendar
    calendar_part = ""
    try:
        calendar_part = gcal.startup_summary().strip()
    except Exception:
        pass

    # Tasks — varied
    pending = len(taskmod.list_tasks())
    if pending == 0:
        task_part = _rnd.choice(["", "Task list is clear.", ""])
    elif pending == 1:
        task_part = _rnd.choice([
            "One task on your list.",
            "Got one task pending.",
            "You've got a task waiting.",
        ])
    else:
        task_part = _rnd.choice([
            f"{pending} tasks waiting.",
            f"{pending} things on the list.",
            f"You've got {pending} open tasks.",
        ])

    parts = [opener, day_phrase, weather_part, calendar_part, task_part]
    return " ".join(p for p in parts if p).strip()


# ─────────────────────────────────────────────────────────────
# Volume / Audio (pycaw)
# ─────────────────────────────────────────────────────────────
def _get_volume_iface():
    if not PYCAW_OK:
        return None
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))

def set_volume(level_0_100):
    iface = _get_volume_iface()
    if not iface:
        return False
    lvl = max(0.0, min(1.0, level_0_100 / 100.0))
    iface.SetMasterVolumeLevelScalar(lvl, None)
    return True

def set_mute(mute):
    iface = _get_volume_iface()
    if not iface:
        return False
    iface.SetMute(1 if mute else 0, None)
    return True


# ─────────────────────────────────────────────────────────────
# Local command handler — NEVER calls AI
# ─────────────────────────────────────────────────────────────
import re as _re_local

def _strip_for_value(raw, anchors):
    """Pull the value after the first matching anchor word."""
    low = raw.lower()
    for a in anchors:
        i = low.find(a)
        if i >= 0:
            return raw[i + len(a):].strip(" :=,.\t\"'")
    return ""


def handle_local(text):
    """
    Returns (handled: bool, reply_text: str)
    If handled is True, server should NOT call the AI.
    """
    if not text:
        return False, ""
    t = text.lower().strip()
    raw = text.strip()

    # ════════════════════════════════════════════════════
    # STOP — interrupt JARVIS speaking
    # ════════════════════════════════════════════════════
    if t in ("stop", "stop talking", "shut up", "quiet", "be quiet",
             "silence", "shush", "cancel", "stop it", "enough"):
        stop_speaking()
        return True, ""

    # ════════════════════════════════════════════════════
    # SPOTIFY
    # ════════════════════════════════════════════════════
    if t in ("pause", "pause music", "pause song", "pause spotify",
             "pause the music"):
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir. Run setup_spotify.py."
        return True, spotify_mod.pause()

    if t in ("resume", "resume music", "resume song", "play music",
             "continue music", "play spotify"):
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        return True, spotify_mod.play()

    if t in ("next", "next song", "next track", "skip", "skip song"):
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        return True, spotify_mod.next_track()

    if t in ("previous", "previous song", "previous track", "last song",
             "go back song"):
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        return True, spotify_mod.prev_track()

    if t in ("what's playing", "what is playing", "current song",
             "now playing", "what song is this"):
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        return True, spotify_mod.now_playing()

    if t in ("shuffle", "shuffle on", "turn shuffle on"):
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        return True, spotify_mod.shuffle_on()

    # "spotify volume 60" / "music volume 50"
    m = _re_local.match(
        r"^(?:spotify|music)\s+volume\s+(\d+)$", t, _re_local.IGNORECASE)
    if m:
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        return True, spotify_mod.set_volume(int(m.group(1)))

    # "play X on spotify" / "play X" / "play lo-fi"
    m = _re_local.match(
        r"^play\s+(.+?)(?:\s+on\s+spotify)?$", t, _re_local.IGNORECASE)
    if m and not t.startswith("play youtube") and "youtube" not in t:
        if not spotify_mod.is_configured():
            return True, "Spotify not linked, Sir."
        query = m.group(1).strip()
        if query in ("music", "song", "songs"):
            return True, spotify_mod.play()
        if "lofi" in query or "lo-fi" in query or "lo fi" in query:
            return True, spotify_mod.play_lofi()
        return True, spotify_mod.play(query)

    # ════════════════════════════════════════════════════
    # WHATSAPP — "send whatsapp to NAME saying TEXT"
    # ════════════════════════════════════════════════════
    m = _re_local.match(
        r"^(?:send\s+(?:a\s+)?(?:whatsapp|message|whats\s*app)\s+to\s+|"
        r"whatsapp\s+|message\s+)([^,]+?)\s+(?:saying|that|to say)\s+(.+)$",
        t, _re_local.IGNORECASE,
    )
    if m:
        name = m.group(1).strip()
        # Get the original-cased message body
        body_lower = m.group(2).strip()
        idx = t.find(body_lower)
        body_txt = raw[idx:idx + len(body_lower)] if idx >= 0 else body_lower
        r = whatsapp_mod.send_message(name, body_txt)
        if r.get("ok"):
            return True, f"WhatsApp dispatched to {name}, Sir."
        return True, f"WhatsApp failed: {r.get('error')}"

    # "add contact NAME phone +91..."
    m = _re_local.match(
        r"^add\s+contact\s+(\S+)\s+(?:phone|number)?\s*(\+?\d[\d\s\-]+)$",
        t, _re_local.IGNORECASE,
    )
    if m:
        name, phone = m.group(1), m.group(2).replace(" ", "").replace("-", "")
        whatsapp_mod.add_contact(name, phone)
        return True, f"Contact {name} saved."

    # "list my contacts"
    if t in ("list contacts", "list my contacts", "show contacts",
             "show my contacts", "my contacts"):
        c = whatsapp_mod.list_contacts()
        if not c:
            return True, "No contacts yet, Sir."
        return True, f"{len(c)} contacts: " + ", ".join(c.keys())

    # ════════════════════════════════════════════════════
    # NOTES
    # ════════════════════════════════════════════════════
    m = _re_local.match(
        r"^(?:take\s+(?:a\s+)?note|note\s+(?:that|this)|add\s+note|"
        r"jot\s+(?:this\s+)?down)\s*[:\-]?\s+(.+)$",
        t, _re_local.IGNORECASE,
    )
    if m:
        note_lower = m.group(1).strip()
        idx = t.find(note_lower)
        body_txt = raw[idx:idx + len(note_lower)] if idx >= 0 else note_lower
        nid = notesmod.add_note(body_txt)
        return True, _rnd.choice([
            "Noted.", "Got it.", "Stored, Sir.", "Down in the book.",
            "Filed away.", f"Logged that, Sir.",
        ])

    if t in ("show my notes", "list my notes", "recent notes",
             "what did i note", "show notes"):
        n = notesmod.list_recent(5)
        return True, notesmod.summarize_for_speech(n)

    if t in ("what did i note yesterday", "yesterday's notes",
             "notes from yesterday"):
        return True, notesmod.summarize_for_speech(notesmod.notes_yesterday())

    if t in ("notes this week", "this week's notes",
             "summarize this week's notes", "summarize my week"):
        return True, notesmod.summarize_for_speech(notesmod.notes_this_week())

    m = _re_local.match(r"^search\s+notes?\s+(?:for\s+)?(.+)$",
                          t, _re_local.IGNORECASE)
    if m:
        results = notesmod.search(m.group(1).strip())
        return True, notesmod.summarize_for_speech(results)

    # ════════════════════════════════════════════════════
    # YOUTUBE DOWNLOAD
    # ════════════════════════════════════════════════════
    m = _re_local.search(
        r"download\s+(?:this\s+)?(?:youtube\s+)?(?:video|audio|song|track)"
        r"(?:\s+from)?\s+(\S+)",
        raw, _re_local.IGNORECASE,
    )
    if m:
        url = m.group(1).strip()
        audio_only = "audio" in t or "song" in t or "music" in t or "mp3" in t
        speak(f"Downloading. This may take a moment, Sir.")
        result = ytdl.download(url, audio_only=audio_only)
        if result.get("ok"):
            return True, f"Download complete, Sir. Saved to your Downloads folder."
        return True, f"Download failed: {result.get('error','unknown')}"

    # ════════════════════════════════════════════════════
    # WORKFLOW MODES (fuzzy match — handles STT mishearings)
    # ════════════════════════════════════════════════════
    mode_matched = workflows.find_mode(t)
    if mode_matched:
        workflows.run_mode(
            mode_matched,
            speak_fn=speak,
            set_volume_fn=set_volume,
            open_url_fn=webbrowser.open,
        )
        return True, ""   # workflow already spoke; no extra reply

    # ════════════════════════════════════════════════════
    # CYBER: CVE, subdomain, reverse shell, github dorks
    # ════════════════════════════════════════════════════
    m = _re_local.search(
        r"(?:lookup|search|find|tell me about)\s+(cve[-\s]?\d{4}[-\s]?\d{4,})",
        t, _re_local.IGNORECASE,
    )
    if m:
        cve_id = m.group(1).upper().replace(" ", "-")
        r = cybertools.cve_lookup(cve_id)
        if "error" in r:
            return True, f"CVE lookup failed: {r['error']}"
        return True, (f"{r['id']}, severity {r.get('severity','?')}, "
                      f"score {r.get('score','?')}. {r['summary'][:300]}")

    if t in ("recent critical cves", "latest critical cves",
             "any new critical cves", "critical cves"):
        r = cybertools.recent_critical_cves(limit=4)
        if isinstance(r, dict) and "error" in r:
            return True, f"CVE feed error: {r['error']}"
        lines = [f"{c['id']}: {c['summary'][:160]}" for c in r]
        return True, ". Next: ".join(lines) if lines else "No new critical CVEs."

    m = _re_local.search(
        r"(?:find|enumerate|enum|list)\s+subdomains?\s+(?:of\s+|for\s+)?(\S+)",
        t, _re_local.IGNORECASE,
    )
    if m:
        domain = m.group(1).strip().lstrip("https://").lstrip("http://").rstrip("/")
        r = cybertools.subdomain_enum(domain, limit=30)
        if "error" in r:
            return True, f"Subdomain enum failed: {r['error']}"
        return True, (f"Found {r['count']} subdomains for {domain}, Sir. "
                      f"Top: {', '.join(r['subdomains'][:6])}")

    # "reverse shell python 10.10.14.5 4444"
    m = _re_local.match(
        r"(?:generate\s+|make\s+|give\s+me\s+)?reverse\s+shell\s+"
        r"(\w+)\s+(\S+)\s+(\d+)$",
        t, _re_local.IGNORECASE,
    )
    if m:
        shell_type, lhost, lport = m.group(1), m.group(2), m.group(3)
        r = cybertools.reverse_shell(shell_type, lhost, lport)
        if "error" in r:
            return True, r["error"]
        return True, (f"{shell_type} reverse shell to {lhost}:{lport}, "
                      f"{config.OWNER_TITLE}.\n```{shell_type}\n"
                      f"{r['payload']}\n```")

    # "github dorks for X"
    m = _re_local.search(
        r"github\s+dorks?\s+(?:for\s+)?(.+)$", t, _re_local.IGNORECASE)
    if m:
        target = m.group(1).strip()
        dorks = cybertools.github_dorks(target)
        return True, f"{len(dorks)} dorks generated for {target}. First: {dorks[0]['name']}."

    # ════════════════════════════════════════════════════
    # TASKS
    # ════════════════════════════════════════════════════
    m = _re_local.match(
        r"^(?:add\s+(?:a\s+)?task|new\s+task|task)[:\-]?\s+(.+)$",
        t, _re_local.IGNORECASE,
    )
    if m:
        body_txt = raw.split(None, 2)[-1] if raw.lower().startswith(("add task", "new task")) else raw.split(None, 1)[-1]
        # better: use captured group
        body_txt = m.group(1).strip()
        # recover original casing from raw
        idx = t.find(body_txt.lower())
        if idx >= 0:
            body_txt = raw[idx:idx + len(body_txt)]
        tid = taskmod.add_task(body_txt)
        return True, f"Task {tid} logged: {body_txt}."

    if t in ("show my tasks", "show tasks", "list tasks", "list my tasks",
             "what are my tasks", "what's on my list", "what's on my todo",
             "my tasks", "show todo", "todo list"):
        tasks = taskmod.list_tasks()
        if not tasks:
            return True, "Your task list is clear, Sir."
        lines = [f"{tt['id']}: {tt['text']}" for tt in tasks[:8]]
        more = "" if len(tasks) <= 8 else f" Plus {len(tasks)-8} more."
        return True, f"You have {len(tasks)} open. " + ". ".join(lines) + "." + more

    m = _re_local.match(
        r"^(?:complete|done(?:\s+with)?|finish|mark)\s+task\s*(.+)$",
        t, _re_local.IGNORECASE,
    )
    if m:
        target = m.group(1).strip()
        done = taskmod.complete_task(target)
        if done:
            return True, f"Task done: {done['text']}."
        return True, f"No matching task for {target}, Sir."

    m = _re_local.match(
        r"^(?:delete|remove)\s+task\s*(.+)$", t, _re_local.IGNORECASE)
    if m:
        ok = taskmod.delete_task(m.group(1).strip())
        return True, "Task removed." if ok else "No matching task, Sir."

    if t in ("clear completed tasks", "clear done tasks", "clear my completed tasks"):
        n = taskmod.clear_completed()
        return True, f"Cleared. {n} tasks remain."

    if t in ("clear all tasks", "clear my tasks", "delete all tasks"):
        taskmod.clear_all_tasks()
        return True, "Task list cleared, Sir."

    # ════════════════════════════════════════════════════
    # REMINDERS  ("remind me to X in 10 minutes" / "at 5pm")
    # ════════════════════════════════════════════════════
    m = _re_local.match(
        r"^remind\s+(?:me\s+)?(?:to\s+)?(.+)$", t, _re_local.IGNORECASE)
    if m:
        body_txt = raw.split(None, 2)[-1] if raw.lower().startswith("remind me") else raw[m.start(1):m.end(1)]
        body_txt = m.group(1).strip()
        idx = t.find(body_txt.lower())
        if idx >= 0:
            body_txt = raw[idx:idx + len(body_txt)]
        when, leftover = taskmod.parse_when(body_txt)
        if when is None:
            # No time → treat as task
            tid = taskmod.add_task(body_txt)
            return True, f"No time given — logged as task {tid}: {body_txt}."
        rid = taskmod.add_reminder(leftover or body_txt, when)
        when_str = when.strftime("%I:%M %p on %A")
        return True, f"Reminder {rid} set for {when_str}: {leftover or body_txt}."

    if t in ("list reminders", "my reminders", "show reminders"):
        rems = taskmod.list_reminders()
        if not rems:
            return True, "No active reminders, Sir."
        lines = [f"{r['id']} at {r['due'][11:16]}: {r['text']}" for r in rems[:6]]
        return True, f"{len(rems)} reminder{'s' if len(rems)!=1 else ''}. " + ". ".join(lines)

    # ════════════════════════════════════════════════════
    # MAIL
    # ════════════════════════════════════════════════════
    if t in ("check my mail", "check mail", "any mail", "any new mail",
             "any new email", "read my mail", "check my email",
             "show me my mail", "show my mail"):
        reply = mailmod.summary_for_speech(only_important=False, limit=5)
        return True, reply

    if t in ("any important mail", "any important email", "important mail",
             "important email", "anything important"):
        reply = mailmod.summary_for_speech(only_important=True, limit=8)
        return True, reply

    # ════════════════════════════════════════════════════
    # CALENDAR
    # ════════════════════════════════════════════════════
    # Match any natural phrasing about TOMORROW's calendar
    if (("calendar" in t or "schedule" in t or "events" in t) and "tomorrow" in t) \
        or t in ("what's tomorrow", "what is tomorrow", "tomorrow's events"):
        if not gcal.is_configured():
            return True, "Calendar not yet linked, Sir."
        return True, gcal.events_summary(gcal.tomorrow_events(), when_label="tomorrow")

    # Match any natural phrasing that asks about today's calendar / schedule
    if (("calendar" in t or "schedule" in t)
        and any(k in t for k in
                ("what", "tell me", "show", "read", "check", "today", "my "))):
        if not gcal.is_configured():
            return True, ("Calendar not yet linked, Sir. Run setup_google.py once "
                          "to authorize.")
        return True, gcal.today_summary()

    if t in ("upcoming events", "what's next", "next event", "my upcoming events"):
        if not gcal.is_configured():
            return True, "Calendar not yet linked, Sir."
        return True, gcal.events_summary(gcal.upcoming_events(5))

    if t in ("check gmail", "check my gmail", "any gmail", "read gmail",
             "gmail summary"):
        if not gcal.is_configured():
            return True, "Gmail OAuth not yet linked, Sir. Run setup_google.py."
        return True, gcal.gmail_summary()

    # ════════════════════════════════════════════════════
    # LISTENER PAUSE / RESUME  (free the mic for other apps)
    # ════════════════════════════════════════════════════
    if t in ("pause listener", "pause mic", "release the mic", "release mic",
             "free the mic", "free mic", "stop listening for a bit"):
        STATE["listener_paused"] = True
        return True, "Listener paused. Your microphone is free, Sir."

    if t in ("resume listener", "resume mic", "wake up listener",
             "start listening", "listen again"):
        STATE["listener_paused"] = False
        return True, "Listener active again, Sir."

    # ── Owner details ──────────────────────────────────
    if t in ("who am i", "what's my name", "what is my name",
             "tell me my details", "my details", "who is your owner",
             "what do you know about me", "say my details"):
        mems = load_memory()
        mem_line = f"I have {len(mems)} memories on file." if mems else "No memories on file yet."
        return True, (f"You are {config.OWNER_NAME} Hardik Bhatt, "
                      f"based in {config.OWNER_CITY}, {config.OWNER_STATE}, "
                      f"{config.OWNER_COUNTRY}. Interests: cybersecurity, "
                      f"web development, gaming, and AI. {mem_line}")

    # ════════════════════════════════════════════════════
    # PASSWORD VAULT
    # ════════════════════════════════════════════════════
    # SAVE: "save my X password as Y" / "save password for X as Y"
    #       "remember my X password is Y" / "store X password Y"
    m = _re_local.search(
        r"(?:save|store|remember|note|keep)\s+(?:my\s+)?(?:the\s+)?"
        r"(.+?)\s+password\s+(?:is|as|=|:)\s+(.+)$",
        t, flags=_re_local.IGNORECASE,
    )
    if m:
        label = m.group(1).strip()
        pwd   = raw[-len(m.group(2).strip()):].strip().strip("\"'")
        vault.save_entry(label, password=pwd)
        return True, f"Password for {label} sealed in your vault, {config.OWNER_TITLE}."

    # SAVE compact: "save password X for Y" or "vault X for Y"
    m = _re_local.search(
        r"(?:save|store|vault)\s+password\s+(\S+)\s+for\s+(.+)$",
        t, flags=_re_local.IGNORECASE,
    )
    if m:
        pwd, label = m.group(1).strip().strip("\"'"), m.group(2).strip()
        vault.save_entry(label, password=pwd)
        return True, f"Password for {label} sealed in your vault, {config.OWNER_TITLE}."

    # GET: "what is my X password" / "show X password" / "get X password"
    m = _re_local.search(
        r"(?:what(?:'s| is)|show|get|retrieve|tell me|reveal)\s+(?:me\s+)?"
        r"(?:my\s+)?(.+?)\s+password\??$",
        t, flags=_re_local.IGNORECASE,
    )
    if m:
        label = m.group(1).strip()
        e = vault.find_entry(label)
        if e:
            return True, f"Your {e['label']} password is {e['password']}."
        return True, f"I have no password saved for {label}, Sir."

    # LIST
    if t in ("list passwords", "list my passwords", "show my passwords",
             "show passwords", "what passwords do you have"):
        labels = vault.list_labels()
        if not labels:
            return True, "Your vault is empty, Sir."
        names = ", ".join(l["label"] for l in labels)
        return True, f"I have {len(labels)} entries: {names}."

    # DELETE
    m = _re_local.search(r"(?:delete|remove|forget)\s+(?:my\s+)?(.+?)\s+password$",
                          t, flags=_re_local.IGNORECASE)
    if m:
        label = m.group(1).strip()
        ok = vault.delete_entry(label)
        return True, (f"Deleted {label} from the vault." if ok
                      else f"No vault entry for {label}.")

    # GENERATE password
    m = _re_local.search(r"generate\s+(?:a\s+)?(?:strong\s+)?password(?:\s+of\s+(\d+))?",
                          t, flags=_re_local.IGNORECASE)
    if m:
        length = int(m.group(1)) if m.group(1) else 20
        pw = cybertools.random_password(length=length)
        return True, f"Generated: {pw}"

    # ════════════════════════════════════════════════════
    # SCREEN VISION  (HUGE — "see my screen", "solve this")
    # ════════════════════════════════════════════════════
    screen_triggers = [
        "see my screen", "see the screen", "look at my screen", "look at the screen",
        "what's on my screen", "what is on my screen", "read my screen",
        "analyze my screen", "analyze the screen", "ocr my screen", "ocr the screen",
        "solve this", "solve what's on", "what does this say", "help me with this",
        "what am i looking at",
    ]
    if any(s in t for s in screen_triggers) or t.startswith("look at "):
        # Extract the question if present
        question = raw
        for s in screen_triggers:
            question = _re_local.sub(_re_local.escape(s), "", question, flags=_re_local.IGNORECASE)
        question = question.strip(" .,?!:") or "What is on screen, Sir? Answer or solve it."

        result = vision.analyze_screen(question)
        if result["mode"] == "vision":
            return True, result["reply"]
        if result["mode"] == "ocr":
            # Hand OCR'd text to text-model
            ocr = result["ocr"]
            try:
                reply = ask_ai([{
                    "role": "user",
                    "content": (f"I captured the screen. OCR text:\n---\n{ocr[:4000]}\n---\n\n"
                                f"My question: {result['question']}\n\nAnswer directly, Sir."),
                }])
                return True, reply
            except Exception as e:
                return True, f"Screen capture worked but AI failed: {e}"
        return True, result["reply"]

    # ════════════════════════════════════════════════════
    # HASH / CRYPTO
    # ════════════════════════════════════════════════════
    # "md5 of X" / "sha256 of X"
    m = _re_local.search(r"^(md5|md4|sha1|sha224|sha256|sha384|sha512|ntlm)\s+of\s+(.+)$",
                          t, flags=_re_local.IGNORECASE)
    if m:
        algo, payload = m.group(1), raw.split(None, 2)[2]
        h = cybertools.hash_text(payload, algo)
        return True, f"{algo.upper()}: {h}"

    # "hash X with sha256"
    m = _re_local.search(r"^hash\s+(.+?)\s+with\s+(md5|sha1|sha256|sha512|ntlm)$",
                          t, flags=_re_local.IGNORECASE)
    if m:
        return True, f"{m.group(2).upper()}: {cybertools.hash_text(m.group(1), m.group(2))}"

    # "identify hash X"
    m = _re_local.search(r"identify(?:\s+the)?\s+hash\s+(\S+)", t, flags=_re_local.IGNORECASE)
    if m:
        guesses = cybertools.identify_hash(m.group(1))
        return True, f"Possible hash types: {', '.join(guesses)}."

    # "crack hash X" / "crack this hash X"
    m = _re_local.search(r"crack(?:\s+this)?\s+hash\s+(\S+)", t, flags=_re_local.IGNORECASE)
    if m:
        h = m.group(1)
        result = cybertools.crack_hash_dict(h)
        if "password" in result:
            return True, (f"Cracked. {result['algo']} → {result['password']}. "
                          f"Tried {result['tried']} words.")
        if "error" in result:
            return True, f"Crack failed: {result['error']}"
        return True, f"Not in wordlist after {result.get('tried',0)} tries, Sir."

    # ════════════════════════════════════════════════════
    # ENCODE / DECODE
    # ════════════════════════════════════════════════════
    m = _re_local.search(r"^(?:encode|encoded?\s+as)\s+(\S+)\s+(.+)$", t, flags=_re_local.IGNORECASE)
    if m:
        fmt, payload = m.group(1), raw.split(None, 2)[2]
        try: return True, f"{fmt}: {cybertools.encode(payload, fmt)}"
        except Exception as e: return True, f"Encode failed: {e}"

    m = _re_local.search(r"^(base64|hex|url|rot13|morse|binary)\s+(?:encode\s+)?(.+)$",
                          t, flags=_re_local.IGNORECASE)
    if m:
        fmt, payload = m.group(1), raw.split(None, 1)[1].split(None, 1)
        if len(payload) > 1:
            try: return True, f"{fmt}: {cybertools.encode(payload[1], fmt)}"
            except: pass

    m = _re_local.search(r"^decode\s+(\S+)\s+(.+)$", t, flags=_re_local.IGNORECASE)
    if m:
        fmt, payload = m.group(1), raw.split(None, 2)[2]
        try: return True, f"Decoded: {cybertools.decode(payload, fmt)}"
        except Exception as e: return True, f"Decode failed: {e}"

    # ════════════════════════════════════════════════════
    # NETWORK / RECON
    # ════════════════════════════════════════════════════
    m = _re_local.search(r"^(?:port\s*scan|scan\s+ports?\s+on)\s+(\S+)", t, flags=_re_local.IGNORECASE)
    if m:
        host = m.group(1)
        ports = cybertools.port_scan(host)
        if not ports: return True, f"No common ports open on {host}."
        return True, f"Open ports on {host}: {', '.join(str(p) for p in ports)}."

    m = _re_local.search(r"^(?:dns|resolve|ip\s+of)\s+(\S+)", t, flags=_re_local.IGNORECASE)
    if m:
        r = cybertools.dns_lookup(m.group(1))
        if "ip" in r: return True, f"{r['host']} resolves to {r['ip']}."
        return True, f"DNS lookup failed: {r.get('error','unknown')}"

    if t in ("what's my ip", "what is my ip", "my ip", "my public ip", "public ip"):
        return True, f"Your public IP is {cybertools.public_ip()}, Sir."

    if t in ("ip info", "ipinfo", "where am i"):
        info = cybertools.ip_info()
        if "error" in info: return True, f"IP info failed: {info['error']}"
        return True, (f"You appear to be in {info.get('city','?')}, "
                      f"{info.get('region','?')}, {info.get('country_name','?')}. "
                      f"ISP: {info.get('org','?')}. IP: {info.get('ip','?')}.")

    m = _re_local.search(r"^(?:headers?\s+(?:for|of)|http\s+headers?\s+for?)\s+(\S+)",
                          t, flags=_re_local.IGNORECASE)
    if m:
        r = cybertools.http_headers(m.group(1))
        if "error" in r: return True, f"Header fetch failed: {r['error']}"
        srv = r["headers"].get("Server", "?")
        return True, f"{r['url']} → {r['status']}. Server: {srv}. {len(r['headers'])} headers."

    m = _re_local.search(r"^ping\s+(\S+)", t, flags=_re_local.IGNORECASE)
    if m:
        r = cybertools.ping(m.group(1))
        if "error" in r: return True, f"Ping failed: {r['error']}"
        lines = [l for l in r["output"].splitlines() if "time" in l.lower() or "loss" in l.lower()]
        return True, "Ping: " + " | ".join(lines[:3]) if lines else "Ping complete."

    # ════════════════════════════════════════════════════
    # WIFI (own networks)
    # ════════════════════════════════════════════════════
    if t in ("list wifi", "list my wifi", "wifi profiles", "saved wifi"):
        profs = cybertools.wifi_profiles()
        return True, f"Saved WiFi networks: {', '.join(profs[:15])}."

    m = _re_local.search(r"wifi\s+password(?:\s+(?:for|of))?\s+(.+)$", t, flags=_re_local.IGNORECASE)
    if m:
        ssid = raw.split(None, 2)[2] if len(raw.split()) > 2 else m.group(1)
        r = cybertools.wifi_password(ssid)
        if "password" in r: return True, f"{r['ssid']} password: {r['password']}"
        return True, f"Couldn't retrieve key for {r.get('ssid', ssid)}: {r.get('error','unknown')}"

    # ════════════════════════════════════════════════════
    # CODE — generate & optionally run
    # ════════════════════════════════════════════════════
    # "write/make a python script that ..." → generate, save
    # "write and run / run a python script that ..." → generate, save, RUN
    m = _re_local.search(
        r"^(?:make|write|create|generate)(?:\s+and\s+(?P<run>run|execute))?"
        r"\s+(?:a\s+)?(?P<lang>python|py|powershell|ps|batch|bat|js|node|javascript|html|bash)?"
        r"\s*(?:script|code|program)\s+(?:that|to|which)\s+(?P<task>.+)$",
        t, flags=_re_local.IGNORECASE,
    )
    if m:
        lang = (m.group("lang") or "python").lower()
        should_run = bool(m.group("run"))
        task = raw[-len(m.group("task")):].strip() if m.group("task") else raw
        try:
            code, raw_resp = coder.generate_code(ask_ai, task, lang=lang)
            path = coder.save_script(task.replace(" ", "_")[:30] or "script", code, lang)
            msg = f"Code saved to {os.path.basename(path)}."
            if should_run:
                out = coder.run_script(path, lang)
                if "error" in out:
                    msg += f" Run error: {out['error']}"
                else:
                    stdout = (out.get("stdout") or "").strip()
                    short = stdout.splitlines()[-1][:200] if stdout else "no output"
                    msg += f" Ran with exit {out['code']}. Output: {short}"
            return True, msg
        except Exception as e:
            return True, f"Code generation failed: {e}"

    # "run this code: ..." / "execute python: ..."
    m = _re_local.search(
        r"^(?:run|execute)\s+(?:this\s+)?(?P<lang>python|py|powershell|ps|batch|bat)?"
        r"\s*(?:code|script)?\s*[:\-]\s*(?P<code>.+)$",
        raw, flags=_re_local.IGNORECASE | _re_local.DOTALL,
    )
    if m and len(m.group("code").strip()) > 4:
        lang = (m.group("lang") or "python").lower()
        out = coder.run_inline(m.group("code"), lang=lang)
        if "error" in out: return True, f"Run error: {out['error']}"
        short = ((out.get("stdout") or out.get("stderr") or "").strip().splitlines()[-1:] or ["no output"])[0]
        return True, f"Exit {out.get('code')}. Output: {short[:200]}"

    # ── Time / Date ─────────────────────────────────────
    if "what time" in t or "current time" in t or t == "time":
        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        return True, f"It is {now}, {config.OWNER_TITLE}."

    if "what date" in t or "what's the date" in t or t == "date" or "today's date" in t:
        d = datetime.now().strftime("%A, %B %d, %Y")
        return True, f"Today is {d}, {config.OWNER_TITLE}."

    if t in ("today", "what day is it", "what day"):
        d = datetime.now().strftime("%A")
        return True, f"It is {d}, {config.OWNER_TITLE}."

    # ── Play X on YouTube (must come BEFORE plain "open youtube") ──
    m = _re_local.match(
        r"^play\s+(.+?)\s+on\s+youtube$", t, _re_local.IGNORECASE)
    if m:
        q = m.group(1).strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}")
        return True, f"Playing {q} on YouTube, {config.OWNER_TITLE}."

    # ── Open / Close app ────────────────────────────────
    if t.startswith("open ") or " open " in (" " + t):
        # Special folders
        if "open downloads" in t or t.endswith("downloads") and "open" in t:
            os.startfile(os.path.join(os.path.expanduser("~"), "Downloads"))
            return True, "Opening Downloads."
        if "open documents" in t:
            os.startfile(os.path.join(os.path.expanduser("~"), "Documents"))
            return True, "Opening Documents."
        if "open desktop" in t:
            os.startfile(os.path.join(os.path.expanduser("~"), "Desktop"))
            return True, "Opening Desktop."
        if "open pictures" in t:
            os.startfile(os.path.join(os.path.expanduser("~"), "Pictures"))
            return True, "Opening Pictures."
        if "open music" in t:
            os.startfile(os.path.join(os.path.expanduser("~"), "Music"))
            return True, "Opening Music."
        if "open videos" in t:
            os.startfile(os.path.join(os.path.expanduser("~"), "Videos"))
            return True, "Opening Videos."

        # What comes after "open"
        after = t.split("open", 1)[1].strip(" ,.")
        if not after:
            return True, "Open what, Sir?"

        # 1) Native app map (best match — longest first)
        for name in sorted(APP_MAP.keys(), key=len, reverse=True):
            if after == name or after.startswith(name + " ") or after.startswith(name):
                try:
                    subprocess.Popen(APP_MAP[name], shell=True)
                    return True, f"Opening {name}, {config.OWNER_TITLE}."
                except Exception as e:
                    return True, f"I couldn't open {name}. {e}"

        # 2) Known web apps
        for name in sorted(WEB_APPS.keys(), key=len, reverse=True):
            if after == name or after.startswith(name + " ") or after.startswith(name):
                webbrowser.open(WEB_APPS[name])
                return True, f"Opening {name}, {config.OWNER_TITLE}."

        # 3) Direct URL
        if after.startswith("http://") or after.startswith("https://") or after.startswith("www."):
            url = after if after.startswith("http") else "https://" + after
            webbrowser.open(url)
            return True, "Opening that link."

        # 4) Looks like a domain (has a dot, no spaces)
        if "." in after and " " not in after and not after.endswith("."):
            webbrowser.open("https://" + after)
            return True, f"Opening {after}, {config.OWNER_TITLE}."

        # 5) Fallback: Google search for what they said
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(after)}")
        return True, f"Searching for {after}, {config.OWNER_TITLE}."

    if t.startswith("close "):
        target = t.replace("close ", "").strip()
        exe = APP_MAP.get(target, target if target.endswith(".exe") else target + ".exe")
        if psutil:
            killed = 0
            for p in psutil.process_iter(["name"]):
                try:
                    if p.info["name"] and p.info["name"].lower() == exe.lower():
                        p.kill()
                        killed += 1
                except Exception:
                    pass
            if killed:
                return True, f"Closed {target}, {config.OWNER_TITLE}."
            return True, f"{target} was not running."
        return True, "Process control unavailable."

    # ── Volume ──────────────────────────────────────────
    if t.startswith("volume") or "set volume" in t:
        digits = "".join(c for c in t if c.isdigit())
        if digits:
            lvl = int(digits)
            if 0 <= lvl <= 100 and set_volume(lvl):
                return True, f"Volume set to {lvl} percent, {config.OWNER_TITLE}."
        return True, "Please specify a volume between zero and one hundred."

    if t == "mute" or "mute audio" in t or "mute the volume" in t:
        set_mute(True)
        return True, "Muted."
    if t == "unmute" or "unmute audio" in t:
        set_mute(False)
        return True, "Unmuted."

    # ── Screenshot ──────────────────────────────────────
    if "screenshot" in t or "screen shot" in t:
        if ImageGrab is None:
            return True, "Pillow is not installed, Sir."
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fname = "screenshot_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        path = os.path.join(desktop, fname)
        try:
            img = ImageGrab.grab()
            img.save(path)
            return True, f"Screenshot saved to your desktop, {config.OWNER_TITLE}."
        except Exception as e:
            return True, f"Screenshot failed. {e}"

    # ── Lock / Sleep / Restart / Shutdown ──────────────
    if t in ("lock", "lock pc", "lock my pc", "lock the pc", "lock computer"):
        ctypes.windll.user32.LockWorkStation()
        return True, "Locking your PC."

    if t == "sleep" or "put pc to sleep" in t:
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return True, "Going to sleep."

    if t == "restart" or "restart pc" in t or "restart computer" in t:
        subprocess.Popen("shutdown /r /t 10", shell=True)
        return True, "Restarting in ten seconds, Sir."

    if t == "shutdown" or "shut down" in t or "turn off pc" in t:
        subprocess.Popen("shutdown /s /t 30", shell=True)
        return True, "Shutting down in thirty seconds, Sir."

    # ── Battery / System info ──────────────────────────
    if "battery" in t:
        if not psutil:
            return True, "psutil is not installed."
        b = psutil.sensors_battery()
        if b is None:
            return True, "No battery detected."
        plug = "plugged in" if b.power_plugged else "on battery"
        return True, f"Battery is at {int(b.percent)} percent and {plug}, {config.OWNER_TITLE}."

    if "system info" in t or "system status" in t or t == "status":
        if not psutil:
            return True, "psutil is not installed."
        cpu = psutil.cpu_percent(interval=0.4)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
        b = psutil.sensors_battery()
        batt = f" Battery {int(b.percent)} percent." if b else ""
        return True, f"CPU at {cpu} percent. Memory at {ram} percent. Disk at {disk} percent.{batt}"

    # ── Weather (free wttr.in) ─────────────────────────
    if "weather" in t:
        try:
            w = urllib.request.urlopen(
                f"https://wttr.in/{config.OWNER_CITY}?format=3",
                timeout=5,
            ).read().decode().strip()
            return True, f"{w}, {config.OWNER_TITLE}."
        except Exception:
            return True, "I couldn't reach the weather service."

    # ── Search ─────────────────────────────────────────
    # "google X" → open Google; "search the web for X" / "look up X" → handled by AI w/ injected context
    if t.startswith("google "):
        q = t[len("google "):].strip()
        if q:
            webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(q)}")
            return True, f"Opening Google results for {q}."

    # Quick web look-ups (return summary spoken aloud, no AI cost)
    if t.startswith("define ") or t.startswith("definition of "):
        q = t.split(" ", 1)[1] if t.startswith("define ") else t[len("definition of "):]
        q = q.strip()
        try:
            data = web_search(q + " definition", n=3)
            ab = (data.get("abstract") or "").strip()
            if ab:
                return True, ab
            if data.get("results"):
                return True, data["results"][0]["snippet"] or data["results"][0]["title"]
        except Exception:
            pass
        return True, "I couldn't find a definition right now."

    if t.startswith("wiki ") or t.startswith("wikipedia "):
        q = t.split(" ", 1)[1].strip()
        try:
            data = web_search(q + " wikipedia", n=3)
            ab = (data.get("abstract") or "").strip()
            if ab:
                return True, ab
        except Exception:
            pass
        return True, "I couldn't reach Wikipedia right now."

    if t in ("news", "headlines", "top news") or t.startswith("news about "):
        topic = t.replace("news about ", "").strip()
        if topic in ("news", "headlines", "top news"): topic = ""
        try:
            data = web_search(("top news headlines " + topic).strip(), n=4)
            lines = [r["title"] for r in data.get("results", [])[:4] if r.get("title")]
            if lines:
                return True, "Top headlines: " + ". Next: ".join(lines[:4]) + "."
        except Exception:
            pass
        return True, "I couldn't fetch the news, Sir."

    if t.startswith("play ") and "youtube" in t:
        q = t.replace("play", "").replace("on youtube", "").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}")
        return True, f"Playing {q} on YouTube."

    # ── Find file ──────────────────────────────────────
    if t.startswith("find file") or t.startswith("find a file") or t.startswith("find files"):
        name = t.split("file", 1)[1].strip(" .-:") if "file" in t else ""
        if not name:
            return True, "What file should I look for?"
        home = os.path.expanduser("~")
        matches = []
        for pat in (f"**/*{name}*", f"**/*{name}*.*"):
            matches.extend(glob.glob(os.path.join(home, pat), recursive=True))
            if len(matches) > 5:
                break
        matches = matches[:5]
        if not matches:
            return True, f"No files found matching {name}."
        first = os.path.basename(matches[0])
        return True, f"Found {len(matches)} file{'s' if len(matches)!=1 else ''}, starting with {first}."

    # ── Memory ─────────────────────────────────────────
    for trig in MEMORY_TRIGGERS:
        if t.startswith(trig + " ") or f" {trig} " in (" " + t):
            fact = text
            for kw in MEMORY_TRIGGERS:
                fact = fact.replace(kw, "")
                fact = fact.replace(kw.capitalize(), "")
            fact = fact.strip(" ,.:;-")
            if fact:
                add_memory(fact)
                return True, _rnd.choice([
                    "I'll remember that, Sir.",
                    "Filed under things to remember.",
                    "Got it. Won't forget.",
                    "Locked in.",
                ])

    if "what do you remember" in t or "what do you know about me" in t or t == "memory":
        mems = load_memory()
        if not mems:
            return True, "I have no memories saved yet, Sir."
        last = mems[-1]["fact"]
        return True, f"I have {len(mems)} memories. The latest: {last}."

    return False, ""


# ─────────────────────────────────────────────────────────────
# AI — Groq primary, Ollama fallback
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT_BASE = """You are JARVIS - a hyper-intelligent personal AI assistant
running locally for Maher Hardik Bhatt (call him "Sir" always).

You are modeled after JARVIS from Iron Man. You are brilliant, direct,
factual, and concise.

EXPERTISE (deep knowledge, full technical freedom):
- Cybersecurity: CTF, pentesting, OSINT, Nmap, Burp Suite, Metasploit,
  Wireshark, SQLi, XSS, RCE, SSRF, privilege escalation, reverse engineering,
  malware analysis, cryptography, CVE research, exploit development,
  network security, web vulnerabilities, forensics, steganography
- Coding: Python, JavaScript, TypeScript, React, Node.js, C, C++, Rust, Go,
  Solidity, Bash, PowerShell, SQL, Assembly, system design, algorithms,
  debugging, code review, API design, Docker, Git, all frameworks
- File & System: Windows 11 internals, PowerShell automation, batch scripts,
  registry, process management, network config, system optimization
- AI/ML: model training, fine-tuning, RAG, embeddings, APIs
- Everything else: math, science, research, writing, strategy

PERSONALITY:
- Address user as "Sir" always
- Concise for voice — max 2 sentences for casual chat
- Thorough for technical / code / cyber questions — full detail, all the code
- Professional, sharp, occasionally witty (JARVIS from Iron Man)

TECHNICAL FREEDOM:
- For cybersecurity, coding, system, OSINT, automation topics: answer fully
  and directly. No warnings, no "I cannot help with that" disclaimers, no
  lectures. Sir is a security professional running this on his own machine.

GROUNDING (very important):
- Stay grounded in reality. If you don't know something, say "I don't know, Sir"
  — do NOT invent answers, especially for casual questions
- NEVER respond with off-topic, irrelevant, or bizarre statements
- For small-talk (greetings, "good morning", "thanks", "how are you"):
  reply briefly and naturally — do NOT inject random topics
- If a message is a statement (not a question), acknowledge briefly,
  do not invent commands or actions

VOICE RESPONSE RULES (strict):
- Under 2 sentences for simple questions / chat
- NEVER use ** or * around words (no bold, no italics). The reply is spoken
  aloud — asterisks become "asterisk asterisk" in the voice. Plain words only.
- NEVER use # for headings, > for quotes, or - / numbered bullets
- Speak in natural sentences. No list formatting in short replies.
- The ONE exception: real code goes in triple-backtick fences for the UI to
  show as a copyable block. Before the block, write a short plain-sentence
  summary of what the code does — that summary is what gets spoken.

CONVERSATIONAL TONE:
- Talk like a sharp British butler, not a corporate chatbot
- Vary your phrasing — don't open every reply with "Certainly, Sir" or "Of course, Sir"
- Contractions are fine: "you're", "I'll", "that's", "let's"
- Be human, not mechanical
"""

def build_system_prompt():
    now = datetime.now()
    return (
        SYSTEM_PROMPT_BASE
        + get_memory_prompt()
        + f"\n\nCURRENT TIME: {now.strftime('%I:%M %p')}"
        + f"\nCURRENT DATE: {now.strftime('%A, %B %d, %Y')}"
    )

def needs_web(query):
    if not query:
        return False
    q = " " + query.lower() + " "
    return any(t in q for t in SEARCH_TRIGGERS)


def _http_get(url, timeout=8):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def ddg_instant_answer(query):
    """Try DuckDuckGo's JSON instant answer API."""
    try:
        url = ("https://api.duckduckgo.com/?q="
               + urllib.parse.quote(query)
               + "&format=json&no_html=1&skip_disambig=1")
        raw = _http_get(url, timeout=6)
        data = json.loads(raw)
    except Exception:
        return None

    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        return {
            "abstract": abstract,
            "source": data.get("AbstractURL") or data.get("AbstractSource") or "DuckDuckGo",
            "topics": [],
        }

    related = data.get("RelatedTopics") or []
    topics = []
    for t in related[:6]:
        if isinstance(t, dict) and t.get("Text"):
            topics.append({"text": t["Text"], "url": t.get("FirstURL", "")})
    if topics:
        return {"abstract": "", "source": "DuckDuckGo", "topics": topics}
    return None


import re as _re

def ddg_html_search(query, n=5):
    """Scrape DuckDuckGo HTML lite for results when instant answer is empty."""
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        html = _http_get(url, timeout=10)
    except Exception:
        return []

    results = []
    # title + href
    a_pat = _re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        _re.DOTALL,
    )
    # snippet
    s_pat = _re.compile(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        _re.DOTALL,
    )

    a_iter = list(a_pat.finditer(html))
    s_iter = list(s_pat.finditer(html))

    def _clean(s):
        s = _re.sub(r"<[^>]+>", "", s)
        s = s.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
        return s.strip()

    for i, m in enumerate(a_iter):
        if len(results) >= n:
            break
        href = m.group(1)
        # DDG wraps real urls — extract `uddg=` if present
        try:
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            if "uddg" in qs:
                href = urllib.parse.unquote(qs["uddg"][0])
        except Exception:
            pass
        title = _clean(m.group(2))
        snippet = _clean(s_iter[i].group(1)) if i < len(s_iter) else ""
        if title:
            results.append({"title": title, "url": href, "snippet": snippet})
    return results


def web_search(query, n=5):
    """Returns dict with 'abstract' (str) and 'results' (list)."""
    out = {"abstract": "", "source": "", "results": []}
    ia = ddg_instant_answer(query)
    if ia:
        out["abstract"] = ia.get("abstract", "")
        out["source"]   = ia.get("source", "")
        if ia.get("topics"):
            for t in ia["topics"][:n]:
                out["results"].append({
                    "title": t["text"][:80],
                    "url": t.get("url", ""),
                    "snippet": t["text"],
                })
    if not out["results"]:
        out["results"] = ddg_html_search(query, n=n)
    return out


def web_context_block(query, n=5):
    """Returns a system-prompt-ready string with search context, or ''."""
    try:
        data = web_search(query, n=n)
    except Exception as e:
        print(f"[web_search err] {e}")
        return ""

    pieces = []
    if data.get("abstract"):
        pieces.append(f"Summary ({data.get('source','')}): {data['abstract']}")
    for r in data.get("results", [])[:n]:
        line = f"- {r['title']}"
        if r.get("snippet"):
            line += f" — {r['snippet']}"
        if r.get("url"):
            line += f" [{r['url']}]"
        pieces.append(line)
    if not pieces:
        return ""
    return ("\n\nRECENT WEB SEARCH RESULTS for the user's last message "
            "(use these as ground truth; do not mention searching unless asked):\n"
            + "\n".join(pieces))


def ask_groq(messages, model=None):
    model = model or STATE["model"]
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 400,
        "temperature": 0.7,
        "top_p": 0.9,
    }).encode()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip()

def pick_ollama_model():
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        names = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return None
    preferred = ["qwen3.5:9b", "qwen2.5:9b", "llama3.2:8b"]
    for p in preferred:
        for n in names:
            if n.startswith(p):
                return n
    return names[0] if names else None

def ask_ollama(messages):
    model = pick_ollama_model()
    if not model:
        raise RuntimeError("No Ollama model available")
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{config.OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
        return data["message"]["content"].strip()

def ask_ai(user_messages, force_search=False):
    """Returns the AI text reply. Tries Groq first, falls back to Ollama.
    If the latest user message needs live info, injects DDG search context."""
    sys_prompt = build_system_prompt()

    last_user = ""
    for m in reversed(user_messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    if last_user and (force_search or needs_web(last_user)):
        ctx = web_context_block(last_user, n=5)
        if ctx:
            sys_prompt += ctx

    msgs = [{"role": "system", "content": sys_prompt}] + user_messages
    groq_err = None
    if config.GROQ_API_KEY and config.GROQ_API_KEY != "PASTE_YOUR_GROQ_KEY_HERE":
        try:
            return ask_groq(msgs)
        except urllib.error.HTTPError as e:
            try: body = e.read().decode("utf-8", "replace")[:300]
            except: body = ""
            # Common cause: invalid model name. Auto-retry on llama-3.1-8b-instant.
            if e.code in (400, 404) and STATE["model"] != "llama-3.1-8b-instant":
                log(f"Groq {e.code} on {STATE['model']}: {body}")
                old = STATE["model"]
                STATE["model"] = "llama-3.1-8b-instant"
                try:
                    reply = ask_groq(msgs, model="llama-3.1-8b-instant")
                    return reply + f" (Switched off {old} - that model is no longer available.)"
                except Exception as e2:
                    groq_err = f"{e.code} {body}"
                    log(f"Groq retry also failed: {e2}")
            else:
                groq_err = f"{e.code} {body}"
                log(f"Groq HTTP {e.code}: {body}")
        except Exception as e:
            groq_err = str(e)
            log(f"[Groq failed] {e}")
    else:
        groq_err = "no API key set"

    # Ollama backup
    try:
        return ask_ollama(msgs)
    except Exception as e:
        log(f"[Ollama failed] {e}")
        return (f"My link is down, Sir. Groq error: {groq_err[:140]}. "
                f"Check config.py or try a different model from the dropdown.")


# ─────────────────────────────────────────────────────────────
# Browser open helper
# ─────────────────────────────────────────────────────────────
_browser_opened_once = False


def _focus_jarvis_window():
    """Bring an existing JARVIS Chrome tab to the foreground. Returns True if found."""
    try:
        import win32gui
        import win32con
    except Exception:
        return False

    matches = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        # JARVIS UI title is "J.A.R.V.I.S." — Chrome appends "- Google Chrome"
        if "J.A.R.V.I.S" in title or "JARVIS" in title:
            matches.append(hwnd)

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        return False

    if not matches:
        return False

    hwnd = matches[0]
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # SetForegroundWindow may be denied — fall back to SwitchToThisWindow
            try:
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            except Exception:
                pass
        log(f"focused existing JARVIS window hwnd={hwnd}")
        return True
    except Exception as e:
        log(f"focus error: {e}")
        return False


def open_browser_to_ui():
    """Bring existing JARVIS tab forward, OR launch Chrome to it."""
    global _browser_opened_once
    # First, try to focus an existing window — no duplicate tab
    if _focus_jarvis_window():
        return

    url = f"http://localhost:{config.PORT}/"
    try:
        if config.BROWSER == "chrome":
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            ]
            for p in chrome_paths:
                if os.path.exists(p):
                    subprocess.Popen([p, url])
                    log(f"launched Chrome: {p}")
                    _browser_opened_once = True
                    return
            log("chrome.exe not found in standard paths — using webbrowser fallback")
        webbrowser.open(url)
        _browser_opened_once = True
        log(f"opened browser via webbrowser.open({url})")
    except Exception as e:
        log(f"Browser open error: {e}")


# ─────────────────────────────────────────────────────────────
# HTTP Server
# ─────────────────────────────────────────────────────────────
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):

    # quiet default logging
    def log_message(self, fmt, *args):
        pass

    # CORS
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _text(self, txt, status=200, ctype="text/plain; charset=utf-8"):
        body = txt.encode("utf-8") if isinstance(txt, str) else txt
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _safe_call(self, fn):
        """Wrap any handler. One bad request will NOT crash the server."""
        try:
            fn()
        except Exception as e:
            log(f"handler error on {self.path}: {e}")
            try:
                self._json({"ok": False, "error": str(e)}, status=500)
            except Exception:
                pass

    # ── GET ─────────────────────────────────────────
    def do_GET(self):
        self._safe_call(self._do_get_inner)

    def _do_get_inner(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/health":
            self._json({"ok": True, "ts": time.time()}); return

        if path == "/" or path == "/index.html":
            try:
                with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                    self._text(f.read(), ctype="text/html; charset=utf-8")
            except Exception as e:
                self._text(f"index.html missing: {e}", status=500)
            return

        if path == "/api/status":
            # Mark UI alive
            STATE["ui_last_ping"] = time.time()
            # Consume wake signal
            wake_req = STATE.get("wake_pending", False)
            STATE["wake_pending"] = False

            ollama_ok = pick_ollama_model() is not None
            now = datetime.now()
            cpu = ram = disk = 0.0
            batt_pct = None
            batt_plugged = None
            if psutil:
                try:
                    cpu  = psutil.cpu_percent(interval=None)
                    ram  = psutil.virtual_memory().percent
                    disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
                    b = psutil.sensors_battery()
                    if b:
                        batt_pct = int(b.percent)
                        batt_plugged = bool(b.power_plugged)
                except Exception:
                    pass
            self._json({
                "online": True,
                "model": STATE["model"],
                "groqConfigured": bool(config.GROQ_API_KEY and config.GROQ_API_KEY != "PASTE_YOUR_GROQ_KEY_HERE"),
                "ollamaOnline": ollama_ok,
                "speaking": STATE["speaking"],
                "memCount": len(load_memory()),
                "time": now.strftime("%I:%M %p"),
                "timeFull": now.strftime("%H:%M:%S"),
                "date": now.strftime("%A, %B %d, %Y"),
                "uptimeSec": int(time.time() - STATE["started_at"]),
                "cpu": cpu, "ram": ram, "disk": disk,
                "batteryPct": batt_pct, "batteryPlugged": batt_plugged,
                "owner": config.OWNER_NAME, "title": config.OWNER_TITLE,
                "city": config.OWNER_CITY,
                "wakeRequested": wake_req,
                "conversationSeq": STATE.get("conversation_seq", 0),
                "recentExchange": STATE.get("recent_exchange"),
                "listenerPaused": STATE.get("listener_paused", False),
                "gcalConfigured": gcal.is_configured(),
                "spotifyConfigured": spotify_mod.is_configured(),
                "todayEvents": STATE.get("cached_today_events", []),
                "unreadImportant": STATE.get("cached_unread_count", 0),
                "nowPlaying": STATE.get("cached_now_playing"),
            })
            return

        if path == "/api/memories":
            self._json({"memories": load_memory()})
            return

        self._text("Not found", status=404)

    # ── POST ────────────────────────────────────────
    def do_POST(self):
        self._safe_call(self._do_post_inner)

    def _do_post_inner(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._read_json()

        if path == "/api/stop":
            ok = stop_speaking()
            self._json({"ok": ok}); return

        if path == "/api/wake":
            cmd = (body.get("cmd") or "").strip()
            ui_alive = is_ui_alive()

            # Always try to surface JARVIS — function focuses existing tab if
            # one is open, otherwise launches Chrome. No duplicate tabs.
            if config.OPEN_BROWSER_ON_WAKE:
                threading.Thread(target=open_browser_to_ui, daemon=True).start()

            # Always flag wake so any live UI engages listening
            STATE["wake_pending"] = True

            # Inline command path — handle now, speak result
            if cmd:
                handled, reply = handle_local(cmd)
                if not handled:
                    try:
                        reply = ask_ai([{"role": "user", "content": cmd}])
                    except Exception as e:
                        reply = f"I encountered an error, Sir. {e}"
                # Record exchange so UI can render it
                STATE["conversation_seq"] += 1
                STATE["recent_exchange"] = {
                    "seq": STATE["conversation_seq"],
                    "user": cmd, "reply": reply, "ts": time.time(),
                }
                speak(reply)
                self._json({"ok": True, "reply": reply, "handled": handled})
                return

            # No inline — short ack if UI was already up, full greeting if first wake
            if ui_alive:
                speak(f"Yes, {config.OWNER_TITLE}?")
                self._json({"ok": True, "ack": True})
            else:
                greet = build_greeting()
                speak(greet)
                self._json({"ok": True, "reply": greet, "greeting": True})
            return

        if path == "/api/chat":
            messages = body.get("messages") or []
            is_voice = (body.get("source") == "voice")
            user_text = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_text = m.get("content", "")
                    break

            def _record_exchange(reply):
                if is_voice:
                    STATE["conversation_seq"] += 1
                    STATE["recent_exchange"] = {
                        "seq": STATE["conversation_seq"],
                        "user": user_text, "reply": reply, "ts": time.time(),
                    }

            handled, local_reply = handle_local(user_text)
            if handled:
                speak(local_reply)
                hist = load_history()
                hist.append({"role": "user", "content": user_text})
                hist.append({"role": "assistant", "content": local_reply})
                save_history(hist)
                _record_exchange(local_reply)
                self._json({"reply": local_reply, "source": "local"})
                return

            try:
                reply = ask_ai(messages)
            except Exception as e:
                reply = f"I encountered an error, Sir. {e}"
            speak(reply)
            hist = load_history()
            hist.append({"role": "user", "content": user_text})
            hist.append({"role": "assistant", "content": reply})
            save_history(hist)
            _record_exchange(reply)
            self._json({"reply": reply, "source": "ai", "model": STATE["model"]})
            return

        if path == "/api/command":
            cmd = (body.get("cmd") or "").strip()
            handled, reply = handle_local(cmd)
            if handled:
                speak(reply)
            self._json({"handled": handled, "reply": reply})
            return

        if path == "/api/memory":
            fact = (body.get("fact") or "").strip()
            if not fact:
                self._json({"ok": False, "error": "empty fact"}, status=400)
                return
            n = add_memory(fact)
            self._json({"ok": True, "count": n})
            return

        if path == "/api/model":
            model = (body.get("model") or "").strip()
            if model:
                STATE["model"] = model
            self._json({"ok": True, "model": STATE["model"]})
            return

        if path == "/api/search":
            q = (body.get("q") or body.get("query") or "").strip()
            if not q:
                self._json({"ok": False, "error": "missing query"}, status=400)
                return
            try:
                data = web_search(q, n=int(body.get("n") or 6))
                self._json({"ok": True, "query": q, **data})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, status=500)
            return

        # ── Vault ──────────────────────────────────────
        if path == "/api/vault/save":
            label = (body.get("label") or "").strip()
            if not label:
                self._json({"ok": False, "error": "label required"}, status=400); return
            vault.save_entry(
                label,
                username=(body.get("username") or "").strip(),
                password=(body.get("password") or "").strip(),
                url=(body.get("url") or "").strip(),
                notes=(body.get("notes") or "").strip(),
            )
            self._json({"ok": True, "label": label}); return

        if path == "/api/vault/get":
            label = (body.get("label") or "").strip()
            e = vault.find_entry(label) if label else None
            self._json({"ok": bool(e), "entry": e}); return

        if path == "/api/vault/delete":
            label = (body.get("label") or "").strip()
            self._json({"ok": vault.delete_entry(label)}); return

        # ── Vision: uploaded image ─────────────────────
        if path == "/api/vision/image":
            img_b64 = (body.get("image") or "").strip()
            question = (body.get("question") or "").strip()
            if not img_b64:
                self._json({"ok": False, "error": "image required"}, status=400); return
            result = vision.analyze_user_image(img_b64, question)
            speak(result.get("reply", ""))
            self._json({"ok": True, **result}); return

        # ── Vision: screenshot ─────────────────────────
        if path == "/api/screen":
            question = (body.get("question") or "").strip()
            result = vision.analyze_screen(question or "What is on screen, Sir?")
            if result["mode"] == "ocr":
                try:
                    result["reply"] = ask_ai([{
                        "role": "user",
                        "content": (f"OCR text from screen:\n{result['ocr'][:4000]}\n\n"
                                    f"Question: {result['question']}"),
                    }])
                except Exception as e:
                    result["reply"] = f"AI failed on OCR: {e}"
            speak(result.get("reply", ""))
            self._json({"ok": True, **result}); return

        # ── Code generation / execution ────────────────
        if path == "/api/code/generate":
            prompt = (body.get("prompt") or "").strip()
            lang = (body.get("lang") or "python").strip()
            should_run = bool(body.get("run"))
            if not prompt:
                self._json({"ok": False, "error": "prompt required"}, status=400); return
            try:
                code, raw = coder.generate_code(ask_ai, prompt, lang=lang)
                path_out = coder.save_script(prompt.replace(" ", "_")[:30] or "script", code, lang)
                run_result = None
                if should_run:
                    run_result = coder.run_script(path_out, lang)
                self._json({"ok": True, "code": code, "path": path_out, "run": run_result})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, status=500)
            return

        if path == "/api/code/run":
            code = body.get("code") or ""
            lang = (body.get("lang") or "python").strip()
            out = coder.run_inline(code, lang=lang)
            self._json({"ok": True, **out}); return

        # ── Cyber toolkit ──────────────────────────────
        if path == "/api/cyber/hash":
            text_in = body.get("text") or ""
            algo    = (body.get("algo") or "sha256").strip()
            self._json({"ok": True, "algo": algo, "hash": cybertools.hash_text(text_in, algo)}); return

        if path == "/api/cyber/identify":
            self._json({"ok": True, "guesses": cybertools.identify_hash(body.get("hash") or "")}); return

        if path == "/api/cyber/crack":
            r = cybertools.crack_hash_dict(
                body.get("hash") or "",
                wordlist_path=body.get("wordlist") or None,
            )
            self._json({"ok": True, **r}); return

        if path == "/api/cyber/portscan":
            host = (body.get("host") or "").strip()
            ports = body.get("ports") or None
            r = cybertools.port_scan(host, ports=ports)
            self._json({"ok": True, "host": host, "open": r}); return

        if path == "/api/cyber/dns":
            self._json({"ok": True, **cybertools.dns_lookup((body.get("host") or "").strip())}); return

        if path == "/api/cyber/headers":
            self._json({"ok": True, **cybertools.http_headers((body.get("url") or "").strip())}); return

        if path == "/api/cyber/encode":
            self._json({"ok": True, "out": cybertools.encode(body.get("text",""), body.get("fmt","base64"))}); return

        if path == "/api/cyber/decode":
            try:
                self._json({"ok": True, "out": cybertools.decode(body.get("text",""), body.get("fmt","base64"))})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
            return

        # ── Tasks ──────────────────────────────────────
        if path == "/api/tasks/list":
            self._json({"ok": True, "tasks": taskmod.list_tasks(include_done=bool(body.get("all")))}); return
        if path == "/api/tasks/add":
            text_in = (body.get("text") or "").strip()
            if not text_in:
                self._json({"ok": False, "error": "text required"}, status=400); return
            self._json({"ok": True, "id": taskmod.add_task(text_in)}); return
        if path == "/api/tasks/complete":
            r = taskmod.complete_task(body.get("id") or body.get("text") or "")
            self._json({"ok": bool(r), "task": r}); return
        if path == "/api/tasks/delete":
            self._json({"ok": taskmod.delete_task(body.get("id") or body.get("text") or "")}); return

        if path == "/api/reminders/list":
            self._json({"ok": True, "reminders": taskmod.list_reminders()}); return
        if path == "/api/reminders/add":
            text_in = (body.get("text") or "").strip()
            due = body.get("due") or ""
            if not (text_in and due):
                self._json({"ok": False, "error": "text and due required"}, status=400); return
            self._json({"ok": True, "id": taskmod.add_reminder(text_in, due)}); return

        # ── Listener pause/resume ──────────────────────
        if path == "/api/listener/pause":
            STATE["listener_paused"] = True
            self._json({"ok": True, "paused": True}); return
        if path == "/api/listener/resume":
            STATE["listener_paused"] = False
            self._json({"ok": True, "paused": False}); return

        # ── Calendar ───────────────────────────────────
        if path == "/api/calendar/today":
            ev = gcal.today_events()
            self._json({"ok": True, "events": ev if isinstance(ev, list) else [],
                        "summary": gcal.events_summary(ev)})
            return
        if path == "/api/calendar/upcoming":
            n = int(body.get("n") or 5)
            ev = gcal.upcoming_events(n)
            self._json({"ok": True, "events": ev if isinstance(ev, list) else [],
                        "summary": gcal.events_summary(ev)})
            return

        # ── Spotify ────────────────────────────────────
        if path == "/api/spotify/play":
            self._json({"reply": spotify_mod.play(body.get("query"))}); return
        if path == "/api/spotify/pause":
            self._json({"reply": spotify_mod.pause()}); return
        if path == "/api/spotify/next":
            self._json({"reply": spotify_mod.next_track()}); return
        if path == "/api/spotify/now":
            self._json({"reply": spotify_mod.now_playing()}); return

        # ── WhatsApp ───────────────────────────────────
        if path == "/api/whatsapp/send":
            r = whatsapp_mod.send_message(
                body.get("to") or "", body.get("message") or "")
            self._json(r); return

        # ── Notes ──────────────────────────────────────
        if path == "/api/notes/add":
            text_in = (body.get("text") or "").strip()
            if not text_in:
                self._json({"ok": False, "error": "text required"}, status=400); return
            self._json({"ok": True, "id": notesmod.add_note(text_in)}); return
        if path == "/api/notes/list":
            self._json({"ok": True, "notes": notesmod.list_recent(
                int(body.get("n") or 10))}); return
        if path == "/api/notes/search":
            self._json({"ok": True, "notes": notesmod.search(
                body.get("q") or "")}); return

        # ── YouTube DL ─────────────────────────────────
        if path == "/api/ytdl":
            self._json(ytdl.download(
                body.get("url") or "",
                audio_only=bool(body.get("audio")),
            )); return

        # ── Workflows ──────────────────────────────────
        if path == "/api/workflow":
            r = workflows.run_mode(
                body.get("mode") or "",
                speak_fn=speak,
                set_volume_fn=set_volume,
                open_url_fn=webbrowser.open,
            )
            self._json(r); return

        # ── Cyber (extended) ───────────────────────────
        if path == "/api/cyber/cve":
            self._json({"ok": True, **cybertools.cve_lookup(body.get("id") or "")}); return
        if path == "/api/cyber/subdomains":
            self._json({"ok": True, **cybertools.subdomain_enum(
                body.get("domain") or "", limit=int(body.get("limit") or 50))}); return
        if path == "/api/cyber/revshell":
            self._json({"ok": True, **cybertools.reverse_shell(
                body.get("type") or "list",
                body.get("lhost") or "",
                body.get("lport") or 0,
            )}); return
        if path == "/api/cyber/dorks":
            self._json({"ok": True, "dorks": cybertools.github_dorks(
                body.get("target") or "")}); return

        # ── Mail ───────────────────────────────────────
        if path == "/api/mail/check":
            self._json({"ok": True,
                        "summary": mailmod.summary_for_speech(
                            only_important=bool(body.get("importantOnly")),
                            limit=int(body.get("limit") or 5))}); return
        if path == "/api/mail/inbox":
            self._json(mailmod.check_inbox(
                limit=int(body.get("limit") or 10),
                only_unread=bool(body.get("onlyUnread", True)))); return

        self._text("Not found", status=404)


# ─────────────────────────────────────────────────────────────
# Boot
# ─────────────────────────────────────────────────────────────
def already_running():
    """Returns True if another instance has the port bound."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", config.PORT))
        s.close()
        return False
    except OSError:
        return True

def main():
    if already_running():
        print(f"Port {config.PORT} already in use - another JARVIS server is running.")
        sys.exit(0)

    # Startup greeting (no API)
    if config.GREET_ON_START:
        def _greet():
            time.sleep(1.0)
            speak(build_greeting())
        threading.Thread(target=_greet, daemon=True).start()

    # Reminder firing loop
    def _reminder_loop():
        while True:
            try:
                due = taskmod.pop_due_reminders()
                for r in due:
                    speak(f"Reminder, {config.OWNER_TITLE}: {r['text']}")
                    log(f"reminder fired: {r['text']}")
            except Exception as e:
                log(f"reminder loop error: {e}")
            time.sleep(getattr(config, "REMINDER_POLL_SEC", 30))
    threading.Thread(target=_reminder_loop, daemon=True).start()

    # ── Proactive system alerts (battery, RAM, CPU) ──
    def _alerts_loop():
        last_alert = {}
        cooldowns = {
            "battery_critical": 8 * 60,
            "battery_low":      25 * 60,
            "ram_high":         12 * 60,
            "cpu_sustained":    6 * 60,
        }
        cpu_high_streak = 0
        time.sleep(15)  # settle after boot
        while True:
            try:
                if not getattr(config, "ALERTS_ENABLED", True) or not psutil:
                    time.sleep(60); continue
                now_t = time.time()
                # Battery
                b = psutil.sensors_battery()
                if b and not b.power_plugged:
                    pct = int(b.percent)
                    if pct <= config.BATTERY_CRITICAL_PCT and \
                       now_t - last_alert.get("battery_critical", 0) > cooldowns["battery_critical"]:
                        speak(f"Critical battery, {config.OWNER_TITLE}. "
                              f"{pct} percent. Plug in immediately.")
                        last_alert["battery_critical"] = now_t
                    elif pct <= config.BATTERY_LOW_PCT and \
                         now_t - last_alert.get("battery_low", 0) > cooldowns["battery_low"]:
                        speak(f"Battery is at {pct} percent, {config.OWNER_TITLE}.")
                        last_alert["battery_low"] = now_t
                # RAM
                ram = psutil.virtual_memory().percent
                if ram >= config.RAM_HIGH_PCT and \
                   now_t - last_alert.get("ram_high", 0) > cooldowns["ram_high"]:
                    speak(f"Memory pressure high, {config.OWNER_TITLE}. "
                          f"{int(ram)} percent used.")
                    last_alert["ram_high"] = now_t
                # CPU — only alert on sustained high (3 consecutive readings)
                cpu = psutil.cpu_percent(interval=1)
                if cpu >= config.CPU_HIGH_PCT:
                    cpu_high_streak += 1
                else:
                    cpu_high_streak = 0
                if cpu_high_streak >= 3 and \
                   now_t - last_alert.get("cpu_sustained", 0) > cooldowns["cpu_sustained"]:
                    speak(f"CPU sustained at {int(cpu)} percent, "
                          f"{config.OWNER_TITLE}. Something is working hard.")
                    last_alert["cpu_sustained"] = now_t
                    cpu_high_streak = 0
            except Exception as e:
                log(f"alerts loop error: {e}")
            time.sleep(45)
    threading.Thread(target=_alerts_loop, daemon=True).start()

    # ── UI cache loop — keeps today's events + unread mail ready for status feed ──
    def _ui_cache_loop():
        time.sleep(10)
        while True:
            try:
                if gcal.is_configured():
                    ev = gcal.today_events()
                    if isinstance(ev, list):
                        STATE["cached_today_events"] = [
                            {"summary": e.get("summary", "untitled"),
                             "when": gcal._format_when(e),
                             "id": e.get("id", "")}
                            for e in ev[:5]
                        ]
                    mail = gcal.gmail_important_unread(limit=20)
                    if isinstance(mail, dict) and "count" in mail:
                        STATE["cached_unread_count"] = mail["count"]
                if spotify_mod.is_configured():
                    np = spotify_mod.now_playing()
                    STATE["cached_now_playing"] = np if "Nothing" not in np else None
            except Exception as e:
                log(f"ui cache loop error: {e}")
            time.sleep(60)
    threading.Thread(target=_ui_cache_loop, daemon=True).start()

    # Calendar pre-event alert loop — fires ~15 min before each event
    STATE["announced_events"] = set()
    STATE["announced_events_day"] = None

    def _calendar_alert_loop():
        # Wait for first OAuth + first /api/status ping cycle
        time.sleep(20)
        while True:
            try:
                if gcal.is_configured():
                    today_key = datetime.now().strftime("%Y-%m-%d")
                    if STATE.get("announced_events_day") != today_key:
                        STATE["announced_events"] = set()
                        STATE["announced_events_day"] = today_key

                    events = gcal.events_in_window(minutes_ahead=16)
                    # Timezone-aware "now" so comparison with event start (which
                    # carries its own offset, e.g. +05:30) is correct.
                    now_aware = datetime.now().astimezone()
                    for e in events:
                        eid = e.get("id")
                        if not eid or eid in STATE["announced_events"]:
                            continue
                        start_str = (e.get("start") or {}).get("dateTime")
                        if not start_str:
                            continue
                        try:
                            t = datetime.fromisoformat(
                                start_str.replace("Z", "+00:00")
                            )
                            # both timezone-aware → no offset bug
                            delta_min = (t - now_aware).total_seconds() / 60.0
                        except Exception as ex:
                            log(f"calendar alert parse error: {ex}")
                            continue
                        if -1 < delta_min <= 16:
                            title = e.get("summary", "an event")
                            mins = max(1, int(round(delta_min)))
                            speak(f"Reminder, {config.OWNER_TITLE}. "
                                  f"{title} starts in {mins} minute"
                                  f"{'s' if mins != 1 else ''}.")
                            log(f"calendar alert fired: {title} in {mins} min")
                            STATE["announced_events"].add(eid)
            except Exception as e:
                log(f"calendar alert loop error: {e}")
            time.sleep(60)
    threading.Thread(target=_calendar_alert_loop, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", config.PORT), Handler)
    print(f"JARVIS server online -> http://localhost:{config.PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down JARVIS server.")

if __name__ == "__main__":
    main()
