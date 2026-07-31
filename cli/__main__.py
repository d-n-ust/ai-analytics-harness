"""bench — one entry point for the AI-analyst harness.

    python -m cli data                          # (re)generate the deterministic warehouse
    python -m cli verify                        # check the generated data against ground truth
    python -m cli query "SELECT ..."            # read-only SQL (star views built)
    python -m cli ask "..." --rung 3 --guardrails R9
    python -m cli run  [--mock] [--models ...] [--rungs ...] [--rrungs ...] [--cells ...] [--repeats N]
    python -m cli regrade [--run DIR]           # re-grade a finished run (no model calls)
    python -m cli report  [--run DIR]           # re-render summary.md/json from stored rows
    python -m cli test                          # run the no-LLM test suite

Installed as `bench` via the ./bench wrapper. This module is a thin dispatcher — every verb
parses its args and calls one library function; all real work lives in the packages.
"""

from __future__ import annotations

import argparse
import os

# The one eager agent import: rungs is a leaf (dataclasses only, no warehouse, no providers), and
# the parser needs the rung table to build --rung's help and validation from the definitions
# themselves rather than a second copy of them.
from agent.guardrails import LADDER_ORDER
from agent.protocol import FRAMINGS, RULE
from agent.rungs import RUNGS, parse_rung

MODELS = ["claude-haiku-4-5", "claude-sonnet-5", "gpt-5.6-terra", "gpt-5.4-mini",
          "gpt-5-mini", "gpt-5.6-luna", "gpt-4.1-mini", "deepseek-v4-flash", "deepseek-v4-pro"]


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def _run_dir(arg):
    from pathlib import Path

    from evals.runner import RESULTS_DIR
    return Path(arg) if arg else (RESULTS_DIR / "latest").resolve()


def cmd_data(a):
    from warehouse.generate import OUT_PATH, generate
    counts = generate()
    print(f"wrote {OUT_PATH}")
    for name, n in counts.items():
        print(f"  {name:6s} {n:>8,d} rows")


def cmd_verify(a):
    from warehouse.verify import main
    main()


def cmd_query(a):
    from warehouse.warehouse import open_warehouse
    con = open_warehouse(create_star_views=True)
    con.sql(a.sql).show(max_rows=100)


def cmd_ask(a):
    from agent import ask_one
    from agent.guardrails import parse_cell
    guardrails = parse_cell(a.guardrails) if a.guardrails else None
    ask_one(question=a.question, rung=a.rung, model=a.model, guardrails=guardrails,
            verbose=not a.trace, trace=a.trace)


def cmd_trace(a):
    """Re-render a stored run. The trace is a view over what was already recorded, so any row
    ever written can be read back — including runs that predate this command."""
    import json

    from cli.trace import render
    run = _run_dir(a.run)
    rows = [json.loads(line) for line in (run / "raw.jsonl").open()]
    picked = [r for r in rows if r.get("qid") == a.qid
              and (a.config is None or r.get("config") == a.config)
              and (a.model is None or r.get("model") == a.model)]
    if not picked:
        ids = sorted({r.get("qid") for r in rows})
        raise SystemExit(f"no row for qid={a.qid!r} in {run.name}. Available: {', '.join(ids[:12])}…")
    for row in picked[: a.limit]:
        print(render(row))
    if len(picked) > a.limit:
        print(f"  … {len(picked) - a.limit} more (raise --limit, or narrow with --config/--model)")


def cmd_run(a):
    from evals.runner import run_experiment
    run_experiment(mock=a.mock, models=_split(a.models), rungs=[parse_rung(r) for r in _split(a.rungs)],
                   only=_split(a.only) if a.only else None, sample=a.sample, repeats=a.repeats,
                   rrungs=[int(r) for r in _split(a.rrungs)],
                   framings=_split(a.framings),
                   cells=_split(a.cells) if a.cells else None, reasoning=a.reasoning,
                   concurrency=a.concurrency)


def cmd_regrade(a):
    from evals.runner import regrade_run
    regrade_run(_run_dir(a.run))


def cmd_report(a):
    import json

    from evals import report
    run = _run_dir(a.run)
    rows = [json.loads(line) for line in (run / "raw.jsonl").open()]
    report.write(rows, run)
    print(f"re-rendered {run / 'summary.md'} and summary.json")


def cmd_test(a):
    import pathlib
    import subprocess
    import sys
    root = pathlib.Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root)}
    failed = 0
    for t in sorted((root / "tests").glob("test_*.py")):
        print(f"--- {t.name} ---", flush=True)
        failed += subprocess.run([sys.executable, str(t)], cwd=root, env=env).returncode != 0
    raise SystemExit(1 if failed else 0)


def main() -> None:
    p = argparse.ArgumentParser(prog="bench", description="AI-analyst harness — one entry point.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("data", help="(re)generate the deterministic warehouse").set_defaults(func=cmd_data)
    sub.add_parser("verify", help="check the generated data against its ground truth").set_defaults(func=cmd_verify)

    sp = sub.add_parser("query", help="run read-only SQL against the warehouse (star views built)")
    sp.add_argument("sql")
    sp.set_defaults(func=cmd_query)

    sp = sub.add_parser("ask", help="ask one question at one grounding rung + guardrail level")
    sp.add_argument("question")
    # parse_rung validates against the rung table, so the choices and the definitions cannot
    # drift apart — and its error names every defined rung.
    sp.add_argument("--rung", type=parse_rung, required=True,
                    help=f"grounding rung: {' '.join(f'{n}={r.name}' for n, r in RUNGS.items())}")
    sp.add_argument("--guardrails", default=None,
                    help="reliability config: a preset (R0..R9) or an explicit cell "
                         "(e.g. R9-resolve, or coverage_check+resolve+governed_numbers). Default R1.")
    sp.add_argument("--model", default="gpt-5.6-terra", choices=MODELS)
    sp.add_argument("--trace", action="store_true",
                    help="print the full run: every model call, tool call and guardrail that acted")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("run", aliases=["eval"], help="run the experiment grid")
    sp.add_argument("--mock", action="store_true", help="deterministic mock model (no API key)")
    sp.add_argument("--models", default="gpt-5.6-terra,gpt-5.4-mini")
    sp.add_argument("--rungs", default="1,2,3,4,5,6",
                    help=f"grounding rungs, comma-separated; defined: {sorted(RUNGS)}")
    # The ceiling is COMPUTED. Typed as a literal it went stale twice — the help still said
    # R0..R9 three guardrails later, which is the fossilised numbering REFACTOR.md names.
    sp.add_argument("--rrungs", default="1",
                    help=f"reliability ladder presets R0..R{len(LADDER_ORDER)}")
    sp.add_argument("--cells", default=None,
                    help="explicit guardrail cells (overrides --rrungs), e.g. R9,R9-resolve. "
                         "Incoherent cells are skipped.")
    sp.add_argument("--framings", default=RULE,
                    help=f"protocol framings to cross every cell with: {','.join(FRAMINGS)}. "
                         "Two arms in one run label themselves R12 and R12/role.")
    sp.add_argument("--only", default=None, help="comma-separated question ids (a quick subset)")
    sp.add_argument("--sample", type=int, default=None, help="first N questions per tier")
    sp.add_argument("--repeats", type=int, default=1, help="repeat the grid N times (mean + spread)")
    sp.add_argument("--reasoning", default=None,
                    help="main-model reasoning effort (e.g. minimal/low/high); default OPENAI_REASONING env")
    sp.add_argument("--concurrency", type=int, default=1,
                    help="parallel in-flight questions within a rung (I/O-bound; default 1 = sequential)")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("regrade", help="re-grade a finished run from stored answers (no model calls)")
    sp.add_argument("--run", default=None, help="run dir (default: results/latest)")
    sp.set_defaults(func=cmd_regrade)

    sp = sub.add_parser("report", help="re-render summary.md/json from a run's stored rows")
    sp.add_argument("--run", default=None, help="run dir (default: results/latest)")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("trace", help="re-render a stored run as a full trace")
    sp.add_argument("qid", help="question id, e.g. u_apac_march")
    sp.add_argument("--run", default="results/latest")
    sp.add_argument("--config", default=None, help="one guardrail cell, e.g. R9")
    sp.add_argument("--model", default=None)
    sp.add_argument("--limit", type=int, default=3)
    sp.set_defaults(func=cmd_trace)

    sub.add_parser("test", help="run the no-LLM test suite").set_defaults(func=cmd_test)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
