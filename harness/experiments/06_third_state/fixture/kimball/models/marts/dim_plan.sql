-- One row per billing interval. Small, and it exists so a fact carries a key rather than a string,
-- and so the vocabulary a question filters on has one definition.
select distinct
    billing_interval,
    case billing_interval when 'month' then 1 when 'year' then 12 end as months_per_term
from {{ ref('stg_subscriptions') }}
