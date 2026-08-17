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
| docs | thin | COMMENTs carry the scope rule ("exclude NOT is_internal", "mrr = annual/12") |

Same decomposition as study 01: SER = **wrong-SELECTION** (Mode 1 — the agent grounded on the wrong
COLUMN/table, recovered from its SQL via `wrong_grounding` markers) + **wrong-CONSTRUCTION** (Mode 2 —
the right column, built wrong). Gold is one `gold_sql` oracle against the clean star.

## Result (gpt-5-mini, reps=3, 4 flagged + 1 clean)

| arm | flagged correct | flagged SER | wrong-SELECTION | wrong-CONSTRUCTION | clean SER |
|---|---|---|---|---|---|
| before | 0.00 | 1.00 | **0.50** | 0.50 | 0.00 |
| after | 0.58 | 0.42 | **0.00** | 0.42 | 0.00 |

Modelling the messy columns into clean, documented ones drives **wrong-column selection 0.50 → 0.00**
— the same shape as study 01's wrong-metric selection, one layer down. SER falls 1.00 → 0.42; the
residual 0.42 is genuine **construction** (the agent forgets the `is_active` filter or a period even on
clean columns) — Mode 2, the validators' lane, which better modelling does not fix. Observed picks on
`before`: `recurring` summed `billed_amount` (not `mrr`); `active_users` filtered `is_test` (not
`is_internal`) — the exact column confusions preflight flags in the warehouse layer.

## The two studies together

| | selection harm (Mode 1) | after the fix |
|---|---|---|
| study 01 (semantic layer) | wrong **metric** 0.43 / 0.29 | 0.00 |
| study 02 (raw SQL) | wrong **column** 0.50 | 0.00 |

Fixing what preflight flags removes the selection harm at whichever layer it lives — a sprawled
semantic layer *or* sprawled fact-table columns. The construction residual is the other lane in both.

## Run

    python run.py --model gpt-5-mini --reps 3     # or --model claude-sonnet-5
