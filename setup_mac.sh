#!/bin/bash
# One-command setup for Leanline on macOS. Run:  bash setup_mac.sh
# Needs: Python 3.10+ (brew install python) and Git. Does: venv, install, tests, Claude Desktop config.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install it with: brew install python   (or from python.org)"
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Python 3.10+ is required. Found: $(python3 --version). Install a newer one: brew install python"
  exit 1
fi

echo "[1/4] Creating virtual environment..."
python3 -m venv .venv

echo "[2/4] Installing Leanline and its dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

echo "[3/4] Running tests..."
.venv/bin/python -m pytest -q || echo "Some tests failed. Setup continues; tell Claude which ones failed."

echo "[4/4] Registering Leanline in Claude Desktop..."
LEANLINE_PY="$PWD/.venv/bin/python" python3 - <<'PY'
import json, os, shutil
from pathlib import Path

cfg = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
cfg.parent.mkdir(parents=True, exist_ok=True)
data = {}
if cfg.exists():
    shutil.copy(cfg, str(cfg) + ".bak")  # backup before touching it
    text = cfg.read_text(encoding="utf-8").strip()
    if text:
        data = json.loads(text)
data.setdefault("mcpServers", {})["leanline"] = {
    "command": os.environ["LEANLINE_PY"],
    "args": ["-m", "leanline", "serve"],
}
cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Updated {cfg}")
PY

echo
echo "Setup finished. Fully quit Claude Desktop (Cmd+Q) and reopen it."
echo 'Then ask Claude: "Use leanline read_relevant on <folder> to answer: <question>"'
