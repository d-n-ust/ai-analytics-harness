-- One row per calendar day. Everything that needs a row for a day on which nothing happened joins
-- to this: a balance needs one, and so does a customer's inactive month.
select unnest(generate_series(DATE '2025-09-01', DATE '2026-07-12', INTERVAL 1 DAY))::date as date_day
