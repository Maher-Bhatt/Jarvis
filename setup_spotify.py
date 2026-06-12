"""
One-time Spotify OAuth setup.
Run: py -3.11 C:\\Kalki\\setup_spotify.py
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import config
import spotify_mod

spotify_mod.CACHE_PATH = os.path.join(BASE_DIR, "data", "spotify_token.json")
os.makedirs(os.path.dirname(spotify_mod.CACHE_PATH), exist_ok=True)


def main():
    print("=" * 64)
    print(" KALKI - Spotify OAuth Setup")
    print("=" * 64)

    if not getattr(config, "SPOTIFY_CLIENT_ID", "") or \
       not getattr(config, "SPOTIFY_CLIENT_SECRET", ""):
        print("\n  MISSING Spotify credentials in config.py.")
        print("\n  ONE-TIME SETUP STEPS:")
        print("  1. Go to https://developer.spotify.com/dashboard")
        print("  2. Log in with your Spotify account")
        print("  3. Create app -> name: KALKI, description anything")
        print("  4. Set Redirect URI: http://127.0.0.1:8889/callback")
        print("  5. Copy Client ID and Client Secret")
        print("  6. Add to C:\\Kalki\\config.py:")
        print("     SPOTIFY_CLIENT_ID     = 'paste_id_here'")
        print("     SPOTIFY_CLIENT_SECRET = 'paste_secret_here'")
        print("     SPOTIFY_REDIRECT_URI  = 'http://127.0.0.1:8889/callback'")
        print("  7. Re-run this script\n")
        sys.exit(1)

    print(f"\n  Found credentials. Token cache: {spotify_mod.CACHE_PATH}")
    print("  Opening browser for Spotify authorization...\n")

    try:
        sp = spotify_mod._client(interactive=True)
        user = sp.current_user()
        print(f"  -> Authorized as: {user.get('display_name','?')} "
              f"({user.get('email','?')})")
    except Exception as e:
        print(f"\n  AUTH FAILED: {e}")
        sys.exit(1)

    print("\n" + "=" * 64)
    print("  Spotify linked. Try: 'Hey KALKI play lo-fi'")
    print("=" * 64)


if __name__ == "__main__":
    main()
