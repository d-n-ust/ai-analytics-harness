#!/usr/bin/env python3
"""Regrade a stored head-to-head against another label file, with no model call.

The rows store each reading (filters, periods, group_by, grain, decision record), so a label
correction is applied to the readings as they were made. Prints the same totals as head_to_head.py.

    python regrade.py results/<run>-head_to_head.json replication3/tests_corrected.yml
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import yaml
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402
from head_to_head import OUTCOMES, READERS, adopt, outcome  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result")
    ap.add_argument("labels")
    args = ap.parse_args()
    run = json.loads((HERE / args.result).read_text())
    labels = {(t["group"], t["q"]): t["expect"] for t in yaml.safe_load((HERE / args.labels).read_text())["tests"]}
    con = open_warehouse(create_star_views=True)
    determines, aliases = R.layer_determines(con), R.layer_aliases(con)
    counts = {r: collections.Counter() for r in READERS}
    for row in run["rows"]:
        expect = labels[(row["group"], row["q"])]
        reading = row["reading"]
        graded = R.reading_errors({expect.get("metric", "app_opens"): reading}, {"expect": expect}, determines, aliases)
        result = {"ok": graded["action_ok"] and not graded["errors"], "result": graded["action"]}
        counts[row["reader"]][outcome(result)] += 1
    print(f"{'reader':15}" + "".join(f"{o:>15}" for o in OUTCOMES))
    for reader in READERS:
        print(f"{reader:15}" + "".join(f"{counts[reader][o]:>15}" for o in OUTCOMES))
    verdict, why = adopt({r: dict(counts[r]) for r in READERS}, 3 * run["reps"])
    print(f"\nadoption rule: {'MET' if verdict else 'NOT MET'} ({why})")


if __name__ == "__main__":
    main()
