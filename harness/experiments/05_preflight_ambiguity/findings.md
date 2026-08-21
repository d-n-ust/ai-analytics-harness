# Experiment 05 — findings from the two superseded studies

> **Superseded on 2026-08-21.** The published measurement is the merged experiment in
> `one_warehouse/`: one dbt-shaped warehouse with models *and* a metrics layer over them, and one
> agent holding both `query_metric` and raw SQL. Splitting the two floors into separate studies made
> one warehouse look like two experiments and left half of each untested. Headline from the merged
> run: 11 static findings before and 0 after; wrong-metric selection 24% → 0.00 (`gpt-5-mini`) and
> 11% → 0.00 (`gpt-5.6-terra`) where the layer governs the concept.
>
> This file is kept as the record of how the design got there, including the fixture defects the
> studies had and the corrections that followed. The numbers below are those studies' numbers and
> are not the ones to quote.

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
to bare names, so the agent disambiguates by name. `high_after` is the governed remodel of the same
business (one metric per concept, scope as a stated rule), and preflight re-scans it to 0. An earlier
draft of this file said the fix "resolves exactly what preflight flags"; the diff shows a full remodel,
so the causal claim is stated at the environment level: replacing the sprawled layer with a governed one
removes the selection harm, and the re-scan verifies the governed layer is ambiguity-free.

Static scans are persisted for both representations, re-run with the published `preflight-analytics
0.2.0`, lexical gate: the bespoke three-layer environments (`scan.md`: small 1 → 0, high **19 → 0**)
and the MetricFlow layers the agent actually queried (`scan_mf.md`: small 1 → 0, high **7 → 0**).

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

Per-family wrong-selection on `high_before` shows an honest, uneven shape rather than a flat average
(wrong picks / answers given; abstentions excluded — an agent that refuses has picked nothing):

| family | the trap | gpt-5-mini | claude-sonnet-5 | static (0.2.0, `scan_mf.md`) |
|---|---|---|---|---|
| recurring_revenue | picked `recurring_revenue` / `monthly_recurring_revenue`, wanted `mrr` | 6/6 | 5/6 | LOW DUPLICATE `mrr ~ monthly_recurring_revenue`; `recurring_revenue` joins via the embeddings gate, and the bespoke rep flags the family HIGH |
| new_users | picked `new_users`, wanted `new_signups` | 4/4 | 1/5 | HIGH SCOPE_TRAP, exactly this pair |
| value_moments | picked `real_value_moments` / `total_moments`, wanted `value_moments` | 2/9 | 1/7 | HIGH SCOPE_TRAP cluster |
| actives | never mis-picked; claude-sonnet-5 abstained 3/3 | 0/3 | 0/0 | HIGH SCOPE_TRAP cluster |
| habits | never mis-picked | 0/6 | 0/6 | none (the all-vs-active split lives in table contents, not YAML) |

The bite mechanism is name-match: harm concentrates where a decoy's name matches the question wording
and the governed metric's does not. Findings mark risk, not destiny — the most-flagged family
(`actives`) never bit, and the same `value_moments` finding sits on the low-sprawl layer at 0.00.

Two of claude-sonnet-5's five wrong revenue picks used `monthly_recurring_revenue`, which is `mrr`
under a second name: the returned figure was numerically right and the grounding still ungoverned, the
mildest form of the failure.

Building this per-family join surfaced a detector blind spot: `mrr ~ recurring_revenue` was expected
to flag as a CONCEPT_FORK (the fixture's own comment says so) but the confusability gate cannot pair
an acronym with a spelled-out name when descriptions are stripped. Fixed in `preflight-analytics
0.2.0` (structural pairing: meaning-agreement bypasses the name gate), validated as a no-op on
`jaffle-shop`, `jaffle-sl-template`, and a public Cube model. All static counts in this file are
0.2.0 numbers.

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
compiled `manifest.json`, 5 semantic models, 18 metrics, 10 model nodes). preflight 0.2.0 (lexical
gate, the default install) read all three layers and reported **14 findings (5 high)**, each cited
back to the source `.yml` or `.sql` line an analytics engineer edits:

| finding | what | citation |
|---|---|---|
| SCOPE_TRAP | `food_orders` is `orders` plus a hidden filter; a bare "how many orders" is silently scoped | `orders.yml:139` |
| CONCEPT_FORK | `food_revenue` ~ `drink_revenue` ~ `revenue`: one aggregation over different columns, three numbers | `order_items.yml:30` |
| DUPLICATE (cross-layer) | the semantic measure `order_total` and the warehouse column `order_total`: one meaning, two names, two paths | `orders.yml:18` |

This shows the finding types are not bespoke to the study fixtures. They appear in a widely-used public
dbt template that nobody built as a trap.

## Honest boundaries

- **Static prediction is study 01's claim only.** A preflight scan of the bare study-02 DDL reports no
  findings (`study_02_no_semantic_layer/scan.md`): its ambiguity lives in definitions that are not
  written down (two undocumented account flags, a missing `mrr` column), and a static scanner of
  definitions cannot read what was never written. Study 02 measures the repair, not the prediction.
- **Sample is modest by design**: 10 flagged questions (study 01), 5 (study 02), three repetitions each,
  two models. These are directions with a clear, repeated signal, not large-n estimates.
- **preflight owns selection, not construction.** The construction residual is reported, not hidden. On
  a raw warehouse it is the argument for a semantic layer (study 01); the semantic layer's own residual
  is the argument for the Mode-2 validators.
- **The gold is authored alongside the fixtures.** The circularity is managed by a deterministic oracle
  (no LLM judgement), blind red-team authoring of the questions before the fixes, and grounding
  recovered from the trace by mechanism, but it is not eliminated. See the cofounder review.
