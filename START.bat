@echo off
title KALKI v5
color 0B
echo.
echo ============================================================
echo   KALKI v5 - Starting
echo ============================================================
echo.
echo Starting KALKI server...
start /B py -3.11 server.py
timeout /t 2 /nobreak >nul
echo Starting wake word listener...
start /B py -3.11 listener.py
echo.
echo KALKI is running.  Say "Hey KALKI" to activate.
echo Close this window to stop KALKI.
echo.
pause
