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

## 10 · Five responses to ambiguity, measured

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

## 8 · Not measured

- ~~**Over-clarification on the hard case.**~~ Measured in §10: 10 of 12 under the gate. The
  predicted fix — a mechanical channel for the request having named the scope — was built (arm C)
  and the agent never used it.
- **A rate of any kind.** One question, one fixture. The sizing work in `00_reading.md` says a usable
  pile needs four to five distinct contested concepts, and the noise band does not exist.
- **The second turn.** No user simulator, so a clarification is priced at half an episode and
  abandonment is unmeasurable.
- **Cost of the gate.** It runs each competitor once per contested call. Cheap on DuckDB, unmeasured
  on anything else.

## 9 · Candidate next arms

- **Disclose the definition's own filter in the scope line.** The MetricFlow adapter's scope line
  says "no filters — the whole population this metric defines" while the metric itself carries
  `is_internal = false`. The harness's own layer says "the metric definition already restricts: NOT
  is_internal" in the same position. The information is in the SQL either way, but the prose summary
  is what gets skimmed, and this is the cheapest untried advisory lever.
- ~~**Answer with both, disclosed**~~ — built and measured in §10 (arms D and E). §4's objection
  was right about the advisory form and did not apply to the checked one: the model does not have to
  pick well, it has to be prevented from picking silently.
- **A non-zero divergence threshold**, as a lever rather than a default.
