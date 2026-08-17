# Preflight ambiguity counts per environment (all three grounding layers)

Gate: **embeddings**. Each env is scanned across semantic + warehouse + docs; the `layers` column of a finding shows which grounding layers it spans (sem/war/doc).

| environment | facts | high | medium | low | total |
|---|---|---|---|---|---|
| small_before | 17 | 1 | 0 | 0 | 1 |
| high_before | 63 | 7 | 2 | 9 | 18 |

## Findings


### small_before (1 findings)
```
[high   SCOPE_TRAP             sem        ] real_value_moments  ~  value_moments
```

### high_before (18 findings)
```
[high   DEFINITION_DIVERGENCE  doc        ] active user  ~  active user
[high   DEFINITION_DIVERGENCE  doc        ] value moment  ~  value moment
[high   GRAIN_MISMATCH         sem        ] dau  ~  mau
[high   SCOPE_TRAP             sem        ] android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  total_moments  ~  value_moments  ~  weekly_value_moments
[high   SCOPE_TRAP             sem        ] active_users  ~  actives  ~  engaged_users
[high   SCOPE_TRAP             sem        ] gross_revenue  ~  net_revenue
[high   SCOPE_TRAP             sem        ] new_signups  ~  new_users
[medium GRAIN_MISMATCH         sem        ] monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
[medium NAME_COLLISION         war        ] user_id
[low    DUPLICATE              sem        ] total_moments  ~  value_moments
[low    DUPLICATE              sem        ] active_users  ~  monthly_active_users
[low    DUPLICATE              sem        ] net_revenue  ~  recurring_revenue
[low    DUPLICATE              sem        ] new_signups  ~  signups
[low    NAME_COLLISION         doc+sem    ] value moment  ~  value moment  ~  real_value_moments  ~  value_moments
[low    NAME_COLLISION         doc+sem    ] active user  ~  active user  ~  active_users
[low    NAME_COLLISION         sem        ] monthly_recurring_revenue  ~  recurring_revenue
[low    NAME_COLLISION         doc+sem    ] revenue  ~  net_revenue
[low    SIBLING                sem        ] android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
```
