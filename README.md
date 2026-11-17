# Leanline

A local MCP server that cuts the tokens an AI assistant spends on documents and logs. It turns your files into a small knowledge graph (SQLite), returns only the sections a question needs, and logs every saving it makes.

**Status: Phase 1 (v0.1).** Documents and logs only. No savings numbers are published yet: they will appear here only after they are measured with `benchmarks/bench_phase1.py` on real folders.

Everything runs on your machine. No cloud service, no telemetry.

## Install

```
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Use with Claude Desktop (Windows)

Edit `%APPDATA%\Claude\claude_desktop_config.json`. Use the full path to the venv's Python so Claude Desktop finds the dependencies:

```json
{
  "mcpServers": {
    "leanline": {
      "command": "C:\\path\\to\\Leanline\\.venv\\Scripts\\python.exe",
      "args": ["-m", "leanline", "serve"]
    }
  }
}
```

Restart Claude Desktop. Leanline stores its graph and run log in `~/.leanline` (override with the `LEANLINE_HOME` environment variable).

## Tools (Phase 1)

| Tool | What it does |
|---|---|
| `read_relevant(path_or_folder, question, max_tokens=2000, section="")` | Best-matching sections from a file or folder (.md .txt .docx .pdf .pptx .log), with names of other sections to request. `section="name"` fetches a section by name. |
| `compact(file_or_text, kind="auto", full=false)` | Shrinks logs, JSON, HTML or plain text. Always states what was dropped. `full=true` returns the original. |
| `remember(path, digest)` / `recall(path)` | Store a digest of a file keyed by its content hash; `recall` returns it only while the file is unchanged. |

Every call appends a line to `runs.jsonl` and ends with a one-line footer showing tokens returned versus the raw source.

## Measure savings

```
leanline report
python benchmarks/bench_phase1.py --folder <your folder> --questions <questions.txt>
```

Token counts are estimates from one local tokenizer (`tiktoken` cl100k_base when available, otherwise characters/4), not billing figures. The "raw" baseline is the extracted text of every file the call drew from, which is what the assistant would otherwise read.

## Honest limits

- Savings happen only when the assistant calls Leanline instead of opening files itself.
- They depend on the question: broad questions return close to the whole source.
- Retrieval is keyword-based (SQLite FTS5); paraphrased questions can miss. The "more sections" list is the safety net.
- Scanned PDFs without a text layer are not supported.
- Reported savings do not include the tokens of the assistant's own tool calls, so they are an upper bound on net savings.
- Compaction is lossy by design; check the "dropped" note and use `full=true` when exactness matters.

## Roadmap

See [docs/DESIGN.md](docs/DESIGN.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md).
