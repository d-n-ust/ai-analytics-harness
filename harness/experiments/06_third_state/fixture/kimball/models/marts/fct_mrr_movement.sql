-- One row per customer per month, with the change categorised. THE COMPANION TO THE SNAPSHOT.
--
-- The snapshot beside this holds the BALANCE and is semi-additive: read it, never sum it across
-- dates. This holds the CHANGE and is fully additive: new + expansion − churn − contraction is the
-- month's net movement, and those genuinely do add up across months and customers.
--
--   mrr(31 Jul) − mrr(30 Jun)  ==  sum of every movement in July
--
-- Two facts because MRR is asked about in two ways and only one of them is a balance. Putting both
-- in one table forces one aggregation rule onto measures that need opposite ones.
select
    date_month,
    customer_id,
    mrr,
    prior_mrr,
    mrr - prior_mrr                                as mrr_delta,
    case
        when prior_mrr = 0 and mrr > 0
             and date_month = min(case when mrr > 0 then date_month end)
                                over (partition by customer_id)      then 'new'
        when prior_mrr = 0 and mrr > 0                               then 'reactivation'
        when prior_mrr > 0 and mrr = 0                               then 'churn'
        when mrr > prior_mrr                                         then 'expansion'
        when mrr < prior_mrr                                         then 'contraction'
        else 'unchanged'
    end                                            as change_category
from {{ ref('int_customer_month_lag') }}
