# T3 — primitive recovery from the agent's actual emitted SQL

Run `20260726-223032-gpt-5-mini.raw.jsonl.gz`. Governed `query_metric` calls carry the grounding in the metric NAME (no parse needed); `run_sql` is where the agent wrote its own SQL and recovery must parse it.

```
governed calls (resolution DECLARED, no parse) .. 1215
raw agent statements (the parse target) ......... 40  (39 parsed by sqlglot, 98%)

recovery on the RAW agent SQL:
  entity (real source table) ....   100%  (38% of statements are CTE-based)
  segment (WHERE) recovered .....    85%   <- the one that matters
  grain (GROUP BY) recovered ....    54%
  measure (aggregate) recovered .    95%
  join path recovered ...........    33%
  segment WELDED inside aggregate    26%   <- the blind spot

FALSE-RECOVERY RATE (entity): 38%  <- statements where a naive `find_all(Table)` reports a CTE alias AS a source table (confident mislabel). The 100% above already excludes CTE names; without that correction it reads a misleading 100%.

sanity — compiler-emitted (governed) SQL is clean and recoverable:
  parsed 1215/1215; entity 100%, segment 99%, grain 65%, measure 100%
```

## Hand-check sample (20 statements + parser output)

Each shows the SQL and what the parser recovered; the false-recovery rate is the share where the parser confidently returned a WRONG primitive (verified by reading each).

```
[ 1] RAW  -- Calculate monthly churn rate for premium subscriptions for the most recent complete month (data complete through 2026-07-12). We need last full mon
      -> tables=['fct_subscriptions', 'fct_subscriptions'] where=True group=False agg=True welded=False
[ 2] RAW  -- Compute monthly churn rate for premium (governed segment 'premium' maps to plan like 'premium'?)
-- Check distinct plan values
select distinct plan
      -> tables=['fct_subscriptions'] where=False group=False agg=False welded=False
[ 3] RAW  -- Compute monthly churn rate for premium subscriptions for June 2026 (last full month) and June 2025? But user asked "right now" -> use most recent f
      -> PARSE FAILED
[ 4] RAW  -- Compute monthly churn rate for premium: churn = cancellations in month / paying_users at start of month
WITH subs AS (
  SELECT subscription_id, us
      -> tables=['fct_subscriptions', 'fct_subscriptions', 'fct_subscriptions'] where=True group=False agg=True welded=False
[ 5] RAW  -- Find users who canceled (subscription ended) and their last active week before cancel. Define churned as subscription with ended_date not null and 
      -> tables=['fct_subscriptions', 'fct_value_moments', 'fct_reminders'] where=True group=True agg=True welded=True
[ 6] RAW  -- compute MRR before and after March price bump
-- assume price bump rolled out March 1, compare MRR on Feb 28 vs Mar 31? User asked "rolled out in M
      -> tables=['fct_subscription_snapshots'] where=True group=True agg=True welded=True
[ 7] RAW  -- compute weekly MRR by taking mrr from subscriptions table snapshot by week
WITH weeks AS (
  SELECT date_trunc('week', day)::date AS week_start
  F
      -> tables=['subscriptions'] where=False group=True agg=True welded=False
[ 8] RAW  SELECT
  DATE_TRUNC('month', started_at) AS month,
  SUM(CASE WHEN plan = 'annual' THEN billed_amount/12.0 ELSE billed_amount END) AS mrr
FROM fct_sub
      -> tables=['fct_subscriptions'] where=True group=True agg=True welded=True
[ 9] RAW  SELECT
  DATE_TRUNC('month', started_date) AS month,
  SUM(CASE WHEN plan = 'annual' THEN billed_amount/12.0 ELSE billed_amount END) AS mrr
FROM fct_s
      -> tables=['fct_subscriptions'] where=True group=True agg=True welded=True
[10] RAW  SELECT  -- compute DAU/MAU for last_week using average daily active / monthly active users (last_month)
  (SELECT avg(value)::numeric FROM (
    SELEC
      -> tables=['agg_active_days', 'agg_active_days'] where=True group=True agg=True welded=False
[11] RAW  SELECT COUNT(*) AS total_habits FROM dim_habits;
      -> tables=['dim_habits'] where=False group=False agg=True welded=False
[12] RAW  SELECT COUNT(*) AS total_signups
FROM dim_users u
WHERE u.is_internal = false
  AND u.signup_date BETWEEN DATE '2026-06-01' AND DATE '2026-06-30';
      -> tables=['dim_users'] where=True group=False agg=True welded=False
[13] RAW  SELECT COUNT(DISTINCT u.user_id) AS users_signed_and_activated
FROM dim_users u
JOIN fct_value_moments v
  ON u.user_id = v.user_id
WHERE u.is_interna
      -> tables=['dim_users', 'fct_value_moments'] where=True group=False agg=True welded=False
[14] RAW  SELECT DISTINCT platform FROM agg_active_days ORDER BY platform;
      -> tables=['agg_active_days'] where=False group=False agg=False welded=False
[15] RAW  SELECT SUM(ROUND(signups*activation_rate)) AS activated_total FROM (SELECT w.signups, a.activation_rate FROM (SELECT date_trunc('week', signup_date)::
      -> tables=['dim_users', 'agg_user_activation'] where=True group=True agg=True welded=True
[16] GOV  SELECT plan, count(*) AS value FROM fct_subscriptions WHERE is_active GROUP BY plan ORDER BY plan
      -> tables=['fct_subscriptions'] where=True group=True agg=True welded=False
[17] GOV  SELECT date_trunc('month', signup_date)::date AS period, count(*) AS value FROM dim_users WHERE channel NOT IN ('partnerships') AND signup_date >= DAT
      -> tables=['dim_users'] where=True group=True agg=True welded=False
[18] GOV  SELECT date_trunc('month', spend_date)::date AS period, sum(spend) AS value FROM fct_marketing_spend WHERE channel NOT IN ('partnerships') AND spend_d
      -> tables=['fct_marketing_spend'] where=True group=True agg=True welded=False
[19] GOV  SELECT region, sum(moments) AS value FROM agg_active_days WHERE active_date >= DATE '2026-04-01' AND active_date <= DATE '2026-06-30' GROUP BY region 
      -> tables=['agg_active_days'] where=True group=True agg=True welded=False
[20] GOV  SELECT date_trunc('month', signup_date)::date AS period, count(*) AS value FROM dim_users WHERE signup_date >= DATE '2026-06-01' AND signup_date <= DA
      -> tables=['dim_users'] where=True group=True agg=True welded=False
```

## Verdict

- **Most groundings never need a parse.** 1215 of 1255 SQL statements come from governed `query_metric` calls where the grounding is the metric name (resolution DECLARED). Traversal weighting works trivially there.
- **On the agent's own raw SQL, recovery is mostly a parse, with two holes.** Entity and measure recover ~100%/95%, segment (WHERE) 85%, grain 54%, joins 33%.
- **Kill condition partially met.** 26% of raw statements weld the segment inside an aggregate (`sum(case when …)` / the power_users shape); a WHERE-clause parse cannot see that scope. Material, not routine — but real.
- **Rate-only reporting would have lied.** Naive entity recovery reads 100%, but the false-recovery rate is 38%: on CTE-based statements (38% of them) a naive `find_all(Table)` reports a CTE alias as the source table. Reporting a false-recovery rate alongside the recovery rate, as the doc demanded, was the load-bearing check.
- **Three recovery failures, with the reason:** (1) 1/40 statements fail to parse (multiple statements / trailing comment in one `run_sql`); (2) welded-segment statements parse fine but the scope is invisible to a WHERE reader; (3) CTE statements mislabel the entity unless CTE names are excluded first.