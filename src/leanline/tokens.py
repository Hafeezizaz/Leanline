"""Token counting. One fixed local tokenizer so every reported number is comparable.

Uses tiktoken (cl100k_base) when it loads; otherwise falls back to characters/4.
Either way this is an *estimate* of any given model's token count.
"""

from __future__ import annotations

import math

_enc = None
_name: str | None = None


def _load() -> None:
    global _enc, _name
    if _name is not None:
        return
    try:
        import tiktoken

        _enc = tiktoken.get_encoding("cl100k_base")
        _name = "tiktoken:cl100k_base"
    except Exception:  # missing package, or encoding file not downloadable offline
        _enc = None
        _name = "approx:chars/4"


def tokenizer_name() -> str:
    _load()
    return _name or "approx:chars/4"


def count_tokens(text: str) -> int:
    if not text:
        return 0
    _load()
    if _enc is not None:
        return len(_enc.encode(text, disallowed_special=()))
    return math.ceil(len(text) / 4)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Longest prefix of text whose token count is <= max_tokens (binary search on chars)."""
    if max_tokens <= 0:
        return ""
    if count_tokens(text) <= max_tokens:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_tokens(text[:mid]) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]
