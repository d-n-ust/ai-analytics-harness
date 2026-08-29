-- One row per subscription TERM: the thing that exists, with its own attributes and lifespan.
--
-- Split out from the fact because a term is an entity, not an event. The snapshot fact beside this
-- carries one row per term per day it was live and holds only the measure; everything descriptive
-- lives here and is joined. That is what lets `plan` be filtered without deciding, in the fact,
-- which day's value of it is the right one.
--
-- `final_status` is named for what it is. The source records how a term ENDED, not what it was on
-- any given day, so no history of status exists and the snapshot cannot pretend otherwise. It is
-- enough for the two revenue definitions, which differ on whether a term later refunded should
-- ever have counted.
select
    subscription_id,
    user_id,
    plan,
    started_date,
    ended_date,
    status                                               as final_status,
    status = 'refunded'                                  as was_refunded,
    -- The measure at the grain it will be aggregated at. The base warehouse leaves the yearly
    -- lump in the fact and divides by twelve inside the metric expression, which puts business
    -- logic in the semantic layer where two metrics can spell it differently.
    case when plan = 'annual' then billed_amount / 12.0 else billed_amount end as mrr_amount
from {{ ref('stg_subscriptions') }}
