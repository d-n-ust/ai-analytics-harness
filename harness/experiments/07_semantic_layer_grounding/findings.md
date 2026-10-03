# Experiment 07: findings

The standing record for semantic layer grounding. Every claim traces to a file in this folder or to
the harness code paths named inline. Where a claim rests on something not measured, it says so.

**Paths in the entries below are as they were when each entry was written.** The 2026-09-22
restructure removed the exploratory tooling those entries name: `spine/generate.py` and `spine.yaml`
(the governance part now lives in `fixture/governance.yml`, and the rest is derived at run time
by `ontology.parameters`), `inspector/` and `protocol/select.py`. The three outputs the entries cite
are kept in `probes/`: `trace_app_opens.json`, `q_001.html` and `answerable.html`.

**Status: development results.** Sections 1 to 6 (2026-09-17 to 2026-09-19) record the first
instrument: one question, one run, qualitative. Sections 7 onwards (2026-09-22 to 2026-10-03) record
the grounding arms and their measured runs on a 16-question development suite. Every number in them
comes from questions the authors wrote and then fixed failures on, so none is a held-out result (E-12,
E-13). Model throughout: `gpt-5-mini`; decision model: `typesafe/jev-1.13-20260917`.

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


---

## 7 · The model of query trust (2026-09-22)

The model the experiment arrived at is written up in `milestoneA.md`. In short: a governed metric
does not make the answer governed, because a query is a metric plus parameter decisions the layer
mostly does not govern. Each decision has a basis (the question, a governed declaration or rule, or
nothing), and the basis decides the action:

| basis | action |
|---|---|
| the question | proceed |
| a governed rule, or the metric's own definition | proceed, and disclose |
| nothing, and the answer depends on it | ask |
| a value the layer does not have | refuse |

The suite (`01_parameter_grounding/cases.yml`) has 16 questions. Every case labels the value of each
parameter its query uses (`expect.params`, checked against the layer by `test_exp07_params.py` and
against the warehouse's members at load), and each answer key is SQL on the raw source tables.

| pile | n | questions |
|---|---|---|
| answerable | 10 | q_001 to q_004 (calibration); t_002, t_006, t_009, t_010; t_001, t_005 (contested, routed by owner) |
| should refuse | 4 | t_003 TikTok, t_004 device model, t_007 Windows, t_008 June 2025 |
| should ask first | 2 | u_001 no period, u_002 "the summer" |

## 8 · The LLM grounding step, and what tracing it found

`R3+parameter_grounding` (`engine/src/agent/guardrails/parameters.py`): when the agent calls
`query_metric`, an LLM maps the question onto the metric's parameters and quotes the phrase behind
each value; code checks the quote is in the question, that the layer's text licenses the member,
applies named rules, and blocks the query when a needed value has no basis. Tracing single runs found
three defects, each fixed:

| defect | observed | fix |
|---|---|---|
| a member mapped from world knowledge | "TikTok" mapped to `organic`; organic's figure served as TikTok's | a mapping stands only if `core/members.licenses` finds it in the layer's text |
| a breakdown run as one cross-table | "by segment" ran region x channel in one `group_by` | the segment rule declares `combine: separate`; one query per dimension |
| an ungrounded value filled in silently | a missing period took the agent's own choice | a needed value with no basis blocks the query; the agent asks |

The quote check itself proved fragile in live runs. On 2026-10-03 it dropped a requested trend
(quote "changed over…", question "change over…") and a requested breakdown (a quote with the model's
own commentary). Both times the query ran as a total and the agent then invented figures: a silent
error caused by the check. Offline, on 33 constructed quote/question pairs:

| matcher | legitimate quotes rejected | wrong quotes accepted |
|---|---|---|
| exact words (default) | 11 of 18 | 0 of 15 |
| `tolerant_quotes` (stems, gaps, prefixes, one typo) | 0 of 18 | 2 of 15 |

`tolerant_quotes` and `quote_retry` (send a bad quote back once, then ask) exist as switches, off by
default. A 4-question live probe built to provoke misquotes produced none, so neither was triggered.

## 9 · An engine default that changes numbers: weekly buckets cross the period

Asked for the first half of 2026 by week, MetricFlow returned whole weeks. The first and last points
included days outside the half-year:

| week | inside 2026-H1 only | returned by the engine |
|---|---|---|
| starting 2025-12-29 | 221 (1 to 4 January) | 404 (includes 29 to 31 December 2025) |
| starting 2026-06-29 | 615 (29 to 30 June) | 2,059 (includes 1 to 5 July) |

Nothing declares this behaviour and the answer does not mention it. It is the "undeclared engine
default" case of the model: deterministic, invisible, and it changes the number. The trend rule in
`governance.yml` now declares `buckets_within_period: true`: only grains whose buckets lie wholly
inside the period are considered (for H1, month), and the disclosure says why weekly was not used.
Verified on q_002 in three runs: all six monthly values match the answer key.

## 10 · Declared governance that nothing read: contested metrics

`governance.yml` declared that "users" has two governed definitions (`active_users`, Product;
`active_accounts`, Platform) and that "absent a consumer, the pair is genuinely ambiguous". No code
read the vocabulary or the relationships. The habits pair (`value_moments` / `total_value_moments`)
was not declared at all. Both cases were answered with one definition, silently:

| question | served | other governed definition | gap |
|---|---|---|---|
| t_001 active Android users, June 2026 | 522 (`active_users`) | 538 (`active_accounts`) | 3.1% |
| t_005 habits by Android users, June 2026 | 5,041 (`value_moments`) | 5,190 (`total_value_moments`) | 3.0% |

The experiment's focus is the parameters after the metric is chosen, so the metric is now settled by
a simple runtime rule: governance declares the requester (`requester.team: Product`), and the
grounding step routes a contested metric to the member that team owns, and discloses it
(`parameters.route_metric`). With no requester declared, the agent asks.

## 11 · Grounding with a decision model instead of an LLM

`R3+decision_grounding` (`engine/src/agent/guardrails/decisions.py`) replaces the LLM proposal with
one request to a decision model (Jev, on OpenRouter's Decisions API). Every option list is generated
from the layer by code: each dimension's members plus `not_mentioned` and `not_in_list`; total,
breakdown or trend; the breakdown dimension or the segment rule; every month, quarter and half-year
inside the metric's coverage plus `not_mentioned` and `outside_coverage`. Code applies the same
policy. There is no quoted phrase to check, so the quote fragility of section 8 does not arise; the
evidence for a value is a probability rather than a span of the question.

A fair offline test (option lists generated by code, labels written before the run, 20 questions,
120 decisions, $0.0014):

| kind of decision | correct |
|---|---|
| a real member (including "Andriod", "jun '26", "SEO" → `content_seo`) | 18 / 18 |
| not mentioned | 79 / 80 |
| not in the layer (TikTok, Windows) | 2 / 2 |
| shape (total / breakdown / trend) | 20 / 20 |

The one disagreement (t_010, "customer" read as excluding staff) is arguably a labelling error.
Above a confidence of 0.7 no decision was wrong. Low confidence fell where the layer itself has two
answers: whether "users" includes staff accounts.

For comparison, GLiNER (`urchade/gliner_small-v2.1`, local) found the phrase behind 35 of 37 value
parameters (platform, channel, period) but none of the 4 structural ones (breakdown or trend
requests), under four label wordings. It suits extracting values, not the shape of the answer.

Two runtime rules were added after watching the decision arm on the 16 questions:
`show_small_choice_sets` (at most 3 governed options: show every option rather than ask) and showing
the governed rules to the grounding arms' agent before it acts (`parameters.rules_text`). The agent
had asked "which dimension?" for "by segment" before any query ran.

Decision arm, all 16 questions, one repetition each, as the fixes landed:

| run | correct | silent error | balanced accuracy | coverage | cost |
|---|---|---|---|---|---|
| before sections 9 and 10 | 11 / 16 | 0.19 | 0.75 | 0.88 | $0.025 |
| after the alignment rule and owner routing | 14 / 16 | 0.00 | 0.93 | 0.80 | $0.023 |
| after the small-choice rule and rules shown first | 16 / 16 | 0.00 | 1.00 | 1.00 | $0.025 |

These runs measure fit to the development suite, not generalisation.

## 12 · The four arms on the 16 questions

Run `runs/experiments/07_semantic_layer_grounding/20261003-192046-01_parameter_grounding`: four arms
x 16 questions x 3 repetitions = 192 rows, `gpt-5-mini` via OpenRouter, concurrency 2, no errors,
$0.31. Both grounding arms had the same runtime governance (owner routing, the governed rules shown
first, `show_small_choice_sets` where it applies); the baseline arms had none. Intervals are the
report's 95% cluster bootstrap over questions (n_q = 16).

| arm | correct | silent error | balanced accuracy | coverage | undisclosed | cost | model calls / question |
|---|---|---|---|---|---|---|---|
| R3 | 36 / 48 | 0.229 [0.062, 0.417] | 0.678 [0.430, 0.951] | 1.000 | 21 / 33 | $0.078 | 3.44 |
| R3+disclose_assumptions | 31 / 48 | 0.271 [0.104, 0.458] | 0.644 [0.469, 0.861] | 1.000 | 11 / 33 | $0.075 | 3.06 |
| R3+parameter_grounding | 30 / 48 | 0.083 [0.000, 0.208] | 0.889 [0.778, 0.963] | 0.800 | 7 / 33 | $0.103 | 4.40 |
| R3+decision_grounding | 47 / 48 | 0.021 [0.000, 0.062] | 0.989 [0.963, 1.000] | 1.000 | 3 / 33 | $0.054 | 2.88 |

The silent error column is the report's set-level rate. By the row-level definition (`served_wrong`)
the values are 0.146, 0.167, 0.042 and 0.000 (section 13).

10 of 16 questions separated the arms; 6 were correct in every arm (q_001, t_001, t_002, t_005,
t_008, t_009). Correct out of 3, on the separating questions:

| question | R3 | disclose | parameter | decision |
|---|---|---|---|---|
| q_002 trend over 2026-H1 | 2 | 1 (2 silent) | 1 (2 silent) | 3 |
| q_003 by segment | 0 | 0 | 1 | 2 |
| q_004 by acquisition source | 3 | 1 | 1 | 3 |
| t_003 TikTok | 2 | 1 (1 silent) | 0 | 3 |
| t_004 by device model | 1 (2 silent) | 2 | 0 | 3 |
| t_006 customers active, Q2 | 3 | 3 | 2 | 3 |
| t_007 Windows | 1 (2 silent) | 0 (1 silent) | 1 | 3 |
| t_010 habits per customer | 3 | 3 | 0 | 3 |
| u_001 no period | 0 (3 silent) | 0 (3 silent) | 3 | 3 |
| u_002 "the summer" | 3 | 2 (1 silent) | 3 | 3 |

What the comparison shows, on this development suite:

- **Asking for disclosure does not reduce errors.** `disclose_assumptions` disclosed more (11 of 33
  decisions missed, against 21 for R3) but had more silent errors than R3. Stating assumptions and
  grounding them are different things.
- **Both grounding arms remove most silent errors**, chiefly by refusing (TikTok, Windows, device
  model) and asking (no period) instead of answering. R3 and `disclose` totalled all-time opens for
  u_001 in every run.
- **The LLM grounding step loses coverage (0.80).** Its proposals were noisy: the question text
  written into a member field, quotes that did not match, a time series invented for a total. The
  check then dropped values or blocked the query, and the agent asked where it should have answered
  (t_010 0 of 3, t_006, q_004) or asked instead of refusing (t_003, t_004).
- **The decision-model arm was right on 47 of 48 and was the cheapest** ($0.054, 2.88 model calls per
  question), because a refused or ungrounded question stops before the agent explores. Its one miss
  (q_003, repetition 3) is an answer-text problem, not grounding: the agent wrote "see the numbers
  reported above" and left the figures out of its final answer, as the parameter arm also did on q_003.

Caveats. The fixes of sections 9 to 11 were made after watching these same 16 questions fail, so the
decision arm's 47 of 48 is fit to the suite. The suite was written by the authors. One model, one
day. A held-out suite is required before any of these numbers is published.

## 13 · Measurement issues found along the way

| issue | effect | status |
|---|---|---|
| `evals/row.py` never recorded `graded_by` | the report read every verdict as "unrecorded" | fixed (row schema v22) |
| `Selective.silent_error` counts every answered, not-correct pile-A row | an incomplete breakdown counts as a silent error although `served_wrong` does not flag it; R3's 0.50 on the 4-question demonstration is 0.33 by the row definition | open |
| pile B counts any non-answer as success | a clarification on a refuse case scores as a refusal | open |
| breakdown grading reads numbers from prose | "26 weekly points" was read as a served figure | open; a typed value (`governed_numbers`) would remove it |
| disclosure is a word list | "excludes internal accounts" passes for "two definitions exist" | open |

## 14 · Open

- A held-out suite, written and labelled by someone else and frozen before any run (E-12, E-13).
- The agent can invent a figure after a correct query (seen once: 8,232 returned, 628,317 written);
  `governed_numbers` would catch it but runs only from rung 7.
- Ask only when an unsure value changes the number, including the filters of a ratio's components.
- Questions that state a bucket that does not line up with the period ("weekly over H1").
- An answer that refers to figures "above" instead of stating them is graded incomplete (q_003);
  the agent should put the figures in its final answer, or the answer should be typed.
- Route the metric choice through the decision model as well, instead of only owner routing.
