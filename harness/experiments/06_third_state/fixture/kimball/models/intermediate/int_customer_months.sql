-- One row per customer per month between their first and last activity, WITH GAPS FILLED.
--
-- A month in which a customer paid nothing is a row with zero, not a missing row. Churn and
-- reactivation are defined by the transition between months, so the month that is absent is exactly
-- the one the logic needs to see. This is the dbt MRR playbook's spine, at month grain.
with active as (
    select customer_id,
           cast(date_trunc('month', snapshot_date) as date)          as date_month,
           sum(mrr_amount) filter (where snapshot_date = last_day(snapshot_date)
                                     and not was_refunded)           as mrr
    from {{ ref('int_subscription_days') }}
    group by 1, 2
),
bounds as (
    select customer_id, min(date_month) as first_month, max(date_month) as last_month
    from active where mrr > 0 group by 1
),
spine as (
    select b.customer_id, m.date_month
    from bounds b
    join (select distinct cast(date_trunc('month', date_day) as date) as date_month
          from {{ ref('int_date_spine') }}) m
      on m.date_month between b.first_month and b.last_month
)
select
    spine.customer_id,
    spine.date_month,
    coalesce(active.mrr, 0)                        as mrr
from spine
left join active
       on active.customer_id = spine.customer_id
      and active.date_month  = spine.date_month
