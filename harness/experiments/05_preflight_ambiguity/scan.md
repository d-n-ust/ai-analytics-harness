# Preflight ambiguity counts per environment

Gate: **embeddings**. Findings are confusable metric pairs/clusters preflight flags.

| environment | metrics | high | medium | low | total |
|---|---|---|---|---|---|
| small_before | 17 | 1 | 0 | 0 | 1 |
| high_before | 25 | 5 | 1 | 6 | 12 |

## Findings


### small_before (1 findings)
```
[high   SCOPE_TRAP] real_value_moments  ~  value_moments
```

### high_before (12 findings)
```
[high   GRAIN_MISMATCH] dau  ~  mau
[high   SCOPE_TRAP] android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  total_moments  ~  value_moments  ~  weekly_value_moments
[high   SCOPE_TRAP] active_users  ~  actives  ~  engaged_users
[high   SCOPE_TRAP] gross_revenue  ~  net_revenue
[high   SCOPE_TRAP] new_signups  ~  new_users
[medium GRAIN_MISMATCH] monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
[low    DUPLICATE] total_moments  ~  value_moments
[low    DUPLICATE] active_users  ~  monthly_active_users
[low    DUPLICATE] net_revenue  ~  recurring_revenue
[low    DUPLICATE] new_signups  ~  signups
[low    NAME_COLLISION] monthly_recurring_revenue  ~  recurring_revenue
[low    SIBLING] android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
```
