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

## 12 · First principles, and what the market does

### The problem, derived

1. **The object of ambiguity is the answer**, not the question and not the metric. Two readings
   matter only if they produce different numbers for this request.
2. **Detection requires an enumerable set of readings.** Derived from the wording, the set is
   unbounded and phrasing-dependent. Derived from the governed layer, it is finite and
   precomputable. This is the real argument for a semantic layer in agentic analytics. It also fixes
   a hard limit: **only ambiguity represented in the layer is detectable this way.**
3. **There are four terminal responses**, not three: pick one silently, refuse, ask, answer every
   reading.
4. **Anything ending in "and then the model decides" performs at chance.** Four replications here:
   the prompt rule, the SQL disclosure, the declared-scope retry, the advisory rival figure.
5. **The verification target is the answer, not the inputs** (§11).
6. **Nothing ranks refuse against ask against answer-both without a cost model** — a price on a
   silent single reading, on a round trip, and on an abandoned session.
7. **Reducible against irreducible** is the decisive split. Published guidance assumes the first.

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

## 13 · Not measured

- ~~**Over-clarification on the hard case.**~~ Measured in §8: 10 of 12 under the gate. The
  predicted fix — a mechanical channel for the request having named the scope — was built (arm C)
  and the agent never used it.
- **A rate of any kind.** Sixteen questions, one fixture, one model, three reps. The sizing work in
  `00_reading.md` says a usable pile needs four to five distinct contested concepts; it now has four,
  and the noise band still does not exist. Two of the five-arm comparisons are separated by one or
  two questions, which is inside the run-to-run spread observed at one rep.
- **The second turn.** No user simulator, so a clarification is priced at half an episode and
  abandonment is unmeasurable. This is the largest hole in the arm comparison: it flatters B and C
  and penalises D and E.
- **`WRONG_COST`.** Still the placeholder 4.0, and it is the only thing standing between the §8
  table and a defensible choice between arm B and arm E.
- **Any model but `gpt-5-mini`.** The D-to-E gap is a compliance failure; a stronger model may close
  it without the check. Either result is publishable and they imply opposite decisions.
- **`trajectory_verify`'s over-refusal rate on this fixture** (§10). Eight runs point in both
  directions; that is a hint, not a measurement.
- **Cost of the gate.** It runs each competitor once per contested call. Cheap on DuckDB, unmeasured
  on anything else.

## 14 · Candidate next arms

- **Disclose the definition's own filter in the scope line.** The MetricFlow adapter's scope line
  says "no filters — the whole population this metric defines" while the metric itself carries
  `is_internal = false`. The harness's own layer says "the metric definition already restricts: NOT
  is_internal" in the same position. The information is in the SQL either way, but the prose summary
  is what gets skimmed, and this is the cheapest untried advisory lever.
- ~~**Answer with both, disclosed**~~ — built and measured in §8 (arms D and E). §4's objection
  was right about the advisory form and did not apply to the checked one: the model does not have to
  pick well, it has to be prevented from picking silently.
- **A non-zero divergence threshold**, as a lever rather than a default.
- **Verify the answer rather than the input** (§11): have the answer carry its arithmetic, substitute
  the rival operand, recompute, and check for the recomputed figure. This is the one open defect in
  arm E that is understood well enough to fix.
- **Sub-type the wrong numbers on answerable questions** (§9). Fourteen wrong answers, none
  classified, all diagnosed by hand. Everything above depends on this being automatic.
- **Rename `prev_week` to `week_before_last`** (§9). Two names in one enum that read as synonyms in
  English, resolving to different weeks.
- **Give the MetricFlow layer a member resolver**, so `resolve` and `governed_notes` can run and the
  judge stops treating a definitional filter as a narrowing (§10). This also unpins the experiment
  from R4.
- **Route a persistently firing cluster to its owners** (§12). Nothing in the market does this, and
  it is the step that turns an irreducible contest into a reducible one.
