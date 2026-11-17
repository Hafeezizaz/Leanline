import json

from leanline import runlog
from leanline.compact import compact_text, detect_kind

LOG = (
    "\n".join(f"2026-01-01 10:{i // 60:02d}:{i % 60:02d} INFO Heartbeat ok seq={i}" for i in range(200))
    + "\n2026-01-01 11:00:00 ERROR Database connection lost\n"
)

JSON_DOC = json.dumps({"items": [{"id": i, "name": "n" * 200} for i in range(100)]})

HTML_DOC = (
    "<html><head><title>T</title><script>var x=1</script></head><body><nav>Menu</nav>"
    "<main><h1>Hello</h1><p>World text</p></main><footer>Foot</footer></body></html>"
)


def test_detect_kind():
    assert detect_kind(JSON_DOC) == "json"
    assert detect_kind(HTML_DOC) == "html"
    assert detect_kind(LOG) == "log"
    assert detect_kind("just some words here") == "text"
    assert detect_kind("anything", name="x.json") == "json"


def test_compact_log_keeps_errors_and_collapses_repeats(engine):
    out = engine.compact(LOG)
    assert "ERROR" in out and "Database connection lost" in out
    assert "x200" in out
    assert "dropped:" in out and "collapsed" in out
    r = runlog.read_runs(engine.runs_path)[-1]
    assert r["task_type"] == "logs" and r["saved_tokens"] > 0


def test_compact_full_returns_original(engine):
    out = engine.compact(LOG, kind="log", full=True)
    assert "Heartbeat ok seq=199" in out
    assert runlog.read_runs(engine.runs_path)[-1]["full"] is True


def test_compact_json_keeps_structure_and_samples(engine):
    out = engine.compact(JSON_DOC)
    assert '"items"' in out and "more items" in out
    assert '"id": 50' not in out
    assert "...(+" in out  # long string cut


def test_compact_html_keeps_main_text_only(engine):
    out = engine.compact(HTML_DOC)
    assert "Hello" in out and "World text" in out
    assert "Menu" not in out and "var x" not in out and "Foot" not in out


def test_compact_plain_collapses_duplicates():
    out, dropped = compact_text("a\na\na\n\nb\n", "text")
    assert "repeated x3" in out and "b" in out
    assert "2 consecutive duplicate" in dropped


def test_compact_accepts_a_file_path(engine, tmp_path):
    p = tmp_path / "x.log"
    p.write_text(LOG, encoding="utf-8")
    out = engine.compact(str(p))
    assert "Database connection lost" in out
    assert str(p.resolve()) in runlog.read_runs(engine.runs_path)[-1]["source_paths"]


def test_compact_rejects_documents_and_bad_kind(engine, tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF")
    assert "read_relevant" in engine.compact(str(p))
    assert "Unknown kind" in engine.compact("text", kind="bogus")
