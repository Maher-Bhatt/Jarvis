"""
KALKI Google Calendar integration.
Uses OAuth — first-time setup runs setup_google.py to authorize.
"""

import os
import datetime
import pickle
import threading

_creds_lock = threading.Lock()


def _atomic_pickle_dump(obj, path):
    """Write pickle atomically — temp file + replace.
    Prevents the file from being half-written if two threads race."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

CRED_PATH  = None   # set by server.py / setup_google.py
TOKEN_PATH = None
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _lazy_imports():
    """Return the Google libs or raise a helpful error."""
    try:
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        return Request, InstalledAppFlow, build
    except ImportError as e:
        raise RuntimeError(
            "Google libraries not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib"
        ) from e


def _get_creds(interactive=False):
    """Thread-safe credential loader with atomic writes."""
    with _creds_lock:
        Request, InstalledAppFlow, _ = _lazy_imports()
        creds = None
        if TOKEN_PATH and os.path.exists(TOKEN_PATH):
            try:
                with open(TOKEN_PATH, "rb") as f:
                    creds = pickle.load(f)
            except (EOFError, pickle.UnpicklingError, OSError) as e:
                print(f"[gcal] token corrupt — discarding: {e}")
                try: os.remove(TOKEN_PATH)
                except Exception: pass
                creds = None
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _atomic_pickle_dump(creds, TOKEN_PATH)
                return creds
            except Exception as e:
                print(f"[gcal] token refresh failed: {e}")
        if not interactive:
            raise RuntimeError(
                "No valid Google token. Run setup_google.py once to authorize."
            )
        if not CRED_PATH or not os.path.exists(CRED_PATH):
            raise FileNotFoundError(
                f"Place Google OAuth credentials.json at {CRED_PATH}. "
                f"Get one at https://console.cloud.google.com (Desktop OAuth client)."
            )
        flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        _atomic_pickle_dump(creds, TOKEN_PATH)
        return creds


def is_configured():
    return bool(TOKEN_PATH and os.path.exists(TOKEN_PATH))


def _service(api, version):
    _, _, build = _lazy_imports()
    return build(api, version, credentials=_get_creds(), cache_discovery=False)


# ─── Calendar ─────────────────────────────────────────────
def _iso(dt):
    return dt.isoformat() + "Z"


def today_events():
    try:
        svc = _service("calendar", "v3")
        # Use the user's LOCAL timezone for "today" boundaries — Google parses
        # the offset from the RFC3339 string we pass in.
        now = datetime.datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = now.replace(hour=23, minute=59, second=59, microsecond=0)
        r = svc.events().list(
            calendarId="primary",
            timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=20,
        ).execute()
        return r.get("items", [])
    except Exception as e:
        return {"error": str(e)}


def upcoming_events(n=5):
    try:
        svc = _service("calendar", "v3")
        now = datetime.datetime.now().astimezone()
        r = svc.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=n,
        ).execute()
        return r.get("items", [])
    except Exception as e:
        return {"error": str(e)}


def tomorrow_events():
    try:
        svc = _service("calendar", "v3")
        tom = datetime.datetime.now().astimezone() + datetime.timedelta(days=1)
        start = tom.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = tom.replace(hour=23, minute=59, second=59, microsecond=0)
        r = svc.events().list(
            calendarId="primary",
            timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=20,
        ).execute()
        return r.get("items", [])
    except Exception as e:
        return {"error": str(e)}


def events_in_window(minutes_ahead=16):
    """Events starting in the next N minutes (for reminder alerts).
    Uses local tz-aware times so calculations match the user's clock."""
    try:
        svc = _service("calendar", "v3")
        now = datetime.datetime.now().astimezone()
        end = now + datetime.timedelta(minutes=minutes_ahead)
        r = svc.events().list(
            calendarId="primary",
            timeMin=now.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=10,
        ).execute()
        return r.get("items", [])
    except Exception:
        return []


def _format_when(ev):
    s = ev["start"].get("dateTime") or ev["start"].get("date") or ""
    if "T" in s:
        try:
            t = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            return t.astimezone().strftime("%I:%M %p").lstrip("0")
        except Exception:
            return s
    return "all day"


def events_summary(events, when_label="today"):
    if isinstance(events, dict) and "error" in events:
        return f"Calendar error: {events['error']}"
    if not events:
        return "Your calendar is clear, Sir."
    parts = []
    for e in events[:4]:
        title = e.get("summary", "untitled")
        when  = _format_when(e)
        parts.append(f"{title} at {when}")
    n = len(events)
    word = "event" if n == 1 else "events"
    extra = "" if n <= 4 else f" Plus {n-4} more."
    return f"{n} {word} {when_label}: " + "; ".join(parts) + "." + extra


def today_summary():
    """Speak today's events. If today is clear, fall through to the next
    upcoming event so Sir always hears what's coming."""
    today = today_events()
    if isinstance(today, list) and today:
        return events_summary(today)
    if isinstance(today, dict) and "error" in today:
        return f"Calendar error: {today['error']}"

    # Today's clear — show the next scheduled event so user knows what's ahead
    tom = tomorrow_events()
    if isinstance(tom, list) and tom:
        n = len(tom)
        first = tom[0]
        return (f"Your calendar is clear today, Sir. Tomorrow you have "
                f"{n} event{'s' if n != 1 else ''}, starting with "
                f"{first.get('summary','untitled')} at {_format_when(first)}.")

    upcoming = upcoming_events(3)
    if isinstance(upcoming, list) and upcoming:
        first = upcoming[0]
        when = _format_when_long(first)
        return (f"Your calendar is clear today, Sir. Your next event is "
                f"{first.get('summary','untitled')} on {when}.")

    return "Your calendar is clear, Sir."


def _format_when_long(ev):
    """Human-readable date+time for events further out."""
    s = ev["start"].get("dateTime") or ev["start"].get("date") or ""
    if "T" in s:
        try:
            t = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            return t.astimezone().strftime("%A %B %d at %I:%M %p").replace(" 0", " ")
        except Exception:
            return s
    try:
        t = datetime.datetime.strptime(s, "%Y-%m-%d")
        return t.strftime("%A %B %d")
    except Exception:
        return s


def _events_phrase(events, when):
    n = len(events)
    if n == 0:
        return ""
    if n == 1:
        e = events[0]
        return f"One event {when}: {e.get('summary','untitled')} at {_format_when(e)}"
    head = []
    for e in events[:3]:
        head.append(f"{e.get('summary','untitled')} at {_format_when(e)}")
    extra = f", plus {n-3} more" if n > 3 else ""
    return f"{n} events {when}: " + "; ".join(head) + extra


def short_greeting_line():
    """Backward-compatible single-line summary (today only)."""
    if not is_configured():
        return ""
    events = today_events()
    if isinstance(events, dict) and "error" in events:
        return ""
    if not events:
        return " Your calendar is clear today."
    return " " + _events_phrase(events, "today") + "."


def startup_summary():
    """Spoken at KALKI startup: today's events + tomorrow's events + important mail."""
    if not is_configured():
        return ""

    parts = []

    today = today_events()
    if isinstance(today, list):
        if today:
            parts.append(_events_phrase(today, "today"))
        else:
            parts.append("Your calendar is clear today")

    tom = tomorrow_events()
    if isinstance(tom, list) and tom:
        parts.append(_events_phrase(tom, "tomorrow"))

    important = gmail_important_unread(limit=5)
    if isinstance(important, dict) and "error" not in important:
        n = important.get("count", 0)
        if n > 0:
            parts.append(
                f"{n} important unread email{'s' if n != 1 else ''} in your primary inbox"
            )

    return " " + ". ".join(parts) + "." if parts else ""


# ─── Gmail (filtered to PRIMARY only — no promotions, social, updates, forums, spam) ─────────
GMAIL_IMPORTANT_QUERY = (
    "is:unread category:primary "
    "-category:promotions -category:social -category:updates -category:forums "
    "-label:spam -label:trash"
)


def gmail_unread(limit=10, query=None):
    try:
        svc = _service("gmail", "v1")
        q = query if query is not None else GMAIL_IMPORTANT_QUERY
        r = svc.users().messages().list(
            userId="me", q=q, maxResults=limit,
        ).execute()
        msgs = r.get("messages", [])
        out = []
        for m in msgs[:limit]:
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
            labels = full.get("labelIds", [])
            out.append({
                "from":    headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date":    headers.get("Date", ""),
                "snippet": full.get("snippet", "")[:120],
                "important": "IMPORTANT" in labels,
                "starred":   "STARRED" in labels,
            })
        return {"emails": out, "count": len(out)}
    except Exception as e:
        return {"error": str(e)}


def gmail_important_unread(limit=10):
    """Alias of gmail_unread with the important filter (used by startup_summary)."""
    return gmail_unread(limit=limit)


def gmail_summary():
    r = gmail_unread(limit=5)
    if "error" in r:
        return f"Gmail error: {r['error']}"
    if not r["emails"]:
        return "No important unread mail, Sir. Promotions and notifications skipped."
    parts = []
    for e in r["emails"][:4]:
        sender = e["from"].split("<")[0].strip().strip('"')[:30] or e["from"][:30]
        subj = e["subject"][:60]
        marker = "★ " if e.get("starred") else ("! " if e.get("important") else "")
        parts.append(f"{marker}from {sender}: {subj}")
    return (f"{len(r['emails'])} important unread. " + "; ".join(parts) + ".")[:600]
