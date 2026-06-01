"""
JARVIS Notes & Journal — quick capture, tagged, full-text search.
"""

import os
import json
import re
from datetime import datetime, timedelta

NOTES_PATH = None  # set by server


def _load():
    try:
        with open(NOTES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(d):
    os.makedirs(os.path.dirname(NOTES_PATH), exist_ok=True)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def _extract_tags(text):
    return [t.lower() for t in re.findall(r"#(\w+)", text)]


def add_note(text):
    notes = _load()
    nid = (max((n["id"] for n in notes), default=0)) + 1
    notes.append({
        "id": nid,
        "text": text.strip(),
        "tags": _extract_tags(text),
        "ts": datetime.now().isoformat(timespec="seconds"),
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    _save(notes)
    return nid


def list_recent(n=5):
    return sorted(_load(), key=lambda x: x["ts"], reverse=True)[:n]


def notes_on(date_str):
    return [n for n in _load() if n.get("date") == date_str]


def notes_yesterday():
    yest = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return notes_on(yest)


def notes_this_week():
    today = datetime.now().date()
    start = today - timedelta(days=today.weekday())
    out = []
    for n in _load():
        try:
            d = datetime.strptime(n["date"], "%Y-%m-%d").date()
            if d >= start:
                out.append(n)
        except Exception:
            pass
    return out


def search(query):
    q = query.lower()
    return [n for n in _load()
            if q in n["text"].lower() or q in " ".join(n.get("tags", []))]


def delete_note(nid_or_text):
    notes = _load()
    needle = str(nid_or_text).lower()
    keep = [n for n in notes if not (
        str(n["id"]) == needle or needle in n["text"].lower())]
    if len(keep) != len(notes):
        _save(keep)
        return True
    return False


def summarize_for_speech(notes_list, max_items=4):
    if not notes_list:
        return "No notes."
    items = []
    for n in notes_list[:max_items]:
        items.append(n["text"][:80])
    return (f"{len(notes_list)} note{'s' if len(notes_list)!=1 else ''}. "
            + ". ".join(items))[:600]
