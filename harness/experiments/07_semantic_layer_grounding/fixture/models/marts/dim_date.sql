-- The conformed calendar. It is wider than the data, so that a question about a period with no data
-- is placed on the calendar and then refused for coverage, rather than not found. It runs from
-- 1 December 2024 to 28 February 2027 so that every season it holds is whole.
--
-- `season` and `season_year` are meteorological seasons for the northern hemisphere (Analytics,
-- provisional): spring is March to May, summer June to August, autumn September to November, winter
-- December to February. A winter is named by the year of its January, so winter 2026 is December 2025
-- to February 2026.
select d as date_day,
       cast(date_trunc('week',    d) as date) as week_start,
       cast(date_trunc('month',   d) as date) as month_start,
       cast(date_trunc('quarter', d) as date) as quarter_start,
       extract(year from d)                   as year,
       (extract(quarter from d))              as quarter_of_year,
       last_day(d) = d                        as is_month_end,
       case when extract(month from d) in (3, 4, 5)  then 'spring'
            when extract(month from d) in (6, 7, 8)  then 'summer'
            when extract(month from d) in (9, 10, 11) then 'autumn'
            else 'winter' end                 as season,
       extract(year from d) + case when extract(month from d) = 12 then 1 else 0 end as season_year
from (select unnest(generate_series(DATE '2024-12-01', DATE '2027-02-28', INTERVAL 1 DAY))::date as d)
