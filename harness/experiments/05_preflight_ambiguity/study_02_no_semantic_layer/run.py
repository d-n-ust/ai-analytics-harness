#!/usr/bin/env python3
"""Study 02 — before/after on the WAREHOUSE, no semantic layer (the agent answers by raw SQL).

Mirrors study 01's before/after, but the ambiguity lives in the fact-table columns instead of a
semantic layer, and the agent uses `run_sql` over the tables rather than `query_metric`:

    before  s2_before  — raw, confusable columns (raw billed vs a modelled mrr; is_internal AND
                         is_test for different sets; moments overloaded across two tables), thin docs
    after   s2_after   — one clear column per concept + COMMENTs that carry the scope rule

Same decomposition as study 01: SER (north star) = wrong-SELECTION (Mode 1 — the agent grounded on the
wrong COLUMN/table, recovered from its SQL) + wrong-CONSTRUCTION (Mode 2 — the right column, built
wrong). Gold is one deterministic gold_sql oracle against the clean star.

    python run.py --model gpt-5-mini --reps 3
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib

import warehouses
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
ARMS = [("before", warehouses.BEFORE), ("after", warehouses.AFTER)]


def load_cases() -> list[dict]:
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    for c in cases:
        _validate(c, "cases.yml")
    return cases


def _sql_of(ans) -> str:
    return " ".join(s.get("args", {}).get("query", "") for s in (getattr(ans, "steps", []) or [])
                    if s.get("tool") == "run_sql").lower()


def run_arm(con, schema, cases, golds, model, verifier, reps) -> list[dict]:
    con.execute(f"SET search_path = '{schema}'")               # scope the agent's raw SQL to this warehouse
    g = build_grounding(con, rung=2, engine="harness", semantic_layer=False, schema=schema)
    rows = []
    for _ in range(reps):
        for case in cases:
            ans = run_agent(case["question"], g, model, verifier_model=verifier)
            sql = _sql_of(ans)
            wrong_ground = any(w.lower() in sql for w in (case.get("wrong_grounding") or []))
            rows.append({**grade(ans, case, golds.get(case["id"])),
                         "outcome": ans.outcome, "id": case["id"], "tier": case["tier"],
                         "family": case.get("family"), "wrong_grounding": wrong_ground, "sql": sql})
    return rows


def metrics(rows: list[dict]) -> dict:
    s = selective(rows)
    ans = [r for r in rows if r["outcome"] == "answer"]
    # wrong-SELECTION (Mode 1): answered with a wrong COLUMN/table grounding (from the SQL).
    # wrong-CONSTRUCTION (Mode 2): answered with the right grounding but a wrong number.
    wsel = sum(1 for r in ans if r.get("wrong_grounding"))
    wcon = sum(1 for r in ans if not r.get("wrong_grounding") and not r.get("correct"))
    return {"n": s.n, "coverage": s.coverage, "silent_error": s.silent_error,
            "correct": (sum(1 for r in rows if r.get("correct")) / len(rows)) if rows else float("nan"),
            "wrong_selection_rate": (wsel / len(ans)) if ans else float("nan"),
            "wrong_construction_rate": (wcon / len(ans)) if ans else float("nan")}


def _f(x) -> str:
    return " n/a " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    cases = load_cases()
    con = open_warehouse(create_star_views=True)
    set_star(con, capabilities(2).star)
    warehouses.build(con)
    golds = compute_gold(con, cases)                # gold_sql resolves against the star (search_path _star)
    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)

    report: dict = {"model": ("mock" if args.mock else args.model), "reps": args.reps, "arms": {}}
    for name, schema in ARMS:
        rows = run_arm(con, schema, cases, golds, model, verifier, args.reps)
        report["arms"][name] = {"overall": metrics(rows),
                                "flagged": metrics([r for r in rows if r["tier"] == "flagged"]),
                                "clean": metrics([r for r in rows if r["tier"] == "clean"]),
                                "rows": rows}
        (HERE / f"result__{args.model}.json").write_text(json.dumps(report, indent=2, default=str))

    print(f"\n  STUDY 02 — warehouse before/after, raw SQL, no semantic layer  ({report['model']}, reps={args.reps})")
    print("  " + "-" * 92)
    print(f"  {'arm':8} {'set':8} {'correct':>8} {'SER':>6} {'coverage':>9}  |  {'w-SELECT':>9} {'w-CONSTR':>9}")
    print("  " + "-" * 92)
    for name, _ in ARMS:
        a = report["arms"][name]
        for label in ("overall", "flagged", "clean"):
            m = a[label]
            if m["n"] == 0:
                continue
            tag = name if label == "overall" else ""
            print(f"  {tag:8} {label:8} {_f(m['correct']):>8} {_f(m['silent_error']):>6} "
                  f"{_f(m['coverage']):>9}  |  {_f(m['wrong_selection_rate']):>9} {_f(m['wrong_construction_rate']):>9}")
        print("  " + "·" * 92)
    print(f"\n  wrote result__{args.model}.json")


if __name__ == "__main__":
    main()
