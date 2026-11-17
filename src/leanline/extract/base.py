from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Section:
    ordinal: int
    heading_path: str
    level: int
    text: str


@dataclass
class LogGroup:
    signature: str
    level: str
    count: int
    first_ts: str
    last_ts: str
    sample: str


@dataclass
class Extracted:
    kind: str
    text: str  # full extracted text; its token count is the "read it whole" baseline
    sections: list[Section] = field(default_factory=list)
    terms: list[tuple[str, int]] = field(default_factory=list)  # (term, section ordinal)
    links: list[tuple[int, str]] = field(default_factory=list)  # (section ordinal, target)
    log_groups: list[LogGroup] = field(default_factory=list)
