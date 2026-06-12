"""
Read the URL of the active browser tab via Windows UI Automation.

Lets KALKI act on "scan THIS website" — it grabs whatever is in the focused
browser's address bar (Chrome / Edge / Brave / Firefox). Best-effort and
never raises: returns a normalized URL string or None.
"""

import re

_URL_RE = re.compile(
    r"^(?:https?://)?"
    r"(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}"     # domain
    r"(?::\d+)?(?:[/?#]\S*)?$"
)

# Address-bar Edit controls are named like these across browsers.
_BAR_HINTS = ("address", "search", "url", "location")


def _normalize(val):
    if not val:
        return None
    val = val.strip().strip('"').split()[0] if val.strip() else ""
    if not val or " " in val:
        return None
    if not _URL_RE.match(val):
        return None
    if not val.startswith(("http://", "https://")):
        val = "https://" + val
    return val


def get_active_url():
    """Return the URL in the focused browser's address bar, or None."""
    try:
        import comtypes.client
        import win32gui
    except Exception:
        return None

    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as C
    except Exception:
        return None

    try:
        uia = comtypes.client.CreateObject(
            C.CUIAutomation, interface=C.IUIAutomation)
    except Exception:
        return None

    try:
        hwnd = win32gui.GetForegroundWindow()
        root = uia.ElementFromHandle(hwnd)
    except Exception:
        root = None
    if root is None:
        try:
            root = uia.GetFocusedElement()
        except Exception:
            return None

    try:
        cond = uia.CreatePropertyCondition(
            C.UIA_ControlTypePropertyId, C.UIA_EditControlTypeId)
        edits = root.FindAll(C.TreeScope_Descendants, cond)
    except Exception:
        return None

    best = None
    try:
        n = edits.Length
    except Exception:
        n = 0
    for i in range(n):
        try:
            el = edits.GetElement(i)
            name = (el.CurrentName or "").lower()
            pat = el.GetCurrentPattern(C.UIA_ValuePatternId)
            if not pat:
                continue
            vp = pat.QueryInterface(C.IUIAutomationValuePattern)
            val = vp.CurrentValue
        except Exception:
            continue
        url = _normalize(val)
        if not url:
            continue
        # Prefer the control that names itself an address/search bar.
        if any(h in name for h in _BAR_HINTS):
            return url
        if best is None:
            best = url
    return best
