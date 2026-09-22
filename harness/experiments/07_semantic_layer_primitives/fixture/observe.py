#!/usr/bin/env python3
"""Run the agent on ONE arbitrary question and dump its trace — no grading.

`run.py` grades against `cases.yml`, which needs a single gold answer. The probe questions in this
experiment are deliberately ambiguous and have no single gold, so this runner just observes: it
builds the same grounding `run.py` does (rung 3, MetricFlow layer, query_metric + raw SQL) and writes
the trace in the shape `inspector/inspect.py` reads.

    python observe.py "How did Android app opens change over the first half of 2026?" \
        --out ../results/trace_time.json
"""
from __future__ import annotations

import argparse
import json
import pathlib

import run  # reuse run.py's grounding setup and imported engine entry points


def observe(question: str, model_name: str = "gpt-5-mini") -> dict:
    con = run.open_warehouse(create_star_views=True)
    run.fixture_build.build(con, drop=True)
    cur = run.scoped_cursor(con)
    grounding = run.build_grounding(cur, rung=run.RUNG, spec_path=run.LAYER, engine="metricflow",
                                    semantic_layer=True, schema=run.MARTS)
    grounding.semantic.catalogue = "normalised"
    grounding.refresh_catalogue()
    grounding.system += "\n\n" + run.SCHEMA_EXPLANATION
    model = run.get_model(model_name, mock=False)
    verifier = run.get_verifier(model_name, mock=False)
    answer = run.run_agent(question, grounding, model, verifier_model=verifier)

    return {
        "question": question,
        "outcome": answer.outcome,
        "declared": getattr(answer, "declared_value", None),
        "source_metric": getattr(answer, "source_metric", None),
        "answer_text": getattr(answer, "answer", None),
        "explanation": getattr(answer, "explanation", None),
        "reason": getattr(answer, "reason", None),
        "candidates": list(getattr(answer, "candidates", []) or []),
        "steps": [dict(s) for s in getattr(answer, "steps", [])],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    row = observe(args.question, args.model)
    pathlib.Path(args.out).write_text(json.dumps([row], indent=2, default=str))
    print(f"wrote {args.out}")
    print(f"outcome={row['outcome']}  served={row['declared']}")
    for s in row["steps"]:
        a = {k: v for k, v in (s.get("args") or {}).items()}
        print(f"  {s.get('tool')}({a})")


if __name__ == "__main__":
    main()
