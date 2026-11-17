"""File extractors. extract_file() dispatches on extension."""

from __future__ import annotations

from pathlib import Path

from .base import Extracted, LogGroup, Section
from .logs import extract_log
from .markdown import extract_markdown
from .office import extract_docx, extract_pdf, extract_pptx

EXT_KIND = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".log": "log",
    ".docx": "docx",
    ".pptx": "pptx",
    ".pdf": "pdf",
}
SUPPORTED_EXTS = set(EXT_KIND)

__all__ = ["Extracted", "LogGroup", "Section", "EXT_KIND", "SUPPORTED_EXTS", "extract_file", "read_text"]


def read_text(path: Path) -> str:
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")  # never fails; good enough for legacy Windows text


def extract_file(path) -> Extracted:
    p = Path(path)
    kind = EXT_KIND.get(p.suffix.lower())
    if kind is None:
        raise ValueError(f"unsupported file type '{p.suffix}'")
    if kind in ("markdown", "text"):
        return extract_markdown(read_text(p), kind)
    if kind == "log":
        return extract_log(read_text(p))
    if kind == "docx":
        return extract_docx(p)
    if kind == "pptx":
        return extract_pptx(p)
    return extract_pdf(p)
