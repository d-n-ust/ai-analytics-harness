#!/usr/bin/env python3
"""Stage 4 of the readiness audit: every way a question can express each element in scope.

Each test is one wording with its expected outcome. It goes through the question reader alone (no
agent, no data query), the way a call would be checked, and is graded on the action the reading
implies and the values it allows (01_parameter_grounding/run.py `reading_errors`). Tests of the
metric slot go through the metric choice instead (gates/reading.which_measure). Wordings in one
invariance group must all read the same.

    python element_tests.py tests_dev.yml            # about $0.0007 per test
    python element_tests.py tests_dev.yml --reader typed --only 1,8,9
    python element_tests.py tests_heldout.yml --totals-only

Readings run one at a time: they read the warehouse through one cursor, and readings sharing a
cursor across threads mixed the members of different dimensions (three false refusals, 2026-10-08).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import yaml
from agent.gates.reading import which_measure
from agent.guardrails import decisions, forks, parse_cell
from agent.runtime.grounding import build_grounding
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402


def run_test(test: dict, semantic, cursor, determines: dict, governance: dict | None = None,
             typed: bool = False) -> dict:
    expect = test["expect"]
    if test["element"] == "metric":
        choice = decisions.choose_metric(test["q"], semantic.metrics, forks.words_by_metric(semantic))
        asked, cost = decisions.question_level({}, test["q"], semantic)
        action, _c = which_measure(choice["probabilities"], semantic.metrics, asked, semantic)
        got = action or choice["choice"]
        return {"result": got, "ok": got == expect["outcome"], "errors": [] if got == expect["outcome"] else
                [f"{got} instead of {expect['outcome']}"], "cost": cost + choice["cost"]}
    cache: dict = {}
    reading, cost = decisions.reading_for(test["q"], expect.get("metric", "app_opens"), semantic, cursor,
                                          R.GOVERNANCE if governance is None else governance, cache, typed)
    graded = R.reading_errors(cache, {"expect": expect}, determines)
    return {"result": graded["action"], "ok": graded["action_ok"] and not graded["errors"],
            "errors": ([] if graded["action_ok"] else [f"action {graded['action']}"]) + graded["errors"],
            "reading": {"filters": reading["filters"], "periods": reading["periods"], "group_by": reading["group_by"]},
            "open": [f"{d['state']}: {d['why']}" for d in reading["decisions"] if d["state"] in ("refuse", "ungrounded")],
            "cost": cost}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tests")
    ap.add_argument("--totals-only", action="store_true",
                    help="print counts per element only: for a sealed set whose failures must not be read")
    ap.add_argument("--reader", choices=("questionnaire", "typed"), default="questionnaire")
    ap.add_argument("--only", default="", help="comma-separated 1-based test numbers: a probe")
    args = ap.parse_args()
    tests = yaml.safe_load((HERE / args.tests).read_text())["tests"]
    if args.only:
        tests = [tests[int(i) - 1] for i in args.only.split(",")]
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    cursor = R.scoped_cursor(con)
    semantic = build_grounding(cursor, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                               guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    determines = R.layer_determines(con)
    results = [{**t, **run_test(t, semantic, cursor, determines, typed=args.reader == "typed"),
                "reader": args.reader} for t in tests]
    groups: dict = {}
    for r in results:
        if r.get("group"):
            groups.setdefault(r["group"], set()).add(json.dumps([r["result"], r.get("reading")], sort_keys=True))
    by_element: dict = {}
    for r in results:
        by_element.setdefault(r["element"], [0, 0])[0] += r["ok"]
        by_element[r["element"]][1] += 1
    print(f"{'element':12} {'pass':>7}")
    for e, (ok, n) in by_element.items():
        print(f"{e:12} {ok:>3}/{n:<3}")
    print(f"\n{sum(r['ok'] for r in results)} of {len(results)} pass; invariance groups consistent "
          f"{sum(len(v) == 1 for v in groups.values())} of {len(groups)}; ${sum(r['cost'] for r in results):.4f}")
    if not args.totals_only:
        for r in results:
            if not r["ok"]:
                print(f"  FAIL [{r['element']} · {r['block']}] {r['q']}\n       {'; '.join(r['errors'])}"
                      + "".join(f"\n         {o}" for o in r.get("open") or []))
    tag = "" if args.reader == "questionnaire" else f"-{args.reader}"
    out = HERE / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}-{pathlib.Path(args.tests).stem}{tag}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=1, default=str))
    print(f"\nwrote {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
