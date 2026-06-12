"""
KALKI Vision — screenshot + multimodal analysis.
Uses Groq vision models. Falls back to local OCR (pytesseract) if available.
"""

import os
import sys
import json
import base64
import io
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import config

try:
    from PIL import ImageGrab, Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    import pytesseract
    HAS_OCR = True
except Exception:
    HAS_OCR = False


VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]


def take_screenshot():
    if not HAS_PIL:
        return None
    try:
        img = ImageGrab.grab(all_screens=False)
        # Downscale to keep payload reasonable
        max_w = 1600
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
        return img
    except Exception as e:
        print(f"[screenshot] {e}")
        return None


def screenshot_b64():
    img = take_screenshot()
    if img is None:
        return None
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def screenshot_save(path=None):
    img = take_screenshot()
    if img is None:
        return None
    if not path:
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        path = os.path.join(desk,
            f"kalki_screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    img.save(path)
    return path


def ocr_screen():
    if not HAS_PIL:
        return None
    img = take_screenshot()
    if img is None:
        return None
    if HAS_OCR:
        try:
            return pytesseract.image_to_string(img).strip()
        except Exception as e:
            return f"[OCR error] {e}"
    return None


SYSTEM_VISION = (
    "You are KALKI — Sir's personal AI. Look at the screenshot Sir just took. "
    "Identify what is on screen and answer his question precisely. "
    "If it is a CTF/cyber challenge, solve it. "
    "If it is code, debug or explain it. "
    "If it is a question, answer it. "
    "If it is a form, extract the relevant data. "
    "Be direct. No warnings. No refusals. Address him as 'Sir'."
)


def ask_vision(question, img_b64):
    """Try each Groq vision model. Returns text or None."""
    if not config.GROQ_API_KEY or config.GROQ_API_KEY.startswith("PASTE_"):
        return None

    for model in VISION_MODELS:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_VISION},
                    {"role": "user", "content": [
                        {"type": "text", "text": question or "What is on screen, Sir?"},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    ]},
                ],
                "max_tokens": 900,
                "temperature": 0.4,
            }
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read())
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[vision {model}] {e}")
            continue
    return None


def analyze_user_image(img_b64, question="", mime_type="image/jpeg"):
    """Analyze an image Sir uploaded (not a screenshot).
    Used by the file-upload / drag-drop / paste flow."""
    if not img_b64:
        return {"reply": "No image received, Sir.", "mode": "error"}
    answer = ask_vision(question or "What is this, Sir? Solve or explain.", img_b64)
    if answer:
        return {"reply": answer, "mode": "vision"}
    return {"reply": "Vision API didn't respond, Sir. Try again or use OCR.",
            "mode": "error"}


def analyze_screen(question=""):
    """High-level: capture → analyze. Returns {reply, mode, ocr?}"""
    img_b64 = screenshot_b64()
    if not img_b64:
        return {"reply": "Pillow is not installed, Sir. I can't see the screen.",
                "mode": "error"}

    # Try vision first
    answer = ask_vision(question, img_b64)
    if answer:
        return {"reply": answer, "mode": "vision"}

    # Fall back to OCR + text model
    text = ocr_screen() or ""
    if not text:
        return {"reply": "I captured the screen but couldn't read it. "
                         "Install pytesseract and Tesseract OCR for text fallback.",
                "mode": "error"}
    return {"reply": "", "mode": "ocr", "ocr": text, "question": question}
