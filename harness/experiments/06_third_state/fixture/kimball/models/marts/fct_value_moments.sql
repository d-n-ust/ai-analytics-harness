-- TRANSACTION FACT. One row per completed habit, at the moment it happened.
--
-- Additive in every direction, unlike the subscription snapshot beside it: two days of completions
-- genuinely add to two days of completions. That is why it is a transaction fact and the balance
-- is a snapshot — the grain follows from what the measure admits, not from convenience.
select
    event_id                                       as value_moment_id,
    user_id                                        as customer_id,
    habit_id,
    event_ts                                       as completed_ts,
    event_date                                     as completed_date,
    week,
    source                                         as recorded_by
from {{ ref('stg_events') }}
where event_type = 'value_moment'
