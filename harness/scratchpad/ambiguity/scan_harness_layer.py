#!/usr/bin/env python3
"""Scan the harness's own governed semantic layer with preflight — a reality check on the
habit-tracking domain before we build the sprawl experiment.

The harness's semantic_layer.yml is dict-keyed (metric name -> definition), with the aggregate as a
SQL expression and the population in `default_filters`. This is experiment glue, not a preflight
dialect: it converts that format into preflight GroundingFacts using preflight's public building
blocks, so the package stays free of a harness-specific adapter.

    python scan_harness_layer.py [path/to/semantic_layer.yml]
"""

from __future__ import annotations

import pathlib
import sys

import sqlglot
import yaml
from preflight import GroundingFact, detect_collisions
from preflight.adapters import additivity
from preflight.scope import build_scope
from sqlglot import exp

DEFAULT = pathlib.Path(__file__).resolve().parents[3] / "engine/src/semantic/semantic_layer.yml"


def parse_agg(expr: str | None):
    """A harness agg expression -> (agg, measure, derived). A division or two aggregates is a ratio."""
    if not expr:
        return (None, None, False)
    try:
        tree = sqlglot.parse_one(expr, read="postgres")
    except Exception:
        return (None, expr[:40].lower(), False)
    aggs = list(tree.find_all(exp.AggFunc))
    if tree.find(exp.Div) or len(aggs) > 1:
        return ("ratio", expr[:40].lower(), True)
    if aggs:
        af = aggs[0]
        key = af.key.lower()
        if isinstance(af, exp.Count) and af.this is not None and af.this.find(exp.Distinct):
            key = "count_distinct"
        inner = af.this
        if inner is None or isinstance(inner, exp.Star):
            measure = None
        else:
            col = inner.find(exp.Column)
            measure = col.name.lower() if col else inner.sql().lower()[:30]
        return (key, measure, False)
    return (None, expr[:40].lower(), False)


def facts_from_harness_layer(doc: dict) -> list[GroundingFact]:
    metrics = doc.get("metrics") or {}
    items = metrics.items() if isinstance(metrics, dict) else ((m["name"], m) for m in metrics)
    out = []
    for name, m in items:
        agg, measure, derived = parse_agg(m.get("agg"))
        scope = build_scope(" and ".join(m.get("default_filters") or []))
        synonyms = " ".join(m.get("synonyms") or [])
        out.append(GroundingFact(
            id=f"sl:{name}", label=name, layer="semantic", kind="metric",
            entity=m.get("entity"), agg=agg, measure=measure,
            base=(m.get("base") or "").split(".")[-1].lower() or None,
            additive=additivity(agg), scope=scope, derived=derived,
            text=f"{name.replace('_', ' ')}. {m.get('description', '')} {synonyms}".strip()))
    return out


def main() -> None:
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    facts = facts_from_harness_layer(yaml.safe_load(path.read_text()))
    findings = detect_collisions(facts, gate="lexical")
    print(f"{len(facts)} metric facts from {path.name}; {len(findings)} findings")
    for f in findings:
        items = "  ~  ".join(it.label for it in f.items)
        print(f"  [{f.danger:6} {f.type}] {items}")
        print(f"       {f.note}")


if __name__ == "__main__":
    main()
