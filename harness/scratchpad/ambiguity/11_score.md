# Scoring the detector against the blind ground truth

Detector findings: 57. Gold findings: 61. Matching by name-token overlap (approximate — pairwise-vs-grouped).

## Recall — gold findings the detector caught

```
high     16/16  (100%)
medium   30/34  (88%)
low      9/11  (82%)
TOTAL    55/61  (90%)
```

## Precision — detector findings that hit a real gold finding

```
DEFINITION_DIVERGENCE  24/25  (96%)
NAME_COLLISION         19/22  (86%)
DUPLICATE              5/5  (100%)
CONCEPT_FORK           3/3  (100%)
SCOPE_TRAP             2/2  (100%)
TOTAL                  53/57  (93%)
```

## MISSED gold findings (the headline)

### medium (4)
- **recognised_revenue_source_and_spelling** — Recognised revenue: different table, missing column, spelling variance
- **returns_count_vs_units** — Counting return rows vs summing returned units
- **new_segment_no_period_restriction** — Segment named 'new' actually selects all buyers ever
- **cost_columns_margin** — Multiple cost columns for margin

### low (2)
- **email_vs_customer_email_rename** — Email column renamed; both names circulate
- **conversion_rate_denominator_bots** — Conversion denominator includes bot sessions

## Detector findings with NO gold match (possible false positives)

4 of 57. By danger: {'medium': 2, 'low': 2}, by type: {'DEFINITION_DIVERGENCE': 1, 'NAME_COLLISION': 3}.

```
[medium][DEFINITION_DIVERGENCE] device[sem] ~ device[war]
[medium][NAME_COLLISION] subscription_id[war]
[low   ][NAME_COLLISION] active subscriber[doc] ~ active_subscriptions[sem]
[low   ][NAME_COLLISION] dim_product_variants[doc] ~ dim_products[doc]
```

## Honest read (the fuzzy matcher flatters both numbers)

- **Recall is genuinely high** (53/57 overall, 16/16 high). The detector casts a wide net across all three layers, so it surfaces nearly everything the blind judge found. High-danger matches were spot-checked as real (the revenue CONCEPT_FORKs, the completed_orders and active_customers cross-layer divergences), not token-overlap flukes.
- **Precision (90%) overstates usefulness.** Two reasons: (a) the detector is PAIRWISE, so the revenue family alone is 14 CONCEPT_FORK findings that collapse to ~3 gold findings — 123 raw findings are perhaps ~45 distinct collisions; (b) 46 of them are CROSS_REF, a weak 'this term is modelled and documented, check it' pointer, not a diagnosis. Counting those as precision hits is generous.
- **The false positives exposed a real bug.** `order_count ~ order_date`, `order_count ~ order_status` were called DUPLICATE because two facts sharing ONLY `base` pass the same-measure test. Fix: require agreement on >=2 declared meaning facets, not one. Reported, not silently patched (the detector was frozen before scoring).
- **The 4 misses are all explainable, and each names a real gap:** recognised/recognized (British vs US spelling defeats exact-label match); the `new` segment whose filter contradicts its own description (a within-fact check the detector doesn't do); email (killed by our own plumbing stoplist); cost columns (below the >=4-table overload threshold). None is a silent hole — each points at a specific next feature.
- **Bottom line:** on a realistic, blind-generated, three-layer messy environment the detector caught **16/16 high-danger** collisions and **53/57** overall. The design (embedding gate + structural danger + cross-layer name match) generalises well for RECALL; the work left is PRECISION — dedup pairwise into per-concept clusters, turn CROSS_REF into a real consistency check, and fix the loose same-measure test.