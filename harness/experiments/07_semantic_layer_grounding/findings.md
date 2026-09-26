# Experiment 07: findings

The standing record for semantic layer grounding. Every claim traces to a file in this folder or to
the harness code paths named inline. Where a claim rests on something not measured, it says so.

**Paths in the entries below are as they were when each entry was written.** The 2026-09-22
restructure removed the exploratory tooling those entries name: `spine/generate.py` and `spine.yaml`
(the governance part now lives in `fixture/governance.yml`, and the rest is derived at run time
by `ontology.parameters`), `inspector/` and `protocol/select.py`. The three outputs the entries cite
are kept in `probes/`: `trace_app_opens.json`, `q_001.html` and `answerable.html`.

**Status: preliminary.** One question, one run of one model. This establishes the instrument and its
first reading, not a rate. Qualitative by design: no accuracy numbers are claimed for the agent.

---

## The subject — reliability lives in the selectable parameters

A catalogue match gives you a governed **metric**. It does not tell you the **question** was answered
with confidence. But the reliability of one question does not come down to *every* decision behind
the number. It comes down to the decisions the agent could actually **select** when it ran the query
— the **optionality**.

The distinction that organises this experiment:

- **Selectable parameters** — the agent's action space in the `query_metric` call: which metric,
  which segment filters, which time range, which grain. Each is a choice, so each can be wrong, and
  each should rest on a **grounding**. This is the reliability surface.
- **Fixed parameters** — frozen upstream, into the fact table, the measure, or the metric's own
  definition. The agent cannot change them at query time. **No optionality means no room for a
  query-time error**, so these are not the agent's to get wrong and are excluded from the audit.

The instrument (`inspector/inspect.py`) shows only the selectable parameters and asks one thing of
each: is the chosen value grounded, or is it an assumption? Confidence follows the assumptions.

The fixture is the exp06 warehouse, dbt models and MetricFlow layer, copied under `fixture/` so it
can be modified without disturbing experiment 06.

---

## The spine, and its two halves

The reference the audit grounds against, generated in two parts; only one is written by hand.

| half | count | source |
|---|---:|---|
| **generated base** — entities, join graph, measures (source fact, aggregation, time role, scope filter, grain, **additivity**), attributes, and — read from DuckDB — **coverage** and **member sets** | 37 nodes | `generate.py`, from the MetricFlow layer + dbt models + the warehouse |
| **governance overlay** — vocabulary (word → candidate set), the contested relation, named segments, owner/status, and the closure section | 29 facts | `overlay.yaml`, hand-written |

**The overlay's size is a finding: it is the shape of what the semantic layer cannot express.**
Additivity is *derived* from the aggregate (`generate.py:_additivity`), not written by hand, which
dropped the overlay from 33 facts to 29 — a fact the aggregate already implies is not a gap. A drift
guard (`generate.py:check_drift`) refuses to regenerate if a hand-written segment's filter stops
matching the metric it annotates.

---

## 1 · The `query_metric` parameter surface

This is the ground truth for what is selectable. The tool the agent holds
(`engine/src/agent/tools/query.py:81`) accepts exactly these parameters:

| parameter | schema | selectable? | how its values are constrained |
|---|---|---|---|
| `metric` | string (required) | **yes** | must name a governed metric (`list_metrics`) |
| `filters` | object `{dim: value}` | **yes** | any dimension of the metric; a value outside the dimension's members is flagged (`_unknown_filter_values`) |
| `group_by` | array of strings | **yes** | **not enumerated in the schema** — validity is decided by the layer, see below |
| `time_grain` | **enum** `("day","week","month")` | **yes** | a closed enum (`warehouse/config.py:40`); the same three for every metric |
| `period` | enum of presets, or `YYYY-MM` / `YYYY-Qn` / `YYYY-Hn` | **yes** | a pattern; omission means "current value" |
| `start` / `end` | date strings | yes | for exact ranges |

Everything else the number depends on — the aggregation, the metric's built-in scope filter, the time
role, the event definition, additivity — is **not** a parameter of this tool. It is fixed the moment
the metric is chosen.

### `time_grain` — a closed enum, so only *wrong-for-intent* is possible

Because `time_grain` is an `enum` of `day` / `week` / `month`, the agent **cannot pass an invalid
value** — the schema rejects it — and the set is identical for every metric. So the grain risk here
is never an invalid grain; it is a **valid grain that is wrong for the question**: `time_grain='day'`
is legal but returns 30 daily numbers where "how many in June" wanted one total.

### `group_by` — validity comes from the semantic graph, not the schema

`group_by` is an open `array of strings`. Which dimensions are valid for a specific metric is decided
by MetricFlow (`metricflow_engine.py:allowed_filters` → `simple_dimensions_for_metrics`), from **two
places** (the code's own words: "a metric's dimensions arrive from its own model, and every model
reachable by a shared entity"). Live, for `app_opens`:

```
own model (activity, on fct_user_days):
  activity__active_date  activity__platform  activity__channel
  activity__region       activity__country   activity__is_internal   metric_time
reachable by the activity → user join:
  user__signup_date  user__region  user__channel  user__is_internal
```

So the rule is: **a metric can be grouped by the dimensions of the entity it counts, plus the
dimensions of any entity joined to it.** A `group_by` outside that set (e.g. `subscription__plan`,
a different entity not joined here) does not compile; MetricFlow raises an error at compile time,
which the harness shortens to something actionable. The tool schema does not catch it, because it
does not enumerate the dimensions.

### The reliability point: validity ≠ correctness-for-intent

| | invalid value | valid but wrong for the question |
|---|---|---|
| `time_grain` | impossible (closed enum) | possible (`day` when a total was asked) |
| `group_by` | possible to attempt; engine refuses it at compile time | possible (`region` when a total was asked) |

**The engine guarantees a grain choice is valid. Nothing guarantees it is what the question asked
for.** That gap is why grain stays a selectable parameter worth grounding even when the value is
structurally legal. The spine reproduces MetricFlow's "own model + join-reachable" rule from its join
graph and each attribute's entity, so the inspector can check a `group_by` against the metric's
allowed set without calling the engine.

---

## 2 · The run, and the selectable-choice audit

`gpt-5-mini`, rung 3 (star schema + governed MetricFlow layer, raw SQL still offered), one rep
(`probes/trace_app_opens.json`). One call, then it stopped:

```
query_metric(metric='app_opens', filters={'activity__platform': 'android'}, period='2026-06') → 8232
```

8,232 reconciles with the case's independent `gold_sql` (`fixture/cases.yml:a_android_opens_june`,
tolerance 0.02): a correct answer. The audit (`probes/q_001.html`) covers only the four selectable
choices:

| selectable parameter | chosen | grounding | risk it guards against | state |
|---|---|---|---|---|
| metric | `app_opens` | `vocabulary['app opens']` → one match | wrong-metric selection | grounded |
| segment: platform | `= android` | `android` is a member in the warehouse | filter value not a real member | grounded |
| time range | `2026-06` | from the question, and inside coverage `2025-09-05..2026-07-12` | period outside the data | grounded |
| grain (group-by) | single total, no `group_by` | the question shape ("how many") | wrong breakdown level | grounded |

**Verdict: FULLY GROUNDED.** Every parameter the agent could have gotten wrong rests on a basis.

Picking the metric also fixed six parameters the agent cannot change — aggregation (`sum`),
population filter (`is_internal=false`), time role (`active_date`), event definition (app open =
`etype 1`, decoded in `stg_events.sql`), additivity (additive), and timezone. With no optionality,
none of them is a query-time risk, so none appears in the audit. The timezone is the one that is
*fixed and ungrounded* — nothing declares a zone — but that is a modelling assumption baked into the
layer, affecting every answer equally, not a choice the agent made.

---

## 3 · Why the metric choice is the highest-leverage selectable parameter

Choosing the metric silently fixes the whole bundle above (population, aggregation, time role, …). So
the single most consequential thing the agent selects is *which metric*, and its risk — wrong-metric
selection — is only real when a concept maps to more than one governed definition.

- For `app_opens`, `vocabulary['app opens']` has one candidate, so the metric choice is forced and
  grounded. No optionality at the metric level either.
- For a **contested** concept the picture inverts: `vocabulary['active users']` maps to
  `active_users` and `active_accounts`, which differ only on the population filter. There, the
  metric choice **is** a silent population choice, so the population moves from fixed to selectable,
  and the metric row becomes an assumption unless the question or a policy separates them. That is
  the mechanism behind the classic silent-error on ambiguous questions.

The general rule: **a fixed parameter becomes selectable exactly when the layer offers more than one
metric that differ on it.** Optionality is a property of the catalogue, not of the parameter.

---

## 4 · Schema gaps — what the layer could not state

Each had to be computed from the warehouse or written into the overlay, because MetricFlow has no
field for it. The primary output that grows with each question.

| gap | evidence | how the spine fills it |
|---|---|---|
| **No declared member set.** `platform` collapses **11 raw spellings** (incl. null) into 4 mart members; `channel` collapses **17 into 5**. The rule lives only in `stg_users.sql`. | `spine.yaml` `attributes.platform.raw_values` vs `values` | member set read from the warehouse; raw spellings from `_source` |
| **No coverage window.** The layer declares none. | `spine.yaml` `coverage.*._computed_from` | min/max of each fact's time dimension, from DuckDB |
| **No timezone / calendar.** Nothing declares a zone or a fiscal calendar. | absent everywhere | recorded as `none` grounding on the fixed timezone parameter |
| **No owner or status field.** MetricFlow shoves owner into free-text descriptions. | `overlay.yaml` `measures.*.owner/status` | hand-written in the overlay |
| **No word → candidate-set map.** A word maps to one or several governed definitions; the layer cannot say. | `overlay.yaml` `vocabulary` | hand-written; `"active users"` → two candidates is where the metric choice becomes a risk |
| **No relation between definitions.** "Two metrics answer the same question" is prose. | `overlay.yaml` `relationships.rel_active_user_definition` | contested node with owner, evidence tier, status, policy |

`additivity` was on this list in the first pass and was removed: it is derivable from the aggregate,
so it was never a gap the layer had, only one this spine had failed to compute.

---

## 5 · Answerability is a graph lookup (the step before the audit)

Before the selectable audit runs, a concept resolves to one of three states, decided by the spine
alone (`inspector/answerable.py`, `probes/answerable.html`):

| concept | verdict | why |
|---|---|---|
| app opens | **GOVERNED** | `vocabulary['app opens']` → one metric |
| active users | **GOVERNED** (two candidates) | → `active_users`, `active_accounts` — the metric choice carries the optionality |
| 90-day retention | **COMPUTABLE** | no governed metric, but `user.signup_date` and `activity.active_date` ground and are joinable |
| minutes in app | **UNINSTRUMENTED** | `not_captured`: no event carries a duration or end timestamp |
| page views | **UNINSTRUMENTED** | `not_captured`: no page/screen event type |

**COMPUTABLE vs UNINSTRUMENTED is decidable only because the spine asserts closure**
(`closure.captured_is_complete`). An agent reasoning open-world cannot prove the warehouse lacks a
duration column, so it would invent a definition; the closed-world graph makes the absence a fact.

---

## 6 · What is not yet built

- **The audit does not yet compute the metric-level optionality automatically.** It reads the
  vocabulary candidate count, but does not cross-check against `allowed_filters` to confirm which
  fixed parameters *could* have been selectable via an alternative metric.
- **`group_by` validity is checked against the spine, not the live engine.** The spine reproduces
  the "own model + join-reachable" rule, but is not yet diffed against `simple_dimensions_for_metrics`
  to prove the two agree.
- **`time_grain` and `period` grounding is read from the result string**, not the compiled MetricFlow
  SQL. The compiled query is the exact record and should be the source.
- **Only one question, one run.** No rate, no repeats, no held-out set. The claim is structural: a
  correct answer whose four selectable choices are all grounded.
