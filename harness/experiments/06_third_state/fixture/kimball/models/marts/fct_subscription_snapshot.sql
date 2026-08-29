-- PERIODIC SNAPSHOT. One row per subscription per day on which it was live.
--
-- MRR is a BALANCE — a level that exists at an instant — and Kimball's rule for a balance is that
-- it belongs in a periodic snapshot and is SEMI-ADDITIVE: summable across customers and plans on
-- one date, never summable across dates.
--
-- The base warehouse models it as a transaction sum over `started_date`, and three things follow,
-- all measured before this table was written:
--
--   "MRR as at 2026-03-31" cannot be expressed at all. The nearest the layer will answer is
--   322.36, the terms that STARTED that month, against a true balance of 1,110.24.
--   Asking for a period silently swaps a stock reading for a cohort one, 3.4x apart, with no
--   error anywhere: the metric exists, the period is inside coverage, every guardrail passes.
--   And the twelve monthly figures sum to exactly the current balance, because they are cohorts
--   of it — so a reader who sums them gets a number that reconciles and means something else.
--
-- Live on a date means started on or before it and not yet ended. A term that was later cancelled
-- WAS live before it ended and counts on those days, which is the whole reason a snapshot exists
-- rather than a filter on current status.
select
    d.date_day                                           as snapshot_date,
    s.subscription_id,
    s.user_id,
    s.plan,
    s.final_status,
    s.was_refunded,
    s.mrr_amount
from {{ ref('dim_subscriptions') }} s
join {{ ref('dim_date') }} d
  on s.started_date <= d.date_day
 and (s.ended_date is null or s.ended_date > d.date_day)
