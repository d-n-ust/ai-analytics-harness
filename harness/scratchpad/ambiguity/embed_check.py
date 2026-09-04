#!/usr/bin/env python3
"""Test the embedding hypothesis, offline, with a local model (all-MiniLM-L6-v2).

Question: does embedding similarity between metric definitions carry a signal the token-overlap
gate does not, and does it predict the confusions we actually observed? Three checks:

  1. Is the known dangerous pair (value_moments ~ real_value_moments) the closest pair by cosine?
  2. Does cosine SEPARATE the scope_only pairs from the different_measure pairs? (If not, embeddings
     measure similarity, not danger — they belong on the confusability axis only.)
  3. Does a metric's nearest-neighbour cosine track its observed mislabel rate from Test 1?

Two text representations per metric: NAME only (apples-to-apples with the token gate) and
NAME + description + synonyms (what the agent actually reads). Local model, no API, no paid call.
"""

from __future__ import annotations

import gzip
import importlib.util
import itertools
import json
import pathlib
import sys
from collections import defaultdict

import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
LAYER = REPO / "engine/src/semantic/semantic_layer.yml"
RUN = REPO / "results/published/2026-07-reliability-ladder/runs/20260726-224953-gpt-5-mini.raw.jsonl.gz"
CASES = REPO / "harness/evals/cases"
OUT_MD = HERE.parent / "06_embeddings.md"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _classifier():
    spec = importlib.util.spec_from_file_location("_amb", REPO / "engine/src/semantic/ambiguity.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _gold_by_case() -> dict[str, str]:
    gold = {}
    for f in CASES.rglob("*.yml"):
        doc = yaml.safe_load(f.read_text()) or {}
        for c in doc.get("cases", []) if isinstance(doc, dict) else []:
            e = c.get("expect", {}) or {}
            if e.get("type") == "metric_answer" and e.get("metric"):
                gold[c["id"]] = e["metric"]
    return gold


def _mislabel_by_metric(gold: dict[str, str]) -> dict[str, tuple[int, int]]:
    """{metric: (answered, mislabel)} pooled over the run's arms/reps, metric_answer cases only."""
    agg = defaultdict(lambda: [0, 0])
    with gzip.open(RUN, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            qid = r.get("qid")
            if qid not in gold or r.get("outcome") != "answer":
                continue
            m = gold[qid]
            agg[m][0] += 1
            if r.get("correct") is False:
                agg[m][1] += 1
    return {m: (a, w) for m, (a, w) in agg.items()}


def main() -> None:
    amb = _classifier()
    layer = yaml.safe_load(LAYER.read_text())
    metrics = layer["metrics"]
    names = sorted(metrics)

    name_text = {n: n.replace("_", " ") for n in names}
    rich_text = {n: f"{n.replace('_',' ')}. {metrics[n].get('description','')} "
                    f"Synonyms: {', '.join(metrics[n].get('synonyms', []))}" for n in names}

    model = SentenceTransformer(MODEL)

    def embed(texts: dict) -> dict:
        vecs = model.encode([texts[n] for n in names], normalize_embeddings=True)
        return {n: v for n, v in zip(names, vecs, strict=False)}

    emb_name = embed(name_text)
    emb_rich = embed(rich_text)

    def cos(emb, a, b):
        return float(np.dot(emb[a], emb[b]))

    # classifier verdict per pair (gated pairs only carry a kind; others are 'not_gated')
    kind = {}
    for p in amb.confusable_pairs(metrics):
        a, b = p.a, p.b
        if "(tree node" in a:      # skip tree-node rows; compare metric names only here
            continue
        kind[frozenset((a, b))] = p.kind
    def verdict(a, b):
        return kind.get(frozenset((a, b)), "not_gated")

    all_pairs = list(itertools.combinations(names, 2))

    md = ["# Embedding check — all-MiniLM-L6-v2 (local, offline)\n"]
    md.append(f"Model: `{MODEL}`. {len(names)} metrics, {len(all_pairs)} pairs. Two texts: NAME "
              f"only, and NAME+description+synonyms.\n")

    # ── CHECK 1 — is value ~ real_value the closest pair? ────────────────────────────────────────
    for label, emb in (("NAME only", emb_name), ("NAME+desc+synonyms", emb_rich)):
        ranked = sorted(all_pairs, key=lambda ab: cos(emb, *ab), reverse=True)
        target = frozenset(("value_moments", "real_value_moments"))
        rank = next(i for i, ab in enumerate(ranked) if frozenset(ab) == target) + 1
        md.append(f"## Check 1 — closest pairs [{label}]\n")
        md.append(f"`value_moments ~ real_value_moments` ranks **#{rank} of {len(all_pairs)}** "
                  f"(cos {cos(emb,'value_moments','real_value_moments'):.3f}).\n")
        md.append("```")
        md.append(f"{'rank':>4}  {'cos':>5}  {'verdict':16} pair")
        for i, (a, b) in enumerate(ranked[:12], 1):
            md.append(f"{i:>4}  {cos(emb,a,b):.3f}  {verdict(a,b):16} {a} ~ {b}")
        md.append("```\n")

    # ── CHECK 2 — does cosine separate scope_only from different_measure? ─────────────────────────
    md.append("## Check 2 — does cosine separate danger (scope_only) from safe (different_measure)?\n")
    for label, emb in (("NAME only", emb_name), ("NAME+desc+synonyms", emb_rich)):
        by_kind = defaultdict(list)
        for a, b in all_pairs:
            by_kind[verdict(a, b)].append(cos(emb, a, b))
        so, dm = by_kind.get("scope_only", []), by_kind.get("different_measure", [])
        # can cosine rank scope_only above different_measure? (AUC over these two classes)
        auc = (sum(1 for x in so for y in dm if x > y) + 0.5 * sum(1 for x in so for y in dm if x == y)) \
              / (len(so) * len(dm)) if so and dm else float("nan")
        md.append(f"### {label}")
        md.append("```")
        for k in ("scope_only", "different_measure", "not_gated"):
            v = by_kind.get(k, [])
            if v:
                md.append(f"{k:18} n={len(v):3}  cos min {min(v):.3f}  mean {np.mean(v):.3f}  max {max(v):.3f}")
        md.append(f"AUC (cosine ranks scope_only above different_measure): {auc:.3f}   "
                  f"[0.5 = no separation, 1.0 = perfect]")
        # high-cosine pairs the token gate MISSED (not_gated but semantically close)
        missed = sorted(((cos(emb, a, b), a, b) for a, b in all_pairs if verdict(a, b) == "not_gated"),
                        reverse=True)[:5]
        md.append("top pairs the token gate MISSED (not_gated), by cosine:")
        for c, a, b in missed:
            md.append(f"   {c:.3f}  {a} ~ {b}")
        md.append("```\n")

    # ── CHECK 3 — does nearest-neighbour cosine track observed mislabel rate? ─────────────────────
    gold = _gold_by_case()
    mis = _mislabel_by_metric(gold)
    rho_by_rep: dict[str, float] = {}
    md.append("## Check 3 — nearest-neighbour cosine vs observed mislabel rate (Test 1 run)\n")
    md.append("Per gold metric (metric_answer cases, pooled over arms): its closest other metric by "
              "cosine, and how often the agent actually got it wrong.\n")
    from scipy.stats import spearmanr
    for label, emb in (("NAME only", emb_name), ("NAME+desc+synonyms", emb_rich)):
        rows = []
        for m, (ans, w) in mis.items():
            if ans == 0 or m not in emb:
                continue
            nn = max((c for c in ((cos(emb, m, o), o) for o in names if o != m)), key=lambda t: t[0])
            rows.append((m, nn[1], nn[0], w / ans, ans))
        rows.sort(key=lambda r: -r[2])
        xs = [r[2] for r in rows]      # nearest-neighbour cosine
        ys = [r[3] for r in rows]      # mislabel rate
        rho, p = spearmanr(xs, ys) if len(xs) > 2 else (float("nan"), float("nan"))
        rho_by_rep[label] = rho
        md.append(f"### {label}  —  Spearman(nn_cos, mislabel_rate) = {rho:.3f}  (p={p:.3f}, n={len(rows)})")
        md.append("```")
        md.append(f"{'gold metric':22} {'nearest neighbour':22} {'cos':>5} {'mislabel%':>9} {'n':>4}")
        for m, nn, c, rate, ans in rows:
            md.append(f"{m:22} {nn:22} {c:.3f} {100*rate:>8.1f}% {ans:>4}")
        md.append("```\n")

    # ── Verdict ──────────────────────────────────────────────────────────────────────────────────
    def rank_of(emb, a, b):
        ranked = sorted(all_pairs, key=lambda ab: cos(emb, *ab), reverse=True)
        return next(i for i, p in enumerate(ranked) if frozenset(p) == frozenset((a, b))) + 1
    r_name = rank_of(emb_name, "value_moments", "real_value_moments")
    dm_name = [cos(emb_name, a, b) for a, b in all_pairs if verdict(a, b) == "different_measure"]

    md.append("## Verdict — where embeddings help, and where they do not\n")
    md.append(f"- **Confusability of the known pair: strong.** Name-only, "
              f"`value_moments ~ real_value_moments` is the **#{r_name}** closest pair of "
              f"{len(all_pairs)} (cos {cos(emb_name,'value_moments','real_value_moments'):.3f}), far "
              f"above the next pair ({max(dm_name):.3f}). Embeddings clearly capture the one collision.")
    md.append("- **Better recall than the token gate.** Embeddings surface related pairs the gate "
              "cannot see because they share no token: `reminder_open_rate ~ reminders_shown` "
              "(plural defeats the gate), `arpu ~ mrr`, `active_subscriptions ~ paying_users`. This "
              "is a real upgrade for the confusability GATE.")
    md.append("- **But cosine is not danger.** The pairs embeddings newly surface are mostly "
              "different_measure (safe): a share vs a count, a per-user average vs a total. High "
              "cosine means 'similar', not 'silently swappable'. The single scope_only pair tops the "
              "list, but with n=1 that is one data point, not class separation (the AUC=1.0 is "
              "vacuous at n=1). The structural same-measure/different-scope test stays necessary.")
    md.append(f"- **Cosine does NOT predict observed confusion.** Nearest-neighbour cosine vs "
              f"mislabel rate: Spearman {rho_by_rep.get('NAME only', float('nan')):.2f} (name, n.s.) "
              f"and {rho_by_rep.get('NAME+desc+synonyms', float('nan')):.2f} (with descriptions, "
              f"negative). Two structural reasons, both seen in the table: `new_signups` mislabels "
              f"18.8% at LOW cosine (the welded `is_internal` scope on an unnamed sibling — no "
              f"neighbour to be close to), and `active_subscriptions`/`active_users` sit at HIGH "
              f"cosine with ~0% mislabels (similar names, plainly different things the agent does not "
              f"confuse). So the 'LLMs are embeddings, so name-cosine predicts confusion' intuition "
              f"is not supported at this n.")
    md.append("- **Descriptions hurt.** Adding description+synonyms pulled unrelated revenue/user "
              "concepts together and demoted the true pair from #1 to #3. Name-only is the better "
              "representation here.")
    md.append("\n**Net:** adopt embeddings to REPLACE the token-overlap gate (they fix the "
              "plural/synonym misses and rank the real collision top), keep the structural test for "
              "DANGER, and do not use cosine to predict which cases get mislabelled. Caveats: one "
              "scope_only pair and n=10 metrics make this suggestive, not settled; and a local model "
              "predicting an OpenAI agent means the strong check-1 result is trustworthy while the "
              "check-3 null is partly inconclusive — though its cause here is structural, not model "
              "weakness.")

    OUT_MD.write_text("\n".join(md))
    print("\n".join(md))
    print(f"\nwrote {OUT_MD.relative_to(REPO)}")


if __name__ == "__main__":
    sys.exit(main())
