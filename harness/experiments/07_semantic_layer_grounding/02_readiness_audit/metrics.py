#!/usr/bin/env python3
"""The experiment's three headline numbers for each blind head-to-head, per reader, from stored rows
(no model call): silent wrong, balanced accuracy and coverage, as `harness/evals/selective.py` defines
them, applied to the reader's action and parameters.

  pile A  answerable           label metric_answer or breakdown
  pile B  unanswerable         label refuse, or ambiguous (refuse or ask)
  pile C  needs a question     label clarify, or contested (answer or ask)

  silent wrong       readings answered wrongly with nothing marking them, over all readings
  balanced accuracy  the mean over the piles present of the share handled correctly
  coverage           of pile A, the share the reader attempted (answered, right or wrong)

    python metrics.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import yaml
from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402
from head_to_head import READERS, outcome  # noqa: E402

PILE = {"metric_answer": "A", "breakdown": "A", "refuse": "B", "ambiguous": "B", "clarify": "C", "contested": "C"}

# The first set's rows predate stored readings, so its corrections (replication/label_audit.md) are
# applied to the stored outcomes: (group, words in the wording or "", reader or "") -> outcome.
SET1_OVERRIDES = [
    ("i02", "", "", "correct"),                                  # the undefined grain key
    ("i08", "Germany and France", "typed", "correct"),           # country_name for country, same rows
    ("i10", "US app opens", "typed", "correct"),                 # drifted to a listed value
    ("i10", "United States", "", "correct"),
]
SETS = [
    ("1", "results/20261009-224447-head_to_head.json", "replication/tests_corrected.yml", "stored"),
    ("2", "results/20261010-125356-head_to_head.json", "replication2/tests_corrected.yml", "regrade"),
    ("3", "results/20261010-201801-head_to_head.json", "replication3/tests_corrected.yml", "regrade"),
]


def main() -> None:
    con = open_warehouse(create_star_views=True)
    determines, aliases = R.layer_determines(con), R.layer_aliases(con)
    print(f"{'set':4}{'reader':15}{'readings':>9}{'silent wrong':>14}{'balanced acc.':>15}{'coverage':>10}")
    for name, result, labels_path, how in SETS:
        rows = json.loads((HERE / result).read_text())["rows"]
        labels = {(t["group"], t["q"]): t["expect"] for t in yaml.safe_load((HERE / labels_path).read_text())["tests"]}
        for reader in READERS:
            tally = {p: [0, 0] for p in "ABC"}
            silent = attempted = answerable = n = 0
            for row in (r for r in rows if r["reader"] == reader):
                expect = labels[(row["group"], row["q"])]
                if how == "regrade":
                    g = R.reading_errors({"app_opens": row["reading"]}, {"expect": expect}, determines, aliases)
                    action, out = g["action"], outcome({"ok": g["action_ok"] and not g["errors"], "result": g["action"]})
                else:
                    action, out = row["result"], row["outcome"]
                    for group, words, who, forced in SET1_OVERRIDES:
                        if row["group"] == group and words in row["q"] and who in ("", reader):
                            out = forced
                pile = PILE[expect["type"]]
                tally[pile][0] += out == "correct"
                tally[pile][1] += 1
                silent += out == "silent wrong"
                if pile == "A":
                    answerable += 1
                    attempted += action == "answer"
                n += 1
            per_pile = [ok / total for ok, total in tally.values() if total]
            print(f"{name:4}{reader:15}{n:>9}{silent / n:>14.1%}{sum(per_pile) / len(per_pile):>15.1%}"
                  f"{attempted / answerable:>10.1%}")
            print(f"{'':4}{'':15}{'':>9}{silent:>14}  piles " + "  ".join(
                f"{p} {ok}/{total}" for p, (ok, total) in tally.items() if total))


if __name__ == "__main__":
    main()
