#!/usr/bin/env python3
"""The combined pipeline, prototyped on 5 isolated examples.

Design decisions from Tests 1-2 and the embedding checks, assembled:

  GATE   — embedding similarity of the NAMES (replaces token overlap). Fixes the plural/synonym
           misses; casts a wide, high-recall net.
  MEANING— same measure = agreement on the meaning facets BOTH metrics declare (entity/agg/base).
           `unit` is dropped (proven redundant, and never declared in the wild).
  SCOPE  — among same-measure candidates, classify the scope difference by SUBSUMPTION, not by name:
             identical scope        -> alias  (vague; answer either)
             one scope subsumes other-> SCOPE TRAP (a bare question is silently scoped) -> clarify
             incomparable scopes    -> sibling (a question must name one; not a silent default)
  DIVERGENCE is binary — if the scopes differ at all, the numbers can differ; magnitude is not part
           of detection (it only prices the consequence later).

Danger is the SCOPE TRAP: same measure, one scope a subset of the other, names confusable. That is
value_moments vs real_value_moments. The pipeline is run on 5 tiny isolated catalogs below.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
OUT_MD = HERE.parent / "08_pipeline.md"
GATE = 0.40                    # embedding cosine floor for "confusable candidate" (from the probe)
MEANING = ("entity", "agg", "base")


def _considers():
    spec = importlib.util.spec_from_file_location("_amb", REPO / "engine/src/semantic/ambiguity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.considers


considers = _considers()


def assess(a: str, ma: dict, b: str, mb: dict, cos: float) -> dict:
    """Classify one candidate pair. Returns the gate results, the class, and the action."""
    token_gate = considers(a, b)          # the OLD gate, for contrast
    embed_gate = cos >= GATE
    out = {"a": a, "b": b, "cos": cos, "token_gate": token_gate, "embed_gate": embed_gate}

    if not embed_gate:
        out.update(danger="ignore", action="—",
                   reason="names not similar enough to be confusable")
        return out

    declared = [f for f in MEANING if ma.get(f) is not None and mb.get(f) is not None]
    if not all(ma.get(f) == mb.get(f) for f in declared):
        diff = [f for f in declared if ma.get(f) != mb.get(f)]
        out.update(danger="safe", action="answer",
                   reason=f"different measure (differs in {', '.join(diff)}) -> numbers land far "
                          f"apart, a swap is loud")
        return out

    sa, sb = set(ma.get("filters") or []), set(mb.get("filters") or [])
    if sa == sb:
        out.update(danger="vague", action="answer either",
                   reason="identical definition under two names -> alias; same number always")
        return out
    if sa <= sb or sb <= sa:
        wider, narrower = (a, b) if sa <= sb else (b, a)
        out.update(danger="SCOPE TRAP (high)", action="clarify",
                   reason=f"same measure; '{narrower}' is '{wider}' plus a filter -> a bare question "
                          f"is silently scoped, numbers differ, swap is invisible")
        return out
    out.update(danger="sibling (low)", action="note",
               reason="same measure, incomparable scopes -> a question must name one; not a silent "
                      "default swap")
    return out


# ── 5 isolated examples, each a 2-metric catalog exercising one behaviour ─────────────────────────
EXAMPLES = [
    ("1. Bare vs scoped — the core trap", "orders", "completed_orders", {
        "orders":           {"entity": "order", "agg": "count(*)", "base": "orders", "filters": []},
        "completed_orders": {"entity": "order", "agg": "count(*)", "base": "orders",
                             "filters": ["status = completed"]},
    }),
    ("2. Similar name, different measure", "active_users", "active_subscriptions", {
        "active_users":         {"entity": "user", "agg": "count(distinct user_id)",
                                 "base": "events", "filters": ["active"]},
        "active_subscriptions": {"entity": "subscription", "agg": "count(*)",
                                 "base": "subscriptions", "filters": ["is_active"]},
    }),
    ("3. Sibling vs sibling", "food_orders", "drink_orders", {
        "food_orders":  {"entity": "order", "agg": "count(*)", "base": "orders",
                         "filters": ["type = food"]},
        "drink_orders": {"entity": "order", "agg": "count(*)", "base": "orders",
                         "filters": ["type = drink"]},
    }),
    ("4. Alias — identical definition, two names", "gross_revenue", "total_revenue", {
        "gross_revenue": {"entity": "revenue", "agg": "sum(amount)", "base": "payments", "filters": []},
        "total_revenue": {"entity": "revenue", "agg": "sum(amount)", "base": "payments", "filters": []},
    }),
    ("5. Recall win — synonym, no shared token, subsumption", "revenue", "net_sales", {
        "revenue":   {"entity": "revenue", "agg": "sum(amount)", "base": "payments", "filters": []},
        "net_sales": {"entity": "revenue", "agg": "sum(amount)", "base": "payments",
                      "filters": ["not refunded"]},
    }),
]


def main() -> None:
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    # embed every name once
    names = sorted({n for *_, cat in EXAMPLES for n in cat})
    vecs = model.encode([n.replace("_", " ") for n in names], normalize_embeddings=True)
    emb = {n: v for n, v in zip(names, vecs, strict=False)}
    def cos(a, b):
        return float(np.dot(emb[a], emb[b]))

    md = ["# The combined pipeline on 5 isolated examples\n"]
    md.append(f"GATE = embedding cosine ≥ {GATE} (all-MiniLM-L6-v2, name-only). MEANING = "
              f"agreement on declared entity/agg/base (unit dropped). SCOPE = subsumption of the "
              f"declared filters. Danger = SCOPE TRAP (same measure, one scope inside the other, "
              f"names confusable).\n")

    results = []
    for title, a, b, cat in EXAMPLES:
        r = assess(a, cat[a], b, cat[b], cos(a, b))
        results.append((title, r))
        md.append(f"## {title}\n")
        md.append(f"`{a}` ~ `{b}`  — embedding cos **{r['cos']:.3f}**  "
                  f"(embed gate {'PASS' if r['embed_gate'] else 'fail'}, "
                  f"token gate {'pass' if r['token_gate'] else 'MISS'})\n")
        md.append(f"- **class:** {r['danger']}")
        md.append(f"- **action:** {r['action']}")
        md.append(f"- **why:** {r['reason']}\n")

    # ── the contrast table ───────────────────────────────────────────────────────────────────────
    md.append("## Summary\n")
    md.append("```")
    md.append(f"{'example':44} {'cos':>5} {'tokgate':>7} {'class':18} {'action':13}")
    for title, r in results:
        md.append(f"{title[:44]:44} {r['cos']:.3f} {('pass' if r['token_gate'] else 'MISS'):>7} "
                  f"{r['danger']:18} {r['action']:13}")
    md.append("```\n")

    # what each example proves
    md.append("What the 5 show, together:\n")
    md.append("- **#1** the core trap is flagged: same measure, bare vs scoped -> **clarify**.")
    md.append("- **#2** a similar NAME with a different MEASURE is not flagged -> **answer**. "
              "Embeddings alone would warn here; the structural stage correctly stands it down.")
    md.append("- **#3** two scoped siblings are not a silent-default trap -> **note**, not clarify. "
              "The subsumption test kills the sibling noise that over-fired in Test 2.")
    md.append("- **#4** an identical definition under two names is an **alias** -> answer either; "
              "never asked about.")
    md.append("- **#5** a dangerous pair whose names share **no token** (`revenue`/`net_sales`) is "
              "caught by the embedding gate (cos {:.2f}) though the old token gate MISSES it. This is "
              "the recall win, and it is a real scope trap -> **clarify**.".format(results[4][1]["cos"]))
    md.append("\nDivergence stays binary throughout: #1, #3, #5 have differing definitions so the "
              "numbers CAN differ (flag on that fact, not on a percentage); #4 is identical so it "
              "never can. Magnitude is left for pricing the consequence, not for detection.")

    OUT_MD.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT_MD.relative_to(REPO)}")


if __name__ == "__main__":
    sys.exit(main())
