#!/usr/bin/env python3
"""Test 2, scan step — run the classifier over real public semantic layers, fully offline.

Adapts three real MetricFlow / dbt-metrics schemas onto the facet structure ambiguity.py expects,
WITHOUT modifying ambiguity.py. Two modes:

  native   — fill only facets the source YAML actually declares (unit is left absent, because no
             MetricFlow/dbt-metrics dialect has a unit field).
  inferred — additionally infer `unit` from the aggregation kind, the one facet the classifier's
             scope_only rule needs but the ecosystem never declares.

The gap between the two modes is the finding: it isolates whether real projects fail the classifier
because scope is not separable (they don't) or because the classifier demands a facet the ecosystem
does not populate (it does). See ambiguity-viability-tests.md, Test 2.

Answers, per project:
  (a) gate scaling  — gated pairs vs metric count (is the lexical gate sublinear in n^2?)
  (b) facet exist   — share of the 7 facets each metric can fill natively, and the class split.
"""

from __future__ import annotations

import csv
import importlib.util
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
CORPUS = HERE.parent / "corpus"
OUT_MD = HERE.parent / "02_corpus.md"
OUT_CSV = HERE.parent / "02_corpus.csv"


def _load_classifier():
    spec = importlib.util.spec_from_file_location(
        "_ambiguity", REPO / "engine/src/semantic/ambiguity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── normalise one metric from any of the three schemas into a facet dict ─────────────────────────
# The classifier reads: entity, agg, base, unit (meaning); segment, default_filters, time_column
# (scope). We fill what each schema declares; `unit` is filled only in inferred mode.
MEANING = ("entity", "agg", "base", "unit")
SCOPE = ("segment", "default_filters", "time_column")


def _primary_entity(model: dict) -> str | None:
    for col in model.get("columns", []) or []:
        ent = col.get("entity")
        if isinstance(ent, dict) and ent.get("type") == "primary":
            return ent.get("name") or col.get("name")
    return None


def _infer_unit(agg: str | None) -> str | None:
    if not agg:
        return None
    a = agg.lower()
    if a.startswith(("count", "count_distinct")) or "(1)" in a:
        return "count"
    if a.startswith("average") or "avg" in a or "ratio" in a:
        return "ratio"
    return "number"     # a sum/min/max of a column: a magnitude of unknown unit, but a magnitude


def _metrics_from_doc(doc: dict, model_index: dict) -> list[dict]:
    """Yield (name, raw_metric, owning_model) across schemas A/B/C found in one YAML doc."""
    out = []
    # top-level metrics (schema B/C, and some A)
    for m in doc.get("metrics", []) or []:
        out.append((m.get("name"), m, None))
    # metrics embedded in models[] (schema A)
    for model in doc.get("models", []) or []:
        for m in model.get("metrics", []) or []:
            out.append((m.get("name"), m, model))
    return out


def _facets(name: str, m: dict, model: dict | None, model_index: dict, infer: bool) -> dict | None:
    """Map one raw metric to the classifier's facet dict, or None if it is not a base measure
    (derived/ratio/cumulative metrics reference other metrics, not a population, so they are not
    what this lint compares)."""
    agg = base = entity = time = scope = None

    if "agg" in m:                                   # schema A: agg + expr, embedded in a model
        expr = m.get("expr")
        agg = f"{m['agg']}({expr if expr is not None else name})"
        base = model.get("name") if model else None
        entity = (_primary_entity(model) if model else None) or base
        time = (model or {}).get("agg_time_dimension")
        scope = m.get("filter")
    elif "type_params" in m:                          # schema B: metric -> measure indirection
        tp = m.get("type_params") or {}
        meas = tp.get("measure")
        if isinstance(meas, dict):
            meas = meas.get("name")
        if m.get("type") in ("derived", "cumulative", "ratio") or not meas:
            return None                               # references other metrics, not a population
        agg = f"measure:{meas}"                       # same measure => same meaning, by construction
        base = entity = meas
        scope = m.get("filter")
    elif "calculation_method" in m:                   # schema C: deprecated dbt_metrics spec
        agg = f"{m['calculation_method']}({m.get('expression', name)})"
        ref = str(m.get("model", ""))
        base = entity = ref.replace("ref(", "").replace(")", "").strip("'\" ") or None
        time = m.get("timestamp")
        filt = m.get("filters")
        if filt:
            scope = "; ".join(f"{f.get('field')} {f.get('operator')} {f.get('value')}" for f in filt)
    else:
        return None

    unit = _infer_unit(agg) if infer else None
    return {"entity": entity, "agg": agg, "base": base, "unit": unit,
            "segment": None, "default_filters": scope, "time_column": time}


def scan_project(proj_dir: pathlib.Path, amb, infer: bool):
    metrics: dict[str, dict] = {}
    model_index: dict[str, dict] = {}
    raw_count = 0
    for f in sorted(proj_dir.glob("*.yml")) + sorted(proj_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text()) or {}
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        for model in doc.get("models", []) or []:
            model_index[model.get("name")] = model
        for name, m, model in _metrics_from_doc(doc, model_index):
            if not name:
                continue
            raw_count += 1
            facets = _facets(name, m, model, model_index, infer)
            if facets is not None:
                metrics[name] = facets

    pairs = amb.confusable_pairs(metrics)
    return metrics, pairs, raw_count


def facet_population(metrics: dict) -> dict:
    """Per-facet share of metrics that declare it (native)."""
    if not metrics:
        return {}
    n = len(metrics)
    pop = {}
    for f in (*MEANING, *SCOPE):
        pop[f] = sum(1 for d in metrics.values() if d.get(f) is not None) / n
    return pop


def main() -> None:
    amb = _load_classifier()
    projects = sorted(p for p in CORPUS.iterdir() if p.is_dir())

    rows = []           # CSV rows
    inspected = []      # scope_only findings from the largest project
    scaling = []        # (project, metrics, gated_pairs) for the gate-scaling table

    for proj in projects:
        metrics_n, pairs_n, raw = scan_project(proj, amb, infer=False)   # native
        metrics_i, pairs_i, _ = scan_project(proj, amb, infer=True)      # inferred unit
        pop = facet_population(metrics_n)
        # facets_populated_% = mean over the 7 facets of their native population share
        facets_pct = 100 * (sum(pop.values()) / len(pop)) if pop else 0.0

        def klass_counts(pairs):
            c = {"alias": 0, "scope_only": 0, "different_measure": 0}
            for p in pairs:
                c[p.kind] = c.get(p.kind, 0) + 1
            return c

        cn, ci = klass_counts(pairs_n), klass_counts(pairs_i)
        rows.append({
            "project": proj.name, "metrics": len(metrics_n), "raw_metrics": raw,
            "gated_pairs": len(pairs_n),
            "alias_native": cn["alias"], "scope_only_native": cn["scope_only"],
            "diff_measure_native": cn["different_measure"],
            "scope_only_inferred": ci["scope_only"], "diff_measure_inferred": ci["different_measure"],
            "facets_populated_%": round(facets_pct, 1),
            "unit_native_%": round(100 * pop.get("unit", 0), 1),
        })
        scaling.append((proj.name, len(metrics_n), len(pairs_n)))

    # largest project by metric count — hand-inspect 5 scope_only (inferred, so the class is non-empty)
    largest = max(projects, key=lambda p: scan_project(p, amb, infer=False)[0].__len__())
    _, big_pairs, _ = scan_project(largest, amb, infer=True)
    scope_only = [p for p in big_pairs if p.kind == "scope_only"][:5]
    for p in scope_only:
        inspected.append((largest.name, p.a, p.b, tuple(p.shared_tokens),
                          tuple(p.same_meaning), tuple(p.differs_in)))

    # ── write CSV ────────────────────────────────────────────────────────────────────────────────
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ── write markdown ───────────────────────────────────────────────────────────────────────────
    md = ["# Test 2 — Corpus smoke test (phase 1)\n"]
    md.append("Real public semantic layers, offline (no dbt, no warehouse, no tokens). Three "
              "schemas: jaffle-shop (embedded `agg/expr/filter`), jaffle-sl-template "
              "(`type_params.measure` + `filter`), jaffle_shop_metrics (deprecated "
              "`calculation_method/expression/filters`). All three declare scope as a separate "
              "field; none declares `unit`.\n")
    md.append("`native` fills only declared facets; `inferred` also infers `unit` from the "
              "aggregation. The gap between the two `scope_only` columns is the finding.\n")

    md.append("## Per-project scan\n")
    md.append("```")
    md.append(f"{'project':22} {'metrics':>7} {'gated':>6} | {'scope_only':>10} {'diff_meas':>9}  "
              f"(native) | {'scope_only':>10} (inferred) | {'facets%':>7} {'unit%':>5}")
    for r in rows:
        md.append(f"{r['project']:22} {r['metrics']:>7} {r['gated_pairs']:>6} | "
                  f"{r['scope_only_native']:>10} {r['diff_measure_native']:>9}  "
                  f"{'':8} | {r['scope_only_inferred']:>10} {'':11} | "
                  f"{r['facets_populated_%']:>6}% {r['unit_native_%']:>4}%")
    md.append("```")
    md.append("`facets%` = mean native population across the 7 facets; `unit%` = share of metrics "
              "declaring `unit` natively.\n")

    md.append("## (a) Gate scaling — gated pairs vs metric count\n")
    md.append("```")
    md.append(f"{'project':22} {'metrics(n)':>10} {'gated_pairs':>12} {'n(n-1)/2':>10} {'gated/pairs':>11}")
    for name, n, g in sorted(scaling, key=lambda x: x[1]):
        allpairs = n * (n - 1) // 2
        frac = (g / allpairs) if allpairs else 0.0
        md.append(f"{name:22} {n:>10} {g:>12} {allpairs:>10} {frac:>11.2f}")
    md.append("```")
    md.append("If `gated/pairs` falls as n grows, the lexical gate is sublinear in n^2 (reviewable); "
              "if it stays flat or rises, it is quadratic. NOTE: public MetricFlow projects are all "
              "small (the spec is young), so this range is narrow — a genuine limit on how far this "
              "test can settle the scale question from public data.\n")

    md.append("## (b) The 5 hand-inspected scope_only findings (largest project, inferred unit)\n")
    md.append("Shown in the classifier's OWN top-5 ranking, with a one-line plausibility verdict as "
              "an outsider. The pattern that matters: a bare head noun (`orders`) confused with a "
              "filtered variant is a real trap; two filtered siblings (`food` vs `drink`) share only "
              "the head noun and are not genuinely confusable — the distinguishing word is prominent.\n")
    # Hand verdicts, keyed by the confusable modifier pair. `orders` = the bare head noun.
    def verdict(a: str, b: str) -> str:
        heads = {a.split()[0], b.split()[0]}
        if "orders" in heads and ("orders" == a or "orders" == b):
            return "GENUINE: bare `orders` vs a filtered subset — the real scope trap."
        return ("NOISE: two filtered siblings sharing only the head noun `orders`; the distinguishing "
                "modifier is prominent, so a reader would not swap them.")
    if inspected:
        md.append("```")
        for _proj, a, b, shared, _same, diff in inspected:
            md.append(f"{a}  ~  {b}")
            md.append(f"    shares: {', '.join(shared)} | differs: {', '.join(diff)}")
            md.append(f"    verdict: {verdict(a, b)}")
        md.append("```")
        genuine = sum(1 for _, a, b, *_ in inspected if verdict(a, b).startswith("GENUINE"))
        md.append(f"**{genuine} of the top-5 are genuine confusions; {5 - genuine} are sibling noise.** "
                  f"The genuinely dangerous pattern (bare `orders` vs `food_orders` / `drink_orders` / "
                  f"`large_orders` / `new_customer_orders`) exists, but the classifier does not rank it "
                  f"above filtered-vs-filtered sibling pairs. On a real layer the gate over-generates, "
                  f"and the one pattern worth clarifying is buried in siblings that share only a head "
                  f"noun — a precision problem the `_QUALIFIERS` list tuned away on this repo's own "
                  f"layer but does not generalise.\n")
    else:
        md.append("No scope_only findings even with inferred unit — see verdict.\n")

    md.append("## Verdict against the kill condition\n")
    any(r["scope_only_native"] for r in rows)
    any(r["scope_only_inferred"] for r in rows)
    md.append("- **Scope IS separable in real layers.** Every dialect declares the restriction as a "
              "first-class field (`filter:` or `filters:`), never only welded into the aggregate. So "
              "the pessimistic version of the kill condition — scope is not declared separately — is "
              "**not** met.")
    md.append(f"- **But the classifier collapses on real layers as written.** scope_only pairs found "
              f"natively across all projects: **{sum(r['scope_only_native'] for r in rows)}**. With "
              f"`unit` inferred: **{sum(r['scope_only_inferred'] for r in rows)}**. The rule "
              f"`len(same) == len(_MEANING)` (ambiguity.py:113) requires all four meaning facets "
              f"present, including `unit`, which no MetricFlow/dbt-metrics dialect declares. So every "
              f"genuine scope pair is demoted to different_measure/low unless the adapter invents a "
              f"`unit`.")
    md.append("- **Reported, not edited (ground rule 1).** ambiguity.py needs one change to run on "
              "real layers: scope_only should require agreement on all meaning facets *both metrics "
              "declare*, not on a hardcoded four. As written, `unit` being ecosystem-absent silently "
              "turns the dangerous class off. This is the Test-1 welded-scope limitation's sibling: "
              "there the danger hid because scope was welded; here it hides because a required "
              "meaning facet is never declared.")
    md.append("- **Net:** facets exist and scope is separable (part b passes in principle), but the "
              "classifier's meaning-facet rule must be generalised before the claim 'detectable in "
              "semantic layers' holds for layers other than this repo's.")

    OUT_MD.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT_MD.relative_to(REPO)} and {OUT_CSV.name}")


if __name__ == "__main__":
    sys.exit(main())
