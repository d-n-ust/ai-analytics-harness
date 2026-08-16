#!/usr/bin/env python3
"""Score the detector AND the original blind LLM gold against the HUMAN-blessed gold.

Human gold = the 9 red-team-consensus-high clusters + the 13 disputes the practitioner personally
confirmed dangerous (below). We ask: of the human's high-danger collisions, how many does the v3
detector flag high, and how many did the original single-LLM GROUND_TRUTH.yml flag high? Whoever
recalls the human better is the one that agrees with the practitioner.
"""

from __future__ import annotations

import json
import pathlib
import re

import yaml

HERE = pathlib.Path(__file__).resolve()
ENV = HERE.parent / "env_retail"
CLUSTERS = json.loads((ENV / "redteam/clusters.json").read_text())

# the 13 disputed clusters the human ruled DANGEROUS (Pile 1 ten + region + store keys + product keys)
CONFIRMED = {
    "margin_which_cost_which_denominator", "store_ops_sales_tax_in", "online_status_filter_missing",
    "aov_mislabeled_and_overlapping", "inventory_three_numbers", "gross_margin_pct_mixes_gross_and_net",
    "average_basket_gross_vs_net", "loyalty_penetration_basket_vs_dollar", "v_active_members_flag_based",
    "is_comp_value_Y_vs_true_vs_1", "region_five_vs_six", "store_identifier_codes", "product_key_sprawl",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(s).lower())


def _overlap(a: set, b: set) -> int:
    return len(a & b)


def main() -> None:
    human = [c for c in CLUSTERS if c["n_high"] == 3 or c["id"] in CONFIRMED]
    for c in human:
        c["labelset"] = {_norm(x) for x in c["labels"]}

    # detector high findings -> label sets
    det = json.loads((ENV / "findings.json").read_text())
    det_high = [{_norm(it["label"]) for it in f["items"]} for f in det if f["danger"] == "high"]

    # original LLM gold high findings -> identifier tokens from prose refs
    gold = yaml.safe_load((ENV / "GROUND_TRUTH.yml").read_text())["findings"]
    gold_high = []
    for f in gold:
        if f.get("danger") != "high":
            continue
        toks = set()
        for it in f["items"]:
            for m in re.findall(r"[a-z][a-z0-9_]{2,}", str(it.get("ref", "")).lower()):
                toks.add(_norm(m))
        gold_high.append(toks)

    def hit(labelset: set, candidates: list) -> bool:
        need = 1 if len(labelset) == 1 else 2
        return any(_overlap(labelset, c) >= need for c in candidates)

    rows = []
    for c in human:
        rows.append({"id": c["id"], "consensus": c["n_high"] == 3,
                     "det": hit(c["labelset"], det_high), "gold": hit(c["labelset"], gold_high)})

    det_r = sum(r["det"] for r in rows)
    gold_r = sum(r["gold"] for r in rows)
    n = len(rows)

    md = ["# Human-gold scorecard (retail)\n",
          f"Human high-danger gold: **{n}** collisions (9 red-team-consensus + 13 practitioner-confirmed).\n",
          "Who agrees with the human:\n```",
          f"  detector (v3) recall on human gold ... {det_r}/{n} ({100*det_r/n:.0f}%)",
          f"  original LLM gold recall on human ... {gold_r}/{n} ({100*gold_r/n:.0f}%)",
          "```\n",
          "Per collision (D = v3 detector flagged high, G = original LLM gold flagged high):\n```"]
    for r in sorted(rows, key=lambda r: (not r["consensus"], r["id"])):
        tag = "consensus" if r["consensus"] else "you-ruled"
        md.append(f"  [{'D' if r['det'] else '.'}{'G' if r['gold'] else '.'}] {r['id']:42} ({tag})")
    md.append("```")
    md.append("\nD. = the detector missed it; .G = only the LLM gold had it; .. = BOTH missed a "
              "collision the human confirmed (the real blind spots).")
    misses = [r for r in rows if not r["det"] and not r["gold"]]
    if misses:
        md.append(f"\n**Both missed ({len(misses)}):** " + ", ".join(r["id"] for r in misses))

    (ENV / "human_scorecard.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
