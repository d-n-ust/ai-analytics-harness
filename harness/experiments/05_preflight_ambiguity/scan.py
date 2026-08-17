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
import sys
from collections import Counter, defaultdict

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


_RANK = {"high": 0, "medium": 1, "low": 2}
# The three grounding layers a primitive can live in (the repair-matrix mapping).
_LAYER = {"doc": ("DOCUMENTATION", "grain · segments"),
          "war": ("WAREHOUSE", "entity · measure"),
          "sem": ("SEMANTIC LAYER", "additive · higher-level metrics")}
_C = {"high": "\033[38;5;167m", "medium": "\033[38;5;179m", "low": "\033[38;5;101m",
      "b": "\033[1m", "dim": "\033[2m", "accent": "\033[38;5;72m", "reset": "\033[0m"}


def _group(findings):
    """findings -> {layer_key: [findings]}; 'cross' when a finding spans more than one layer."""
    groups = defaultdict(list)
    for f in findings:
        spans = sorted({it.layer[:3] for it in f.items})
        groups["cross" if len(spans) > 1 else spans[0]].append(f)
    for v in groups.values():
        v.sort(key=lambda f: (_RANK[f.danger], f.type))
    return groups


def _line(f, on, max_items=6):
    c = (lambda s, k: f"{_C[k]}{s}{_C['reset']}") if on else (lambda s, k: s)
    labels = [it.label for it in f.items]
    more = c(f"  +{len(labels) - max_items}", "dim") if len(labels) > max_items else ""
    return (f"    {c('●', f.danger)} {c(f.danger[0].upper(), f.danger)} "
            f"{c(f'{f.type:22}', 'dim')} " + "  ~  ".join(labels[:max_items]) + more)


def _report(results, gate, on):
    c = (lambda s, k: f"{_C[k]}{s}{_C['reset']}") if on else (lambda s, k: s)
    out = ["", "  " + c("PREFLIGHT AMBIGUITY MAP", "b") + c(f"          gate: {gate}", "dim"),
           "  " + c("─" * 60, "dim")]
    for name, facts, findings in results:
        by = Counter(f.danger for f in findings)
        n = len(findings)
        out.append(f"  {name:15} {c(f'{n:>2}', 'b')} confusion{' ' if n == 1 else 's'}   "
                   + c(f"({len(facts)} facts · "
                       f"{by['high']} high {by['medium']} med {by['low']} low)", "dim"))
    out.append("  " + c("●", "high") + " high   " + c("●", "medium") + " medium   "
               + c("●", "low") + " low")

    for name, _facts, findings in results:
        if not findings:
            continue
        out.append("\n" + c("════ ", "accent") + c(name, "b")
                   + c(" " + "═" * (54 - len(name)), "accent"))
        groups = _group(findings)
        if groups["cross"]:
            out.append("\n  " + c("CROSS-LAYER", "accent")
                       + c("  · a term grounded two ways, in two places", "dim"))
            out += [_line(f, on) for f in groups["cross"]]
        for lk in ("doc", "war", "sem"):
            if groups[lk]:
                title, grounds = _LAYER[lk]
                out.append("\n  " + c(title, "b") + c(f"  · grounds {grounds}", "dim"))
                out += [_line(f, on) for f in groups[lk]]
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="auto", choices=("auto", "lexical", "embeddings"))
    ap.add_argument("--no-color", action="store_true", help="plain output even to a terminal")
    args = ap.parse_args()

    order = ["small_before", "small_after", "high_before", "high_after"]
    envs = sorted((p for p in LAYERS.iterdir() if p.is_dir()),
                  key=lambda p: order.index(p.name) if p.name in order else 99)
    results = [(env.name, facts := load_env(env), detect_collisions(facts, gate=args.gate))
               for env in envs]

    # colour only when writing to a real terminal
    print(_report(results, args.gate, on=sys.stdout.isatty() and not args.no_color))
    # plain record beside the layers
    (HERE / "scan.md").write_text("```\n" + _report(results, args.gate, on=False) + "\n```\n")


if __name__ == "__main__":
    main()
