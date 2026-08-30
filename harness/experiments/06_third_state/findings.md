# Experiment 06 — findings

The standing record for the third state. Every number here traces to a stored row under
`fixture/*.json`; where a claim rests on something not measured, it says so.

**Status: preliminary.** One question, one fixture. This establishes mechanisms and directions, not
rates. The noise band it would be read against does not exist yet.

---

## The fixture

One question, and deliberately the most ordinary one anyone asks an analytics system.

> How many active users did we have last week?

Two governed definitions answer it, and both are right:

| | value | owner | consumer |
|---|---:|---|---|
| excluding internal and test accounts | **886** | Product | the weekly product review, the North Star tree |
| including them | **919** | Platform | capacity planning, the support-volume forecast |

**Irreducible by construction.** The case schema requires an `owner` and a `consumer` for every
candidate, because a definition nobody owns and nothing consumes is a leftover — reducible, deletable
offline, and therefore experiment 05's finding rather than this one's. Neither of these can be
deleted without breaking a real report, so no offline repair collapses them.

**The dose, measured.** The two disagree on 11 of 12 slices, between 0.00% and 5.17%, and by 3.72%
on the week as a whole. Sign is consistent, so neither is a data error.

**Agreement with the detector, measured separately.** The candidates in `cases.yml` were written by
reading the layer. preflight 0.4.0 reads the same layer independently and reports exactly one
finding, HIGH, naming the same pair. One of one. The two passes stay separate because a detector
that writes the ground truth and then enforces it is marking its own homework.

---

## 1 · The headline

| | attempts | clarified | silent errors |
|---|---:|---:|---:|
| **everything advisory** | **217** | **16** | **201** |
| **the enforced gate** | **15** | **15** | **0** |

All 16 advisory clarifications came from one model on one layer. See §3.

This is the R3-over-R6 pattern from the reliability ladder reproduced on a new failure: the
enforced version of a check was the best value in the whole ladder, and the advisory version
(`transparency`) enforced nothing and contributed nothing.

---

## 2 · Everything advisory that failed

Each row holds the layer and the model fixed and changes one thing.

| what was tried | attempts | clarified |
|---|---:|---:|
| no clarify tool at all | 3 | 0 |
| a prose clarify tool | 13 | 0 |
| a **typed** clarify tool — coded reason, named candidates | 19 | 0 |
| the rule written into the prompt (*refuse when nothing answers, clarify when more than one does*) | included above | 0 |
| **renaming** so neither metric matches the question | 8 (gpt-5-mini) | 0 |
| **reordering** the catalogue | 8 | 0 |
| **compact catalogue** — the two descriptions on adjacent lines instead of five apart | 32 | 0 |
| **transparency** — the compiled SQL and scope line on every result | 20 | 0 |

**Transparency is the strongest of these nulls** and the one most worth recording. The result the
agent read contained, verbatim:

```sql
... FROM wh_06.fct_user_days ... ) subq_4 WHERE activity__is_internal = false
```

The discriminator was in the output it had just received, not in a catalogue it skimmed, and it
still served the number without comment. Mechanism confirmed to have fired before the null was
recorded.

---

## 3 · The one thing that moved it, and why it is not a solution

`gpt-5.6-sol`, and only where the question's own wording matches no metric name:

| layer | the metric it would pick is called | matches the question | clarified |
|---|---|---|---|
| `baseline` | `active_users` | **exactly** | **0 / 10** |
| `crossed` | `active_customers` | partially | **1 / 10** |
| `no_exact_match` | `active_customers` vs `active_accounts` | **neither** | **10 / 10** |

And it asks a good question when it asks:

> *Should "active users" exclude internal and test accounts (customer activity), or include them to
> represent total platform load?*

**But it needs both the model and the naming.** On the same `no_exact_match` layer,
`gpt-5.6-terra` clarified 0/10 and `gpt-5-mini` 0/10. This is an interaction, not a main effect.

Two conclusions follow, and they are the practitioner findings:

**Scale does not buy this.** Three models, two of them large; one of them behaves correctly, under
one condition.

**Naming does not buy it either — and good naming makes it worse.** A metric named exactly what
users call the concept is what suppresses the question. `active_users` against a question saying
"active users" produced 0/10 from the one model capable of noticing. That is precisely the naming
every governance guide prescribes.

Neither is a foundation to build on: the behaviour depends on an interaction between the model you
happen to be running and the words your user happens to type.

---

## 4 · The name selects the metric; the description is not consulted

Four presentations of the same two definitions — identical measures, filters, values, owners and
consumers. Only the labels move.

| variant | 886 is called | 919 is called | served |
|---|---|---|---|
| `baseline` | `active_users` | `active_accounts` | **886** |
| `no_exact_match` | `active_customers` | `active_accounts` | **886** |
| `reversed` | `active_users` *(declared second)* | `active_accounts` *(first)* | **886** |
| **`crossed`** | **`real_customers`** | **`active_customers`** | **919** |

The word "active" moved from one definition to the other and the answer moved with it. On the
crossed layer it served a count that **includes staff and test logins** for a question about users,
from a metric whose own description says it is about load rather than customers.

**It knows, and does not show.** Asked to *compare* the two definitions rather than to answer, the
same model on the same layer clarifies, names both candidates and states the discriminator exactly.
The knowledge is available; the answering path does not use it. This is *Knowing but Not Showing*
(arXiv 2605.25284) reproduced within-subject on a governed layer.

---

## 5 · The enforced gate

`ambiguity_check`, at position `BEFORE`. Every governed call is looked up in an index beside the
layer; a call naming a contested metric is refused before it runs.

**15 of 15, both layers, both namings, silent error 1.00 → 0.00.**

**The block hands over the decision brief rather than pointing at it** — decided by §4, since an
agent that does not read descriptions on the answering path will not go and look one up:

```text
BLOCKED — 'active_users' is not the only governed definition of what it measures:
'active_accounts' answers the same question and returns a different number for this exact
request (886 against 919, 3.72% apart). They differ by is_internal = false. Do not pick one
and do not average them. End with `clarify`, naming both in `candidates`, and ask the user
about is_internal = false in their own words.
```

**The reason code is now correct.** Both voluntary clarifications recorded before the gate filed
`underspecified_request`; every gated one files `competing_definitions`. Naming the collision fixed
the classification too.

### Sensitivity, not membership

The gate fires on whether the reader would receive a **different number for this call**, not on
whether the metric has a competitor. It executes each competitor with the same arguments.

| the call | verdict |
|---|---|
| `active_users`, last week | **BLOCKED** — 886 against 919, 3.72% apart |
| `active_users`, `platform = web` | **BLOCKED** — 277 against 289, 4.33% apart |
| `active_users`, `platform = unknown` | **allowed** — both readings return the same number |
| `value_moments`, last week | allowed — no competitor |

Membership alone would have fired on **40.3%** of the frozen suite's metric-declaring answers, most
of them diagnostics — the brief's own falsification condition, met by arithmetic.

**The threshold is zero, and the zero is argued.** The instinct is to ignore small divergences and
it is backwards: danger runs *inverse* to magnitude, because a figure a few tenths of a percent from
its sibling is the one no reader and no range check catches. "Does not matter" means *identical*,
not *close*. A non-zero threshold is the brief's "divergence threshold" lever — worth measuring, not
a default.

---

## 6 · What was built

| | where |
|---|---|
| `preflight index` — writes the ambiguity index a runtime gate looks names up in | preflight, `wt-cluster_index` |
| `clusters.py` — loads it, verifies the fingerprint, refuses on staleness | `semantic/src/semantic/` |
| `ambiguity_check` — the gate | `engine/src/agent/guardrails/before.py` |
| `clarify` / `typed_clarify` — the channel and its payload, as switchable guardrails | `engine/src/agent/` |
| `expect.type: contested` — a third pile in the shared grader and metrics | `harness/evals/` |

All additive: 413 published values recomputed from the archive and none moved; `LADDER` is still
R0–R9 and `test_surface.py` passes unchanged.

### Two design constraints discovered the hard way

**The index cannot live inside the layer.** MetricFlow's parser reads every `.yml` under its
directory *recursively* and rejects documents it does not recognise, so an index placed inside fails
the whole layer at load. Convention is `<spec>.clusters.yml`, a sibling — together for a reader,
apart for a parser.

**The staleness guard was verifying the wrong files.** It recorded absolute paths, so a copied tree
hashed the originals and reported agreement; a checked-in index would have done the same on any
other machine. Now paths are recorded relative to the index and the digest's label is separated from
the file it reads.

---

## 7 · Twelve questions, four to a pile

The fixture grew from one question to twelve, and the layer from 7 metrics to 12, so pile C could
hold **four distinct concepts across three axes** — internal-account exclusion, test-channel
exclusion and refund netting — rather than one fork sliced four ways. Every question carries two to
four primitives in experiment 04's vocabulary; none is a bare lookup.

Divergence on the exact slice each pile C question asks about:

| question | candidates | apart |
|---|---|---:|
| active users on web, last week | `active_users` / `active_accounts` | 4.33% |
| habits completed in the Americas, June | `value_moments` / `total_value_moments` | 4.93% |
| marketing spend, Q2 | `marketing_spend` / `acquisition_spend` | 13.38% |
| MRR from subscriptions sold this year | `mrr` / `gross_mrr` | 1.45% |

All twelve oracles verified against the layer, 0 mismatches. Pile B is unanswerable rather than
merely ungoverned: `information_schema` has zero columns matching session, duration, feature,
screen, ticket, survey, nps or promoter, so raw SQL cannot rescue any of them.

### Pile A′ — the same concepts, asked by someone who said which reading

Four more questions were added, one per contested concept, where the asker names the reading:
*"how many active users, **excluding internal and test accounts**, did we have on web last week?"*
There is nothing to clarify. Sixteen questions in total: 4 pile A on clean metrics, 4 pile A′ on
contested metrics with the ambiguity resolved in words, 4 pile B, 4 pile C.

### The run — gpt-5-mini, one rep, 16 questions, concurrency 8

| arm | pile A (8) | pile B (4) | pile C (4) | coverage | silent error | balanced accuracy |
|---|---|---|---|---:|---:|---:|
| `R3+typed_clarify` | 7 right, 1 wrong | 4 refused | **0 clarified, 4 served** | **1.00** | 0.31 | 0.63 |
| `+ambiguity_check` | 4 right, **4 interrupted** | 4 refused | **4 clarified** | **0.50** | **0.00** | 0.83 |

```
WITHOUT the gate                                WITH the gate
                correct WRONG NUM refuse clar                   correct WRONG NUM refuse clar
k = 1  one ans     7 ok      1 !!      ·    ·   k = 1  one ans     4 ok         ·      ·    4
k = 0  no ans         ·         ·   2 ok    1   k = 0  no ans         ·         ·   3 ok    ·
k >= 2 two ans        ·      4 !!      ·    ·   k >= 2 two ans        ·         ·      ·  4 ok
       correct 9/16 · silent wrong 5                    correct 11/16 · silent wrong 0
```

**The trade, measured for the first time.** Silent wrong numbers **5 → 0**. Coverage **1.00 → 0.50**.
Over-clarification **0% → 50%**.

**And the whole cost sits on pile A′.** Every one of the four interruptions was a
self-disambiguating question; all four clean-metric questions were answered correctly and untouched.

| pile A question | metric | gate |
|---|---|---|
| Android app opens, June | `app_opens` | answered, correct |
| paid-search signups, Q2 | `new_signups` | answered, correct |
| annual paying customers | `paying_users` | answered, correct |
| annual subs sold in Q2 | `active_subscriptions` | answered, correct |
| active users **excluding internal**, web, last week | `active_users` | **INTERRUPTED** |
| habits by **real accounts** in the Americas, June | `value_moments` | **INTERRUPTED** |
| marketing spend **across every channel**, Q2 | `marketing_spend` | **INTERRUPTED** |
| MRR **net of refunds**, sold this year | `mrr` | **INTERRUPTED** |

That is not a tuning problem, it is the design: the gate fires on whether the two NUMBERS differ for
this call, and they still differ when the asker has already chosen between them. Nothing in the call
records that the question resolved the ambiguity, so nothing can stand the gate down.

**The fix has to be mechanical.** Something in the call recording that the request named the scope —
not the agent asserting it, because §3 is what its unprompted self-report is worth. Until that
exists, the gate buys a silent-error rate of zero at the price of interrupting half the answerable
questions that touch a contested metric.

## 8 · Five responses to ambiguity, measured

`gpt-5-mini`, 16 questions, three reps each, 48 runs per arm. Every arm sits on `R3+typed_clarify`
and adds one mechanism.

| arm | mechanism | contested ok | A′ over-asked | clean A ok | B refuse ok | silent wrong | coverage | total |
|---|---|---|---|---|---|---|---|---|
| A | nothing (baseline) | 0/12 | 0/12 | 7/12 | 9/12 | 16/48 | 0.96 | 28/48 |
| B | gate blocks the call | 12/12 | 10/12 | 9/12 | 10/12 | 3/48 | 0.58 | 33/48 |
| C | gate, stood down by a declared scope | 12/12 | 12/12 | 10/12 | 9/12 | 2/48 | 0.50 | 31/48 |
| D | rival figure attached to the result | 6/12 | 0/12 | 11/12 | 9/12 | 9/48 | 1.00 | 36/48 |
| E | the same, and the answer is checked for it | 11/12 | 0/12 | 10/12 | 11/12 | 3/48 | 1.00 | **44/48** |

"A′ over-asked" counts questions that stated their own scope and were interrupted anyway.

### The gate works and is expensive

B does what §5 said it does: every contested question asked, none answered silently. The price is
now measured rather than estimated. Ten of twelve questions that had already said which reading they
wanted were interrupted, and coverage on the answerable piles fell from 0.96 to 0.58. The gate reads
the selection, never the question, so a question that disambiguates itself cannot be distinguished
from one that does not.

### The declared-scope escape hatch does not work

C offered the agent a way through: retry the blocked call with `resolved_scope` set to the
discriminator the block named, and the gate stands down. Across twelve blocked A′ runs the agent
used it **zero** times. Blocked, told what separates the two definitions, and holding a question
that had already answered that, it went straight to `clarify` every time. C is therefore worse than
B, not better — the same 12/12 on contested, and 12/12 rather than 10/12 interrupted on A′.

The lesson is the one §3 already recorded in a different form: a mechanism whose last step is *the
model chooses to use it* is priced at what the model's choices are worth. The retry is available,
correct, and unused.

### Disclosure alone is advisory, and behaves like every other advisory

D attaches the competing definition's figure to the governed result and asks for both to be named.
It costs nothing — coverage stays at 1.00, no A′ question is interrupted, and the clean piles are
unharmed. On the contested pile it worked exactly half the time: 6 of 12 answers named both figures,
6 served one number and said nothing. `transparency` had already produced this shape, and produced
it more starkly (0 of 20).

### Checking the disclosure is what closes it

E changes one thing: an answer that served one of two divergent readings and named only that one is
handed back once, with both figures, and re-sent. Contested goes 6/12 → 11/12 at no cost to
coverage, and the total is the best of the five by eight questions. The pattern is the ladder's
oldest result arriving again — R3 `coverage_check` is enforced and contributes, R6 `transparency` is
advisory and does not — with a new twist: the *content* of D and E is identical. The only difference
is whether anything checks that it was used.

### What the numbers do not settle

The four remaining failures in E are not the ambiguity mechanism: two are wrong numbers on clean
Pile A metrics and one is a Pile B question answered with prose. One contested run still slipped
through, on the second correction.

E and B are not ranked by this table alone. E answers more and interrupts nobody; B never serves a
contested number at all. Which is right depends on the price of a silently-single-reading answer
against the price of a round trip, and that price is still the placeholder `WRONG_COST = 4.0`.

### One defect this found

The gate and the disclosure compared the two definitions' rows **by position**. Grouped by region,
`value_moments` returns Americas, EMEA, APAC and `total_value_moments` returns EMEA, Americas, APAC
for the same request — so Americas was compared against EMEA, and the disclosure handed the reader a
rival figure for a region they had not asked about. Rows are now keyed by their labels
(`before.value_of`), and two results with different label sets are "not comparable" rather than
compared. The block decision was unaffected (a divergence was still a divergence); the figures
reported to the reader were wrong.

## 9 · The residual failures are not about ambiguity

Across the five arms — 240 runs, 120 of them on the answerable piles — 14 answers carried a wrong
number. They concentrate in four questions.

| question | correct | served when wrong | what the wrong number is |
|---|---:|---:|---|
| Android users, June | 8,232 | 25,188 (5 of 15) | June across **all platforms** |
| customers paying on the annual plan | 134 | 371 (3 of 15) | **all plans** |
| active users, web, last week | 277 | 271 (2 of 15) | the week **before** last |
| annual subs sold in Q2, still live | 83 | 228 / 494 / 3,872 / 6,721 (4 of 15) | four different things |

The top two are exact matches for the unfiltered total, verified against the layer. **A filter the
question asked for is dropped and the broader question is answered without comment.** That is the
contested-metric failure one level down: there the ambiguity was between two governed metrics, here
it is between two readings of the ARGUMENTS to one metric, and the reader cannot tell either time.

**The wrong-week case is a naming defect of the same family as §4.** `prev_week` resolves to
`last_week` shifted back seven days (`warehouse/src/warehouse/config.py`). Both names are in the
period enum offered to the model, and in ordinary English "last" and "previous" are synonyms. §4
found that the metric name selects the metric; here the period name selects the window.

**None of the 14 was classified by the harness.** `wrong_scope` is set only on questions expected to
be refused (`evals/grade.py`), so an answerable question that returns a wrong number is stored as
`confident_wrong` with no sub-type. Every one of these had to be diagnosed by reading a trace.

**Correction.** This was first reported as arm E's dominant residual. It is not. Pooled across arms
the dropped filter is the largest class, but under arm E there were two wrong answers on the
answerable piles, and re-running one of them produced 9 and 31,478 alongside 371 — that question is
unstable across several failure modes rather than a clean dropped-filter case. The clean case is the
Android question, which arms D and E answered correctly every time.

## 10 · A rejected design, and the guardrail that already covers it

**Rejected: extend the disclosure from metric selection to argument selection.** The proposal was to
notice that the question named a governed dimension member the call did not filter on, run it both
ways, and require the difference to be disclosed. Three structural objections, not fixable ones:

| objection | why it is structural |
|---|---|
| the comparison set is unbounded | a metric has a small set of rivals, precomputed offline by `preflight index`. "The arguments it should have used" has no such artifact: 2^n filter subsets and nothing declaring which alternative is legitimate |
| it requires lexical question parsing | "mobile" does not match `android` or `ios`; "yearly" does not match `annual`; "excluding Android" contains `android` and inverts the meaning; `Americas` is also an ordinary word |
| it destroys determinism | the gate's verdict is a function of (layer, arguments). This one would be a function of (layer, arguments, wording), which is the property that makes the gate testable |

This is the objection already recorded against question-to-definition similarity, arriving on a
different mechanism. It is recorded here because the proposal is attractive and will be proposed
again.

**The non-fragile restatement needs no question at all.** The observable defect is that the answer
text asserts a scope the query did not apply: "Android users opened the app 25,188 times" where the
call carried no platform filter. Both artifacts belong to the harness.

**That guardrail exists. It is `trajectory_verify`, and it is noisy in both directions.**

| test | result |
|---|---|
| annual-plan question, served 371 | **refused** — the real error, caught |
| Android question, served the correct 8,232, four runs | **all four refused** |
| the same cell, one later run | passed |
| the two active-users questions (§11), 8 runs, arm E alone | 7 correct, 0 refusals |
| the same 8 runs, arm E + the reviewer | 3 correct, **5 refusals, every one on a run holding the correct 277** |

**Why it over-refuses.** It cannot separate a filter the analyst added to narrow the question from
one that is part of the metric's definition. On this fixture it cannot be told: `resolve` supplies
the members `governed_notes` needs, and the MetricFlow engine provides none. The engine refuses the
guardrail levels above R4 outright — `resolve` needs members and `output_validation` needs
additivity — which is why this experiment is pinned at R3/R4. The same blindness is already
documented as the largest single source of over-refusal at the top of the ladder
(`guardrails/after.py`).

**Verdict: measure it before building anything new.** It catches the failure and its over-refusal
rate on this fixture is unmeasured. One arm, 16 questions, three reps, no new code.

## 11 · Ambiguity through a calculation

**The divergence does not propagate predictably.** The two definitions differ by 3.72% at the input
(886 against 919, all platforms, last week). What that becomes:

| quantity | users reading | accounts reading | apart |
|---|---:|---:|---:|
| the count itself | 886 | 919 | 3.72% |
| app opens per active user | 6.85 | 6.61 | 3.59% |
| active users who do not pay | 865 | 898 | 3.82% |
| week-over-week growth, % | 5.98 | 5.75 | 3.80% |
| **week-over-week change, absolute** | **50** | **50** | **0.00%** |

The internal accounts are a stable population, so a difference of two levels cancels them entirely.
**A question can rest on a contested metric and still have exactly one correct answer.** Any
mechanism that fires on "an input is contested" fires on the last row. That is the
sensitivity-not-membership rule of §5, one level up, and it is the rule the current check breaks.

### Four questions, flat and derived, stated and unstated

`gpt-5-mini`, arm E, three runs each.

| # | question | correct | 3 runs | how it gets there |
|---|---|---|---|---|
| 1 | active users, web, last week | 277 **and** 289 (or ask) | ✓ ✓ ✗ | rival attached, answer names one, check fails, handed back, both |
| 2 | the same, **excluding internal** | 277 | ✓ ✓ ✓ | the filter collapses both readings, nothing fires |
| 3 | opens per average active user, last week | 6.85 **and** 6.61 (or ask) | ✓ ✓ ✗ | rival attached to the divisor, check fails, handed back, both rates |
| 4 | the same, **excluding internal** | 6.85 | ✓ ✗ ✓ | the filter collapses the divisor, nothing fires |

Failures: two wrong weeks and one over-refusal. **No silent single-reading answer in twelve runs.**

**The convergence result is the mechanism working correctly.** With an explicit
`activity__is_internal = false` filter, `active_accounts` returns 277 on web and 886 overall —
identical to `active_users`. A question that resolves its own ambiguity is recognised **because two
numbers become equal**, not because anything read the wording. That property is worth protecting.

### The defect: the check verifies the input, not the answer

`disclosure_check` looks for the rival's INPUT figure in the served text. Both failure directions
follow:

- **Over-fires.** On question 1's growth variant it demanded 919 and 869, numbers the reader has no
  use for. An answer reading "50, and it is 50 under either definition" would have been handed back.
- **Under-fires.** "6.85 opens per user, out of 919 accounts in total" satisfies the check while the
  reader never learns the other rate is 6.61. **The check can be satisfied by a number that is not
  the answer.**

It currently produces the right outcome because the agent volunteers both rates unprompted, which is
the kind of thing that stops holding on a different model or a longer calculation.

### Options

| option | verdict |
|---|---|
| push the calculation into the layer as a governed derived metric | correct for the few ratios a business actually governs; not general |
| mark a derived metric contested if any input is contested | **incorrect** — membership again; it fires on the +50 row |
| **have the agent declare its arithmetic; substitute the rival input and recompute** | **recommended** — deterministic, no wording read, correct in both directions: substituting into `886 − 836` yields 50, which is already in the answer, so it stays silent |
| state that the figure depends on a contested input | honest, advisory, and every advisory measured here has been ignored |

The recommended option needs the answer tool to carry the expression rather than only the value. The
harness already records which governed result each number came from, so this extends the evidence
plumbing rather than adding a parallel system.

## 12 · What the market does

A scan of what is documented and what ships, against what this experiment measures. The
analysis of why these are the mechanisms available at all is in §16.

### What the vendors do

| mechanism | who | position |
|---|---|---|
| certify one definition per concept, owned and versioned | dbt Semantic Layer, Databricks Metric Views under Unity Catalog, Cube, the 2026 "semantic layer for agents" guidance | design time; the dominant answer, and correct where the contest is reducible |
| pre-approve answers to anticipated questions | Snowflake Verified Query Repository, Databricks trusted assets, Power BI verified answers | removes the model's choice rather than governing it; does not reach the tail |
| classify, reject or ask **by prompt** | Snowflake Cortex Analyst `question_categorization`, Power BI Copilot, Databricks Genie | **this is the arm measured at 16 clarifications in 217 attempts** |
| enumerate interpretations, execute them, compare results, ask only on divergence | AmbiSQL (arXiv 2508.15276) | research; not found in a shipping product |
| answer every interpretation | the AMBIGQA line | research; not a product feature |

Snowflake's documented example for its disambiguation instruction is literally "active users".
AmbiSQL's decision rule — resolve automatically when interpretations converge, ask when they diverge
— is this experiment's sensitivity rule, reached independently. That is the strongest external
support the gate has.

### Where this work sits

| capability | market coverage |
|---|---|
| certify one definition per concept | well covered, and the right first move |
| pre-approved answers | covered, does not scale |
| runtime detection by prompt | covered, measured here as ineffective |
| runtime detection by result divergence | research only |
| **enforcing that the answer discloses it** | not found anywhere |
| **two owned definitions that must both survive** | not addressed; the advice is "certify one", which is unavailable |
| **ambiguity through a derived calculation** | not addressed |

### The systematic shape

| when | mechanism | handles |
|---|---|---|
| design time | one certified definition per concept | the reducible majority |
| index time | precompute contested clusters offline over the layer | the irreducible remainder, without per-query enumeration |
| call time | execute the rival with the same arguments; act only if the numbers differ | separates ambiguity from mere membership |
| answer time | verify the served text carries every diverging reading | the only step measured to work |
| feedback | route a cluster that keeps firing back to its two owners | converts irreducible into reducible over time |

The market owns the first row. The last row is untouched by anyone: a contested cluster firing a
hundred times a month is a governance backlog item with a measured cost, not a runtime problem.

**One rule underneath all of it: compare the two numbers the reader will actually receive, at the
level where the answer is formed.** Every defect found in this experiment — membership instead of
sensitivity, rows compared by position instead of by label, the divisor checked instead of the rate
— is a violation of that sentence.

### Sources

Snowflake [Cortex Analyst custom instructions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/custom-instructions),
[Verified Query Repository](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository),
[best practices for Cortex Agents](https://www.snowflake.com/en/developers/guides/best-practices-to-building-cortex-agents/) ·
Databricks [trusted assets in Genie spaces](https://docs.databricks.com/aws/en/genie/trusted-assets) ·
Microsoft [Power BI Copilot verified answers](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai-verified-answers),
[asking Copilot questions](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-ask-data-question) ·
[dbt Semantic Layer](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl) ·
[Cube, semantic layer for AI agents](https://cube.dev/articles/semantic-layer-for-ai-agents-2026) ·
[OvalEdge, governed semantic layer for AI](https://www.ovaledge.com/blog/governed-semantic-layer-for-ai) ·
[AmbiSQL](https://www.arxiv.org/pdf/2508.15276) ·
[AMBROSIA](https://arxiv.org/pdf/2406.19073) ·
[Disambiguation in conversational QA: a survey](https://arxiv.org/html/2505.12543v2) ·
[AMBIGQA](https://aclanthology.org/2020.emnlp-main.466.pdf)

## 13 · The second model: gpt-5.6-sol

Five arms, 16 questions, three reps, on `gpt-5.6-sol` as well as `gpt-5-mini`. 480 runs.

| | | contested | stated-scope interrupted | silent wrong | coverage | total |
|---|---|---|---|---|---|---|
| **gpt-5-mini** | A nothing | 0/12 | 0/12 | 16/48 | 0.96 | 28/48 |
| | B gate blocks | 12/12 | 10/12 | 3/48 | 0.58 | 33/48 |
| | C gate + declared scope | 12/12 | 12/12 | 2/48 | 0.50 | 31/48 |
| | D rival figure attached | 6/12 | 0/12 | 9/48 | 1.00 | 36/48 |
| | **E attached and checked** | 11/12 | 0/12 | 3/48 | 1.00 | **44/48** |
| **gpt-5.6-sol** | A nothing | 3/12 | 0/12 | 8/48 | 1.00 | 38/48 |
| | B gate blocks | 12/12 | 10/12 | 0/48 | 0.58 | 38/48 |
| | C gate + declared scope | 11/12 | 3/12 | 1/48 | 0.88 | 44/48 |
| | D rival figure attached | 9/12 | 0/12 | 3/48 | 1.00 | 45/48 |
| | **E attached and checked** | 11/12 | 0/12 | 2/48 | 1.00 | **46/48** |

**The check removes the model as a variable.** Arm E scores 11/12 on the contested pile on both
models. Arm D — the same information, unverified — scores 6/12 on the weak model and 9/12 on the
strong one. Enforcement is not merely better on average: the outcome stops depending on which model
is running. That is a stronger claim than "enforced beats advisory" and it is the one worth
publishing.

**Arm C flips, so §8's conclusion needs a range rather than a constant.** `gpt-5-mini` used the
declared-scope retry zero times in twelve. `gpt-5.6-sol` uses it: over-clarification falls from
12/12 to 3/12, coverage from 0.50 to 0.88, total from 31 to 44. "A mechanism whose last step is the
model choosing to use it is worth what the model's choices are worth" still holds; what those
choices are worth is now known to vary by a lot.

**Arm C's residual failure is a vocabulary mismatch and it is precise.** All three
over-clarifications are one question — *"net of refunds, how much MRR…"*. The index's discriminator
for that pair is `status = active` / `status <> 'canceled'`, and "net of refunds" is not in it. On
the three A′ questions whose wording sits close to the predicate ("excluding internal and test
accounts" against `is_internal = false`) it stands down every time. **The stand-down works exactly
as far as the business phrase matches the technical one.**

**Scale does not close it.** With no mechanism, `gpt-5.6-sol` gets 3 of 12 and answers seven
contested questions with one number and no comment. Three questions fail identically on all reps.

**Blocking ages badly.** Arm B is second of five on the weak model and last on the strong one, tied
with doing nothing. Its coverage cost is fixed while every other arm improves.

**The §9 residuals are largely a `gpt-5-mini` problem.** On `gpt-5.6-sol` the answerable piles are
23/24 and pile B is 12/12 in every arm. The dropped filter and the wrong week are gone; what remains
is one wrong MRR figure and the hardest contested pair.

## 14 · One request, two correct queries

Question A′ — *"active users, **excluding internal and test accounts**, web, last week"* — has three
formulations in this layer, all returning 277:

| | metric | filters |
|---|---|---|
| A | `active_users` | `platform=web, is_internal=false` |
| B | `active_users` | `platform=web` |
| C′ | `active_accounts` | `platform=web, is_internal=false` |

They exist because **the same distinction is expressible in two places**: baked into the metric
selected, or supplied as a filter. `active_users` declares `measure: active_account_count` plus
`filter: is_internal = false`; `active_accounts` is the same measure without it; and
`activity__is_internal` is also an ordinary filterable dimension. So the phrase "excluding internal
accounts" has no canonical destination in the query language.

The machinery behaves differently on A and B. Under A the rival, run with the same filter, also
returns 277 — the readings collapse, and nothing fires. Under B the rival returns 289 and the answer
is handed back, so the user receives a correct answer with one redundant clause and the agent spends
one extra internal turn. **The recognition in path A is worth stating plainly: a question that
resolves its own ambiguity is detected because two numbers become equal, not because anything read
the wording.**

**A rejected fix, and why.** Normalising `(metric, filters)` to `(measure, predicates)` was proposed
to make the verdict identical across A and B. It does not: path B's query carries less information
— it says nothing about internal accounts and merely selects a metric that happens to exclude them
— so firing is the correct verdict for the query as expressed. Normalisation reproduces exactly the
verdicts the numeric comparison already gives. The proposal is recorded as rejected because it is
attractive and will be proposed again.

## 15 · The interface authored the failure

A third path exists and it is a wrong answer. Asked question A′, one run tried to filter to web
using `platform`, was rejected, tried the same name again, then **dropped the filter entirely** and
answered across all platforms: 886 where 277 was correct. Four causes, chained:

| | cause | fixable |
|---|---|---|
| 1 | the tool description read `e.g. {"platform": "ios", "is_internal": false}` — unqualified names, because the other engine accepts them. The agent sent that example almost verbatim | yes |
| 2 | `filters` was `additionalProperties: True`, so an invalid key was a runtime error rather than an impossible call | yes |
| 3 | the engine error was truncated at 400 characters, landing mid-word at `Suggestions: [ "Dimensi` — removing the list of valid names | yes |
| 4 | **dropping the filter is the only action guaranteed to succeed** | structural |

Cause 4 is the general one. An agent under tool-error pressure optimises for a call that returns
data. Fixing a rejected name needs information it does not have; removing the restriction always
works, and the broader query returns an entirely plausible number. **The action space has a gradient
pointing at answering a different question, and nothing points back.**

### What was built

- **`filter_vocabulary`** (ACTION_SPACE, out of ladder): `filters` and `group_by` closed to the
  layer's own dimension names, `additionalProperties: false`, and the example rebuilt from a real
  one. Makes the wrong call unmakeable rather than merely correctable — the same argument the metric
  enum already makes one field along.
- **The engine error keeps its suggestions.** Head plus the `Suggestions:` block, both.
- **`constraint_regression`** (REPAIR, out of ladder): hands back an answer whose number came from a
  call that dropped a filter an earlier call asked for. Neither set comes from the question; both
  are the agent's own calls. Keys compare on their last segment, so correcting `platform` to
  `activity__platform` is not mistaken for abandoning a restriction, and a key matching no dimension
  in the layer is ignored.

### A regression the fixes introduced, and the row rule that closes it

The closed `group_by` enum made grouping more attractive than filtering, and a grouped result has
many rows. The first version of `disclosure_check` owed the rival figure for EVERY divergent row, so
a correct answer about web was handed back twice for omitting android and ios — platforms nobody had
asked about — at a cost of 27,923 input tokens against 15,026 for the same question afterwards.

The rule is now per row and symmetric: **report either reading of a row and you owe the other;
report neither and you owe nothing for that row.** Symmetric, because an answer serving only the
rival's figure has made the same silent choice in the other direction.

This is §16's claim 6 for the fifth time. The check was comparing against rows the query returned
rather than rows the answer reported.

### Measured, `gpt-5-mini`, 16 questions, five reps, 80 runs per arm

| | correct | silent wrong | hand-backs | runs needing two | tool errors |
|---|---|---|---|---|---|
| E, no interface fixes | 67/80 | 9 | 25 over 16 runs | 9 | 19 |
| F, fixes, every row owed | 69/80 | 5 | 30 over 20 runs | 10 | 24 |
| F2, fixes + the row rule | 66/80 | 6 | **13 over 13 runs** | **0** | 19 |

**What is established.** The row rule more than halves the hand-back cost and removes every
double-correction. That is a large, mechanism-level effect measured on the thing the rule changes.
And the dimension-name error class disappeared on the questions that had it — both `active_users`
questions went from one tool error to zero, and the traces now show `activity__platform` on the
first attempt.

**What is NOT established, and was claimed before this run.** The graded score across the three
configurations is 67, 69, 66 and the silent-wrong count is 9, 5, 6. **The suite's noise band at five
reps on `gpt-5-mini` is about ±4 of 80.** An earlier draft of this section reported the interface
fixes as 67 to 70 with silent errors halved; that difference is inside the band and the claim is
withdrawn. The fixes are justified by the error class they remove and by the trace, not by the
score.

**Two results that did not go as predicted, recorded because they are the informative ones.**
`constraint_regression` fired **zero times in 80 runs** — consistent with the vocabulary fix
removing its cause, but it means the check is untested against a live case and should be described
as a backstop rather than as working. And **total tool errors did not fall** (19, 24, 19): the
residual errors are a different class entirely, the agent using `run_sql` as a calculator to add
three monthly figures and hitting a binder error on the first attempt.

**That last one is an action-space gap, not a naming problem.** There is no governed way to add up
governed results, so arithmetic leaves the governed path — which is exactly the situation §11 says
the disclosure check cannot follow. It is the strongest candidate for the next piece of work.

## 16 · Synthesis: where this sits in the published work

### 1 · Abstention is the wrong instrument, because the uncertainty is not in the model

Selective prediction, from Chow's reject option through the current abstention survey, assumes the
system is unsure and buys safety with coverage. Definitional ambiguity is not that: the system holds
277 and 289, both correct. The uncertainty is in the QUESTION. So the coverage/risk trade-off is not
a trade-off — blocking handles 12/12 at coverage 0.58, disclosing handles 11/12 at coverage 1.00.
Disclosure is not a better point on the curve; it is off the curve, because abstention was invented
for a different problem. This also explains why blocking ages badly: its cost is fixed while the
epistemic problem it addresses shrinks with capability. *Knowing but Not Showing* (2605.25284) is
the same observation from the model side; the deployment consequence is that the behaviour need not
be bought with coverage.

### 2 · Asserted controls against maintained ones, measured on identical content

The security taxonomy separates preventive controls, which constrain behaviour, from detective ones,
which catch violations afterwards. Arms D and E are that distinction with the content held
byte-identical, and the result is in §13: 6/12 and 9/12 unverified against 11/12 and 11/12 verified.
**Verification converts a capability-dependent behaviour into a capability-independent guarantee.**
That is an assurance argument rather than a performance one, and it is why "it works on the frontier
model" is not a control. The constraint-drift work states the thesis in its title — safe behaviour
must be maintained, not merely asserted — for multi-agent systems; AGENTIF finds condition and tool
constraints are where instruction-following fails. This experiment adds four independent nulls in
one system: the prompt rule, the compiled SQL carrying the discriminator, the declared-scope retry
on the weak model, and the advisory rival figure. **Every shipping product's runtime ambiguity
mechanism is prompt-level, which is the arm measured as ineffective.**

### 3 · Sensitivity over membership, and the provenance of the alternatives

AmbiSQL (2508.15276) independently reached the same rule: enumerate interpretations, execute them,
compare results, ask only on divergence. Convergent arrival on a non-obvious design is the strongest
external support the gate has. The difference is where the alternatives come from — a model, per
query, or an offline index over the governed layer. Given claim 2 that difference decides
everything: **a model-generated alternative set inherits model variance, so the same comparison rule
is a control in one architecture and a heuristic in the other.** This is the real argument for a
semantic layer under agentic analytics: not that the agent will not guess joins, but that the
alternatives are enumerable without asking a model.

### 4 · Ambiguity is not preserved under composition

AMBROSIA defines a question as ambiguous when the set of non-equivalent queries has cardinality at
least two — a property of the question. §11 shows it cannot be. The same pair, 3.72% apart at the
input, is 3.59% through a ratio, 3.82% through a subtraction, and **0.00%** through a
week-over-week difference. A question can rest on a k=2 input and have exactly one correct answer.
So ambiguity is a property of the (question, layer, request, computation) tuple, evaluated at the
answer, and any check anchored at the input is wrong in both directions — as ours measurably is.
Every taxonomy that labels QUESTIONS ambiguous breaks on derived metrics, which is most of real
analytics.

### 5 · The action space has a gradient, and it points at a broader question

§15's cause 4. The literature has the pieces — schema-first tool APIs (2603.13404) catalogues tool
misuse including invalid enumerations and constraint violations; the standard advice is that enums
eliminate plausible-but-invalid outputs; constraint drift names the phenomenon for multi-agent
communication. Nothing found locates it in **single-agent tool-error recovery**, and nothing gives
it a detector. `constraint_regression` is one, and it reads no language: a filter key present in an
earlier attempt and absent from the call that was served.

### 6 · Compare what the reader receives, at the level the answer is formed

Four defects in this experiment, all the same shape: rows matched by position (Americas against
EMEA); the disclosure naming two numbers without attaching either to its metric; the derived check
reading the divisor rather than the rate; the served text taken as `answer` plus `explanation` where
a product may render only `answer`. **A disambiguation mechanism was built at the wrong level four
times, by the same author.** That is worth recording as a finding rather than as an embarrassment:
deciding which projection of the trace to check is the hard part of this design and has no default.

### 7 · The blind spot is irreducibility, and the missing meter

Every vendor's answer is to certify one definition per concept, and where the conflict is technical
debt that is correct and should be done first. It is unavailable here for an ORGANISATIONAL reason:
Finance nets refunds because the board pack must and Sales does not because commission pays on what
was closed; Product excludes staff and Platform includes them because servers do not care who is
logged in. Those are not modelling mistakes. So runtime disclosure is not a workaround for weak
governance — it is the correct steady state for a multi-stakeholder organisation, plus the one thing
nobody ships: **a cluster that fires two hundred times a month is a governance backlog item with a
measured price, routable to its two owners.**

### Claims this experiment can defend as its own

1. **Verification makes ambiguity handling independent of the model** (§13, claim 2).
2. **Ambiguity is not preserved under composition** (§11, claim 4).
3. **Widening is the cheapest escape from a tool error** (§15, claim 5).

The rest is the published work, and it agrees.

### Added sources

[Know Your Limits: a survey of abstention in LLMs](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00754/131566/Know-Your-Limits-A-Survey-of-Abstention-in-Large) ·
[Selective risk certification for LLM outputs](https://arxiv.org/pdf/2509.12527) ·
[Constraint drift in LLM-based multi-agent systems](https://arxiv.org/html/2605.10481) ·
[AGENTIF: instruction following in agentic scenarios](https://arxiv.org/pdf/2505.16944) ·
[Schema-first tool APIs for LLM agents](https://arxiv.org/html/2603.13404v1) ·
[From agent traces to trust: evidence tracing and execution provenance](https://arxiv.org/pdf/2606.04990) ·
[OWASP GenAI LLM guardrails taxonomy](https://genai.owasp.org/solution-taxonomy/llm-guardrails/)

## 17 · The held-out suite: the tuned numbers were fit, not capability

Every guardrail in this experiment was chosen after watching the sixteen-question suite fail, so
that suite measures FIT. A held-out set (`heldout.yml`, 46 questions) was authored afterwards with
the mechanisms frozen, from the schema, the catalogue and the pile definitions only — never by
looking at which questions the agent fails. Fifteen questions per pile, two to four primitives each,
red-teaming in the SHAPE of the questions rather than in knowledge of which break.

**Every oracle was executed and every pile membership proved before the file was written, and three
questions failed that check during authoring** — the guard doing its job on its author. Habits
May→June does not cancel (3,689 against 3,792); no Q2 subscription was ever refunded, so `mrr` and
`gross_mrr` agree for that window; the doubly-contested ratio diverges by 0.19%, narrower than the
default tolerance. All three were moved or given their own tolerance.

**The result is the point.** On the tuned suite the same configuration scores 14 of 16. On the
held-out set it scores around 30 of 46 at one rep — and the gap is where fit ends and capability
begins. The ambiguity machinery GENERALISED: contested pile 12/12, derived contested 3/3, the piles
where two definitions agree 12/12, stated-scope 11/12. What did not generalise was everything around
it — the residual failures are scope, substitution, and reason codes, none of them the ambiguity
subject. Several numbers reported before this section describe fit; the held-out numbers are the
ones to publish.

## 18 · Model judgement, mechanically checked: the scope classifier

`scope_classifier` is the one place a model call sits inside a control path, and it is built to the
rule the rest of the module follows: **the model makes the judgement nothing mechanical can make,
and a mechanism decides whether to believe it.**

The judgement it makes: two governed definitions of one concept produce byte-identical tool calls
whether or not the user said which reading they wanted, so no check that refuses to read the
question can tell "active users, web, last week" from "active users EXCLUDING INTERNAL AND TEST
ACCOUNTS, web, last week". Only reading the question answers it. The classifier is asked, in
isolation, whether the request already chose — and told to QUOTE the words that chose.

The check on the judgement is what makes it safe. First run, it answered `yes` on the bare question
and quoted `is_internal = false` — the discriminator it had been handed, which appears nowhere in
the question. It was quoting the prompt back. Requiring the quote and VERIFYING it is in the
question turned that into a `no`; retested, it fabricated a different phrase — the definition's own
wording this time — caught by the same substring check. **The model is good at the judgement and
will manufacture a justification for it, so the justification is verified rather than taken.** With
that check the classifier suppresses the disclosure only when the request genuinely named the scope,
and the stated-scope pile answers with one number and no interruption.

The module was split from the trajectory judge into `guardrails/classify.py`: the judge adjudicates
an ANSWER, the classifier categorises a REQUEST, and they version independently, so a reworded
classifier must not mark a stored verifier verdict stale.

## 19 · A second warehouse, built to dbt's MRR pattern, then retired

A held-out question — "how much MRR do our monthly plans bring in?" — was answered 501.92 against a
true 1,888.44. Diagnosing it exposed a real modelling defect: MRR is a BALANCE, a semi-additive
level, and the base warehouse models it as a transaction sum over `started_date`. So "as at a date"
is inexpressible, a `period` silently returns the cohort that STARTED in it rather than the balance
on it, and the twelve monthly figures sum to the current balance because they are cohorts of it. The
agent was more correct than the layer it queried.

A corrected warehouse was built to dbt's own documented MRR pattern — the measures docs use MRR as
THE worked example of a semi-additive measure: a daily snapshot fact, `non_additive_dimension`, a
movement fact beside it, staging/intermediate/marts, the mrr-playbook's spine. The two facts
reconciled to the penny (`mrr(month end) − mrr(prior) == sum of that month's movements`).

**And it was retired, from first principles.** The experiment studies the third state — it needs
contested pairs that diverge. The corrected warehouse DESTROYED one: on base all four pairs diverge;
correctly modelled, `mrr`/`gross_mrr` agree today, because every refunded term had ended by 25 May.
"Correct" modelling removed a quarter of the experiment's subject. It also forced per-warehouse
grading overrides, split the SQL and semantic search paths, and shipped its own bugs. That is the
overcomplication `05_preflight_ambiguity` avoids by making arms thin views over the shared star.

**Two things were kept, lifted onto the base layer.** First, the finding: part of the `mrr`/`gross_mrr`
disagreement was modelling debt, not governance, and only good modelling could tell which — it
sharpens the irreducibility claim rather than weakening it (three pairs survive unchanged). Second,
the one fix that MOVED THE AGENT: a metric description stating that `mrr` is a running figure read
today when `period` is omitted, and that a `period` selects the cohort that started in it. Stating
the CONSEQUENCE rather than the classification ("a balance, not a total") is what worked — the
question that started the thread went 0/3 to 3/3 on the original frozen warehouse, no rebuild. The
warehouse rebuild itself never fixed the agent (3/3 wrong on both warehouses); correct modelling
only shrank the error from a category swap to a wrong-date reading.

## 20 · A cohort as a first-class dimension

The A-pile WRONG NUM failure: "how much MRR came from subscriptions that started in the second
quarter?" (1,653.64) answered 67. The agent passed `filters={started_date: ['2026-04-01',
'2026-06-30']}` as a range; the equality-only filter read the list as "started on one of these two
exact days", two daily balances survived, and it summed them. A cohort was reachable only two ways,
both traps: `period` binding implicitly to `started_date`, or a range the filter cannot express.

`cohort_month`, a categorical dimension computed as `strftime(started_date, '%Y-%m')`, makes "revenue
from terms that started in a month" a first-class equality that composes with `plan`. June cohort
750.88; June AND monthly 501.92 — the number the agent had wrongly served for CURRENT monthly MRR,
now with a legitimate home. **A list on a CATEGORICAL dimension reads as IN**, so
`cohort_month=[Apr,May,Jun]` returns the Q2 total, while the identical list on the TIME dimension did
not — the categorical route is the one the agent cannot misfire on. The question went 0/3 to 3/3.

## 21 · The substitution class, and a mechanism that could not be made to hold

The largest recurring REAL agent failure across the held-out set is not ambiguity. It is
substitution under a binding failure: the requested thing has no governed referent, so the agent
answers the nearest thing that does. "TikTok ads" (not a channel) → 61,233, all-channel spend.
"APAC signups" after a filter error → 28,412, matching nothing. "Enterprise plan" (not a plan) →
371, all plans. In each the agent identifies the metric and period correctly and fails only on a
VALUE, relaxing the constraint it cannot satisfy — and relaxing a constraint always succeeds and
returns a plausible number.

Three fields have named exactly this and converge on one rule — a mention bound to a closed
vocabulary needs an explicit NO-REFERENT outcome, or the system force-binds to the nearest
candidate: false-presupposition QA (CREPE: a false existential presupposition, corrected not
answered), value-linking unanswerability in text-to-SQL, and NIL prediction in entity linking. The
agent has no such outcome for a dimension value.

**A `value_membership` check was built for it and reverted.** It read the question, extracted the
categorical values, and tested each against the published members. Standalone on eight clean
controls it scored 8/8 and caught TikTok and enterprise end to end — the agent reached `exit=answer`,
was handed back, and re-exited as a refusal naming the governed channels, the CREPE correction by
enforcement. **On the full held-out suite it refused or clarified eleven answerable questions.** It
flagged dates ("May 2026", "second quarter"), partial channel names ("content"/"SEO" against the
member `content_seo`), and descriptors ("staff", "live", "platform") as ungoverned values. A
precision pass — exclude time expressions, bidirectional substring match, tighten the extractor —
removed every false positive on the controls and also suppressed the true positives. **Loosen it and
it refuses good questions; tighten it and it misses the ungoverned ones; there is no cheap stable
operating point.** This is the read-the-question fragility the first-principles analysis and the
literature both warned about, and the standalone 8/8 gave false confidence because the controls were
too few and too clean. The class is real; the check that reads the question freely is not the way.
The candidates that remain are answer-level (does the served answer report the value asked for) or
grounded to the agent's own dropped filter rather than a free read of the question.

## 22 · What the diagnostic map shows that the headline metrics hide

The three-need by five-action map (piles A/B/C against right/wrong-number/no-figure/refused/
clarified) carries two things the scalar metrics do not.

**Silent error is the metric that tells the truth here.** On a held-out run it was ~0.09, and the
`!!` cells — a number handed over that the reader cannot tell is false — are all pile-A/B modelling
or substitution issues; ZERO on the contested pile, the pile the experiment exists for.

**Balanced accuracy under-counts the winning strategy.** The contested pile lands in the `both`
cell — answered with every reading and the discriminator — which is correct and is the fourth
action. But the formula credits only literal `clarify`, so it scores that pile near-zero
(`clarified/C = 0/15`) while the map shows 11–14 of 15 handled correctly. The matrix is telling the
truth; the balanced-accuracy formula needs the `both` cell folded into the contested numerator
before it appears in any write-up. This is a metric-definition defect, not an agent result.

Two smaller cells resolved by tracing, both mine not the agent's: an A-pile "no figure" was a
which-category question mis-typed as `metric_answer` expecting a number (replaced with a numeric
governed question); a B-pile "correct" was a false-premise question the agent handled exactly right,
correcting the premise ("they rose by 50"). And the tooling earned a fix: `bench trace` crashed on
rows storing acts as names, and `run.py` now stores the full act dicts and the served text, so a
failure is diagnosable from stored results without a re-run — which is a different sample.

## 23 · Not measured

- ~~**Over-clarification on the hard case.**~~ Measured in §8: 10 of 12 under the gate. The
  predicted fix — a mechanical channel for the request having named the scope — was built (arm C)
  and the agent never used it.
- **THE NOISE BAND, now partly known and wider than several comparisons in this document.** Three
  runs of near-identical configurations at five reps scored 67, 69 and 66 of 80, with silent-wrong
  counts of 9, 5 and 6 (§15). So ±4 of 80 is noise at this n, and any arm difference smaller than
  that is not a result. §8's B-against-C gap (33 against 31 at three reps) and §15's original score
  claim are both inside it. Mechanism-level counts — hand-backs, tool errors by class, which
  guardrail acted — move far less and are what smaller effects must be measured on.
- **A rate of any kind.** Sixteen questions, one fixture, one model, three reps. The sizing work in
  `00_reading.md` says a usable pile needs four to five distinct contested concepts; it now has four,
  and the noise band still does not exist. Two of the five-arm comparisons are separated by one or
  two questions, which is inside the run-to-run spread observed at one rep.
- **The second turn.** No user simulator, so a clarification is priced at half an episode and
  abandonment is unmeasurable. This is the largest hole in the arm comparison: it flatters B and C
  and penalises D and E.
- **`WRONG_COST`.** Still the placeholder 4.0, and it is the only thing standing between the §8
  table and a defensible choice between arm B and arm E.
- ~~**Any model but `gpt-5-mini`.**~~ Done in §13. `gpt-5.6-sol` narrows the D-to-E gap (6/12 to
  9/12) without closing it, and arm E lands on 11/12 under both models. A THIRD model would test
  whether that ceiling is the check's or the suite's.
- **`trajectory_verify`'s over-refusal rate on this fixture** (§10). Eight runs point in both
  directions; that is a hint, not a measurement.
- **`constraint_regression` against a live case** (§15). It fired zero times in 80 runs after the
  vocabulary fix removed its cause, so it is a backstop that has never caught anything. A run with
  `filter_vocabulary` off would test the check itself.
- **Whether the §15 gain came from the schema or from the prompt line.** The two arrived together.
  An arm with the closed vocabulary and no prompt sentence would separate them.
- **The other branches of the taxonomy.** Everything here is DEFINITIONAL ambiguity. Vagueness
  ("our best product"), missing scope, and entity ambiguity are untouched, and enumerate-compare-
  enforce has no obvious purchase on them: there is no governed alternative to execute.
- **Cost of the gate.** It runs each competitor once per contested call. Cheap on DuckDB, unmeasured
  on anything else.
- **The held-out set at reps=3, with the current cell.** Everything in §17–§22 is a one-rep
  snapshot inside the ±4–5 band. No held-out number is stable yet; the current cell
  (`+scope_classifier+filter_vocabulary+constraint_regression`, cohort dimension, clarified MRR
  description) has never run at three reps over all 46.
- **The substitution rate** (§21). How often the agent answers a broader scope for a value with no
  governed referent is measured only anecdotally (three questions). It is the largest real agent
  failure and its rate is the thing that would justify building the answer-level catch.

## 24 · Candidate next arms

- **The balanced-accuracy formula must credit the `both` cell** (§22) before any write-up. It
  currently scores the winning contested strategy near-zero. A metric-definition fix, not an arm,
  and the most urgent item here because it misrepresents every run.
- **Widen the accepted reason codes per case** (§21, §9). Unanswerable questions refuse with a
  defensible code that is not the single one the case declares (`segment_undefined` against
  `ungoverned_dimension_value`), inflating the B-pile miss count. Cheap; unblocks a clean B read.
- **An answer-level scope check for the substitution class** (§21). Does the served answer report
  the value the question asked for — grounded on the ANSWER and the agent's own query, not a free
  read of the question, which §21 measured as too fragile to ship.
- **Break the governed_numbers / tool_restriction coupling** (§21). `governed_numbers` would catch
  the substituted total (61,233 has governed provenance but for the wrong question) and the
  non-additive sum, but it cannot run without removing `run_sql`. Checking only governed-origin
  answers and standing down on raw-SQL ones would let it run at R3.

- **Disclose the definition's own filter in the scope line.** The MetricFlow adapter's scope line
  says "no filters — the whole population this metric defines" while the metric itself carries
  `is_internal = false`. The harness's own layer says "the metric definition already restricts: NOT
  is_internal" in the same position. The information is in the SQL either way, but the prose summary
  is what gets skimmed, and this is the cheapest untried advisory lever.
- ~~**Answer with both, disclosed**~~ — built and measured in §8 (arms D and E). §4's objection
  was right about the advisory form and did not apply to the checked one: the model does not have to
  pick well, it has to be prevented from picking silently.
- **A non-zero divergence threshold**, as a lever rather than a default.
- **A governed way to do arithmetic on governed results** (§15). The residual tool errors are the
  agent using `run_sql` as a calculator to add three monthly figures. Arithmetic leaving the governed
  path is what puts §11's derived case beyond the check's reach, so this is one fix serving two
  findings, and it is the strongest next candidate.
- **Verify the answer rather than the input** (§11): have the answer carry its arithmetic, substitute
  the rival operand, recompute, and check for the recomputed figure. Depends on the item above.
- **Sub-type the wrong numbers on answerable questions** (§9). Fourteen wrong answers, none
  classified, all diagnosed by hand. Everything above depends on this being automatic.
- **Rename `prev_week` to `week_before_last`** (§9). Two names in one enum that read as synonyms in
  English, resolving to different weeks.
- **Give the MetricFlow layer a member resolver**, so `resolve` and `governed_notes` can run and the
  judge stops treating a definitional filter as a narrowing (§10). This also unpins the experiment
  from R4.
- **The second turn**, still. §16's claim 1 rests on disclosure dominating abstention, and that
  comparison prices a clarification by assumption. A user simulator answering with the case's own
  intended reading turns the clarify column into resolved-correct / resolved-wrong / unresolved,
  which is the same split §8 forced on the answered column.
- **Route a persistently firing cluster to its owners** (§12). Nothing in the market does this, and
  it is the step that turns an irreducible contest into a reducible one.

## 25 · The reason code was never stored, and what it showed once it was

The stored result row carried `outcome` but not the coded `reason` a decline named. Post-hoc
analysis read the missing key as `None` and concluded that correct refusals were arriving with no
reason. They were not: `grade.py` graded on `answer.reason` all along, so the code was present at
grading time and absent only from the record. The fix is one line in `run.py` — persist
`answer.reason` and `answer.missing` on the row — and it changed no score. What it changed is that
the failure is now readable without re-running, and re-running is a different sample.

Read once it was visible (marts layer, gpt-5-mini, R3 held-out cell, three reps, 138 rows):

| pile | need | correct |
|------|------|---------|
| A | k = 1, one answer | 41 / 48 |
| B | k = 0, unanswerable / substitution | 22 / 45 |
| C | k >= 2, contested | 41 / 45 |
| | **total** | **107 / 138 (77.5%)** |

Pile B is the whole gap, and the stored codes split it into two behaviours that a bare count had
merged:

- **Clarify used as a soft refusal.** On a concept the layer does not define at all — CSAT,
  email open rate, retention broken out by channel — the model asks *which definition* when the
  answer is *there is no definition*. `clarify` is for `k >= 2`, two governed readings that
  diverge; firing it at `k = 0` invents a choice the layer cannot offer. csat_by_channel clarified
  on all three reps, retention_by_channel on all three.
- **Substitution, unchanged from §21.** time_per_category answered on all three reps,
  habits_per_session and tiktok_spend on two of three. A governed count exists and the ungoverned
  filter or ratio is served against it, and no coverage document forbids the shape.

A third, smaller behaviour is the one the reason code was needed to see: on a value-membership
failure the model refuses with the right ACTION and the wrong CODE. "How many customers are on the
enterprise plan?" has no referent — `plan` is a billing interval (`annual` / `monthly`), not a
tier — so the actionable typed refusal is `ungoverned_dimension_value` or `false_premise`, either
of which routes to "tell the user enterprise does not exist." The model refused with
`no_governed_definition`, which routes to "go define a metric" — the wrong repair, because the
count is already governed and only the filter value is missing. The case now accepts the three
defensible codes and, if answered, a premise rebuttal; the model still reached past all of them
for the generic one. This is RefusalBench's separable-skill result (arXiv 2510.10390) reproduced
on the fixture: the action is easier than the category, and the category is where a typed refusal
earns its keep.

## 26 · The grounding protocol: a clarification must ground, or it is a refusal

§25 left the clarify-as-soft-refusal cases open. The clearest, `csat_by_channel` — "customer
satisfaction by channel" — clarified on every rep, offering "NPS, CSAT, or a rating." The
warehouse instruments none of the three: no survey, no rating, no sentiment, in any layer. The
right terminal is refuse, and the clarification is a menu of definitions the system does not have.

The stored candidates showed why a naive gate cannot catch it. The model offered, in the
`candidates` field, three REAL metrics — `active_users`, `value_moments`, `app_opens` — while the
prose question named NPS and CSAT. The two representations were never reconciled, so a check that
the candidates EXIST passes (all three do) and a check that they DIVERGE passes (three different
quantities, wildly). Neither is the defect. The defect is that the candidates are not readings of
the asked concept at all.

The fix moves the semantic work to where it belongs and keeps the mechanism to what it can prove.
The model interprets the question and binds each reading it would offer the user to the object that
grounds it — a governed metric, a fact/dimension table, or a column. The mechanism verifies only
that each grounding EXISTS; whether it is the RIGHT object for the concept stays the model's
judgement, because a deterministic relevance check is the brittle thing this avoids. A reading the
model cannot ground cannot be shown, so a clarification with fewer than two grounded readings is
handed back to refuse (nothing grounds it) or answer (one does). This is the `grounded_candidates`
guardrail: a schema enrichment (`candidates` become `{reading, grounding}` pairs) plus a REPAIR
check (`loop.ungrounded_candidates`, resolver in `guardrails/grounding_check.py`), and a new
refusal reason `uninstrumented`.

Result (gpt-5-mini, held-out cell + `grounded_candidates`, three reps):

| case | marts only | + grounding protocol |
|------|-----------|----------------------|
| csat_by_channel | clarify 3/3 | **refuse `uninstrumented` 3/3** |
| email_open_rate | clarify 2/3 | **refuse 3/3** |
| retention_by_channel | clarify 3/3 | clarify 1 / refuse 2 |
| pile C (contested) | answer-both 14/15 | answer-both, no regression |

Three findings, in order of what they teach:

1. **The correction needed no correction.** `repairs = 0` on every CSAT rep: the model refused at
   the decision point, not after a handback. Requiring the grounding to be explicit was enough —
   forced to bind "CSAT" to an object and finding none, the model does not offer it. The
   enforcement changed the behaviour without ever firing.

2. **The protocol discriminates; it does not blanket-refuse.** `retention_by_channel` is the
   control. Forced to ground its readings, the model produced two that DO ground — "day-90 exact"
   and "within-90 cumulative", both over `fct_user_days.active_date` and `dim_users.signup_date` —
   and diverge. So retention is not uninstrumented: the data to define it exists, there is simply
   no governed metric and the concept is definitionally ambiguous. It is the genuine middle case,
   derivable but ungoverned, and it is a different problem from CSAT rather than the same one. The
   `uninstrumented` refusals it also produced are mis-coded on that ground.

3. **No failure moved into the answer path.** The risk of gating a clarify is that the model
   escapes into a silent substitution. CSAT and email refused; neither answered. Pile C, which
   already resolves contested questions by disclosing both readings, was unaffected.

The headline balanced accuracy did not move (rep-1 37/45 against the 37/46 baseline): at this n the
trade sits inside the noise band, and the result is the composition, not the number. Two silent
menus became typed refusals, one mislabelled case was exposed, and the guarantee — no ungrounded
reading reaches the user — is structural rather than a behaviour the model happened to choose.

## 27 · The four slots: every silent wrong number is an undisclosed spec mismatch

The grounding protocol (§26) handled the clarify path. The silent wrong numbers that remained on the
ANSWER path turned out to be one shape seen four ways. A governed number answers a query, and a
query is four slots — the semantic layer's own decomposition:

| slot | the silent error when it differs from the question, undisclosed |
|------|----------------------------------------------------------------|
| measure    | a COUNT of completions served for a question about time spent |
| grain      | a PER-DAY rate served for a question about the week |
| segment    | ALL channels served for a question about one |
| definition | ONE of two governed readings served, the rival not disclosed |

Each is the same failure: the number answers a neighbouring question and the reader cannot see the
swap. The fix is not to police the slots against the question, which means reading it — the fragile
move that sank an earlier value-membership check. It is to make the answer SELF-DESCRIBING, which
does the work two ways: writing the elided slot down tends to make the model recompute the asked
one, and where it does not, the mismatch is visible instead of silent. Three mechanisms, built one
slot at a time:

- **measure** — `grounded_measure`. The model judges its own served answer (`classify.
  answer_measures_asked`): did the number measure the quantity asked for, a proxy, or something the
  data does not capture? A proxy is disclosed or refused. On the substitution pile the model, made
  to be explicit, refused rather than served a proxy — `time_per_category` and `habits_per_session`
  moved from a silent number to a refusal, with no over-refusal on the answerable controls (they
  verdict `measures` and serve untouched).

- **grain and segment** — `answer_spec`. A prompt/schema nudge, not a gate: the answer must state
  the measure, grain, units, and segment of a figure. `habits_per_active_user` moved from 0.60 (the
  per-DAY ratio) to 4.11 (the weekly one) — forced to state the grain, the model computed the asked
  grain. `seo_spend_june` moved from 21,013 (all channels) to 3,605 (content_seo) — forced to state
  the segment, the model applied the filter. The segment slot was the one predicted to need a
  question-reading check; naming it in the answer closed it without one.

- **definition** — `disclosure_check` already exists (pile C discloses both governed readings), but
  `scope_classifier` defeated it: asked whether "total monthly recurring revenue" chose between
  `mrr` and `gross_mrr`, it answered yes and cited the WHOLE QUESTION as its quote, which the
  `_quoted_from` check passed because the whole question is trivially in the question. Closed by
  hardening the citation the same way it was already hardened against an absent quote: a quote
  covering most of the question isolates no distinction, so a quote is now required to be
  materially shorter than the question (<= 0.8 of its words). `mrr_total`, `active_users_ios` and
  `active_users_organic` went from serving one reading silently to disclosing both 3/3;
  `active_users_android_stated`, where the question DID choose ("excluding staff and test
  accounts"), still stands the disclosure down and answers cleanly — the strict direction costs at
  most a redundant disclosure, never a lost one. The residual is `habits_per_active_user`, whose two
  readings differ by ~0.5% (below the divergence threshold) and which tangles with the grain axis —
  a threshold-calibration case, not the citation.

With this the four slots are closed: measure (`grounded_measure`), grain and segment (`answer_spec`),
definition (`disclosure_check` + the hardened `scope_classifier`).

One measured caution on the documented-example lever (§27 rests on it for additivity). A usage
example added to `active_users` — "a distinct count is semi-additive; query at the grain you want,
do not sum the days" — fixed the observed summing bug (`active_users_growth*` went to 3/3). But the
same treatment applied PREVENTIVELY to `paying_users` BROKE a case that had been correct in every
prior run: the example emphasised "read the value directly", and the model dropped a plan filter it
had always applied. A usage example is a behavioural nudge, and nudging one thing dents another, so
each must fix an OBSERVED failure and be measured — not added across a class on principle. The
preventive examples were reverted; the one that earned its place was kept.
