-- The conformed channel dimension, shared by the marketing-spend fact and the account dimension so
-- "spend by channel" and "signups by channel" mean the same channel. Built from the channels that
-- actually appear in either place.
with c as (
    select channel from {{ ref('stg_users') }}
    union
    select channel from {{ ref('stg_marketing_spend') }}
)
select distinct channel,
       channel in ('paid_search')                    as is_paid,
       channel = 'partnerships'                       as is_test_integration,
       channel not in ('partnerships')                as is_real_acquisition
from c where channel is not null
