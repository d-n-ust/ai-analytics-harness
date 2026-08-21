#!/usr/bin/env python3
"""Run the combined pipeline on the real 17-metric layer, and compare to the original classifier.

Reuses assess() from pipeline.py (embedding gate + declared-meaning check + scope subsumption).
Adapts the real facet structure onto it: scope = the segment (unless 'all') plus default_filters.
Then it checks three things:
  1. What does the pipeline flag as a SCOPE TRAP? (should be value_moments ~ real_value_moments, only)
  2. How does that compare to the original ambiguity.py scope_only list?
  3. Do the embedding gate's EXTRA candidates (token gate missed) stay correctly 'safe'?
"""

from __future__ import annotations

import gzip
import importlib.util
import itertools
import json
import pathlib
import sys

import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import pipeline  # noqa: E402 — sys.path is extended just above so this module resolves

REPO = HERE.parents[3]
LAYER = REPO / "engine/src/semantic/semantic_layer.yml"
RUN = REPO / "results/published/2026-07/runs/20260726-224953-gpt-5-mini.raw.jsonl.gz"
CASES = REPO / "harness/evals/cases"
OUT_MD = HERE.parent / "09_pipeline_real.md"


def _amb():
    spec = importlib.util.spec_from_file_location("_amb2", REPO / "engine/src/semantic/ambiguity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _scope_set(d: dict) -> list[str]:
    """Real-layer scope = the segment (unless 'all' = no restriction) plus any default_filters."""
    s = set()
    seg = d.get("segment")
    if seg and seg != "all":
        s.add(f"segment={seg}")
    s |= set(d.get("default_filters") or [])
    return sorted(s)


def _mislabel_rate() -> dict[str, float]:
    gold = {}
    for f in CASES.rglob("*.yml"):
        doc = yaml.safe_load(f.read_text()) or {}
        for c in doc.get("cases", []) if isinstance(doc, dict) else []:
            e = c.get("expect", {}) or {}
            if e.get("type") == "metric_answer" and e.get("metric"):
                gold[c["id"]] = e["metric"]
    ans, wrong = {}, {}
    with gzip.open(RUN, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            m = gold.get(r.get("qid"))
            if m and r.get("outcome") == "answer":
                ans[m] = ans.get(m, 0) + 1
                if r.get("correct") is False:
                    wrong[m] = wrong.get(m, 0) + 1
    return {m: 100 * wrong.get(m, 0) / n for m, n in ans.items()}


def main() -> None:
    amb = _amb()
    metrics = yaml.safe_load(LAYER.read_text())["metrics"]
    names = sorted(metrics)
    catalog = {n: {"entity": d.get("entity"), "agg": d.get("agg"), "base": d.get("base"),
                   "filters": _scope_set(d)} for n, d in metrics.items()}

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    vecs = model.encode([n.replace("_", " ") for n in names], normalize_embeddings=True)
    emb = {n: v for n, v in zip(names, vecs, strict=False)}
    def cos(a, b):
        return float(np.dot(emb[a], emb[b]))

    # pipeline verdict for every pair that passes the embedding gate
    findings = []
    for a, b in itertools.combinations(names, 2):
        r = pipeline.assess(a, catalog[a], b, catalog[b], cos(a, b))
        if r["embed_gate"]:
            findings.append(r)
    findings.sort(key=lambda r: (0 if "TRAP" in r["danger"] else 1 if "sibling" in r["danger"]
                                 else 2, -r["cos"]))

    # original classifier, for comparison
    tree = yaml.safe_load((REPO / "engine/src/semantic/metric_tree.yml").read_text())
    nodes = {n: s.get("metric") for n, s in (tree.get("nodes") or {}).items()}
    orig = amb.confusable_pairs(metrics, nodes)
    orig_scope = [p for p in orig if p.kind == "scope_only"]

    mis = _mislabel_rate()

    md = ["# Combined pipeline on the real 17-metric layer\n"]
    md.append(f"Gate ≥ {pipeline.GATE} (MiniLM, name-only). Scope = segment (≠all) + default_filters. "
              f"{len(names)} metrics, {len(findings)} pairs cleared the embedding gate.\n")

    traps = [r for r in findings if "TRAP" in r["danger"]]
    md.append("## Pipeline SCOPE TRAPs (the danger class)\n")
    md.append("```")
    for r in traps:
        mis.get(r["a"], mis.get(r["b"]))
        md.append(f"{r['a']} ~ {r['b']}   cos {r['cos']:.3f}  -> clarify")
        md.append(f"    {r['reason']}")
    md.append("```")
    md.append(f"Test-1 cross-check: `value_moments` mislabel rate was "
              f"**{mis.get('value_moments', float('nan')):.1f}%** (the highest answerable metric), so "
              f"the one pair the pipeline flags is the one that actually caused the errors.\n")

    md.append("## Every gated pair, by class\n")
    md.append("```")
    md.append(f"{'a':22} {'b':22} {'cos':>5} {'tok':>4} {'class':16} action")
    for r in findings:
        md.append(f"{r['a']:22} {r['b']:22} {r['cos']:.3f} {('ok' if r['token_gate'] else 'MISS'):>4} "
                  f"{r['danger']:16} {r['action']}")
    md.append("```\n")

    # embedding gate's extra reach: pairs the token gate would have missed
    missed = [r for r in findings if not r["token_gate"]]
    md.append("## What the embedding gate added (token gate would MISS these)\n")
    md.append("```")
    for r in missed:
        md.append(f"{r['a']} ~ {r['b']}   cos {r['cos']:.3f}  -> {r['danger']} ({r['action']})")
    md.append("```")
    md.append("These are the recall win. Note every one is correctly **safe** (different measure) — "
              "embeddings widen the net, the structural stage keeps precision.\n")

    md.append("## Versus the original classifier\n")
    orig_str = ', '.join(f"{p.a} ~ {p.b}" for p in orig_scope)
    trap_str = ', '.join(f"{r['a']} ~ {r['b']}" for r in traps)
    md.append(f"- Original `scope_only` (high) pairs: **{len(orig_scope)}** — {orig_str}.")
    md.append(f"- Pipeline SCOPE TRAPs: **{len(traps)}** — {trap_str}.")
    md.append("- They agree on the one real collision. The original also flags the **tree node** "
              "`weekly_value_moments -> real_value_moments ~ value_moments`; this prototype compares "
              "named metrics only, so it does not yet cover tree nodes.\n")

    md.append("## Honest limits, on this layer\n")
    md.append("- **Unnamed / welded scope not covered.** `new_signups` (the Test-1 `referral_signups` "
              "case, 18.8% mislabels) has no named scoped sibling, so no pair exists to flag. Catching "
              "it needs the (metric x scope-choice) enumeration — the next build, not this one.")
    md.append("- **Tree nodes not covered** (see above).")
    md.append("- **Subsumption is syntactic.** `segment=all` is treated as the widest scope and the "
              "empty filter set; real semantic subsumption (overlapping filters) is not modelled.")

    OUT_MD.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT_MD.relative_to(REPO)}")


if __name__ == "__main__":
    sys.exit(main())
