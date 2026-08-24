@echo off
title AllotCheck (local)
cd /d "%~dp0backend"

REM ============================================================
REM  ADMIN PASSWORD (token) for the /admin dashboard.
REM  Change "changeme" below to your own secret and save.
REM  Use the SAME value on the /admin login page.
REM ============================================================
set ALLOTCHECK_ADMIN_TOKEN=Vijay@2026Secret
REM ============================================================

echo Starting AllotCheck...
echo   App    :  http://localhost:8080/
echo   Admin  :  http://localhost:8080/admin
echo A browser tab will open automatically. Close this window to stop.
echo.
python local_server.py
if errorlevel 1 python3 local_server.py
if errorlevel 1 (
  echo.
  echo Python not found. Install it from https://www.python.org/downloads/
  echo and tick "Add Python to PATH" during setup.
  pause
)
