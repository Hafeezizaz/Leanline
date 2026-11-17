"""Phase 1 benchmark: our answer size vs. reading the files whole.

Usage:
  python benchmarks/bench_phase1.py                       # synthetic sample (not representative!)
  python benchmarks/bench_phase1.py --folder DIR --questions questions.txt [--logfile app.log]

questions.txt: one question per line. All numbers are measured at run time with the same
tokenizer as the run log; none are hard-coded. "Raw" is the extracted text of every file in
the folder, which is what an assistant would otherwise read. Our returned size includes the
footer. The assistant's own tool-call tokens are NOT counted.
"""

from __future__ import annotations

import argparse
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from leanline import runlog  # noqa: E402
from leanline.report import format_report  # noqa: E402
from leanline.tokens import tokenizer_name  # noqa: E402
from leanline.tools import Engine  # noqa: E402

TOPICS = [
    "refund policy", "password reset", "data retention", "incident escalation",
    "deployment freeze", "vendor onboarding", "audit logging", "access review",
]
WORDS = (
    "the system process request value record team review update service policy owner change window "
    "report ticket queue release approval customer account limit schedule notice backup region"
).split()


def make_sample(folder: Path, n_docs: int = 6, seed: int = 7) -> tuple[list[str], Path]:
    rng = random.Random(seed)
    for i in range(n_docs):
        parts = [f"# Handbook {i + 1}\n"]
        for topic in TOPICS:
            filler = " ".join(rng.choice(WORDS) for _ in range(180))
            parts.append(f"## {topic.title()}\nThe {topic} procedure applies to all teams. {filler}\n")
        (folder / f"handbook_{i + 1}.md").write_text("\n".join(parts), encoding="utf-8")
    lines = []
    for n in range(3000):
        lines.append(f"2026-03-01 10:{(n // 60) % 60:02d}:{n % 60:02d} INFO request {n} served in {rng.randint(5, 90)}ms")
        if n % 700 == 350:
            lines.append(f"2026-03-01 10:{(n // 60) % 60:02d}:{n % 60:02d} ERROR upstream timeout after {n} ms")
    log = folder / "app.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    questions = [f"What is the {t}?" for t in TOPICS[:5]]
    return questions, log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder")
    ap.add_argument("--questions")
    ap.add_argument("--logfile")
    ap.add_argument("--max-tokens", type=int, default=2000)
    args = ap.parse_args()

    tmp = tempfile.TemporaryDirectory()
    home = Path(tmp.name) / "home"
    engine = Engine(home=home)

    if args.folder:
        folder = Path(args.folder)
        if not args.questions:
            sys.exit("--questions is required with --folder")
        questions = [q.strip() for q in Path(args.questions).read_text(encoding="utf-8").splitlines() if q.strip()]
        logfile = Path(args.logfile) if args.logfile else None
        label = f"user folder {folder}"
    else:
        folder = Path(tmp.name) / "sample"
        folder.mkdir()
        questions, logfile = make_sample(folder)
        label = "SYNTHETIC sample (generated; not representative of real documents)"

    print(f"Benchmark: {label}\nTokenizer: {tokenizer_name()}\n")
    print(f"{'question':<42}{'raw':>10}{'returned':>10}{'saved %':>9}")
    for q in questions:
        engine.read_relevant(str(folder), q, args.max_tokens)
        r = runlog.read_runs(engine.runs_path)[-1]
        pct = 100.0 * r["saved_tokens"] / r["raw_tokens"] if r["raw_tokens"] else 0.0
        print(f"{q[:40]:<42}{r['raw_tokens']:>10}{r['returned_tokens']:>10}{pct:>8.0f}%")
    if logfile:
        engine.compact(str(logfile))
        r = runlog.read_runs(engine.runs_path)[-1]
        pct = 100.0 * r["saved_tokens"] / r["raw_tokens"] if r["raw_tokens"] else 0.0
        print(f"{'compact(' + logfile.name + ')':<42}{r['raw_tokens']:>10}{r['returned_tokens']:>10}{pct:>8.0f}%")

    print("\n" + format_report(runlog.read_runs(engine.runs_path)))
    tmp.cleanup()


if __name__ == "__main__":
    main()
