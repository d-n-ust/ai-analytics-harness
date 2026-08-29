-- TRANSACTION FACT. One row per app open.
select
    event_id                                       as app_open_id,
    user_id                                        as customer_id,
    event_ts                                       as opened_ts,
    event_date                                     as opened_date,
    week,
    source                                         as recorded_by
from {{ ref('stg_events') }}
where event_type = 'app_open'
