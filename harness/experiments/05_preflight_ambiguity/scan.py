#!/usr/bin/env python3
"""Run preflight over each environment in `layers/` — across all three grounding layers — and
tabulate the ambiguities it finds.

Each `layers/<env>/` is a full environment in the layers a primitive grounds in (per the repair
matrix):
    semantic.yml    higher-level metrics + additivity  (the semantic layer)
    warehouse.sql   entity + measure                   (dim/fact tables)
    docs.md         grain + segments                   (documentation)

preflight reads all three and reports confusions WITHIN a layer and ACROSS layers (a term the docs
define two ways that also names a metric and a column). The semantic layer is in the harness's
dict-keyed format, converted here; warehouse and docs use preflight's own adapters.

    python scan.py                 # scan every env, write scan.md
    python scan.py --gate lexical  # force the dependency-free gate (default: embeddings if installed)
"""

from __future__ import annotations

import argparse
import pathlib
from collections import Counter

import sqlglot
import yaml
from sqlglot import exp

from preflight import GroundingFact, adapt_docs, adapt_warehouse, detect_collisions
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


def facts_from_semantic(doc: dict) -> list[GroundingFact]:
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
            grain=m.get("grain"), additive=additivity(agg), scope=scope, derived=derived,
            text=f"{name.replace('_', ' ')}. {m.get('description', '')} {synonyms}".strip()))
    return out


def load_env(env: pathlib.Path) -> list[GroundingFact]:
    """Every grounding fact across the three layers present in an env directory."""
    facts: list[GroundingFact] = []
    sem = env / "semantic.yml"
    if sem.exists():
        facts += facts_from_semantic(yaml.safe_load(sem.read_text()))
    wh = env / "warehouse.sql"
    if wh.exists():
        facts += adapt_warehouse(wh)
    docs = env / "docs.md"
    if docs.exists():
        facts += adapt_docs(docs)
    return facts


def _layers_of(finding) -> str:
    return "+".join(sorted({it.layer[:3] for it in finding.items}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="auto", choices=("auto", "lexical", "embeddings"))
    args = ap.parse_args()

    order = ["small_before", "small_after", "high_before", "high_after"]
    envs = sorted((p for p in LAYERS.iterdir() if p.is_dir()),
                  key=lambda p: order.index(p.name) if p.name in order else 99)

    rows = ["# Preflight ambiguity counts per environment (all three grounding layers)\n",
            f"Gate: **{args.gate}**. Each env is scanned across semantic + warehouse + docs; the "
            "`layers` column of a finding shows which grounding layers it spans (sem/war/doc).\n",
            "| environment | facts | high | medium | low | total |",
            "|---|---|---|---|---|---|"]
    detail = ["\n## Findings\n"]
    for env in envs:
        facts = load_env(env)
        findings = detect_collisions(facts, gate=args.gate)
        by = Counter(f.danger for f in findings)
        rows.append(f"| {env.name} | {len(facts)} | {by['high']} | {by['medium']} | {by['low']} "
                    f"| {len(findings)} |")
        detail.append(f"\n### {env.name} ({len(findings)} findings)\n```")
        for f in findings:
            detail.append(f"[{f.danger:6} {f.type:22} {_layers_of(f):11}] "
                          + "  ~  ".join(it.label for it in f.items))
        detail.append("```")

    out = "\n".join(rows) + "\n" + "\n".join(detail) + "\n"
    (HERE / "scan.md").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
