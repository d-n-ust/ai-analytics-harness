#!/usr/bin/env python3
"""The collision detector, v2 — precision pass over the whole grounding surface.

Changes from v1 (scored at 93% recall / 90% raw precision but noisy):
  - same-measure requires agreement on >=2 declared meaning facets, not one (kills the
    order_count ~ order_date DUPLICATE class of false positive).
  - pairwise findings are CLUSTERED per collision-type into per-concept groups (the revenue
    family becomes one finding, not 14).
  - the old always-on CROSS_REF pointer is replaced by an EVIDENCE-based cross-layer check: a
    metric documented under the same name is only flagged when the doc prose does not reference
    the columns the metric actually computes on (a real definition conflict), else dropped.

Types: DUPLICATE, SCOPE_TRAP, SIBLING, CONCEPT_FORK, DEFINITION_DIVERGENCE, NAME_COLLISION.
"""

from __future__ import annotations

import itertools
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

import numpy as np
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from grounding import load_env                       # noqa: E402

ENV = HERE.parent / "env_sales"
OUT_MD = HERE.parent / "10_env_findings.md"
OUT_JSON = HERE.parent / "10_env_findings.json"
GATE = 0.55
GENERIC = {"id", "created_at", "updated_at", "email", "currency", "phone", "zip", "city",
           "raw_payload", "tags", "handle", "customer_key", "order_key", "product_key",
           "revenue_key", "date_key", "session_id", "anonymous_id", "referrer", "landing_page"}
_ID = re.compile(r"[a-z_][a-z0-9_]{2,}")


def subsumes(a: tuple, b: tuple) -> bool:
    sa, sb = set(a), set(b)
    return sa < sb or sb < sa


def _cols(s: str | None) -> set[str]:
    return set(_ID.findall(s.lower())) if s else set()


def classify(a, b, cos: float):
    """Return (type, danger, note) or None. Divergence is asserted only with evidence."""
    cross = a.layer != b.layer
    exact = a.label == b.label
    M = ("entity", "agg", "base", "measure")
    shared = [f for f in M if a.meaning[f] is not None and b.meaning[f] is not None]
    meaning_eq = len(shared) >= 2 and all(a.meaning[f] == b.meaning[f] for f in shared)

    # 1. same measure (>=2 shared meaning facets, all agree)
    if meaning_eq:
        if a.scope == b.scope:
            return ("DUPLICATE", "medium", "same measure and scope under two names")
        if subsumes(a.scope, b.scope):
            wide, narrow = (a, b) if set(a.scope) < set(b.scope) else (b, a)
            return ("SCOPE_TRAP", "high",
                    f"same measure; '{narrow.label}' is '{wide.label}' plus a filter — bare "
                    f"question silently scoped, swap invisible")
        return ("SIBLING", "low", "same measure, incomparable scopes — a question must name one")

    # 2. concept fork: same entity+agg+table, DIFFERENT measured column/expr (the revenue family)
    if (a.entity and a.entity == b.entity and a.agg == b.agg and a.base and a.base == b.base
            and a.measure and b.measure and a.measure != b.measure):
        return ("CONCEPT_FORK", "high",
                f"same entity/table aggregated the same way over different columns — a bare concept "
                f"resolves to different numbers")

    # 3. same term, two prose definitions that differ
    if exact and a.layer == "docs" and b.layer == "docs":
        ta, tb = set(a.text.lower().split()), set(b.text.lower().split())
        j = len(ta & tb) / len(ta | tb) if ta and tb else 1.0
        return ("DEFINITION_DIVERGENCE", "high", f"'{a.label}' documented two different ways") if j < 0.6 else None

    # 4. same term across layers with comparable scope that conflicts
    if exact and cross and a.scope and b.scope and set(a.scope) != set(b.scope):
        return ("DEFINITION_DIVERGENCE", "high",
                f"'{a.label}' resolves to a different scope in {a.layer} vs {b.layer}")

    # 5. same term across layers, one side prose — flag only if the doc omits the modelled columns
    if exact and cross:
        sl, dc = (a, b) if a.measure else (b, a)
        cols = _cols(sl.measure)
        if cols and dc.text and not (cols & _cols(dc.text)):
            return ("DEFINITION_DIVERGENCE", "medium",
                    f"'{a.label}' is modelled on {sorted(cols)} but its documentation does not "
                    f"reference those columns")
        return None

    # 6. same term, same layer, different measure -> overloaded name
    if exact:
        return ("NAME_COLLISION", "medium", f"two different '{a.label}' in the {a.layer} layer")

    # 7. near-identical names, different things
    if cos >= 0.82:
        return ("NAME_COLLISION", "low", f"'{a.label}' and '{b.label}' read alike, different things")
    return None


class Union:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, x, y):
        self.p[self.find(x)] = self.find(y)


def main() -> None:
    facts = load_env(ENV)
    by_id = {f.id: f for f in facts}
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    primary = [f for f in facts if (f.layer == "semantic" and f.kind in ("metric", "segment", "dimension"))
               or (f.layer == "docs")]
    warehouse = [f for f in facts if f.layer == "warehouse"]
    pool = primary + warehouse
    vecs = model.encode([f.label.replace("_", " ") for f in pool], normalize_embeddings=True)
    emb = {f.id: v for f, v in zip(pool, vecs)}
    cos = lambda x, y: float(np.dot(emb[x.id], emb[y.id]))

    # collect classified pairs
    pairs = []  # (type, danger, note, a_id, b_id)
    for a, b in itertools.combinations(primary, 2):
        if a.label in GENERIC or b.label in GENERIC:
            continue
        c = cos(a, b)
        if a.label != b.label and c < GATE:
            continue
        v = classify(a, b, c)
        if v:
            pairs.append((*v, a.id, b.id))
    wh_by_label = defaultdict(list)
    for f in warehouse:
        if f.label not in GENERIC:
            wh_by_label[f.label].append(f)
    for p in primary:
        for w in wh_by_label.get(p.label, []):
            v = classify(p, w, 1.0)
            if v:
                pairs.append((*v, p.id, w.id))

    # cluster per type via union-find (per-concept groups instead of pairwise)
    findings = []
    danger_rank = {"high": 0, "medium": 1, "low": 2}
    by_type = defaultdict(list)
    for t, d, note, ai, bi in pairs:
        by_type[t].append((d, note, ai, bi))
    for t, edges in by_type.items():
        uf = Union()
        for _, _, ai, bi in edges:
            uf.union(ai, bi)
        comp_members = defaultdict(set)
        comp_meta = defaultdict(lambda: {"danger": "low", "note": ""})
        for d, note, ai, bi in edges:
            root = uf.find(ai)
            comp_members[root] |= {ai, bi}
            if danger_rank[d] < danger_rank[comp_meta[root]["danger"]] or not comp_meta[root]["note"]:
                comp_meta[root] = {"danger": d, "note": note}
        for root, members in comp_members.items():
            items = [{"id": mid, "label": by_id[mid].label, "layer": by_id[mid].layer}
                     for mid in sorted(members)]
            findings.append({"type": t, "danger": comp_meta[root]["danger"],
                             "note": comp_meta[root]["note"], "items": items})

    # warehouse overloaded column names (>=4 tables) — single-item findings
    col_by_label = defaultdict(list)
    for f in warehouse:
        if f.kind == "column" and f.label not in GENERIC:
            col_by_label[f.label].append(f.base)
    for label, tables in sorted(col_by_label.items()):
        if len(set(tables)) >= 4:
            findings.append({"type": "NAME_COLLISION", "danger": "medium",
                             "note": f"column '{label}' in {len(set(tables))} tables — meaning may differ",
                             "items": [{"id": f"wh:*.{label}", "label": label, "layer": "warehouse"}]})

    findings.sort(key=lambda f: (danger_rank[f["danger"]], f["type"], -len(f["items"])))
    OUT_JSON.write_text(json.dumps(findings, indent=1))

    bt, bd = Counter(f["type"] for f in findings), Counter(f["danger"] for f in findings)
    md = ["# Collision detector v2 (clustered) over the sales environment\n"]
    md.append(f"{len(facts)} grounding facts. {len(findings)} collision findings "
              f"(clustered per concept). By type: {dict(bt)}. By danger: {dict(bd)}.\n")
    for dl in ("high", "medium", "low"):
        rows = [f for f in findings if f["danger"] == dl]
        if not rows:
            continue
        md.append(f"## {dl.upper()} ({len(rows)})\n```")
        for f in rows:
            items = "  ~  ".join(f"{it['label']}[{it['layer'][:3]}]" for it in f["items"])
            md.append(f"[{f['type']}] {items}")
            md.append(f"    {f['note']}")
        md.append("```\n")
    OUT_MD.write_text("\n".join(md))
    print("\n".join(md[:3]))
    print(f"wrote {OUT_MD.name} and {OUT_JSON.name}  ({len(findings)} findings)")


if __name__ == "__main__":
    sys.exit(main())
