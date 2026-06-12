"""
KALKI Mail — IMAP inbox scan.
Requires EMAIL_ADDRESS + EMAIL_APP_PASSWORD set in config.py.
For Gmail, generate an App Password at https://myaccount.google.com/apppasswords
"""

import imaplib
import email
from email.header import decode_header
from datetime import datetime

import config


IMPORTANT_KEYWORDS = [
    "urgent", "important", "asap", "action required", "deadline",
    "invoice", "payment", "due", "expir", "security", "verify",
    "password", "login attempt", "alert", "warning",
    "interview", "offer", "exam", "meeting",
]


def _decode(s):
    if not s:
        return ""
    try:
        parts = decode_header(s)
    except Exception:
        return s
    out = ""
    for txt, enc in parts:
        if isinstance(txt, bytes):
            try:
                out += txt.decode(enc or "utf-8", "ignore")
            except Exception:
                out += txt.decode("utf-8", "ignore")
        else:
            out += txt
    return out.strip()


def _connect():
    if not (getattr(config, "EMAIL_ADDRESS", "") and getattr(config, "EMAIL_APP_PASSWORD", "")):
        raise RuntimeError("Email not configured. Set EMAIL_ADDRESS and "
                           "EMAIL_APP_PASSWORD in config.py.")
    M = imaplib.IMAP4_SSL(config.IMAP_SERVER, config.IMAP_PORT)
    M.login(config.EMAIL_ADDRESS, config.EMAIL_APP_PASSWORD)
    return M


def check_inbox(limit=10, only_unread=True):
    try:
        M = _connect()
    except Exception as e:
        return {"error": str(e)}

    try:
        M.select("INBOX")
        rc, ids = M.search(None, "UNSEEN" if only_unread else "ALL")
        if rc != "OK":
            return {"error": f"search failed: {rc}"}

        id_list = ids[0].split()[-limit:]
        emails = []
        for eid in reversed(id_list):
            rc, data = M.fetch(eid, "(RFC822.HEADER)")
            if rc != "OK" or not data or not data[0]:
                continue
            msg = email.message_from_bytes(data[0][1])
            subj = _decode(msg.get("Subject", ""))
            frm  = _decode(msg.get("From", ""))
            date = msg.get("Date", "")
            blob = (subj + " " + frm).lower()
            important = any(k in blob for k in IMPORTANT_KEYWORDS)
            emails.append({
                "from": frm, "subject": subj, "date": date,
                "important": important,
            })
        return {"emails": emails, "count": len(emails)}
    finally:
        try: M.logout()
        except Exception: pass


def summary_for_speech(only_important=False, limit=5):
    r = check_inbox(limit=limit, only_unread=True)
    if "error" in r:
        return f"I can't reach your mail: {r['error']}"
    items = r["emails"]
    if only_important:
        items = [e for e in items if e["important"]]
    if not items:
        return ("No important unread mail, Sir." if only_important
                else "No unread mail, Sir.")
    lines = []
    for e in items[:limit]:
        short_from = e["from"].split("<")[0].strip().strip('"')[:30] or e["from"][:30]
        short_subj = e["subject"][:60]
        prefix = "Important: " if e["important"] else ""
        lines.append(f"{prefix}from {short_from}, subject {short_subj}")
    return (f"{len(items)} unread. " + ". Next: ".join(lines))[:600]
