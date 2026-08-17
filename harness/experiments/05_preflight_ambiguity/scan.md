```

  PREFLIGHT AMBIGUITY MAP          gate: embeddings
  ────────────────────────────────────────────────────────────
  small_before     1 confusion    (17 facts · 1 high 0 med 0 low)
  high_before     18 confusions   (63 facts · 7 high 2 med 9 low)
  ● high   ● medium   ● low

════ small_before ══════════════════════════════════════════

  SEMANTIC LAYER  · grounds additive · higher-level metrics
    ● H SCOPE_TRAP             real_value_moments  ~  value_moments

════ high_before ═══════════════════════════════════════════

  CROSS-LAYER  · a term grounded two ways, in two places
    ● L NAME_COLLISION         value moment  ~  value moment  ~  real_value_moments  ~  value_moments
    ● L NAME_COLLISION         active user  ~  active user  ~  active_users
    ● L NAME_COLLISION         revenue  ~  net_revenue

  DOCUMENTATION  · grounds grain · segments
    ● H DEFINITION_DIVERGENCE  active user  ~  active user
    ● H DEFINITION_DIVERGENCE  value moment  ~  value moment

  WAREHOUSE  · grounds entity · measure
    ● M NAME_COLLISION         user_id

  SEMANTIC LAYER  · grounds additive · higher-level metrics
    ● H GRAIN_MISMATCH         dau  ~  mau
    ● H SCOPE_TRAP             android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  total_moments  ~  value_moments  +1
    ● H SCOPE_TRAP             active_users  ~  actives  ~  engaged_users
    ● H SCOPE_TRAP             gross_revenue  ~  net_revenue
    ● H SCOPE_TRAP             new_signups  ~  new_users
    ● M GRAIN_MISMATCH         monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
    ● L DUPLICATE              total_moments  ~  value_moments
    ● L DUPLICATE              active_users  ~  monthly_active_users
    ● L DUPLICATE              net_revenue  ~  recurring_revenue
    ● L DUPLICATE              new_signups  ~  signups
    ● L NAME_COLLISION         monthly_recurring_revenue  ~  recurring_revenue
    ● L SIBLING                android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments

```
