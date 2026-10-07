#!/usr/bin/env python3
"""The wording sweep: does every way people ask for a number reach that number?

Each wording in `wordings.yml` goes through the steps that decide WHICH governed number answers a
question, without the agent and without querying data:

    1. the question check reads which declared word names the counted thing (decisions.question_level)
    2. the layer decides for the requester (guardrails/forks.py): one metric, show several, or ask
    3. where no declared word settles it, the decision model's metric choice and its rules apply
       (gates/reading.which_measure): refuse, ask, or the metric it reads

The outcome is compared with the wording's expected one. A miss is a finding for the metric's
owner: declare the word (or declare it ambiguous) in the layer's `meta.terms`, then run again.

    python sweep.py                      # every wording, about $0.0004 each
    python sweep.py --only customers     # wordings containing a phrase
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from agent.gates.reading import which_measure
from agent.guardrails import decisions, forks, parse_cell
from agent.guardrails.parameters import route_metric
from agent.runtime.grounding import build_grounding
from warehouse.warehouse import open_warehouse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run as R  # noqa: E402


def outcome(question: str, semantic, governance: dict) -> dict:
    """What decides the number for one wording, and the decision: a metric, "ask" or "refuse"."""
    asked, cost = decisions.question_level({}, question, semantic)
    choice = decisions.choose_metric(question, semantic.metrics, forks.words_by_metric(semantic))
    cost += choice["cost"]
    top = choice["choice"] if choice["choice"] in semantic.metrics else next(iter(semantic.metrics))
    # In the runtime's order: the call is routed on the declared word, and the answer is then held to
    # the metric choice, whose "no measure named" and "none in the list" rules apply either way.
    action, _candidates = which_measure(choice["probabilities"], semantic.metrics, asked, semantic)
    if action is not None:
        result, how = action, "model's metric choice"
    elif asked["term_known"] and asked["term"]:
        metric, decision = route_metric(top, governance, semantic, asked["term"], True)
        result = "ask" if decision and decision["state"] == "ungrounded" else metric
        if decision and "show every one" in (decision.get("disclose") or ""):
            result = "several"                      # every reading shown, each with its figure
        how = f"declared word '{asked['term']}'"
    else:
        result, how = choice["choice"], "model's metric choice"
    ranked = sorted(((p, m) for m, p in choice["probabilities"].items()), reverse=True)[:2]
    return {"result": result, "how": how, "top": [(m, round(p, 2)) for p, m in ranked], "cost": cost}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wordings", default="wordings.yml")
    ap.add_argument("--only", default=None, help="only wordings containing this phrase")
    args = ap.parse_args()
    spec = yaml.safe_load((R.HERE / args.wordings).read_text())
    governance = {**R.GOVERNANCE, "requester": {"team": spec.get("requester") or "Product"}}
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    semantic = build_grounding(R.scoped_cursor(con), rung=R.RUNG, spec_path=R.LAYER, engine="metricflow",
                               semantic_layer=True, guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    items = [(group, w["q"], str(w["expect"])) for group, ws in spec["wordings"].items() for w in ws
             if not args.only or args.only.lower() in w["q"].lower()]
    # Readings must not share a cursor across threads; this needs none, only the layer and requests.
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda it: outcome(it[1], semantic, governance), items))

    misses, by_group = [], {}
    for (group, q, expect), r in zip(items, results, strict=True):
        ok = r["result"] == expect
        by_group.setdefault(group, [0, 0])[0] += ok
        by_group[group][1] += 1
        if not ok:
            misses.append((group, q, expect, r))
    print(f"\n{'group':24} {'right':>7}")
    for group, (right, n) in by_group.items():
        print(f"{group:24} {right:>3}/{n:<3}")
    print(f"\n{sum(r for r, _ in by_group.values())} of {len(items)} wordings reach the expected outcome; "
          f"${sum(r['cost'] for r in results):.4f}")
    if misses:
        print("\nFindings (declare the word, or declare it ambiguous, then run again):")
        for group, q, expect, r in misses:
            print(f"  [{group}] {q}\n      expected {expect}, got {r['result']} by the {r['how']}; model read {r['top']}")
    out = R.RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([{"group": g, "q": q, "expect": e, **r} for (g, q, e), r in zip(items, results, strict=True)],
                              indent=1, default=str))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
