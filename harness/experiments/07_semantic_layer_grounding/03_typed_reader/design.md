# Typed reader: design (draft 3, 2026-10-09)

A new question reader for `decision_grounding`, built beside the current one. It produces the same
reading as today, so the call check, the planner and the answer gates do not change. Draft 1 was
reviewed by five experts (question-to-SQL architecture, agentic-systems architecture, test design
with measurement validity, semantic modelling with data governance, and the challenger); section 12
lists what changed and why. Draft 3 makes the closed world strict (the owner's decision).

## 0. The idea this serves

For each metric, the parameters that must be set to query it; for each parameter, a closed world of
allowed values, so that the value is found deterministically. For `app_opens`:

| parameter | closed world | how the value is found |
|---|---|---|
| metric | governed metrics and their declared words (`meta.terms`) | lookup |
| platform filter | values read from the data; word table; groups (`mobile`: android, ios) | lookup, set operations |
| region, country, channel filters | values read from the data; words; country under region | lookup, set operations |
| staff filter | fixed by the metric's definition | not a choice |
| period | the calendar (date table) and the dates the data covers | calendar arithmetic, coverage |
| time grain | day, week, month, quarter, year; the trend rule when none is stated | lookup or rule |
| breakdown | the metric's dimensions, time, the standard-breakdown rule | lookup or rule |

The parameter surface is built today by `ontology.parameters.build`. The one step that cannot be
deterministic is reading which words of the question refer to which parameter. This design is about
making that step as small as possible and checking it, while everything else stays a lookup.

**Strict closed world.** A number is served only when every parameter value comes from the closed
world. A word outside it is never given a meaning by a model; the model may only help word the
question back ("Did you mean android?") or the refusal.

## 1. Why

The current reader (`agent/guardrails/decisions.py`, `read` and `_questions`) asks the decision model
a questionnaire generated from the layer: for every dimension, how the question restricts it and
whether it names each value; for every month, quarter and half-year, whether the question names it.
Code assembles the answers with confidence thresholds.

Five of the problems found in the readiness audit come from this format. Two others (D11, a grain
constant; D13, the engine widening a period to whole buckets) do not, and were fixed elsewhere.

| problem | cause in the format | patch added in stage 6 |
|---|---|---|
| "every platform except web" refused as a missing channel (D4) | every dimension judges every word | an exclusion-phrase mask built from a word list |
| a group word as one figure, and its complement | answers are per value; the format cannot express a group. In the controlled test, the arm where the model reads the word table returned "mobile" as one figure 0 of 12 times and failed 6 of 6 complements. Production passes only because code overrides the model | a code lookup that overrides the model |
| "week by week" split 0.62 / 0.30 between trend and breakdown by time (D7) | two options with the same meaning | P(trend) + P(breakdown) × P(by time) |
| "summer 2026", "2024", "October 2025 to June 2026" | a period exists only if it is in the offered list | a wider list; seasons, years and ranges are still impossible |
| a prose fact does not reach the per-value questions (controlled test) | each per-value question shows one clause of the description | none |

The questionnaire also grows with the layer: each value and each period adds a judgement.

It has one property worth keeping: **every judgement carries a probability, and an unsure judgement
becomes a question to the user.** Draft 1 lost this. Its extractor made forced choices (keep or
exclude, total or series, which period) with no confidence, and its verifier checked only
restrictions. Draft 2 keeps the property by confirming each extracted judgement (section 5).

Lessons from the earlier arms (findings.md):

| finding | consequence here |
|---|---|
| Exact quote matching rejected 11 of 18 legitimate quotes; a rejected quote dropped a requested trend, and the agent then served invented figures (section 8; the 33 test pairs are not in the repository) | a quote is never dropped; the quote check is not trusted as evidence of a role (it confirms that words occur, not what they do) |
| The decision model chose among closed options well: 18/18 values including "Andriod" and "SEO", on 20 questions with labels written by the authors; "not in the layer" rests on 2 items (section 11) | the decision model confirms closed judgements; its suggestion role is new and is measured separately |
| GLiNER found 35 of 37 value phrases, 0 of 4 structural requests (section 11) | structure needs a general language model |
| A reading that claimed completeness made the agent miss what it missed (section 19) | every open point is a typed outcome; nothing unresolved is presented as settled |

## 2. Principle: propose, then confirm; code does everything with a rule

| step | who | what |
|---|---|---|
| 1. propose | a general language model, structured output, no knowledge of the layer | marks which words do what, and writes each time expression in a typed form |
| 2. account | code | every declared word and every date word in the question must be covered by the proposal |
| 3. resolve | code | word tables, set operations, calendar, coverage, rules |
| 4. suggest | the decision model, closed choice | only for a word no table has: what to say back; never applied |
| 5. confirm | the decision model, yes/no per judgement | each judgement the proposal made, with a probability |

Three rules:

1. **Every unresolved or unconfirmed element ends in a typed outcome** that quotes the words it is
   about. No silent default, no dropped element.
2. **Every meaning comes from the closed world.** A word, a group, an exclusion, a default or a
   season resolves only through a declaration. A word no declaration has is asked about.
3. **One idea, one field.** A series is one field with a unit, so equivalent readings cannot split.

## 3. Step 1, the proposal (model output, schema-validated)

One structured call (a forced tool call) with the question only. The extractor sees no dimension
names and no values; it is taught by examples from an unrelated domain. Its output therefore depends
on the question alone: it is computed once per question, shared by every metric, and replays after a
layer change without a new request.

```
figures:   [{terms: [{quote, keep: bool}]}]     # one item = one figure; terms are combined with AND
time:      [{quote, value: TIMEX3}]             # several items = a comparison
series:    {quote, unit: day|week|month|quarter|year|null} | null
breakdown: [{quote}]
premise:   {quote, about: quote} | null         # something stated as already true ("now that X stopped")
```

`TIMEX3` is the TimeML value format: `2026-06`, `2026-Q2`, `2026-H1`, `2026`, `2026-SU` (season),
an interval of two of them, or one of the relative names the warehouse already resolves
(`warehouse.config.NAMED_PERIODS`, by `resolve_period` against `ANALYSIS_DATE`). Anything else is
`unplaceable`. A negation word is never inside a quote: "non-mobile" is the quote "mobile" with
`keep: false`.

| question | figures | time | series |
|---|---|---|---|
| "App opens in June 2026 on every platform except web" | `[{terms: [{web, false}]}]` | `2026-06` | null |
| "Mobile app opens, March 2026" | `[{terms: [{mobile, true}]}]` | `2026-03` | null |
| "Android vs iOS opens in May 2026" | `[{terms: [{Android, true}]}, {terms: [{iOS, true}]}]` | `2026-05` | null |
| "Android and iOS opens together in May 2026" | `[{terms: [{Android, true}, {iOS, true}]}]` | `2026-05` | null |
| "Android users from referral, except staff" | `[{terms: [{Android, true}, {referral, true}, {staff, false}]}]` | — | null |
| "Android opens month by month, first half of 2026" | `[{terms: [{Android, true}]}]` | `2026-H1` | `{unit: month}` |

Terms on one dimension inside one figure are combined by set operations ("mobile except iOS" =
android). Terms on two dimensions are combined with AND.

## 4. Steps 2 and 3, accounting and resolution (code only)

**Accounting (recall check).** Code scans the whole question for every declared value word, domain
word and date expression (month and season names, years, quarter and half forms), as `claimed()`
does today. Each hit must fall inside a proposed quote. A hit outside every quote triggers one
re-extraction that names the uncovered words; if they are still uncovered, the outcome is
`quote_unaccounted` (ask). This check does not depend on the model. It is the tractability
condition of PRECISE: every content word maps to one element or the question is not answered as is.

**Quotes.** Each quote must occur in the question (the tolerant matcher in `parameters.py`). A quote
that does not occur triggers one re-extraction, then `quote_not_found` (ask). The match confirms that
the words occur; their role is confirmed in step 5.

**Values.** A term's quote is looked up in the word table of every value domain in scope (section 8):
normalised tokens, plural ignored, longest phrase first. Misspellings are not matched by edit
distance; they are stored as hidden labels, or end in `word_unknown` with a suggestion.

| lookup result | outcome |
|---|---|
| one domain, one value | resolved |
| a group value ("mobile") | its members, by `broader`, as one set |
| words left over ("Google" in "Google Android phones") | `word_unknown` (ask, naming the words; section 6) |
| the word is in two domains | `ambiguous_value` (ask, naming both) |
| nothing found | `word_unknown` or `unlisted_value` (section 6) |

`keep: false` takes the complement inside the domain; the complement of a group needs every value to
have a parent, which the declarations guarantee. A dimension the metric's own filter fixes keeps
today's rule (`_fixed_by_metric`). A dimension the question does not mention is not restricted;
today's `determines` logic is no longer needed, because no dimension is restricted unless a word
resolves to it.

**Shapes the reading cannot carry (phase 1).** Today's reading holds one list of values per dimension,
and the call check crosses them. Two cases cannot be represented and end in `figures_not_representable`
(ask): figures that differ in more than one dimension ("Android from referral vs iOS from SEO"), and
`keep: false` on a combination of two dimensions. Several figures with several time items are crossed
when the question is a comparison of the same figures over periods, and asked about otherwise.

**Time.** Code turns each value into a date interval. Calendar periods come from the calendar;
seasons from the date table (section 8), and `season_undeclared` (ask) when it has none; relative
names from `resolve_period`; `unplaceable` asks, showing the coverage. Coverage: no day inside the
data, `out_of_coverage` (refuse); partly inside, today's policy (refuse) for the head-to-head (section
11, question 4); inside, applied. No time item: `period_missing` (ask). A range is handed to the call
check as `start` and `end`, which `query_metric` and `check._span_of` already accept; `period` stays
a named period.

**Series and grain.** `series.unit` sets the grain; a null unit takes the trend rule; bucket edges
follow D13. A series adds `metric_time` to `group_by`.

**Breakdown.** A breakdown quote is looked up in the domain words (the dimension's names) and in the
synonyms of the group-by rule ("segment" for `canonical_segments`). Not found:
`dimension_not_supported` (refuse), with a suggestion when one dimension is close (section 6).

**Premise.** `about` resolves as a value and goes to today's premise check (a governed query).

## 5. Step 5, confirmation (the decision model, one request)

Each judgement the proposal made becomes a yes/no question about the question, built by code from
the resolved reading:

| judgement | example question |
|---|---|
| each term's polarity | "Does the question leave out web?" |
| figure grouping, when a figure has two terms on one dimension | "Does the question ask for Android and iOS as one combined number?" |
| shape | "Does the question ask for one number per month?" / "for a single number?" |
| each time item | "Does the question ask about June 2026?" |
| each breakdown | "Does the question ask to split the number by region?" |
| beyond (today's residual question) | "Does the question also narrow what is counted by something this reading leaves out?" |

Every question is asked in one request. Below 0.7 on a judgement, or at 0.7 or above on **beyond**:
`reading_unconfirmed` (ask, naming the judgement). The confirmation can only add a question; it never
adds or removes a value. Parts supplied by declarations or rules (the complement's `unknown`, the
standard breakdown, the trend grain, the metric's own filter) are labelled as governed and are not
asked about.

This keeps the questionnaire's property where it matters: the questions are about the few judgements
this question needs, not about every value of the layer.

## 6. Step 4, suggestions (only for words no table has)

The closed world has no entry for the word, so no number is served for it. The decision model only
decides **what the analyst says back**. Given the question, the quote and the values of every domain
in scope, it chooses among: each value as **the same thing**; "a {dimension} value the layer does not
have", once per dimension; and "something else".

| suggestion | what the analyst says |
|---|---|
| the same thing as one value, p ≥ 0.7, no other option ≥ 0.15 | `word_unknown` (ask): "Did you mean android?" |
| a value the layer does not have, for one dimension, p ≥ 0.7 | `unlisted_value` (refuse): "There is no TikTok channel. The channels are …" |
| anything else | `word_unknown` (ask), offering the plausible values, or none |

When the user confirms a suggestion, the pair goes to the proposals table (section 8) for the owner;
only an accepted row enters the word table. A misspelling the owner expects to recur is stored as a
hidden label. The model's choice changes the wording of a non-answer and nothing else.

## 7. Outcomes

| outcome | action | type in prior taxonomies |
|---|---|---|
| `quote_unaccounted`, `quote_not_found` | ask | — |
| `word_unknown` | ask, with a suggestion when there is one | PRACTIQ ambiguous / nonexistent value |
| `ambiguous_value` | ask | PRACTIQ ambiguous value |
| `unlisted_value` | refuse | PRACTIQ nonexistent value |
| `dimension_not_supported` | refuse | PRACTIQ nonexistent column |
| `figures_not_representable` | ask | AMBROSIA scope |
| `season_undeclared`, `period_unplaceable`, `period_missing` | ask | AmbiSQL temporal granularity |
| `out_of_coverage` | refuse | — |
| `reading_unconfirmed` | ask | — |
| `no_causal_evidence`, `false_premise` | refuse | AmbiSQL false premise |

**Failures of the reader itself.** Extractor timeout, server error, or output invalid against the
schema after one retry: `ReadingUnavailable`, so the run falls back to the plain agent and says so,
as today. A suggestion or confirmation failure after a valid extraction: ask. A configuration fault
(no key, unknown model) is a hard error, as in `_ask` today.

## 8. Declarations (the layer side)

Words are keyed by a **value domain** (ISO/IEC 11179), the list of allowed values a dimension draws
from, not by the dimension's name: `channel` appears in two semantic models with different
descriptions, `region` in two. Each semantic dimension names its domain (`config.meta.value_domain`).

```
seeds/value_domains.csv       value_domain, label, steward, parent_domain
seeds/permissible_values.csv  value_domain, value, label, definition, broader
seeds/value_words.csv         value_domain, word, value, label_type (alt|hidden), warrant (owner|user), added_on
seeds/domain_words.csv        value_domain, word
value_word_proposals          value_domain, word, proposed_value, p, question_id, status, decided_by, decided_on
```

- **A group is a value.** `mobile` is a value of a `device_type` domain; `android` and `ios` point
  to it through `broader` (SKOS). Each word maps to exactly one value, so a group and a collision can
  no longer look the same.
- **Region is a group over country**, by the same pattern. Staging joins the table instead of the
  CASE in `stg_users.sql`, which today emits `Other`, a value no description lists. The channel code
  mapping (`ppc`, `ref`) moves into the same reference data.
- **Every allowed value has a label and a definition** (replaces `value_meanings.csv`, which listed
  only unclear values, so "done" and "missing" looked the same).
- **Calendar.** Seasons and any fiscal periods are columns of the date table, which extends beyond
  the data. Governance keeps the reference-date rule (`ANALYSIS_DATE`), the hemisphere, and the year
  a winter belongs to.
- **Tests run in the build:** unique (domain, normalised word); a word in two domains is a warning
  that feeds `ambiguous_value`; relationships from words and from mart columns to the allowed
  values; `broader` not null where a domain has a parent.
- The group-by rule's words use the key the metric terms already use: `synonyms:`.

This replaces the two tables chosen for D1 (`value_words` keyed by dimension, `value_meanings` for
unclear values only). The data-modelling expert's earlier `device_class` suggestion is this model.

What the readiness audit then checks: every dimension in scope has a domain; the mart's values are a
subset of the allowed values; every value has a definition; every group is declared and every child
has a parent; every domain has a steward; the share of value mentions resolved by the tables versus
questions back; the calendar extends beyond the data; each test runs.

## 9. Integration

- New package `agent/guardrails/reader/`: `propose.py` (model), `account.py`, `resolve.py`,
  `calendar.py` (pure), `suggest.py` and `confirm.py` (decision model).
- One entry with today's signature and return, `reading_for(...) -> (reading, cost)`. The proposal is
  cached per question and runs beside `question_level`; resolution runs per metric.
- The guardrail option `typed_reader` selects it (cell `R4+decision_grounding+typed_reader`). The
  metric choice is unchanged in phase 1.
- Stored with the reading: the proposal, every suggestion and confirmation request with its exact input
  and answers. Replay recomputes code steps and reuses a stored answer only when its input is
  identical; otherwise it marks the reading stale, as `residual_stale` does today.
- The proposal model is configurable, is not the agent's model, and is chosen on the development
  wordings.

## 10. Plan and evaluation

**Spike first (the largest risk is a silent omission by the proposal).** Build the proposal, the
accounting check and the confirmation only. Run them on `tests_dev.yml`, `controlled_items.yml` and
the red-team suites, with extraction labels written before the run. Count per field: omissions,
omissions caught by accounting, omissions caught by confirmation, and false asks on items labelled
as answers. Build the rest only if omissions that pass both checks are near zero.

**Then:** declarations (section 8), resolvers with unit tests and no model, the suggestions.

**Input domain model and coverage.** Characteristics: restriction form, number of restricted
dimensions, time form, coverage, number of periods, series, breakdown, premise (blocks as in the
test-design review). Criterion: base choice from "Android app opens, June 2026", plus pair-wise for
restriction form × figure count, time × coverage, series × time, breakdown × a restriction on the
same dimension; each error block once. Untested today: restrictions on region, country and channel;
separate figures; two-dimension figures; ambiguous words; year, range, relative and current periods;
declared seasons; period comparisons; partly covered months; quarter and year series; premises;
groups no dimension holds. A development extension set covers these.

**Grader fixes, before any comparison:** one figure versus several (the label says which); "no
filter" kept as an explicit value inside a list of readings; a breakdown's served values must match
the restriction, and series buckets must lie inside the period; grain graded where the label states
it; ranges accepted by `_months`. Stored rows are regraded at no cost.

**Comparison.** Pre-registered before any sealed run: primary outcome per reading (correct, silent
wrong, safe miss, wrong refusal or ask); adoption rule: silent wrong no higher, and correct lower by
at most one intent; 3 repetitions; metric-choice intents reported apart (both readers share them).

**Sealed sets.** The current sealed set was written before stage 6, but its intents file was in the
implementer's context during stage 6 and while this design was written. Its wordings are unseen, so it
measures robustness to wording, not generalisation to new requests. Before its single use: the
"mobile phones" intent is relabelled to the owner's decision (one figure, android and ios), with the
old label reported as secondary; the "except the website" intent is reported as a separate slice.
A **replication sealed set** is built by the same procedure, from new intents written by an author
who has seen neither the fixes nor this design, with only its hash committed until the run. The
adoption decision is taken on the replication set.

## 11. Open questions, as answered by the review

| question | answer |
|---|---|
| Should the proposal see dimension names? | No, nothing about the layer (all reviewers). |
| Apply a 1:1 link or ask? | Never apply: strict closed world (owner's decision, draft 3). The model only suggests what to ask |
| Is `quotes` + `keep` enough? | Yes, with `keep` per quote and AND inside a figure; no nesting |
| Partly covered periods | Refuse during the head-to-head, so only the reader changes. Afterwards: ask, offering the covered interval; a series answers its covered buckets with a disclosure; comparisons, growth and distinct counts refuse |

## 12. Changes from draft 1

| change | raised by | reason |
|---|---|---|
| confirmation of every judgement (section 5) | challenger, architect | draft 1's forced choices had no probability; a dropped series or a flipped polarity passed every check |
| accounting check in code | NL-to-SQL, architect | a declared word the proposal leaves out would silently restore D2 |
| `keep` per quote; negation outside the quote | NL-to-SQL, challenger | "except staff" inside a figure; "non-mobile" |
| linker relation types, rival threshold, per-dimension "does not have" options, restricted leftover choice | NL-to-SQL, architect, governance, challenger | "Europe" to EMEA, "Facebook ads" to paid search, "Google" as a channel |
| `figures_not_representable` | architect | the reading contract crosses dimensions |
| ranges as `start`/`end`; relative names only from `resolve_period` | architect, NL-to-SQL | `period` strings are read in seven places; replay must not depend on the day |
| failure contract | architect | not defined in draft 1 |
| `measure`, `premise.kind`, `other` removed | architect | nothing read them; `other` made the field choose between refuse and ask |
| value domains, groups as values, permissible values, proposals, calendar in the date table, tests in the build | governance | a group and a collision looked the same; words keyed by a name used twice; tests never ran |
| spike first; pre-registered rule; grader fixes; replication sealed set | architect, test design | the comparison had no decision rule, and the sealed set is contaminated |
| strict closed world: the linker only suggests; section 0 states the parameter framing | owner (draft 3) | the original idea: every value is found deterministically in a closed world |
| section 1 wording | challenger | "every fragility" was wrong; the controlled-test row described an arm, not production |
