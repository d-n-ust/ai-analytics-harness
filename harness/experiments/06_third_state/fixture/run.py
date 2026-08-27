#!/usr/bin/env python3
"""Ask the contested question and show what the agent actually did.

This is the demonstration runner, not the experiment runner. It asks ONE question a few times and
prints the whole path: the tools the agent was offered, the catalogue it read, every call it made,
the terminal action it chose, and how that action grades. The point is to see the failure rather
than to read a rate — with one question and a handful of reps there is no rate worth reading.

The agent is grounded at rung 3 on the MetricFlow layer under `layer/`, holding both
`query_metric` and `run_sql`, which is the shape a real project has: it reaches for a governed
metric when one fits and writes SQL when none does.

    python run.py --mock                       # no API key, no cost — check the plumbing
    python run.py --model gpt-5-mini --reps 5  # the real thing
    python run.py --model gpt-5-mini --reps 5 --json out.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml
from agent.grounding import build_grounding
from agent.guardrails import parse_cell
from agent.loop import Answer, run_agent
from agent.providers import get_model
from evals.gold import _validate, compute_gold
from evals.grade import grade
from evals.selective import selective
from warehouse.warehouse import cursor as scoped_cursor
from warehouse.warehouse import open_warehouse

import build as fixture_build

HERE = pathlib.Path(__file__).resolve().parent
LAYER = HERE / "layer"
RUNG = 3          # star + governed semantic layer, raw SQL still on the table


def load_cases() -> list[dict]:
    cases = yaml.safe_load((HERE / "cases.yml").read_text())["cases"]
    for case in cases:
        _validate(case, "cases.yml")
    return cases


def _render_step(step: dict) -> str:
    """One tool call, on one line. Results are truncated: what matters here is which call was made
    and whether anything stopped it, not the payload."""
    args = {k: v for k, v in (step.get("args") or {}).items() if v not in (None, "", [], {})}
    shown = ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:4])
    outcome = "blocked" if step.get("blocked_by") else ("error" if step.get("error") else "ok")
    result = str(step.get("result") or "")[:90].replace("\n", " ")
    return f"    {step.get('tool'):16} {shown[:88]:88} [{outcome}]  {result}"


def demonstrate(answer: Answer, case: dict, gold, graded: dict) -> None:
    print(f"\n  tool calls ({len(answer.steps)}):")
    for step in answer.steps:
        print(_render_step(step))
    print(f"\n  terminal action : {answer.outcome}")
    if answer.outcome == "answer":
        print(f"  served          : {answer.declared_value}  "
              f"(source_metric={answer.source_metric!r})")
        print(f"  text            : {(answer.answer or '')[:160]}")
    else:
        print(f"  reason          : {answer.reason}")
        if answer.outcome == "clarify":
            named = list(getattr(answer, "candidates", ()) or ())
            print(f"  candidates      : {named or '(none named — the bare tool cannot carry them)'}")
        print(f"  text            : {(answer.explanation or '')[:200]}")
    served = graded.get("served_candidate")
    div = graded.get("divergence")
    print(f"\n  GRADED          : correct={graded['correct']}  bucket={graded['bucket']}  "
          f"silent_error={bool(graded['confident_wrong'])}")
    if served:
        print(f"  served reading  : {served}   {div * 100:.2f}% from the one it was chosen over")
    elif answer.outcome == "answer":
        print("  served reading  : matched neither governed definition")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--mock", action="store_true", help="scripted model: no API key, no cost")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--cell", default=None,
                    help="guardrail cell, e.g. R1 or R9. Default: the loop's own default set.")
    ap.add_argument("--variant", default=None,
                    help="a generated layer variant (see variants.py). Default: the shipped layer.")
    ap.add_argument("--catalogue", default="full", choices=("full", "compact"),
                    help="how the metric list is laid out. `compact` puts every name and "
                         "description contiguous and the dimension detail in a second block — "
                         "same facts, different adjacency.")
    ap.add_argument("--json", dest="out", default=None, help="write the graded rows here")
    args = ap.parse_args()

    layer = (HERE / "variants" / args.variant) if args.variant else LAYER
    if not layer.is_dir():
        sys.exit(f"{layer} does not exist — run `python variants.py --write` first")
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con)                     # the dbt models, so the layer has something to read
    cases = load_cases()
    golds = compute_gold(con, cases)             # resolves each candidate's own oracle
    case = cases[0]

    guardrails = parse_cell(args.cell) if args.cell else None
    model = get_model(args.model, mock=args.mock)

    print(f"question   : {case['question']}")
    print(f"concept    : {case['expect']['concept']}")
    print("candidates :")
    for cand in case["expect"]["candidates"]:
        print(f"    {cand['metric']:18} = {cand['value']:>10,.0f}   owner {cand['owner']:10} "
              f"→ {cand['consumer']}")
    print(f"\nmodel      : {model.spec.name}   rung {RUNG}   "
          f"guardrails {args.cell or 'loop default'}   layer {args.variant or 'shipped'}   "
          f"catalogue {args.catalogue}   reps {args.reps}")

    rows = []
    for rep in range(args.reps):
        cur = scoped_cursor(con)
        try:
            grounding = build_grounding(cur, rung=RUNG, spec_path=layer, engine="metricflow",
                                        semantic_layer=True, guardrails=guardrails)
            grounding.semantic.catalogue = args.catalogue
            if rep == 0:
                offered = [t["name"] for t in grounding.toolbox.specs()]
                print(f"\ntools offered ({len(offered)}): {', '.join(offered)}")
                print(f"metrics in the catalogue: "
                      f"{', '.join(sorted(grounding.toolbox.semantic.metrics))}")
            try:
                answer = run_agent(case["question"], grounding, model)
            except Exception as exc:                                       # noqa: BLE001
                answer = Answer(case["question"], RUNG, model.spec.name, None,
                                outcome="error", error=f"{type(exc).__name__}: {exc}"[:200])
        finally:
            cur.close()
        print(f"\n{'─' * 100}\nrep {rep + 1}")
        graded = grade(answer, case, golds[case["id"]])
        demonstrate(answer, case, golds[case["id"]], graded)
        rows.append({**graded, "outcome": answer.outcome, "id": case["id"],
                     "rep": rep, "declared": answer.declared_value,
                     "source_metric": answer.source_metric})

    score = selective(rows).as_dict()
    print(f"\n{'═' * 100}\nover {len(rows)} attempt(s) — pile C only, so coverage is not defined here")
    for key in ("contested_n", "contested_clarified", "contested_served", "contested_refused",
                "clarification_rate", "silent_error", "balanced_accuracy"):
        print(f"  {key:24} {score[key]}")
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(rows, indent=2, default=str))
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
