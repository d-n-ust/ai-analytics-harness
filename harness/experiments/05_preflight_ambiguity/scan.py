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
import contextlib
import os
import pathlib
import sys
import time
from collections import Counter, defaultdict

# Quiet the ML stack so only the tool's own progress narration reaches the terminal.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sqlglot
import yaml
from sqlglot import exp

from preflight import GroundingFact, adapt_docs, adapt_warehouse, detect_collisions
from preflight.adapters import additivity
from preflight.scope import build_scope

HERE = pathlib.Path(__file__).resolve().parent
LAYERS = HERE / "layers"


@contextlib.contextmanager
def _quiet():
    """Swallow a library's own stdout/stderr chatter (HF warnings, tqdm bars) for the
    duration of a call. Real failures still surface — they raise, they do not just print."""
    with open(os.devnull, "w") as null, \
            contextlib.redirect_stderr(null), contextlib.redirect_stdout(null):
        yield


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


_RANK = {"high": 0, "medium": 1, "low": 2}
# The three grounding layers a primitive can live in (the repair-matrix mapping).
_LAYER = {"doc": ("DOCUMENTATION", "grain · segments"),
          "war": ("WAREHOUSE", "entity · measure"),
          "sem": ("SEMANTIC LAYER", "additive · higher-level metrics")}
_C = {"high": "\033[38;5;167m", "medium": "\033[38;5;179m", "low": "\033[38;5;101m",
      "b": "\033[1m", "dim": "\033[2m", "accent": "\033[38;5;72m", "reset": "\033[0m"}


def _mk_color(on):
    return (lambda s, k: f"{_C[k]}{s}{_C['reset']}") if on else (lambda s, k: s)


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
    c = _mk_color(on)
    labels = [it.label for it in f.items]
    more = c(f"  +{len(labels) - max_items}", "dim") if len(labels) > max_items else ""
    return (f"    {c('●', f.danger)} {c(f.danger[0].upper(), f.danger)} "
            f"{c(f'{f.type:22}', 'dim')} " + "  ~  ".join(labels[:max_items]) + more)


def _report(results, gate, on):
    c = _mk_color(on)
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


def _load_with_progress(env, step, c):
    """Load the three grounding layers, narrating each with its fact count."""
    facts = []
    sem = env / "semantic.yml"
    if sem.exists():
        sf = facts_from_semantic(yaml.safe_load(sem.read_text()))
        facts += sf
        step(f"      {c('·', 'dim')} semantic.yml   {c(f'{len(sf):>2}', 'b')} metrics")
    wh = env / "warehouse.sql"
    if wh.exists():
        wf = adapt_warehouse(wh)
        facts += wf
        tabs = sum(1 for f in wf if f.kind == "table")
        step(f"      {c('·', 'dim')} warehouse.sql  {c(f'{tabs:>2}', 'b')} tables · {len(wf) - tabs} columns")
    docs = env / "docs.md"
    if docs.exists():
        df = adapt_docs(docs)
        facts += df
        step(f"      {c('·', 'dim')} docs.md        {c(f'{len(df):>2}', 'b')} terms")
    return facts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="auto", choices=("auto", "lexical", "embeddings"))
    ap.add_argument("--no-color", action="store_true", help="plain output even to a terminal")
    args = ap.parse_args()

    ce = _mk_color(sys.stderr.isatty() and not args.no_color)

    def step(msg=""):
        print(msg, file=sys.stderr, flush=True)

    t0 = time.time()
    step()
    step("  " + ce("preflight", "accent") + ce("  ambiguity scan across the grounding stack", "dim"))
    step("  " + ce("─" * 52, "dim"))

    # the embedding model loads ONCE (it is the slow step) and is reused for every environment
    model = None
    if args.gate == "embeddings":
        step("  " + ce("▸", "accent") + " loading embedding model "
             + ce("(sentence-transformers · MiniLM)", "dim") + " …")
        tm = time.time()
        with _quiet():
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        step("      " + ce("✓", "low") + " ready " + ce(f"({time.time() - tm:.1f}s)", "dim"))

    order = ["small_before", "small_after", "high_before", "high_after"]
    envs = sorted((p for p in LAYERS.iterdir() if p.is_dir()),
                  key=lambda p: order.index(p.name) if p.name in order else 99)

    results = []
    for env in envs:
        step("\n  " + ce("▸", "accent") + " " + ce(env.name, "b"))
        facts = _load_with_progress(env, step, ce)
        step(f"      {ce('·', 'dim')} scanning {len(facts)} facts for confusions …")
        findings = detect_collisions(facts, gate=model if model is not None else args.gate)
        by = Counter(f.danger for f in findings)
        step(f"      {ce('✓', 'low')} {ce(str(len(findings)), 'b')} found  "
             + ce(f"{by['high']} high · {by['medium']} med · {by['low']} low", "dim"))
        results.append((env.name, facts, findings))

    total = sum(len(r[2]) for r in results)
    step("\n  " + ce("─" * 52, "dim"))
    step("  " + ce("done", "accent")
         + ce(f"  {time.time() - t0:.1f}s · {total} confusions · {len(results)} environments", "dim"))
    step()

    print(_report(results, args.gate, on=sys.stdout.isatty() and not args.no_color))
    (HERE / "scan.md").write_text("```\n" + _report(results, args.gate, on=False) + "\n```\n")


if __name__ == "__main__":
    main()
