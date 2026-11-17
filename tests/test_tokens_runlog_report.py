from leanline import runlog
from leanline.report import format_report, summarize
from leanline.tokens import count_tokens, truncate_to_tokens


def test_count_tokens_basic():
    assert count_tokens("") == 0
    assert count_tokens("hello world") > 0
    assert count_tokens("hello world " * 50) > count_tokens("hello world")


def test_truncate_to_tokens_respects_limit():
    text = "alpha beta gamma delta " * 100
    cut = truncate_to_tokens(text, 20)
    assert count_tokens(cut) <= 20
    assert text.startswith(cut)
    assert truncate_to_tokens("short", 100) == "short"


def test_make_record_keeps_negative_saving():
    rec = runlog.make_record("compact", "logs", ["x"], raw_tokens=10, returned_tokens=30)
    assert rec["saved_tokens"] == -20


def test_runlog_roundtrip_skips_corrupt_lines(tmp_path):
    path = tmp_path / "runs.jsonl"
    runlog.append(path, runlog.make_record("t", "documents", ["a"], 100, 10))
    with open(path, "a", encoding="utf-8") as f:
        f.write("not json\n")
    runlog.append(path, runlog.make_record("t", "documents", ["b"], 50, 5))
    runs = runlog.read_runs(path)
    assert len(runs) == 2
    assert runlog.read_runs(tmp_path / "missing.jsonl") == []


def test_report_aggregates_by_task_type():
    runs = [
        runlog.make_record("read_relevant", "documents", ["a"], 1000, 100),
        runlog.make_record("compact", "logs", ["b"], 500, 50),
        runlog.make_record("compact", "logs", ["c"], 500, 150),
    ]
    rep = summarize(runs)
    assert rep["documents"]["saved_tokens"] == 900
    assert rep["logs"]["calls"] == 2
    assert rep["logs"]["raw_tokens"] == 1000
    assert rep["logs"]["returned_tokens"] == 200
    text = format_report(runs)
    assert "documents" in text and "logs" in text and "TOTAL" in text


def test_empty_report():
    assert format_report([]) == "No runs logged yet."
