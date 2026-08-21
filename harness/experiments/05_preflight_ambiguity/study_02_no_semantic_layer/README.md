# Study 02 — before/after on the warehouse (no semantic layer)

Study 01's before/after, moved down a layer: the ambiguity lives in the **fact-table columns**, not a
semantic layer, and the agent answers by **raw SQL** (`run_sql`), never `query_metric`. This is the
common dbt setup — models, no governed metrics — and it tests whether *dimensional modelling* alone
(clean columns + docs) removes the harm, or whether governance is still needed.

## The two warehouses (`warehouses.py`, views over the live star)

| | before (`s2_before`) | after (`s2_after`) |
|---|---|---|
| revenue | raw `billed_amount` only (no MRR) | modelled `mrr` (annual/12) and `net_revenue` columns |
| internal accounts | **two** flags `is_internal` **and** `is_test` (different sets) | one `is_internal` |
| value moments | `moments` in **two** tables (`activity`, `daily_rollup`) | one `fct_activity.moments` |
| docs | thin | COMMENTs carry the scope rule ("mrr = annual/12", "exclude NOT is_internal from every metric") |

Same decomposition as study 01: SER = **wrong-SELECTION** (Mode 1 — the agent grounded on the wrong
COLUMN/table, recovered from its SQL via `wrong_grounding` markers) + **wrong-CONSTRUCTION** (Mode 2 —
the right column, built wrong). Gold is one `gold_sql` oracle against the clean star.

The internal-account rule is stated **uniformly** in the `after` docs: staff and test accounts
(`is_internal`) are excluded from *every* metric, revenue included, and the gold matches. An earlier
draft governed it only for user/activity metrics and left revenue implicit, and one activity gold
(`value_moments`) failed to apply its own stated rule; both models then excluded internal accounts
consistently and were scored wrong for a gold inconsistency, not a real error. Making the rule uniform
removed that confound. Whether internal accounts belong in revenue is a governed choice; the point is
the layer must state it once and the gold must follow, which is itself the kind of gap preflight exists
to surface.

## Result (reps=3, 4 flagged + 1 clean, flagged tier)

| model | arm | correct | SER | coverage | wrong-SELECTION | wrong-CONSTRUCTION |
|---|---|---|---|---|---|---|
| gpt-5-mini | before | 0.25 | 0.67 | 0.92 | **0.55** | 0.18 |
| gpt-5-mini | after | 1.00 | 0.00 | 1.00 | **0.00** | 0.00 |
| sonnet-5 | before | 0.08 | 0.42 | 0.50 | **0.67** | 0.17 |
| sonnet-5 | after | 1.00 | 0.00 | 1.00 | **0.00** | 0.00 |

Modelling the messy columns into clean, documented ones drives **wrong-column selection to 0.00** on
both models — the same shape as study 01's wrong-metric selection, one layer down — and here it takes
SER with it (0.67 → 0.00 and 0.42 → 0.00), because a raw-SQL agent given clean columns and a complete,
consistent scope rule has nothing left to build wrong on this question set. Observed picks on `before`:
`recurring` summed `billed_amount` (not `mrr`); `active_users` filtered `is_test` (not `is_internal`).
Coverage 0.50 on sonnet-5 `before` is the agent abstaining on half the ambiguous questions rather than
answering them wrong, which is the safer failure; after the fix it answers all of them correctly.

## Static scan (`scan_s2.py` → `scan.md`): a boundary, verified

A preflight scan of the bare `s2_before` DDL reports **no findings** (`scan.md`, published 0.1.0,
lexical gate). This is not a bug in the scan; it is the boundary of static definition analysis. The
before-warehouse's ambiguity lives in definitions that are **not written down**: `is_internal` vs
`is_test` share no name similarity and no documentation states what either excludes; `mrr` does not
exist as a column at all, so nothing collides with `billed_amount`; `moments` appears in only two
tables, below the overload threshold calibrated for real stars. Study 02 therefore measures the
**repair** (modelling + stated scope rules drive wrong-selection 0.55/0.67 → 0.00), not static
prediction. Static prediction is study 01's claim, where the sprawl is written down and preflight
reads it. An earlier draft of this README said preflight flags these column confusions; that was
never backed by a persisted scan and is corrected here.

## The two studies together

| | selection harm (Mode 1) before | after the fix |
|---|---|---|
| study 01 (semantic layer) | wrong **metric** 0.43 / 0.29 | 0.00 / 0.00 |
| study 02 (raw SQL) | wrong **column** 0.55 / 0.67 | 0.00 / 0.00 |

Fixing what preflight flags removes the selection harm at whichever layer it lives — a sprawled
semantic layer *or* sprawled fact-table columns — on both models. Study 01 keeps a small construction
residual (the semantic layer still leaves the agent a query to shape); study 02's residual goes to zero
because clean, fully-documented columns leave nothing to build wrong on these five questions.

## Run

    python run.py --model gpt-5-mini --reps 3     # or --model claude-sonnet-5
