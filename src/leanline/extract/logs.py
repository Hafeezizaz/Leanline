"""Log parsing: group entries by normalised signature; used by the extractor and by compact()."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .base import Extracted, LogGroup, Section

TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|ERR|SEVERE|FATAL|CRITICAL)\b")
LEVEL_MAP = {"WARNING": "WARN", "ERR": "ERROR", "SEVERE": "ERROR", "CRITICAL": "FATAL", "NOTICE": "INFO"}
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
NUM_RE = re.compile(r"\d+")
BAD_RE = re.compile(r"(?i)\b(exception|traceback|error|failed|fatal)\b")
# Lines that continue the previous entry (stack traces and similar).
CONT_RE = re.compile(
    r"^(\s+\S|Traceback \(most recent|Caused by:|Exception in thread|[\w.$]+(?:Error|Exception)(?::|\s|$))"
)

HIGH = {"ERROR", "FATAL", "WARN"}
SAMPLE_LINES = 15


@dataclass
class LogData:
    total_lines: int
    entries: int
    first_ts: str
    last_ts: str
    level_counts: dict
    groups: list  # list[LogGroup], in order of first appearance


def signature(first_line: str) -> str:
    s = TS_RE.sub("", first_line)
    s = LEVEL_RE.sub("", s, count=1)
    s = UUID_RE.sub("<UUID>", s)
    s = IP_RE.sub("<IP>", s)
    s = HEX_RE.sub("<HEX>", s)
    s = NUM_RE.sub("<N>", s)
    s = re.sub(r"\s+", " ", s).strip(" -:[]|")
    return (s or "(empty)")[:200]


def parse_log(text: str) -> LogData:
    lines = text.splitlines()
    entries: list[list] = []  # [first_line, level, ts, continuation_lines]
    for line in lines:
        if not line.strip():
            continue
        head = line[:60]
        ts_m = TS_RE.search(head)
        lv_m = LEVEL_RE.search(head)
        if entries and not ts_m and CONT_RE.match(line):
            entries[-1][3].append(line)
            continue
        level = None
        if lv_m:
            level = LEVEL_MAP.get(lv_m.group(1), lv_m.group(1))
        entries.append([line, level, ts_m.group(0) if ts_m else "", []])

    groups: dict[tuple[str, str], LogGroup] = {}
    counts: Counter = Counter()
    first_ts = last_ts = ""
    for first, level, ts, extra in entries:
        if level is None:
            level = "ERROR" if BAD_RE.search(first) else "UNKNOWN"
        counts[level] += 1
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        key = (level, signature(first))
        g = groups.get(key)
        if g is None:
            sample = "\n".join([first[:300]] + [x[:300] for x in extra[: SAMPLE_LINES - 1]])
            groups[key] = LogGroup(key[1], level, 1, ts, ts, sample)
        else:
            g.count += 1
            if ts:
                g.last_ts = ts
                if not g.first_ts:
                    g.first_ts = ts
    return LogData(len(lines), len(entries), first_ts, last_ts, dict(counts), list(groups.values()))


def summary_line(data: LogData) -> str:
    span = f"{data.first_ts} -> {data.last_ts}" if data.first_ts else "n/a"
    levels = ", ".join(f"{k}={v}" for k, v in sorted(data.level_counts.items())) or "none"
    return (
        f"Lines: {data.total_lines}\nEntries: {data.entries}\nTime range: {span}\n"
        f"Levels: {levels}\nDistinct patterns: {len(data.groups)}"
    )


def extract_log(text: str) -> Extracted:
    data = parse_log(text)
    sections = [Section(0, "Summary", 1, summary_line(data))]
    high = sorted((g for g in data.groups if g.level in HIGH), key=lambda g: -g.count)
    for g in high[:200]:
        span = f"{g.first_ts} -> {g.last_ts}" if g.first_ts else "n/a"
        body = f"Level: {g.level}\nCount: {g.count}\nSeen: {span}\nSample:\n{g.sample}"
        sections.append(Section(len(sections), f"{g.level} x{g.count}: {g.signature[:80]}", 2, body))
    other = sorted((g for g in data.groups if g.level not in HIGH), key=lambda g: -g.count)
    if other:
        body = "\n".join(f"x{g.count} [{g.level}] {g.signature}" for g in other[:30])
        sections.append(Section(len(sections), "Other patterns", 2, body))
    return Extracted(kind="log", text=text, sections=sections, log_groups=data.groups)
