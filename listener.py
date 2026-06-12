"""
KALKI v5 — Wake Word Listener
Always-on system mic. Captures wake word, then the follow-up command.
NEVER calls AI itself — POSTs to /api/wake (greeting/Chrome) or /api/chat
(voice command). The browser tab is purely a display.
"""

import os
import re
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

# Common Google STT mishearings of "Kalki".
# NOTE: only Kalki-like tokens that are whole words (matched with \b), so they
# never fire inside ordinary speech. Avoid bare substrings like "cal".
WAKE_FUZZY = ["kalki", "kalka", "kalkee", "kalky", "kal ki",
              "calki", "kalgi", "khalki", "hey kalki", "ok kalki"]


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


def _word_match(needle, haystack):
    """Whole-word match so 'kalki' never fires inside 'atomic'/'custom'."""
    return re.search(r"\b" + re.escape(needle) + r"\b", haystack) is not None


def contains_wake(phrase):
    low = phrase.lower()
    return any(_word_match(w, low) for w in WAKE_WORDS + WAKE_FUZZY)


def contains_stop(phrase):
    low = phrase.lower().strip()
    if low in STOP_WORDS:
        return True
    return any(low == s or low.startswith(s + " ") for s in STOP_WORDS)


def extract_inline(phrase):
    """Return text after the EARLIEST whole-word wake match."""
    low = phrase.lower()
    best = None
    for w in WAKE_WORDS + WAKE_FUZZY:
        m = re.search(r"\b" + re.escape(w) + r"\b", low)
        if m and (best is None or m.start() < best):
            best = m.start()
            end = m.end()
    if best is not None:
        return phrase[end:].strip(" ,.:;-?!")
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
    """Block while KALKI is speaking so its own voice doesn't get transcribed."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if not is_speaking():
            time.sleep(0.12)
            return
        time.sleep(0.18)


def pick_input_device():
    """Choose the STT mic. Avoids the Bluetooth headset so it stays in
    high-quality A2DP output mode instead of dropping to muffled HFP/HSP
    every time the wake-word listener opens the mic.

    Order: explicit config.STT_INPUT_DEVICE substring  ->  a built-in/internal
    mic  ->  any non-Bluetooth input  ->  system default (None).
    """
    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as e:
        log(f"could not list mics: {e}")
        return None
    if not names:
        return None

    want = (getattr(config, "STT_INPUT_DEVICE", "") or "").strip().lower()
    avoid_bt = getattr(config, "STT_AVOID_BLUETOOTH", True)

    # Bluetooth / hands-free profiles to avoid (they force muffled HFP).
    BT_HINTS = ("bluetooth", "hands-free", "handsfree", "headset", "airpods",
                "wireless", "hfp", "hsp", "bt audio")
    # Mappers / outputs / loopbacks that follow the system default — skip so we
    # don't accidentally route through the BT headset again.
    SKIP_HINTS = BT_HINTS + ("sound mapper", "primary sound", "stereo mix",
                             "what u hear", "what you hear", "wave speaker",
                             "mirroring", "speaker", "output")
    # Real built-in microphones.
    GOOD_HINTS = ("microphone array", "built-in", "internal", "realtek")

    # 1) explicit choice from config
    if want:
        for i, n in enumerate(names):
            if n and want in n.lower():
                log(f"STT mic (config match): [{i}] {n}")
                return i

    # 2) a physical built-in mic that is NOT bluetooth / not a mapper
    for i, n in enumerate(names):
        low = (n or "").lower()
        if avoid_bt and any(b in low for b in SKIP_HINTS):
            continue
        if any(g in low for g in GOOD_HINTS):
            log(f"STT mic (built-in): [{i}] {n}")
            return i

    # 3) any input that names itself a microphone and isn't bluetooth
    if avoid_bt:
        for i, n in enumerate(names):
            low = (n or "").lower()
            if "mic" in low and not any(b in low for b in SKIP_HINTS):
                log(f"STT mic (non-BT mic): [{i}] {n}")
                return i

    log("STT mic: using system default")
    return None


VOSK_MODEL_PATH = os.path.join(BASE_DIR,
    getattr(config, "VOSK_MODEL_PATH", os.path.join("data", "vosk-model")))


def vosk_available():
    # Vosk's small offline model can't recognize the out-of-vocabulary name
    # "kalki" — it transcribes garbage and the wake word never fires. So Vosk
    # is OPT-IN only (STT_ENGINE="vosk"); "auto"/"google" use reliable cloud STT.
    if (getattr(config, "STT_ENGINE", "google") or "google").lower() != "vosk":
        return False
    try:
        import vosk  # noqa
    except Exception:
        return False
    return os.path.isdir(VOSK_MODEL_PATH)


def run_vosk(dev_index):
    """Offline wake-word loop using Vosk — no network, low CPU, low heat."""
    import json as _json
    import vosk
    import pyaudio

    vosk.SetLogLevel(-1)
    try:
        model = vosk.Model(VOSK_MODEL_PATH)
    except Exception as e:
        log(f"vosk model load failed: {e}; falling back to Google")
        return False

    RATE, CHUNK = 16000, 4000
    pa = pyaudio.PyAudio()

    def open_stream():
        kw = dict(format=pyaudio.paInt16, channels=1, rate=RATE,
                  input=True, frames_per_buffer=CHUNK)
        if dev_index is not None:
            kw["input_device_index"] = dev_index
        return pa.open(**kw)

    try:
        stream = open_stream()
    except Exception as e:
        log(f"vosk stream open failed: {e}; falling back to Google")
        pa.terminate()
        return False

    rec = vosk.KaldiRecognizer(model, RATE)
    log(f"listening via VOSK (offline). wake words: {WAKE_WORDS}")

    def next_final(timeout):
        """Read until a non-empty final result or timeout. Returns text."""
        end = time.time() + timeout
        while time.time() < end:
            data = stream.read(CHUNK, exception_on_overflow=False)
            if rec.AcceptWaveform(data):
                txt = _json.loads(rec.Result()).get("text", "").strip()
                if txt:
                    return txt
        return ""

    paused_logged = 0
    while True:
        try:
            # Release the mic while paused so other apps can use it.
            if is_paused():
                try:
                    stream.stop_stream()
                except Exception:
                    pass
                if time.time() > paused_logged:
                    log("listener paused — mic released")
                    paused_logged = time.time() + 30
                time.sleep(1.5)
                continue
            if not stream.is_active():
                try:
                    stream.start_stream()
                except Exception:
                    stream = open_stream(); rec = vosk.KaldiRecognizer(model, RATE)

            data = stream.read(CHUNK, exception_on_overflow=False)

            # Ignore audio while KALKI is speaking (don't transcribe own voice).
            if is_speaking():
                rec.Reset() if hasattr(rec, "Reset") else None
                continue

            if not rec.AcceptWaveform(data):
                continue
            phrase = _json.loads(rec.Result()).get("text", "").strip()
            if not phrase:
                continue
            log(f"heard: {phrase}")

            if contains_stop(phrase):
                post_stop(); continue
            if not contains_wake(phrase):
                continue

            inline = extract_inline(phrase)
            if inline:
                post_chat_voice(inline)
                wait_until_silent(max_wait=8.0)
                time.sleep(0.3)
                continue

            # wake only → greet, then capture the follow-up command
            post_wake("")
            wait_until_silent(max_wait=4.0)
            follow = next_final(timeout=6)
            if not follow:
                log("no follow-up command within window")
                continue
            log(f"follow-up: {follow}")
            if contains_stop(follow):
                post_stop(); continue
            post_chat_voice(follow)
            wait_until_silent(max_wait=12.0)
            time.sleep(0.3)

        except KeyboardInterrupt:
            log("listener stopped by user")
            return True
        except Exception as e:
            log(f"vosk loop error: {e}")
            time.sleep(1)


def main():
    log("listener starting")
    if not wait_for_server():
        log("server never came up; listener exiting")
        return
    log("server reachable, opening mic")

    dev_index = pick_input_device()

    # Prefer offline Vosk (no network, less heat). Fall back to Google STT.
    if vosk_available():
        try:
            if run_vosk(dev_index):
                return
        except Exception as e:
            log(f"vosk engine crashed: {e}; using Google STT")
        log("falling back to Google STT")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.7
    try:
        mic = sr.Microphone(device_index=dev_index)
    except Exception as e:
        log(f"mic open failed on device {dev_index}: {e}; falling back to default")
        try:
            mic = sr.Microphone()
        except Exception as e2:
            log(f"default mic open failed: {e2}")
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
