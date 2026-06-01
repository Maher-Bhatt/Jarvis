"""
JARVIS v5 — Silent Launcher
- Registers Windows auto-start (HKCU Run + Startup folder shortcut).
- Spawns server.py + listener.py with no console windows.
- Respawns either child if it dies.
"""

import os
import sys
import time
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import config

LOG_PATH = os.path.join(BASE_DIR, "data", "launcher.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


def find_pythonw():
    here = os.path.dirname(sys.executable)
    p = os.path.join(here, "pythonw.exe")
    if os.path.exists(p):
        return p
    p = os.path.join(here, "python.exe")
    if os.path.exists(p):
        return p
    return sys.executable


def spawn(script):
    pyw = find_pythonw()
    cflags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    return subprocess.Popen(
        [pyw, os.path.join(BASE_DIR, script)],
        cwd=BASE_DIR,
        creationflags=cflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def register_registry(enabled=True):
    try:
        import winreg
    except Exception as e:
        log(f"winreg unavailable: {e}")
        return False
    pyw = find_pythonw()
    launcher = os.path.abspath(__file__)
    cmd = f'"{pyw}" "{launcher}"'
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, "JARVIS_v5", 0, winreg.REG_SZ, cmd)
            log(f"registry autostart set: {cmd}")
        else:
            try: winreg.DeleteValue(key, "JARVIS_v5")
            except FileNotFoundError: pass
            log("registry autostart removed")
        winreg.CloseKey(key)
        return True
    except Exception as e:
        log(f"registry write failed: {e}")
        return False


def register_startup_folder(enabled=True):
    """Drop a .bat in the user's Startup folder as a redundant launcher."""
    startup = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    bat = os.path.join(startup, "JARVIS_v5.bat")
    pyw = find_pythonw()
    launcher = os.path.abspath(__file__)
    try:
        os.makedirs(startup, exist_ok=True)
        if enabled:
            content = (
                "@echo off\r\n"
                f'start "" "{pyw}" "{launcher}"\r\n'
            )
            with open(bat, "w", encoding="utf-8") as f:
                f.write(content)
            log(f"startup .bat written: {bat}")
        else:
            if os.path.exists(bat):
                os.remove(bat)
                log("startup .bat removed")
        return True
    except Exception as e:
        log(f"startup folder write failed: {e}")
        return False


def main():
    log("launcher start")

    if config.AUTO_START:
        register_registry(True)
        register_startup_folder(True)

    server_proc = spawn("server.py")
    log(f"server.py pid={server_proc.pid}")
    time.sleep(2.5)
    listener_proc = spawn("listener.py")
    log(f"listener.py pid={listener_proc.pid}")

    try:
        while True:
            time.sleep(5)
            if server_proc.poll() is not None:
                log(f"server died (rc={server_proc.returncode}) — respawning")
                server_proc = spawn("server.py")
            if listener_proc.poll() is not None:
                log(f"listener died (rc={listener_proc.returncode}) — respawning")
                listener_proc = spawn("listener.py")
    except KeyboardInterrupt:
        try: server_proc.terminate()
        except Exception: pass
        try: listener_proc.terminate()
        except Exception: pass
        log("launcher stopping (KeyboardInterrupt)")


if __name__ == "__main__":
    main()
