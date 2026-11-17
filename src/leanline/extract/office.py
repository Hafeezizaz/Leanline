"""Extractors for .docx, .pptx and .pdf. Each converts content to markdown-like text, then
reuses the markdown section splitter. Third-party imports are lazy so the rest of the
package works without them."""

from __future__ import annotations

import re
from pathlib import Path

from .base import Extracted
from .markdown import extract_markdown


def extract_docx(path: Path) -> Extracted:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(str(path))
    lines: list[str] = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"Heading (\d)", style)
            if m:
                lines.append("#" * min(int(m.group(1)), 6) + " " + t)
            elif style == "Title":
                lines.append("# " + t)
            else:
                lines.append(t)
            lines.append("")
        elif tag == "tbl":
            tbl = Table(child, d)
            for row in tbl.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                lines.append(" | ".join(cells))
            lines.append("")
    return extract_markdown("\n".join(lines), "docx")


def extract_pptx(path: Path) -> Extracted:
    from pptx import Presentation

    prs = Presentation(str(path))
    lines: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        title_shape = slide.shapes.title
        title = ""
        if title_shape is not None and title_shape.has_text_frame:
            title = title_shape.text_frame.text.strip()
        lines.append(f"# Slide {i}" + (f": {title}" if title else ""))
        if title:
            lines.append(title)
        for shape in slide.shapes:
            if title_shape is not None and shape == title_shape:
                continue
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    lines.append(t)
            elif getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    lines.append(" | ".join(c.text.strip() for c in row.cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            n = slide.notes_slide.notes_text_frame.text.strip()
            if n:
                lines.append("Notes: " + n)
        lines.append("")
    return extract_markdown("\n".join(lines), "pptx")


def extract_pdf(path: Path) -> Extracted:
    from pypdf import PdfReader

    r = PdfReader(str(path))
    if r.is_encrypted:
        r.decrypt("")  # raises if a password is required; ingestion reports the file as skipped
    lines: list[str] = []
    for i, page in enumerate(r.pages, 1):
        t = (page.extract_text() or "").strip()
        if t:
            lines.append(f"# Page {i}")
            lines.append(t)
            lines.append("")
    return extract_markdown("\n".join(lines), "pdf")
