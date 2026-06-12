# ──────────────────────────────────────────────────────────────
# KALKI — Configuration Template
# Copy this file to config.py and fill in your own keys / settings.
# config.py is gitignored so your secrets never get committed.
# ──────────────────────────────────────────────────────────────

# ── GROQ AI (required for the LLM brain) ────────────────────
# Get a free key at https://console.groq.com
GROQ_API_KEY = "PASTE_YOUR_GROQ_KEY_HERE"

# ── OWNER ───────────────────────────────────────────────────
OWNER_NAME    = "YourName"
OWNER_TITLE   = "Sir"          # or whatever KALKI should call you
OWNER_CITY    = "YourCity"
OWNER_STATE   = "YourState"
OWNER_COUNTRY = "YourCountry"

# ── VOICE (edge-tts) ────────────────────────────────────────
# Most human / least robotic: en-US-BrianMultilingualNeural (default),
#   en-US-AndrewMultilingualNeural — newest neural models, very natural.
# British butler (JARVIS vibe): en-GB-RyanNeural, en-GB-ThomasNeural
# Other US males: en-US-GuyNeural, en-US-TonyNeural (deep)
TTS_VOICE  = "en-US-BrianMultilingualNeural"
TTS_RATE   = "+0%"                # +N% faster, -N% slower
TTS_PITCH  = "+0Hz"               # +/-N Hz to shift pitch
TTS_VOLUME = "+0%"

# ── SERVER ──────────────────────────────────────────────────
PORT    = 8888
BROWSER = "chrome"

# ── AI ──────────────────────────────────────────────────────
GROQ_MODEL  = "llama-3.3-70b-versatile"   # smart default
OLLAMA_URL  = "http://localhost:11434"     # used only if Groq fails
MAX_HISTORY = 20

# ── WAKE WORDS ──────────────────────────────────────────────
WAKE_WORDS = ["hey kalki", "kalki", "hey sir", "ok kalki"]

# ── MIC / STT INPUT ─────────────────────────────────────────
# Keep Bluetooth headphones in high-quality A2DP: the listener avoids the
# BT mic (which forces muffled HFP mode) and uses the built-in mic instead.
STT_AVOID_BLUETOOTH = True
STT_INPUT_DEVICE    = ""   # name substring to force a device, else auto
STT_ENGINE          = "auto"          # auto | vosk (offline) | google (cloud)
VOSK_MODEL_PATH     = "data/vosk-model"

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
