# ──────────────────────────────────────────────────────────────
# JARVIS — Configuration Template
# Copy this file to config.py and fill in your own keys / settings.
# config.py is gitignored so your secrets never get committed.
# ──────────────────────────────────────────────────────────────

# ── GROQ AI (required for the LLM brain) ────────────────────
# Get a free key at https://console.groq.com
GROQ_API_KEY = "PASTE_YOUR_GROQ_KEY_HERE"

# ── OWNER ───────────────────────────────────────────────────
OWNER_NAME    = "YourName"
OWNER_TITLE   = "Sir"          # or whatever JARVIS should call you
OWNER_CITY    = "YourCity"
OWNER_STATE   = "YourState"
OWNER_COUNTRY = "YourCountry"

# ── VOICE (edge-tts) ────────────────────────────────────────
TTS_VOICE  = "en-GB-RyanNeural"   # try en-US-GuyNeural, en-AU-WilliamNeural
TTS_RATE   = "-5%"
TTS_VOLUME = "+10%"

# ── SERVER ──────────────────────────────────────────────────
PORT    = 8888
BROWSER = "chrome"

# ── AI ──────────────────────────────────────────────────────
GROQ_MODEL  = "llama-3.3-70b-versatile"   # smart default
OLLAMA_URL  = "http://localhost:11434"     # used only if Groq fails
MAX_HISTORY = 20

# ── WAKE WORDS ──────────────────────────────────────────────
WAKE_WORDS = ["hey jarvis", "jarvis", "hey sir", "ok jarvis"]

# ── STARTUP ─────────────────────────────────────────────────
AUTO_START           = True
GREET_ON_START       = True
OPEN_BROWSER_ON_WAKE = True

# ── MEMORY / HISTORY (paths inside data/) ───────────────────
MEMORY_FILE  = "data/memory.json"
HISTORY_FILE = "data/history.json"

# ── EMAIL (optional, IMAP route — Gmail App Password) ───────
# OAuth Gmail is set up separately via setup_google.py.
# Leave blank to disable IMAP.
EMAIL_ADDRESS      = ""
EMAIL_APP_PASSWORD = ""
IMAP_SERVER        = "imap.gmail.com"
IMAP_PORT          = 993

# ── REMINDER LOOP ───────────────────────────────────────────
REMINDER_POLL_SEC = 30

# ── SPOTIFY (optional) ──────────────────────────────────────
# Create app at https://developer.spotify.com/dashboard
# Redirect URI MUST be: http://127.0.0.1:8889/callback
SPOTIFY_CLIENT_ID     = ""
SPOTIFY_CLIENT_SECRET = ""
SPOTIFY_REDIRECT_URI  = "http://127.0.0.1:8889/callback"

# ── PROACTIVE ALERTS ────────────────────────────────────────
ALERTS_ENABLED       = True
BATTERY_LOW_PCT      = 20
BATTERY_CRITICAL_PCT = 10
RAM_HIGH_PCT         = 90
CPU_HIGH_PCT         = 95
