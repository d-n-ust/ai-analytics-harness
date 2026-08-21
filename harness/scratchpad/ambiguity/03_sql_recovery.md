# T3 — primitive recovery from the agent's actual emitted SQL (all published runs)

Pooled across all four published runs. The grounding RUNG matters: at low rungs the agent has no governed metrics and must write SQL; at high rungs it calls named metrics. Sampling one high-rung run understates raw-SQL usage (an earlier single-run pass read 3%).

## Governed vs raw SQL, by grounding rung
```
rung    run_sql  query_metric   raw %
R0           83           309     21%
R1           51           276     16%
R2           38           178     18%
R3           17           177      9%
R4            0           171      0%
R5            0           194      0%
R6           23           942      2%
R7            0           738      0%
R8            0           777      0%
R9            0          1099      0%
R?           82          1839      4%
ALL         294          6700      4%
```
At the raw-warehouse rungs the agent writes its own SQL far more; the governed rungs push it onto named metrics (grounding declared, no parse). So 'is recovery needed' depends on how governed the deployment is.

## Recovery on the raw agent SQL (the parse target)
```
raw statements pooled ........ 265  (261 parsed, 98%)

NAIVE parser (find_all(Table), WHERE-only) — what a first cut reports:
  entity 'recovered' ........... 100%   but FALSE-RECOVERY 34% (a CTE alias reported as a source table)
  scope 'recovered' (WHERE) .... 80%   and misses welded scope

BETTER parser (sqlglot scope-resolved entity; reads welded CASE scope out of aggregate):
  entity (real source table) ... 92%   false-recovery now ~0
  scope (WHERE or welded) ...... 81%   (WHERE 80% + welded 20% now extracted, not lost)
  measure ...................... 89%
  grain (GROUP BY present) ..... 49%   (absence = a total, not a miss)
  join path (JOIN present) ..... 35%

sanity — governed compiler SQL: 4263/4263 parse, entity 100%, scope 98%, measure 100%
```
**Catch B addressed, properly.** Entity now uses sqlglot's scope resolver (`sqlglot.optimizer.scope.traverse_scope`), which resolves each table reference per scope like a compiler — dropping entity false-recovery from 34% to ~0. This is strictly more correct than a flat 'drop any name that is a CTE' heuristic, which loses a physical table whose name a CTE happens to reuse (they agree on this data, 261/261, only because no such collision occurs). Reading the CASE condition out of the aggregate recovers the 20% of welded scope a WHERE-only parser lost.

## Hand-check sample (20 statements + better-parser output)
```
[ 1] RAW  -- Calculate monthly churn rate for premium subscriptions WITH subs AS ( SELECT DATE_TRUNC('month', event_date) AS month, user_id, status FR
      -> tables=['fct_subscriptions'] scope=True grain=True agg=True welded_scope=["status = 'active'", "status = 'cancelled' and event_date >= month and event_date < month + interval '1' month"]
[ 2] RAW  -- Calculate monthly churn rate for premium subscriptions for the most recent complete month (data complete through 2026-07-12). We need las
      -> tables=['fct_subscriptions'] scope=True grain=False agg=True
[ 3] RAW  -- Calculate trial-to-paid conversion over last quarter (most recent complete quarter ending before 2026-07-16) WITH params AS ( SELECT '202
      -> tables=['fct_subscriptions'] scope=True grain=True agg=True
[ 4] RAW  -- Check churners over a longer recent period to have enough data: last 8 weeks ending 2026-07-12 with churners as ( select user_id, ended_d
      -> tables=['fct_reminders', 'fct_subscriptions', 'fct_value_moments'] scope=True grain=True agg=True welded_scope=['completions_final_week = 0', "v.completed_date between c.ended_date - interval '7' day and c.ended_date"]
[ 5] RAW  -- Check if trial info exists in dim_users or subscriptions via status or started_date pattern SELECT status, COUNT(*) FROM fct_subscription
      -> tables=['fct_subscriptions'] scope=False grain=True agg=True
[ 6] RAW  -- Compare final week vs prior week activity for churned users WITH churned AS ( SELECT user_id, ended_date FROM fct_subscriptions WHERE sta
      -> tables=['fct_subscriptions', 'fct_value_moments'] scope=True grain=True agg=True welded_scope=['v.completed_date between w.week_start and w.ended_date', 'v.completed_date between w.week_start and w.ended_date']
[ 7] RAW  -- Compute LTV and CAC for last 4 weeks (2026-06-15 to 2026-07-12) WITH m AS ( SELECT SUM(mrr) AS total_mrr FROM ( SELECT mrr FROM ( SELECT 
      -> tables=[] scope=False grain=False agg=True
[ 8] RAW  -- Compute LTV and CAC using governed metrics proxies: LTV = ARPU * gross margin * lifetime (months). Use naive lifetime = 1 / monthly churn
      -> tables=[] scope=False grain=False agg=False
[ 9] RAW  -- Compute LTV-to-CAC -- LTV = ARPU * gross_margin_months? We need assumptions. Use CLTV = ARPU * (1 / churn_rate). Need churn. Compute mont
      -> tables=['subscriptions'] scope=False grain=False agg=False
[10] RAW  -- Compute behavior in the final week before subscription ended (canceled) WITH cancellations AS ( SELECT user_id, ended_date AS cancel_date
      -> tables=['fct_subscriptions', 'fct_value_moments'] scope=True grain=True agg=True welded_scope=['completions = 0 or completions is null']
[11] RAW  -- Compute monthly churn for premium: count of users with active subscription at start of month and who ended (canceled) during that month. 
      -> tables=['fct_subscriptions'] scope=True grain=True agg=True
[12] RAW  -- Compute monthly churn rate for premium (governed segment 'premium' maps to plan like 'premium'?) -- Check distinct plan values select dis
      -> tables=['fct_subscriptions'] scope=False grain=False agg=False
[13] RAW  -- Compute monthly churn rate for premium (paid) subscriptions for the most recent complete month WITH subs AS ( SELECT user_id, plan, start
      -> tables=['fct_subscriptions'] scope=True grain=False agg=True
[14] RAW  -- Compute monthly churn rate for premium plan for June 2026 (last full month). WITH subs AS ( SELECT user_id, plan, started_date AS start_d
      -> tables=['fct_subscriptions'] scope=True grain=False agg=True
[15] RAW  -- Compute monthly churn rate for premium subscriptions for June 2026 (last full month before 2026-07-12) WITH subs AS ( SELECT user_id, pla
      -> tables=['fct_subscriptions'] scope=True grain=False agg=True
[16] RAW  -- Compute monthly churn rate for premium subscriptions for June 2026 (last full month) and June 2025? But user asked "right now" -> use mos
      -> PARSE FAILED
[17] GOV  SELECT plan, count(*) AS value FROM fct_subscriptions WHERE is_active GROUP BY plan ORDER BY plan
      -> tables=['fct_subscriptions'] scope=True grain=True agg=True
[18] GOV  SELECT date_trunc('month', signup_date)::date AS period, count(*) AS value FROM dim_users WHERE channel NOT IN ('partnerships') AND signup_d
      -> tables=['dim_users'] scope=True grain=True agg=True
[19] GOV  SELECT date_trunc('month', spend_date)::date AS period, sum(spend) AS value FROM fct_marketing_spend WHERE channel NOT IN ('partnerships') A
      -> tables=['fct_marketing_spend'] scope=True grain=True agg=True
[20] GOV  SELECT region, sum(moments) AS value FROM agg_active_days WHERE active_date >= DATE '2026-04-01' AND active_date <= DATE '2026-06-30' GROUP 
      -> tables=['agg_active_days'] scope=True grain=True agg=True
```

## Verdict

- **Raw-SQL usage is rung-dependent, not ~3%.** Pooled across all runs the agent wrote 294 raw statements; at the raw-warehouse rungs it is the norm and at governed rungs it is rare. Where it calls named metrics the grounding is declared and needs no parse.
- **The better parser closes both Catch-B holes.** CTE-aware entity kills the false-recovery (34%→~0); reading welded CASE scope lifts scope recovery to 81%. Recovery from real agent SQL is a parse — not an inference — for entity, measure and scope; grain/join are 'absent, not missed'.
- **The methodological lesson stands.** The naive 100% entity and WHERE-only scope hid a 34% confident mislabel and a 20% blind spot. Measuring the false-recovery rate is what exposed both and pointed at the fix.