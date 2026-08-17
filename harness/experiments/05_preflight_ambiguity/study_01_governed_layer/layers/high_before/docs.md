# Habit-tracking data dictionary

The place a pressured team documents GRAIN and SEGMENTS (per the repair matrix: these ground in
docs, not in the tables). Written by different people at different times, so several terms are
defined more than once, and not the same way twice.

## active user
A user with at least one value moment in the period, excluding internal and test accounts. This is
the definition Finance and the North Star tree use; it is user-distinct and segment-restricted.

## active user
A user who opened the app on a given day. Session-based, counted from front-end telemetry, and it
includes every account — internal and test as well. Growth dashboards use this one.

## value moment
A completed habit. The canonical activity event; counted from the `moments` column and excludes
nothing. One row per completion.

## value moment
An engagement event of any kind — a reminder open, a streak view, a completion. Counted from
`completed_habits`, which is broader than completions alone.

## revenue
Subscription revenue. Usually taken as billed amount, though some reports net out refunds and
inactive subscriptions first, so the number depends on who ran it.

## grain
Daily metrics are reported per `active_date`. Note that older extracts key on `event_date`, and the
`fct_daily` rollup uses `day`; these are the same calendar day but different column names, and a join
that assumes one will silently miss the others.

## is_internal
The flag that excludes internal/test accounts from user metrics. Note: `dim_users` carries both
`is_internal` and `is_test`; the governed metrics filter on `is_internal` only, so an account flagged
`is_test` but not `is_internal` is still counted.
