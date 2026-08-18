# Finding catalog — what each one means, and how to fix it

preflight reports seven kinds of grounding collision. This is the field guide: for each, a real
example, why it puts a wrong number in front of someone, and the recommended fix. Most fixes share one
idea — **move a hidden scope out of a metric's name or SQL and into a dimension or an explicit filter,
so the choice an analyst (or an agent) makes is visible and governed.**

Severity (`high` / `medium` / `low`) is preflight's estimate of how likely the confusion is to bite at
query time. Fix HIGH first. The examples below use dbt MetricFlow YAML; the same shapes exist in Cube
(segments) and LookML (`sql_always_where`).

| type | one line | severity |
|---|---|---|
| [SCOPE_TRAP](#scope_trap) | a metric is another metric plus a hidden filter | high |
| [CONCEPT_FORK](#concept_fork) | one concept, several metrics over different columns | high |
| [GRAIN_MISMATCH](#grain_mismatch) | the same measure at two grains, and it cannot be rolled up | high / medium |
| [DEFINITION_DIVERGENCE](#definition_divergence) | one term defined two ways, or a metric its docs do not describe | high / medium |
| [NAME_COLLISION](#name_collision) | two names read alike, or one column name reused across tables, meaning different things | medium / low |
| [DUPLICATE](#duplicate) | the same thing under two names | low |
| [SIBLING](#sibling) | the same measure under incomparable scopes | low |

---

## SCOPE_TRAP

**What.** Metric B is metric A with an extra filter, and both are offered as bare metrics. A question
that names the concept can silently resolve to the scoped one.

**Example** (`dbt-labs/jaffle-sl-template`, `orders.yml:139`):

```yaml
metrics:
  - name: orders                     # count of all orders
    type: simple
    type_params: { measure: order_count }
  - name: food_orders                # orders, silently restricted to food
    type: simple
    type_params: { measure: order_count }
    filter: "{{ Dimension('order_id__is_food_order') }} = true"
```

**Why it bites.** "How many orders did we do?" can land on `food_orders` and under-count, and the
number looks completely plausible. The scope (food only) is invisible in the answer.

**Fix — expose the flag as a dimension and drop the scoped metric.** Keep one `orders`; make the thing
it was filtering on a dimension, so "food orders" is `orders` filtered to it, not a second metric:

```yaml
# one metric …
metrics:
  - name: orders
    type: simple
    type_params: { measure: order_count }
# … and the flag it filtered on becomes a dimension
dimensions:
  - name: is_food_order              # an order can contain BOTH food and drink, so these
    type: categorical                # flags overlap — keep them as separate booleans, not one
    expr: is_food_order              # food|drink partition (which would lose the both-orders)
  - name: is_drink_order
    type: categorical
    expr: is_drink_order
```

"Food orders" is then `orders` filtered to `is_food_order`, and the bare `food_orders` metric is
removed. (jaffle already scopes `food_orders` with an explicit `filter:` rather than a baked-in CASE,
which is the legible half; the trap is only that it still coexists with `orders` as a peer metric.)
Where a scope is genuinely a clean partition — one value per row, like `region` or `plan` — use a
single categorical dimension with a `case` expr instead, as in [CONCEPT_FORK](#concept_fork) below.

---

## CONCEPT_FORK

**What.** Several metrics on the same table, aggregated the same way, over **different columns** — so a
bare concept resolves to different numbers. The tell is a shared head noun (`revenue`) with the scope
baked into each measure's SQL.

**Example** (`dbt-labs/jaffle-sl-template`, `order_items.yml`):

```yaml
measures:
  - name: revenue
    agg: sum
    expr: product_price
  - name: food_revenue
    agg: sum
    expr: case when is_food_item = 1 then product_price else 0 end   # scope hidden in the measure
  - name: drink_revenue
    agg: sum
    expr: case when is_drink_item = 1 then product_price else 0 end
```

**Why it bites.** Three `revenue` metrics coexist, and `is_food_item` / `is_drink_item` are independent
flags, so an item can be neither. That means `food_revenue + drink_revenue ≠ revenue`; anyone who
assumes they decompose gets a wrong number, and a bare "revenue" question can pick a scoped one.

**Fix — one measure, category as a dimension.** The categorical flags already exist; fold them into one
dimension and drop the scoped measures:

```yaml
measures:
  - name: revenue
    agg: sum
    expr: product_price
dimensions:
  - name: product_category           # food | drink | other
    type: categorical
    expr: >
      case when is_food_item = 1 then 'food'
           when is_drink_item = 1 then 'drink' else 'other' end
```

"Food revenue" is now `revenue` grouped by `product_category = 'food'`. One unambiguous metric, the
breakdown is a GROUP BY, and it scales — a new category is a dimension value, not a new metric. (If a
named `food_revenue` is a hard requirement, define it as `type: simple` over the `revenue` measure with
a `filter` on the dimension, which converts the fork into a legible subset.)

---

## GRAIN_MISMATCH

**What.** A number that should not be added up over time is offered per day, so someone adds the days up
and gets a number that is far too big.

**Example.** `active_subscriptions` is a running count: how many are active *right now*. If it is
available per day, a monthly dashboard will sum the 30 daily numbers.

```yaml
measures:
  - name: active_subscriptions       # how many are active right now
    agg: sum
    expr: is_active
```

**Why it bites.** It works like a bank balance. You do not add up your balance from each day to get a
monthly balance. A subscription that stayed active all month is counted on all 30 days, so the monthly
total comes out about 30 times too high. The number looks normal, and it is wrong.

**Fix.** Take a snapshot per period, and tell the layer to use the period's ending value instead of
adding the days together:

```yaml
measures:
  - name: active_subscriptions
    agg: sum
    expr: is_active
    non_additive_dimension:
      name: metric_time
      window_choice: max            # use the end-of-period value, don't add the days up
```

The same is true for any "count of distinct things" (distinct users, distinct accounts): it does not add
up across days. Show it only for the exact period you counted (a day, a week, a month), or count it again
for each period.

---

## DEFINITION_DIVERGENCE

**What.** One term carries two meanings, or a metric is built on a column its own documentation never
describes. Two forms: doc-vs-doc (a glossary term defined two ways) and cross-layer (a metric whose
description does not mention what it actually measures).

**Example** (`dbt-labs/jaffle-shop`, `orders.yml`): the metric `order_total` is modelled on the column
`order_total`, but its description does not reference it, so an agent reading the description alone has
no anchor for what the number is.

**Why it bites.** An agent grounds on the prose it is given. If the definition and the SQL disagree, or
the definition is silent about the columns, the agent cannot tell which reading is intended and picks
one.

**Fix — one definition, and make it describe what the metric measures.**

```yaml
metrics:
  - name: order_total
    description: "Sum of item price plus tax per order (models the order_total column)."   # names the basis
    type: simple
    type_params: { measure: order_total }
```

For the doc-vs-doc case, delete the duplicate glossary entry and keep a single definition that the
governed metric points to.

---

## NAME_COLLISION

**What.** Two names read alike but mean different things — often one is a prefix of the other, or they
differ only by a unit.

**Example** (`dbt-labs/jaffle-shop`, `order_items.yml:46`): `food_revenue` (dollars) and
`food_revenue_pct` (a share). "Food revenue" matches both, and the dollars metric is a prefix of the
percentage one.

**Why it bites.** A retrieval or embedding step matching "food revenue" can return either; the units are
different, so the wrong pick is off by orders of magnitude, not a rounding error.

**Fix — make the unit explicit and non-overlapping in both names.**

```yaml
metrics:
  - name: food_revenue_usd          # was: food_revenue
    description: "Food revenue in dollars."
  - name: food_revenue_share        # was: food_revenue_pct
    description: "Food revenue as a fraction of total revenue."
```

Neither name is now a prefix of the other, and each states its unit.

**The other way this fires: one column name in many tables.** A non-key column like `status`, `amount`,
or `type` that appears on several tables may mean something different in each — `orders.status` is a
fulfilment state, `subscriptions.status` is a billing state. An agent that has learned "status" from one
table will read it wrong on another.

**Fix — qualify the meaning, or confirm it is genuinely one concept.** If the columns mean different
things, give them distinct names (`order_status`, `subscription_status`) or document each in its table.
If they really are one shared concept, make that explicit (a conformed dimension, or a note that the
meaning is the same everywhere) so the shared name is a decision, not a coincidence.

---

## DUPLICATE

**What.** The same measure, scope, and grain under two names. Two sub-cases with different responses.

**Benign (usually no action):** a semantic measure named after the warehouse column it wraps
(`order_total[sem] ~ order_total[war]` in jaffle). This is expected wiring; preflight flags it `low` so
you know the two names denote one number, reachable two ways.

**Actionable:** two *metrics* in the same layer that compute the identical thing under different names,
e.g. `mrr` and `monthly_recurring_revenue`. Pick one canonical name and remove the other (or make it a
documented alias) so an agent is not choosing between two identical options.

```yaml
# keep one:
metrics:
  - name: mrr
    description: "Monthly recurring revenue. Canonical; `monthly_recurring_revenue` was removed."
# and delete the duplicate metric.
```

---

## SIBLING

**What.** The same measure under two **incomparable** scopes — neither filter is a subset of the other,
so no single question answers both. Lower danger than a scope trap, because the names usually differ,
but it signals metric proliferation.

**Example** (realistic):

```yaml
metrics:
  - name: revenue_us                 # filter: region = 'us'
  - name: revenue_web                # filter: channel = 'web'
```

**Why it bites.** Rarely a wrong number on its own, but every new cut (`revenue_emea`,
`revenue_mobile`, `revenue_us_web`) is another metric, and the combinatorial set is impossible to keep
consistent.

**Fix — cuts are dimensions.** One `revenue`, with `region` and `channel` as dimensions:

```yaml
metrics:
  - name: revenue
    type: simple
    type_params: { measure: revenue }
dimensions:
  - name: region
    type: categorical
  - name: channel
    type: categorical
```

"US web revenue" is `revenue` filtered to `region = 'us' and channel = 'web'` — one metric, any cut.

---

## The pattern under most of these

Five of the seven (SCOPE_TRAP, CONCEPT_FORK, SIBLING, and often NAME_COLLISION and DUPLICATE) are the
same mistake wearing different costumes: **a scope or a cut that belongs in a dimension has been encoded
in a metric's name or its SQL.** The fix is almost always to expose that choice as a dimension or an
explicit, governed filter, leaving one canonical metric per concept. That is also what makes a layer
legible to an agent: one name per concept, and every narrowing visible as an argument.
