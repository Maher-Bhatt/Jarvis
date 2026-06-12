"""
KALKI clipboard helper — read the Windows clipboard and auto-analyze it.
Powers "decode/explain my clipboard" and the quick-capture feature.
"""

import re
import json
import base64

import cybertools


def read_text():
    """Return clipboard text, or None."""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            data = None
        finally:
            win32clipboard.CloseClipboard()
        return data
    except Exception:
        return None


def set_text(s):
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(s, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return True
    except Exception:
        return False


def _b64url(s):
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s).decode("utf-8", "replace")


def analyze(text):
    """Detect the type of clipboard content and decode/explain it.
    Returns (spoken_summary, detail_text)."""
    if not text:
        return "Your clipboard is empty, Sir.", ""
    t = text.strip()

    # JWT
    if re.match(r"^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$", t):
        try:
            h, p, _ = t.split(".")
            header = json.loads(_b64url(h))
            payload = json.loads(_b64url(p))
            detail = ("JWT decoded:\n\nHEADER:\n"
                      + json.dumps(header, indent=2)
                      + "\n\nPAYLOAD:\n" + json.dumps(payload, indent=2))
            alg = header.get("alg", "?")
            sub = payload.get("sub") or payload.get("email") or payload.get("name") or ""
            return (f"That's a JWT, {{t}}. Algorithm {alg}"
                    + (f", subject {sub}." if sub else "."), detail)
        except Exception:
            pass

    # URL
    if re.match(r"^https?://\S+$", t):
        return ("That's a URL, {t}. Say 'scan this website' to audit it.", t)

    # hex
    if re.match(r"^(0x)?[0-9a-fA-F]{8,}$", t) and len(t.replace("0x", "")) % 2 == 0:
        try:
            dec = cybertools.decode(t.replace("0x", ""), "hex")
            if dec.isprintable():
                return ("Hex decoded, {t}.", f"Hex -> {dec}")
        except Exception:
            pass

    # base64
    if re.match(r"^[A-Za-z0-9+/=\s]{12,}$", t) and len(t.strip()) % 4 == 0:
        try:
            dec = cybertools.decode(t, "base64")
            if dec and sum(c.isprintable() for c in dec) > len(dec) * 0.8:
                return ("Base64 decoded, {t}.", f"Base64 -> {dec}")
        except Exception:
            pass

    # URL-encoded
    if "%" in t and re.search(r"%[0-9a-fA-F]{2}", t):
        try:
            dec = cybertools.decode(t, "url")
            if dec != t:
                return ("URL-decoded, {t}.", f"URL -> {dec}")
        except Exception:
            pass

    # hash (by length)
    if re.match(r"^[0-9a-fA-F]+$", t) and len(t) in (32, 40, 56, 64, 96, 128):
        guesses = cybertools.identify_hash(t)
        return (f"Looks like a {', '.join(guesses)} hash, {{t}}.",
                f"Hash type guess: {', '.join(guesses)}\nSay 'crack hash {t}' to attempt it.")

    # plain text — short summary
    words = len(t.split())
    preview = t[:200]
    return (f"Plain text on your clipboard, {{t}} — {words} words.", preview)
