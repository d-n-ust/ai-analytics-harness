select habit_id, user_id, habit_name, category, created_date, archived_date, is_archived
from {{ ref('stg_habits') }}
