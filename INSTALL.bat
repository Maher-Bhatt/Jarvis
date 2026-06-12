@echo off
title KALKI v5 - Installer
color 0B
echo.
echo ============================================================
echo   KALKI v5 - Installing Dependencies
echo ============================================================
echo.
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install SpeechRecognition pyaudio edge-tts pygame psutil pywin32 Pillow pycaw comtypes requests
echo.
echo ============================================================
echo   Done!  Now do this:
echo   1. Open config.py in Notepad
echo   2. Paste your Groq API key (get free at console.groq.com)
echo   3. Run START.bat
echo ============================================================
echo.
pause
