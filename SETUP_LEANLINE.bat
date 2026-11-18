@echo off
setlocal
cd /d "%~dp0"

rem ---- One-click setup for Leanline on a new Windows machine ----
rem Needs: Python 3.10+ and Git already installed.
rem Does: create .venv, install Leanline, run the tests, register it in Claude Desktop.

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if "%PY%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if "%PY%"=="" (
  echo Python was not found. Install Python 3.10 or newer from python.org, tick "Add to PATH", then run this again.
  pause
  exit /b 1
)

echo [1/4] Creating virtual environment...
%PY% -m venv .venv
if errorlevel 1 (
  echo Could not create the virtual environment.
  pause
  exit /b 1
)

echo [2/4] Installing Leanline and its dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 (
  echo Install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

echo [3/4] Running tests...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 echo Some tests failed. Setup continues, but tell Claude which ones failed.

echo [4/4] Registering Leanline in Claude Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_claude_desktop.ps1"

echo.
echo Setup finished. Fully quit Claude Desktop (tray icon, Quit) and reopen it.
echo Then ask Claude: "Use leanline read_relevant on <folder> to answer: <question>"
pause
