select u.*, c.region
from {{ ref('stg_users') }} u
left join {{ ref('dim_country') }} c using (country)
