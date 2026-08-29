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
-- BOTH DATES ARE CARRIED, and that is the point of the second one. A subscription term has more
-- than one date that a period filter could legitimately attach to, and "June MRR" means different
-- things depending on which: the balance on 30 June (2,420.56) or the revenue from terms that
-- STARTED in June (750.88). Kimball calls these role-playing dates.
--
-- Carrying only one date does not resolve that ambiguity, it hides it. The base warehouse carries
-- only `started_date` and can therefore express only the cohort reading; the first version of THIS
-- table carried only `snapshot_date` and could express only the balance. Each looks unambiguous
-- from inside, and each has silently answered a question nobody chose, in a YAML default nobody
-- reads. Carrying both makes the choice visible at query time, which is where it can be detected.
select
    snapshot_date,
    started_date,
    subscription_id,
    customer_id,
    billing_interval,
    final_status,
    was_refunded,
    mrr_amount
from {{ ref('int_subscription_days') }}
