#!/usr/bin/env python3
"""Study 02 — the governance ladder (no-semantic-layer vs semantic-layer).

The SAME plain business questions, asked of the same agent at three levels of governance:

    rung 1  messy raw tables (cryptic names, encoded meanings) — raw SQL, no metrics
    rung 2  clean conformed star                               — raw SQL, no metrics
    rung 3  governed semantic layer                            — the agent queries metrics

This tests the practice's thesis directly: the semantic layer's value is governance — it makes
ambiguity resolvable. On raw data the agent must weld its own SQL and either refuses (it cannot tell
which event type is a "value moment") or guesses (a silent error). Gold is one deterministic gold_sql
oracle against the clean star, computed once, so it is the same truth at every rung.

    python ladder.py --model gpt-5-mini --reps 3

Needs an API key for a real run (ANTHROPIC_API_KEY or OPENAI_API_KEY, per the model).
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib

import yaml

from agent.grounding import build_grounding
from agent.loop import run_agent
from agent.providers import get_model, get_verifier
from agent.rungs import capabilities
from evals.gold import _validate, compute_gold
from evals.grade import grade
from evals.selective import selective
from warehouse.warehouse import open_warehouse, set_star

HERE = pathlib.Path(__file__).resolve().parent
RUNGS = [(1, "messy raw"), (2, "clean star"), (3, "semantic layer")]


def load_cases() -> list[dict]:
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    for c in cases:
        _validate(c, "cases.yml")
    return cases


def run_rung(con, rung: int, cases, golds, model, verifier, reps: int) -> list[dict]:
    set_star(con, capabilities(rung).star)            # rung 1 drops the star: genuinely raw-only
    g = build_grounding(con, rung=rung, engine="harness", semantic_layer=(rung >= 3))
    rows = []
    for _ in range(reps):
        for case in cases:
            ans = run_agent(case["question"], g, model, verifier_model=verifier)
            rows.append({**grade(ans, case, golds.get(case["id"])),
                         "outcome": ans.outcome, "id": case["id"]})
    return rows


def _fmt(x) -> str:
    return " n/a " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    cases = load_cases()
    con = open_warehouse(create_star_views=True)      # gold is computed with the star present ...
    golds = compute_gold(con, cases)                  # ... so it is the same truth at every rung
    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)

    report: dict = {"model": ("mock" if args.mock else args.model), "reps": args.reps, "rungs": {}}
    for rung, label in RUNGS:
        rows = run_rung(con, rung, cases, golds, model, verifier, args.reps)
        s = selective(rows)
        n = len(rows)
        report["rungs"][str(rung)] = {
            "label": label, "n": n,
            "correct": sum(1 for r in rows if r.get("correct")) / n,
            "coverage": s.coverage, "silent_error": s.silent_error,
            "answered": sum(1 for r in rows if r["outcome"] == "answer") / n,
            "refused": sum(1 for r in rows if r["outcome"] in ("refuse", "clarify")) / n,
            "rows": rows}
        (HERE / f"ladder_result__{args.model}.json").write_text(json.dumps(report, indent=2, default=str))

    print(f"\n  STUDY 02 — governance ladder  ({report['model']}, reps={args.reps}, {len(cases)} questions)")
    print("  " + "-" * 74)
    print(f"  {'rung':22} {'correct':>8} {'silent_err':>11} {'answered':>9} {'refused':>8}")
    print("  " + "-" * 74)
    for rung, label in RUNGS:
        m = report["rungs"].get(str(rung))
        if not m:
            continue
        print(f"  {f'{rung} {label}':22} {_fmt(m['correct']):>8} {_fmt(m['silent_error']):>11} "
              f"{_fmt(m['answered']):>9} {_fmt(m['refused']):>8}")
    print(f"\n  wrote {(HERE / f'ladder_result__{args.model}.json').name}")


if __name__ == "__main__":
    main()
