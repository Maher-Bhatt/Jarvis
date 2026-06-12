"""
KALKI Web Scanner — authorized, non-destructive web vulnerability assessment.

Findings-only. Does NOT exploit, brute-force, fuzz, or DoS. It performs the
same passive + light-active checks a defender runs on their own site:
  - TLS / certificate health
  - Security response headers (HSTS, CSP, X-Frame-Options, ...)
  - Cookie flags (Secure / HttpOnly / SameSite)
  - Server / framework version disclosure
  - CORS misconfiguration
  - Exposed sensitive files (.env, .git, backups, server-status, ...)
  - Directory listing
  - Dangerous HTTP methods (TRACE/PUT/DELETE)
  - Mixed content + info leakage in HTML

For use on sites you own or are authorized to test.
"""

import os
import re
import ssl
import json
import socket
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

SCANS_DIR = "data/scans"
UA = "KALKI-Scanner/1.0 (authorized security testing)"
TIMEOUT = 6

SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

# Sensitive paths to probe (GET, non-destructive). title -> (path, signature).
SENSITIVE_PATHS = [
    ("Exposed .env file",            "/.env",            ("=", "APP_", "SECRET", "KEY", "PASSWORD", "DB_")),
    ("Exposed .git repository",      "/.git/HEAD",       ("ref:", "refs/heads")),
    ("Exposed .git config",          "/.git/config",     ("[core]", "repositoryformatversion")),
    ("Exposed .svn metadata",        "/.svn/entries",    ("dir", "svn")),
    ("Exposed config.json",          "/config.json",     ("{", "}")),
    ("Exposed backup archive",       "/backup.zip",      ("PK",)),
    ("Exposed database dump",        "/backup.sql",      ("INSERT", "CREATE TABLE", "DROP TABLE")),
    ("Exposed WordPress backup",     "/wp-config.php.bak",("DB_PASSWORD", "DB_NAME")),
    ("Exposed phpinfo()",            "/phpinfo.php",      ("phpinfo()", "PHP Version")),
    ("Exposed .htaccess",            "/.htaccess",        ("RewriteRule", "AuthType", "Options")),
    ("Exposed Apache server-status", "/server-status",    ("Apache Server Status", "Server uptime")),
    ("Exposed .DS_Store",            "/.DS_Store",        ("Bud1",)),
    ("Exposed Docker compose",       "/docker-compose.yml",("services:", "image:")),
    ("Exposed environment sample",   "/.env.example",     ("=", "APP_")),
    ("Exposed npm debug log",        "/npm-debug.log",    ("npm", "error")),
]

INFO_PATHS = ["/robots.txt", "/sitemap.xml", "/.well-known/security.txt"]


def _norm_url(url):
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _ctx_insecure():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _request(url, method="GET", timeout=TIMEOUT):
    """Return (status, headers_dict, body_text, final_url) or raises."""
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx_insecure()) as r:
        body = b""
        try:
            body = r.read(200_000)  # cap body read
        except Exception:
            pass
        return (r.status, dict(r.getheaders()), body.decode("utf-8", "ignore"), r.geturl())


def _finding(sev, title, detail, fix=""):
    return {"severity": sev, "title": title, "detail": detail, "fix": fix}


# ── individual checks ────────────────────────────────────────
def check_tls(host, port=443):
    out = []
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                proto = ssock.version()
        if proto in ("TLSv1", "TLSv1.1", "SSLv3"):
            out.append(_finding("HIGH", "Weak TLS protocol",
                                f"Server negotiated {proto}.",
                                "Disable TLS 1.0/1.1; require TLS 1.2+."))
        not_after = cert.get("notAfter")
        if not_after:
            exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (exp - datetime.now(timezone.utc)).days
            if days < 0:
                out.append(_finding("CRITICAL", "TLS certificate expired",
                                    f"Expired {-days} days ago ({not_after}).",
                                    "Renew the certificate immediately."))
            elif days < 15:
                out.append(_finding("MEDIUM", "TLS certificate expiring soon",
                                    f"Expires in {days} days ({not_after}).",
                                    "Renew before expiry."))
    except ssl.SSLCertVerificationError as e:
        out.append(_finding("HIGH", "TLS certificate not trusted",
                            f"Verification failed: {e}",
                            "Install a valid cert chain matching the hostname."))
    except Exception as e:
        out.append(_finding("INFO", "TLS check inconclusive", str(e)))
    return out


def check_headers(url):
    out = []
    try:
        status, headers, body, final = _request(url)
    except Exception as e:
        return [_finding("INFO", "Site unreachable over HTTPS", str(e))], None, None

    h = {k.lower(): v for k, v in headers.items()}
    scheme = urllib.parse.urlparse(final).scheme

    sec_headers = {
        "strict-transport-security": ("HIGH", "Missing HSTS header",
            "No Strict-Transport-Security — connection can be downgraded to HTTP.",
            "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains"),
        "content-security-policy": ("MEDIUM", "Missing Content-Security-Policy",
            "No CSP — increases XSS and injection blast radius.",
            "Define a restrictive CSP, e.g. default-src 'self'."),
        "x-frame-options": ("MEDIUM", "Missing X-Frame-Options",
            "Page can be framed — clickjacking risk.",
            "Add: X-Frame-Options: DENY (or CSP frame-ancestors 'none')."),
        "x-content-type-options": ("LOW", "Missing X-Content-Type-Options",
            "MIME-sniffing not disabled.",
            "Add: X-Content-Type-Options: nosniff"),
        "referrer-policy": ("LOW", "Missing Referrer-Policy",
            "Referrer may leak to third parties.",
            "Add: Referrer-Policy: strict-origin-when-cross-origin"),
        "permissions-policy": ("LOW", "Missing Permissions-Policy",
            "Browser features not restricted.",
            "Add a Permissions-Policy limiting camera/mic/geolocation."),
    }
    if scheme == "https" and "strict-transport-security" not in h:
        f = sec_headers["strict-transport-security"]
        out.append(_finding(*f))
    for key, f in sec_headers.items():
        if key == "strict-transport-security":
            continue
        if key not in h:
            out.append(_finding(*f))

    # frame-ancestors in CSP counts as clickjacking protection
    if "x-frame-options" not in h and "frame-ancestors" in h.get("content-security-policy", "").lower():
        out = [o for o in out if o["title"] != "Missing X-Frame-Options"]

    # Version / tech disclosure
    server = headers.get("Server", "") or h.get("server", "")
    if server and re.search(r"\d", server):
        out.append(_finding("LOW", "Server version disclosed",
                            f"Server: {server}",
                            "Suppress version banners (e.g. ServerTokens Prod)."))
    xpb = headers.get("X-Powered-By") or h.get("x-powered-by")
    if xpb:
        out.append(_finding("LOW", "Technology disclosed via X-Powered-By",
                            f"X-Powered-By: {xpb}",
                            "Remove the X-Powered-By header."))

    # CORS
    acao = h.get("access-control-allow-origin")
    acac = h.get("access-control-allow-credentials", "").lower()
    if acao == "*" and acac == "true":
        out.append(_finding("HIGH", "Insecure CORS configuration",
                            "Access-Control-Allow-Origin: * with credentials allowed.",
                            "Never combine wildcard origin with credentials; echo a vetted origin."))
    elif acao == "*":
        out.append(_finding("INFO", "Permissive CORS",
                            "Access-Control-Allow-Origin: * (no credentials).",
                            "Scope CORS to trusted origins if APIs return private data."))

    # Cookie flags
    set_cookie = headers.get("Set-Cookie", "")
    if set_cookie:
        low = set_cookie.lower()
        if "secure" not in low:
            out.append(_finding("MEDIUM", "Cookie without Secure flag",
                                "A Set-Cookie lacks the Secure attribute.",
                                "Add Secure so cookies are HTTPS-only."))
        if "httponly" not in low:
            out.append(_finding("MEDIUM", "Cookie without HttpOnly flag",
                                "A Set-Cookie lacks HttpOnly — readable by JS (XSS theft).",
                                "Add HttpOnly to session cookies."))
        if "samesite" not in low:
            out.append(_finding("LOW", "Cookie without SameSite",
                                "No SameSite attribute — CSRF exposure.",
                                "Add SameSite=Lax or Strict."))

    return out, headers, body


def check_methods(url):
    out = []
    try:
        status, headers, _, _ = _request(url, method="OPTIONS")
        allow = (headers.get("Allow") or headers.get("allow") or "").upper()
        for danger in ("TRACE", "PUT", "DELETE", "CONNECT"):
            if danger in allow:
                sev = "MEDIUM" if danger == "TRACE" else "HIGH"
                out.append(_finding(sev, f"Dangerous HTTP method enabled: {danger}",
                                    f"Allow: {allow}",
                                    f"Disable {danger} unless required."))
    except Exception:
        pass
    return out


def check_paths(base):
    out = []
    def probe(item):
        title, path, sig = item
        try:
            status, headers, body, _ = _request(base + path, timeout=5)
            if status == 200 and any(s.lower() in body.lower() for s in sig):
                return _finding("HIGH", title,
                                f"{base + path} returned 200 with matching content.",
                                "Remove the file from the web root or block access.")
        except Exception:
            return None
        return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(probe, it) for it in SENSITIVE_PATHS]):
            r = fut.result()
            if r:
                out.append(r)
    return out


def check_dir_listing(base):
    out = []
    for path in ("/", "/uploads/", "/images/", "/files/", "/backup/"):
        try:
            status, headers, body, _ = _request(base + path, timeout=5)
            if status == 200 and ("Index of /" in body or "<title>Directory listing" in body):
                out.append(_finding("MEDIUM", "Directory listing enabled",
                                    f"{base + path} exposes a file index.",
                                    "Disable autoindex / directory browsing."))
                break
        except Exception:
            pass
    return out


def check_html_leaks(body, scheme):
    out = []
    if not body:
        return out
    if scheme == "https" and re.search(r'src=["\']http://', body, re.I):
        out.append(_finding("LOW", "Mixed content",
                            "HTTPS page loads resources over plain HTTP.",
                            "Serve all assets over HTTPS."))
    if re.search(r"<!--.*?(todo|fixme|password|api[_-]?key|secret).*?-->", body, re.I | re.S):
        out.append(_finding("LOW", "Sensitive hint in HTML comment",
                            "An HTML comment mentions todo/password/key/secret.",
                            "Strip developer comments from production HTML."))
    return out


# ── secrets in source (HTML + JS) ────────────────────────────
_SECRET_PATTERNS = [
    ("AWS access key id",      re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Google API key",         re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Slack token",            re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Stripe live secret key", re.compile(r"sk_live_[0-9a-zA-Z]{24,}")),
    ("GitHub token",           re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("Private key block",      re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----")),
    ("JWT",                    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("Hardcoded credential",   re.compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password|access[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
]


def scan_secrets(text, where):
    out, seen = [], set()
    if not text:
        return out
    for label, pat in _SECRET_PATTERNS:
        for m in pat.finditer(text):
            snippet = m.group(0)[:60]
            key = (label, snippet)
            if key in seen:
                continue
            seen.add(key)
            out.append(_finding("HIGH", f"Possible {label} in {where}",
                                f"Match: {snippet}",
                                "Move secrets server-side; rotate any real key found."))
            if len(out) >= 8:
                return out
    return out


def analyze_source(base, body):
    """Fetch same-origin JS, scan everything for secrets, map form/injection
    surface. Returns (findings, full_source_text)."""
    findings = []
    full = body or ""
    host = urllib.parse.urlparse(base).netloc

    # secrets in the HTML itself
    findings += scan_secrets(body, "page HTML")

    # linked same-origin scripts
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', body or "", re.I)
    fetched = 0
    for src in srcs:
        if fetched >= 8:
            break
        url = urllib.parse.urljoin(base + "/", src)
        if urllib.parse.urlparse(url).netloc != host:
            continue   # only our own scripts
        try:
            _, _, js, _ = _request(url, timeout=6)
        except Exception:
            continue
        fetched += 1
        full += f"\n\n/* ==== {url} ==== */\n" + js
        findings += scan_secrets(js, f"script {src.split('/')[-1]}")

    # forms / injection surface
    forms = re.findall(r"<form\b[^>]*>(.*?)</form>", body or "", re.I | re.S)
    inputs = re.findall(r'<input\b[^>]*name=["\']([^"\']+)["\']', body or "", re.I)
    if forms:
        joined = " ".join(forms)
        actions = re.findall(r'action=["\']([^"\']*)["\']', " ".join(
            re.findall(r"<form\b[^>]*>", body or "", re.I)), re.I)
        if any(a.startswith("http://") for a in actions):
            findings.append(_finding("MEDIUM", "Form submits over plain HTTP",
                                     "A <form action> targets an http:// URL.",
                                     "Point form actions at https:// endpoints."))
        if re.search(r'type=["\']password["\']', joined, re.I) and base.startswith("http://"):
            findings.append(_finding("HIGH", "Password field on non-HTTPS page",
                                     "A password input is served over HTTP.",
                                     "Serve all auth pages over HTTPS."))
        if not re.search(r'name=["\'][^"\']*(csrf|token|authenticity|nonce)[^"\']*["\']', joined, re.I):
            findings.append(_finding("LOW", "Form has no obvious CSRF token",
                                     f"{len(forms)} form(s), no csrf/token hidden field seen.",
                                     "Add an anti-CSRF token to state-changing forms."))
        findings.append(_finding("INFO", "Input surface mapped",
                                 f"{len(forms)} form(s), {len(inputs)} input field(s): "
                                 f"{', '.join(inputs[:12])}",
                                 "Validate and sanitize each input server-side."))
    return findings, full


# ── orchestration ────────────────────────────────────────────
def scan(url, active=True):
    target = _norm_url(url)
    host = urllib.parse.urlparse(target).hostname or url
    findings = []

    # reachability
    try:
        status, headers, body, final = _request(target)
        scheme = urllib.parse.urlparse(final).scheme
    except Exception as e:
        # try http fallback
        try:
            target = "http://" + host
            status, headers, body, final = _request(target)
            scheme = "http"
            findings.append(_finding("HIGH", "No HTTPS",
                                     "Site served over plain HTTP only.",
                                     "Enable HTTPS and redirect HTTP to HTTPS."))
        except Exception as e2:
            return {"target": url, "error": f"unreachable: {e2}", "findings": []}

    base = f"{scheme}://{host}"

    findings += check_tls(host)
    h_out, _, body = check_headers(target)
    findings += h_out
    findings += check_methods(target)
    findings += check_paths(base)
    findings += check_dir_listing(base)
    findings += check_html_leaks(body or "", scheme)

    # source code + JS secrets + injection surface
    src_findings, full_source = analyze_source(base, body or "")
    findings += src_findings
    source_path = _save_source(host, base, full_source)

    # active checks (still non-destructive: benign markers, observe-only)
    if active:
        try:
            findings += check_reflected_xss(target, base)
            findings += check_open_redirect(base)
            findings += crawl_links(base, body or "", limit=4)
        except Exception:
            pass

    # info paths (not vulns, context)
    info = []
    for p in INFO_PATHS:
        try:
            s, _, _, _ = _request(base + p, timeout=4)
            if s == 200:
                info.append(p)
        except Exception:
            pass

    findings.sort(key=lambda f: SEV_ORDER.get(f["severity"], 9))
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    report_path = _write_report(host, base, findings, counts, info, source_path)
    return {"target": base, "host": host, "findings": findings,
            "counts": counts, "info": info, "report_path": report_path,
            "source_path": source_path}


def _no_redirect_location(url):
    """GET without following redirects; return the Location header (or '')."""
    class _NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(_NR)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        r = opener.open(req, timeout=6)
        return r.headers.get("Location", "") or ""
    except urllib.error.HTTPError as e:
        return e.headers.get("Location", "") or ""
    except Exception:
        return ""


def check_reflected_xss(target, base):
    """Inject a harmless marker into query params; flag UNESCAPED reflection.
    Non-destructive — a single benign GET per param."""
    out = []
    parsed = urllib.parse.urlparse(target if "?" in target else base)
    qs = urllib.parse.parse_qs(parsed.query)
    marker = "kqz9x7"
    payload = marker + "<svg/onload=alert(1)>"
    params = list(qs.keys()) or ["q", "s", "search", "id", "page", "redirect"]
    for p in params[:6]:
        flat = {k: v[0] for k, v in qs.items()}
        flat[p] = payload
        url = parsed._replace(query=urllib.parse.urlencode(flat)).geturl()
        try:
            _, _, body, _ = _request(url, timeout=6)
        except Exception:
            continue
        if marker + "<svg" in (body or ""):
            out.append(_finding("HIGH", f"Reflected XSS surface on '{p}'",
                                f"Marker reflected UNESCAPED at {url}",
                                "HTML-encode user input on output; add CSP."))
        elif marker in (body or "") and "&lt;svg" in body:
            out.append(_finding("INFO", f"Param '{p}' reflected (escaped)",
                                "Input is echoed but correctly HTML-escaped.",
                                "Keep encoding; no action needed."))
    return out


def check_open_redirect(base):
    """Probe common redirect params for off-site redirection. Observes only."""
    out = []
    bait = "https://kalki-probe.example.org/x"
    for p in ("url", "next", "redirect", "return", "returnUrl", "dest",
              "destination", "continue", "redir", "u"):
        url = base + "/?" + p + "=" + urllib.parse.quote(bait)
        loc = _no_redirect_location(url)
        if loc and ("kalki-probe.example.org" in loc or loc.startswith(bait)):
            out.append(_finding("HIGH", f"Open redirect via '{p}'",
                                f"{url}  ->  Location: {loc}",
                                "Allow-list redirect targets; reject absolute URLs."))
            break
    return out


def crawl_links(base, body, limit=4):
    """Lightly crawl a few same-origin pages and scan them for secrets."""
    out = []
    host = urllib.parse.urlparse(base).netloc
    hrefs = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', body or "", re.I)
    seen, pages = set(), []
    for h in hrefs:
        u = urllib.parse.urljoin(base + "/", h.split("#")[0])
        if urllib.parse.urlparse(u).netloc != host or u in seen:
            continue
        seen.add(u)
        pages.append(u)
        if len(pages) >= limit:
            break
    for u in pages:
        try:
            _, _, b, _ = _request(u, timeout=5)
        except Exception:
            continue
        out += scan_secrets(b, f"page {u.split('/')[-1] or 'root'}")
    if pages:
        out.append(_finding("INFO", "Crawled internal pages",
                            f"Checked {len(pages)}: {', '.join(p.split('/')[-1] or '/' for p in pages)}",
                            "Review linked pages for the same issues."))
    return out


def _save_source(host, base, source_text):
    """Dump the gathered HTML + JS to a file so Sir can read the source."""
    if not source_text:
        return None
    os.makedirs(SCANS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCANS_DIR, f"{host}_{ts}_source.txt")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"/* Source captured from {base} at {datetime.now().isoformat(timespec='seconds')} */\n\n")
            fh.write(source_text)
        return path
    except Exception:
        return None


def _write_report(host, base, findings, counts, info, source_path=None):
    os.makedirs(SCANS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCANS_DIR, f"{host}_{ts}.txt")
    lines = []
    lines.append("=" * 64)
    lines.append(f"KALKI WEB SCAN REPORT")
    lines.append(f"Target : {base}")
    lines.append(f"Time   : {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Note   : Authorized, non-destructive assessment. Findings only.")
    if source_path:
        lines.append(f"Source : captured -> {source_path}")
    lines.append("=" * 64)
    summary = ", ".join(f"{counts[s]} {s}" for s in sorted(counts, key=lambda k: SEV_ORDER[k])) or "no issues found"
    lines.append(f"SUMMARY: {summary}")
    if info:
        lines.append(f"INFO   : present -> {', '.join(info)}")
    lines.append("")
    if not findings:
        lines.append("No issues detected by the checks performed. (Not a guarantee of security.)")
    for i, f in enumerate(findings, 1):
        lines.append(f"[{i}] {f['severity']}  —  {f['title']}")
        lines.append(f"     What : {f['detail']}")
        if f.get("fix"):
            lines.append(f"     Fix  : {f['fix']}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def summarize_for_speech(result, title="Sir"):
    """Short spoken summary; the full detail lives in the report file."""
    if result.get("error"):
        return f"I couldn't reach {result['target']}, {title}. {result['error']}"
    counts = result.get("counts", {})
    findings = result.get("findings", [])
    if not findings:
        return (f"Scan complete, {title}. No issues flagged by my checks on "
                f"{result['host']}. The full report is saved.")
    parts = [f"{counts[s]} {s.lower()}" for s in sorted(counts, key=lambda k: SEV_ORDER[k])]
    top = findings[0]
    return (f"Scan complete, {title}. Found {', '.join(parts)} on {result['host']}. "
            f"Top issue: {top['title']}. Full report with fixes is saved to the scans folder.")
