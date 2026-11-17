"""Savings report: aggregate the run log by task type."""

from __future__ import annotations

ORDER = ["documents", "data", "logs", "web", "code"]


def summarize(runs: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in runs:
        t = r.get("task_type", "other")
        s = out.setdefault(t, {"calls": 0, "raw_tokens": 0, "returned_tokens": 0, "saved_tokens": 0})
        s["calls"] += 1
        s["raw_tokens"] += int(r.get("raw_tokens", 0))
        s["returned_tokens"] += int(r.get("returned_tokens", 0))
        s["saved_tokens"] += int(r.get("saved_tokens", 0))
    for s in out.values():
        s["saved_pct"] = (100.0 * s["saved_tokens"] / s["raw_tokens"]) if s["raw_tokens"] else 0.0
    return out


def format_report(runs: list[dict]) -> str:
    if not runs:
        return "No runs logged yet."
    rep = summarize(runs)
    keys = [k for k in ORDER if k in rep] + sorted(k for k in rep if k not in ORDER)
    head = f"{'task type':<12}{'calls':>7}{'raw tokens':>14}{'returned':>12}{'saved':>12}{'saved %':>9}"
    lines = [head, "-" * len(head)]
    total = {"calls": 0, "raw_tokens": 0, "returned_tokens": 0, "saved_tokens": 0}
    for k in keys:
        s = rep[k]
        lines.append(
            f"{k:<12}{s['calls']:>7}{s['raw_tokens']:>14}{s['returned_tokens']:>12}"
            f"{s['saved_tokens']:>12}{s['saved_pct']:>8.0f}%"
        )
        for f in total:
            total[f] += s[f]
    pct = (100.0 * total["saved_tokens"] / total["raw_tokens"]) if total["raw_tokens"] else 0.0
    lines.append("-" * len(head))
    lines.append(
        f"{'TOTAL':<12}{total['calls']:>7}{total['raw_tokens']:>14}{total['returned_tokens']:>12}"
        f"{total['saved_tokens']:>12}{pct:>8.0f}%"
    )
    tokenizers = sorted({r.get("tokenizer", "?") for r in runs})
    lines.append("")
    lines.append(f"Tokenizer(s): {', '.join(tokenizers)} (estimates, not billing figures).")
    lines.append("Savings exclude the assistant's own tool-call tokens, so they are an upper bound on net savings.")
    return "\n".join(lines)
