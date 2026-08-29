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
    s.final_status,
    s.was_refunded,
    s.mrr_amount
from {{ ref('stg_subscriptions') }} s
join {{ ref('int_date_spine') }} d
  on s.started_date <= d.date_day
 and (s.ended_date is null or s.ended_date > d.date_day)
