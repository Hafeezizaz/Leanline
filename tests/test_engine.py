import leanline.tools as tools
from leanline import runlog


def test_read_relevant_returns_matching_section_only(engine, docs):
    out = engine.read_relevant(str(docs), "how long do refunds take?")
    assert "original payment method" in out
    assert "first day" not in out
    assert "[leanline]" in out


def test_read_relevant_logs_a_run(engine, docs):
    engine.read_relevant(str(docs), "refunds")
    runs = runlog.read_runs(engine.runs_path)
    assert len(runs) == 1
    r = runs[0]
    assert r["tool"] == "read_relevant" and r["task_type"] == "documents"
    assert r["raw_tokens"] > 0 and r["returned_tokens"] > 0
    assert r["saved_tokens"] == r["raw_tokens"] - r["returned_tokens"]


def test_budget_truncates_first_section(engine, docs):
    out = engine.read_relevant(str(docs), "refunds", max_tokens=5)
    assert "truncated" in out


def test_section_by_name(engine, docs):
    out = engine.read_relevant(str(docs), "", section="Retry")
    assert "exponential backoff" in out
    assert "original payment method" not in out


def test_no_match_returns_outline(engine, docs):
    out = engine.read_relevant(str(docs), "zzzxyz")
    assert "No section matched" in out
    assert "Refunds" in out


def test_missing_path_and_unsupported_folder(engine, tmp_path):
    assert "not found" in engine.read_relevant(str(tmp_path / "nope"), "x").lower()
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "a.bin").write_bytes(b"x")
    assert "No supported files" in engine.read_relevant(str(empty), "x")


def test_unchanged_file_is_not_reextracted(engine, docs, monkeypatch):
    calls = []
    real = tools.extract_file

    def counting(p):
        calls.append(p)
        return real(p)

    monkeypatch.setattr(tools, "extract_file", counting)
    f = docs / "billing.md"
    engine.read_relevant(str(f), "refunds")
    engine.read_relevant(str(f), "retry")
    assert len(calls) == 1
    f.write_text(f.read_text(encoding="utf-8") + "\n## Extra\nNew content here.\n", encoding="utf-8")
    out = engine.read_relevant(str(f), "new content")
    assert len(calls) == 2
    assert "New content here" in out


def test_remember_and_recall(engine, docs):
    f = docs / "billing.md"
    assert "No digest" in engine.recall(str(f))
    engine.remember(str(f), "Billing: retries 3x, refunds 5 days.")
    assert "Billing: retries 3x" in engine.recall(str(f))
    f.write_text("# Changed\ncontent", encoding="utf-8")
    assert "stale" in engine.recall(str(f))
