select event_id as value_moment_id, user_id, habit_id, event_ts as completed_ts,
       event_date as completed_date, week, source as recorded_by
from {{ ref('stg_events') }} where event_type = 'value_moment'
