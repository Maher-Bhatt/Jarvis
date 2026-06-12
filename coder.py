"""
KALKI Code Engine — generate code via Groq, save, execute.
Supports Python, PowerShell, Batch.
"""

import os
import re
import sys
import subprocess
from datetime import datetime

SCRIPTS_DIR = None  # set by server.py


# Extension map
LANG_EXT = {
    "python": "py", "py": "py",
    "powershell": "ps1", "ps": "ps1", "ps1": "ps1",
    "batch": "bat", "bat": "bat", "cmd": "bat",
    "javascript": "js", "js": "js", "node": "js",
    "html": "html",
    "bash": "sh", "sh": "sh",
}


def _safe_name(name):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "script")).strip("_")
    return s[:40] or "script"


def strip_code_fence(text):
    """Pull out the first fenced code block; else return original."""
    if not text:
        return ""
    m = re.search(r"```[a-zA-Z0-9_+\-]*\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def save_script(name, code, lang="python"):
    ext = LANG_EXT.get(lang.lower(), "txt")
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    path = os.path.join(
        SCRIPTS_DIR,
        f"{_safe_name(name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}",
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


def run_script(path, lang="python", timeout=60):
    lang = lang.lower()
    if lang in ("python", "py"):
        cmd = [sys.executable, path]
    elif lang in ("powershell", "ps", "ps1"):
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", path]
    elif lang in ("batch", "bat", "cmd"):
        cmd = [path]
    elif lang in ("javascript", "js", "node"):
        cmd = ["node", path]
    else:
        return {"error": f"can't execute {lang} scripts here"}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "stdout": (p.stdout or "")[:6000],
            "stderr": (p.stderr or "")[:2000],
            "code": p.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def run_inline(code, lang="python", name="inline", timeout=60):
    code = strip_code_fence(code)
    path = save_script(name, code, lang)
    out = run_script(path, lang, timeout)
    out["path"] = path
    return out


# ─── Groq-driven code generation ────────────────────────
CODE_SYSTEM_PROMPT = (
    "You are KALKI — Sir's personal coding engine. "
    "Write production-quality {LANG} code that does exactly what Sir asks. "
    "Output ONLY the code in a single fenced block (```{LANG} ... ```). "
    "No prose before or after. No explanations unless explicitly requested. "
    "Code must be self-contained and runnable. "
    "For Python: stdlib only unless Sir names a package. "
    "Include print statements so output is visible when run."
)


def generate_code(ask_ai_fn, prompt, lang="python"):
    """ask_ai_fn is the server's ask_ai. Returns code string (fence stripped)."""
    sys_msg = CODE_SYSTEM_PROMPT.replace("{LANG}", lang)
    raw = ask_ai_fn([
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": prompt},
    ])
    return strip_code_fence(raw), raw
