@echo off
title JARVIS v5
color 0B
echo.
echo ============================================================
echo   JARVIS v5 - Starting
echo ============================================================
echo.
echo Starting JARVIS server...
start /B py -3.11 server.py
timeout /t 2 /nobreak >nul
echo Starting wake word listener...
start /B py -3.11 listener.py
echo.
echo JARVIS is running.  Say "Hey JARVIS" to activate.
echo Close this window to stop JARVIS.
echo.
pause
