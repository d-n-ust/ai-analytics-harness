-- The conformed date dimension. Every fact joins it; nothing computes calendar arithmetic twice.
--
-- Kimball's first rule for a star: one date dimension, shared. Without it each fact invents its
-- own notion of a month boundary and two of them eventually disagree. It is also what makes a
-- periodic snapshot expressible at all — a snapshot needs a row for every date, including dates on
-- which nothing happened, and only a date dimension has those.
select
    d                                                    as date_day,
    cast(date_trunc('week',    d) as date)               as week_start,
    cast(date_trunc('month',   d) as date)               as month_start,
    cast(date_trunc('quarter', d) as date)               as quarter_start,
    cast(date_trunc('year',    d) as date)               as year_start,
    last_day(d)                                          as month_end,
    d = last_day(d)                                      as is_month_end
from (
    select unnest(generate_series(DATE '2025-09-01', DATE '2026-07-12', INTERVAL 1 DAY))::date as d
)
