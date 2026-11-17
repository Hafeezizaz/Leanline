"""compact(): shrink logs, JSON, HTML and plain text. Every function returns
(compacted_text, dropped_description) so the caller can always say what was lost."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .extract.logs import HIGH, LEVEL_RE, TS_RE, parse_log, summary_line

KINDS = ("log", "json", "html", "text")

LOG_SAMPLE_LINES = 12
MAX_ERROR_GROUPS = 50
TOP_OTHER = 10

JSON_SAMPLES = 2
JSON_STR_MAX = 80
JSON_MAX_KEYS = 40
JSON_MAX_DEPTH = 6

HTML_DROP_TAGS = ["script", "style", "nav", "header", "footer", "aside", "noscript", "svg", "form", "iframe"]


def detect_kind(text: str, name: str = "") -> str:
    ext = Path(name).suffix.lower() if name else ""
    if ext == ".json":
        return "json"
    if ext in (".html", ".htm"):
        return "html"
    if ext == ".log":
        return "log"
    head = text.lstrip()[:2000]
    if head[:1] in ("{", "["):
        try:
            json.loads(text)
            return "json"
        except ValueError:
            pass
    if re.search(r"<\s*(!doctype html|html|body|div|p)\b", head, re.I):
        return "html"
    lines = [ln for ln in text.splitlines()[:200] if ln.strip()]
    if lines:
        hits = sum(1 for ln in lines if TS_RE.search(ln[:60]) or LEVEL_RE.search(ln[:60]))
        if hits / len(lines) >= 0.3:
            return "log"
    return "text"


def compact_log(text: str) -> tuple[str, str]:
    data = parse_log(text)
    high = [g for g in data.groups if g.level in HIGH]
    other = sorted((g for g in data.groups if g.level not in HIGH), key=lambda g: -g.count)
    shown = high[:MAX_ERROR_GROUPS]

    out = ["== Log summary ==", summary_line(data), "", f"== Errors and warnings: {len(high)} distinct patterns =="]
    for g in shown:
        span = f"{g.first_ts} -> {g.last_ts}" if g.first_ts else "no timestamp"
        out.append(f"[{g.level}] x{g.count} ({span})")
        sample = g.sample.splitlines()
        out.extend("  " + ln for ln in sample[:LOG_SAMPLE_LINES])
        if len(sample) > LOG_SAMPLE_LINES:
            out.append(f"  ... {len(sample) - LOG_SAMPLE_LINES} more lines")
    n_other = min(TOP_OTHER, len(other))
    out.append("")
    out.append(f"== Other patterns: {len(other)} distinct (top {n_other}) ==")
    for g in other[:n_other]:
        out.append(f"x{g.count} [{g.level}] {g.signature}")

    parts = []
    repeats = sum(g.count - 1 for g in shown)
    if repeats:
        parts.append(f"{repeats} repeated error/warning entries (first sample of each pattern kept)")
    if len(high) > len(shown):
        parts.append(f"{len(high) - len(shown)} further error/warning patterns")
    other_entries = sum(g.count for g in other)
    if other_entries:
        parts.append(
            f"{other_entries} non-error entries collapsed into {len(other)} patterns "
            f"(top {n_other} shown, one-line signature only)"
        )
    parts.append(f"stack/sample lines beyond {LOG_SAMPLE_LINES} per pattern")
    return "\n".join(out), "; ".join(parts)


def _shrink(o, depth: int, st: dict):
    if depth > JSON_MAX_DEPTH:
        st["depth"] += 1
        return "..."
    if isinstance(o, dict):
        items = list(o.items())
        out = {k: _shrink(v, depth + 1, st) for k, v in items[:JSON_MAX_KEYS]}
        if len(items) > JSON_MAX_KEYS:
            st["keys"] += len(items) - JSON_MAX_KEYS
            out["..."] = f"+{len(items) - JSON_MAX_KEYS} more keys"
        return out
    if isinstance(o, list):
        if len(o) <= JSON_SAMPLES + 1:
            return [_shrink(x, depth + 1, st) for x in o]
        st["items"] += len(o) - JSON_SAMPLES
        shown = [_shrink(x, depth + 1, st) for x in o[:JSON_SAMPLES]]
        shown.append(f"... +{len(o) - JSON_SAMPLES} more items (of {len(o)})")
        return shown
    if isinstance(o, str) and len(o) > JSON_STR_MAX:
        st["strings"] += 1
        return o[:JSON_STR_MAX] + f"...(+{len(o) - JSON_STR_MAX} chars)"
    return o


def compact_json(text: str) -> tuple[str, str]:
    try:
        obj = json.loads(text)
    except ValueError:
        out, dropped = compact_plain(text)
        return out, "input is not valid JSON, treated as text; " + dropped
    st = {"items": 0, "strings": 0, "keys": 0, "depth": 0}
    out = json.dumps(_shrink(obj, 0, st), indent=1, ensure_ascii=False, default=str)
    parts = [f"lists cut to {JSON_SAMPLES} sample items ({st['items']} items omitted)"]
    if st["strings"]:
        parts.append(f"{st['strings']} strings cut at {JSON_STR_MAX} chars")
    if st["keys"]:
        parts.append(f"{st['keys']} object keys beyond {JSON_MAX_KEYS}")
    if st["depth"]:
        parts.append(f"{st['depth']} values deeper than level {JSON_MAX_DEPTH}")
    return out, "; ".join(parts)


def compact_html(text: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for t in soup(HTML_DROP_TAGS):
        t.decompose()
    root, root_name = soup, "document"
    for name in ("main", "article", "body"):
        found = soup.find(name)
        if found is not None:
            root, root_name = found, f"<{name}>"
            break
    lines = [ln.strip() for ln in root.get_text("\n").splitlines()]
    body = "\n".join(ln for ln in lines if ln)
    out = (f"Title: {title}\n\n" if title else "") + body
    return out, (
        f"all markup, links and attributes; script/style/nav/header/footer/aside/form blocks; kept text of {root_name}"
    )


def compact_plain(text: str) -> tuple[str, str]:
    out: list[str] = []
    prev = None
    run = 0
    dup = 0
    blanks = 0

    def flush() -> None:
        if prev is not None and run > 1:
            out.append(f"  (line repeated x{run})")

    for line in text.splitlines():
        if not line.strip():
            blanks += 1
            continue
        if line == prev:
            run += 1
            dup += 1
            continue
        flush()
        out.append(line)
        prev, run = line, 1
    flush()
    return "\n".join(out), f"{dup} consecutive duplicate lines and {blanks} blank lines collapsed"


def compact_text(text: str, kind: str) -> tuple[str, str]:
    if not text.strip():
        return "(empty input)", "nothing"
    if kind == "log":
        return compact_log(text)
    if kind == "json":
        return compact_json(text)
    if kind == "html":
        return compact_html(text)
    return compact_plain(text)
