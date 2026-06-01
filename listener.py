"""
JARVIS v5 — Wake Word Listener
Always-on system mic. Captures wake word, then the follow-up command.
NEVER calls AI itself — POSTs to /api/wake (greeting/Chrome) or /api/chat
(voice command). The browser tab is purely a display.
"""

import os
import sys
import time
import json
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import config

LOG_PATH = os.path.join(BASE_DIR, "data", "listener.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


try:
    import speech_recognition as sr
except Exception as e:
    log(f"speech_recognition import failed: {e}")
    sys.exit(1)


SERVER     = f"http://localhost:{config.PORT}"
STOP_WORDS = ["stop", "stop talking", "shut up", "be quiet", "silence",
              "quiet", "shush", "cancel"]
WAKE_WORDS = [w.lower() for w in config.WAKE_WORDS]

# Common Google STT mishearings of "Jarvis"
WAKE_FUZZY = ["jarvis", "javis", "jervis", "service", "javed",
              "jarves", "jarviss", "jervice", "darvis", "harvis",
              "yarvis", "hey google"]


def _post(endpoint, body=None, timeout=15):
    try:
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            f"{SERVER}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        log(f"POST {endpoint} failed: {e}")
        return None


def post_wake(cmd_text=""):
    log(f"WAKE -> '{cmd_text}'")
    _post("/api/wake", {"cmd": cmd_text or ""})


def post_chat_voice(text):
    """Send a voice-captured command. source=voice so UI renders it."""
    log(f"CHAT(voice) -> '{text}'")
    _post(
        "/api/chat",
        {"messages": [{"role": "user", "content": text}], "source": "voice"},
        timeout=45,
    )


def post_stop():
    log("STOP")
    _post("/api/stop")


def _status():
    try:
        with urllib.request.urlopen(f"{SERVER}/api/status", timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def is_speaking():
    return _status().get("speaking", False)


def is_paused():
    return _status().get("listenerPaused", False)


def server_alive():
    try:
        urllib.request.urlopen(f"{SERVER}/api/health", timeout=2).read()
        return True
    except Exception:
        return False


def wait_for_server():
    for _ in range(60):
        if server_alive():
            return True
        time.sleep(1)
    return server_alive()


def contains_wake(phrase):
    low = phrase.lower()
    if any(w in low for w in WAKE_WORDS):
        return True
    return any(f in low for f in WAKE_FUZZY)


def contains_stop(phrase):
    low = phrase.lower().strip()
    if low in STOP_WORDS:
        return True
    return any(low == s or low.startswith(s + " ") for s in STOP_WORDS)


def extract_inline(phrase):
    """Return text after the wake phrase."""
    low = phrase.lower()
    for w in WAKE_WORDS + WAKE_FUZZY:
        i = low.find(w)
        if i >= 0:
            return phrase[i + len(w):].strip(" ,.:;-?!")
    return ""


def listen_once(recognizer, mic, phrase_time_limit=4, timeout=None):
    try:
        with mic as source:
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        return recognizer.recognize_google(audio)
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        log(f"Google STT error: {e}")
        time.sleep(1)
        return None


def wait_until_silent(max_wait=4.0):
    """Block while JARVIS is speaking so its own voice doesn't get transcribed."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if not is_speaking():
            time.sleep(0.12)
            return
        time.sleep(0.18)


def main():
    log("listener starting")
    if not wait_for_server():
        log("server never came up; listener exiting")
        return
    log("server reachable, opening mic")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.7

    try:
        mic = sr.Microphone()
    except Exception as e:
        log(f"mic open failed: {e}")
        return

    with mic as source:
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1.2)
        except Exception as e:
            log(f"ambient calibration failed: {e}")

    log(f"listening (wake words: {WAKE_WORDS})")
    pause_status_log_at = 0

    while True:
        try:
            # ── Yield the mic when paused (so other apps can use it) ──
            if is_paused():
                if time.time() > pause_status_log_at:
                    log("listener paused — mic released")
                    pause_status_log_at = time.time() + 30
                time.sleep(2.0)
                continue

            # ── Idle listen: short cycling windows so the mic releases
            #    briefly between waits, letting other apps share it. ──
            phrase = listen_once(
                recognizer, mic,
                phrase_time_limit=4, timeout=6,
            )
            if not phrase:
                # Brief breather so other apps can grab the mic in shared mode
                time.sleep(0.15)
                continue
            log(f"heard: {phrase}")

            if contains_stop(phrase):
                post_stop()
                continue

            if not contains_wake(phrase):
                continue

            inline = extract_inline(phrase)

            if inline:
                # Wake + command in one breath: ship it
                post_chat_voice(inline)
                wait_until_silent(max_wait=8.0)
                time.sleep(0.4)
                continue

            # ── Wake only → server speaks "Yes, Sir?" then we capture follow-up ──
            post_wake("")
            wait_until_silent(max_wait=4.0)

            follow = listen_once(
                recognizer, mic,
                phrase_time_limit=10, timeout=6,
            )
            if not follow:
                log("no follow-up command within window")
                continue

            log(f"follow-up: {follow}")
            if contains_stop(follow):
                post_stop()
                continue

            post_chat_voice(follow)
            wait_until_silent(max_wait=12.0)
            time.sleep(0.4)

        except KeyboardInterrupt:
            log("listener stopped by user")
            return
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
