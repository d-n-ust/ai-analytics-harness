select event_id as reminder_id, user_id, event_ts as reminded_ts, event_date as reminded_date, week
from {{ ref('stg_events') }} where event_type = 'reminder_click'
