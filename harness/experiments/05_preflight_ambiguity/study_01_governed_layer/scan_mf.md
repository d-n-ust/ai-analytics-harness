```

  METRICFLOW LAYER SCAN            gate: lexical
  ------------------------------------------------------------
  small_before    1 findings   (8 facts · 1 high 0 med 0 low)
  small_after     0 findings   (7 facts · 0 high 0 med 0 low)
  high_before     7 findings   (19 facts · 3 high 0 med 4 low)
  high_after      0 findings   (7 facts · 0 high 0 med 0 low)

==== small_before ==============================================
  H SCOPE_TRAP             real_value_moments  ~  value_moments

==== small_after ==============================================
  (no findings)

==== high_before ==============================================
  H SCOPE_TRAP             active_users  ~  actives  ~  dau  ~  engaged_users  ~  mau  ~  monthly_active_users
  H SCOPE_TRAP             real_value_moments  ~  total_moments  ~  value_moments
  H SCOPE_TRAP             new_signups  ~  new_users
  L DUPLICATE              actives  ~  dau  ~  engaged_users  ~  mau  ~  monthly_active_users
  L DUPLICATE              total_moments  ~  value_moments
  L DUPLICATE              monthly_recurring_revenue  ~  mrr
  L DUPLICATE              paying_users  ~  subscribers

==== high_after ==============================================
  (no findings)

```
