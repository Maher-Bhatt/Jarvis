"""
JARVIS Vault — DPAPI-encrypted local password store.
Per-Windows-user, machine-locked. No master password.
Falls back to base64 (clearly marked) if pywin32 is missing.
"""

import os
import json
import base64
from datetime import datetime

try:
    import win32crypt
    HAS_DPAPI = True
except Exception:
    HAS_DPAPI = False

VAULT_PATH = None  # set by server.py before first use


def _enc(plain):
    if plain is None or plain == "":
        return ""
    data = plain.encode("utf-8") if isinstance(plain, str) else plain
    if HAS_DPAPI:
        blob = win32crypt.CryptProtectData(data, "jarvis-vault", None, None, None, 0)
        return "DPAPI:" + base64.b64encode(blob).decode()
    return "B64:" + base64.b64encode(data).decode()


def _dec(blob):
    if not blob:
        return ""
    if blob.startswith("DPAPI:") and HAS_DPAPI:
        raw = base64.b64decode(blob[6:])
        try:
            return win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1].decode("utf-8")
        except Exception:
            return ""
    if blob.startswith("B64:"):
        try:
            return base64.b64decode(blob[4:]).decode("utf-8")
        except Exception:
            return ""
    return blob


def _load():
    try:
        with open(VAULT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(d):
    os.makedirs(os.path.dirname(VAULT_PATH), exist_ok=True)
    with open(VAULT_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def save_entry(label, username="", password="", url="", notes=""):
    if not label:
        return False
    d = _load()
    key = label.lower().strip()
    d[key] = {
        "label": label,
        "username": _enc(username),
        "password": _enc(password),
        "url": url or "",
        "notes": notes or "",
        "saved": datetime.now().isoformat(timespec="seconds"),
    }
    _save(d)
    return True


def list_labels():
    d = _load()
    return [
        {"label": v["label"], "url": v.get("url", ""), "saved": v.get("saved", "")}
        for v in d.values()
    ]


def get_entry(label):
    d = _load()
    e = d.get(label.lower().strip())
    if not e:
        return None
    return {
        "label": e["label"],
        "username": _dec(e.get("username", "")),
        "password": _dec(e.get("password", "")),
        "url": e.get("url", ""),
        "notes": e.get("notes", ""),
        "saved": e.get("saved", ""),
    }


def find_entry(query):
    """Fuzzy match — first label containing the query."""
    if not query:
        return None
    q = query.lower().strip()
    d = _load()
    if q in d:
        return get_entry(q)
    for k in d.keys():
        if q in k or k in q:
            return get_entry(k)
    return None


def delete_entry(label):
    d = _load()
    k = label.lower().strip()
    if k in d:
        del d[k]
        _save(d)
        return True
    # try fuzzy delete
    for key in list(d.keys()):
        if label.lower() in key:
            del d[key]
            _save(d)
            return True
    return False
