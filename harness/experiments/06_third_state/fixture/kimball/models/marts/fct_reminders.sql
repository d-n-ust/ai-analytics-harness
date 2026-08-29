-- TRANSACTION FACT. One row per reminder the product sent and the customer clicked.
select
    event_id                                       as reminder_id,
    user_id                                        as customer_id,
    event_ts                                       as reminded_ts,
    event_date                                     as reminded_date,
    week
from {{ ref('stg_events') }}
where event_type = 'reminder_click'
