#!/usr/bin/env python3
"""Run preflight over each semantic layer in `layers/` and tabulate the ambiguities it finds.

This is the "dose" measurement of the experiment: how many confusions preflight flags in each of the
four environments (small/high x before/after). It converts the harness's dict-keyed layer format into
preflight GroundingFacts (parsing the SQL `agg` expression; population from `default_filters`) and runs
the detector.

    python scan.py                 # scan all layers/*.yml, write scan.md
    python scan.py --gate lexical  # force the dependency-free gate (default: embeddings if installed)

Needs preflight installed (`pip install "preflight[embeddings]"`). The embedding gate is the validated
path and the one the experiment reports; the lexical fallback misses synonym-based confusions.
"""

from __future__ import annotations

import argparse
import pathlib
from collections import Counter

import sqlglot
import yaml
from sqlglot import exp

from preflight import GroundingFact, detect_collisions
from preflight.adapters import additivity
from preflight.scope import build_scope

HERE = pathlib.Path(__file__).resolve().parent
LAYERS = HERE / "layers"


def _parse_agg(expr: str | None):
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


def facts_from_layer(doc: dict) -> list[GroundingFact]:
    metrics = doc.get("metrics") or {}
    items = metrics.items() if isinstance(metrics, dict) else ((m["name"], m) for m in metrics)
    out = []
    for name, m in items:
        agg, measure, derived = _parse_agg(m.get("agg"))
        scope = build_scope(" and ".join(m.get("default_filters") or []))
        synonyms = " ".join(m.get("synonyms") or [])
        out.append(GroundingFact(
            id=f"sl:{name}", label=name, layer="semantic", kind="metric",
            entity=m.get("entity"), agg=agg, measure=measure,
            base=(m.get("base") or "").split(".")[-1].lower() or None,
            additive=additivity(agg), scope=scope, derived=derived,
            text=f"{name.replace('_', ' ')}. {m.get('description', '')} {synonyms}".strip()))
    return out


def scan_layer(path: pathlib.Path, gate: str):
    facts = facts_from_layer(yaml.safe_load(path.read_text()))
    findings = detect_collisions(facts, gate=gate)
    by = Counter(f.danger for f in findings)
    return facts, findings, by


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="auto", choices=("auto", "lexical", "embeddings"))
    args = ap.parse_args()

    order = ["small_before", "small_after", "high_before", "high_after"]
    layers = sorted(LAYERS.glob("*.yml"), key=lambda p: order.index(p.stem) if p.stem in order else 99)

    rows = ["# Preflight ambiguity counts per environment\n",
            f"Gate: **{args.gate}**. Findings are confusable metric pairs/clusters preflight flags.\n",
            "| environment | metrics | high | medium | low | total |",
            "|---|---|---|---|---|---|"]
    detail = ["\n## Findings\n"]
    for path in layers:
        facts, findings, by = scan_layer(path, args.gate)
        rows.append(f"| {path.stem} | {len(facts)} | {by['high']} | {by['medium']} | {by['low']} "
                    f"| {len(findings)} |")
        detail.append(f"\n### {path.stem} ({len(findings)} findings)\n```")
        for f in findings:
            detail.append(f"[{f.danger:6} {f.type}] " + "  ~  ".join(it.label for it in f.items))
        detail.append("```")

    out = "\n".join(rows) + "\n" + "\n".join(detail) + "\n"
    (HERE / "scan.md").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
