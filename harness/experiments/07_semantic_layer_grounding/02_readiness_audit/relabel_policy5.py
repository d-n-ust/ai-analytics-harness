#!/usr/bin/env python3
"""Relabel the development sets to design draft 5 (the owner's decisions, 2026-10-10): a misspelling,
synonym or narrower word is answered and stated (`assumption: true`); a period partly inside the data is
answered for the covered part and stated (`partial: true`). Only development sets: the two replication
sets were burned when their failures were read.

    python relabel_policy5.py      # writes *_policy5.yml beside each set
"""
from __future__ import annotations

import copy
import pathlib
import re

import yaml

HERE = pathlib.Path(__file__).resolve().parent
TYPOS = re.compile(r"\b(andriod|refferal|referal)\b", re.I)


def answer(params: dict, kind: str = "metric_answer", **flags) -> dict:
    return {"type": kind, "metric": "app_opens", "params": params, **flags}


# (set, group or block) -> new expectation, from each item's own wording and the decided policy
RULES = {
    ("dev", "undeclared synonym (other value)"): answer({"platform": "ios", "period": "2026-06"}, assumption=True),
    ("dev", "season (declared, partly covered)"): answer({"platform": "android", "period": "2026-06-01/2026-08-31"}, partial=True),
    ("r1", "i03"): answer({"platform": "android", "period": "2026-05"}, assumption=True),       # Samsung phones
    ("r1", "i14"): answer({"region": "Americas", "period": "2025"}, partial=True),
    ("r1", "i16"): answer({"period": "2025-09-01/2025-11-30", "group_by": ["metric_time"], "time_grain": "week"},
                          "breakdown", partial=True),
    ("r2", "i03"): answer({"platform": ["android", "ios"], "period": "2025", "group_by": ["platform"]},
                          "breakdown", partial=True),
    ("r2", "i09"): answer({"platform": "ios", "period": "2026-05"}, assumption=True),           # iPhone users
    ("r2", "i10"): answer({"country_name": "Germany", "period": "2026-Q2"}, assumption=True),   # Deutschland
    ("r2", "i18"): answer({"channel": ["content_seo", "organic", "paid_search", "partnerships"], "period": "2026"},
                          partial=True),
    ("r2", "i19"): {"type": "clarify", "metric": "app_opens", "params": {"country_name": "Brazil", "period": "ask"}},
    ("r2", "i21"): answer({"period": "2026-07", "group_by": ["platform", "region", "channel"]}, "breakdown", partial=True),
}
SETS = {"dev": "tests_dev.yml", "r1": "replication/tests_corrected.yml", "r2": "replication2/tests_corrected.yml"}


def main() -> None:
    for key, path in SETS.items():
        tests = yaml.safe_load((HERE / path).read_text())["tests"]
        out, changed = [], 0
        for t in tests:
            t = copy.deepcopy(t)
            new = RULES.get((key, t.get("group") or t.get("block")))
            if key == "r1" and t.get("group") == "i10" and "the States" in t["q"]:
                new = answer({"country": "US", "period": "2025-10"}, assumption=True)
            if new is not None:
                t["expect"] = new
            elif TYPOS.search(t["q"]) and t["expect"]["type"] in ("metric_answer", "breakdown"):
                t["expect"] = {**t["expect"], "assumption": True}
            else:
                out.append(t)
                continue
            changed += 1
            out.append(t)
        target = HERE / path.replace(".yml", "_policy5.yml")
        target.write_text(f"# {path} relabelled to design draft 5 by relabel_policy5.py. Development data.\n"
                          + yaml.safe_dump({"tests": out}, sort_keys=False, allow_unicode=True, width=120))
        print(f"{target.relative_to(HERE)}: {changed} of {len(out)} relabelled")


if __name__ == "__main__":
    main()
