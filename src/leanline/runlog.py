"""Append-only JSONL run log: one line per tool call, used for the savings report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .tokens import tokenizer_name


def make_record(
    tool: str,
    task_type: str,
    source_paths: list[str],
    raw_tokens: int,
    returned_tokens: int,
    dropped: str = "",
    full: bool = False,
    raw_bytes: int = 0,
) -> dict:
    """Build one log record. saved_tokens may be negative: we keep it, never clamp it."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "task_type": task_type,
        "source_paths": list(source_paths),
        "raw_bytes": raw_bytes,
        "raw_tokens": raw_tokens,
        "returned_tokens": returned_tokens,
        "saved_tokens": raw_tokens - returned_tokens,
        "dropped": dropped,
        "full": full,
        "tokenizer": tokenizer_name(),
    }


def append(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_runs(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    runs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue  # skip a torn or corrupt line
    return runs
