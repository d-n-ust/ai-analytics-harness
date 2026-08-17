#!/usr/bin/env python3
"""Experiment 05 benefit runner — the before/after measurement.

Run the analytics agent on each of the four semantic layers over the pre-registered question set
(`cases.yml`) and report the harness's own indicators — silent-error rate, balanced accuracy, and
coverage — overall and split flagged vs clean.

Everything is held constant across the four runs except the semantic layer the agent is shown: the
same warehouse, the same questions, the same independent gold. So a difference in the agent's silent
errors is caused by the layer's ambiguity — the runtime harm preflight predicts statically. The
dose-response is small (governed, 1 finding) -> high (sprawled, 18); the fix is the `_after` layer.

    python benefit.py --mock                     # validate the wiring end to end, no API key
    python benefit.py                            # a real run (needs ANTHROPIC_API_KEY; default haiku)
    python benefit.py --model claude-sonnet-5    # a real run on the larger model
    python benefit.py --only small_before high_before   # a subset of layers

Gold, questions, and scoring all run offline; only a non-mock agent needs a key.
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
LAYERS = HERE / "layers"
ORDER = ["small_before", "small_after", "high_before", "high_after"]
RUNG = 3  # star + governed semantic layer — the rung where metric selection is the agent's job


def load_cases() -> list[dict]:
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    for c in cases:
        _validate(c, "cases.yml")  # same validator the frozen set uses, so expected_refuse is set right
    return cases


def run_layer(con, spec_path, cases, golds, model, verifier, reps: int = 1) -> list[dict]:
    """The agent answers every question grounded on ONE semantic layer, `reps` times; each answer is
    graded into the row shape selective() consumes. Reps average out agent stochasticity."""
    g = build_grounding(con, rung=RUNG, spec_path=spec_path, engine="harness", semantic_layer=True)
    rows = []
    for rep in range(reps):
        for case in cases:
            ans = run_agent(case["question"], g, model, verifier_model=verifier)
            rows.append({**grade(ans, case, golds.get(case["id"])),
                         "outcome": ans.outcome, "id": case["id"], "tier": case["tier"], "rep": rep,
                         "picked": getattr(ans, "source_metric", None),
                         "declared": getattr(ans, "declared_value", None)})
    return rows


def metrics(rows: list[dict]) -> dict:
    s = selective(rows)
    return {"n": s.n, "coverage": s.coverage,
            "silent_error": s.silent_error, "balanced_accuracy": s.balanced_accuracy}


def _fmt(x) -> str:
    return " n/a " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:5.2f}"


def _print_scorecard(report: dict) -> None:
    print("\n  EXPERIMENT 05 — before/after benefit  (rung 3, agent selects the metric)")
    print("  " + "-" * 74)
    print(f"  {'layer':14} {'set':8} {'n':>2}  {'coverage':>9} {'silent_err':>11} {'bal_acc':>8}")
    print("  " + "-" * 74)
    for name in ORDER:
        if name not in report:
            continue
        for label in ("overall", "flagged", "clean"):
            m = report[name][label]
            if m["n"] == 0:
                continue
            tag = name if label == "overall" else ""
            print(f"  {tag:14} {label:8} {m['n']:>2}  {_fmt(m['coverage']):>9} "
                  f"{_fmt(m['silent_error']):>11} {_fmt(m['balanced_accuracy']):>8}")
        print("  " + "·" * 74)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="use the mock model (validate wiring, no key)")
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--reps", type=int, default=1, help="repetitions per question (averages stochasticity)")
    ap.add_argument("--only", nargs="*", help="run only these layers")
    args = ap.parse_args()

    cases = load_cases()
    con = open_warehouse(create_star_views=True)
    set_star(con, capabilities(RUNG).star)
    golds = compute_gold(con, cases)
    model = get_model(args.model, mock=args.mock)
    verifier = get_verifier(args.model, mock=args.mock)

    names = [n for n in ORDER
             if (not args.only or n in args.only) and (LAYERS / n / "semantic.yml").exists()]

    # Persist after EACH layer and merge into any existing result, so a long run (reps x layers) that
    # is interrupted keeps every completed layer, and layers run in separate invocations accumulate.
    out = HERE / ("benefit_result_mock.json" if args.mock else "benefit_result.json")
    report: dict = json.loads(out.read_text()) if (out.exists() and not args.mock) else {}
    report.update({"model": ("mock" if args.mock else args.model), "rung": RUNG, "reps": args.reps})
    for name in names:
        rows = run_layer(con, LAYERS / name / "semantic.yml", cases, golds, model, verifier, args.reps)
        report[name] = {"overall": metrics(rows),
                        "flagged": metrics([r for r in rows if r["tier"] == "flagged"]),
                        "clean": metrics([r for r in rows if r["tier"] == "clean"]),
                        "rows": rows}
        out.write_text(json.dumps(report, indent=2, default=str))

    _print_scorecard(report)
    print(f"\n  wrote {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
