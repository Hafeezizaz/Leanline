@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem ---- One-click commit + push for Leanline (https://github.com/Hafeezizaz/Leanline) ----
rem Safe by design: sets the repo-local identity, never force-pushes, rebases on pull.

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

rem Repo-local identity only (never global, never a work email).
git config user.name "Hafeez Izaz"
git config user.email "96226601+Hafeezizaz@users.noreply.github.com"
for /f "delims=" %%e in ('git config user.email') do echo Committing as: %%e
echo.

set "BRANCH=main"
set /p BRANCH=Branch to push [main]:
if "!BRANCH!"=="" set "BRANCH=main"
set "CUR="
for /f "delims=" %%b in ('git branch --show-current') do set "CUR=%%b"
if /i not "!CUR!"=="!BRANCH!" git checkout -B "!BRANCH!"

git add -A
git status --short
echo.

set "MSG="
set /p MSG=Commit message (imperative, under 72 chars):
if "!MSG!"=="" (
  echo No message given - cancelled.
  pause
  exit /b 1
)

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
echo Done. Open a pull request on GitHub if you pushed a feature branch.
pause
