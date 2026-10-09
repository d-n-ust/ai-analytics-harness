-- One row per account per day on which it did anything at all.
--
-- `is_internal` is denormalised onto the fact so that a metric can scope on it without a join.
-- That is a convenience and it is also how the two definitions of "active user" downstream came to
-- differ: the column is right there, so filtering it is a choice each metric makes on its own, and
-- nothing forces the two to agree. The platform and country attributes are carried the same way, so
-- the semantic layer can filter and group by them as dimensions of the activity.
select
    e.user_id,
    e.event_date                                                     as active_date,
    e.week,
    count(*) filter (where e.event_type = 'value_moment')            as value_moments,
    count(*) filter (where e.event_type = 'app_open')                as app_opens,
    u.is_internal,
    u.region,
    u.country,
    c.country_name,
    u.platform,
    p.device_type,
    u.channel
from {{ ref('stg_events') }} e
join {{ ref('dim_users') }} u using (user_id)
left join {{ ref('dim_country') }} c on c.country = u.country
left join {{ ref('dim_platform') }} p on p.platform = u.platform
group by 1, 2, 3, 6, 7, 8, 9, 10, 11, 12
