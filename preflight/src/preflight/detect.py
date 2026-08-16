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
import re
from collections import defaultdict

from ._gate import make_gate

GATE = 0.55
WH_SYN = 0.82           # similarity floor for warehouse near-synonym columns (higher: 300+ columns)
_ID = re.compile(r"[a-z_][a-z0-9_]{2,}")
_TECH = {"id", "raw_payload", "tags", "currency", "zip", "phone", "handle", "referrer",
         "landing_page", "anonymous_id"}


def _is_plumbing(label: str) -> bool:
    """Drop by ROLE, not by a hand list: surrogate keys, timestamps, and pure technical columns.
    Keeps business keys (`customer_id` vs `user_id` is a real collision) and `email` (a real rename)."""
    l = label.lower()
    return (l in _TECH or l.endswith("_key") or l.endswith("_at")
            or l in ("created_at", "updated_at"))


def _constraints(scope: tuple) -> dict:
    return {(col, kind): payload for col, kind, payload in scope}


def _pop_subset(narrow: tuple, wide: tuple) -> bool:
    """Is population(narrow) ⊆ population(wide)? Every constraint the wider side imposes must be
    implied by the narrower one — value-sets widen (status∈{completed} ⊆ {completed,fulfilled}),
    the narrow side may add columns. Compares MEANING of the population, not raw SQL strings."""
    cn, cw = _constraints(narrow), _constraints(wide)
    for (col, kind), pw in cw.items():
        pn = cn.get((col, kind))
        if pn is None:
            return False
        if kind == "set":
            if not (pn <= pw):
                return False
        elif pn != pw:
            return False
    return True


def scope_equal(a, b) -> bool:
    return frozenset(a.scope) == frozenset(b.scope)


def subsumes(a, b) -> bool:
    """One population strictly inside the other (a real scope trap), by parsed predicates."""
    if scope_equal(a, b):
        return False
    return _pop_subset(a.scope, b.scope) or _pop_subset(b.scope, a.scope)


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
        if scope_equal(a, b):
            if a.grain == b.grain:
                return ("DUPLICATE", "low", "same measure, scope and grain under two names")
            # same population, different grain — a semi-/non-additive measure cannot be rolled up
            add = a.additive or b.additive
            danger = "high" if add in ("semi", "non") else "medium"
            return ("GRAIN_MISMATCH", danger,
                    f"same measure and population at different grain ('{a.grain}' vs '{b.grain}'); "
                    f"the measure is {add or 'additive'}"
                    + (" and cannot be summed across that grain" if add in ("semi", "non") else ""))
        if subsumes(a, b):
            narrow, wide = (a, b) if _pop_subset(a.scope, b.scope) else (b, a)
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


def detect_collisions(facts, gate="auto", model=None) -> list[dict]:
    """Detect confusable grounding facts across the whole surface, most dangerous first.

    `gate` selects the confusability gate — which name-pairs are alike enough to examine (danger is
    then decided structurally, never by similarity). "auto" uses embeddings when installed and falls
    back to a dependency-free lexical gate; "lexical" forces the fallback; "embeddings" requires the
    optional extra. Any object with `.encode` may be passed as `model` (or positionally as `gate`)
    to reuse one instance and reproduce a specific model's ranking."""
    if not isinstance(gate, str):        # a model object passed positionally (back-compat)
        model, gate = gate, "embeddings"
    by_id = {f.id: f for f in facts}
    # the grounding surface an agent queries on = everything except raw warehouse structure
    primary = [f for f in facts if (f.layer in ("semantic", "queries")
                                    and f.kind in ("metric", "segment", "dimension", "query"))
               or (f.layer == "docs")]
    warehouse = [f for f in facts if f.layer == "warehouse"]
    pool = primary + warehouse
    sim, _gate_name = make_gate([f.label for f in pool], kind=gate, model=model)
    cos = lambda x, y: sim(x.label, y.label)

    # collect classified pairs
    pairs = []  # (type, danger, note, a_id, b_id)
    for a, b in itertools.combinations(primary, 2):
        if _is_plumbing(a.label) or _is_plumbing(b.label):
            continue
        c = cos(a, b)
        if a.label != b.label and c < GATE:
            continue
        v = classify(a, b, c)
        if v:
            pairs.append((*v, a.id, b.id))
    wh_by_label = defaultdict(list)
    for f in warehouse:
        if not _is_plumbing(f.label):
            wh_by_label[f.label].append(f)
    for p in primary:
        for w in wh_by_label.get(p.label, []):
            v = classify(p, w, 1.0)
            if v:
                pairs.append((*v, p.id, w.id))

    # warehouse near-synonym columns (the AE gap: on_hand ~ qty_on_hand, extended_price ~ line_amount)
    wh_cols = [f for f in warehouse if f.kind == "column" and not _is_plumbing(f.label)]
    seen_label = {}
    uniq = []                                    # one representative per (label) to cut 300->~120
    for f in wh_cols:
        if f.label not in seen_label:
            seen_label[f.label] = f
            uniq.append(f)
    for a, b in itertools.combinations(uniq, 2):
        if a.label == b.label or cos(a, b) < WH_SYN:
            continue
        pairs.append(("NAME_COLLISION", "low",
                      f"warehouse columns '{a.label}' and '{b.label}' read alike — likely the same "
                      f"thing under two names, or two things under alike names", a.id, b.id))

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
        if f.kind == "column" and not _is_plumbing(f.label):
            col_by_label[f.label].append(f.base)
    for label, tables in sorted(col_by_label.items()):
        if len(set(tables)) >= 4:
            findings.append({"type": "NAME_COLLISION", "danger": "medium",
                             "note": f"column '{label}' in {len(set(tables))} tables — meaning may differ",
                             "items": [{"id": f"wh:*.{label}", "label": label, "layer": "warehouse"}]})

    findings.sort(key=lambda f: (danger_rank[f["danger"]], f["type"], -len(f["items"])))
    return findings
