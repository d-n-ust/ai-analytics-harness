```

  PREFLIGHT AMBIGUITY MAP          gate: lexical
  ────────────────────────────────────────────────────────────
  small_before     1 confusion    (18 facts · 1 high 0 med 0 low)
  small_after      0 confusions   (17 facts · 0 high 0 med 0 low)
  high_before     19 confusions   (68 facts · 8 high 2 med 9 low)
  high_after       0 confusions   (39 facts · 0 high 0 med 0 low)
  ● high   ● medium   ● low

════ small_before ══════════════════════════════════════════

  SEMANTIC LAYER  · grounds additive · higher-level metrics
    ● H SCOPE_TRAP             real_value_moments  ~  value_moments
        small_before/semantic.yml:65   real_value_moments:
        small_before/semantic.yml:35   value_moments:

════ high_before ═══════════════════════════════════════════

  CROSS-LAYER  · a term grounded two ways, in two places
    ● L NAME_COLLISION         value moment  ~  value_moments
        high_before/docs.md:15         ## value moment
        high_before/docs.md:19         ## value moment
        high_before/semantic.yml:15    value_moments:                                   # bare name — the trap
    ● L NAME_COLLISION         active user  ~  active_users
        high_before/docs.md:7          ## active user
        high_before/docs.md:11         ## active user
        high_before/semantic.yml:73    active_users:

  DOCUMENTATION  · grounds grain · segments
    ● H DEFINITION_DIVERGENCE  active user
        high_before/docs.md:7          ## active user
        high_before/docs.md:11         ## active user
    ● H DEFINITION_DIVERGENCE  value moment
        high_before/docs.md:15         ## value moment
        high_before/docs.md:19         ## value moment

  WAREHOUSE  · grounds entity · measure
    ● M NAME_COLLISION         moments
        high_before/warehouse.sql:19   moments INT,                  -- value moments ...
        high_before/warehouse.sql:29   moments INT,                 -- 'moments' overloaded: also in fct_events and fct_daily
        high_before/warehouse.sql:47   moments INT,                 -- 'moments' a THIRD time, different table
        high_before/warehouse.sql:55   moments INT                  -- 'moments' a FOURTH time: now overloaded across enough tables to flag

  SEMANTIC LAYER  · grounds additive · higher-level metrics
    ● H CONCEPT_FORK           monthly_recurring_revenue  ~  recurring_revenue
        high_before/semantic.yml:138   monthly_recurring_revenue:                       # DUPLICATE of mrr
        high_before/semantic.yml:131   recurring_revenue:                               # CONCEPT_FORK vs mrr (same base/agg, diff column)
    ● H GRAIN_MISMATCH         active_users  ~  dau  ~  mau  ~  monthly_active_users
        high_before/semantic.yml:73    active_users:
        high_before/semantic.yml:96    dau:                                             # GRAIN_MISMATCH vs mau: distinct count is semi-additive
        high_before/semantic.yml:105   mau:
        high_before/semantic.yml:88    monthly_active_users:                            # DUPLICATE of active_users
    ● H SCOPE_TRAP             android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  total_moments  ~  value_moments  +1
        high_before/semantic.yml:45    android_value_moments:
        high_before/semantic.yml:37    ios_value_moments:                               # SIBLING vs android (incomparable scopes)
        high_before/semantic.yml:62    monthly_value_moments:
        high_before/semantic.yml:22    real_value_moments:                              # SCOPE_TRAP vs value_moments (NOT is_internal)
        high_before/semantic.yml:30    total_moments:                                   # DUPLICATE of value_moments
        high_before/semantic.yml:15    value_moments:                                   # bare name — the trap
        high_before/semantic.yml:53    weekly_value_moments:                            # GRAIN_MISMATCH vs monthly (same measure, diff grain)
    ● H SCOPE_TRAP             active_users  ~  actives  ~  dau  ~  engaged_users  ~  mau  ~  monthly_active_users
        high_before/semantic.yml:73    active_users:
        high_before/semantic.yml:81    actives:                                         # SCOPE_TRAP vs active_users (drops NOT is_internal)
        high_before/semantic.yml:96    dau:                                             # GRAIN_MISMATCH vs mau: distinct count is semi-additive
        high_before/semantic.yml:114   engaged_users:                                   # NAME_COLLISION / concept vs active_users
        high_before/semantic.yml:105   mau:
        high_before/semantic.yml:88    monthly_active_users:                            # DUPLICATE of active_users
    ● H SCOPE_TRAP             gross_revenue  ~  net_revenue  ~  recurring_revenue
        high_before/semantic.yml:145   gross_revenue:                                   # SCOPE_TRAP / concept vs net_revenue
        high_before/semantic.yml:151   net_revenue:
        high_before/semantic.yml:131   recurring_revenue:                               # CONCEPT_FORK vs mrr (same base/agg, diff column)
    ● H SCOPE_TRAP             new_signups  ~  new_users  ~  signups
        high_before/semantic.yml:160   new_signups:
        high_before/semantic.yml:174   new_users:                                       # SCOPE_TRAP vs signups (NOT is_internal)
        high_before/semantic.yml:167   signups:                                         # DUPLICATE of new_signups
    ● M GRAIN_MISMATCH         monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
        high_before/semantic.yml:62    monthly_value_moments:
        high_before/semantic.yml:22    real_value_moments:                              # SCOPE_TRAP vs value_moments (NOT is_internal)
        high_before/semantic.yml:53    weekly_value_moments:                            # GRAIN_MISMATCH vs monthly (same measure, diff grain)
    ● L DUPLICATE              total_moments  ~  value_moments
        high_before/semantic.yml:30    total_moments:                                   # DUPLICATE of value_moments
        high_before/semantic.yml:15    value_moments:                                   # bare name — the trap
    ● L DUPLICATE              active_users  ~  monthly_active_users
        high_before/semantic.yml:73    active_users:
        high_before/semantic.yml:88    monthly_active_users:                            # DUPLICATE of active_users
    ● L DUPLICATE              monthly_recurring_revenue  ~  mrr
        high_before/semantic.yml:138   monthly_recurring_revenue:                       # DUPLICATE of mrr
        high_before/semantic.yml:124   mrr:
    ● L DUPLICATE              net_revenue  ~  recurring_revenue
        high_before/semantic.yml:151   net_revenue:
        high_before/semantic.yml:131   recurring_revenue:                               # CONCEPT_FORK vs mrr (same base/agg, diff column)
    ● L DUPLICATE              new_signups  ~  signups
        high_before/semantic.yml:160   new_signups:
        high_before/semantic.yml:167   signups:                                         # DUPLICATE of new_signups
    ● L DUPLICATE              paying_users  ~  subscribers
        high_before/semantic.yml:184   paying_users:
        high_before/semantic.yml:191   subscribers:                                     # DUPLICATE of paying_users
    ● L SIBLING                android_value_moments  ~  ios_value_moments  ~  monthly_value_moments  ~  real_value_moments  ~  weekly_value_moments
        high_before/semantic.yml:45    android_value_moments:
        high_before/semantic.yml:37    ios_value_moments:                               # SIBLING vs android (incomparable scopes)
        high_before/semantic.yml:62    monthly_value_moments:
        high_before/semantic.yml:22    real_value_moments:                              # SCOPE_TRAP vs value_moments (NOT is_internal)
        high_before/semantic.yml:53    weekly_value_moments:                            # GRAIN_MISMATCH vs monthly (same measure, diff grain)

```
