# J.A.R.V.I.S.
### *Just A Rather Very Intelligent System*

![Python 3.11+](https://img.shields.io/badge/python-3.11+-white?style=flat-square&labelColor=black)
![License MIT](https://img.shields.io/badge/license-MIT-00ff80?style=flat-square&labelColor=black)
![Platform Windows](https://img.shields.io/badge/platform-Windows-ff0080?style=flat-square&labelColor=black)
![Voice AI](https://img.shields.io/badge/voice-AI%20Assistant-ff8800?style=flat-square&labelColor=black)

A Windows-native, voice-first AI personal assistant inspired by the JARVIS from Iron Man — built from scratch in Python and a single HTML file.

Lives quietly in the background. Wakes on **"Hey JARVIS"**. Speaks in a neural British voice. Manages your day, runs your code, hacks your hashes, and reads your calendar — all through one Iron Man–style HUD.

> Built it for myself. Sharing because I'd want to see it if someone else built it.

---

## What it can do

### Voice & Brain
- 🎙 **Always-on wake word** — "Hey JARVIS" from anywhere; works even when the browser tab is closed
- 🧠 **Groq-powered** — `llama-3.3-70b-versatile` for thinking, `llama-4-scout` for vision
- 🗣 **Neural TTS** — Microsoft edge-tts `en-GB-RyanNeural`
- 🛑 **"Stop" command** — cuts speech instantly

### Personal Assistant
- 📅 **Google Calendar** — speaks today + tomorrow's events on every boot; warns 15 min before each meeting
- 📬 **Gmail Primary** — reads important unread; filters out Promotions, Social, Updates, Forums, Spam
- ✅ **Tasks + reminders** — natural-language "remind me to X at 5 PM"
- 📝 **Notes + journal** — `#tags` parsed; "notes from yesterday", "search notes for X"
- 🔐 **Password vault** — DPAPI-encrypted (Windows user-locked, no master password)
- 💬 **WhatsApp messaging** — "send a WhatsApp to Dev saying I'll be late"
- 🎵 **Spotify control** — "play lo-fi", "next song", "pause" (auto-launches Spotify if not running)
- 🎯 **Workflow modes** — "study mode", "gaming mode", "CTF mode" trigger multi-step action chains

### Cybersecurity
- 🔓 **Hashes** — identify, generate (MD5/SHA/NTLM/MD4), dictionary-crack
- 🔄 **Encode/decode** — base64, hex, URL, rot13, morse, binary
- 🐛 **CVE intel** — `lookup CVE-2024-3094` (NVD), "recent critical CVEs"
- 🌐 **Subdomain enumeration** — crt.sh + hackertarget fallback
- 🐙 **GitHub dorking** — pre-baked search URLs for AWS keys, .env files, SSH keys
- 💥 **Reverse shell payloads** — 10 languages (Bash, Python, PowerShell, Perl, Ruby, …)
- 🔍 **Port scan, DNS, HTTP headers, ping** — 42-port TCP probe
- 📡 **WiFi password recovery** — own networks via `netsh`
- 👁 **Screen vision** — Groq vision analyzes screenshots ("look at my screen and solve this")

### Drag, Drop, Done
- 📎 **Click 📎, drag-and-drop, or paste Ctrl+V** to attach images / code / text
- Images go to Groq vision for analysis
- Text/code files are appended to your prompt

### Code Engine
- 💻 **"Write and run a python script that scans port 80 on 10 IPs"** — generates, saves, executes
- Python, PowerShell, Batch, Node, HTML

### Proactive Alerts
- 🔋 Battery (<20% / <10% warnings)
- 💾 RAM (>90% pressure)
- 🌡 CPU (sustained >95%)
- All speak unprompted with sensible cooldowns (8–25 min)

### The HUD
- Pure black background with neon accent that shifts hue per state (white → magenta → orange → green)
- Real-time FFT frequency bars on the orb, driven by your live mic input
- Live CPU/RAM/disk/network/power graphs, scrolling telemetry
- Code blocks with one-click COPY button
- Typewriter animation on JARVIS replies
- Animated grid background, drifting scan beam, wake-flash on activation

---

## Quick Start (5 minutes)

### Requirements
- Windows 10 or 11
- Python 3.11 ([download here](https://www.python.org/downloads/release/python-3119/))
- A microphone
- A free [Groq API key](https://console.groq.com) (sign up with Google)

### 1. Clone the repo
```bat
git clone https://github.com/Maher-Bhatt/Jarvis.git C:\Jarvis
cd C:\Jarvis
```

### 2. Create your config
```bat
copy config.example.py config.py
notepad config.py
```

In `config.py`, paste your Groq API key:
```python
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxxxxxxx"
```

Also set:
```python
OWNER_NAME    = "YourName"
OWNER_TITLE   = "Sir"        # what JARVIS should call you
OWNER_CITY    = "YourCity"   # for weather
```

### 3. Install dependencies
Double-click **`INSTALL.bat`** — or run:
```bat
py -3.11 -m pip install -r requirements.txt
```

If `pyaudio` fails to build (rare):
```bat
py -3.11 -m pip install pipwin && py -3.11 -m pipwin install pyaudio
```

### 4. Launch
Double-click **`START.bat`** — within 2 seconds you'll hear JARVIS greet you, and Chrome opens to `http://localhost:8888`.

That's it. Say **"Hey JARVIS, what time is it"** to test.

### 5. (optional) Auto-start on every Windows boot
```bat
py -3.11 launcher.py
```
This registers JARVIS under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` and drops a Startup-folder shortcut as backup. JARVIS will now launch silently every time you log in.

To undo: open `regedit`, delete `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\JARVIS_v5`.

---

## Optional integrations (set up only what you want)

### Google Calendar + Gmail
1. Go to **[console.cloud.google.com](https://console.cloud.google.com)** → Create a project
2. APIs & Services → Library → enable **Google Calendar API** and **Gmail API**
3. OAuth consent screen → External → fill basics → add your Gmail as a **test user**
4. Credentials → Create Credentials → **OAuth client ID** → **Desktop app**
5. Download the JSON → save as `data\google_credentials.json`
6. Run: `py -3.11 setup_google.py`
7. Browser opens → click your Gmail → Allow. Done. Token cached forever.

### Spotify
1. Go to **[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)** → Create app
2. **Redirect URI:** `http://127.0.0.1:8889/callback` (exact)
3. Tick **Web API**, agree to ToS, Save
4. Copy **Client ID** and **Client Secret** into `config.py`:
   ```python
   SPOTIFY_CLIENT_ID     = "..."
   SPOTIFY_CLIENT_SECRET = "..."
   ```
5. Run: `py -3.11 setup_spotify.py`
6. Browser opens → Allow.

### WhatsApp
Just open `https://web.whatsapp.com` in Chrome once and scan the QR. After that JARVIS can send messages through it.

Add contacts:
> *"Hey JARVIS, add contact Dev +919876543210"*

Send messages:
> *"Hey JARVIS, send WhatsApp to Dev saying I'll be late"*

### Hash cracking
Drop a wordlist at `data\wordlist.txt` (e.g., rockyou.txt) and JARVIS can crack hashes:
> *"Hey JARVIS, crack hash 5f4dcc3b5aa765d61d8327deb882cf99"*

---

## Voice command reference

### Music
| Say | Action |
|---|---|
| "Play lo-fi" / "Play Believer" | Spotify search + play |
| "Pause" / "Resume" | Spotify playback |
| "Next song" / "Previous song" | Skip / back |
| "What's playing" | Speaks current track |
| "Spotify volume 50" | Sets volume |

### Productivity
| Say | Action |
|---|---|
| "What's on my calendar" | Today; falls through to tomorrow if clear |
| "What's on my calendar tomorrow" | Tomorrow's events |
| "Check gmail" | Important unread (Primary inbox only) |
| "Add task X" / "Show my tasks" | Tasks |
| "Remind me to X in 10 minutes" / "at 5 PM" | Reminders |
| "Take a note Y" / "Notes from yesterday" | Notes |
| "Send WhatsApp to <name> saying Y" | WhatsApp message |
| "Save my Gmail password as hunter2" | Vault |
| "What is my Gmail password" | Speaks + displays |
| "Generate a strong password" | 20-char random |

### Cyber
| Say | Action |
|---|---|
| "MD5 of admin123" | Hashes the string |
| "Identify hash <hash>" | Guesses by length |
| "Crack hash <hash>" | Dictionary attack |
| "Lookup CVE-2024-3094" | NVD lookup |
| "Recent critical CVEs" | Last 30 days |
| "Find subdomains of paypal.com" | crt.sh + hackertarget |
| "GitHub dorks for example.com" | Search URL list |
| "Reverse shell python 10.10.14.5 4444" | Payload in code block |
| "Port scan 192.168.1.1" | Top 42 TCP ports |
| "DNS google.com" / "Headers for example.com" | Recon |
| "Base64 encode <text>" / "Decode base64 <blob>" | Codecs |
| "What's my IP" / "IP info" | Public IP + geolocation |

### System
| Say | Action |
|---|---|
| "What time is it" / "Battery" / "System info" | Local |
| "Set volume 60" / "Mute" | pycaw |
| "Take a screenshot" | Saves to Desktop |
| "Lock my PC" / "Sleep" / "Restart" / "Shutdown" | Windows |
| "Open Chrome" / "Open YouTube" | Launches |

### Workflow modes (fuzzy match handles mishearings)
| Say | What runs |
|---|---|
| "Study mode" | Opens VS Code, lo-fi playlist, lowers volume |
| "Gaming mode" | Opens Steam + Discord, kills Chrome |
| "CTF mode" | Opens VS Code, terminal, exploit-db, GTFOBins |
| "Focus mode" | Lowers volume, kills Discord |
| "Morning routine" | Opens Gmail + Calendar |
| "Shutdown routine" | Closes apps, locks PC |

### Meta
| Say | Action |
|---|---|
| "Stop" / "Shut up" | Cuts current speech |
| "Pause listener" / "Resume listener" | Frees mic for other apps |
| "Remember <fact>" / "What do you remember" | Long-term memory |

---

## Architecture

```
                ┌─────────────────────────┐
                │   index.html (the HUD)  │
                │   Canvas + JS + CSS     │
                └──────────┬──────────────┘
                           │ /api/* HTTP+JSON
                           ▼
   ┌───────────────────────┴──────────────────────────┐
   │                  server.py                       │
   │  http.server + ThreadingMixIn (stdlib only)      │
   │  - intent router (local commands)                │
   │  - background loops (alerts, calendar, reminders)│
   │  - voice TTS pipeline                            │
   └─┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬───────┘
     │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   vault gcal vision coder spotify whatsapp notes tasks
   cybertools  workflows  mail  ytdl
                           ▲
                           │ POST /api/wake|chat|stop
                           │
                ┌──────────┴──────────────┐
                │      listener.py        │
                │  SpeechRecognition+PyAudio
                │  cycles mic, fuzzy match│
                └─────────────────────────┘

   launcher.py (silent boot, registers HKCU\...\Run)
```

**Why stdlib only for the server?** No Flask, no FastAPI, no npm — JARVIS depends on Python's `http.server` + `ThreadingMixIn` and a single HTML file. Easier to audit, faster to start, no build step.

---

## Project layout

```
Jarvis/
├── server.py             ← HTTP API + intent router + bg loops
├── listener.py           ← Always-on wake word + follow-up
├── launcher.py           ← Silent boot + Windows autostart
├── config.example.py     ← Template (copy to config.py)
├── index.html            ← The HUD (canvas + vanilla JS)
├── requirements.txt
├── INSTALL.bat
├── START.bat
│
│   ── Modules ──
├── vault.py              ← DPAPI password store
├── cybertools.py         ← Hashes, codecs, network, CVE, recon, payloads
├── vision.py             ← Screenshot / image analysis via Groq vision
├── coder.py              ← Code generation + execution
├── tasks.py              ← Tasks + reminders
├── notes.py              ← Notes + full-text search
├── mail.py               ← IMAP Gmail (alt to OAuth)
├── gcal.py               ← Google Calendar + Gmail OAuth
├── spotify_mod.py        ← Spotify Web API
├── whatsapp_mod.py       ← WhatsApp via pywhatkit
├── workflows.py          ← Multi-step modes
├── ytdl.py               ← yt-dlp wrapper
│
└── setup_google.py / setup_spotify.py    ← One-time OAuth
```

`data/` is created automatically on first run and holds your local state (memory, tasks, vault, tokens). It's `.gitignore`d — your secrets never leak.

---

## Tech stack

| Layer | Tech |
|---|---|
| Server | Python 3.11 stdlib (`http.server` + `ThreadingMixIn`) |
| LLM | Groq API (llama-3.3-70b-versatile / llama-4-scout vision) |
| TTS | Microsoft edge-tts + pygame mixer |
| STT | SpeechRecognition + Google STT |
| Calendar/Mail | google-api-python-client + google-auth-oauthlib |
| Music | spotipy |
| Messaging | pywhatkit |
| Vault | pywin32 / `win32crypt` (DPAPI) |
| System | psutil, pycaw, pillow |
| Recon | crt.sh, NVD API, hackertarget.com |
| Frontend | Vanilla JS + Canvas2D, single `index.html` |

---

## Troubleshooting

**JARVIS doesn't greet me on launch.** Make sure your speakers are unmuted and `START.bat` shows no errors. If pygame fails, reinstall: `pip install --force-reinstall pygame`.

**Wake word "Hey JARVIS" doesn't work.** Google STT needs internet. Check that `data/listener.log` says "listening". Also: Windows privacy → Microphone → make sure desktop apps can use it.

**Spotify says "no active device".** Open Spotify (desktop or web player or phone) and hit play on any song for 2 seconds. JARVIS will auto-launch Spotify if it's not running, but Spotify still needs to register a device first.

**Server unreachable in browser.** Check Task Manager for `pythonw.exe` processes. If none, run `START.bat` again. The Windows Firewall may prompt the first time — click Allow.

**Groq quota exceeded.** The free tier is 6,000 requests/day on the 70B model — should be plenty. If exceeded, JARVIS falls back to Ollama (if you have it installed) or just says it's unavailable.

---

## License

MIT — see [LICENSE](LICENSE). Cybersecurity tooling is for **authorized testing only**.

---

## Acknowledgments

- The vision and the name come from Marvel's Tony Stark. JARVIS from the movies = the inspiration.
- [Groq](https://groq.com) for absurdly fast LLaMA inference
- [edge-tts](https://github.com/rany2/edge-tts) for the neural Ryan voice
- [crt.sh](https://crt.sh) and [NVD](https://nvd.nist.gov) for free security data

---

> *"Sometimes you gotta run before you can walk."* — Tony Stark

Built by **[Maher Hardik Bhatt](https://github.com/Maher-Bhatt)** · If you build something cool on top, tag me.
