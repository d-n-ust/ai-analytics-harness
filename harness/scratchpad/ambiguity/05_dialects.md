# T5 — dialect portability (MetricFlow + Cube)

Desk exercise, no code. Does the meaning/scope split the classifier depends on survive in the two
open, checkable semantic-layer dialects? (LookML skipped — proprietary; MetricFlow and Cube are the
ones a reader can verify against public repos.)

The three reference metrics, translated by hand:

- **value_moments** — `sum(moments)`, all users.
- **real_value_moments** — `sum(moments)`, excludes internal/test accounts. Same measure, narrower scope.
- **power_users** — distinct users who logged ≥5 moments on any day, excludes internal/test.

---

## MetricFlow (dbt semantic layer)

```yaml
semantic_models:
  - name: activity
    model: ref('agg_active_days')          # one row = one user-active-day
    entities: [{name: user, type: primary, expr: user_id}]
    dimensions:
      - {name: active_date, type: time, type_params: {time_granularity: day}}
      - {name: is_internal, type: categorical}
      - {name: moments,     type: categorical}      # exposed so a metric can filter on it
    measures:
      - {name: moments_sum,    agg: sum,            expr: moments}
      - {name: distinct_users, agg: count_distinct, expr: user_id}

metrics:
  - name: value_moments                    # all
    type: simple
    type_params: {measure: moments_sum}
  - name: real_value_moments               # scope as a FIRST-CLASS filter, not welded
    type: simple
    type_params: {measure: moments_sum}
    filter: "{{ Dimension('user__is_internal') }} = false"
  - name: power_users                       # threshold is ALSO a filter — no CASE needed
    type: simple
    type_params: {measure: distinct_users}
    filter: "{{ Dimension('user__is_internal') }} = false and {{ Dimension('user__moments') }} >= 5"
```

Scope lives in the metric `filter:` — a first-class field. `real_value_moments` differs from
`value_moments` only there, so the classifier reads them as same-measure/different-scope. Even
`power_users` needs no `CASE`: a row filter `moments >= 5` under `count_distinct(user_id)` is exactly
"distinct users with a ≥5 day."

## Cube

```javascript
cube('Activity', {
  sql: `SELECT * FROM agg_active_days`,
  measures: {
    moments_sum:    { sql: 'moments', type: 'sum' },
    distinct_users: { sql: 'user_id', type: 'countDistinct' },
    power_users:    { sql: 'user_id', type: 'countDistinct',
                      filters: [{ sql: `${CUBE}.moments >= 5` }] },   // threshold as a filter
  },
  dimensions: { is_internal: { sql: 'is_internal', type: 'boolean' },
                active_date: { sql: 'active_date', type: 'time' } },
  segments: {
    real: { sql: `${CUBE}.is_internal = false` },   // named, reusable population filter
  },
});
// value_moments      = measure moments_sum
// real_value_moments = measure moments_sum + segment `real`
// power_users        = measure power_users + segment `real`
```

Cube separates scope two ways, both first-class: a named **segment** (reusable across measures) and a
measure **`filters`** array. Neither requires welding a `CASE` into the aggregation.

---

## Portability table

| dialect | where scope lives | scope separable? | welding permitted? | if welded, classifier degrades to |
|---|---|---|---|---|
| **MetricFlow** | metric `filter:` | **yes**, and idiomatic | yes (a `CASE` in `expr`) | `different_measure` / low |
| **Cube** | `segments` + measure `filters:` | **yes**, and idiomatic | yes (a `CASE` in measure `sql`) | `different_measure` / low |
| (LookML) | `sql_always_where` / measure `filters` / inline `sql:` | not tested here | — | — |

**Corpus evidence that separation is the idiom (not just the docs).** In the public MetricFlow
projects sampled in T2, metrics use the separate `filter:` field **7 times** (jaffle-shop and
jaffle-sl-template) and weld a population restriction into a `CASE WHEN` essentially **never** in the
modern spec. Docs show the clean form and repos use it.

---

## The `power_users` finding

`power_users` welds its segment into the aggregation **in this repo's own layer**
(`count(distinct case when moments >= 5 then user_id end)`), and that is exactly why `ambiguity.py`
classifies the shipped version `different_measure`/low instead of `scope_only`/high. But the
translations above show the welding is a **choice, not a necessity** — both MetricFlow and Cube
express `power_users` with a *separate* filter. The dangerous downgrade is caused by a modelling
decision, not by any dialect forcing it.

---

## Verdict — how conditional the claim has to become

**For MetricFlow and Cube: not much.** Scope is a separable, first-class construct in both, and the
separated form is the idiomatic one (the corpus confirms it). So the kill condition — "welding scope
is idiomatic on a major platform, so the dangerous class silently downgrades" — is **not met** for
these two dialects. The claim does not need a heavy platform conditional here.

The residual risk is real but different from the one the test feared: **teams weld by choice** even in
dialects that support separation — this repo did it for `power_users`; the no-SL team welds everything
into query `WHERE` clauses; the sales/retail generators welded some metrics into `expr`. That is a
discipline problem, not a dialect limitation, and it is the case the v3 detector now handles by
**parsing the SQL** to recover the welded scope rather than relying on a declared `filter:` field.

**The one honest conditional that remains:** LookML is untested here. Its inline `sql:` on measures
makes welding easier to reach, so it is the platform where welding might genuinely be idiomatic and the
dangerous class might systematically downgrade. Confirming that needs the LookML repo-grep the doc
originally specified — the remaining piece of T5.
