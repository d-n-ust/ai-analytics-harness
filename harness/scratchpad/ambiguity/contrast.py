#!/usr/bin/env python3
"""No-semantic-layer contrast: run the SAME detector on three configs of the SAME company.

  A governed  = warehouse + docs + semantic layer      (the proficient team)
  B welded    = warehouse + docs + saved BI queries     (the no-SL team; scope welded into WHERE)
  C bare      = warehouse + docs only                   (lower bound: no metric definitions anywhere)

Questions:
  - What does the governed layer ADD to what a static detector can catch? (A vs C)
  - Does a no-SL team's welded-SQL surface recover the same dangerous collisions? (B vs A)
  - How recoverable is welded scope from real saved queries at all? (the Test-3 question)
"""

from __future__ import annotations

import pathlib
import sys
from collections import Counter

from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from preflight import detect  # noqa: E402
from preflight import grounding  # noqa: E402

ENV = HERE.parent / "env_sales"
OUT_MD = HERE.parent / "12_contrast.md"


def main() -> None:
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    wh = grounding.adapt_warehouse(ENV / "warehouse/schema.sql")
    docs = grounding.adapt_docs(ENV / "docs/data_dictionary.md")
    sl = grounding.adapt_semantic(ENV / "semantic/semantic_layer.yml")
    q = grounding.adapt_queries(ENV / "no_sl/queries.sql")

    configs = {
        "A governed (wh+docs+SL)": wh + docs + sl,
        "B welded (wh+docs+queries)": wh + docs + q,
        "C bare (wh+docs)": wh + docs,
    }

    md = ["# No-semantic-layer contrast (same company, three configs)\n"]

    # ── Test-3 recoverability of welded scope from the saved queries ─────────────────────────────
    n = len(q)
    rec = Counter()
    for f in q:
        for k, ok in (f.recovered or {}).items():
            rec[k] += int(ok)
    with_scope = sum(1 for f in q if f.scope)
    md.append("## Welded-scope recoverability from saved SQL (Test 3, in miniature)\n")
    md.append(f"{n} saved queries. sqlglot recovered: agg {rec['agg']}/{n}, base (table) "
              f"{rec['base']}/{n}, WHERE/scope {rec['scope']}/{n}. Queries carrying a non-empty "
              f"welded scope: {with_scope}/{n}.\n")
    md.append("So welded scope is largely RECOVERABLE from real query SQL — it is invisible to a "
              "name-only lint, not to one that parses the query.\n")

    # ── run the detector on each config ──────────────────────────────────────────────────────────
    METRIC_LAYERS = {"semantic", "queries"}
    rows = []
    detail = {}
    for name, facts in configs.items():
        findings = detect.detect_collisions(facts, gate=model)
        detail[name] = findings
        # findings that involve a metric/query definition (the governed/welded surface)
        metric_findings = [f for f in findings
                           if any(it["layer"] in METRIC_LAYERS for it in f["items"])]
        bt = Counter(f["type"] for f in findings)
        n_def = sum(1 for x in facts if x.layer in METRIC_LAYERS and x.kind in ("metric", "query"))
        rows.append({
            "config": name, "def_facts": n_def, "total": len(findings),
            "high": sum(1 for f in findings if f["danger"] == "high"),
            "metric_level": len(metric_findings),
            "scope_trap": bt.get("SCOPE_TRAP", 0), "concept_fork": bt.get("CONCEPT_FORK", 0),
            "def_div": bt.get("DEFINITION_DIVERGENCE", 0), "name_coll": bt.get("NAME_COLLISION", 0),
        })

    md.append("## Findings by config\n```")
    md.append(f"{'config':30} {'defs':>4} {'findings':>8} {'high':>4} {'metric-lvl':>10} "
              f"{'sc_trap':>7} {'c_fork':>6} {'def_div':>7} {'name':>5}")
    for r in rows:
        md.append(f"{r['config']:30} {r['def_facts']:>4} {r['total']:>8} {r['high']:>4} "
                  f"{r['metric_level']:>10} {r['scope_trap']:>7} {r['concept_fork']:>6} "
                  f"{r['def_div']:>7} {r['name_coll']:>5}")
    md.append("```")
    md.append("`defs` = number of metric/query definitions on the surface; `metric-lvl` = findings "
              "that involve at least one such definition.\n")

    # ── the governed-vs-welded high findings, side by side ───────────────────────────────────────
    def high_metric(name):
        return [f for f in detail[name]
                if f["danger"] == "high" and any(it["layer"] in METRIC_LAYERS for it in f["items"])]
    md.append("## High-danger metric-level findings: governed vs welded\n")
    for name in ("A governed (wh+docs+SL)", "B welded (wh+docs+queries)"):
        hs = high_metric(name)
        md.append(f"### {name} — {len(hs)}")
        md.append("```")
        for f in hs:
            items = "  ~  ".join(f"{it['label']}[{it['layer'][:3]}]" for it in f["items"])
            md.append(f"[{f['type']}] {items}")
        md.append("```\n")

    md.append("## Read\n")
    a = next(r for r in rows if r["config"].startswith("A"))
    b = next(r for r in rows if r["config"].startswith("B"))
    c = next(r for r in rows if r["config"].startswith("C"))
    md.append(f"- **The governed layer is where the danger becomes catchable.** Bare warehouse+docs "
              f"(C) surfaces {c['metric_level']} metric-level collisions and {c['scope_trap']} scope "
              f"traps — there are no metric definitions to compare. Add the semantic layer (A) and "
              f"the detector finds {a['metric_level']} metric-level findings incl. {a['scope_trap']} "
              f"scope traps and {a['concept_fork']} concept forks.")
    md.append(f"- **A no-SL team's welded SQL is recoverable, so the collisions are still catchable "
              f"(B) — but the surface is messier.** B has {b['def_facts']} ad-hoc query definitions "
              f"vs A's {a['def_facts']} governed ones, and flags {b['metric_level']} metric-level "
              f"collisions. Welding scope into WHERE does NOT hide it from a SQL-parsing detector; "
              f"it hides it only from a name-only lint, and from an agent that reads the schema but "
              f"not the saved queries.")
    md.append(f"- **The real difference is governance, not detectability.** With the SL there are "
              f"{a['def_facts']} definitions and one is meant to be authoritative; without it there "
              f"are {b['def_facts']} saved queries and none is. The detector can flag the forks in "
              f"both, but only the governed layer gives a place to resolve them.")
    md.append(f"- **But the agent's view is config C, not B.** An agent usually grounds on the "
              f"schema + docs and writes its OWN SQL; it does not necessarily read all "
              f"{b['def_facts']} saved queries. From that seat the metric-level ambiguity is "
              f"invisible ({c['metric_level']} catchable in C), and the agent welds a fresh, "
              f"unreviewed scope every time — exactly the Test-1 finding at environment scale. The "
              f"saved queries are recoverable IF handed to a parser, but they are not a governed "
              f"grounding surface.")
    md.append("- **Two honest caveats on B's lower numbers.** concept_fork is 0 for welded queries "
              "because the adapter does not recover `entity` from SQL (entity is the hardest "
              "primitive to parse — the Test-3 blind spot), so the revenue-family fork is under-"
              "counted, not absent. And def_div is lower partly because ad-hoc query names "
              "(`net_revenue_finance_pack`) do not align with the docs glossary, so fewer cross-layer "
              "name matches fire. Both are detector/adapter limits, not evidence that welding is safe.")

    OUT_MD.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT_MD.name}")


if __name__ == "__main__":
    sys.exit(main())
