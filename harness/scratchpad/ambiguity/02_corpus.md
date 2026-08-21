# Test 2 — Corpus smoke test (phase 1)

Real public semantic layers, offline (no dbt, no warehouse, no tokens). Three schemas: jaffle-shop (embedded `agg/expr/filter`), jaffle-sl-template (`type_params.measure` + `filter`), jaffle_shop_metrics (deprecated `calculation_method/expression/filters`). All three declare scope as a separate field; none declares `unit`.

`native` fills only declared facets; `inferred` also infers `unit` from the aggregation. The gap between the two `scope_only` columns is the finding.

## Per-project scan

```
project                metrics  gated | scope_only diff_meas  (native) | scope_only (inferred) | facets% unit%
jaffle-shop                 17     28 |          0        28           |         10             |   60.5%  0.0%
jaffle-sl-template          11     13 |          0        12           |          2             |   46.8%  0.0%
jaffle_shop_metrics          4      0 |          0         0           |          0             |   57.1%  0.0%
```
`facets%` = mean native population across the 7 facets; `unit%` = share of metrics declaring `unit` natively.

## (a) Gate scaling — gated pairs vs metric count

```
project                metrics(n)  gated_pairs   n(n-1)/2 gated/pairs
jaffle_shop_metrics             4            0          6        0.00
jaffle-sl-template             11           13         55        0.24
jaffle-shop                    17           28        136        0.21
```
If `gated/pairs` falls as n grows, the lexical gate is sublinear in n^2 (reviewable); if it stays flat or rises, it is quadratic. NOTE: public MetricFlow projects are all small (the spec is young), so this range is narrow — a genuine limit on how far this test can settle the scale question from public data.

## (b) The 5 hand-inspected scope_only findings (largest project, inferred unit)

Shown in the classifier's OWN top-5 ranking, with a one-line plausibility verdict as an outsider. The pattern that matters: a bare head noun (`orders`) confused with a filtered variant is a real trap; two filtered siblings (`food` vs `drink`) share only the head noun and are not genuinely confusable — the distinguishing word is prominent.

```
drink_orders  ~  food_orders
    shares: orders | differs: default_filters
    verdict: NOISE: two filtered siblings sharing only the head noun `orders`; the distinguishing modifier is prominent, so a reader would not swap them.
drink_orders  ~  large_orders
    shares: orders | differs: default_filters
    verdict: NOISE: two filtered siblings sharing only the head noun `orders`; the distinguishing modifier is prominent, so a reader would not swap them.
drink_orders  ~  new_customer_orders
    shares: orders | differs: default_filters
    verdict: NOISE: two filtered siblings sharing only the head noun `orders`; the distinguishing modifier is prominent, so a reader would not swap them.
drink_orders  ~  orders
    shares: orders | differs: default_filters
    verdict: GENUINE: bare `orders` vs a filtered subset — the real scope trap.
food_orders  ~  large_orders
    shares: orders | differs: default_filters
    verdict: NOISE: two filtered siblings sharing only the head noun `orders`; the distinguishing modifier is prominent, so a reader would not swap them.
```
**1 of the top-5 are genuine confusions; 4 are sibling noise.** The genuinely dangerous pattern (bare `orders` vs `food_orders` / `drink_orders` / `large_orders` / `new_customer_orders`) exists, but the classifier does not rank it above filtered-vs-filtered sibling pairs. On a real layer the gate over-generates, and the one pattern worth clarifying is buried in siblings that share only a head noun — a precision problem the `_QUALIFIERS` list tuned away on this repo's own layer but does not generalise.

## Verdict against the kill condition

- **Scope IS separable in real layers.** Every dialect declares the restriction as a first-class field (`filter:` or `filters:`), never only welded into the aggregate. So the pessimistic version of the kill condition — scope is not declared separately — is **not** met.
- **But the classifier collapses on real layers as written.** scope_only pairs found natively across all projects: **0**. With `unit` inferred: **12**. The rule `len(same) == len(_MEANING)` (ambiguity.py:113) requires all four meaning facets present, including `unit`, which no MetricFlow/dbt-metrics dialect declares. So every genuine scope pair is demoted to different_measure/low unless the adapter invents a `unit`.
- **Reported, not edited (ground rule 1).** ambiguity.py needs one change to run on real layers: scope_only should require agreement on all meaning facets *both metrics declare*, not on a hardcoded four. As written, `unit` being ecosystem-absent silently turns the dangerous class off. This is the Test-1 welded-scope limitation's sibling: there the danger hid because scope was welded; here it hides because a required meaning facet is never declared.
- **Net:** facets exist and scope is separable (part b passes in principle), but the classifier's meaning-facet rule must be generalised before the claim 'detectable in semantic layers' holds for layers other than this repo's.