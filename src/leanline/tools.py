"""Engine: the logic behind the MCP tools. server.py is a thin wrapper around this."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from . import runlog
from .compact import KINDS, compact_text, detect_kind
from .extract import EXT_KIND, SUPPORTED_EXTS, extract_file, read_text
from .graph import Graph
from .tokens import count_tokens, tokenizer_name, truncate_to_tokens

MAX_FILE_BYTES = 50 * 1024 * 1024
MORE_SECTIONS_SHOWN = 15

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "was", "were", "be",
    "how", "what", "which", "who", "when", "where", "why", "do", "does", "did", "i", "we", "you", "it",
    "this", "that", "these", "those", "me", "my", "our", "can", "could", "should", "would", "about", "from",
    "by", "at", "as", "any", "all", "there", "their", "tell", "show", "give",
}

TASK_TYPE = {"log": "logs", "json": "data", "html": "web", "text": "documents"}


def default_home() -> Path:
    return Path(os.environ.get("LEANLINE_HOME") or (Path.home() / ".leanline"))


def match_query(question: str) -> str:
    """Turn a natural-language question into an FTS5 OR query of quoted terms."""
    terms: list[str] = []
    for w in re.findall(r"[A-Za-z0-9_]+", question.lower()):
        if len(w) < 2 or w in STOPWORDS:
            continue
        terms.append(w)
        if w.endswith("s") and len(w) > 3:
            terms.append(w[:-1])
    uniq = list(dict.fromkeys(terms))
    return " OR ".join(f'"{t}"' for t in uniq)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def footer(returned: int, raw: int, dropped: str = "") -> str:
    saved = raw - returned
    pct = (100.0 * saved / raw) if raw else 0.0
    s = (
        f"\n\n[leanline] returned ~{returned} tokens; raw source ~{raw} tokens; "
        f"saved ~{saved} ({pct:.0f}%); tokenizer={tokenizer_name()}"
    )
    if dropped:
        s += f"\n[leanline] dropped: {dropped}"
    return s


def finish(body: str, raw: int, dropped: str = "") -> tuple[str, int]:
    """Append the footer and return (final_text, returned_tokens). returned_tokens is the
    token count of body plus footer, so the footer's own cost is included (+/- 1 token)."""
    total = count_tokens(body + footer(count_tokens(body), raw, dropped))
    return body + footer(total, raw, dropped), total


class Engine:
    def __init__(self, home=None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.graph = Graph(self.home / "graph.db")
        self.runs_path = self.home / "runs.jsonl"

    # ---- ingestion --------------------------------------------------------------

    def _collect(self, p: Path) -> list[Path]:
        if p.is_file():
            return [p]
        files: list[Path] = []
        for root, dirs, names in os.walk(p):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in {"node_modules", "__pycache__"})
            for n in sorted(names):
                if n.startswith("~$"):
                    continue
                if Path(n).suffix.lower() in SUPPORTED_EXTS:
                    files.append(Path(root) / n)
        return files

    def ingest(self, path) -> tuple[list[int], list[str]]:
        """Extract new or changed files into the graph. Returns (file ids, notes)."""
        p = Path(path).expanduser()
        ids: list[int] = []
        notes: list[str] = []
        for f in self._collect(p):
            try:
                size = f.stat().st_size
                if size > MAX_FILE_BYTES:
                    notes.append(f"Skipped {f.name}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
                    continue
                key = str(f.resolve())
                h = _sha256(f)
                row = self.graph.get_file(key)
                if row is not None and row["content_hash"] == h:
                    ids.append(row["id"])
                    continue
                ex = extract_file(f)
                raw_tokens = count_tokens(ex.text)
                ids.append(self.graph.upsert_file(key, h, size, raw_tokens, ex))
            except Exception as e:  # corrupt, encrypted, unsupported ...
                notes.append(f"Skipped {f.name}: {e}")
        return ids, notes

    def _log(self, tool, task_type, infos, raw, returned, dropped="", full=False):
        rec = runlog.make_record(
            tool,
            task_type,
            [i["path"] for i in infos],
            raw,
            returned,
            dropped=dropped,
            full=full,
            raw_bytes=sum(i["size_bytes"] for i in infos),
        )
        runlog.append(self.runs_path, rec)

    @staticmethod
    def _task_type(infos: list[dict]) -> str:
        return "logs" if infos and all(i["kind"] == "log" for i in infos) else "documents"

    # ---- tools ------------------------------------------------------------------

    def read_relevant(self, path_or_folder: str, question: str, max_tokens: int = 2000, section: str = "") -> str:
        p = Path(path_or_folder).expanduser()
        if not p.exists():
            return f"Path not found: {path_or_folder}"
        ids, notes = self.ingest(p)
        if not ids:
            msg = f"No supported files found (supported: {', '.join(sorted(SUPPORTED_EXTS))})."
            return msg + ("\n" + "\n".join(notes) if notes else "")
        infos = self.graph.file_infos(ids)
        raw = sum(i["raw_tokens"] for i in infos)
        names = {i["path"]: Path(i["path"]).name for i in infos}

        rows = self.graph.sections_matching(ids, section) if section else self.graph.search(match_query(question), ids)

        chosen: list[tuple[dict, str, bool]] = []
        rest: list[dict] = []
        used = 0
        for r in rows:
            if used + r["tokens"] <= max_tokens:
                chosen.append((r, r["text"], False))
                used += r["tokens"]
            elif not chosen:
                chosen.append((r, truncate_to_tokens(r["text"], max_tokens), True))
                used = max_tokens
            else:
                rest.append(r)

        parts: list[str] = []
        truncated = False
        if not chosen:
            what = f"section '{section}'" if section else "your question"
            parts.append(f"No section matched {what}. Sections available:")
            for o in self.graph.outline(ids):
                parts.append(f"- {Path(o['path']).name} > {o['heading_path']} (~{o['tokens']} tokens)")
            parts.append('Retry with different keywords, or request one by name with section="...".')
        else:
            for r, text, was_cut in sorted(chosen, key=lambda c: (c[0]["path"], c[0]["ordinal"])):
                parts.append(f"### {names[r['path']]} > {r['heading_path']}  (~{r['tokens']} tokens)\n{text}")
                if was_cut:
                    truncated = True
                    parts.append(
                        f'[truncated to fit max_tokens; request section="{r["heading_path"]}" with a larger max_tokens]'
                    )
            if rest:
                parts.append("More sections (not shown; request with section=\"<name>\"):")
                for r in rest[:MORE_SECTIONS_SHOWN]:
                    parts.append(f"- {names[r['path']]} > {r['heading_path']} (~{r['tokens']} tokens)")
                if len(rest) > MORE_SECTIONS_SHOWN:
                    parts.append(f"- ... and {len(rest) - MORE_SECTIONS_SHOWN} more")
        if notes:
            parts.extend(notes)

        dropped = f"{len(rest)} other matching sections not shown"
        if truncated:
            dropped += "; first section truncated"
        text, returned = finish("\n\n".join(parts), raw, dropped)
        self._log("read_relevant", self._task_type(infos), infos, raw, returned, dropped)
        return text

    def _load_input(self, file_or_text: str):
        """Return (text, name, source_infos). Treats short single-line input as a path if it exists."""
        s = file_or_text
        p = None
        if len(s) < 1024 and "\n" not in s:
            try:
                cand = Path(s).expanduser()
                if cand.is_file():
                    p = cand
            except (OSError, ValueError):
                p = None  # not a usable path: treat the input as text
        if p is None:
            return s, "", [{"path": "(inline text)", "size_bytes": len(s.encode("utf-8")), "kind": "raw"}]
        if EXT_KIND.get(p.suffix.lower()) in ("docx", "pptx", "pdf"):
            raise ValueError("compact handles logs, JSON, HTML and text; use read_relevant for documents")
        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError("file is larger than 50 MB")
        return read_text(p), p.name, [{"path": str(p.resolve()), "size_bytes": size, "kind": "raw"}]

    def compact(self, file_or_text: str, kind: str = "auto", full: bool = False) -> str:
        try:
            text, name, infos = self._load_input(file_or_text)
        except ValueError as e:
            return f"Error: {e}"
        raw = count_tokens(text)
        k = detect_kind(text, name) if kind == "auto" else kind
        if k not in KINDS:
            return f"Unknown kind '{kind}'. Use one of: auto, {', '.join(KINDS)}."
        if full:
            body, dropped = text, "nothing (full=true)"
        else:
            body, dropped = compact_text(text, k)
        out, returned = finish(body, raw, dropped)
        self._log("compact", TASK_TYPE[k], infos, raw, returned, dropped, full)
        return out

    def remember(self, path: str, digest: str) -> str:
        p = Path(path).expanduser()
        if not p.is_file():
            return f"File not found: {path}"
        h = _sha256(p)
        self.graph.set_digest(str(p.resolve()), h, digest)
        return f"Stored digest for {p.name} (content hash {h[:12]}). It stays valid while the file is unchanged."

    def recall(self, path: str) -> str:
        p = Path(path).expanduser()
        if not p.is_file():
            return f"File not found: {path}"
        key = str(p.resolve())
        row = self.graph.get_digest(key)
        if row is None:
            return f"No digest stored for {p.name}. Read the file, then call remember."
        if row["content_hash"] != _sha256(p):
            return f"Digest for {p.name} is stale: the file changed since it was stored. Re-read it and call remember again."
        ids, _ = self.ingest(p)
        infos = self.graph.file_infos(ids)
        raw = sum(i["raw_tokens"] for i in infos)
        out, returned = finish(row["digest"], raw, "everything except the stored digest")
        self._log("recall", self._task_type(infos), infos, raw, returned, "everything except the stored digest")
        return out
