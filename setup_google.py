"""
One-time Google (Calendar + Gmail) OAuth setup.
Run this ONCE with regular python.exe (not pythonw) so you can see the prompt
and the browser auth flow.

Usage:
    py -3.11 C:\\Kalki\\setup_google.py
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import gcal

gcal.CRED_PATH  = os.path.join(BASE_DIR, "data", "google_credentials.json")
gcal.TOKEN_PATH = os.path.join(BASE_DIR, "data", "google_token.pickle")
os.makedirs(os.path.dirname(gcal.CRED_PATH), exist_ok=True)


def main():
    print("=" * 64)
    print(" KALKI - Google Calendar + Gmail OAuth Setup")
    print("=" * 64)

    if not os.path.exists(gcal.CRED_PATH):
        print("\n  MISSING credentials.json")
        print(f"  Expected at: {gcal.CRED_PATH}\n")
        print("  ONE-TIME SETUP STEPS:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create a project (or pick an existing one)")
        print("  3. APIs & Services -> Library:")
        print("     - Enable 'Google Calendar API'")
        print("     - Enable 'Gmail API'")
        print("  4. APIs & Services -> OAuth consent screen:")
        print("     - External, fill basics, add YOUR email as a test user")
        print("  5. APIs & Services -> Credentials -> Create Credentials")
        print("     -> OAuth client ID -> Application type: Desktop app")
        print("  6. Download JSON")
        print(f"  7. Save it as:  {gcal.CRED_PATH}")
        print("  8. Re-run this script\n")
        sys.exit(1)

    print(f"\n  Found:  {gcal.CRED_PATH}")
    print("  Opening browser for Google authorization...")
    print("  (Approve the consent screen, then this window will finish.)\n")

    try:
        creds = gcal._get_creds(interactive=True)
        print(f"  -> Token saved: {gcal.TOKEN_PATH}")
    except Exception as e:
        print(f"\n  AUTH FAILED: {e}")
        sys.exit(1)

    print("\n  Testing Calendar API ...")
    cal = gcal.today_summary()
    print(f"  {cal}")

    print("\n  Testing Gmail API ...")
    gm = gcal.gmail_summary()
    print(f"  {gm}")

    print("\n" + "=" * 64)
    print("  All set, Sir. KALKI now has Calendar + Gmail access.")
    print("=" * 64)


if __name__ == "__main__":
    main()
