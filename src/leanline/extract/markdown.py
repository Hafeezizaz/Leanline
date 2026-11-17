"""Markdown / plain-text extractor. Also used by the docx, pptx and pdf extractors,
which first convert their content to markdown-like text."""

from __future__ import annotations

import re

from .base import Extracted, Section

MAX_WORDS = 500  # sections longer than this are split into parts

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

TERM_RES = [
    # **Term**: definition   /   **Term** - definition
    re.compile(r"\*\*([^*\n]{2,60})\*\*\s*(?:[:—–]|-)\s+\S"),
    # "Term" means ...
    re.compile(r"[\"“]([A-Z][\w \-/]{1,50}?)[\"”]\s+(?:means|refers to|is defined as|shall mean)"),
]
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SEC_REF_RE = re.compile(r"\b[Ss]ections?\s+(\d+(?:\.\d+)*)")


def _slices(body: str) -> list[str]:
    """Split a long body into chunks of at most ~MAX_WORDS words on paragraph/line boundaries."""
    if len(body.split()) <= MAX_WORDS:
        return [body]
    units: list[str] = []
    for para in body.split("\n\n"):
        if len(para.split()) <= MAX_WORDS:
            units.append(para)
            continue
        for line in para.split("\n"):
            words = line.split()
            if len(words) <= MAX_WORDS:
                units.append(line)
            else:
                for i in range(0, len(words), MAX_WORDS):
                    units.append(" ".join(words[i : i + MAX_WORDS]))
    chunks: list[str] = []
    cur: list[str] = []
    n = 0
    for u in units:
        w = len(u.split())
        if cur and n + w > MAX_WORDS:
            chunks.append("\n\n".join(cur))
            cur, n = [], 0
        cur.append(u)
        n += w
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def split_sections(text: str, preamble: str = "(intro)") -> list[Section]:
    raw: list[tuple[str, int, str]] = []  # (heading_path, level, body)
    stack: list[tuple[int, str]] = []
    path, level = preamble, 0
    buf: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            raw.append((path, level, "\n".join(buf).strip()))
            lvl = len(m.group(1))
            title = m.group(2).strip() or "(untitled)"
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, title))
            path = " > ".join(t for _, t in stack)
            level = lvl
            buf = []
        else:
            buf.append(line)
    raw.append((path, level, "\n".join(buf).strip()))

    sections: list[Section] = []
    for hp, lvl, body in raw:
        if not body:
            continue
        parts = _slices(body)
        for k, part in enumerate(parts, 1):
            p = hp if len(parts) == 1 else f"{hp} (part {k})"
            sections.append(Section(len(sections), p, lvl, part))
    if not sections and text.strip():
        sections.append(Section(0, "(document)", 0, text.strip()))
    return sections


def extract_markdown(text: str, kind: str = "markdown") -> Extracted:
    sections = split_sections(text, preamble="(text)" if kind == "text" else "(intro)")
    terms: list[tuple[str, int]] = []
    links: list[tuple[int, str]] = []
    seen: set[str] = set()
    for s in sections:
        for rx in TERM_RES:
            for m in rx.finditer(s.text):
                name = m.group(1).strip()
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    terms.append((name, s.ordinal))
        for m in MD_LINK_RE.finditer(s.text):
            links.append((s.ordinal, m.group(1)))
        for m in SEC_REF_RE.finditer(s.text):
            links.append((s.ordinal, m.group(1)))
    return Extracted(kind=kind, text=text, sections=sections, terms=terms, links=links)
