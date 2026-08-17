# Habit-tracking data dictionary

One governed definition per term — the after-fix of high_before's dictionary, where several terms
were defined more than once and not the same way twice. Each term below has a single meaning that
matches the governed metric and the warehouse column it grounds.

## active users
A user with at least one value moment in the period, excluding internal and test accounts. This is
the definition Finance, the North Star tree, and the governed `active_users` metric all use:
user-distinct and segment-restricted.

## value moments
A completed habit — the canonical activity event, counted from the `moments` column, one row per
completion. Raw volume counts every account; the governed `value_moments` metric exposes WHO counts
as an argument (segment=all or segment=active), so scope is a query choice, not a second definition.

## revenue
Subscription revenue, taken as billed amount from `fct_subscriptions.billed_amount`. Figures net of
refunds are a derived metric computed from this column, not a competing definition of the word.

## grain
Daily metrics are reported per `active_date` — the single grain column across the warehouse. Older
`event_date` / `day` extracts were consolidated into it.

## is_internal
The single flag that excludes internal and test accounts from user metrics. There is no separate
`is_test` flag: an account that should be excluded is flagged `is_internal`.
