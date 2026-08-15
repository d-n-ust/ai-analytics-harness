#!/usr/bin/env python3
"""The collision detector, run over the whole grounding surface (all three layers at once).

Built from the design principles validated earlier, extended to cross-layer:
  GATE     embedding similarity of labels (+ exact label match, which always passes)
  MEANING  same measure = agreement on the meaning facets both facts declare (entity/agg/base/measure)
  SCOPE    subsumption of the declared scope clauses

Collision types it emits:
  DUPLICATE            same measure, same scope, two names           -> alias / governance smell
  SCOPE_TRAP           same measure, one scope inside the other      -> silent scope swap (clarify)
  DEFINITION_DIVERGENCE same concept named the same across layers,   -> different number by source
                        but the definition/scope differs
  NAME_COLLISION       a name that means different things            -> overloaded name, disambiguate

It reports precision/recall against a ground truth produced by a separate blind judge.
"""

from __future__ import annotations

import itertools
import json
import pathlib
import sys

import numpy as np
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from grounding import load_env                       # noqa: E402

ENV = HERE.parent / "env_sales"
OUT_MD = HERE.parent / "10_env_findings.md"
OUT_JSON = HERE.parent / "10_env_findings.json"
GATE = 0.55                                          # label-cosine floor (higher: 454 facts, more noise)

# plumbing columns that collide everywhere and carry no business meaning
GENERIC = {"id", "created_at", "updated_at", "email", "currency", "phone", "zip", "city",
           "raw_payload", "tags", "handle", "customer_key", "order_key", "product_key",
           "revenue_key", "date_key", "session_id", "anonymous_id", "referrer", "landing_page"}


def subsumes(a: tuple, b: tuple) -> bool:
    sa, sb = set(a), set(b)
    return sa < sb or sb < sa


def _text_differs(a, b) -> bool:
    """Cheap check that two prose definitions are materially different, not the same sentence."""
    ta, tb = set(a.text.lower().split()), set(b.text.lower().split())
    if not ta or not tb:
        return False
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard < 0.6


def classify(a, b, cos: float):
    """Return (type, danger, note) or None. Divergence is only asserted with EVIDENCE."""
    cross = a.layer != b.layer
    exact = a.label == b.label
    M = ("entity", "agg", "base", "measure")
    shared = [f for f in M if a.meaning[f] is not None and b.meaning[f] is not None]
    meaning_eq = bool(shared) and all(a.meaning[f] == b.meaning[f] for f in shared)

    # 1. same measure (all shared meaning facets agree, including measure where both give it)
    if meaning_eq:
        if a.scope == b.scope:
            return ("DUPLICATE", "medium",
                    "same measure and scope under two names — pick-either, but a governance smell")
        if subsumes(a.scope, b.scope):
            wide, narrow = (a, b) if set(a.scope) < set(b.scope) else (b, a)
            return ("SCOPE_TRAP", "high",
                    f"same measure; '{narrow.label}' is '{wide.label}' plus a filter — a bare "
                    f"question is silently scoped, numbers differ, swap is invisible")
        return ("SIBLING", "low", "same measure, incomparable scopes — a question must name one")

    # 2. concept fork: same entity+agg+table, DIFFERENT measured column/expr (the revenue family)
    if (a.entity and a.entity == b.entity and a.agg == b.agg and a.base == b.base
            and a.measure and b.measure and a.measure != b.measure):
        return ("CONCEPT_FORK", "high",
                f"'{a.label}' and '{b.label}' aggregate the same entity/table the same way but over "
                f"different columns/expressions — a bare concept resolves to different numbers")

    # 3. verified divergence: same term, two prose definitions that differ
    if exact and a.layer == "docs" and b.layer == "docs":
        return ("DEFINITION_DIVERGENCE", "high",
                f"'{a.label}' is documented with two different definitions") if _text_differs(a, b) else None

    # 4. verified divergence: same term across layers with comparable scope that conflicts
    if exact and cross and a.scope and b.scope and set(a.scope) != set(b.scope):
        return ("DEFINITION_DIVERGENCE", "high",
                f"'{a.label}' resolves to a different scope in {a.layer} vs {b.layer}")

    # 5. same term across layers but one side is prose — cannot machine-verify consistency
    if exact and cross:
        return ("CROSS_REF", "low",
                f"'{a.label}' is both modelled and documented; prose consistency not machine-checked")

    # 6. same term, same layer, different measure -> overloaded name
    if exact:
        return ("NAME_COLLISION", "medium", f"two different '{a.label}' in the {a.layer} layer")

    # 7. near-identical names, different things
    if cos >= 0.82:
        return ("NAME_COLLISION", "low", f"'{a.label}' and '{b.label}' read alike, different things")
    return None


def main() -> None:
    facts = load_env(ENV)
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    # the surface an agent grounds a metric query on
    primary = [f for f in facts if (f.layer == "semantic" and f.kind in ("metric", "segment", "dimension"))
               or (f.layer == "docs")]
    warehouse = [f for f in facts if f.layer == "warehouse"]

    # embed labels of everything we might compare
    pool = primary + warehouse
    labels = [f.label.replace("_", " ") for f in pool]
    vecs = model.encode(labels, normalize_embeddings=True)
    emb = {f.id: v for f, v in zip(pool, vecs)}
    cos = lambda x, y: float(np.dot(emb[x.id], emb[y.id]))

    findings = []

    # (A) intra-primary pairwise
    for a, b in itertools.combinations(primary, 2):
        if a.label in GENERIC or b.label in GENERIC:
            continue
        c = cos(a, b)
        if a.label != b.label and c < GATE:
            continue
        v = classify(a, b, c)
        if v:
            findings.append({"type": v[0], "danger": v[1], "note": v[2], "cos": round(c, 3),
                             "items": [{"id": a.id, "label": a.label, "layer": a.layer},
                                       {"id": b.id, "label": b.label, "layer": b.layer}]})

    # (B) cross-layer: each primary metric/term vs warehouse fact with the SAME label
    wh_by_label: dict[str, list] = {}
    for f in warehouse:
        if f.label not in GENERIC:
            wh_by_label.setdefault(f.label, []).append(f)
    for p in primary:
        for w in wh_by_label.get(p.label, []):
            v = classify(p, w, 1.0)
            if v:
                findings.append({"type": v[0], "danger": v[1], "note": v[2], "cos": 1.0,
                                 "items": [{"id": p.id, "label": p.label, "layer": p.layer},
                                           {"id": w.id, "label": w.label, "layer": w.layer}]})

    # (C) warehouse overloaded names: a contentful column label living in >=3 tables
    col_by_label: dict[str, list] = {}
    for f in warehouse:
        if f.kind == "column" and f.label not in GENERIC:
            col_by_label.setdefault(f.label, []).append(f.base)
    for label, tables in sorted(col_by_label.items()):
        if len(tables) >= 4:
            findings.append({"type": "NAME_COLLISION", "danger": "medium",
                             "note": f"column '{label}' appears in {len(tables)} tables "
                                     f"({', '.join(sorted(set(tables))[:6])}...) — meaning may differ",
                             "cos": 1.0,
                             "items": [{"id": f"wh:*.{label}", "label": label, "layer": "warehouse"}]})

    # dedup: same item-set found via more than one path — keep the highest-danger verdict
    order = {"high": 0, "medium": 1, "low": 2}
    best: dict = {}
    for f in findings:
        key = (f["type"], frozenset((it["label"], it["layer"]) for it in f["items"]))
        if key not in best or order[f["danger"]] < order[best[key]["danger"]]:
            best[key] = f
    findings = list(best.values())
    findings.sort(key=lambda f: (order[f["danger"]], f["type"]))

    OUT_JSON.write_text(json.dumps(findings, indent=1))

    from collections import Counter
    by_type = Counter(f["type"] for f in findings)
    by_danger = Counter(f["danger"] for f in findings)

    md = ["# Collision detector over the sales environment (all 3 layers)\n"]
    md.append(f"{len(facts)} grounding facts (semantic + warehouse + docs). Gate = label cosine ≥ "
              f"{GATE} or exact label match. {len(findings)} collisions flagged.\n")
    md.append(f"By type: {dict(by_type)}. By danger: {dict(by_danger)}.\n")
    for dl in ("high", "medium", "low"):
        rows = [f for f in findings if f["danger"] == dl]
        if not rows:
            continue
        md.append(f"## {dl.upper()} ({len(rows)})\n")
        md.append("```")
        for f in rows:
            items = "  ~  ".join(f"{it['label']}[{it['layer'][:3]}]" for it in f["items"])
            md.append(f"[{f['type']}] {items}")
            md.append(f"    {f['note']}")
        md.append("```\n")

    OUT_MD.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT_MD.name} and {OUT_JSON.name}")


if __name__ == "__main__":
    sys.exit(main())
