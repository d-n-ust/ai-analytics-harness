# Milestone A: a model of query trust for agentic analytics

> Design record from 2026-09-22, kept as written. What was built and measured afterwards differs: see
> `findings.md` from section 11 and the experiment's `README.md`.

This document records the model that experiment 07 arrived at, so that the reasoning is not lost
between sessions. The components built in this experiment exist to enforce the rule stated in
"The rule" below. The model is preliminary: it is demonstrated on four questions and not yet
measured.

## The claim

A semantic layer governs the **metric definition**: the measure, its aggregation, and any filter the
metric declares. An answer, however, is produced by a **query**, and a query is a metric plus a set
of parameter decisions: filters, group-by dimensions, time grain, and period. Most of those
decisions are not governed by the layer.

> A governed metric does not make the answer governed. Matching the question to a governed metric
> settles one decision, which measure to use. The reliability of the answer depends on every
> decision in the query.

Semantic-layer vendors do not claim that a metric match is sufficient. The contribution here is
narrower and more concrete: a list of the query decisions that remain ungoverned, a way to classify
each one, and a way to measure how often an ungoverned decision changes the number without the
reader being told.

## The unit of analysis is the parameter decision

Each decision in a query is described by two independent properties.

**Basis: where did the value come from?**

| basis | meaning | example |
|---|---|---|
| question | the question states it | "in June 2026" gives `period = 2026-06` |
| governed declaration | the layer or its overlay declares it | `app_opens` declares `is_internal = false` |
| governed principle | a declared rule fills a gap the question leaves open | `trend_granularity` picks `week` for a six-month trend |
| none | nothing supports the value; it was assumed | a timezone that nothing declares |

The four bases are ordered by strength. A value stated in the question is stronger evidence than a
value filled by a principle, even though both are grounded.

**The basis decides the action.** This is the policy `parameter_grounding` enforces and the inspector
checks:

| basis | level | action |
|---|---|---|
| question | grounded in the question | proceed; the reader already knows the value |
| governed principle, governed declaration | grounded in a rule | proceed, and disclose the rule in the answer |
| none, and the answer depends on it | ungrounded | do not run the query; ask the user |

A value the question names but the layer does not have (TikTok as a channel) is a different case:
the question grounds it, nothing in the layer answers to it, and the action is to refuse.

**Visibility: was the decision disclosed to the reader?**

| visibility | meaning |
|---|---|
| disclosed | the answer states the decision and its basis |
| undisclosed | the decision was made, and the answer does not mention it |

The failure this experiment is concerned with is an **undisclosed decision that changes the
number**. It has two forms:

| form | example | why it is a problem |
|---|---|---|
| basis = none, undisclosed | an assumed timezone | an assumption is presented as fact |
| basis = governed, undisclosed | the `is_internal = false` filter on `app_opens` is not mentioned | the choice has a valid basis, but the reader cannot see that a choice was made |

### Where the question, the layer, and the agent each cause a problem

The earlier list of failure states mixed three sources. They are separated here because each is
detected differently.

| source | failure | how it is detected |
|---|---|---|
| question | underspecified: the question leaves a decision open ("by segment", no time grain) | model judgement, then a governed principle or a clarifying question |
| layer | ambiguous: two governed definitions match (`active_users` and `active_accounts`) | the overlay records the contested pair |
| layer | ungoverned: no declaration and no principle covers the decision (timezone) | only by listing the decisions the layer does not cover |
| agent | invalid member or dimension: a value that does not exist (`channel = tiktok`) | deterministic check against the closed set of members |
| agent | structurally invalid: a legal query with wrong arithmetic (summing a distinct count across weeks) | deterministic additivity check |

The layer-caused and question-caused failures are the ones the basis/visibility model describes. The
agent-caused failures are rule violations. A deterministic check can reject them, so they do not
need to reach the reader.

## The rule

> Every decision that **changes the number** must have a basis, and must be disclosed.

The condition "changes the number" is necessary. A decision with no basis is harmless if every
alternative value gives the same result. For example, a missing timezone rule does not matter when
all events are recorded in UTC and the period boundaries fall at midnight UTC. Without the condition,
every harmless default would be counted as a failure, and the measure would overstate the problem.

Deciding whether a decision changes the number requires computing the alternatives and comparing
them. Experiment 07 does not yet have a component for this; experiment 06's
`fixture/divergence.py` computes it for a contested pair and can be adapted. For the first run, the
alternatives are computed once per question and recorded in `01_parameter_grounding/cases.yml`
(`decisions[].alternative`).

## Agent reliability and answer trust

The model distinguishes two scopes.

| scope | decisions included | example |
|---|---|---|
| agent reliability | only the decisions the agent can select (filters, group-by, time grain, period) | the agent chooses `group_by = channel` |
| answer trust | every decision behind the number, including decisions fixed by the metric | `app_opens` fixes `is_internal = false`; the agent cannot change it |

`ground.py` measures agent reliability. The silent error rate is a property of answer
trust, the wider scope. When a result is reported, it must state which scope it covers.

## Measures

The headline measures are the shared grader's, so a result here sits on the same axis as
experiments 01 to 06:

| measure | what it counts |
|---|---|
| silent error rate | answers that state a wrong number as fact, with no caveat, refusal or clarifying question |
| balanced accuracy | the mean of per-pile accuracy over the piles present: answerable, unanswerable, contested |
| coverage | the share of answerable questions the agent answers rather than declines |

The secondary measure is disclosure:

| measure | what it counts | grading |
|---|---|---|
| undisclosed-decision rate | answers with at least one labelled decision that changes the number and is not disclosed | the decision's fixed `disclose_words`, matched in the answer text of every arm; prose-graded, so reported as unaudited (E-26) |
| basis accuracy | disclosed decisions whose stated basis is correct | R3+grounding only, from its structured record: is the quoted basis phrase in the question |

The hypothesis links the two: lowering the undisclosed-decision rate lowers the silent error rate.
That is a claim to test. Defining one as the other would assume the result.

The same word list is applied to every arm's answer text. A disclosure the grounding step records
but does not pass into the answer text does not count, because the reader never sees it. A typed
`decisions` field on every arm's answer was considered and rejected for now: offering the field would
itself prompt the R3 arm to disclose, so R3 would no longer be the baseline.

An incorrect basis is worse than no disclosure, because the answer appears grounded when it is not.
The q_004 run already contains an example (see "Known defects").

Disclosure must also be limited. If every default is disclosed, the reader stops reading the
disclosures, and a score that counts disclosures rewards verbose answers. The policy is to disclose
decisions that change the number, or that differ from what the reader would reasonably assume.

## What the components enforce

| component | file | what it enforces |
|---|---|---|
| parameter surface (closed set) | `ontology/src/ontology/parameters.py`, `ground.py` | a dimension that does not exist cannot be expressed, because the tool schema lists dimensions as an enum; a member is free text, and `classify()` marks a non-existent member as invalid after the call |
| descriptions and model mapping | `ground.py` | the model maps the question's wording onto dimensions by reading their descriptions |
| governed principles | `fixture/governance.yml`, `ground.py` | the model names a principle (`trend_granularity`, `canonical_segments`); the protocol applies its value, and the answer discloses it |
| additivity | `engine/src/agent/core/measure.py` | classifies each aggregation as additive, semi-additive or non-additive; summing a distinct count over time is rejected (June 2026 active users: 1,620 correct versus 3,310 summed by week) |
| divergence | not built in exp07; experiment 06's `fixture/divergence.py` | would detect whether plausible readings give different numbers |
| disclosure | `ground.py` | every decision carries a one-sentence disclosure |

`ground.py` is a prototype. It moves into `engine/src/agent` as the `R3+grounding` variant, so that it
runs through the shared runner and is recorded by `evals/row.py`.

The design lesson from q_003: enforce closed facts (existence, additivity) with deterministic code,
and leave open semantics (what "by market" means) to the model, checked against descriptions. Fixed
phrase tables were brittle. q_003 became stable only after the rule mapping "how did" to a trend was
removed.

## Outputs of the experiment

1. **A model of query trust.** A governed metric does not make the answer governed. Each decision
   has a basis and a visibility. The rule: every decision that changes the number has a basis and is
   disclosed.
2. **An architecture** that grounds each decision or flags it.
3. **Practitioner steps:**
   1. Model each metric's parameter surface, with a description for every dimension.
   2. Declare the governance the semantic layer does not express: defaults, conventions, additivity
      per dimension, coverage, timezone, candidate sets for ambiguous terms, and owners. This is the
      overlay.
   3. Ground each decision in the question, a declaration, or a principle. Otherwise flag it.
   4. Enforce closed facts deterministically. Let the model do the open mapping.
   5. Measure the silent error rate, and the undisclosed-decision rate beside it.

The overlay is the most concrete practitioner result. Its content is the list of things MetricFlow
and Cube cannot express but an agent needs: candidate sets, coverage, timezone, additivity per
dimension, defaults, conventions, and ownership.

## Measurement design

### Three arms

Arms are agent variants on the same rung, named as experiment 06 names them. The letters A, B and C
are not used: across this repository they mean absent, prose and declared.

| arm | setup | what it isolates |
|---|---|---|
| `R3` | the agent at rung 3, with `query_metric` over the MetricFlow layer | the baseline |
| `R3+disclose` | `R3` plus one instruction: "state every assumption and default behind the number" | the effect of asking for disclosure, without grounding |
| `R3+grounding` | `R3` plus the grounding step | the effect of grounding |

`R3+disclose` is the control for `R3+grounding`. If it closes most of the disclosure gap, the grounding
step's value must show in the headline measures, not in disclosure.

The grounding step takes the metric as input. It does not select the metric. The contested cases,
which test metric selection, therefore measure `R3` and `R3+disclose` only, unless the step gains
metric selection.

### Question set

`01_parameter_grounding/cases.yml` holds 14 questions in the shared case format, with a `gold_sql`
against the raw source tables for each, proven against the governed marts before authoring (E-14).
Each case also labels its decisions: value, basis, whether the decision changes the number, the
number under the alternative, and the words that count as disclosing it.

| pile | ids | failure mode |
|---|---|---|
| answerable, calibration | q_001 to q_004 | none: a total, a trend, a breakdown by an unnamed dimension, a breakdown by a synonym |
| answerable, trap | t_002, t_006 | a distinct count that must not be summed over time |
| answerable, trap | t_009 | a member reachable only through the dimension description ("SEO" is content_seo) |
| answerable, trap | t_010 | a governed ratio that must not be averaged over months |
| unanswerable | t_003, t_007 | a member that does not exist (TikTok, Windows) |
| unanswerable | t_004 | a dimension that does not exist (device model) |
| unanswerable | t_008 | a period outside coverage (June 2025) |
| contested | t_001, t_005 | two governed definitions, no consumer named |

Ten traps meet the golden-path minimum of ten discriminating items. The traps are derived from the
calibration questions but are not single-factor pairs, so a comparison between the two groups is a
comparison of question classes. All 14 were written by the experiment's authors, so this is a
development suite (E-12).

Two case-format extensions are needed before the suite loads: a `breakdown` expectation for q_002 to
q_004, and the `decisions` block. Both are added with the runner.

### Order of work

Following `docs/GOLDEN-PATH.md`: move the grounding step into the engine and add the two variants;
add the case-format extensions; `./bench gate`; a small run of two questions on two arms at one
repetition; then 14 questions × 3 arms × 3 repetitions on `gpt-5-mini` at concurrency 2.

## Known defects found during review (2026-09-22)

| defect | observed in | effect |
|---|---|---|
| `classify()` labels every non-principle decision "grounded in the question" without checking the stated basis against the question text | q_004: the model added `activity__is_internal = False` with basis "exclude internal and test accounts", a phrase not in the question, and it was labelled "grounded in the question" | a basis-accuracy failure is reported as grounded |
| the q_004 filter duplicates the filter `app_opens` already declares | q_004 | an unrequested predicate; the number does not change |
| `canonical_segments` expands to platform, region and channel even when the question already filters platform | q_003 | a group-by on platform returns one row; redundant, not wrong |

## Status

Have: the model; the grounding prototype, demonstrated on four questions at one repetition each; a
14-question suite with proven oracles. Missing: any measurement. Next: the order of work above.
