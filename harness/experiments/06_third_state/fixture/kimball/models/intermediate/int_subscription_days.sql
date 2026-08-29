-- One row per subscription per day it was live. The interval test lives here, once.
--
-- Live means started on or before the day and not yet ended. A term that later cancelled WAS live
-- before it ended and counts on those days — which is the whole reason this exists rather than a
-- filter on the term's final status.
select
    d.date_day                                     as snapshot_date,
    s.subscription_id,
    s.customer_id,
    s.billing_interval,
    s.started_date,
    -- COHORT MONTH, as a plain string, and it is here because declaring a second time role is not
    -- the same as making it queryable. `period` binds to the agg_time_dimension (`snapshot_date`),
    -- and it is the only way this interface can express a date RANGE — `filters` takes equality
    -- pairs. So "started in June" had no expression at all: filtering `started_date = 2026-06-01`
    -- matches terms that began on the first of the month and nothing else, which is how a question
    -- whose answer is 105 came back as 4.
    --
    -- A cohort attribute turns that range into an equality, which is what a snapshot fact carries
    -- one for. Standard practice, and here it is what makes the second time role reachable.
    strftime(s.started_date, '%Y-%m')              as cohort_month,
    s.final_status,
    s.was_refunded,
    s.mrr_amount
from {{ ref('stg_subscriptions') }} s
join {{ ref('int_date_spine') }} d
  on s.started_date <= d.date_day
 and (s.ended_date is null or s.ended_date > d.date_day)
