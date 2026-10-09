#!/usr/bin/env python3
"""The controlled test (controlled.md): one fact of each kind, held in four ways, code fixed.

Every arm reads the same items with the same code. An arm changes only what the reader is given: the
word table (a copy without the fact's rows), the layer (a copy whose description states the fact),
and the governance setting `fact_consumers`. Readings run one at a time (element_tests.py).

    python controlled.py --reps 1 --only mobile:code     # a probe: one arm, one repetition
    python controlled.py --reps 3                         # every arm; about $0.10

A record, not a runnable test, since 2026-10-09: the "mobile" arms vary the word table
(wh_06_ref.value_words), which modelled attributes replaced (dim_platform.device_type). The results
in controlled.md were produced at commit db7b317; check that commit out to run it again.
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import shutil
import sys
import tempfile
import time

import yaml
from agent.guardrails import parse_cell
from agent.runtime.grounding import build_grounding
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402
from element_tests import run_test  # noqa: E402

PROSE = "Mobile means android and ios together."
NO_MOBILE = "wh_06_ref.value_words_without_mobile"

# arm -> (word table, layer has the prose sentence, fact_consumers)
ARMS = {
    "mobile": {
        "missing": (NO_MOBILE, False, {}),
        "prose": (NO_MOBILE, True, {}),
        "declared_model": (None, False, {"value_words": "model"}),
        "declared_code": (None, False, {}),
    },
    "coverage": {
        "missing": (None, False, {"coverage": "none"}),
        "declared_model": (None, False, {"coverage": "model"}),
        "declared_code": (None, False, {}),
    },
}


def _prose_layer() -> pathlib.Path:
    """A copy of the layer whose platform description also states what "mobile" means."""
    out = pathlib.Path(tempfile.mkdtemp(prefix="layer-prose-"))
    for f in R.LAYER.iterdir():
        shutil.copy(f, out / f.name)
    models = out / "semantic_models.yml"
    old = "The registered client platform: android, ios, web, or unknown."
    text = models.read_text()
    assert old in text, "the platform description changed; update controlled.py"
    models.write_text(text.replace(old, f"{old} {PROSE}"))
    return out


def _governance(table: str | None, consumers: dict) -> dict:
    gov = copy.deepcopy(R.GOVERNANCE)
    if table:
        gov["value_vocabulary"]["words"] = table
    if consumers:
        gov["fact_consumers"] = consumers
    return gov


def _patient(fn, *args):
    """The call, retried after a rate limit (HTTP 429): 5, 20 and 60 seconds."""
    from agent.guardrails.decisions import ReadingUnavailable
    for wait in (5, 20, 60, None):
        try:
            return fn(*args)
        except ReadingUnavailable:
            if wait is None:
                raise
            time.sleep(wait)


def _outcome(result: dict, expect: dict) -> str:
    want = {"metric_answer": "answer", "breakdown": "answer", "refuse": "refuse", "clarify": "ask"}[expect["type"]]
    got = result["result"]
    if result["ok"]:
        return "correct"
    if got == "answer":
        return "silent wrong"
    if want == "answer":
        return "wrong refusal or ask"
    return "safe miss"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--only", default=None, help="fact:arm, comma-separated")
    args = ap.parse_args()
    facts = yaml.safe_load((HERE / "controlled_items.yml").read_text())["facts"]
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    con.execute(f"CREATE OR REPLACE TABLE {NO_MOBILE} AS SELECT * FROM wh_06_ref.value_words WHERE word <> 'mobile'")
    cursor = R.scoped_cursor(con)
    determines = R.layer_determines(con)
    layers = {False: R.LAYER, True: _prose_layer()}
    semantics = {k: build_grounding(cursor, rung=R.RUNG, spec_path=v, engine="metricflow", semantic_layer=True,
                                    guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
                 for k, v in layers.items()}
    only = set(args.only.split(",")) if args.only else None
    rows, cost = [], 0.0
    for fact, arms in ARMS.items():
        for arm, (table, prose, consumers) in arms.items():
            if only and f"{fact}:{arm}" not in only:
                continue
            gov = _governance(table, consumers)
            for item in facts[fact]["items"]:
                for rep in range(args.reps):
                    test = {"element": "platform" if fact == "mobile" else "period", "q": item["q"],
                            "expect": item["expect"]}
                    r = _patient(run_test, test, semantics[prose], cursor, determines, gov)
                    cost += r["cost"]
                    platform = (r.get("reading") or {}).get("filters", {}).get("activity__platform")
                    rows.append({"fact": fact, "arm": arm, "q": item["q"], "control": bool(item.get("control")),
                                 "rep": rep, "outcome": _outcome(r, item["expect"]), "action": r["result"],
                                 "errors": r["errors"], "reading": r.get("reading"),
                                 "one_figure": isinstance(platform, list) and len(platform) == 1
                                 and isinstance(platform[0], list)})
    _report(rows, cost)
    out = HERE / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}-controlled.json"
    out.write_text(json.dumps(rows, indent=1, default=str))
    print(f"\nwrote {out.relative_to(HERE)}")


def _report(rows: list, cost: float) -> None:
    kinds = ("correct", "silent wrong", "safe miss", "wrong refusal or ask")
    print(f"{'fact':9} {'arm':15} {'items':>5} " + " ".join(f"{k:>20}" for k in kinds) + f" {'one figure':>11}")
    for fact in dict.fromkeys(r["fact"] for r in rows):
        for arm in dict.fromkeys(r["arm"] for r in rows if r["fact"] == fact):
            mine = [r for r in rows if r["fact"] == fact and r["arm"] == arm]
            counts = [sum(r["outcome"] == k for r in mine) for k in kinds]
            group = [r for r in mine if r["fact"] == "mobile" and not r["control"] and r["action"] == "answer"
                     and "non-mobile" not in r["q"] and "except" not in r["q"]]
            figure = f"{sum(r['one_figure'] for r in group)}/{len(group)}" if fact == "mobile" else ""
            print(f"{fact:9} {arm:15} {len(mine):>5} " + " ".join(f"{c:>20}" for c in counts) + f" {figure:>11}")
    print(f"\n${cost:.4f}")
    for r in rows:
        if r["outcome"] != "correct":
            print(f"  {r['fact']}:{r['arm']} [{r['outcome']}] {r['q']} -> {r['action']}; {'; '.join(r['errors'])}")


if __name__ == "__main__":
    main()
