from __future__ import annotations

import argparse
from pathlib import Path

from . import runlog
from .report import format_report
from .tools import Engine, default_home


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="leanline", description="Local token-saving MCP server.")
    ap.add_argument("--home", help="state directory (default: ~/.leanline or $LEANLINE_HOME)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser("report", help="print token savings by task type")
    ip = sub.add_parser("ingest", help="index a file or folder now")
    ip.add_argument("path")
    args = ap.parse_args(argv)

    home = Path(args.home) if args.home else default_home()
    cmd = args.cmd or "serve"
    if cmd == "report":
        print(format_report(runlog.read_runs(home / "runs.jsonl")))
    elif cmd == "ingest":
        engine = Engine(home)
        ids, notes = engine.ingest(args.path)
        print(f"Indexed {len(ids)} file(s).")
        for n in notes:
            print(n)
    else:
        from .server import main as serve

        serve(home)
