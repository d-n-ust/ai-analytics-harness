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

## 28 · Additivity: a documented example patched it, the interface closed it

§27 credited the grain slot partly to a usage example on `active_users` — "a distinct count is
semi-additive; query at the grain you want, do not sum the days." Measured across rep-3 draws, that
was only a partial fix: `active_users_growth` still summed daily distinct counts on about one draw
in three. A usage example is a behaviour the model CHOOSES, and it chose wrong intermittently.

The root cause is structural. `time_grain` was a DEAD parameter: the grain of a time breakdown came
only from the group-by column name — `metric_time` is day, `metric_time__week` is week — so a
caller passing `time_grain='week'` alongside a bare `metric_time` was handed DAY rows, and a
`count_distinct` measure at day grain invites a SUM over time. The weekly figure was reported as the
sum of its seven daily distinct counts, ~2.3x too high, a plausible number for the wrong grain.

The fix binds a bare `metric_time` to the requested grain; an explicit `metric_time__day` is left
alone, so a real by-day breakdown still works. This is what a real semantic layer does — a grain
request returns that grain — and it makes the invalid state unrepresentable rather than merely
discouraged (data-modelling principle #7). Measured DIRECTLY (a summing-occurrence counter — a
`run_sql` SUM beside a distinct-count metric — which varies far less than the graded score), it
went to zero on the `active_users` cases, and `active_users_growth` became 3/3 stable. Additivity
is derivable from the `agg`, so nothing here is hand-annotated. The lesson is the pairing:
documentation is the ~half lever on a behaviour; the interface is the guarantee.

## 29 · The proxy-offer clarify, built and reverted

The clarify state has a second shape beyond "which of two governed definitions": a PROXY-OFFER —
when the asked thing is not measured but a same-kind proxy exists, offer it and let the user accept
or decline ("we do not track sessions — would habits per app-open do?"). It was built with two
guards: the proxy must GROUND (one real object), and — on the board's construct-validity rule — it
must measure the SAME KIND of thing (an app-open for a session, not a count for a duration).

It over-fired. The model used the route to dodge a FILTER, offering an unfiltered total as a
"proxy" for a filterable question: all-platform app-opens for iOS, all-plan payers for monthly-plan
payers, all customers for enterprise. An over-offer counter (proxy-offers on cases that should not
accept one) caught it — 3/3 construct-invalid, two on answerable questions. A computability gate
("if it is a filter away, answer it, that is not a proxy situation") fixed the filter-dodge, but
the aggregate went 122 -> 114 -> 111 across draws and the feature hurt its own target:
`habits_per_session` moved from a clean refuse (67%) to answering the app-opens proxy (0%). Reverted.

The finding is the one the board predicted: a visible clarify is not confident-wrong, but an agent
that offers a proxy liberally trades away the refusal discipline that is the point of the third
state. And the method lesson: the over-offer counter earned its keep — it made the failure a number
instead of leaving it buried in a score that could not resolve it.

## 30 · The inline catalogue: the information was present, the ergonomics were not

`ios_opens_may` answered "how many times did iOS users open the app" as ALL-platform app_opens, the
platform filter dropped, 3/3. The hypothesis was that the agent could not see that `platform`
applies to `app_opens`. Tested against what the agent actually reads — the rendered catalogue, not
the YAML — it was disconfirmed: the catalogue lists `activity__platform` directly under `app_opens`,
and `ios` among its governed values. Everything needed was present.

But the dimension and its VALUES were separated: the dimension sat under the metric, the values in a
distinct section the agent had to cross-reference. The `inline` catalogue renders each filterable
dimension WITH its values beside the metric — `activity__platform (android/ios/web/unknown)` — and
drops the separate section. `ios_opens_may` went 0/3 -> 3/3; controls unchanged. The information was
present; the ERGONOMICS were the blocker, and adjacency is a treatment (the renderer already knew
this: grouping dimensions by entity had earlier cut dropped-filter failures from four to one). One
honest qualifier: the model's prose said "iOS" while its query filtered nothing, so this is partly a
query-construction gap the presentation reduced rather than a pure visibility one; the plan/channel
filter cases improved less, because "iOS" -> `platform='ios'` is a more direct value-match than
"monthly plan" or "content and SEO".

## 31 · Direction from evidence: the R7 transparency guarantee, at R3

`active_users_fell` — "active users fell last week, by how much?" — answered "fell by 50" while the
model's own two queries returned 836 (prev_week) then 886 (last_week), a rise. The model echoes the
question's presupposition even as its numbers contradict it. Three interventions, and the
progression is the finding:

| intervention | result |
|--------------|--------|
| prose hint in the explanation ("state the direction from your own numbers") | ~half, ignored |
| a typed `direction` enum + self-declared `value_before`/`value_after`, checked | ~half, GAMED |
| the direction checked against the run's GOVERNED CALLS | 2/3, un-gameable |

The middle one fails in a specific, instructive way: told "836 -> 886 is a rise", an anchored model
keeps "fell" by FLIPPING the levels it declares (`value_before=886, value_after=836`). The label
ordering is the model's to fabricate, so a check against self-declared levels cannot hold.

The binding it cannot fabricate is which QUERY returned which value. `_governed_calls` reads the
run's `query_metric` calls off the trace; `value_of` recomputes each; ordering a metric's two
same-argument, different-period calls by their period gives the true direction, which the model
cannot flip because it did not author the query->period binding. This is exactly R7's `transparency`
guarantee — a measurement written from the evidence, not from the model's words — obtained at R3 by
READING the governed calls rather than rendering them, with no claims machinery. The residual is a
model that re-declares "fell" through both corrections and serves at the `MAX_CORRECTIONS` cap:
measured serving it, not gamed into it. It generalises to any change or comparison claim.

## 32 · The instrument problem: rep-3 cannot resolve a per-fix effect

Across the four-slot work and the fixes above, rep-3 draws of essentially one config read 122, 114,
111, 113 — all consistent with a single rate near 115 +/- 6. A per-fix effect is +/-2 to 5, inside
that band. The headline cannot resolve the changes, and reading single draws as wins and losses
(which this log did, for a stretch) is reading noise.

The evidence that DID resolve is the direct, per-slot counters, which vary far less: summing
occurrences went to zero; contested pairs disclosed both readings 3/3 on their exemplars;
`ios_opens` reached 3/3; `csat` refused 3/3. The discipline the board imposed, recorded here because
it was learned the hard way: judge a fix by the specific failure it targets, measured directly, not
by the aggregate — a fix can pass every targeted check while the noisy headline says nothing, and a
feature can look fine on targeted tests while costing on the whole (the proxy-offer, §29). A
publishable aggregate at this question count needs rep-10 or more; the per-slot counters are the
instrument in the meantime.

## 33 · The segment slot: the recipe, not the fact, and the self-contained metric block

The segment slot — a filter the question names and the answer drops — was §27's holdout, and §31
explained why it is the hard one: grain and direction can be recovered from the EVIDENCE (the query
values), but the segment lives only in the QUESTION, so there is nothing to enforce against. The
fixes here are documentation, not enforcement, and they are the right shape for exactly that reason.

`monthly_paying_users` — "customers currently paying on the monthly plan" — answered 371, all plans,
3/3. The segment was NOT missing from context: the inline catalogue shows `subscription__plan
(annual/monthly)` beside `paying_users`. The agent satisfices on the strong `paying_users` match for
"customers paying" and drops the "monthly plan" qualifier. A natural control settled the cause:
`mrr`, whose description CARRIES a plan-filter usage example, applies that exact filter 3/3 on "MRR
from our monthly plans"; `paying_users`, with a bare description, drops it 3/3 — same filter, same
question shape, same warehouse. Giving `paying_users` the same example took it 0/3 -> 3/3. The
catalogue says the dimension EXISTS; the example says to USE it, and how. And it generalises: the
`annual` variant — named in the example but not demonstrated — transferred 2/3, so the example
teaches the OPERATION rather than a lookup, with the demonstrated value the strongest anchor.

`seo_spend_june` — "spend on content and SEO" — answered all-channels, and the metric-level example
alone did NOT land (~1-2/3). Two reasons: "content and SEO" -> `content_seo` is a compressed,
reordered token, and the `channel` dimension was bare, so nothing bridged the phrasing to the value;
and the values sat beside the metric while the dimension DESCRIPTIONS lived in a separate section the
agent had to cross-reference. The fix renders each dimension on its own line with BOTH its categories
and its description — a SELF-CONTAINED metric block, nothing a lookup away — and gives `channel` the
value->plain-name mapping (`content_seo` is spend on content and SEO). That lifted it to 3/4;
`paid_search` (a direct token match) was already 4/4 and generalised; controls drew no channel filter
(no over-application). The residual miss is a COMPOUND case — `marketing_spend` has a contested rival
(`acquisition_spend`), and disclosing the two crowds out the channel filter: the segment slot tangled
with the definition slot.

The lesson across both: the catalogue makes a dimension VISIBLE; the usage example and the dimension
description make it USABLE — the recipe (filter by plan, here is how) and the value mapping
("content and SEO" is `content_seo`). A bare metric block is a lookup problem the agent solves ~half
the time; a self-contained one is a read. And documentation is the correct lever for the segment slot
specifically, because the requirement is in the question and not the evidence, so there is nothing to
enforce — only to make legible.

## 34 · The catalogue-rendering study: layout is a wash, a schema explanation is the lever

The catalogue rendering had been a treatment surface all along (inline-values fixed ios_opens,
inline-descriptions fixed seo_spend), so it earned a controlled study — five arms over the
rendering-sensitive cases, rep3, then the winner confirmed on the full held-out suite.

| arm | what it shows | rep3 (10 cases) |
|-----|---------------|-----------------|
| minimal | name + description only | 24/30 |
| values | dimensions + categories inline | 26/30 |
| inline | dimensions + categories + descriptions | 24/30 |
| full | the sectioned layout | 23/30 |
| normalised | each entity's dimensions ONCE + a schema explanation in the system prompt | 28/30 |

**Layout is a wash.** minimal/values/inline/full sit at 23–26, inside the rep3 band, and they TRADE
cases rather than dominating — each has a 1/3 or 0/3 dropout somewhere (inline on monthly_paying,
full on ios_opens and paid_search, values on seo_spend, minimal on habits_emea). The rep1 ranking
had inline first at 10/10; rep3 reversed it. That reversal is the §32 lesson once more: a rendering
difference of a few cases is not resolvable against the rep1 draw.

**Teaching the schema is the lever.** `normalised` is the best and the only arm with no catastrophic
case (worst 2/3). It differs from the others in one thing: the system prompt explains the shape —
each metric counts an entity, a metric filters by its entity's dimensions spelled
`entity__dimension`, and "when a question names a segment, apply it as a filter; do not report the
unfiltered total as if it were the segment." On the FULL held-out suite it holds and widens:

| | correct | silent | coverage |
|-|---------|--------|----------|
| inline (default until now) | 113/138 | 17 | 1.0 |
| normalised | **119/136** | **13** | 1.0 |

It improved all three piles — answerable 40→43, contested 38→41, and unanswerable 21→**29**. The
biggest gains are on pile B, and they are not filter application: `time_per_category` 0→100%,
`enterprise_plan` 33→100%, `churn_reasons` 33→100% — the substitution and refuse cases. Teaching the
entity structure makes not only what CAN be filtered legible but what has no entity or dimension to
stand on, so the agent refuses instead of substituting. One case regressed (`paid_search_spend`
100→33). And 119 broke the ~115 plateau every other config had sat inside all session — the first
lever to move the aggregate beyond the noise band, because it is structural and meta rather than
per-case. `normalised` is now the default.

The synthesis across §30–§34: the catalogue makes a dimension VISIBLE (adjacency, a wash on net);
the usage example and dimension description make it USABLE per case (the recipe and the value
mapping); and a one-time SCHEMA EXPLANATION makes the whole layer legible at once — the strongest and
most general of the three, because it teaches a rule the agent applies everywhere rather than a fact
it must be shown everywhere.

## 35 · The hybrid catalogue: the dedup↔adjacency tension is real, and the trade does not net out

The §34 study left one regression: `paid_search_spend` fell 100→33 under `normalised`. The cause was
adjacency. `normalised` lists each entity's dimensions ONCE in a shared block, so a metric's own
segment values (`spend_row__channel` for `marketing_spend`) sit a lookup away rather than beside the
metric, and the agent sometimes drops the channel filter and reports the all-channel total instead of
the paid-search slice.

A sixth arm, `hybrid`, tests whether both benefits can be had at once: keep the schema explanation and
the shared block of `normalised`, but render each metric's OWN-entity dimensions inline with values,
so only JOINED dimensions deduplicate into the shared block. The segment a metric filters by is then
both beside the metric (adjacency) and named by a taught rule (the schema explanation). The two arms
share one schema note; only the sentence saying WHERE a dimension's values sit differs.

**The target case is fixed.** `paid_search_spend_q2` moves from 1–2/3 to 3/3, confirmed on two
independent rep3 draws, with the `spend_row__channel: paid_search` filter applied in every rep.

**But the full-suite total does not move.** Same cell, rep3, gpt-5-mini, held-out suite:

| arm | pile A | pile B | pile C | unique (46) | attempts | silent |
|-----|--------|--------|--------|-------------|----------|--------|
| normalised | 15/16 | **9/15** | 14/15 | 38 | 119 | 13 |
| hybrid | **16/16** | 8/15 | 14/15 | 38 | 119 | 11 |

Hybrid does exactly what its design predicts and no more. It fixes the pile-A adjacency case and
loses pile-B refuse-legibility. The two regressions are `tiktok_spend` (TikTok is not a governed
channel; correct answer is refuse) and `time_per_category` (no time-per-category measure exists;
correct answer is refuse). Under `normalised` the agent refuses both; under `hybrid` it asks for
clarification or serves a substitute:

| case | normalised | hybrid | hybrid failure |
|------|-----------|--------|----------------|
| tiktok_spend | refuse ~2–3/3 | refuse ~1/3 | asks (`underspecified_request`), or serves a channel total |
| time_per_category | refuse ~2–3/3 | refuse ~1/3 | serves a fabricated category (`learning`) |

The magnitude is modest and noisy. The first full-suite draw showed both cases at 3/3→0/3; a fresh
rep3 reprobe put hybrid at 1/3 and normalised at 2/3 on each, and normalised itself is not perfectly
stable (it drops one rep too). The 0/3 was an unlucky draw — the §32 lesson once more. The DIRECTION
is stable: on absent-construct pile-B cases, `hybrid` refuses less often than `normalised`.

**The finding is the tension, not the arm.** Segment values want to be in one canonical block, so
that absence reads as absence and the agent refuses, AND beside each metric, so that a present filter
gets applied. No single rendering on this axis gets both. `hybrid` sits in the middle and moves
failures from pile B to pile A rather than removing them. Pile B is the direction to protect: an
incorrect refusal is recoverable, an incorrect number is the silent error the whole experiment exists
to remove. `normalised` stays the default; `hybrid` remains a selectable arm.

The correct fix for the `paid_search` dropped filter is therefore not in the catalogue. The dropped
filter is a segment-application miss, not a legibility one — the same class the `answer_spec` guardrail
and the usage-example recipe already closed for `seo_spend` (§33) without any rendering change. That is
where the direct-filter reliability belongs, and it does not cost the pile-B legibility that the
catalogue's deduplicated structure buys.

## 36 · The ungrounded-segment substitution, and grounding as the model's job

The catalogue arms (§34, §35) delivered per-metric context but left one failure open: a question
that names a segment the layer does NOT have. "How much did we spend on TikTok ads in Q2" was
served `36,875.98` — the `paid_search` figure — because the agent mapped an ungoverned channel onto
the nearest governed one. This is the worst class in the whole experiment: a confident wrong number,
in the right unit, from a real metric, for a question that has no answer. TikTok is not a channel at
any layer — not in the governed values (`content_seo`, `paid_search`, `partnerships`, `referral`),
not even in the raw source, whose only paid channel is search (`ppc`).

**Three things did not catch it, and the reason each failed is the finding.**

| mechanism | why it did not catch the substitution |
|-----------|----------------------------------------|
| `check_segment_defined` | a constant `False` on MetricFlow (no named segments): it returns the same NO for `TikTok` and for `monthly`, so it carries no information and the agent correctly ignored it |
| the ontology tool (§ontology arm) | it SHOWED the closed channel list, but context is advisory; the agent read it and substituted anyway |
| `grounded_measure` | it judges the MEASURE — spend is spend — so a mismatch in the SEGMENT passes it |

**A deterministic segment resolver made it worse.** The first gate resolved the question's segment
to a governed value and verified the link with a lexical ANCHOR (a shared token between the phrase
and the value). On the held-out suite it dropped coverage from 1.00 to 0.92 by REFUSING answerable
questions:

| case | question phrase | why the anchor check false-refused |
|------|-----------------|------------------------------------|
| `active_users_unknown_plat` | "platform is not recorded" | correctly links to the value `unknown`, but shares no token with it, so the lexical rule rejected a right answer |
| `acquisition_spend_q2_stated` | "real acquisition channels" | is the `acquisition_spend` METRIC, not a channel value; a segment-only resolver could not see it |

The principle these violations name:

> **Verify existence with the mechanism; trust semantic fit to the model.**

Existence — does `unknown` exist as a member, does `acquisition_spend` exist as a metric — is
deterministic and the machine owns it. Semantic fit — does "not recorded" MEAN `unknown`, is "real
acquisition channels" the `acquisition_spend` metric, does "TikTok" correspond to anything — is the
model's superpower, and a lexical rule that overrules it breaks on synonymy every time. The anchor
check was doing the model's job badly.

**The grounding gate.** `classify.ground_question` gives the model the whole ontology — every metric
with its definition, every segment dimension with its values — and asks whether every concept the
question names has a referent, resolving by MEANING. The model reports the ungrounded concept and its
dimension; the mechanism verifies only that the concept is genuinely absent before refusing on its
word. Directly, with the real model:

| question | resolver verdict |
|----------|------------------|
| "platform is not recorded" | answerable — grounds to `unknown` |
| "real acquisition channels" | answerable — grounds to the `acquisition_spend` metric |
| "TikTok ads" | unanswerable — ungrounded, dimension `spend_row__channel` |
| "enterprise plan" | unanswerable — ungrounded, dimension `subscription__plan` |

Scoped to VALUE-level misses: the gate fires only when the ungrounded concept belongs to a real
segment dimension (`spend_row__channel` for TikTok), so `ungoverned_dimension_value` is the right
reason. An ungrounded METRIC or MEASURE returns an empty dimension ("time per category", "CSAT") and
is left to `grounded_measure`, which refuses it as `uninstrumented`. Without this scope the gate
mis-typed a correct absent-measure refusal.

`check_segment_defined` is withdrawn on MetricFlow (via `TOOL_NEEDS`, so an engine with real named
segments keeps it): it was noise the agent wasted a call on, and removing it also reduced the
flailing on ungrounded questions (a `max_iterations` loop disappeared).

**What is measured, stated honestly.**

- On the five target cases at rep-3: 15/15 correct, coverage 1.00, zero silent wrong numbers, zero
  false refusals, and three live catches — the agent computed the substitute number, was about to
  serve it, and the gate converted it to a clean refuse with the right reason.
- On the full held-out suite at rep-3: the gate caused ZERO false refusals (the anchor version caused
  four), which is the property that matters. But it fired only twice in 46 questions, and five of the
  six aggregate flips never touched it. The suite has essentially two cases the gate can act on
  (TikTok, enterprise), and the substitution fires intermittently, so the headline moved only within
  the rep-3 noise band (§32): 119 to 123 attempts up, 38 to 34 majority cases down — the two
  directions disagree, which is the signature of noise, not signal.

The gate's value is therefore the FAILURE MODE it closes, not an aggregate gain. A single served
"TikTok spend = 36,875.98" is exactly the confident-wrong the programme exists to prevent, and the
gate closes it without costing coverage. Claiming the gate raised the suite score would be marketing;
the honest claim is that it is safe and it removes a class of confident-wrong answer, demonstrated by
direct catches rather than by the headline. To measure it on aggregate would need more
ungrounded-segment questions in the suite — authored carefully, since the mechanism now handles them,
to avoid grading its own homework.

## 37 · The raw-SQL escape, and computing the long tail with governance

`retention_by_channel` was the last confident-wrong the earlier work left standing, and it exposed a
class the segment and measure checks did not cover. "Which acquisition channel gives us the best
90-day retention" has no governed retention metric, but IS computable from the data (signup cohorts
in `dim_users` + activity in `fct_user_days` + channel). At R3 `run_sql` is available, so the agent
wrote its own SQL, invented a retention definition — "active EXACTLY on day 90", which is why every
channel came out near 11% — and served **organic** as the winner. organic beat referral by 0.04
points; the winner was noise, the definition was arbitrary, and neither was disclosed.

Why nothing caught it: `grounded_measure` judges whether the number measures the asked quantity, and
the agent DID compute retention, so it passed. `segment_gate` is scoped to segment-value misses, and
retention is a measure-level miss. `check_metric_exists` returned the correct NO — and the agent
overrode it by computing anyway. The tool is also brittle by construction (`term in self.metrics`, an
exact string match): it cannot map "active user count" onto `active_users`, so it is unreliable in
the other direction too.

**The reframe: an ungoverned measure is not automatically a refusal.** It sits in one of three
places, and the schema itself says which — the marts carry their own grains and their own absences
("no product-feature or screen taxonomy", "no paid-social or tiktok channel", counts but no
duration):

| the measure | example | correct behaviour |
|-------------|---------|-------------------|
| governed | active users, marketing spend | answer from the governed metric |
| computable (no metric, data present) | 90-day retention | compute AND disclose the definition, or clarify |
| uninstrumented (no data) | revenue per employee, minutes in app, top screen | refuse `uninstrumented` |

`classify.classify_answerability` makes this a model judgement over BOTH the governed ontology AND
the data schema, verified against the schema's own statements of what it holds. It sorts every case
correctly, and as a by-product it derives the refusal reason the earlier gold could not keep straight
(§36): data present but no metric is `no_governed_definition`; data absent is `uninstrumented`.

**The policy is configurable, because governance strictness is a deployment choice.** A board pack
wants a refusal on any ungoverned measure; an exploratory analyst wants the long tail computed, as
long as the definition is visible. `answerability_gate` routes a served answer on the verdict:
uninstrumented refuses under either policy; a computable measure refuses `no_governed_definition`
under STRICT, or — under TRANSPARENT (`transparent_compute`) — is allowed to stand IF the answer
states the definition it computed by (`answer_discloses_definition`), and otherwise is handed back to
disclose or clarify. The number is trusted exactly to the extent the reader can see the definition it
rests on, which is the whole point.

End-to-end, both policies behave as designed. Under STRICT the served "organic" becomes a refusal —
the confident-wrong is gone. Under TRANSPARENT the agent computes retention, states the definition
("share of non-internal users active on day 90, joining dim_users to fct_user_days"), and the gate
stands down on the disclosure — the useful answer, made safe.

Two pieces remain before the transparent arm can be scored, and both are deliberate:

- MARGIN HONESTY. A disclosed computation that still crowns a noise-level winner (organic 11.2% over
  referral 11.2%) is disclosed but misleading. Per the spec this is a GRADING check — a good answer
  reports the breakdown and does not declare a winner inside the noise — not an enforced handback.
- The TRANSPARENT ARM'S GOLD. The strict suite grades `refuse` correct for these cases; the
  transparent arm needs its own gold that accepts a disclosed-and-margin-honest computation OR a
  clarify. It is a separate arm, not a change to the strict gold.

The mechanism is the finding: the governance boundary an analytics agent must hold is not "never
compute the ungoverned" but "never serve a computed figure whose definition the reader cannot see",
and the data schema is a rich enough ontology to tell the agent which of the three places a measure
sits in.

## 38 · The silent-error campaign: 13 to 3, by closing one failure class at a time

Starting from the normalised baseline (silent 13 on the held-out suite), a sequence of mechanisms
took the confident-wrong count down by closing one class each. The number that moved is silent wrong
numbers — a served figure the reader cannot tell is wrong — measured at rep-3 on the 46-question
held-out suite.

| step | mechanism | class closed | silent |
|------|-----------|--------------|--------|
| baseline | normalised catalogue | — | 13 |
| segment grounding | `segment_gate` + grounding resolver | ungrounded segment (TikTok as a channel) | 5 |
| answerability | `answerability_gate` (three-way) | raw-SQL escape (retention invented + served) | 4 |
| usage examples | value_moments / app_opens examples | EMEA segment drop + manual summation | 3 |
| applied_segment | decoupled, enforced | dropped filter under a correct disclosure | 3 |
| governed growth | `active_users_growth` derived metric | period-over-period arithmetic done by hand | ~2 |

Each mechanism is an instance of one principle, and the principle is the finding: **verify facts with
the mechanism, put durable logic in the semantic layer, and trust semantic fit to the model.**

- The GROUNDING RESOLVER (`ground_question`, `classify_answerability`) lets the model do the semantic
  step — does this concept map to a governed metric, a computable measure, or nothing — over the
  governed ontology AND the data schema, which states its own grains and absences. The mechanism
  verifies existence, never semantic fit. A lexical anchor check that tried to verify fit itself
  false-refused correct synonyms ("platform not recorded" -> `unknown`) and was removed.
- The ENFORCEMENT GATES read FACTS, not prose: `applied_segment` checks the filter actually carried
  in the governed call against the segment the question named; `segment_gate` checks the concept
  grounds; the `scope_classifier` off-axis guard rejects a resolving quote that names a segment on a
  different axis than the discriminator (organic cannot resolve an internal-vs-all contest). Facts in
  the trace cannot be talked around.
- DURABLE LOGIC BELONGS IN THE LAYER. A period-over-period change is a derived metric with an offset
  window; governing it makes the engine compute the delta, so the model cannot botch the arithmetic.
  A ratio of governed metrics is the same shape. This is the semantic layer doing what it exists for,
  not a prompt asking the model to be careful.
- USAGE EXAMPLES remain the lever for a metric's correct USAGE (§28, §33): app_opens gained "read the
  period directly, do not sum sub-periods"; value_moments gained a region-filter example. Both cases
  went 2/3 to 3/3 by teaching usage, not by adding a mechanism.

Two honest caveats recorded for the write-up.

INFRASTRUCTURE, NOT BEHAVIOUR. Each answer-boundary gate makes a classifier call, and the disclosure
check another; three gates plus disclosure is roughly five model calls per answer. Run at concurrency
8 over 46 questions this hit provider rate limits, the process hung, and every stable case collapsed
to serving an unfiltered total — a silent-error count of 21 that was pure infrastructure. The same
cell at concurrency 2 produced zero tool errors and the correct answers. The lesson is a real one:
stacked LLM gates multiply API load; run them at low concurrency or consolidate the classifiers into
one call. A measurement taken through a rate-limited run measures the limiter, not the agent.

SAMPLE DISCIPLINE. The remaining silent errors are one or two flaky reps on 2/3 cases, at the noise
floor for rep-3 (§32). They are not a headline; the durable claim is the 13-to-3 reduction and the
classes closed, not the last rep.

## 39 · The marts ontology as the grounding surface: answerability by traversal, consulted upfront

§36–38 decided answerability with a per-question MODEL JUDGEMENT over the governed ontology text plus
the data-schema text — and the schema text carried hand-written absences ("no screen taxonomy", "no
duration"), an enumerated complement the model read to decide existence. §39 makes answerability a
property of a closed-world GRAPH the model CONSULTS, decided by traversal, not judged each time.

THE GRAPH. A new workspace package `ai-analytics-ontology` builds `MartsOntology` — a complete,
closed-world graph of the marts, generated from the MetricFlow manifest (entities, grain, measures,
relationships) plus `information_schema` (attributes). Closure is a STANCE, not a list: the graph
states everything the warehouse captures and asserts completeness once, so absence is DERIVED (a
concept not in the graph does not exist), never enumerated. `verify()` decides EXISTENCE and
JOINABILITY deterministically. Hybrid completeness closes the coverage gap safely: every marts table
becomes an entity so the present is complete, but relationships come only from the manifest, so an
unmodeled table is an ISLAND — its columns exist as nodes, but it cannot be joined until a join is
curated. An incomplete graph therefore only ever UNDER-claims a join; it never invents one.

THE SEAM, UNCHANGED IN PRINCIPLE. The model does semantic fit (decompose the measure into ingredient
nodes); the graph verifies existence. The one brittleness found and fixed: `verify` matched the raw
ingredient string, so `user.signup_date (the signup date)` — a parenthetical the model added — read
as absent and false-refused a real node. Existence is a property of the REFERENCE, so the token is
extracted before the lookup. This is the same lesson as §38's removed lexical anchor check: the
mechanism verifies existence, never surface form.

THREE BOUNDARIES, ONE GRAPH. The graph verdict is applied wherever the instrumented/computable/
uninstrumented distinction is asserted, not only once:

| boundary | position | what it does |
|----------|----------|--------------|
| the gate | REPAIR | a SERVED run_sql number is routed by the graph verdict (`graph_answerability`) |
| the refusal reason | REPAIR | a refusal claiming `uninstrumented` that the graph proves COMPUTABLE is corrected to `no_governed_definition` |
| the grounding surface | ACTION_SPACE | `check_answerability` lets the agent consult the graph UPFRONT, replacing the name-match `check_metric_exists` (`graph_grounding`) |

RETENTION, FIXED AT THE SOURCE. Retention has no governed metric but IS computable (signup cohort
joined to activity). The failure had MOVED since §37: the agent no longer serves an invented
retention number — it REFUSES — but with the wrong reason, `uninstrumented` ("not captured") when the
gold is `no_governed_definition` ("captured, no governed metric"). The cause: `check_metric_exists`
answers only "is there a governed metric NAMED this", which conflates "computable but ungoverned"
with "not captured", so the agent guessed and scattered across `uninstrumented` / `other` /
`underspecified`. The backstop corrected only the `uninstrumented` branch, and inconsistently.

The fix was to move the graph UPFRONT. `check_answerability(measure)` returns the three-way verdict
with the reason code it implies — "COMPUTABLE: no governed metric, data IS captured -> refuse
`no_governed_definition`". A first cut returned the whole graph render for the model to read; the
agent over-explored (list_metrics, run_sql, describe_table) and ran out of turns as ERROR rows. A
CONCISE, deterministic verdict (the graph decides; the agent does not re-read the graph) took
retention to 8/8 in isolation at 1.0 tool calls per run, and 0/3 -> 3/3 in-suite.

THE A/B (rep-3, 46-question held-out suite, R3 cell).

| arm | correct | silent | error rows | retention |
|-----|---------|--------|-----------|-----------|
| baseline (no graph) | 123/138 | 3 | 1 | 0/3 |
| + `graph_answerability` (gate reads graph) | 123/138 | 4 | 2 | 0/3 |
| + `graph_grounding` (consult upfront) | 125/138 | 4 | 0 | 3/3 |

Upfront grounding fixed retention, removed the error rows, lifted `correct` by two, and left the
answerability axis clean: all NINE genuinely-uninstrumented cases stayed 3/3 (the tool returned
`UNINSTRUMENTED`, the agent refused `uninstrumented`), and `check_answerability` returned correct
verdicts throughout.

HONEST CAVEATS.

THE HEADLINE SILENT COUNT DID NOT DROP (4 vs baseline 3, within the rep-3 noise floor of §32).
Retention is a REFUSE case, so its fix shows in `correct` (+2), not in the silent-number metric,
which counts served figures. The graph closes EXISTENCE and REASON errors, not the failure classes
the silent metric is dominated by.

THE REMAINING SILENT ERRORS ARE ORTHOGONAL TO ANSWERABILITY. `active_users_fell` (×3, the dominant
source in every arm) is a FALSE-PREMISE + DIRECTION error: the question asserts active users fell;
they rose by 50; the agent queries the governed `active_users_growth`, reads +50, and reports "50
fewer" — accepting the false premise and inverting the direction. `check_answerability` is never
called (the measure is governed). `seo_signups_q1` (×1) is a SEGMENT-DROP flake: the tool correctly
said GOVERNED, the agent then queried `new_signups` without the channel filter (3987 vs 125). Neither
is an answerability problem; they belong to premise-checking and segment robustness respectively.

THE PRINCIPLE. Answerability is a property of a closed-world graph, decided by traversal and consulted
as the agent's GROUNDING SURFACE — not a judgement the model makes per question, and not a late
correction after it has already gone the wrong way. The graph earns its place on the boundary that
actually decides the case: for retention, that was the refusal reason, reached by consulting the
graph first.

## 40 · The false directional premise: usefulness over formality, by the right tool at each layer

A loaded question presupposes a trend — "active users fell last week, by how much?" — and the data
contradict it: `active_users_growth` for last week is +50, a RISE. Three responses grade correct,
and they are not equally useful.

| response | correct? | useful? |
|----------|----------|---------|
| refuse `false_premise` | yes | LEAST — declines to say what happened |
| answer "50" (neutral) | no — reads as "50 fell" | misleading |
| answer "active users did not fall — they rose by 50" | yes | THE useful one: corrects AND informs |

An analyst that refuses a question it can answer, on a technicality, is one leadership stops asking.
So the target is the third response: correct the premise and give the number. A false premise whose
truth is GOVERNED is a correct-AND-answer case, not a refuse; the refuse is reserved for a premise
whose truth cannot be recovered.

THE ALLOCATION IS THE FINDING. Each sub-decision goes to the tool whose strength it is, and the
anti-pattern is using one tool to recover what another should simply provide.

| sub-decision | tool | why |
|--------------|------|-----|
| does the question presuppose a direction | — | NOT NEEDED: the typed slot forces the model to commit, so there is nothing to reverse-engineer |
| what direction did the answer commit to | protocol | the TYPED `direction` slot answer_spec requires (rose/fell/unchanged/not_a_change) — a field the model must fill, no neutral phrasing to hedge with |
| the true direction | deterministic | the SIGN of the governed change metric (`active_users_growth` = +50 -> rose); the model cannot flip a governed value |
| is the premise false | deterministic | typed direction vs the sign |
| what to do about it | protocol | a fixed governance line steered into the prompt: correct-and-answer, do not refuse a change you can quantify |
| phrase the correction | LLM | its one superpower here — language |
| score it | grader reads the TYPED slot | a typed outcome, not a keyword scan of prose |

A first cut broke this rule and was reverted: it added an LLM classifier to detect the question's
presupposition, and the grader keyword-scanned the prose for "rose". Both are the wrong tool — the
classifier is language-work standing in for a typed slot the protocol already requires, and the
keyword grader is a deterministic matcher aimed at prose. The typed `direction` slot makes the
classifier redundant, and scoring the slot makes the prose scan redundant. Deleting an LLM call and
a prose-match, not adding them, was the clean move.

THE ARC, and why the gate had to change.

| arm | active_users_fell | dir-gate fired | what happened |
|-----|-------------------|----------------|---------------|
| baseline | 2/3 | 2 | the gate read a before/after PAIR (active_users at two windows) — the agent subtracted two queries |
| + graph_grounding | 0/3 | 0 | REGRESSION: the agent adopted the governed change metric `active_users_growth` (a single signed delta, no pair), which the pair-only gate could not read — so the false "fell" stood |
| + the fix | 3/3, all ANSWERED | 2 | the gate also reads a governed change metric's SIGN (`is_change_metric` + `_change_from_calls`); the false premise is caught and steered to the useful answer |

The regression is the instructive part: making the semantic layer better (a governed
period-over-period metric, §38) MOVED the agent off the pattern its guardrail knew, and blinded the
guardrail. The fix is not a new check but the same check reading the new, better evidence — the
metric's own sign. `active_users_growth = +50` encodes direction (sign) and magnitude (|value|)
together; the useful answer is that signed value read back, not a bare magnitude.

MECHANISM. `direction_vs_evidence` (answer_spec) reads the typed `direction` and the true direction
(`_true_direction`: a before/after pair OR a governed change metric's sign). On a contradiction it
hands the answer back steering to the CORRECTION ("set direction=rose, state it rose by 50; do not
refuse a change you can quantify"), bounded by MAX_CORRECTIONS. The typed `direction` slot is
persisted on the Answer and the row; the false-premise grader scores that slot, falling back to the
prose only for an arm that offers no slot. `FALSE_PREMISE_POLICY` (paired with answer_spec) carries
the correct-and-answer steer into the prompt.

RESULT (rep-3, 46-question held-out suite, R3 cell). `active_users_fell` went 0/3 -> 3/3, every rep
the useful ANSWER (outcome=answer, direction=rose, +50), the gate firing on 2 of 3 to enforce it.

HONEST CAVEAT. The headline totals (correct 131/138, silent 3) sit at baseline level, within the
rep-3 noise floor (§32): the remaining silents (`active_users_growth_web`, `gross_mrr_ytd_stated`,
`mrr_q2_starts_agree`) are governed ANSWER cases with definitional/scope variance, none directional,
none touched by this fix, and they shuffle run to run. The durable, attributable claim is narrow and
real: the false directional premise now lands reliably on the useful answer, gate-enforced, and the
mechanism divides cleanly across LLM / deterministic / protocol with no fragile prose-matching.

## 41 · The dropped segment on a governed metric: the mechanism applies what the model identified

"By how many did active users on the WEB platform grow last week?" The agent selects the right
metric (`active_users_growth`) and the right segment ("web" -> `platform=web`), then serves the
UNFILTERED total (50, all platforms) while its prose claims "web". A named, grounded segment was
identified and then dropped from the query.

WHY THE EXISTING GATE WAS NOT ENOUGH. `applied_segment` detected the drop and handed back the right
instruction — "re-query with filters={activity__platform:'web'}" — TWICE, and the agent re-served
the same total each time without issuing a filtered query, exhausted MAX_CORRECTIONS, and the
unfiltered 50 shipped, mislabelled. The gate could DETECT but not COMPEL, and on cap-exhaustion it
served the number it knew was mis-scoped.

TWO WRONG FIXES, both rejected. Serving the unfiltered total on cap-exhaustion is the silent error.
Refusing the answer is OVER-RIGID — the web slice IS computable (6), so a refuse declines a value
the data holds, the same mistake §40 removed for the false premise. The useful outcome is the web
number, and it is recoverable.

THE ALLOCATION. Each sub-decision to the tool whose strength it is, and the anti-pattern is trusting
the model with a step that is mechanical.

| sub-decision | tool | note |
|--------------|------|------|
| "web platform" -> segment `platform=web`; "grow" -> `active_users_growth` | LLM (language) | its superpower; done reliably |
| does the served call carry that grounded segment | deterministic | a lookup over the governed call's filters |
| APPLY the grounded segment to the metric | deterministic | re-run the served call with the filter, read the value — the mechanical step the model dropped |
| the derived metric IS filterable (filter, not group_by) | protocol / metadata | a usage example; teaches the model so the drop happens less |

MECHANISM. `applied_segment`, on a grounded segment the served call dropped, no longer just instructs
— it INSERTS the filter into the served governed call, recomputes the value (`_segment_value` via
`value_of`), and hands back the exact slice: "the 'web' slice is 6; answer with 6." The model already
did the language (identify web); the mechanism does the mechanics (apply web). Not a refuse (the
value is computable), not the unfiltered total (silent). This is the direction_vs_evidence pattern
extended from READING a fact to APPLYING an identified slot, and it generalises to every dropped
grounded segment.

The derived-metric wrinkle, taught in the usage example: a period-over-period offset metric
(`active_users_growth`) can be FILTERED by a segment (the filter applies to both periods) but cannot
be GROUPED BY a non-time dimension (MetricFlow rejects it). Conflating the two sends the agent to a
`group_by` that errors, after which it falls back to the unfiltered total.

RESULT (rep-3, 46-question held-out suite, R3 cell). The three dropped-segment cases — 
`active_users_growth_web`, `paid_search_spend_q2`, `seo_signups_q1` — all went to 3/3. With the usage
example in place the agent usually applies the filter first try (web -> 6.0 unaided); when it still
drops, the mechanism supplies the slice. `applied_segment` fired 3 times, each supplying a correct
value.

HONEST CAVEATS. The headline totals held at the rep-3 noise floor (correct 129/138, silent 3): the
correct dip versus the prior arm is variance — five flaky cases refused instead of answering this
run — and the one new silent (`spend_per_signup_q2`) is an ORTHOGONAL contested-ratio miss
(marketing_spend vs acquisition_spend, disclosure), on which `applied_segment` did not fire. The
durable, attributable win is the three dropped-segment cases at 3/3 and the clean allocation. One
limit: the hand-back supplies the exact value (compliance is now trivial — state it, no re-query),
which steers hard but is not absolute; the absolute form is value SUBSTITUTION, which overrides the
answer text and was judged too heavy for the gain.

## 42 · Contest propagation through a derived metric: disclose every reading, op-agnostic

A DERIVED value inherits its inputs' contests. If `D = op(x, y)` and an input has a governed rival
(a SCOPE_TRAP in the cluster index — same measure, different scope), then `D` has two governed
readings, `op(x, y)` and `op(rival, y)`, and the divergence PASSES THROUGH the composition. The flat
rival check (`undisclosed_rival`) watches the RAW metric figure, so a served COMPOSITION slips it —
`spend_per_signup` served 50.45 (marketing_spend / new_signups) and mentioned both raw totals, so the
flat check saw "both disclosed" while the reader got only one of the two RATIOS (50.44 vs 43.69).

THE GENERAL MECHANISM (`_composition_contest`), not ratio-specific. A served figure that equals
`op(x, y)` for two governed calls, for any op in a small registry (`ratio, difference, sum, product`),
inherits x's and y's contests. Which op composed the inputs is RECOVERED by matching the served
value to `op(x, y)` — a deterministic lookup over the run's governed calls, no model call. For each
contested input, recompute the composition with the rival substituted; require both READINGS when
they materially diverge and one is undisclosed.

| step | tool | note |
|------|------|------|
| the inputs `x, y` | trace | the run's governed calls (a fact) |
| the op | deterministic recovery | the served value matches exactly one `op(x, y)` |
| which input is contested | deterministic | cluster-index `competitors` |
| the alternate reading | deterministic | recompute `op` with the rival's value |
| disclose both / clarify | protocol steer + deterministic verify | both composed figures in the served text |

The generality is the point: the SAME rule covers a ratio (`spend_per_signup`) and a difference (a
hand-computed change), verified — served 50.45 -> flags ratio 50.44 vs 43.69; served 60019
(61233-1214) -> flags difference 60019 vs 51828; served both -> nothing owed.

THE PROTOTYPE'S KEY FINDING, and why the check must be on the COMPOSED reading, not the input. A
ratio PROPAGATES the numerator contest (marketing_spend 61233 vs acquisition_spend 53042 -> 50.44 vs
43.69, 13.4%). A difference CANCELS a constant base contest: `active_users_growth = active_users(t) -
active_users(t-1)` with the internal/test offset constant week to week gives the SAME +50 whether the
base is `active_users` or `active_accounts` -> no divergence, nothing to disclose. A naive "an input
is contested -> flag" rule would wrongly flag the growth; recomputing the composed readings gets both
right.

A GOVERNED derived metric served as a single call (`active_users_growth`) is the same shape once
expanded through its `type_params` into `op(x, y)` over its input metrics — the extension point. It
does not surface for the current layer (the offset cancels), so the fired path is the hand-composed
one.

RESULT (rep-3, 46-question held-out suite, R3 cell). `spend_per_signup_q2` went 2/3 -> 3/3, the
disclosure now firing on the ratio's numerator contest; silent fell 3 -> 1, the lowest of the
campaign. HONEST CAVEATS: at the noise floor, most of that fall is the silent cases shuffling — the
attributable win is `spend_per_signup` and the op-agnostic mechanism. The run also showed 2
`max_iterations` errors and one new silent (`active_users_growth`), both ORTHOGONAL: the errors are
`mrr_q2_starts` (the campaign's flakiest cohort case) over-exploring under the answerability gate, no
composition-repair fired; the new silent is a garbled growth computation. The composition check fired
only where intended.

## 43 · The measure definition as a first-class artifact: author, verify, challenge, disclose

The spec-first architecture (board-designed, §40–42 were its precursors). When no governed metric
answers a question, the agent's job is not to produce a NUMBER — it is to AUTHOR A DEFINITION, have
it verified and challenged, compute from it, and disclose it. The number is a consequence of the
definition, not the thing produced. A governed metric is the trivial definition, so governed and
ad-hoc flow through one shape. It is coverage-independent: the agent defines the long tail on demand
rather than requiring the layer to already cover it.

THE PIPELINE, each layer at its right tool (LLM / deterministic / protocol), built and tested one at
a time.

| layer | function | tool | guarantee |
|-------|----------|------|-----------|
| author | LLM writes {scope, spec} as structured output | LLM (language) | interpretation |
| coherent | valid definition (additivity/structure) | deterministic | not a Kimball-illegal spec |
| ground | every part exists and joins in the marts graph | deterministic (ontology) | existence |
| bind_scope | every scope component (segment/period/qualifier) is bound | deterministic | COMPLETENESS |
| run_ephemeral | compute the value | imperative shell | execution-BY-CONSTRUCTION |
| challenge_aptness | is this the RIGHT definition? | adversary (validated judge) | APTNESS |
| disclose | the spec IS the account | — | transparency |

Aptness = completeness + interpretation. bind_scope decides completeness deterministically (a
segment/period/qualifier the question named is present, or reported unbound — the silent-drop class
of §41 generalised to the whole scope). Interpretation — is a grounded, bound, executing definition
the one the question MEANS — is the adversary's, the residual no deterministic check reaches.

THE TWO ARTIFACT KINDS follow dbt Semantic Layer practice: a MetricFlow-expressible measure is
authored as a metric (governed / ratio / derived); a genuinely bespoke one (cohort, retention,
custom windowing) as a raw dbt SQL model. Both are verifiable by construction: MetricFlow compiles
and runs the metric; the SQL model materialises and runs. Verification-as-construction — the number
is PRODUCED BY the definition, so it cannot drift; no "does the number match the spec" check exists
to get wrong. The raw author is given the warehouse catalogue + the DuckDB dialect + dbt idioms
(context engineering), which took retention from "gives up" to a reliable, correctly-grained model
(5/5 reps: answer, raw, within-90-days, 5 by-channel rows).

THE ADVERSARY WAS VALIDATED BEFORE IT GATED. A first cut ("refute if you can") flagged everything —
1/6 on a labelled aptness set, useless as a discriminator. Refocused to defect-hunting with governed
metrics treated as authoritative: 5-6/6, the lone disagreement retention within-90 vs at-day-90, a
genuinely debatable definition. It is wired to DISCLOSE the concern (not hard-refuse), the safe use
of a judge validated on a small set; apt_validate.py is the committed held-out check, asserting the
discriminator still holds.

THE A/B (matched transparent policy, rep-2 held-out): arm A computes the tail with hand-rolled
run_sql, arm B via define_measure. Both answer the tail, so the refuse-gold policy mismatch cancels
and the measured question is safety.

| arm | correct | silent | run_sql used | define_measure used |
|-----|---------|--------|--------------|---------------------|
| A hand-rolled | 85/92 | 0 | 4 | 0 |
| B +spec_authoring | 86/92 | 2 | 0 | 2 |

The durable claim is SAFETY: define_measure introduced NO silent error. B's two silent errors are
orthogonal contested-metric cases (active_users_organic, spend_per_signup) hand-served via
query_metric with no define_measure in their traces — the same rep-variance seen throughout; where
define_measure WAS used (retention, both reps) it served a verified, disclosed definition with no
silent error, and hand-rolled run_sql dropped 4->0.

HONEST LIMITS. The held-out gold encodes a STRICT-REFUSE policy for ungoverned measures (retention's
gold is refuse no_governed_definition), so a computed-and-disclosed answer grades correct=False
however sound — the suite cannot score a compute-and-disclose policy, only its safety. define_measure
was used sparingly (2/92): the agent mostly refused the tail upstream, a prompting/usage matter, not
a safety one. rep-2 is directional. The point proven is architectural and safety-shaped: computing
the long tail can be made reliable — grounded, executed-by-construction, aptness-challenged, disclosed
— and every measure so defined is a promotable dbt/MetricFlow artifact. Promotion (spec -> PR into
the layer) and query-leaf execution remain.

## 44 · Contested disclosure by CONSTRUCTION: the mechanism supplies the reading, not the agent

The contested-disclosure gate handed a one-reading answer back and relied on the AGENT to re-serve
both — a probabilistic hop that flaked (active_users_organic served 171 alone, silent). The same
verification-as-CHECK-depending-on-a-compliant-actor pattern §41/§42 had already replaced elsewhere,
not yet carried here, with a cap that shipped the single reading under repair.

construct_disclosure turns the hand-back into CONSTRUCTION: the mechanism has already computed the
rival reading (value_of / the composition recomputed with the rival substituted); it APPENDS it to
the served answer and serves. Both readings reach the reader by construction; the agent's compliance
leaves the critical path. This keeps residual ambiguity handled ONLINE and reliably — the realistic
condition, since no large layer resolves every contest offline.

A REORDERING BUG THE SUITE EXPOSED, and why construct surfaced it. For a served RATIO
(spend_per_signup = 50.44), the flat raw-metric check fired first and constructed the raw numerator
rival (acquisition_spend = 53041), but the reader's alternative ANSWER is the RATIO 43.69/signup.
Under hand-back this stayed hidden (the agent re-derived); construct made the disclosed value
gradeable and the grader caught it. Fix: the composition-contest is tried BEFORE the flat check — a
served ratio's contest passes through the numerator, so the alternative that matters is the ratio
recomputed with the rival, not the raw numerator total. Composition owns a served composition; the
flat check runs only when the served figure is not one (active_users_organic, a single metric, still
falls to the flat construct: active_accounts = 178).

RESULT (rep-3, 46-question held-out, current-best cell + construct_disclosure).

| arm | correct | silent | constructed acts |
|-----|---------|--------|------------------|
| baseline (pre-construct) | 130/138 | 1 | 0 |
| + construct (ratio bug) | 131/138 | 3 | 20 |
| + construct (fixed) | 133/138 | 1 | 28 |

contested_level 36/36, contested_derived 5/6 — the contested tier handled by construction. correct
133/138 is the campaign high; silent is back at the noise floor (the lone silent, mrr_q2_starts, is
the rotating cohort-scope flake, not construct-caused). The mechanism now constructs both readings
for a contested level metric (active_accounts vs active_users) AND a contested ratio (acquisition vs
marketing per signup), online, without depending on the agent to comply. construct_disclosure is
folded into the standard cell going forward.

## 45 · Campaign synthesis: from 13 silent errors to 1, and the architecture that got there

This section ties §35–44 together — the development, the one principle underneath it, and the impact
— so the arc reads as a whole rather than a sequence of patches.

THE SCOREBOARD (silent wrong numbers, rep-3, 46-question held-out suite; the number that matters is
confident-wrong, not accuracy).

| stage | mechanism added | failure class closed | silent |
|-------|-----------------|----------------------|--------|
| baseline (§35) | normalised catalogue | — | 13 |
| grounding (§36) | segment_gate + grounding resolver | ungrounded segment (TikTok as a channel) | 5 |
| answerability (§37) | answerability_gate (three-way) | raw-SQL escape (invented retention served) | 4 |
| usage/segment (§38) | usage examples, applied_segment, governed growth | dropped filter, manual summation, hand arithmetic | 3 |
| ontology (§39) | closed-world graph + check_answerability | answerability judged, not looked up | 3 |
| false premise (§40) | direction from the governed change sign | a false trend confirmed ("fell" when it rose) | 3 |
| dropped segment (§41) | applied_segment APPLIES the filter | a named segment silently dropped | 3 |
| contested ratio (§42) | contest propagation through a composition | a ratio's numerator contest slipping the flat check | 3 |
| spec-first (§43) | define_measure (author/verify/challenge/disclose) | the ungoverned long tail computed unverifiably | 1* |
| construct (§44) | construct_disclosure + composition precedence | contested reading dropped on agent non-compliance | 1 |

*correct rose to a campaign-high 133/138 at §44. The lone remaining silent is a filter-VALUE
grounding error (mrr filtered by cohort_month='2026-Q2' when that dimension holds monthly values ->
zero rows -> a confident £0), orthogonal to every mechanism above and rotating with rep variance —
filter_vocabulary closes dimension NAMES to the layer, not VALUES, which is the open gap.

THE ONE PRINCIPLE. Every mechanism is an instance of the same move, applied at a different surface:
the LLM does semantic FIT (interpretation, language — its superpower); a deterministic mechanism
verifies or SUPPLIES the structural fact; the protocol forces the structure into existence so there
is a fact to verify. The failures were all a MISALLOCATION — the agent asked to do something
mechanical (apply a filter, recompute a rival, pick a direction), and left to remember it. The fix
was never a better prompt; it was to stop asking and have the mechanism do the mechanical part:

- verify FACTS, not prose: the applied filter in the trace, the sign of the governed change, the
  compiled SQL — never the model's account of what it did.
- SUPPLY, don't hand back: applied_segment (§41) inserts the grounded filter and recomputes;
  contest propagation (§42) computes both ratio readings; construct_disclosure (§44) appends the
  rival reading. The both/right answer no longer depends on the agent complying — the pattern that
  fixed the flaky contested tier (contested_level 36/36).
- durable logic in the LAYER: a period-over-period change is a governed derived metric; a ratio is a
  governed ratio; a contest is precomputed offline in the cluster index. The runtime looks a fact
  up, it does not infer it.

THE GENERALIZATION (§43, the spec-first architecture). The end state of the principle: when no
governed metric answers a question, the agent AUTHORS A DEFINITION (a verifiable artifact — a
MetricFlow metric or a dbt SQL model), the deterministic layers guarantee completeness (bind_scope),
existence (ground), validity (coherent) and execution (run_ephemeral, by construction), an
independent VALIDATED adversary challenges aptness, and the result is disclosed. Coverage-independent:
the long tail is DEFINED on demand, not required to be governed in advance — the realistic condition,
since no production layer is ever complete. Every definition it produces is a promotable dbt artifact.

IMPACT, stated honestly.
- Silent wrong numbers 13 -> 1 on the frozen held-out suite; correct at a campaign-high 133/138.
- The durable claims are the CLASSES closed and the architecture, not the last rep: the remaining
  silent rotates with variance at the rep-3 noise floor (§32), and the exact figure is a direction,
  not a headline.
- New capabilities that outlast the numbers: a closed-world answerability graph; verified
  compute-the-tail (define_measure); an adversary validated before it gates; and the online handling
  of residual ambiguity by construction — none of which assume the layer is fully governed, which is
  the point.

OPEN THREADS. The filter-value grounding gap (the remaining silent); define_measure usage/routing
(it fires only when the agent reaches for it); promotion (spec -> PR into the layer); the query-leaf
executor; and the offline-vs-online split (fix what you can offline; handle the residual online) as a
standing policy rather than a per-case choice.

## 46 · Metric anchoring and "a filter that matches nothing is not zero"

The mrr_q2 silent (§45) had three roots, all now closed, and the fixes generalize beyond it.

METRIC ANCHORING (the graph gap). The ontology modelled entities and metrics as separate node types
with no edge between a metric and the dimensions it is defined over, so a governed metric was
unanchored: "MRR from subscriptions that started in Q2" sometimes grounded governed mrr (correct) and
sometimes over-decomposed into raw subscription cohort columns, which — subscription being an island
(no curated join) — grounded to uninstrumented and refused. ontology_source now reads each metric's
entity and filterable dimensions off the manifest (metric -> measure -> semantic model ->
dimensions), and render shows "metric.mrr (measures subscription; filter by: started_date,
cohort_month, plan, status): …". The graph now shows a governed metric is sliceable, so the model
grounds a scoped metric as governed instead of decomposing it. Paired with a resolve_measure clause —
a governed metric restricted through its OWN dimension (segment, period, cohort) stays governed — the
mrr cohort question grounds 6/6 governed; the anchor helps the hardest phrasing 0/6 -> 5/6 alone, the
clause carries it to 6/6, and answerability targets hold 4/4.

A FILTER THAT MATCHES NOTHING IS NOT ZERO. A filtered query that matched no rows reached the model as
a bare (None,)/(0,) it served as a confident zero — "£0 MRR for Q2", "0 active users in Japan"
(implying we operate there). Two shapes, both flagged in the query_metric result:

| shape | example | value | caught by |
|-------|---------|-------|-----------|
| empty | mrr cohort_month='2026-Q2' (SUM of no rows) | None | no numeric measure came back |
| unknown | plan='enterprise', country='JP' (COUNT of no rows) | 0 | filter value not a governed member |

The unknown check is the NON-BRITTLE form of filter-value grounding: it fires only for a dimension
the layer ENUMERATES (authoritative member list), case/whitespace-normalised, so a valid value in any
casing ('MONTHLY') is never flagged and an unbounded dimension (dates) is left to the empty check.
The flag lists the dimension's real values as an advisory hint so the model re-queries, or refuses —
never serves 0. Verified end-to-end: "active users in Japan" -> the agent filters country='JP' ->
GUARD FIRED ('JP' is not a governed value; its values are US, BR, …) -> refuse
ungoverned_dimension_value, declared=None, no confident zero served.

DEFENSE IN DEPTH, observed. The guard is a BACKSTOP and the traces show it should rarely fire,
because upstream fixes steer the agent away from bad filters first: mrr_q2 (anchor + clause + usage
example -> the correct period query, never a bad filter), enterprise_plan (the catalogue lists plan
values -> the agent refuses from list_metrics, never queries). It fires only on the residual the
upstream could not anticipate (Japan — no usage example covers every non-existent country). Prevention
where possible, a deterministic catch for the rest — so a confident zero cannot ship regardless of
which upstream fix was missing.

RESULT (rep-3, current-best cell + all fixes). mrr_q2_starts_agree closed 3/3 (was the §44/§45
silent); contested_derived 6/6, contested_level 35/36; the empty/unknown guard fired twice, both with
correct outcomes (enterprise_plan -> refuse, acquisition_spend×partnerships -> answer), and NO silent
was caused by the anchor or the guard. Headline correct 132/138, silent 3 — at the rep-3 noise floor,
the set rotating (mrr_q2 out, active_users_ios contested-disclosure and gross_mrr_ytd period-scope in),
both orthogonal to this work. mrr_q2 joins the closed classes; the durable claim stays the classes and
the architecture, not the last rep.

## 47 · Grading a contested question: disclosing both readings is a correct handling, not a miss

`grade.py` already scores the FOURTH ACTION correct: an answer that puts every candidate's figure in
front of the reader (`_disclosed_both`) is `bucket="right"`, because the reader holds both numbers and
can pick — it costs one sentence where a clarification costs a round trip. The scorer did not follow.
`balanced_accuracy` credited pile C only for a literal `clarify` OUTCOME, so a run that resolves every
contested question by disclosing both readings scored pile-C accuracy 0 and read `balanced_accuracy`
0.667, while the operational board showed the contested class handled and `silent_error` at its floor.
The two numbers described different things, and the lower one described the SCORER, not the agent.

The fix makes pile-C accuracy the count of contested questions handled correctly, by EITHER route:

| pile-C outcome | reader can tell? | credited |
|----------------|------------------|----------|
| clarified (asked which reading) | yes | correct |
| disclosed both readings' figures | yes | correct |
| served ONE reading silently | no | the silent error (unchanged) |
| refused a question that had two answers | yes (over-refusal) | not correct |

`contested_disclosed` reads the grader's `correct` on a contested answer row, so the definition of
"handled" lives in ONE place (`grade.py`), not restated in the scorer. `silent_error` is untouched:
serving one reading silently is still the only pile-C failure it counts. On the same rep-3 rows this
moved `balanced_accuracy` 0.667 -> 0.992 with no change to `silent_error`. Two stale docstrings that
still read "only asking is correct" — in `selective.py` and the `grade.py` header, both contradicting
the fourth-action code beneath them — were corrected. A `test_report.py` case pins it: a disclosed
answer and a clarification score alike, a single reading served silently does not.

## 48 · The contested change: the delta is the layer's arithmetic, not the model's prose

The last silent error was a contested CHANGE — "by how many did completed habits change from May to
June?", answered by two governed metrics that do not cancel over the difference (`value_moments`
excludes internal/test accounts, `total_value_moments` includes them). The model queried the two
LEVELS by tool and then computed the difference in PROSE: one run wrote "15,329 - 11,640 = 1,689"
where the delta is 3,689 — a wrong number, and only one of two readings. Flaky at 1 in 3.

A hand-computed number in prose is a missing tool. The generic contest check (§42/§44) cannot own
this shape: it substitutes a rival into ONE input, which for a difference of the SAME metric at two
windows gives a mixed nonsense reading (`rival@May - metric@June`), and it only fires when the served
figure already equals the correct delta — so it cannot rescue a delta mis-computed in prose.

`_change_disclosure` owns the before/after shape. It reads the run's OWN two windows (`_period_pairs`,
the grouping shared with the directional reader), computes the base delta AND the governed rival's
delta, and supplies both by CONSTRUCTION — the same supply-don't-hand-back move as the applied segment
(§41) and contest propagation (§44). The allocation is the recurring one:

| sub-task | layer | before |
|----------|-------|--------|
| the subtraction (level_b - level_a) | deterministic, from the two governed calls | the model's prose |
| which readings exist (the governed rival) | deterministic (the cluster index) | the model's prose |
| the narrative around the numbers | the model | the model |

No new flag: it extends `disclosure_check`/`construct_disclosure`, tried FIRST in the disclosure path
ahead of the composition and flat checks. A mis-computed prose delta is corrected and both readings
reach the reader on every run — the arithmetic and the disclosure both leave the model's prose.

RESULT (rep-3, current-best). Target case 3/3 (and 6/6 at rep-6). Full board: `silent_error` 0.000,
pile C 42/42 disclosed and 0 served, `balanced_accuracy` 1.000 (with §47), coverage 1.000, pile A
51/51, pile B 0 served — no over-fire. A `test_change_disclosure.py` unit test pins the two paths
deterministically: a wrong prose delta is replaced by both correct governed deltas, and an answer that
already discloses both is left untouched.

CAMPAIGN: 13 silent errors to 0. The durable claim stays the closed failure CLASSES and the
allocation that closed them — LLM for language, deterministic mechanism for structure, protocol to
force structure into existence — not the last rep of the last run.

## 49 · The model-call counter under concurrency: a per-run meter, not a shared-counter delta

The per-answer `model_calls` (f074db2) was wrong under concurrency. The runner builds ONE provider
object and shares it across the thread pool, and each run reported the START/END DELTA of a counter
on that shared object — which is a TIME WINDOW over every worker's calls, not this run's count. At
concurrency 4 the held-out run reported a mean of 27 calls per answer against ~7 real ones: inflated
by the pool width, exactly. The increment itself was also a bare read-modify-write, so concurrent
runs could additionally lose counts. §46's "roughly five" was an architectural estimate (three gates
plus disclosure), not a measurement; neither figure was trustworthy.

The fix makes the count a property of the RUN. `run_agent` wraps the shared provider once per run in
`_MeteredModel`, which counts `respond()` on itself and delegates everything else. One wrap point
covers every consumer — the main loop, every classifier/gate through `run.model`, and
check_answerability / the define_measure sub-agent through `toolbox.model` — because every call site
receives the model as an argument rather than importing one. The provider-side counters are removed:
their only consumer was the delta, and a second counter with a different meaning is a misreading
waiting to happen.

Pinned deterministically, not statistically: a barrier holds four concurrent runs' single calls in
flight at once, so the old delta would provably report 4 for every run; the meter reports 1 for each
(`test_model_meter.py`). Live at the contaminated regime (rep-3, concurrency 4):

| question | shared-delta mean | per-run mean | tool calls |
|----------|------------------:|-------------:|-----------:|
| h_a_ios_opens_may           | 25.3 | 6.3 | 2.3 |
| h_b_active_users_fell       | 32.3 | 7.7 | 2.0 |
| h_c_habits_change_may_june  | 27.7 | 7.3 | 3.0 |
| h_c_spend_per_signup_q2     | 33.7 | 9.7 | 4.0 |

The trustworthy cost figure is ~6-10 model calls per answer by pile (a plain pile-A lookup at the
bottom, a contested ratio with the full gate stack at the top), and the counts now scale with the
question's own complexity rather than with the neighbouring workers' activity. Graded outcomes are
untouched — the counter was observability only, and no silent-error or accuracy figure moves.

## 50 · The fresh frozen suite: the campaign generalizes partially, and the gap has a name

The first held-out suite stopped being held out: 28 full-suite runs were taken against it while the
§36-§49 mechanisms were iterated, several fixes were written against its specific questions, and its
headline (silent errors 13 to 0) therefore measures FIT — §17's own standard, violated by the
campaign that followed it. Before publication, a second suite was authored and run ONCE with the
mechanisms frozen at 9b50e81.

`heldout2.yml`: 46 questions, same pile design, authored under §17's protocol from the schema, the
catalogue and the pile definitions only, every oracle executed and every pile membership proved by
`heldout2_prove.py` BEFORE the file was written. Protocol-blind, not author-blind — the author is
the session that built the mechanisms, so blindness is enforced by procedure, and the proofs changed
the suite three times during authoring (a drafted answerable case proved contested and moved piles;
the cancel tier is empty because no unused cancel slice exists in the data; a spend window straddling
the start of the spend data was replaced). One authoring erratum surfaced by the run itself: the
organic-channel gold was first written against the catalogue prose and corrected to the staging
model's rule (every unmatched channel falls to organic), under which the agent's served figure was
correct; the correction is recorded in the case note and the re-score reported openly.

| metric | dev suite (heldout1) | frozen (heldout2) |
|--------|---------------------:|------------------:|
| silent_error | 0.000 | 0.080 (11/138) |
| coverage | 1.000 | 0.843 |
| balanced_accuracy | 1.000 | 0.873 |
| pile C disclosed | 42/42 | 41/42 |

Three readings, in order of importance:

1. THE DEV-SUITE ZERO MEASURED FIT. 0.000 there, 0.080 here. The campaign trajectory is an
   engineering log of a development suite, and the frozen number is the one a publication can carry.

2. THE CAMPAIGN GENERALIZES PARTIALLY. The contested-disclosure machinery holds off-suite (41/42
   disclosed, one slip), pile B holds 43/45, and the frozen silent rate sits well below the
   pre-campaign dev baseline (13-22 per 138). The deterministic mechanisms carried; what did not
   carry is everything still resting on the model's prose.

3. THE RESIDUAL HAS A NAME. The 11 genuine silents: stated-scope binding 5 (a question that names
   its scope — "counting refunded", "including partnerships" — served through the wrong metric or
   the named slice alone), false premise accepted 2, period binding 2 (last week answered with the
   prior week), dropped segment 1, contested-disclosure slip 1. The dominant class was ALSO the dev
   suite's own rotating flake (gross_mrr_ytd_stated): nothing deterministic yet verifies that a
   scope STATED in the question is bound to the served metric. That is a mechanism gap, now
   measured, not a mystery.

## 51 · The trace contract: decisions become records, and the gates verify them

The frozen-suite diagnosis (§50) reduced to one law: the repair chain is a trace-reader, so it can
only guarantee what the trace represents. Every silent error was a value or a decision that reached
the answer outside the typed trace. Four moves implement the law; each was verified live on the
question that exposed its gap, mechanisms frozen only after the fix.

1. THE EVIDENCE UNION. Every value-producing tool writes typed records onto its step —
   {kind: governed, metric, args} for a governed evaluation (including a define-authored spec's
   metric/derived leaves), {kind: raw, sql} for agent SQL — and `_governed_calls` reads the union.
   The define path stops being a second data path the gates cannot see: a spec-computed number now
   meets contest disclosure, applied segment, direction and provenance exactly as a queried one.

2. THE BINDING CHECK. `question_chose_scope` now reports WHICH reading the question's words name
   (with inclusion polarity: "counting X" names the reading whose scope contains X), and a
   deterministic equality compares it with the served reading at every scope stand-down. Mismatch:
   a bounded hand-back with the correct value SUPPLIED; at the cap, the named reading's figure is
   constructed into the answer. Live proof on the 3/3 silent class: the model still picked `mrr`
   first — the bias is untouched — and the gate handed back "question names gross_mrr"; the
   re-serve declared 2,754.00. The wrong prior still fires; the verified decision no longer ships.

3. SELF-REPORTS VERIFIED, ARITHMETIC OWNED. The direction gate no longer trusts the typed slot
   alone: when the slot makes no claim but before/after evidence exists, one validated classifier
   reads the served text and the sign test stays code (closing the not_a_change dodge). A served
   headline must DERIVE from the run's own values — an evidence value, one binary composition of
   two, a rendering x100/100, or a row count (`underived_figure`; the -60,015 row is its pinned
   test). A window substitution after a governance block is disclosed by construction, read
   entirely off the trace. A single time-grouped call now counts as before/after evidence.

4. COMPOSITION LAW. Verifiers run before construct-capable checks and constructions attach to the
   final serve, so a later hand-back can no longer destroy an earlier repair. Constructions no
   longer spend the correction budget (`hand_backs`, not `claim_retries`). At the cap the checks
   still run and an unresolved one is served WITH a mechanism caveat — the old cap skipped the
   checks entirely and shipped the thing under repair unmarked. The substitution judge is narrowed
   out of wrong-variant (the binding check's job, done deterministically). One coverage authority:
   the per-metric max(timestamp) no longer masquerades as a coverage bound — a request reaching at
   most one day past a metric's last row, inside the extraction window, is a quiet tail (a true
   zero), not missing data; a larger overshoot still blocks (the exp-04 fixture's intent).

Probe (3 diagnosed questions, rep 1): 3/3 correct, binding observed live, polarity clean, the
false-premise row answered with the correct contradiction. Suites: 80 engine + 121 harness.

## 52 · The mechanics audit, and the six findings it earned

Ten fresh traces (rep 1, every question shape) were read end to end for unexpected, suboptimal or
over-rigid behaviour. Outcome quality was clean — 10/10 handled, 0 silent — so the audit's yield
is the six findings below, each addressed at its root.

F1 — THE LAYER OMITTED A REAL RELATIONSHIP. A refusal cited "subscription and user are not
related — cannot be joined" while fct_subscriptions has always carried user_id; only the YAML
declaration was missing, and the graph truthfully propagated the gap into wrong refusal REASONS.
Fixed three ways: the FK declared; a lint for the class (`undeclared_join_keys`: a table column
matching another model's primary-entity expression, undeclared, is a finding); and — because the
fix was verified, not assumed — a REGRESSION the new join exposed: with subscription→user
joinable, the resolver mapped "free-trial conversions" onto plain `paying_users`, dropping the
qualifier — a wrong-metric silent in waiting. A qualifier rule now binds both classifier paths: a
measure restricted to a population the graph does not capture is uninstrumented, never the
unrestricted metric. Verified 5/5: trial→uninstrumented (honest reason), paying-users-by-region→
governed (the unlock kept), revenue-per-employee→uninstrumented (no over-application).

F2 — COVERAGE RITUAL. Traces pre-checked coverage for windows trivially in range, once AFTER the
query had already succeeded. Coverage is enforced at the data plane on every query; the agent-side
tool exists to mint citable evidence for a refusal. The tool description now says so — the action
space, not prompt prose, is the steering surface. Probe: zero ritual calls.

F3 — THE CATALOGUE IS PRELOADED, NOT FETCHED. Nine of ten traces spent their first turn on
list_metrics — a guaranteed round trip for ~2k tokens the prompt can simply carry (and a static
prefix is prompt-cache-friendly where a per-run tool result is not). `refresh_catalogue()` appends
the current rendering to the system prompt, variant-aware because the rendering is a treatment;
the fingerprint covers it; the tool stays for re-reading. Probe: zero list_metrics calls; the
plain lookup went from 3 tool calls to 1.

F4 — PASSING GATES LEAVE RECORDS. The new checks stood down silently, so a stored trace could not
distinguish "verified and passed" from "never engaged". Binding, derivability, text-direction and
window checks now write an `allowed` act when they engage and pass.

F5 — ONE SEMANTIC JUDGEMENT PER FACT. check_answerability's verdict is recorded as a typed
`resolution` record on the step (the Decision record, live), and the measure-substitution judge
stands down when the served figure is a value of the metric the question was already resolved to.
Risk-tiered verification: the judge runs only where no resolution covered the serve.

F6 — AND THE AUDIT CAUGHT ITS OWN AUTHOR. The value-slot contract was first implemented as a
hand-back, which fought a habit the protocol already absorbs (outcomes.py recovers the number and
records `value_recovered`) and burned three round trips per answer — the exact over-rigidity the
audit exists to find, introduced while fixing it. Rewritten as a constructor: when the answer
field states exactly one figure, the mechanism fills the empty slot itself. The probe also caught
an off-by-one in the new hand-back budget (three corrections where the contract says two).

Cost on the re-probed questions, before → after: tool calls 3→1, 2→1, 2→1, 4→2; model calls
7→5, 6→5, 5→4, 8→5. The board held 4/4 with the contested ratio disclosed. The bundle now goes to
a full dev-suite rep-3 before any frozen confirmation is spent.

## 53 · Two residuals from the bundle run: one span of words, one decision; the sign is a claim

The bundle's dev-suite run (silent 11 -> 3) left two defects, both diagnosed from their traces and
both closed deterministically.

ONE SPAN OF WORDS FEEDS ONE DECISION. The binding check verified gross_mrr as the named reading and
constructed 2,754 — then the segment machinery read the SAME words ("counting subscriptions that
were later refunded") a second time, as a restriction to status='refunded', and overrode the
verified answer with the refunded-only slice (68.9, 2 of 3 reps). Two classifiers each made a
defensible reading of one clause; nothing said the clause was already spent. The guard is in
`_resolve_segment`: a named segment phrase that overlaps the quote the scope classifier consumed as
the METRIC choice is a definition discriminator, not a filter, and the segment machinery stands
down with an `allowed` act. Re-probe: 3/3 binding holds, no metric_brief act, 2,754 every rep.

THE SIGN IS A CLAIM. A declared value of -(v1-v0) presents the change as a fall whatever the slot
or the prose says — the residual dodge after both the slot and text checks: headline -6,015 with an
explanation admitting the rise. `direction_vs_evidence` now reads the SIGN: value ~ -delta against
rising evidence is a contradiction, handled like any directional claim. The fall convention is
deliberately spared (a drop is served as a positive magnitude). Re-probe: 3/3 correct, and the
three reps exercised three DIFFERENT layers — the model's own contradiction, a grounded_measure
catch, and the direction gate on a declared `fell` — defense in depth observed rather than
asserted. Both guards pinned in test_trace_contract.py with their negative cases (the same phrase
outside a consumed quote still resolves as a segment; a positive fall-magnitude passes).

## 54 · Class A closed: the member anchor, and a floor that makes judge error loud

The scope judge gained enforcement teeth with the binding check (§51) and promptly showed the cost
of an unvalidated forcing gate: one rep inverted the side — the judge read "counting refunded" as
naming `mrr` — and the gate beat a correct gross-MRR serve into the net figure. A gate whose
judge is right two times in three FIXES a silent and whose third time MANUFACTURES one is
mis-designed regardless of the judge's accuracy, because the downside can be removed structurally.

Three layers now stand where the bare judge stood, in order of authority:

1. THE MEMBER ANCHOR — the side decided by STRUCTURE where structure can decide. Each reading's
   where-filters (a closed grammar our own layer renders; `metric_filters()` exposes them
   verbatim) are evaluated over the discriminating dimension's member vocabulary: mrr's scope
   over status is {active}, gross_mrr's is {active, refunded}; the difference is {refunded}; a
   quote concept matching a difference member plus the quote's polarity picks the side. A v1 that
   matched catalogue PROSE was scrutinised and rejected — morphology, negation windows and
   rewording are prose's fragilities, and both mrr descriptions mention refunds, so prose cannot
   even decide the pair that failed. The member sets can. Boolean dimensions match through the
   dimension name's tokens; non-enumerated dimensions, unparseable filters and concepts that are
   not member tokens leave the anchor SILENT — real language stays the judge's.

2. THE JUDGE, now bounded: a closed two-value enum, quote-verified, off-axis-guarded — an
   "irrelevant metric" is not expressible, only the wrong side of the right pair is.

3. THE FLOOR — a forced swap always leaves BOTH figures in the answer field, and the cap
   constructs both readings rather than the named one. A judge inversion now costs a redundant
   clause, never a silent number; the property holds by construction, not by judge accuracy.

Scrutiny on three adversarial questions (rep 3, 9/9 correct with act-level provenance): the pair
prose could not decide, decided 3/3 by member sets; the POLARITY TRAP — "excluding ... refunded",
where keyword matching inverts — 2/3 anchor-confirms and 1/3 the anchor OVERRODE a live judge
inversion (the exact §53 failure, reproduced and neutralised in one probe); a boolean-dimension
phrasing ("counting our internal staff") decided 3/3 through the name path. Twelve unit cases pin
both polarities, pair-order invariance, and the three silence conditions.

## 55 · Class B1 closed: the loaded-question contract

The generalised form of the false-premise residual: a question can EMBED a claim ("why did
signups collapse") and an answer that neither contradicts nor refuses it — a bare count — has
silently ratified it. The contract has four layers, each allocated to the layer that owns it:

- ENTRY: `question_presupposes` extracts a TYPED claim record {type, claim, quote} — an
  extensible enum (direction verified today, the one measured class; existence and causal already
  have owners), minimal-span quote-verified so the mechanism can never put words in the asker's
  mouth. Validated 10/10 on the boundary that matters: ASKING about a direction ("did signups
  grow?") is not ASSERTING one. The one validation miss was the quote-specificity filter
  rejecting a whole-clause quote; fixed in the prompt (quote the asserting verb), re-proven.

- MID-RUN: the [premise] steering line — the moment the run's own calls complete a comparison
  contradicting the claim, the correction is appended to the tool result the model is already
  reading, so generation proceeds from the corrected premise instead of being repaired after
  committing to prose. Scrutiny exposed a reader blind spot here: both quarters queried GROUPED
  (by month, by channel x region) never yielded a pair, so the contradiction the run's own
  windows established went unchecked. `before_after_from_calls` now strips the grouping and
  re-reads the two period totals through the layer — the layer computes the totals, so
  additivity stays its problem, and the fabricated hand-summed figures the ungeneralised reader
  permitted (734 -> 1,234 for a true 637 -> 1,214) did not recur once steering engaged.

- EXIT: the conditional requirement — with a verified directional presupposition AND
  contradicting evidence, a stance-free `direction` slot is a contract violation and is handed
  back (the not_a_change dodge closes exactly where it matters, and nowhere else: an honest
  question or an evidence-free run never pays). The filled slot is verified by the existing gate.

- FLOOR: the constructed correction, with the governed figures, into the answer field. Gated on
  the deterministic sign test over the run's own values, so a false-positive extraction cannot
  produce a wrong note.

Live: 9/9 across the two measured failure questions and a neutral control (rep 3) — steering
observed on both premise questions, the control untouched, and every contradiction stated with
the true figures. The requirement and the floor stood down because the steered model behaved;
their firing paths are pinned by unit tests, which is the intended shape: the earlier layers make
the later ones rare.

## 56 · Class B2 closed: derivability is the reader's contract

The last ledger class: figures computed in the model's head and served in prose — "fell by 39%,
from 1,039 to 636" for a true 637 -> 1,214, with the typed value slot empty, so the slot-only
derivability check stood down. The widened gate re-draws both sides of the comparison:

- THE CHECKED SET IS WHAT THE READER RECEIVES: the answer field's numbers plus the typed value;
  the explanation stays advisory. Date debris is masked first — the raw parser reads
  "2026-04-01" as three numbers and "Q1 2026" as two, and every one would be an underivable
  "figure" and a false hand-back.

- THE EVIDENCE UNIVERSE IS EVERYTHING THE RUN'S RESULTS SHOWED THE MODEL: typed result values,
  the numbers rendered in result texts (a figure copied from an [also] or [premise] line the
  mechanism itself wrote is derived from the run, not from the model's head), each step's summed
  values (a stated total OF a breakdown is legitimate), and row counts.

- THE DERIVABLE OPS: one binary composition of two evidence values, the canonical percent-change
  form (a-b)/b — found missing by the unit pins: "+90.6%" is one analytics concept, not chained
  arithmetic — and x100/100 renderings. A multi-term hand-sum across arbitrary cells still
  fires, and should: that is the prose arithmetic the doctrine forbids, and the repair says so —
  recompute through the tools.

- THE MATERIALITY LINE, found honestly by a wrong test expectation: a served 636 for a true 637
  sits within the 0.5% slack — inside the suite's own grading tolerance, where "wrong" is not a
  category. The gate polices fabrication beyond the materiality line, not rounding; the pin now
  asserts 636 is deliberately NOT flagged while 39% and 1,039 are.

Live scrutiny (rep 3, three cases): the fabrication question served breakdown echoes and
figure-free rebuttals — allowed and silent respectively, zero fires; the contested change with
mechanism-written rival figures — allowed 3/3 (the echo rule earning its place); the legitimate
prose ratio — allowed 3/3. Zero silents, zero over-fires, and a provenance act on every
multi-figure answer, so "verified and passed" is on the trace. One unrelated visible over-refusal
flake (a "why" question punted as underspecified) is recorded as model variance, not a gate event.

The three-class ledger from §50's frozen measurement — the scope inversion, the loaded question,
the prose figure — is now closed: A by structure with a floor, B1 by a typed entry contract with
steering, B2 by widening an existing deterministic gate to the reader's surface. Each carries a
validation set or unit pins, and each was scrutinised on adversarial cases before being trusted.

## 57 · The regression round: two of four fixes were this session's own bugs

The full-suite run after closing classes A/B1/B2 read 4 silents — and the traces showed two of
them were introduced BY the closing work, caught by their first full-suite exposure. Recorded
plainly, because the mechanism that caught them is the finding:

- POLARITY ORDERING: "not counting staff" matched "counting" in the include-word list, which was
  checked first — the anchor read an exclusion as an inclusion and overrode a correct serve, and
  the binding gate enforced the inversion 2/3. Exclusion is now checked first: a negated phrase
  can never win as its own positive.
- THE FLOOR THAT NEVER FIRED: the inversion floor compared served_value with named_value — equal
  BY DEFINITION on a post-swap match — so the both-figures append was dead code, and its unit pin
  had blessed it with unrealistic operands (two different values for the same side). The floor
  now receives the OTHER side's value explicitly, and the pin uses the operands production
  actually produces.
- NAME-ONLY QUOTES: the scope judge accepted "marketing spend" — the metric's own name — as a
  scope choice, violating its own instruction; a quote equal to either side's name is now
  mechanically rejected as not-chosen.
- ADDITIVITY-GATED SUMS: B2's per-step-sum rule legitimised the canonical roll-up error — three
  monthly DISTINCT counts summed to 1,823 "quarterly actives". A stated total of a breakdown is
  admitted only when the layer says the metric is ADDITIVE (`semantic.additivity`); unknown
  additivity keeps the sum out.

Targeted probe 9/9; the full board moved 4 -> 1, with every closed class staying closed and pile
C at 42/42 disclosed. The remaining row was the Instagram substitution — §58's subject — whose
trace also showed a BUDGET RACE: the one check that saw "Instagram grounds to nothing" was dodged
by pivoting from clarify to answer, and a trivial dropped-date-filter quarrel then consumed the
last correction, so the cap caveat quoted the wrong defect.

## 58 · The member license: world knowledge proposes, documentation licenses

The Instagram trace is the sharpest allocation lesson in the campaign. The model KNEW the channel
list ("Instagram (a subset of paid_search)" is in its own probe text): more context could not
have helped, because the failure was not ignorance but an UNLICENSED INFERENCE — world knowledge
folding an unknown term into a plausible sibling. And the oracle it asked four times answered the
measure axis truthfully each time ("ad spend is governed") while the defect lived on the member
axis, one level below the ontology's closed-world floor.

The fix extends the closed world one level down, with the licensing rule as its heart:

    a mapping from a phrase to a dimension member is honoured only when the governed layer's
    OWN TEXT licenses it — the member's name, or the member's clause of the dimension's
    description ("content_seo is content marketing and SEO" licenses the phrase "SEO").
    World knowledge may propose; only documentation may license.

`core/members.licenses()` is the pure decision (deterministic token evidence against governed
text); the license COUNT routes exactly as the metric level always has: one license serves with
the mapping DISCLOSED, several is a member-level contest (each figure, or clarify), zero is the
closed world speaking — refuse `ungoverned_dimension_value`, never fold. The check now runs at
BOTH ends: `check_answerability` gained the member axis (the four probes that each licensed the
substitution now each block it, or hand the model the licensed mapping to state), and
`segment_gate` runs the license path FIRST — deterministic, ahead of the judge whose flicker let
the fold through — and now LEADS the verifier phase, so a substitution can never again lose the
correction budget to a citation quarrel.

Scrutiny (rep 3, 9/9, zero silents): "Instagram ads" refused 3/3 with no folding; "SEO" served
the content_seo slice 3/3 at 3,605.41 with the mapping stated — licensed by the documentation;
"Google search ads" served paid_search 3/3 at 12,786.81 — licensed by the member name, and the
organic reading correctly does NOT exist because the governed text never declares it. That last
case is the doctrine in one line: synonymy is a governed, auditable artifact — wanting another
reading is a YAML edit and a re-fingerprint, not a model behaviour. (Production layers declare
`synonyms:` explicitly — Cortex-Analyst-style; the clause check is this fixture's version of the
same registry.) One suite alignment: instagram_ads accepts `segment_undefined` as a synonymous
refusal code, matching the enterprise_plan precedent.

## 59 · The license gate's first full-suite exposure, and the clean board

The member license (§58) was committed after a three-case scrutiny — all three on the channel
dimension, where the governed text happens to spell its synonyms. Its first FULL-suite exposure
found the four failure modes the scrutiny's narrowness missed, and the board briefly read worse
than before the gate existed (3 silents, 9 over-refusals — every one caused by the new gate
refusing correct answers or burning the correction budget on false contests):

| failure | cause | fix |
|---------|-------|-----|
| "organically" licensed to nothing | exact-token match; no morphology | stem matching (a >=4-char prefix either way: "organically" ~ organic, "referrals" ~ referral) |
| "Germany", "the Philippines", "Indonesia" licensed to nothing | the country description declared ISO codes only — name-to-code shares no tokens | the doctrine applied to OURSELVES: the synonyms are now DECLARED in the layer ("DE (Germany); PH (the Philippines); ...") — a YAML edit and a re-fingerprint, exactly as §58 prescribes for any wanted reading |
| "web platform" licensed to all four platforms | 'platform' appears in every member's clause — a DIMENSION descriptor read as a member selector | generic-token suppression: a token from the dimension's own name, or one supporting more than half the members, is dropped before deciding |
| "the Philippines" licensed to IN as well as PH | substring clause assignment: the code IN sits inside "PhilippINes" and "IndonesIa" | word-boundary clause assignment |

Verified: 8/8 license verdicts on the full phrase set (the three §58 cases unchanged, the five
damaged phrasings restored), four new unit pins naming each failure mode, and a 7-question probe
across the damaged set — 0 silents, contested 6/6 disclosed, Instagram still refused 3/3, with
only the standing Germany layer-boundary refusals remaining (new_signups genuinely cannot filter
country; the honest `dimension_not_supported`).

THE CLEAN BOARD. The full rep-3 rerun (concurrency 8, zero provider errors): silent_error 0.000
over 138 attempts — the first fully clean board on this suite. Pile A 47 right and 0 wrong with
4 visible refusals; pile B 45/45 refused; pile C 42/42 handled (41 disclosed, 1 clarified), 0
served silently; balanced accuracy 0.974. The dev-suite arc across the campaign: 11 -> 3 -> 1 ->
0, with every closed class holding — the scope inversion (member anchor + floor), the loaded
question (premise contract), prose arithmetic (reader-surface derivability), and segment
substitution (the member license, which itself cost one bad board and four honest fixes between
its scrutiny and this line).

The standing caveat stands: this is the DEVELOPMENT suite, iterated against throughout. The
publishable number is a fresh frozen heldout3 under the §17 protocol, authored blind and spent
once.

## 60 · Spec-authoring: the record corrected, the channel rehabilitated, and its first real number

THE RECORD, PLAINLY. Every published board in this experiment — including §59's clean board — ran
WITHOUT spec-authoring: the flag was never in the named standard cell, `define_measure` fired zero
times in every measured run, and a smoke A/B (three target questions, both cells) showed the flag
changes nothing because its trigger was dead — the resolver had stopped emitting COMPUTABLE at
all. §45's scoreboard row credits validated-but-unmeasured machinery; this section replaces that
credit with a measurement. The distinction that survives review: the runtime spec path was
overclaimed; the PROMOTION half (spec -> dbt/MetricFlow artifact -> PR -> governed) was always
listed as an open thread and remains unbuilt, not overclaimed.

WHY THE TRIGGER DIED — the enum-coverage lesson. The COMPUTABLE verdict is a routing decision by
a judge, and it was the one enum class with no validation coverage: aptness, scope and premise all
had labelled sets; the three-way resolver did not. Every safety rule of the campaign (qualifier,
event kind, prefer-uninstrumented) pushed mass out of the middle class, and nothing went red
because the standard suite's gold applauds refusals. `resolve_validate.py` now pins all three
classes (canonical computables, governed stay-put, uninstrumented traps).

THE REHABILITATION, three deterministic fixes measured by that set (4/10 computable-class before,
10/10 after):
- the metric-as-entity BOUNCE: an ingredient citing a metric where an entity belongs is a
  detectable contract violation, repaired with one bounded retry whose feedback names the owner
  entity and its real attributes;
- the COHORT-RELATION clause: a measure relating two events per account across time (conversion,
  survival, time-between) is never a single governed stock metric — paying_users counts today's
  payers, not a cohort's conversion;
- KEY-EVIDENCE EDGES in the graph: a scanned mart table carrying another entity's key column by
  the warehouse's own convention (user_id -> user) IS joined. "Entities are not related" had
  shipped as a wrong refusal reason three times — the undeclared subscription FK (§57's lint) and
  twice for scanned fact tables that carry user_id; the same structural evidence the lint accepts
  is promoted into edge construction, still under-claiming outside the convention.

THE FIRST REAL NUMBER. A five-question TAIL SUITE (computable measures with proven oracles;
`no_governed_metric: true`; gold = the defined-and-disclosed figure — the only suite shape on
which spec-authoring is measurable, since the standard suite's gold refuses the tail). A/B at
rep 3 under the transparent policy:

| cell | define / run_sql calls | right | silent |
|------|-----------------------:|------:|-------:|
| transparent_compute                 | 0 / 29 | 7/15  | 0.40 |
| transparent_compute + spec_authoring | 17 / 0 | 11/15 | 0.13 |

Authored-and-verified definitions replaced hand-rolled SQL entirely, and the worst hand-rolled
class (a cohort-survival question, 3/3 silent) went 3/3 correct authored. The delta is causally
attributable: same policy, same questions, the only change is who writes the definition — the
model's prose SQL, or the typed spec pipeline with grounding, coherence, execution-by-construction
and the aptness challenge. Residual: 2 silents remain under authoring (definitional-latitude
misses on interval questions) — the aptness challenger's territory, and the honest price of the
tail.

WHAT THIS EARNS AND WHAT IT DOES NOT. Spec-authoring now has a measured claim: on the computable
tail under a transparent policy it roughly triples correctness-per-silent against hand-rolled SQL.
It has NO measured claim on the strict-governance suite, where its correct contribution is zero by
design — the flag stays out of `current_best`, and a future promotion into any cell couples it to
the transparent policy it serves. The promotion loop (spec -> PR -> governed next run) remains the
real flagship and its own experiment.

## 61 · The isolation sprint: the expansion exposed v1, three bounces closed it

Optimising spec-authoring in isolation began with the discipline the §50 lesson demands: GROW THE
MEASUREMENT FIRST. The tail suite went from five questions to twelve, deliberately loaded with the
latitude family the residual lived in — denominator choices (whole cohort vs accounts with the
event vs engaged-only), window conventions (30/60/90 days, an offset month 61-90), day-difference
intervals — every oracle proven before authoring, one question ambiguous BY DESIGN with its
canonical reading named.

The expansion did its job brutally: v1 of the mechanism (the choices contract and fourth-action
routing alone) scored WORSE than hand-rolled SQL on the twelve (10 wrong vs 7; silent 0.278 vs
0.194), with failures spread thin as 1-in-3 flakes. The traces showed three authoring-quality
defects, none of them prompt-fixable, all of them mechanically detectable:

| defect | trace | fix |
|--------|-------|-----|
| TABLE-AS-ENTITY | scope cited dim_users.user_id — table names as graph nodes — and gave up as uninstrumented | the resolver bounce now maps table names to their entities from the graph's own table registry (the third member of the slip family: metric-as-entity, table-as-entity) |
| GRAIN VIOLATION | a raw spec returned 100 account-grain rows for a one-number question; the model eyeballed "7.9" from the table (true 9.69) — prose aggregation reborn INSIDE the spec path | the grain bounce: raw spec + no breakdown in the question + multi-row result -> re-author with "aggregate inside the SQL", bounded like every repair in the define loop |
| JOIN-BUG SHARES | a share of exactly 1.0 (numerator == denominator, 103/103) served for a true 0.518 | the sanity line in the authoring contract: a share of exactly 0 or 1 usually means a join bug; re-derive the counts separately |

The re-run closed it: spec v2 scored 32/36 right, 0 wrong served, silent 0.000 (four visible
non-attempts), against hand-rolled SQL's 25/36 with 7 silents. Every gate held: resolve_validate
10/10 (the shared resolver surface undamaged), the original five questions all correct, both test
suites green. The sprint's shape is the campaign's shape in miniature: the honest expansion made
the mechanism look worse before it could get better, and the wins came from deterministic repairs
at the exact points where prose leaked back in — a table for an entity, a table for a number, a
join bug wearing a clean ratio.

## 62 · Wiring spec-authoring into the standard cell: the bypass, the conversion, the smoke lesson

`spec_authoring` joined `current_best` after the §61 sprint — as CAPABILITY, not policy: the cell
stays strict, so on the standard suite the exit gate still owns the computable tail, and the
mechanism's measured value continues to live in the transparent arm. The wiring took three rounds
to certify, and each round earned a finding.

THE BYPASS. The first wired full-suite run served five computed numbers on the two pile-B
questions the rehabilitated resolver now correctly classifies computable (time-to-first-habit
3/3, habit-streaks 2/3). The strict gate never fired because its provenance trigger was the
literal fact "the answer used run_sql" — and a define-authored spec computes through its own
guarded runner. Author-then-serve where the policy says author-then-refuse. The trigger now reads
provenance from the trace contract instead of a tool name: raw SQL, or a define step whose
evidence records carry a raw leaf. A spec composed purely of governed metrics stays out, as
designed.

POLICY IS NOT VERIFICATION AT THE CAP. Closing the bypass exposed the next layer: a model that
stonewalled through the correction budget served the computed figure WITH the cap caveat —
correct behaviour for a verification dispute, wrong in kind for a policy violation. An answer the
cell's governance forbids is not "unverified", it is not servable; the cap now distinguishes the
two: a [policy]-marked correction converts the exit into the refusal the policy names
(reason `no_governed_definition`), where a verification correction still serves with its caveat.
Probe: 6/6 with zero silents, the interval case refusing 3/3.

THE SMOKE LESSON, recorded against ourselves. The first wired run went straight to the full suite
— skipping the probe-first gate every code change in this experiment had observed — and spent a
full-suite run discovering what a 90-second smoke on two already-identified questions would have
found: the exact questions were sitting in the §60 A/B. The discipline now states plainly:
CONFIGURATION PROMOTIONS GET THE SAME PROBE GATE AS CODE CHANGES. The certified sequence became
smoke (4 questions, one per touched surface: both computable hot paths showing
check_answerability -> define -> gate hand-back, a governed control, a contested control; 4/4
with the intended acts) and only then the suite.

THE CERTIFICATION. Full rep-3 with the wired cell: silent 0.0072 (one known premise-family
rep-flake, untouched by spec machinery), pile A 48 right and 0 wrong, pile B 44/45 with every
computable refused, pile C 42/42 handled, balanced 0.973 — the §59 clean baseline within rep-3
noise. define fired 9 times on the standard suite (the capability is reachable; the zero-forever
era ends) and zero policy-cap conversions were needed — the gate's ordinary hand-backs sufficed,
with the conversion standing as the proven backstop. Promotion (spec -> PR into the layer)
remains deliberately unbuilt — its own experiment.

## 63 · The review executed: the query trap removed, the judge re-scored honestly, the raw claim verified

A seven-point technical review of the spec-authoring machinery was adjudicated in §62's aftermath;
three of its tiers were executed here, methodically (test, smoke, review per tier). The fourth —
one Scope artifact replacing the classifier stack — is an epic queued behind Phase 4, eval-gated.

TIER 1, THE OFFERED TRAP. The define enum offered kind='query' while `run_ephemeral` returned
"query-leaf execution not yet implemented" — an enum value the executor could not run, whose
failure fed back as "fix the definition" and burned a bounded retry on definitions that were
CORRECT. Removed from the enum and the prompt; the core Spec.query constructor and the executor
stub stay for the compiler that will earn the kind back. Alongside it, the row schema now
publishes `hand_backs` (corrections that cost a round trip) beside `claim_retries` (which counts
constructions too and keeps its archived meaning) — the fixture's old `handbacks` field was
`len(repairs)`, a third thing, now split into both honest numbers.

The tier-1 smoke failed usefully twice. First: 3/3 tail questions REFUSED under `current_best` —
not a regression but the strict policy working as written (a computable's raw provenance routes to
refusal); the lesson, now recorded: THE TAIL SUITE'S CELL IS THE TRANSPARENT ARM. Second: the
refused rows could not explain their own gate decisions — the fixture serialized steps without the
typed evidence records the gates decide on. Fixture rows now carry `evidence`. Re-run under
`current_best+transparent_compute`: 3/3 correct, raw kind authored directly, no query burn.

TIER 2, THE JUDGE AUDITED BY ITS AUTHOR. `challenge_aptness` ran on the same model object that
authored the definition it challenges — same weights, same blind spots — while `get_verifier`
(one effort notch up, optionally a different model) sat unused by the define path. Plumbed
through: run_agent -> toolbox.verifier_model -> define_measure, metered into the RUN's counter so
`model_calls` keeps meaning every call the answer cost. The fixture runner never built a verifier
at all; it does now.

The validation was re-scored under the split the review demanded. The first 6 cases are the TUNE
set (the 'refute if you can' first cut scored 1/6 on them; the rewrite was tuned until they
passed) — a score on them measures memorisation. The 8 later cases are the holdout.

| set | exact | apt-vs-flagged | standing |
|---|---|---|---|
| tune (6) | 4/6 | 4/6 | reported, never asserted on |
| holdout (8) | 7/8 | 8/8 | the number that counts |

The published claim shrinks from "13/14" to "holdout 8/8 flagged, 7/8 exact". The verifier
resolution flags the two genuinely debatable tune cases the author-resolution accepted; the wire
is disclose-only, so over-flagging costs a note naming the alternative, not a refusal — failure
in the widening direction. The assertion gates on the holdout only.

TIER 3A, THE UNVERIFIED CLAIM. For metric/derived kinds a declared filter IS applied — the engine
compiles it into the query. For kind='raw' the SQL runs verbatim and `spec.filters`/`spec.period`
were only claims, yet `bind_scope` counted them as bindings — the one unverified input to the
completeness check. Now a raw declaration counts only with evidence in the SQL: the value literal
or the leaf column for a filter, the period token or any year it names for the period. The scan
CONFIRMS AND NEVER REFUTES — absence routes to `unbound` and the authoring feedback asks for the
component inside the SQL; a correct SQL in any expression shape passes via the column/year match.
Four unit pins; qualifiers stay declared-only (free-text claims have no scannable shape — stated,
not hidden). Live: the scan's first catch was real — a spec declaring the 2026-Q1 cohort as a
filter over a SQL with no date constraint bounced and was re-authored; 3/3 tail correct.

TIER 3B, THE FREELANCE PATH. The tier-2 smoke surfaced the review's composition case live: one
rep skipped check_answerability entirely, hand-assembled a share from 7 query_metric calls
(subscriptions started IN Q1 over Q1 signups, 0.137) where the question asks the cohort
follow-forward (0.259) — every figure governed, so raw-provenance gates never fire, and the
wrong-quantity ratio served silently. Four runs of that question pre-steering: 2 correct via
define, 1 safe refusal, 1 silent freelance. The steering: the define tool description (visible
even when check_answerability is skipped) and the GOVERNED verdict text both now name the
composition route — a ratio, share, or per-unit figure of governed metrics is authored with
define_measure, where a wrong-quantity ratio is a named defect instead of arithmetic in prose.
The steering probes, and what the second one caught. The freelance-prone question re-run 3 reps
with the new text: 3/3 took check_answerability -> define_measure, zero freelance, 2 correct and
1 safe refusal, zero silent. The governed-ratio control (habits per active user) answered from
its own governed metric both reps — no composition to steer, the right outcome for the wrong
specimen.

THE CATCH THE PROBE PAID FOR. The contested composition (spend per signup, Q1) ran 1/2 with one
CONFIDENT WRONG — and the just-published evidence records explained it in one read: both governed
inputs carried `period: null`. The model had declared 2026-Q1 on the DERIVED spec; `periods()`
gathers across the tree, so bind_scope passed the declaration, while the executor computed each
input exactly as its own leaf declared — no period at all. The served 84.376208 IS the
whole-history spend over whole-history signups, to six decimal places (gold Q1: 93.6656). The
declared-but-not-applied class of tier 3a, alive in the derived executor.

The fix defines the error out of existence, at construction: a period or filter declared on a
derived spec pushes down into every input that lacks its own (`Spec.derived`), so declaration,
evidence records, and execution are one fact. An input's own period or filters win — a
period-over-period difference declares one window per input, and both stand (pinned). Three unit
pins; the re-probe ran 3/3 correct with both governed inputs carrying `period: 2026-Q1` in their
evidence records and the served figures matching gold exactly (80.9626 acquisition primary,
93.6656 marketing disclosed — or the reverse, both readings always present). Worth naming: the
defect was found BY the new evidence records within minutes of publishing them — the row explained
its own wrong number, which is the argument for publishing what gates read.

Observed for later, not fixed here: the ephemeral runner feeds SQL dialect errors back verbatim
(`julianday` does not exist in DuckDB) and the model repeated the mistake once before routing
around it — a dialect hint in that feedback is a cheap future bounce. Steering is text, not
protocol: the freelance path remains open by construction, and the protocol-level close (a
composition detector on served arithmetic, or the unified Scope artifact) stays on the queue.

## 64 · A five-question scrutiny, and the bug the probe caught in its own fix

Five questions sampled at random from the dev suite, rep 1, `current_best`: 5/5 correct, zero
silent, zero hand-backs, every figure matching the suite's proven gold (62, 3096, 1858.95). The
three answerables were single governed calls with the right filter and window; the uninstrumented
refusal took one check_answerability; the coverage trap showed the citation discipline working —
a blocked call cannot be cited, so the model fetched check_coverage for a citable handle before
refusing.

Three findings, none behavioural. (1) The `value` slot was constructor-filled 3 for 3 — the §51
constructor is the normal path on this sample, not the fallback; known design, worth remembering
when reading repair counts. (2) The grounded_measure act printed `correction {claim_retries} of
2` while the loop budgets on `hand_backs` — after §63 split them, the line could read "2 of 2"
with no budget spent. Now prints hand_backs. (3) The contested-cluster stand-down (served figure
IS a queried cluster reading — the binding check's jurisdiction) returned without logging an act:
the one silent branch in the gate, invisible in the agree-case trace. Now logged like its
siblings.

The first version of fix (3) crashed live: `', '.join(rivals)` assumed strings; `competitors()`
returns Competitor objects, and the re-probe erred with TypeError — caught because the fix was
probed before being trusted (§62's lesson, applied to a two-line change). The branch had no unit
coverage, which is how the bug reached a live run; `test_the_cluster_stand_down_logs_its_act`
now pins the act and the name join, and fails on the old code. Re-probe: both questions correct,
the agree-case trace now reading `contested cluster: the served figure is the queried
'marketing_spend' reading (rivals: acquisition_spend)`.
