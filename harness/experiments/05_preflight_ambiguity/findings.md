# Experiment 05 — findings

What the two before/after studies measured, and what they show. Every number here is the flagged tier
(the ambiguous questions), reps=3, two models (`gpt-5-mini`, `claude-sonnet-5`), graded by a
deterministic `gold_sql` oracle, not an LLM judge. Practitioner notes and the how-to live in
`practical.md`; this file is the results.

## The question

preflight detects cross-layer analytics ambiguity **statically**, before an agent runs. This experiment
tests whether that static signal predicts, and whether fixing it removes, a **runtime** harm: an
analytics agent putting a wrong number in front of a decision-maker as if it were right.

## Metrics hierarchy

The reader's question is "can I trust this number?", so the reported metrics are built from it and kept
consistent with experiments 01 to 04.

- **North-star triad** (read together, never singly): **silent-error rate (SER)**, **coverage**, and
  **balanced accuracy**. An agent can flatter any one by sacrificing another (drive SER to 0 by
  refusing everything, which collapses coverage), so a real result moves all three the right way at
  once.
- **SER is root-cause-agnostic**: how often the agent served a wrong number, whatever the cause. It
  **decomposes** into two modes:
  - **wrong-SELECTION (Mode 1)** — the agent grounded on the wrong metric, column, or table. This is
    the ambiguity preflight flags, and the only lane preflight claims.
  - **wrong-CONSTRUCTION (Mode 2)** — the agent grounded correctly but built the query wrong (a stray
    period, a missing filter, the wrong grain). This is the validators' lane, not preflight's.
- The selection/construction split is **observed from the trace**, not inferred: the metric the agent
  queried is read from its `query_metric` argument (study 01), and the wrong column or table is
  recovered from substrings in its `run_sql` (study 02).

## Study 01 — governed semantic layer (dbt MetricFlow)

The metric-selection case a governed layer is meant to protect. The agent answers by selecting a
governed metric (`query_metric`). Four environments: `{small,high}_{before,after}`. The headline is the
`high_before → high_after` contrast; `small` is a cited baseline (its before/after was 0 → 0 on
selection, because a well-described governed layer's one residual trap does not bite, so static
overestimates runtime harm there).

`high_before` is authored to look like a pressured team's accretion: three teams' `mrr` /
`recurring_revenue`, five active-user definitions, gross versus net revenue, `moments` overloaded across
tables, `active user` and `value moment` each documented two ways. The metric descriptions are stripped
to bare names, so the agent disambiguates by name. `high_after` resolves exactly what preflight flags
(rename to encode scope, drop a decoy, reconcile a definition), and preflight re-scans it to ~0.

The traps are **structural whole-population** name-match traps across five families: `recurring_revenue`
(question says "recurring revenue", the sprawled layer offers `recurring_revenue` beside the governed
`mrr`), `new_users`, `value_moments`, `habits`, `actives`. Two clean control families
(`marketing_spend`, `paying_users`) are present on every layer.

### Result (flagged tier)

| model | arm | SER | coverage | wrong-SELECTION | wrong-CONSTRUCTION |
|---|---|---|---|---|---|
| gpt-5-mini | high_before | 0.30 | 1.00 | **0.43** | 0.00 |
| gpt-5-mini | high_after | 0.17 | 1.00 | **0.00** | 0.17 |
| sonnet-5 | high_before | 0.33 | 0.83 | **0.29** | 0.21 |
| sonnet-5 | high_after | 0.07 | 0.90 | **0.00** | 0.04 |

Three things hold:

1. **wrong-SELECTION reproduces on both models** (0.43, 0.29) and the fix drives it to **0.00** on both.
   This is the harm preflight predicts, and it is model-robust.
2. **The effect concentrates on the flagged tier.** Clean control questions stay at wrong-selection
   0.00 in both arms.
3. **SER falls** (0.30 → 0.17, 0.33 → 0.07) as the fix removes the selection half.

Per-family wrong-selection on `high_before` (gpt-5-mini) shows an honest, uneven shape rather than a
flat average: `recurring_revenue` 1.00 and `new_users` 1.00 always mis-pick; `value_moments` ~0.22
bites on the sprawled layer but not the governed one; `habits` and `actives` ~0. The same finding has a
different outcome depending on how confusable the specific trap is.

The `high_after` construction residual (gpt-5-mini 0.17, sonnet-5 0.04) is genuine Mode-2 query-building
that the semantic layer still leaves to the agent, not a fixture artifact: the stock metrics are
modelled from monthly snapshots (see `practical.md`), so a stray period does not shrink them. The
before-arm construction reads low (gpt-5-mini 0.00) because where selection is already wrong, the
construction slip beneath it is masked (the agent picks the wrong metric before it can fumble the right
one's query).

The sharper model (sonnet-5) makes less construction noise and **abstains more on the sprawl**
(coverage 0.83) rather than answering confidently wrong.

## Study 02 — raw warehouse, no semantic layer

Study 01's before/after moved one layer down: the ambiguity lives in the **fact-table columns**, not a
semantic layer, and the agent answers by **raw SQL** (`run_sql`) at rung 2. This is the common dbt setup
(models, no governed metrics), and it tests whether dimensional modelling alone (clean columns plus
docs) removes the harm.

Two DuckDB schema-variants of the same star (`warehouses.py`, views, no rows copied):

| | before (`s2_before`) | after (`s2_after`) |
|---|---|---|
| revenue | raw `billed_amount` only (no MRR) | modelled `mrr` (annual/12) and `net_revenue` |
| internal accounts | two flags `is_internal` **and** `is_test` (different sets) | one `is_internal` |
| value moments | `moments` in two tables (`activity`, `daily_rollup`) | one `fct_activity.moments` |
| docs | thin | COMMENTs carry every scope rule |

Five cases (four flagged, one clean). wrong-SELECTION is recovered from `run_sql` substrings marked in
`cases.yml` (`wrong_grounding`): `recurring` grabbing `billed_amount` instead of `mrr`, `active_users`
filtering `is_test` instead of `is_internal`, `value_moments` reading the overloaded `daily_rollup`.

### Result (flagged tier)

| model | arm | correct | SER | coverage | wrong-SELECTION | wrong-CONSTRUCTION |
|---|---|---|---|---|---|---|
| gpt-5-mini | before | 0.25 | 0.67 | 0.92 | **0.55** | 0.18 |
| gpt-5-mini | after | 1.00 | 0.00 | 1.00 | **0.00** | 0.00 |
| sonnet-5 | before | 0.08 | 0.42 | 0.50 | **0.67** | 0.17 |
| sonnet-5 | after | 1.00 | 0.00 | 1.00 | **0.00** | 0.00 |

Modelling the messy columns into clean, documented ones drives **wrong-column selection to 0.00** on
both models, the same shape as study 01's wrong-metric selection one layer down, and here it takes SER
with it (0.67 → 0.00 and 0.42 → 0.00): a raw-SQL agent given clean columns and a complete, consistent
scope rule has nothing left to build wrong on this question set.

Coverage 0.50 on sonnet-5 `before` is the agent **abstaining** on half the ambiguous questions rather
than answering them wrong, which is the safer failure. After the fix it answers all of them correctly
(coverage 1.00).

### A gold inconsistency fixed en route

The first `s2_after` governed the internal-account rule only for user and activity metrics and left
revenue implicit, and one activity gold (`value_moments`) failed to apply its own stated rule. Both
models then excluded internal accounts consistently, which is defensible analytics judgment, and were
graded wrong for a gold inconsistency rather than a real error. The rule was made **uniform and
explicit** (exclude `NOT is_internal` from every metric, revenue included, stated on the `mrr` and
`net_revenue` comments) and both models were re-run. wrong-SELECTION is recovered from the SQL and is
independent of the gold, so only the construction and SER numbers moved. Which accounts belong in
revenue is a governed choice; the point that stands is that the layer must state it once and the gold
must follow, which is itself the kind of gap preflight exists to surface.

## The two studies together

| | selection harm before | after the fix |
|---|---|---|
| study 01 (semantic layer) | wrong **metric** 0.43 / 0.29 | 0.00 / 0.00 |
| study 02 (raw warehouse) | wrong **column** 0.55 / 0.67 | 0.00 / 0.00 |

Fixing what preflight flags removes the selection harm at whichever layer it lives, a sprawled semantic
layer or sprawled fact-table columns, on both models. Study 01 keeps a small construction residual (the
semantic layer still leaves the agent a query to shape); study 02's residual goes to zero because clean,
fully-documented columns leave nothing to build wrong on these five questions.

## Validation on a real, public dbt project

The `dbt-manifest` dialect was pointed at the unmodified `dbt-labs/jaffle-sl-template` (dbt 1.12, its
compiled `manifest.json`, 5 semantic models, 18 metrics, 10 model nodes). preflight read all three
layers (67 grounding facts) and reported **12 findings**, each cited back to the source `.yml` or `.sql`
line an analytics engineer edits:

| finding | what | citation |
|---|---|---|
| SCOPE_TRAP | `food_orders` is `orders` plus a hidden filter; a bare "how many orders" is silently scoped | `orders.yml:139` |
| CONCEPT_FORK | `food_revenue` ~ `drink_revenue` ~ `revenue`: one aggregation over different columns, three numbers | `order_items.yml:30` |
| DUPLICATE (cross-layer) | the semantic measure `order_total` and the warehouse column `order_total`: one meaning, two names, two paths | `orders.yml:18` |

This shows the finding types are not bespoke to the study fixtures. They appear in a widely-used public
dbt template that nobody built as a trap.

## Honest boundaries

- **Sample is modest by design**: 10 flagged questions (study 01), 5 (study 02), three repetitions each,
  two models. These are directions with a clear, repeated signal, not large-n estimates.
- **preflight owns selection, not construction.** The construction residual is reported, not hidden. On
  a raw warehouse it is the argument for a semantic layer (study 01); the semantic layer's own residual
  is the argument for the Mode-2 validators.
- **The gold is authored alongside the fixtures.** The circularity is managed by a deterministic oracle
  (no LLM judgement), blind red-team authoring of the questions before the fixes, and grounding
  recovered from the trace by mechanism, but it is not eliminated. See the cofounder review.
