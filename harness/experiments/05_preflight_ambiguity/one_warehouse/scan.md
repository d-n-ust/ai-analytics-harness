```

  ONE WAREHOUSE — STATIC SCAN        gate: embeddings
  --------------------------------------------------------------
  before   11 findings   (70 definitions · 4 high 3 med 4 low)
  after     0 findings   (45 definitions · 0 high 0 med 0 low)

==== before ==================================================
  H FACT_TWIN          paying_users  ~  subscribers
  H SCOPE_TRAP         active_users  ~  actives  ~  dau  ~  engaged_users  ~  mau  ~  monthly_active_users
  H SCOPE_TRAP         real_value_moments  ~  total_moments  ~  value_moments
  H SCOPE_TRAP         new_signups  ~  new_users
  M FACT_TWIN          active_habits  ~  total_habits
  M VERSIONED_TWIN     dim_users  ~  dim_users_v2
  M VERSIONED_TWIN     fct_subscriptions  ~  fct_subscriptions_2026_03
  L DUPLICATE          actives  ~  dau  ~  engaged_users  ~  mau  ~  monthly_active_users
  L DUPLICATE          total_moments  ~  value_moments
  L DUPLICATE          monthly_recurring_revenue  ~  mrr
  L NAME_COLLISION     monthly_recurring_revenue  ~  recurring_revenue

==== after ==================================================
  (no findings)

```
