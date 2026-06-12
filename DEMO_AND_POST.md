# KALKI — LinkedIn / GitHub Launch Pack

Three things for shipping today:
1. **LinkedIn post draft** (long + short versions)
2. **Demo recording script** (60–90 seconds, voice-driven)
3. **GitHub repo checklist** before you push

---

## 1. LinkedIn post — LONG version (1,300 chars)

> I built my own JARVIS. I called him Kalki.
>
> A few weeks ago I asked myself: what would it take to build the assistant from Iron Man — not a chatbot wrapper, an actual operating-system-level personal AI that runs silently on my laptop, wakes when I speak, sees my screen, and does my work.
>
> Five thousand lines of Python and one HTML file later, here it is.
>
> 🎙 Always-on wake word ("Hey Kalki"). Neural American voice (en-US-GuyNeural — warm, casual, like a mate). Listens from any room, works when my browser is closed.
>
> 🧠 Groq LLaMA-3.3-70B brain with web search injection. Vision via LLaMA-4-Scout — I drag any image into the window and KALKI solves CTF challenges, reads code screenshots, explains error dialogs.
>
> 📅 Reads my Google Calendar + Gmail (Primary inbox only — promos and social filtered). Reminds me 15 minutes before every meeting, unprompted.
>
> 🔐 Cyber toolkit: hash identify + crack, port scan, DNS, HTTP recon, CVE lookup (NVD live), subdomain enumeration (crt.sh), GitHub dorking, reverse-shell payload generation in 10 languages. All voice-driven.
>
> 🎵 Spotify control by voice. WhatsApp messages. Task & reminder management. DPAPI-encrypted password vault. Workflow modes that chain multi-step actions ("study mode", "CTF mode", "gaming mode").
>
> All wrapped in an Iron Man arc-reactor HUD that genuinely reacts to your voice — 72 frequency bars driven by real-time FFT, state-shifting accent colors, copyable code blocks.
>
> Stack: Python stdlib HTTP server (no Flask, no npm), edge-tts for the neural voice, Groq for inference, vanilla Canvas for the UI. Auto-starts silently on every Windows boot.
>
> Code's on GitHub. Built for myself first — sharing because I'd want to see it if someone else built it.
>
> #cybersecurity #AI #python #SideProject #ironMan #KALKI

---

## 1b. LinkedIn post — SHORT version (under 500 chars, snappier)

> I built my own JARVIS. Called him Kalki.
>
> Voice-activated personal AI for Windows. Wakes on "Hey Kalki", speaks in a warm American voice, controls Spotify, reads my Gmail + Calendar, runs hash cracking and CVE lookups, drag-drops images for vision analysis, generates reverse-shell payloads.
>
> Iron Man arc-reactor HUD reacts to my actual voice via FFT. Auto-starts on boot.
>
> 5,000 lines of Python. No Flask. Single HTML file.
>
> Built it for myself. Code on GitHub:
>
> #ironman #AI #cybersecurity

---

## 2. 60–90 second Demo Script (for screen recording)

**Setup:** KALKI already running silently. Chrome closed. Spotify NOT open. Phone with WhatsApp logged in.

### Scene 1 — Wake up (0:00–0:10)
- Sit in front of laptop. Quietly: **"Hey KALKI."**
- Chrome opens to localhost:8888. Iron Man HUD loads with boot terminal sequence.
- KALKI speaks: *"Afternoon, Sir. Sunday. Sunny 32 in Kalol. You have 2 events on the calendar today."*
- Show the right HUD panel: today's calendar + unread mail count visible

### Scene 2 — Calendar + tasks (0:10–0:20)
- **"Hey KALKI, what's on my calendar tomorrow?"**
- KALKI speaks real events from your Google Calendar
- **"Hey KALKI, add task ship KALKI to GitHub by tonight"**
- KALKI: *"Got it."*

### Scene 3 — Cyber (0:20–0:40)
- **"Hey KALKI, MD5 of admin123"**
- KALKI speaks the hash. UI shows it.
- **"Hey KALKI, identify hash 5f4dcc3b5aa765d61d8327deb882cf99"**
- *"Possible types: MD5, NTLM, MD4."*
- **"Hey KALKI, reverse shell python 10.10.14.5 4444"**
- UI shows a code block with the payload + a COPY button. Click it.
- **"Hey KALKI, find subdomains of paypal.com"**
- KALKI reads the top 6 back.

### Scene 4 — Vision (0:40–0:55)
- Switch to a CTF challenge tab (or any screenshot with a question).
- Drag the image onto the KALKI window.
- DROP TO ATTACH overlay appears. Release.
- Type **"solve this"** and hit Enter.
- Groq vision answers in the readout.

### Scene 5 — Spotify (0:55–1:10)
- **"Hey KALKI, play lo-fi"**
- Spotify desktop auto-launches.
- *"Playing lo-fi study beats."*
- Right HUD now shows ♫ track name.

### Scene 6 — Outro (1:10–1:25)
- **"Hey KALKI, ctf mode."**
- VS Code, Windows Terminal, exploit-db, GTFOBins all open.
- KALKI: *"CTF mode active, Sir. Code, terminal, and references ready."*
- **"Hey KALKI, take a note KALKI demo complete."**
- KALKI: *"Filed away."*
- Hold for 2 seconds on the HUD. Cut.

**Recording tip:** Use **OBS Studio** with audio capture from system + mic, so viewers hear KALKI speak AND see the HUD react in real time.

---

## 3. GitHub repo checklist BEFORE you push

```
[ ] README.md          ✓ exists
[ ] LICENSE            ✓ exists
[ ] .gitignore         ✓ exists
[ ] config.example.py  ✓ exists (real config.py is gitignored)
[ ] requirements.txt   ✓ exists
```

**Run this once before `git push`** to make absolutely sure no secrets leak:

```bat
:: Verify gitignore is doing its job
git status
:: Should NOT show: config.py, data/google_token.pickle, data/spotify_token.json,
::                  data/google_credentials.json, data/vault.json, data/contacts.json

:: If any of those show up, fix .gitignore first.
```

**Initial commit:**

```bat
cd C:\Kalki
git init
git add .
git status                 :: ← double-check nothing sensitive
git commit -m "Initial commit — KALKI v5 (Iron Man personal AI)"
git branch -M main
git remote add origin https://github.com/<your-username>/kalki.git
git push -u origin main
```

**After push** — make the repo public, add the following on GitHub:
- **Repo description** (top of the page): *"Voice-activated Iron Man-style AI assistant for Windows — wake word, vision, calendar, Spotify, cybersec toolkit."*
- **Topics** (settings → topics): `kalki`, `ai-assistant`, `voice-assistant`, `cybersecurity`, `python`, `groq`, `iron-man`, `pentesting`
- **README badges** (optional polish — at the top of README.md):

```markdown
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Platform Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)
```

- A **screenshot of the HUD** in the README — take it after refreshing the KALKI tab so the new accent-reactive theme shows. Crop just the HUD (not desktop). Save as `screenshot.png` in repo root, then add `![KALKI HUD](screenshot.png)` near the top of the README.
- A **short GIF** of the demo (use [ScreenToGif](https://www.screentogif.com)) — way better for LinkedIn engagement than a screenshot.

---

## Bonus — the post format for the LinkedIn carousel (10 slides)

If you do the carousel post (LinkedIn favors carousels — way higher reach than single posts):

| Slide | Content |
|---|---|
| 1 | Title slide: "I built KALKI." + arc reactor image |
| 2 | "Why" — one paragraph on the inspiration |
| 3 | Screenshot of the HUD with labels |
| 4 | Voice command demo — "Hey KALKI" sequence |
| 5 | Cyber toolkit screenshot — CVE lookup + reverse shell |
| 6 | Vision demo — drag-drop CTF image |
| 7 | Architecture diagram |
| 8 | Tech stack pills |
| 9 | "Stack: Python stdlib · Groq · edge-tts · vanilla Canvas" |
| 10 | "Code on GitHub →" with link |

Carousels typically get 3–5x more views than text-only posts for technical content.

---

Now go ship it.
