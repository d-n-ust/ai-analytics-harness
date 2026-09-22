select hid as habit_id, uid as user_id, nm as habit_name, cat as category,
       cast(created as date) as created_date, cast(arch as date) as archived_date,
       arch is not null as is_archived
from {{ source('raw', 'hab') }}
