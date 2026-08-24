@echo off
title AllotCheck (local)
cd /d "%~dp0backend"

REM ============================================================
REM  ADMIN TOKEN for the /admin dashboard.
REM  NEVER hard-code a secret in this file (it is committed to git).
REM  Set it in your shell BEFORE running:
REM     set ALLOTCHECK_ADMIN_TOKEN=your-strong-secret      (this window only)
REM     setx ALLOTCHECK_ADMIN_TOKEN "your-strong-secret"   (persists; reopen shell)
REM  On Render: Dashboard -> your service -> Environment -> add the variable.
REM  Use the SAME value on the /admin login page.
REM ============================================================
if "%ALLOTCHECK_ADMIN_TOKEN%"=="" (
  echo [warn] ALLOTCHECK_ADMIN_TOKEN is not set - the /admin dashboard is disabled.
  echo        Set it first, e.g.:  set ALLOTCHECK_ADMIN_TOKEN=your-strong-secret
  echo.
)

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
