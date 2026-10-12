#!/usr/bin/env python3
"""The readiness grid from stored readings (no model call): for one blind set, every labelled
parameter of every reading gets one verdict, and the verdicts are counted per parameter.

  grounded    the reading answered, and this parameter matched the label
  assumed     the same, with an analyst judgement on this parameter stated in the answer
  asks        the reader asked about this parameter, and the label expected a question
  unneeded asks  the reader asked about this parameter, although the label expected an answer
              (a question back stops the reading, so its other parameters are not counted)
  wrong       the reading answered, and an error names this parameter

Grading is `run.reading_errors` against the corrected labels, with the layer's rollups as in the run
(a broader value stated as broader counts as the labelled one, here as assumed). Readings labelled
refuse are left out: they test values the layer does not hold, not a parameter. Two dimensions that
keep the same rows are one column (country and country_name; platform and device_type are kept apart).

    python grid.py [results.json labels.yml]     # default: the fourth blind set
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

import yaml
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402

DEFAULT = ("results/20261011-140413-head_to_head.json", "replication4/tests_corrected.yml")
COLUMN = {"country_name": "country", "country": "country", "platform": "platform", "device_type": "device type",
          "region": "region", "channel": "channel", "period": "period", "time_grain": "time grain",
          "group_by": "group by"}
ORDER = ["platform", "device type", "country", "region", "channel", "period", "time grain", "group by"]


def columns_of(expect: dict) -> dict:
    """{column: label value} for every parameter the label sets."""
    return {COLUMN[k]: v for k, v in (expect.get("params") or {}).items() if k in COLUMN and v not in (None, [], "")}


def named(text: str, column: str, expect: dict) -> bool:
    """Does an error or a reason name this column: its key, or one of its labelled values?"""
    keys = [k for k, c in COLUMN.items() if c == column]
    values = [str(v).lower() for k in keys for v in (lambda x: x if isinstance(x, list) else [x])((expect.get("params") or {}).get(k, []))]
    low = text.lower()
    return any(k.replace("_", " ") in low.replace("_", " ") for k in keys) or any(v and v in low for v in values)


def main() -> None:
    result, labels_path = sys.argv[1:3] if len(sys.argv) >= 3 else DEFAULT
    rows = json.loads((HERE / result).read_text())["rows"]
    labels = {(t["group"], t["q"]): t["expect"] for t in yaml.safe_load((HERE / labels_path).read_text())["tests"]}
    con = open_warehouse(create_star_views=True)
    determines, aliases, rollups = R.layer_determines(con), R.layer_aliases(con), R.layer_rollups(con)
    grid = {c: collections.Counter() for c in ORDER}
    unattributed = []
    for row in rows:
        expect = labels[(row["group"], row["q"])]
        if expect["type"] == "refuse":
            continue
        g = R.reading_errors({"app_opens": row["reading"]}, {"expect": expect}, determines, aliases, rollups)
        cols = columns_of(expect)
        judged = [d for d in row["reading"]["decisions"] if d.get("basis") == "analyst_judgement"]
        if g["action"] == "answer":
            for col, value in cols.items():
                if value == "ask":
                    grid[col]["wrong"] += 1                     # answered what should have been asked
                elif any(named(e, col, expect) for e in g["errors"]):
                    grid[col]["wrong"] += 1
                elif any(named(d["value"], col, expect) for d in judged) or any(named(b, col, expect) for b in g["broader"]):
                    grid[col]["assumed"] += 1
                else:
                    grid[col]["grounded"] += 1
        else:
            reasons = [d.get("why") or "" for d in row["reading"]["decisions"] if d["state"] != "applied"] + g["errors"]
            hit = [c for c in cols if cols[c] == "ask"] or [c for c in cols if any(named(t, c, expect) for t in reasons)] \
                or [c for c in cols if any(d["parameter"] == c for d in row["reading"]["decisions"] if d["state"] != "applied")]
            if not hit:
                unattributed.append((row["q"], reasons[:2]))
            for col in hit:
                grid[col]["asks" if cols[col] == "ask" or expect["type"] == "clarify" else "unneeded asks"] += 1
    print(f"{'parameter':12}{'checks':>7}{'grounded':>10}{'assumed':>9}{'asks':>6}{'unneeded':>10}{'wrong':>7}")
    for col in ORDER:
        c = grid[col]
        n = sum(c.values())
        if n:
            print(f"{col:12}{n:>7}{c['grounded']:>10}{c['assumed']:>9}{c['asks']:>6}{c['unneeded asks']:>10}{c['wrong']:>7}")
    print(f"\nquestions back not attributed to a labelled parameter: {len(unattributed)}")
    for q, why in unattributed:
        print("  ", q[:80], "|", why)
    (HERE / "grid_set4.json").write_text(json.dumps({c: dict(grid[c]) for c in ORDER if grid[c]}, indent=1))


if __name__ == "__main__":
    main()
