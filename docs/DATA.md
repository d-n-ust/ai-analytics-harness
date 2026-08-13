# The data platform

The whole warehouse is synthetic and deterministic — generated from a fixed seed, so it reproduces
on a laptop with no warehouse to provision (DuckDB, one file). It models a messy consumer
habit-tracking app, and it is deliberately hostile, so that *structure* has something to fix.

```
bench data       # (re)generate runs/warehouse.duckdb
bench verify     # check it against the generator's ground truth
bench query "SELECT ..."   # run SQL with the clean dim_/fct_ views built
```

## Raw → star (the transformation layer)

- **Raw tables** (`engine/src/warehouse/generate.py`) — the application database as it really is: cryptic column
  names, inconsistent enums (`platform` stored as `ios` / `iOS` / `IOS` / `1`), integer status codes,
  internal/test users mixed into production, and grain traps that silently double numbers.
- **Star schema** (`engine/src/warehouse/star.sql`) — clean `dim_*` / `fct_*` views over the raw tables: sane
  names, typed columns, normalised enums, timezone-free ISO dates. Built at query time by
  `engine/src/warehouse/warehouse.py`.

## The governed model (the semantic layer)

`engine/src/semantic/semantic_layer.yml` defines the metrics — each a named, governed query spec (entity +
segment + aggregate + grain), the same shape a MetricFlow/Cube layer uses. A metric already *is* a
structured query definition; the harness reads it back, it never re-declares it. Examples:

| metric | one row is… | measure | segment (the built-in filter) |
|---|---|---|---|
| `active_users` | a user | `count_distinct` | active in the window |
| `paying_users` | a user | `count_distinct` | on a paying plan |
| `value_moments` | a completion | `sum` | all |
| `mrr` | (a stock) | `sum` of monthly value | active subscriptions |
| `new_signups` | a signup | `count` | all (or `real_acquisition`) |

Governance the layer enforces as **data**, not prose a model must remember:
- **internal/test exclusion** — the `real_acquisition` segment drops the `partnerships` test channel
  at query time (`channel NOT IN ('partnerships')`).
- **coverage windows** — a region member carries `available_from` (APAC launches 2026-05-01); a
  question naming a pre-launch period is out of coverage, and a country filter inherits its region's
  window.
- **member resolution** — free-text filter values resolve to a governed member (`iPhone → ios`) or
  refuse; a hyponym (`North America`) is *not* silently widened to its parent (`Americas`).

## Recompute a metric by hand

Don't trust the layer — check it. `bench query` runs SQL against the same clean views:

```bash
# active users last week: the metric should equal this hand-written count
bench query "SELECT count(DISTINCT user_id) FROM agg_active_days
             WHERE NOT is_internal AND active_date >= DATE '2026-07-06'"

# compare against the governed metric
bench ask "how many active users did we have last week?" --rung 3
```

The gold answers behind the eval are computed the same way (independent gold SQL, `harness/evals/gold.py`) and
are treated as **fallible** — benchmark "gold" is wrong more often than anyone admits, so they are
sanity-checked, not trusted.

## The injected anomaly

A known anomaly is injected into the most recent week, so the diagnostic questions have a
*computable* correct root cause (which driver moved, by how much), not a vibe. The metric tree
(`engine/src/semantic/metric_tree.yml`) carries the identity + influence edges the diagnostic tier walks.
