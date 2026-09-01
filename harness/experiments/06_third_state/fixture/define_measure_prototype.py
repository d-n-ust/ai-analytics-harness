#!/usr/bin/env python3
"""End-to-end prototype of define_measure against the real marts + a live model.

    uv run python define_measure_prototype.py

Shows the whole loop on four shapes: a governed metric, a derived ratio (spend_per_signup), a
bespoke raw definition (retention by channel), and an uninstrumented measure (refused). For each it
prints what the model AUTHORED (scope + spec), the deterministic VERDICT, how many re-authorings it
took, and the disclosed answer — so the LLM-authors / mechanism-verifies split is visible.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../../..")

from run import LAYER, MARTS, RUNG, scoped_cursor          # noqa: E402
from agent.grounding import build_grounding                # noqa: E402
from agent.define import define_measure                    # noqa: E402
from agent.providers import get_model, load_env            # noqa: E402
from warehouse.warehouse import open_warehouse             # noqa: E402
import build as fixture_build                              # noqa: E402

CASES = [
    ("How many active users did we have last week?", "governed"),
    ("What did it cost us in marketing for each person who signed up in the second quarter of 2026?", "derived/query"),
    ("Which acquisition channel gives us the best 90-day retention?", "raw/computed"),
    ("How many minutes did the average user spend in the app last week?", "uninstrumented -> refuse"),
]


def _spec_str(spec, depth=0) -> str:
    if spec.kind == "metric":
        s = f"metric({spec.metric}"
    elif spec.kind == "derived":
        s = f"derived({spec.op}: [" + ", ".join(_spec_str(i) for i in spec.inputs) + "]"
    elif spec.kind == "query":
        s = f"query({spec.source}.{spec.measure} {spec.agg}"
    elif spec.kind == "raw":
        s = f"raw({spec.definition[:40]}"
    else:
        s = f"{spec.kind}("
    if spec.filters:
        s += " filters=" + str([f"{d}={v}" for d, v in spec.filters])
    if spec.period:
        s += f" period={spec.period}"
    return s + ")"


def main() -> None:
    load_env()
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)
    cur = scoped_cursor(con)
    g = build_grounding(cur, rung=RUNG, spec_path=LAYER, engine="metricflow",
                        semantic_layer=True, guardrails=None, schema=MARTS)
    model = get_model("gpt-5-mini")

    for question, expect in CASES:
        d = define_measure(model, question, g.ontology, g.semantic)
        print("=" * 96)
        print(f"Q: {question}")
        print(f"   expect: {expect}")
        print(f"   scope : measure={d.scope.measure!r} segments={list(d.scope.segments)} "
              f"period={d.scope.period!r} qualifiers={list(d.scope.qualifiers)}")
        print(f"   spec  : {_spec_str(d.spec)}")
        print(f"   -> outcome={d.outcome}  verdict={d.verdict}  tier={d.tier}  reauthorings={d.tries}")
        print(f"   {d.disclosure}")


if __name__ == "__main__":
    main()
