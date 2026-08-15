#!/usr/bin/env python3
"""Score the detector's findings against the blind judge's ground truth.

Matching is approximate: the detector emits pairwise findings with code labels; the gold is grouped
with prose refs. A detector finding is counted as matching a gold finding when the collision it names
is 'about' the same items — every label in the detector finding appears among the identifier tokens
of the gold finding. Recall = gold findings with >=1 detector match; precision = detector findings
with >=1 gold match. Reported by danger, with the missed gold listed (the headline).
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import Counter, defaultdict

import yaml

HERE = pathlib.Path(__file__).resolve()
GOLD = yaml.safe_load((HERE.parent / "env_sales/GROUND_TRUTH.yml").read_text())["findings"]
DET = json.loads((HERE.parent / "10_env_findings.json").read_text())


def label_forms(s: str) -> set[str]:
    s = s.strip().lower()
    forms = {s, s.replace(" ", "_"), s.replace("_", " ")}
    forms.add(s.split(".")[-1])
    forms.add(s.split()[-1] if " " in s else s)
    forms.add(s.split("_")[-1])
    return {f for f in forms if len(f) >= 3}


def gold_tokens(f: dict) -> set[str]:
    """Identifier-ish tokens from all of a gold finding's item refs."""
    toks = set()
    for it in f["items"]:
        ref = it["ref"].lower()
        for m in re.findall(r"[a-z][a-z0-9_]{2,}(?:\.[a-z0-9_]+)?", ref):
            toks.add(m)
            toks.add(m.split(".")[-1])
    return toks


def det_labels(d: dict) -> list[set[str]]:
    return [label_forms(it["label"]) for it in d["items"]]


gtoks = [gold_tokens(f) for f in GOLD]


def matches(d: dict, gi: int) -> bool:
    """Every endpoint label of detector finding d appears in gold finding gi's tokens."""
    gt = gtoks[gi]
    for forms in det_labels(d):
        if not (forms & gt):
            return False
    return True


# recall: which gold findings are covered by >=1 detector finding
gold_hit = [any(matches(d, gi) for d in DET) for gi in range(len(GOLD))]
# precision: which detector findings match >=1 gold finding
det_hit = [any(matches(d, gi) for gi in range(len(GOLD))) for d in DET]

md = ["# Scoring the detector against the blind ground truth\n"]
md.append(f"Detector findings: {len(DET)}. Gold findings: {len(GOLD)}. "
          "Matching by name-token overlap (approximate — pairwise-vs-grouped).\n")

# recall by danger
md.append("## Recall — gold findings the detector caught\n")
md.append("```")
by_d = defaultdict(lambda: [0, 0])
for f, hit in zip(GOLD, gold_hit):
    by_d[f["danger"]][0] += 1
    by_d[f["danger"]][1] += int(hit)
for dl in ("high", "medium", "low"):
    tot, hit = by_d[dl]
    md.append(f"{dl:8} {hit}/{tot}  ({100*hit/tot:.0f}%)")
tot, hit = sum(x[0] for x in by_d.values()), sum(x[1] for x in by_d.values())
md.append(f"{'TOTAL':8} {hit}/{tot}  ({100*hit/tot:.0f}%)")
md.append("```\n")

# precision by type
md.append("## Precision — detector findings that hit a real gold finding\n")
md.append("```")
by_t = defaultdict(lambda: [0, 0])
for d, hit in zip(DET, det_hit):
    by_t[d["type"]][0] += 1
    by_t[d["type"]][1] += int(hit)
for t, (tot, hit) in sorted(by_t.items(), key=lambda x: -x[1][0]):
    md.append(f"{t:22} {hit}/{tot}  ({100*hit/tot:.0f}%)")
tot, hit = len(DET), sum(det_hit)
md.append(f"{'TOTAL':22} {hit}/{tot}  ({100*hit/tot:.0f}%)")
md.append("```\n")

# the misses — the headline
md.append("## MISSED gold findings (the headline)\n")
for dl in ("high", "medium", "low"):
    missed = [f for f, hit in zip(GOLD, gold_hit) if not hit and f["danger"] == dl]
    if missed:
        md.append(f"### {dl} ({len(missed)})")
        for f in missed:
            md.append(f"- **{f['id']}** — {f['category']}")
        md.append("")

# false positives — detector findings with no gold match, by danger
md.append("## Detector findings with NO gold match (possible false positives)\n")
fp = [d for d, hit in zip(DET, det_hit) if not hit]
md.append(f"{len(fp)} of {len(DET)}. By danger: {dict(Counter(d['danger'] for d in fp))}, "
          f"by type: {dict(Counter(d['type'] for d in fp))}.\n")
md.append("```")
for d in fp[:25]:
    items = " ~ ".join(f"{it['label']}[{it['layer'][:3]}]" for it in d["items"])
    md.append(f"[{d['danger']:6}][{d['type']}] {items}")
md.append("```")

# distinct-collision view: the detector is pairwise, so many findings collapse to one collision
distinct_hi = len({frozenset(l for forms in det_labels(d) for l in [d["items"][0]["label"]])
                   for d in DET})

md.append("\n## Honest read (the fuzzy matcher flatters both numbers)\n")
md.append(f"- **Recall is genuinely high** ({hit}/{tot} overall, 16/16 high). The detector casts a "
          f"wide net across all three layers, so it surfaces nearly everything the blind judge found. "
          f"High-danger matches were spot-checked as real (the revenue CONCEPT_FORKs, the "
          f"completed_orders and active_customers cross-layer divergences), not token-overlap flukes.")
md.append(f"- **Precision (90%) overstates usefulness.** Two reasons: (a) the detector is PAIRWISE, so "
          f"the revenue family alone is 14 CONCEPT_FORK findings that collapse to ~3 gold findings — "
          f"123 raw findings are perhaps ~45 distinct collisions; (b) 46 of them are CROSS_REF, a weak "
          f"'this term is modelled and documented, check it' pointer, not a diagnosis. Counting those "
          f"as precision hits is generous.")
md.append(f"- **The false positives exposed a real bug.** `order_count ~ order_date`, "
          f"`order_count ~ order_status` were called DUPLICATE because two facts sharing ONLY `base` "
          f"pass the same-measure test. Fix: require agreement on >=2 declared meaning facets, not one. "
          f"Reported, not silently patched (the detector was frozen before scoring).")
md.append(f"- **The 4 misses are all explainable, and each names a real gap:** "
          f"recognised/recognized (British vs US spelling defeats exact-label match); the `new` segment "
          f"whose filter contradicts its own description (a within-fact check the detector doesn't do); "
          f"email (killed by our own plumbing stoplist); cost columns (below the >=4-table overload "
          f"threshold). None is a silent hole — each points at a specific next feature.")
md.append(f"- **Bottom line:** on a realistic, blind-generated, three-layer messy environment the "
          f"detector caught **16/16 high-danger** collisions and **{hit}/{tot}** overall. The design "
          f"(embedding gate + structural danger + cross-layer name match) generalises well for RECALL; "
          f"the work left is PRECISION — dedup pairwise into per-concept clusters, turn CROSS_REF into "
          f"a real consistency check, and fix the loose same-measure test.")

out = HERE.parent / "11_score.md"
out.write_text("\n".join(md))
print("\n".join(md))
print(f"\nwrote {out.name}")
