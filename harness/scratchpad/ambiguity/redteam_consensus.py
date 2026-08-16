#!/usr/bin/env python3
"""Consensus / dispute analysis over the 3 red-team judges' independent labels.

Clusters each judge's findings across judges (a collision = a set of items they share), then:
  CONSENSUS  — flagged by all 3 with the SAME danger  -> settled gold, no human needed
  SPLIT      — flagged by all 3 but danger differs     -> escalate (danger call)
  MAJORITY   — flagged by 2 of 3                        -> escalate (borderline existence)
  SINGLE     — flagged by only 1                        -> escalate (is it real?)

The human adjudicates only the escalations; consensus + rulings = the human-blessed gold.
"""

from __future__ import annotations

import pathlib
import re
import sys
from collections import defaultdict

import yaml

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import grounding                                       # noqa: E402

RT = HERE.parent / "env_retail/redteam"
ENV = HERE.parent / "env_retail"
OUT = RT / "consensus.md"
_DMAX = {"high": 3, "medium": 2, "low": 1, None: 0}
_GENERIC = {"id", "name", "status", "date", "type", "amount", "value", "count", "code",
            "price", "cost", "total", "description", "created_at", "updated_at", "qty",
            "flag", "key", "date_key", "row", "column", "table", "number"}


def _vocab() -> set[str]:
    """Distinctive real entity names from the environment (metric/segment/dimension/view names, and
    non-generic column/table names). Grounding the match in real labels beats prose-token Jaccard."""
    v = set()
    for f in grounding.load_env(ENV):
        lab = f.label.lower()
        if len(lab) < 4:
            continue
        if f.kind in ("metric", "segment", "dimension", "view", "table") or (
                f.kind in ("column", "term") and lab not in _GENERIC):
            v.add(lab)
    return v


VOCAB = _vocab()


def _labels(f: dict) -> set[str]:
    """The distinctive real entity names a finding references (from its item refs)."""
    text = " ".join(str(it.get("ref", "")).lower() for it in f.get("items", []))
    return {v for v in VOCAB if re.search(r"(?<![a-z0-9_])" + re.escape(v) + r"(?![a-z0-9_])", text)}


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def main() -> None:
    judges = {}
    for j in (1, 2, 3):
        p = RT / f"judge_{j}.yml"
        if not p.exists():
            print(f"missing {p.name} — judges not all done yet")
            return
        doc = yaml.safe_load(p.read_text())
        judges[j] = doc if isinstance(doc, list) else doc.get("findings", [])

    nodes = [(j, i) for j in judges for i in range(len(judges[j]))]
    lab = {n: _labels(judges[n[0]][n[1]]) for n in nodes}
    nolabel = sum(1 for n in nodes if not lab[n])

    # greedy clustering on REAL entity labels: a finding joins a cluster if it shares >=2 distinctive
    # labels with the representative (>=1 for a single-label finding). Real names are distinctive, so
    # this neither chains (like raw-token >=2) nor scatters (like prose Jaccard). Largest findings seed.
    order = sorted((n for n in nodes if lab[n]), key=lambda n: -len(lab[n]))
    members: list[list] = []
    reps: list[set] = []
    for n in order:
        placed = False
        for k, rep in enumerate(reps):
            shared = len(lab[n] & rep)
            if shared >= 2 or (min(len(lab[n]), len(rep)) == 1 and shared >= 1):
                members[k].append(n)
                placed = True
                break
        if not placed:
            reps.append(lab[n])
            members.append([n])

    rows = []
    for mem in members:
        dmax = {1: None, 2: None, 3: None}
        for j, i in mem:
            d = judges[j][i]["danger"]
            if _DMAX[d] > _DMAX[dmax[j]]:
                dmax[j] = d
        n_high = sum(1 for j in (1, 2, 3) if dmax[j] == "high")
        n_present = sum(1 for j in (1, 2, 3) if dmax[j])
        labels = sorted(set().union(*(lab[n] for n in mem)))
        rep_f = judges[mem[0][0]][mem[0][1]]
        rows.append({"dmax": dmax, "n_high": n_high, "n_present": n_present, "id": rep_f["id"],
                     "labels": labels, "why": rep_f.get("confusable_because", "")})

    consensus_high = [r for r in rows if r["n_high"] == 3]
    disputed_high = [r for r in rows if 1 <= r["n_high"] <= 2]
    disputed_high.sort(key=lambda r: (-r["n_high"], -r["n_present"]))

    md = ["# Red-team consensus / dispute analysis (retail)\n",
          f"Judges: 1={len(judges[1])} findings, 2={len(judges[2])}, 3={len(judges[3])} "
          f"({nolabel} findings had no distinctive entity label and were skipped). "
          f"Clustered into {len(rows)} distinct candidate collisions.\n",
          f"Only **high-danger** disagreements are escalated (a medium/low split is not worth "
          f"your time). Consensus-high: **{len(consensus_high)}** settled. High-danger disputes to "
          f"rule: **{len(disputed_high)}**.\n"]

    md.append("## Settled — all 3 judges rated HIGH (no human needed)\n```")
    for r in consensus_high:
        md.append(f"{r['id']:36}  {', '.join(r['labels'][:5])}")
    md.append("```\n")

    md.append("## ESCALATE — high-danger DISPUTES (your call)\n")
    md.append("`n=high/3` is how many judges called it HIGH; J1=finance, J2=merch, J3=data-eng "
              "(dash = that judge did not flag it at all).\n```")
    for r in disputed_high:
        dl = " ".join(f"J{j}={r['dmax'][j] or '-'}" for j in (1, 2, 3))
        md.append(f"[{r['n_high']}/3 high] {r['id']:34} {dl}")
        md.append(f"    items: {', '.join(r['labels'][:6])}")
        if r["why"]:
            md.append(f"    why: {r['why'][:130]}")
    md.append("```")

    OUT.write_text("\n".join(md))
    print("\n".join(md[:6]))
    print(f"\nconsensus-high {len(consensus_high)}, disputed-high {len(disputed_high)}; wrote {OUT.name}")


if __name__ == "__main__":
    main()
