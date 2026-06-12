"""
KALKI Site Watchdog — background monitor for your own + client sites.
Tracks: reachability (up/down), SSL certificate expiry, HTTP status.
Speaks proactive alerts via the server's background loop.
"""

import os
import ssl
import json
import socket
import urllib.request
from datetime import datetime, timezone

WATCHLIST_PATH = None   # set by server.py
UA = "KALKI-Watchdog/1.0"


def _load():
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(sites):
    try:
        with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(sites, f, indent=2)
    except Exception:
        pass


def _host(url):
    u = url.replace("https://", "").replace("http://", "").strip("/")
    return u.split("/")[0]


def add_site(url, label=""):
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    sites = _load()
    if any(s["url"] == url for s in sites):
        return f"Already watching {_host(url)}, Sir."
    sites.append({"url": url, "label": label or _host(url)})
    _save(sites)
    return f"Now watching {_host(url)}, Sir. I'll alert you if it goes down or its cert is expiring."


def remove_site(needle):
    sites = _load()
    keep = [s for s in sites if needle.lower() not in s["url"].lower()
            and needle.lower() not in s.get("label", "").lower()]
    _save(keep)
    removed = len(sites) - len(keep)
    return f"Stopped watching {removed} site(s)." if removed else "No matching watched site, Sir."


def list_sites():
    return _load()


def cert_days_left(host, port=443):
    """Days until the TLS cert expires, or None."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        na = cert.get("notAfter")
        if not na:
            return None
        exp = datetime.strptime(na, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return (exp - datetime.now(timezone.utc)).days
    except Exception:
        return None


def check_site(url):
    """Return {url, host, up, status, cert_days, error}."""
    host = _host(url)
    res = {"url": url, "host": host, "up": False, "status": None,
           "cert_days": None, "error": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            res["up"] = True
            res["status"] = r.status
    except urllib.error.HTTPError as e:
        # responded, just an error code — still "up"
        res["up"] = True
        res["status"] = e.code
    except Exception as e:
        res["error"] = str(e)
    if url.startswith("https://"):
        res["cert_days"] = cert_days_left(host)
    return res


def check_all():
    return [check_site(s["url"]) for s in _load()]


def summarize(results, title="Sir"):
    if not results:
        return f"You aren't watching any sites yet, {title}. Say 'watch' then a website."
    down = [r for r in results if not r["up"]]
    soon = [r for r in results if r.get("cert_days") is not None and r["cert_days"] <= 14]
    parts = []
    if down:
        parts.append(f"{len(down)} down: " + ", ".join(r["host"] for r in down))
    else:
        parts.append(f"all {len(results)} sites up")
    if soon:
        parts.append("certs expiring: " + ", ".join(
            f"{r['host']} in {r['cert_days']}d" for r in soon))
    return f"Site check, {title}: " + ". ".join(parts) + "."
