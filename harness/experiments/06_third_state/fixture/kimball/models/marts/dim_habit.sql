-- One row per habit. The thing a completion points at.
select habit_id, customer_id, habit_name, category, created_date, archived_date, is_archived
from {{ ref('stg_habits') }}
