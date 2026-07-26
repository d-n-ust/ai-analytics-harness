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
    from agent.guardrails import parse_cell
    from agent.session import ask_one
    guardrails = parse_cell(a.guardrails) if a.guardrails else None
    ask_one(question=a.question, rung=a.rung, model=a.model, guardrails=guardrails, verbose=True)


def cmd_run(a):
    from evals.runner import run_experiment
    run_experiment(mock=a.mock, models=_split(a.models), rungs=[int(r) for r in _split(a.rungs)],
                   only=_split(a.only) if a.only else None, sample=a.sample, repeats=a.repeats,
                   rrungs=[int(r) for r in _split(a.rrungs)],
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
    sp.add_argument("--rung", type=int, required=True, choices=[1, 2, 3, 4, 5, 6])
    sp.add_argument("--guardrails", default=None,
                    help="reliability config: a preset (R0..R9) or an explicit cell "
                         "(e.g. R9-resolve, or coverage_check+resolve+single_metric). Default R1.")
    sp.add_argument("--model", default="gpt-5.6-terra", choices=MODELS)
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("run", aliases=["eval"], help="run the experiment grid")
    sp.add_argument("--mock", action="store_true", help="deterministic mock model (no API key)")
    sp.add_argument("--models", default="gpt-5.6-terra,gpt-5.4-mini")
    sp.add_argument("--rungs", default="1,2,3,4,5,6", help="grounding rungs")
    sp.add_argument("--rrungs", default="1", help="reliability ladder presets R0..R9")
    sp.add_argument("--cells", default=None,
                    help="explicit guardrail cells (overrides --rrungs), e.g. R9,R9-resolve. "
                         "Incoherent cells are skipped.")
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

    sub.add_parser("test", help="run the no-LLM test suite").set_defaults(func=cmd_test)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
