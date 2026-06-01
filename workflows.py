"""
JARVIS workflow modes — single-phrase action chains.
"""

import os
import subprocess
import webbrowser


# Action chain definitions. Each step is a (action, *args) tuple.
# Actions are interpreted by `run_mode` below.
MODES = {
    "study mode": [
        ("open_app", "code"),
        ("open_url", "https://open.spotify.com/playlist/37i9dQZF1DWWQRwui0ExPn"),
        ("set_volume", 40),
        ("speak", "Study mode engaged, Sir. Lo-fi playing, Code is open. Focus."),
    ],
    "gaming mode": [
        ("open_app", "steam"),
        ("open_app", "discord"),
        ("set_volume", 70),
        ("kill_app", "chrome"),
        ("speak", "Gaming rig ready, Sir. Background apps cleared."),
    ],
    "shutdown routine": [
        ("kill_app", "chrome"),
        ("kill_app", "code"),
        ("kill_app", "spotify"),
        ("kill_app", "discord"),
        ("lock_pc",),
        ("speak", "Closing things down, Sir. Locking the PC."),
    ],
    "focus mode": [
        ("set_volume", 25),
        ("kill_app", "discord"),
        ("speak", "Focus mode. Distractions silenced."),
    ],
    "morning routine": [
        ("open_url", "https://mail.google.com"),
        ("open_url", "https://calendar.google.com"),
        ("speak", "Good morning, Sir. Calendar and Gmail open."),
    ],
    "ctf mode": [
        ("open_app", "code"),
        ("open_app", "terminal"),
        ("open_url", "https://www.exploit-db.com"),
        ("open_url", "https://gtfobins.github.io"),
        ("speak", "CTF mode active, Sir. Code, terminal, and references ready."),
    ],
}


APP_MAP = {
    "chrome": "chrome.exe",
    "code": "code.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "terminal": "wt.exe",
    "edge": "msedge.exe",
}


def list_modes():
    return list(MODES.keys())


# Common Google STT mishearings + casual aliases per mode.
# Lowercase. Checked as substring.
MODE_ALIASES = {
    "study mode":       ["study", "studying", "study session", "study time",
                         "focus session", "let's study"],
    "gaming mode":      ["gaming", "game mode", "let's game", "play games",
                         "gaming time"],
    "shutdown routine": ["shutdown", "shut down", "wind down", "shutting down",
                         "shutdown mode"],
    "focus mode":       ["focus", "focused mode", "concentrate", "deep work"],
    "morning routine":  ["morning", "morning mode", "wake up"],
    "ctf mode":         ["ctf", "city of mode", "see tee eff", "city of",
                         "capture the flag", "cyber mode", "hacking mode",
                         "set up mode", "ceftc mode", "ceeteeef",
                         "ctf time", "ctf session"],
}


def find_mode(text):
    """Match a mode from natural-language text. Handles mishearings."""
    if not text:
        return None
    t = text.lower().strip()
    # 1) Exact mode name appears in text
    for mode in MODES.keys():
        if mode in t:
            return mode
    # 2) All words from the mode name appear (order-free)
    for mode in MODES.keys():
        words = mode.split()
        if all(w in t for w in words):
            return mode
    # 3) Aliases (covers STT mishearings)
    for mode, aliases in MODE_ALIASES.items():
        for a in aliases:
            if a in t:
                return mode
    return None


def run_mode(mode_name, *, speak_fn=None, set_volume_fn=None,
             open_url_fn=None, lock_fn=None):
    """Execute a workflow. Pass in callable hooks from the server."""
    mode_name = mode_name.lower().strip()
    if mode_name not in MODES:
        return {"ok": False, "error": f"Unknown mode: {mode_name}",
                "available": list(MODES.keys())}

    actions = MODES[mode_name]
    log = []
    for step in actions:
        action = step[0]
        args = step[1:]
        try:
            if action == "open_app":
                exe = APP_MAP.get(args[0], args[0])
                subprocess.Popen(exe, shell=True)
                log.append(f"opened {args[0]}")

            elif action == "kill_app":
                exe = APP_MAP.get(args[0], args[0])
                try:
                    import psutil
                    for p in psutil.process_iter(["name"]):
                        try:
                            if p.info["name"] and p.info["name"].lower() == exe.lower():
                                p.kill()
                        except Exception:
                            pass
                    log.append(f"killed {args[0]}")
                except Exception as e:
                    log.append(f"couldn't kill {args[0]}: {e}")

            elif action == "open_url":
                if open_url_fn:
                    open_url_fn(args[0])
                else:
                    webbrowser.open(args[0])
                log.append(f"opened url {args[0][:40]}")

            elif action == "set_volume":
                if set_volume_fn:
                    set_volume_fn(args[0])
                    log.append(f"volume {args[0]}")

            elif action == "lock_pc":
                if lock_fn:
                    lock_fn()
                else:
                    os.system("rundll32.exe user32.dll,LockWorkStation")
                log.append("locked PC")

            elif action == "speak":
                if speak_fn:
                    speak_fn(args[0])
                log.append(f"said: {args[0][:30]}")

            else:
                log.append(f"unknown action {action}")
        except Exception as e:
            log.append(f"error in {action}: {e}")

    return {"ok": True, "mode": mode_name, "log": log}
