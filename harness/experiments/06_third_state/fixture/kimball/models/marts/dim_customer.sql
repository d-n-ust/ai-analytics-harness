-- One row per customer. The attributes a subscription fact should join to rather than carry.
select
    user_id                                        as customer_id,
    signup_date,
    channel,
    country,
    region,
    platform,
    is_internal
from {{ ref('stg_users') }}
