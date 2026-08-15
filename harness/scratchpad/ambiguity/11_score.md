# Scoring the detector against the blind ground truth

Detector findings: 123. Gold findings: 61. Matching by name-token overlap (approximate — pairwise-vs-grouped).

## Recall — gold findings the detector caught

```
high     16/16  (100%)
medium   31/34  (91%)
low      10/11  (91%)
TOTAL    57/61  (93%)
```

## Precision — detector findings that hit a real gold finding

```
CROSS_REF              45/46  (98%)
NAME_COLLISION         30/35  (86%)
DUPLICATE              11/15  (73%)
CONCEPT_FORK           14/14  (100%)
SCOPE_TRAP             4/6  (67%)
DEFINITION_DIVERGENCE  5/5  (100%)
SIBLING                2/2  (100%)
TOTAL                  111/123  (90%)
```

## MISSED gold findings (the headline)

### medium (3)
- **recognised_revenue_source_and_spelling** — Recognised revenue: different table, missing column, spelling variance
- **new_segment_no_period_restriction** — Segment named 'new' actually selects all buyers ever
- **cost_columns_margin** — Multiple cost columns for margin

### low (1)
- **email_vs_customer_email_rename** — Email column renamed; both names circulate

## Detector findings with NO gold match (possible false positives)

12 of 123. By danger: {'high': 2, 'medium': 5, 'low': 5}, by type: {'SCOPE_TRAP': 2, 'DUPLICATE': 4, 'NAME_COLLISION': 5, 'CROSS_REF': 1}.

```
[high  ][SCOPE_TRAP] completed_orders[sem] ~ order_total[doc]
[high  ][SCOPE_TRAP] paying_customers[sem] ~ paying[sem]
[medium][DUPLICATE] order_count[sem] ~ order_date[sem]
[medium][DUPLICATE] order_count[sem] ~ order_status[sem]
[medium][DUPLICATE] order_date[sem] ~ order_status[sem]
[medium][DUPLICATE] order_date[sem] ~ order_total[doc]
[medium][NAME_COLLISION] subscription_id[war]
[low   ][CROSS_REF] device[sem] ~ device[war]
[low   ][NAME_COLLISION] active_subscriptions[sem] ~ active subscriber[doc]
[low   ][NAME_COLLISION] discount_amount[sem] ~ discount_rate[sem]
[low   ][NAME_COLLISION] discount_rate[sem] ~ discount_amount[doc]
[low   ][NAME_COLLISION] dim_products[doc] ~ dim_product_variants[doc]
```

## Honest read (the fuzzy matcher flatters both numbers)

- **Recall is genuinely high** (111/123 overall, 16/16 high). The detector casts a wide net across all three layers, so it surfaces nearly everything the blind judge found. High-danger matches were spot-checked as real (the revenue CONCEPT_FORKs, the completed_orders and active_customers cross-layer divergences), not token-overlap flukes.
- **Precision (90%) overstates usefulness.** Two reasons: (a) the detector is PAIRWISE, so the revenue family alone is 14 CONCEPT_FORK findings that collapse to ~3 gold findings — 123 raw findings are perhaps ~45 distinct collisions; (b) 46 of them are CROSS_REF, a weak 'this term is modelled and documented, check it' pointer, not a diagnosis. Counting those as precision hits is generous.
- **The false positives exposed a real bug.** `order_count ~ order_date`, `order_count ~ order_status` were called DUPLICATE because two facts sharing ONLY `base` pass the same-measure test. Fix: require agreement on >=2 declared meaning facets, not one. Reported, not silently patched (the detector was frozen before scoring).
- **The 4 misses are all explainable, and each names a real gap:** recognised/recognized (British vs US spelling defeats exact-label match); the `new` segment whose filter contradicts its own description (a within-fact check the detector doesn't do); email (killed by our own plumbing stoplist); cost columns (below the >=4-table overload threshold). None is a silent hole — each points at a specific next feature.
- **Bottom line:** on a realistic, blind-generated, three-layer messy environment the detector caught **16/16 high-danger** collisions and **111/123** overall. The design (embedding gate + structural danger + cross-layer name match) generalises well for RECALL; the work left is PRECISION — dedup pairwise into per-concept clusters, turn CROSS_REF into a real consistency check, and fix the loose same-measure test.