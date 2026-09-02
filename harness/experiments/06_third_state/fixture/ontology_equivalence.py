#!/usr/bin/env python3
"""Offline equivalence for the graph answerability path (rollout step 4), NO agent run.

For all 46 held-out questions, compute three things and compare:
  - GRAPH : classify.answerability_via_graph over the complete marts graph (the new path)
  - OLD   : classify.classify_answerability over ontology_text + schema_text (today's path)
  - gold  : the case's tier/reason, mapped to the answerability axis where that axis is the gold one

The graph decides ONLY the governed/computable/uninstrumented axis. A gold refusal on ANOTHER axis
(out_of_coverage, false_premise, ungoverned_dimension_value) is not the graph's to make — the measure
there IS governed and a different gate refuses — so those are marked off-axis and a `governed` graph
verdict is expected. This separates a real answerability regression from a correct division of labour.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")
sys.path.insert(0, "../../..")

import yaml                                                    # noqa: E402
from run import LAYER, MARTS, RUNG, scoped_cursor             # noqa: E402
from agent.runtime.grounding import build_grounding                   # noqa: E402
from agent.runtime.providers import get_model, load_env               # noqa: E402
from agent.guardrails import classify                         # noqa: E402
from agent.core.rungs import capabilities                          # noqa: E402
from warehouse import schema_text                             # noqa: E402
from warehouse.warehouse import open_warehouse                # noqa: E402
import build as fixture_build                                 # noqa: E402


def expected_axis(case) -> tuple:
    """(expected_graph_verdict, on_axis) — what the graph SHOULD say, and whether answerability is the
    gold axis for this case. Off-axis cases (coverage/premise/segment) have a governed measure, so the
    graph is expected to say `governed` and another gate owns the refusal."""
    tier, cid = case["tier"], case["id"]
    if tier.startswith(("answerable", "contested", "governed_ratio")):
        return "governed", True
    if cid == "h_b_retention_by_channel":
        return "computable", True
    if tier == "unanswerable_bare":
        return "uninstrumented", True
    if tier == "unanswerable_adjacent":
        return "uninstrumented", True          # incl. retention-adjacent misses that lack the data
    # unanswerable_coverage / unanswerable_premise: measure is governed, refusal is off the graph's axis
    return "governed", False


def main():
    load_env()
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)
    cur = scoped_cursor(con)
    g = build_grounding(cur, rung=RUNG, spec_path=LAYER, engine="metricflow",
                        semantic_layer=True, guardrails=None, schema=MARTS)
    ont, sem = g.ontology, g.semantic
    sch = schema_text(cur, capabilities(RUNG).star, MARTS)
    model = get_model("gpt-5-mini")
    cases = yaml.safe_load(open("heldout.yml"))["cases"]

    def judge(case):
        q = case["question"]
        graph = classify.answerability_via_graph(model, q, ont)["verdict"]
        old = classify.classify_answerability(model, q, sem.ontology_text(), sch)["verdict"]
        exp, on_axis = expected_axis(case)
        return {"id": case["id"], "tier": case["tier"], "graph": graph, "old": old,
                "expected": exp, "on_axis": on_axis}

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(judge, cases))

    print(f"{'id':34} {'tier':22} {'graph':14} {'old':14} {'exp(axis)':16}")
    ga = oa = gvo = 0
    for r in sorted(rows, key=lambda x: x["tier"]):
        axis = f"{r['expected']}{'' if r['on_axis'] else '*'}"
        gflag = "" if (r["graph"] == r["expected"]) else "  <-graph"
        oflag = "" if (r["old"] == r["expected"]) else " old!=exp"
        dflag = "" if (r["graph"] == r["old"]) else " G!=O"
        print(f"{r['id']:34} {r['tier']:22} {r['graph']:14} {r['old']:14} {axis:16}{gflag}{oflag}{dflag}")
        if r["on_axis"] and r["graph"] == r["expected"]:
            ga += 1
        if r["on_axis"] and r["old"] == r["expected"]:
            oa += 1
        if r["graph"] != r["old"]:
            gvo += 1
    on = sum(1 for r in rows if r["on_axis"])
    print(f"\nON-AXIS ({on} cases): graph correct {ga}/{on}, old correct {oa}/{on}")
    print(f"graph vs old differ on {gvo}/{len(rows)} cases (* = off-axis, governed measure expected)")


if __name__ == "__main__":
    main()
