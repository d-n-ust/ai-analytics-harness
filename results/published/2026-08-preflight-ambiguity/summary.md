# Preflight ambiguity — does fixing what the scan finds improve the agent?

Experiment 5. One dbt-shaped warehouse with dbt models **and** a MetricFlow metrics layer over them,
36 questions, an agent holding both `query_metric` and raw SQL. The warehouse is measured **before**
and **after** the definitions flagged by a static ambiguity scan are repaired. Final measurement,
run 2026-08-21, both models, 3 reps (n = 108 attempts each).

The question is not "does the scan find confusions" (its own recall/precision answers that). It is
the one a buyer asks: **when you fix what the scan flags, does the agent get measurably more
trustworthy, and what harm is left in problems the scan cannot read?**

## The static dose

The scan reads the definitions before any agent runs. `scan.md` has the full list.

| | definitions | high | med | low | findings |
|---|---|---|---|---|---|
| before | 70 | 4 | 3 | 4 | **11** |
| after | 45 | 0 | 0 | 0 | **0** |

## The agent, before and after

Each attempt is split by whether the scan flagged its concept: **flagged** concepts are the ones the
repair could fix; **clean** concepts are what the scan found nothing to say about. `silent` is the
confident-wrong rate; `wrong-sel` is picking the wrong (decoy) metric; `wrong-constr` is building a
metric wrong in SQL.

### gpt-5-mini (n = 108)

| split | n | silent | wrong-sel | wrong-constr | correct |
|---|---|---|---|---|---|
| overall | 108 | 36.1% → 9.3% | 29.2% → 4.6% | 17.0% → 5.6% | 62.0% → 90.7% |
| flagged | 87 | 43.7% → 9.2% | 34.9% → 4.6% | 20.9% → 5.7% | 55.2% → 90.8% |
| clean | 21 | 4.8% → 9.5% | 5.0% → 4.8% | 0.0% → 4.8% | 90.5% → 90.5% |

### gpt-5.6-terra (n = 108)

| split | n | silent | wrong-sel | wrong-constr | correct |
|---|---|---|---|---|---|
| overall | 108 | 20.4% → 2.8% | 14.8% → 2.9% | 5.6% → 0.0% | 79.6% → 94.4% |
| flagged | 87 | 25.3% → 3.4% | 18.4% → 3.6% | 6.9% → 0.0% | 74.7% → 93.1% |
| clean | 21 | 0.0% → 0.0% | 0.0% → 0.0% | 0.0% → 0.0% | 100.0% → 100.0% |

## What the board shows

- **The repair does its work on the flagged concepts.** For `gpt-5-mini`, silent error on flagged
  concepts falls 43.7% → 9.2% and wrong-metric selection 34.9% → 4.6%; for `gpt-5.6-terra`, 25.3% →
  3.4% and 18.4% → 3.6%. The overall improvement is driven by the flagged half.
- **Scale is not a substitute for governed definitions.** Before any repair, the larger model still
  picks a decoy metric on flagged concepts 18.4% of the time. Governing the definition, not the
  model size, is what removes it.
- **The residual is real, not zero.** After repair, wrong-metric selection is ~4.6% (`gpt-5-mini`)
  and ~3.6% (`gpt-5.6-terra`) on flagged concepts, not 0. The scan-invisible ("clean") split is
  perfect for the larger model but not for `gpt-5-mini`, where the small n = 21 makes its movement
  (silent 4.8% → 9.5%) noise rather than signal.

## Reconciliation note

This board (the final 2026-08-21 run) is the authoritative measurement. The harness top-level
`README.md` currently summarises experiment 5 as "wrong-metric selection goes 24% → 0.00 for
gpt-5-mini and 11% → 0.00 for gpt-5.6-terra, in 93 answers each." Those figures and the "→ 0.00" do
not match this board (flagged n = 87; wrong-selection 34.9% → 4.6% and 18.4% → 3.6%). The README
prose predates this run and should be reconciled to these numbers before the article
(`why-ai-analysts-pick-the-wrong-metric`) ships.

## Provenance and how to check

- **Fixture:** `harness/experiments/05_preflight_ambiguity/one_warehouse/` — `warehouses.py` (the
  before/after warehouses), `cases.yml` (36 questions), `scan.py` / `scan.md` (the static dose),
  `run.py` (the measurement).
- **Boards:** `result__gpt-5-mini.json.gz`, `result__gpt-5.6-terra.json.gz` here — the full per-arm,
  per-split aggregates with their rows, gzipped copies of the experiment's committed results.
- **Findings:** experiment 5's manifest and `docs/REPAIR-MATRIX.md` neighbourhood; the top-level
  README's "5 · Ambiguity" section (pending the reconciliation above).

Read a board back:

```
PYTHONPATH=harness uv run python - <<'PY'
import json, gzip
for m in ("gpt-5-mini", "gpt-5.6-terra"):
    d = json.load(gzip.open(f"results/published/2026-08-preflight-ambiguity/result__{m}.json.gz", "rt"))
    for split in ("overall", "flagged", "clean"):
        b, a = d["arms"]["before"][split], d["arms"]["after"][split]
        print(m, split, "silent", round(b["silent_error"], 3), "->", round(a["silent_error"], 3))
PY
```
