-- The spine plus the previous month's value, so a month-over-month comparison is a subtraction
-- rather than a self-join. One extra month is appended per customer so the month AFTER their last
-- active one exists and churn has somewhere to land.
with padded as (
    select customer_id, date_month, mrr from {{ ref('int_customer_months') }}
    union all
    select customer_id, cast(last_month + INTERVAL 1 MONTH as date), 0
    from (select customer_id, max(date_month) as last_month
          from {{ ref('int_customer_months') }} group by 1)
)
select
    customer_id,
    date_month,
    mrr,
    coalesce(lag(mrr) over (partition by customer_id order by date_month), 0) as prior_mrr
from padded
