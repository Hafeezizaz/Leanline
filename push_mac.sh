#!/bin/bash
# One-command commit + push for Leanline on macOS.
# Usage:  bash push_mac.sh                      -> main, auto commit message
#         bash push_mac.sh feature-x            -> branch feature-x
#         bash push_mac.sh main "My message"    -> custom message
# Safe by design: repo-local identity, never force-pushes, rebases on pull.
set -e
cd "$(dirname "$0")"

[ -d .git ] || git init -b main
git remote get-url origin >/dev/null 2>&1 || git remote add origin https://Hafeezizaz@github.com/Hafeezizaz/Leanline.git

git config user.name "Hafeez Izaz"
git config user.email "96226601+Hafeezizaz@users.noreply.github.com"
echo "Committing as: $(git config user.email)"

BRANCH="${1:-main}"
[ "$(git branch --show-current)" = "$BRANCH" ] || git checkout -B "$BRANCH"
echo "Branch: $BRANCH"

git add -A
git status --short

if ! git diff --cached --quiet; then
  N=$(git diff --cached --name-only | wc -l | tr -d ' ')
  MSG="${2:-Update Leanline ($N files, $(date +%Y-%m-%d-%H%M))}"
  echo "Commit message: $MSG"
  git commit -m "$MSG"
else
  echo "Nothing new to commit."
fi

if git fetch origin "$BRANCH" >/dev/null 2>&1; then
  git pull --rebase origin "$BRANCH"
fi

git push -u origin "$BRANCH"
echo "Done: https://github.com/Hafeezizaz/Leanline"
