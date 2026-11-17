# Leanline design (v0.1)

Apache-2.0 · Python 3.10+ · MCP over stdio · first target Claude Desktop (Windows)

Clean-room rule: no CodeCortex or Ripwire source, names, benchmarks or numbers. Every figure shown comes from our own runs; unmeasured figures stay `TBD`.

## Architecture

```
sources        extractors      graph store        MCP tools           run log
.md .txt  -->  per-format  --> SQLite + FTS5 -->  read_relevant  -->  runs.jsonl --> leanline report
.docx .pdf     -> Section,     (files, sections,   compact             (one line      (dashboard in
.pptx .log     Term, links,     terms, log groups,  remember/recall      per call)      Phase 4)
               LogGroup         edges, digests)
```

State lives in `~/.leanline` (override: `LEANLINE_HOME`). Files are re-extracted only when their SHA-256 changes.

## Graph schema

Nodes: File, Section, Term, LogGroup (Entity, Sheet, Column from later phases). Edges: `contains` (File to Section), `defines` (Section to Term), `links_to` (Section to Section, or unresolved target text), `occurs_in` (LogGroup to File); `mentions`, `owns`, `depends_on` arrive in Phases 2-3.

## Tools (Phase 1)

- `read_relevant(path_or_folder, question, max_tokens=2000, section="")`: FTS5/BM25 ranked sections within a token budget, plus names of other matching sections; `section` fetches by name.
- `compact(file_or_text, kind="auto", full=false)`: log, json, html or text; states what was dropped; `full=true` returns the original.
- `remember(path, digest)` / `recall(path)`: digest keyed by content hash; stale if the file changed.

## Measurement

Each call appends: `ts, tool, task_type, source_paths, raw_bytes, raw_tokens, returned_tokens, saved_tokens, dropped, full, tokenizer`. Tokens use one local tokenizer (tiktoken cl100k_base, else chars/4): an estimate, not a billing figure. Baseline = extracted text of every file the call drew from. Returned size includes the footer. The assistant's own tool-call tokens are not counted, so savings are an upper bound on net savings. Negative savings are logged, never clamped.

## Phases

1. Documents and logs (this release).
2. Data: `data_profile`, `data_query` for CSV, then Excel.
3. Entities and cross-links: `graph_query`, `connect`, `who_owns`, `where_mentioned`.
4. Cross-session memory polish and the local dashboard (127.0.0.1 only).
5. Optional gateway mode compacting other MCP tools' large outputs.

## Honest limits

- Savings happen only when the assistant calls Leanline instead of opening files itself.
- Savings depend on the question; broad questions return close to the whole source.
- Keyword retrieval can miss paraphrases; the "more sections" list is the safety net.
- Scanned PDFs (no text layer) are unsupported.
- Compaction is lossy; always read the "dropped" note.

## Non-goals (v1)

Live connectors, editing Word/PDF, hosted or remote mode, a full code-intelligence engine.
