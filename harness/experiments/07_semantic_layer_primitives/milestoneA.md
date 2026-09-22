# Milestone A: a model of query trust for agentic analytics

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
them. Experiment 07 does not yet have a component for this. The exp06 grader copied into
`fixture/run.py` computes divergence between readings, and can be adapted. For the first run, the
alternatives are computed once per question and recorded in the question file
(`expected.decisions[].alternative`).

## Agent reliability and answer trust

The model distinguishes two scopes.

| scope | decisions included | example |
|---|---|---|
| agent reliability | only the decisions the agent can select (filters, group-by, time grain, period) | the agent chooses `group_by = channel` |
| answer trust | every decision behind the number, including decisions fixed by the metric | `app_opens` fixes `is_internal = false`; the agent cannot change it |

`protocol/ground.py` measures agent reliability. The confident-wrong rate is a property of answer
trust, the wider scope. When a result is reported, it must state which scope it covers.

## Two measures

Two measures are needed. They are related but not the same.

| measure | what it counts | type |
|---|---|---|
| undisclosed-decision rate | answers containing at least one decision that changes the number and is not disclosed | process measure |
| confident-wrong rate | answers that state a wrong number as fact, without a caveat or a clarifying question | outcome measure |

The hypothesis is that reducing the first reduces the second. That is a claim to test. Defining the
confident-wrong rate as the undisclosed-decision rate would assume the result.

A third measure checks the disclosures themselves:

| measure | what it counts |
|---|---|
| basis accuracy | disclosed decisions whose stated basis is correct |

An incorrect basis is worse than no disclosure, because the answer appears grounded when it is not.
The q_004 run already contains an example (see "Known defects").

Disclosure must also be limited. If every default is disclosed, the reader stops reading the
disclosures, and a score that counts disclosures rewards verbose answers. The policy is to disclose
decisions that change the number, or that differ from what the reader would reasonably assume.

## What the components enforce

| component | file | what it enforces |
|---|---|---|
| parameter ontology (closed set) | `ontology/build_ontology.py`, `protocol/ground.py` | a dimension that does not exist cannot be expressed, because the tool schema lists dimensions as an enum; a member is free text, and `classify()` marks a non-existent member as invalid after the call |
| descriptions and model mapping | `protocol/ground.py` | the model maps the question's wording onto dimensions by reading their descriptions |
| governed principles | `spine/overlay.yaml`, `protocol/ground.py` | the model names a principle (`trend_granularity`, `canonical_segments`); the protocol applies its value, and the answer discloses it |
| structural safety | `protocol/structural.py` | the additivity check rejects summing a distinct count over time (June 2026 active users: 1,620 correct versus 3,310 summed by week) |
| divergence | not built in exp07; `fixture/run.py` (exp06 grader) | would detect whether plausible readings give different numbers |
| disclosure | `protocol/ground.py` | every decision carries a one-sentence disclosure |

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
   5. Measure the undisclosed-decision rate and the confident-wrong rate.

The overlay is the most concrete practitioner result. Its content is the list of things MetricFlow
and Cube cannot express but an agent needs: candidate sets, coverage, timezone, additivity per
dimension, defaults, conventions, and ownership.

## Measurement design

### Three arms

| arm | setup | what it isolates |
|---|---|---|
| A. raw agent | `fixture/observe.py`: the agent with `query_metric`, no protocol | the baseline |
| B. raw agent + disclosure instruction | arm A plus one instruction: "state every assumption and default behind the number" | the effect of asking for disclosure, without grounding |
| C. grounding protocol | `protocol/ground.py` | the effect of grounding |

Arm B is the control for arm C. If arm B closes most of the disclosure gap, the protocol's value is
in the quality of its grounding, not in the fact that it discloses. Arm B also measures basis
accuracy for free-text disclosure, which can then be compared with arm C.

`ground.py` takes the metric as an input (`--metric`). It does not select the metric. Questions that
test metric selection (t_001) therefore run in arms A and B only, unless arm C gains a
metric-selection step.

### Question set

The expected query, the basis of each decision, and whether the decision changes the number are
recorded in each question file under `expected`, before any run. Field definitions are in
`questions/README.md`.

| id | question | failure mode | derived from |
|---|---|---|---|
| q_001 | How many times did Android users open the app in June 2026? | none (total) | |
| q_002 | How did Android app opens change over the first half of 2026? | none (trend, grain left open) | |
| q_003 | How did Android app opens break down by segment in June 2026? | none (breakdown, dimension left open) | |
| q_004 | How did app opens break down by acquisition source in Q2 2026? | none (breakdown, synonym) | |
| t_001 | How many Android users were active in June 2026? | ambiguous metric (contested pair) | q_001 |
| t_002 | How many active Android customers did we have in the first half of 2026, week by week and in total? | additivity (sum of a distinct count) | q_002 |
| t_003 | How did app opens from TikTok compare with organic in Q2 2026? | member that does not exist | q_004 |
| t_004 | How did Android app opens break down by device model in June 2026? | concept not captured | q_003 |

The trap questions are derived from the clean ones, but they are not single-factor pairs. t_001 and
t_002 change the metric, because `app_opens` is additive and has no contested twin. The comparison
between the q and t sets is therefore a comparison of question classes, not a controlled pair.

The four q questions are a calibration set. They are answerable and unambiguous, so query
correctness is expected to be close to 100% in every arm. They measure disclosure, basis accuracy,
and run-to-run stability. The four t questions are where a wrong number is possible, so they are
where the confident-wrong rate can be measured.

### First run

8 questions × 3 arms × 3 repetitions on `gpt-5-mini` (t_001 in arms A and B only). Report the
numbers with n stated. Eight self-written questions are not evidence for a general claim. The run
tests the measurement method and gives a first reading.

## Known defects found during review (2026-09-22)

| defect | observed in | effect |
|---|---|---|
| `classify()` labels every non-principle decision "grounded in the question" without checking the stated basis against the question text | q_004: the model added `activity__is_internal = False` with basis "exclude internal and test accounts", a phrase not in the question, and it was labelled "grounded in the question" | a basis-accuracy failure is reported as grounded |
| the q_004 filter duplicates the filter `app_opens` already declares | q_004 | an unrequested predicate; the number does not change |
| `canonical_segments` expands to platform, region and channel even when the question already filters platform | q_003 | a group-by on platform returns one row; redundant, not wrong |
| the overlay phrase list maps "by device" to `activity__platform` | `spine/overlay.yaml` | `ground.py` does not read this list, but `select.py` does; t_004 ("device model") would be mislabelled there |

## Status

Have: the model, and the architecture demonstrated on four questions at one repetition each.
Missing: any measurement. Next: run the three-arm design above.
