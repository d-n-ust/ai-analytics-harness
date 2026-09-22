select d as date_day,
       cast(date_trunc('week',    d) as date) as week_start,
       cast(date_trunc('month',   d) as date) as month_start,
       cast(date_trunc('quarter', d) as date) as quarter_start,
       extract(year from d)                   as year,
       (extract(quarter from d))              as quarter_of_year,
       last_day(d) = d                        as is_month_end
from (select unnest(generate_series(DATE '2025-09-01', DATE '2026-07-12', INTERVAL 1 DAY))::date as d)
