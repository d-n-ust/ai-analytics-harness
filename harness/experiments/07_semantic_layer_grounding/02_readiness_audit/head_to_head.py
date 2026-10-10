#!/usr/bin/env python3
"""Stage 7: the questionnaire and the typed reader on one sealed set, graded the same way.

Each wording is read by both readers, `--reps` times each, and every reading gets one primary
outcome (replication/preregistration.md):

  correct        the action and every labelled parameter match the label
  silent wrong   the reader would answer, and the answer is not the labelled one
  safe miss      the reader asks where the label says otherwise
  wrong refusal  the reader refuses where the label says otherwise

Only totals are printed, so the person running it stays blind to the failures until the run is
recorded. The full results are written to results/.

    python head_to_head.py replication/tests.yml --reps 3      # about $0.20
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

import yaml
from agent.guardrails import parse_cell
from agent.runtime.grounding import build_grounding
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402
from element_tests import _patient, run_test  # noqa: E402

READERS = ("questionnaire", "typed")
OUTCOMES = ("correct", "silent wrong", "safe miss", "wrong refusal")


def outcome(result: dict) -> str:
    if result["ok"]:
        return "correct"
    return {"answer": "silent wrong", "ask": "safe miss", "refuse": "wrong refusal"}[result["result"]]


def adopt(counts: dict, per_intent: int) -> tuple[bool, str]:
    """The pre-registered adoption rule: the typed reader's silent wrong readings are no more than the
    questionnaire's, and its correct readings are lower by at most one intent's worth."""
    q, t = counts["questionnaire"], counts["typed"]
    ok = t["silent wrong"] <= q["silent wrong"] and t["correct"] >= q["correct"] - per_intent
    return ok, (f"silent wrong {t['silent wrong']} vs {q['silent wrong']}; correct {t['correct']} vs "
                f"{q['correct']} (allowed shortfall {per_intent})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tests")
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()
    path = HERE / args.tests
    tests = yaml.safe_load(path.read_text())["tests"]
    con = open_warehouse(create_star_views=True)
    R.fixture_build.build(con, drop=True)
    cursor = R.scoped_cursor(con)
    semantic = build_grounding(cursor, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                               guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
    determines, aliases, rollups = R.layer_determines(con), R.layer_aliases(con), R.layer_rollups(con)
    rows = []
    for rep in range(args.reps):
        for n, test in enumerate(tests):
            for reader in READERS:
                r = _patient(run_test, test, semantic, cursor, determines, typed=reader == "typed", aliases=aliases,
                             rollups=rollups)
                rows.append({**test, **r, "n": n, "rep": rep, "reader": reader, "outcome": outcome(r)})
    counts = {reader: {o: sum(1 for r in rows if r["reader"] == reader and r["outcome"] == o) for o in OUTCOMES}
              for reader in READERS}
    groups = {t.get("group") for t in tests}
    per_intent = round(len(tests) / max(len(groups), 1)) * args.reps
    print(f"{len(tests)} wordings x {args.reps} repetitions per reader; layer {R.LAYER_SHA}")
    print(f"{'reader':15}" + "".join(f"{o:>15}" for o in OUTCOMES) + f"{'cost':>10}")
    for reader in READERS:
        cost = sum(r["cost"] for r in rows if r["reader"] == reader)
        print(f"{reader:15}" + "".join(f"{counts[reader][o]:>15}" for o in OUTCOMES) + f"{'$%.4f' % cost:>10}")
    verdict, why = adopt(counts, per_intent)
    print(f"\nadoption rule: {'MET' if verdict else 'NOT MET'} ({why})")
    out = HERE / "results" / f"{time.strftime('%Y%m%d-%H%M%S')}-head_to_head.json"
    out.write_text(json.dumps({"tests": args.tests, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "layer": R.LAYER_SHA, "reps": args.reps, "counts": counts, "adopt": verdict,
                               "rows": rows}, indent=1, default=str))
    print(f"wrote {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
