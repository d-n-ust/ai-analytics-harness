# No-semantic-layer contrast (same company, three configs)

## Welded-scope recoverability from saved SQL (Test 3, in miniature)

41 saved queries. sqlglot recovered: agg 41/41, base (table) 41/41, WHERE/scope 34/41. Queries carrying a non-empty welded scope: 34/41.

So welded scope is largely RECOVERABLE from real query SQL — it is invisible to a name-only lint, not to one that parses the query.

## Findings by config
```
config                         defs findings high metric-lvl sc_trap c_fork def_div  name
A governed (wh+docs+SL)          39       57   10         43       2      3      25    22
B welded (wh+docs+queries)       41       34    6         17       4      0       4    20
C bare (wh+docs)                  0       18    2          0       0      0       2    12
```
`defs` = number of metric/query definitions on the surface; `metric-lvl` = findings that involve at least one such definition.

## High-danger metric-level findings: governed vs welded

### A governed (wh+docs+SL) — 9
```
[CONCEPT_FORK] booked_revenue[sem]  ~  gross_revenue[sem]  ~  net_revenue[sem]  ~  net_sales[sem]  ~  order_revenue[sem]  ~  revenue[sem]
[CONCEPT_FORK] active_customers[sem]  ~  paying_customers[sem]  ~  total_customers[sem]
[CONCEPT_FORK] churned_mrr[sem]  ~  new_mrr[sem]
[DEFINITION_DIVERGENCE] revenue[doc]  ~  revenue[doc]  ~  revenue[sem]  ~  revenue[war]
[DEFINITION_DIVERGENCE] active_customers[sem]  ~  active_customers[sem]  ~  active_customers[war]
[DEFINITION_DIVERGENCE] completed_orders[sem]  ~  completed_orders[war]
[DEFINITION_DIVERGENCE] active_subscriptions[sem]  ~  active_subscriptions[war]
[SCOPE_TRAP] completed_orders[sem]  ~  order_count[sem]
[SCOPE_TRAP] active_customers[sem]  ~  total_customers[sem]
```

### B welded (wh+docs+queries) — 4
```
[SCOPE_TRAP] net_revenue[doc]  ~  net_revenue_finance_pack[que]  ~  revenue_finance[que]
[SCOPE_TRAP] active_customers[que]  ~  customer_count[que]  ~  new_customers_monthly[que]
[SCOPE_TRAP] new_customers[que]  ~  total_customers[que]
[SCOPE_TRAP] mrr[que]  ~  mrr[war]
```

## Read

- **The governed layer is where the danger becomes catchable.** Bare warehouse+docs (C) surfaces 0 metric-level collisions and 0 scope traps — there are no metric definitions to compare. Add the semantic layer (A) and the detector finds 43 metric-level findings incl. 2 scope traps and 3 concept forks.
- **A no-SL team's welded SQL is recoverable, so the collisions are still catchable (B) — but the surface is messier.** B has 41 ad-hoc query definitions vs A's 39 governed ones, and flags 17 metric-level collisions. Welding scope into WHERE does NOT hide it from a SQL-parsing detector; it hides it only from a name-only lint, and from an agent that reads the schema but not the saved queries.
- **The real difference is governance, not detectability.** With the SL there are 39 definitions and one is meant to be authoritative; without it there are 41 saved queries and none is. The detector can flag the forks in both, but only the governed layer gives a place to resolve them.
- **But the agent's view is config C, not B.** An agent usually grounds on the schema + docs and writes its OWN SQL; it does not necessarily read all 41 saved queries. From that seat the metric-level ambiguity is invisible (0 catchable in C), and the agent welds a fresh, unreviewed scope every time — exactly the Test-1 finding at environment scale. The saved queries are recoverable IF handed to a parser, but they are not a governed grounding surface.
- **Two honest caveats on B's lower numbers.** concept_fork is 0 for welded queries because the adapter does not recover `entity` from SQL (entity is the hardest primitive to parse — the Test-3 blind spot), so the revenue-family fork is under-counted, not absent. And def_div is lower partly because ad-hoc query names (`net_revenue_finance_pack`) do not align with the docs glossary, so fewer cross-layer name matches fire. Both are detector/adapter limits, not evidence that welding is safe.