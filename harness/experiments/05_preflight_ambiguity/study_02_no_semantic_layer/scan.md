```

  STUDY-02 STATIC SCAN            gate: lexical
  ------------------------------------------------------------
  s2_before     2 confusions   (0 high 2 med 0 low)
  s2_after      0 confusions   (0 high 0 med 0 low)

==== s2_before ==============================================
  M VERSIONED_TWIN         subscriptions  ~  subscriptions_2026_03
      'subscriptions_2026_03' reads as a versioned or leftover twin of 'subscriptions' — nothing marks which one is current
  M VERSIONED_TWIN         users  ~  users_v2
      'users_v2' reads as a versioned or leftover twin of 'users' — nothing marks which one is current

==== s2_after ==============================================
  (no findings)

```
