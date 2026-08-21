# Combined pipeline on the real 17-metric layer

Gate ≥ 0.4 (MiniLM, name-only). Scope = segment (≠all) + default_filters. 17 metrics, 17 pairs cleared the embedding gate.

## Pipeline SCOPE TRAPs (the danger class)

```
real_value_moments ~ value_moments   cos 0.904  -> clarify
    same measure; 'real_value_moments' is 'value_moments' plus a filter -> a bare question is silently scoped, numbers differ, swap is invisible
```
Test-1 cross-check: `value_moments` mislabel rate was **29.8%** (the highest answerable metric), so the one pair the pipeline flags is the one that actually caused the errors.

## Every gated pair, by class

```
a                      b                        cos  tok class            action
real_value_moments     value_moments          0.904   ok SCOPE TRAP (high) clarify
moments_per_day        value_moments          0.622   ok safe             answer
active_subscriptions   active_users           0.619   ok safe             answer
moments_per_day        real_value_moments     0.612   ok safe             answer
reminder_open_rate     reminders_shown        0.558 MISS safe             answer
active_users           power_users            0.532   ok safe             answer
active_users           paying_users           0.490   ok safe             answer
active_subscriptions   paying_users           0.490 MISS safe             answer
days_per_user          paying_users           0.475 MISS safe             answer
days_per_user          moments_per_day        0.464 MISS safe             answer
active_users           days_per_user          0.463 MISS safe             answer
paying_users           power_users            0.447   ok safe             answer
active_habits          active_users           0.433   ok safe             answer
active_users           new_signups            0.425 MISS safe             answer
active_subscriptions   new_signups            0.425 MISS safe             answer
days_per_user          power_users            0.403 MISS safe             answer
active_habits          active_subscriptions   0.401   ok safe             answer
```

## What the embedding gate added (token gate would MISS these)

```
reminder_open_rate ~ reminders_shown   cos 0.558  -> safe (answer)
active_subscriptions ~ paying_users   cos 0.490  -> safe (answer)
days_per_user ~ paying_users   cos 0.475  -> safe (answer)
days_per_user ~ moments_per_day   cos 0.464  -> safe (answer)
active_users ~ days_per_user   cos 0.463  -> safe (answer)
active_users ~ new_signups   cos 0.425  -> safe (answer)
active_subscriptions ~ new_signups   cos 0.425  -> safe (answer)
days_per_user ~ power_users   cos 0.403  -> safe (answer)
```
These are the recall win. Note every one is correctly **safe** (different measure) — embeddings widen the net, the structural stage keeps precision.

## Versus the original classifier

- Original `scope_only` (high) pairs: **2** — real_value_moments ~ value_moments, weekly_value_moments (tree node -> real_value_moments) ~ value_moments.
- Pipeline SCOPE TRAPs: **1** — real_value_moments ~ value_moments.
- They agree on the one real collision. The original also flags the **tree node** `weekly_value_moments -> real_value_moments ~ value_moments`; this prototype compares named metrics only, so it does not yet cover tree nodes.

## Honest limits, on this layer

- **Unnamed / welded scope not covered.** `new_signups` (the Test-1 `referral_signups` case, 18.8% mislabels) has no named scoped sibling, so no pair exists to flag. Catching it needs the (metric x scope-choice) enumeration — the next build, not this one.
- **Tree nodes not covered** (see above).
- **Subsumption is syntactic.** `segment=all` is treated as the widest scope and the empty filter set; real semantic subsumption (overlapping filters) is not modelled.