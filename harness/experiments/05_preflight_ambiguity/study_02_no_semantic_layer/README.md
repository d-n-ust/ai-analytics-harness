# Study 02 — no semantic layer (the governance ladder)

Study 01 shows that *within* a governed semantic layer, metric sprawl makes the agent pick the wrong
metric, and fixing what preflight flags removes it. Study 02 asks the prior question: **is a governed
layer worth having at all?** — the common setup is dbt models with no semantic layer, where the agent
writes its own SQL.

## The ladder

The SAME six plain questions, asked of the same agent at three levels of governance:

| rung | what the agent has | how it answers |
|---|---|---|
| 1 · messy raw | the raw application-extract tables (`u`, `hab`, `evt`, `subs`): cryptic names, `evt.etype` an integer, `u.internal` 0/1/NULL | raw SQL |
| 2 · clean star | a conformed star (`dim_users`, `agg_active_days`): clear names, but still no metric definitions | raw SQL |
| 3 · semantic layer | governed metrics | `query_metric` |

Gold is one deterministic `gold_sql` oracle against the clean star, computed once, so it is the same
truth at every rung. `set_star(False)` drops the star for rung 1, so the messy baseline is genuinely
raw-only — the agent cannot quietly query the clean tables.

## Result (gpt-5-mini, reps=3, 6 questions)

| rung | correct | silent-error | refused |
|---|---|---|---|
| 1 · messy raw | 0.61 | **0.33** | 0.06 |
| 2 · clean star | 0.72 | **0.28** | 0.00 |
| 3 · semantic layer | **1.00** | **0.00** | 0.00 |

As governance is added, the silent-error rate falls (0.33 → 0.28 → 0.00) and correctness rises
(0.61 → 0.72 → 1.00). **Without a governed layer the agent silently errs ~a third of the time on plain
questions; the semantic layer drives it to zero.** The harm is Mode-2 construction — on raw data the
agent welds its own scope (which event type is a value moment, which `internal` value to exclude), and
either refuses (it can't tell) or guesses (a silent number). This is why the semantic layer's value is
governance: it makes the ambiguity resolvable rather than leaving it to the agent to weld invisibly.

Together with study 01: **a semantic layer removes the raw-data harm entirely (study 02), and keeping
that layer un-sprawled removes the residual selection harm (study 01).**

## Run

    python ladder.py --model gpt-5-mini --reps 3     # or --model claude-sonnet-5

## Next
- A column-level **wrong-grounding** rate (parse the agent's `run_sql` to see which column/table it
  bound to — e.g. `is_internal` vs `is_test`), so rung-1/2 harm splits into selection vs construction
  the way study 01 does.
- A before/after *within* rung 1 (fix the confusable columns preflight flags) to attribute the ladder
  gain to specific findings.
