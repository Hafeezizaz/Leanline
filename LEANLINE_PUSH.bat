@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem ---- One-click commit + push for Leanline (https://github.com/Hafeezizaz/Leanline) ----
rem Usage:  LEANLINE_PUSH.bat                      -> pushes to main, auto commit message
rem         LEANLINE_PUSH.bat feature-x            -> pushes to branch feature-x
rem         LEANLINE_PUSH.bat main "My message"    -> custom commit message
rem Safe by design: repo-local identity, never force-pushes, rebases on pull.

where git >nul 2>nul
if errorlevel 1 (
  echo Git is not installed or not on PATH.
  pause
  exit /b 1
)

if not exist ".git" (
  git init -b main
  if errorlevel 1 (
    echo git init failed.
    pause
    exit /b 1
  )
)

git remote get-url origin >nul 2>nul
if errorlevel 1 git remote add origin https://Hafeezizaz@github.com/Hafeezizaz/Leanline.git

git config user.name "Hafeez Izaz"
git config user.email "96226601+Hafeezizaz@users.noreply.github.com"
for /f "delims=" %%e in ('git config user.email') do echo Committing as: %%e

set "BRANCH=main"
if not "%~1"=="" set "BRANCH=%~1"
set "CUR="
for /f "delims=" %%b in ('git branch --show-current') do set "CUR=%%b"
if /i not "!CUR!"=="!BRANCH!" git checkout -B "!BRANCH!"
echo Branch: !BRANCH!

git add -A
git status --short
echo.

set "MSG=%~2"
if "!MSG!"=="" (
  set "TS="
  for /f "delims=" %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd-HHmm"') do set "TS=%%t"
  set "N=0"
  for /f %%n in ('git diff --cached --name-only ^| find /c /v ""') do set "N=%%n"
  set "MSG=Update Leanline (!N! files, !TS!)"
)
echo Commit message: !MSG!

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "!MSG!"
  if errorlevel 1 (
    echo Commit failed.
    pause
    exit /b 1
  )
) else (
  echo Nothing new to commit.
)

git fetch origin "!BRANCH!" >nul 2>nul
if not errorlevel 1 (
  git pull --rebase origin "!BRANCH!"
  if errorlevel 1 (
    echo Rebase problem - resolve conflicts, run the tests, then run this again.
    pause
    exit /b 1
  )
)

git push -u origin "!BRANCH!"
if errorlevel 1 (
  echo Push failed.
  pause
  exit /b 1
)

echo.
echo Done: https://github.com/Hafeezizaz/Leanline
pause
