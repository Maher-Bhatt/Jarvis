"""
KALKI Spotify control via Spotify Web API.
First-time setup runs setup_spotify.py to authorize.
"""

import os

CACHE_PATH = None  # set by server.py
SCOPES = (
    "user-modify-playback-state user-read-playback-state "
    "user-read-currently-playing user-library-read playlist-read-private"
)


def _lazy_imports():
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        return spotipy, SpotifyOAuth
    except ImportError as e:
        raise RuntimeError(f"spotipy not installed: {e}")


def is_configured():
    import config
    return bool(getattr(config, "SPOTIFY_CLIENT_ID", "")
                and getattr(config, "SPOTIFY_CLIENT_SECRET", "")
                and CACHE_PATH and os.path.exists(CACHE_PATH))


def _client(interactive=False):
    import config
    spotipy, SpotifyOAuth = _lazy_imports()
    auth = SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=getattr(config, "SPOTIFY_REDIRECT_URI",
                              "http://127.0.0.1:8889/callback"),
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=interactive,
    )
    return spotipy.Spotify(auth_manager=auth)


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        return {"error": str(e)}


# ─── Device management ─────────────────────────────────
def _ensure_active_device(sp):
    """Find a usable device. If none active, transfer to first available.
    Returns device_id or None."""
    try:
        items = sp.devices().get("devices", [])
    except Exception:
        return None
    if not items:
        return None
    active = [d for d in items if d.get("is_active")]
    if active:
        return active[0]["id"]
    # Pick a non-restricted device and transfer
    target = next((d for d in items if not d.get("is_restricted")), items[0])
    try:
        sp.transfer_playback(target["id"], force_play=False)
    except Exception:
        pass
    return target["id"]


def _try_launch_spotify():
    """Open Spotify desktop or web player so a device appears.
    Tries known install paths + URI handler + web fallback."""
    import subprocess
    import webbrowser

    candidates = [
        # Per-user installer (most common)
        os.path.expanduser(r"~\AppData\Roaming\Spotify\Spotify.exe"),
        # Microsoft Store install
        os.path.expanduser(r"~\AppData\Local\Microsoft\WindowsApps\Spotify.exe"),
        # System-wide installs
        r"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic_*\Spotify.exe",
        r"C:\Program Files\Spotify\Spotify.exe",
        r"C:\Program Files (x86)\Spotify\Spotify.exe",
    ]
    import glob
    for pat in candidates:
        for path in (glob.glob(pat) if "*" in pat else [pat]):
            if path and os.path.exists(path):
                try:
                    subprocess.Popen([path],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL,
                                     creationflags=0x00000008 if os.name == "nt" else 0)
                    return "desktop"
                except Exception:
                    continue

    # URI handler (works if Spotify registered `spotify://`)
    try:
        os.startfile("spotify:")
        return "uri"
    except Exception:
        pass

    # Final fallback: open the web player
    try:
        webbrowser.open("https://open.spotify.com")
        return "web"
    except Exception:
        return None


# ─── Playback ──────────────────────────────────────────
import time as _time

_last_query = None   # remembered so "retry" / "play it again" works


def _wait_for_device(sp, timeout=14):
    """Poll until Spotify registers a playback device (after a cold launch)."""
    end = _time.time() + timeout
    while _time.time() < end:
        try:
            items = sp.devices().get("devices", [])
        except Exception:
            items = []
        if items:
            active = next((d for d in items if d.get("is_active")), None)
            return (active or items[0])["id"]
        _time.sleep(1.3)
    return None


def play(query=None):
    """Search + play. Launches Spotify and WAITS for a device if none is
    active, then transfers playback and plays — so a cold start just works."""
    global _last_query
    if query:
        _last_query = query
    q = query or _last_query

    sp = _client()
    device_id = _ensure_active_device(sp)
    launched = False
    if not device_id:
        _try_launch_spotify()
        launched = True
        device_id = _wait_for_device(sp, timeout=14)
    if not device_id:
        return ("I opened Spotify but no device came online, Sir. Open the "
                "Spotify app once and sign in, then say play again.")

    # Make sure our target is the active device.
    try:
        sp.transfer_playback(device_id, force_play=False)
    except Exception:
        pass
    if launched:
        _time.sleep(1.5)   # let the fresh app settle before commanding it

    def _run():
        if not q:
            sp.start_playback(device_id=device_id)
            return "Resuming, Sir."
        r = sp.search(q=q, type="track,playlist,album", limit=5)
        tracks = r.get("tracks", {}).get("items", [])
        plists = r.get("playlists", {}).get("items", [])
        if tracks:
            tr = tracks[0]
            sp.start_playback(device_id=device_id, uris=[tr["uri"]])
            return f"Playing {tr['name']} by {tr['artists'][0]['name']}."
        if plists:
            p = plists[0]
            sp.start_playback(device_id=device_id, context_uri=p["uri"])
            return f"Playing playlist {p['name']}."
        return f"No results for {q}, Sir."

    # Try; on NO_ACTIVE_DEVICE force-activate the device and retry once.
    for attempt in (1, 2):
        try:
            return _run()
        except Exception as e:
            msg = str(e)
            if attempt == 1 and ("NO_ACTIVE_DEVICE" in msg or "404" in msg
                                 or "Device not found" in msg.lower()):
                try:
                    sp.transfer_playback(device_id, force_play=True)
                except Exception:
                    pass
                _time.sleep(2.0)
                continue
            return f"Spotify error: {msg}"


def retry():
    """Re-run the last play request (for 'retry' / 'try again')."""
    return play(_last_query)


def pause():
    sp = _client()
    try:
        sp.pause_playback()
        return "Paused."
    except Exception as e:
        return f"Couldn't pause: {e}"


def next_track():
    sp = _client()
    try:
        sp.next_track()
        return "Skipping."
    except Exception as e:
        return f"Couldn't skip: {e}"


def prev_track():
    sp = _client()
    try:
        sp.previous_track()
        return "Going back, Sir."
    except Exception as e:
        return f"Couldn't go back: {e}"


def set_volume(percent):
    sp = _client()
    try:
        sp.volume(max(0, min(100, int(percent))))
        return f"Spotify volume {int(percent)} percent."
    except Exception as e:
        return f"Couldn't set volume: {e}"


def now_playing():
    sp = _client()
    try:
        r = sp.current_playback()
        if not r or not r.get("item"):
            return "Nothing playing."
        item = r["item"]
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        return f"{item['name']} by {artists}."
    except Exception as e:
        return f"Spotify error: {e}"


def shuffle_on():
    sp = _client()
    try:
        sp.shuffle(True)
        return "Shuffle on."
    except Exception as e:
        return f"Couldn't shuffle: {e}"


def play_lofi():
    return play("lo-fi study beats")
