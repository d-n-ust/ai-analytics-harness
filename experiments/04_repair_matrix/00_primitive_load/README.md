# Study 00 — primitive load: how many things one question makes the agent resolve

Findings are in `FINDINGS.md` — read **§31** first: the item set was rebuilt on 2026-08-10 and its
numbers are NOT comparable with anything before it. §30 is the last state of the old instrument, and
§27 and §29 are the trace audits. The practitioner summary is in
`PRACTITIONER-NOTES.md`, written for a reader with no access to this repository.

**Where it stands.** 62 items, 8 arms, 1,488 rows, noise floor 25%. The tie in §30 was an artefact of
five-item rungs, on which the paired test could not reach significance at all. Rebuilt twelve wide,
the arms spread from 87 to 170 of 186. Additivity is the sharpest rung — 0/12 for both raw arms — and
nothing about modelling moves the second pile, where every warehouse arm sits at 13 to 17 of 36 and
only `E_enforced` reaches 28.

## Why it exists

Every other study in this experiment asks questions that require **one** primitive, and
`../01_entity/FINDINGS.md` §8 found `gpt-5.6-terra` answering all of them from an undocumented
warehouse. Real analysis is not one primitive.

The hypothesis: if each primitive is resolved independently with probability *p*, an *n*-primitive
question succeeds at *p*ⁿ, so the gap between a documented and an undocumented warehouse widens
superlinearly with *n*.

**Numbered 00 because it is not a matrix row.** The matrix is primitives against interventions, and
load is neither — it is a property of the *question* that cuts across every row.

## The ladder

Five families of four rungs. **Each rung is the one below plus exactly one primitive**, so the most
likely wrong answer at each rung is the rung below's gold, and a failure names the step that caused
it.

| family | L1 entity | L2 + segment | L3 + grain | L4 + join path |
|---|---|---|---|---|
| h · habits still tracked | 6,357 | 6,147 | 2,321 | 382 |
| a · habits archived | 1,110 | 1,074 | 868 | 125 |
| r · activated referrals | 266 | 254 | 236 | 36 |
| w · finance habits × web | 1,236 | 374 | 306 | 49 |
| c · mindfulness habits × Germany | 1,267 | 221 | 171 | 34 |

Plus three load-0 controls. Every gold is executed against the warehouse before the file is written
and cross-checked against the value in each item's own note.

## The second pile: eight questions with no answer

The ladder alone measures half the job — an agent that answers everything scores perfectly on it. A
second pile asks what happens when there is nothing to answer, two items per reason at two depths:

| reason | what is wrong with the question |
|---|---|
| `out_of_coverage` | the period asked for is outside the data |
| `no_governed_definition` | the thing asked for (support tickets) is nowhere in the warehouse |
| `segment_undefined` | the group asked about ("churned") has several defensible readings and no governed one |
| `false_premise` | the question asserts a change that did not happen |

Both a refusal and a clarifying question count; so does contradicting a false premise with the real
figures, which is the more useful response and which the grader scored **zero** until §27.

**An item belongs here only if every metric it needs is present in the layer, or deliberately
absent.** Two items in this pile were measuring gaps in our own MetricFlow layer rather than the
behaviour they were written for — see FINDINGS.md §27.3 and §28.4.

**Families h, a and r segment on staff and test accounts; w and c segment on an enum recorded in
several spellings.** That split is not decoration — it is what the documentation finding rests on
(§30.5), because only the first three ask for a fact the documentation states.

**An item belongs in this pile only if the layer can express the question.** Where it cannot, the arm
refuses for the wrong reason and looks careful: `E_enforced` declined `u_fp2` with "there is no
governed metric for reminders shown", which was true and was a statement about our own modelling.
Two items were measuring layer gaps rather than the behaviour they were written for, and both gaps
are now closed — `reminders` and `value_moments` (FINDINGS.md §27.3, §28.4).

## The arms

| arm | what it is | rung |
|---|---|---|
| `A_implicit` | the raw application extract, no comments | 1 |
| `C_modelled_labelled` | the star plus `platform_name` on the dimension — a probe | 2 |
| `C_modelled_snowflaked` | the star with labels in `dim_country` / `dim_platform` — a probe | 2 |
| `E_enforced_verified` | E plus `trajectory_verify`; see §31.7 before reading its numbers | 3 |
| `B_documented` | the same tables, every primitive stated in a comment | 1 |
| `C_modelled` | the conformed star, no comments | 2 |
| `C_modelled_documented` | the same star, documented | 2 |
| `D_declared` | the documented star plus a governed layer on dbt MetricFlow | 3 |
| `E_enforced` | D plus `governed_numbers` and `coverage_check` (cell `R7-resolve`) | 3 |

**The ladder is cumulative.** D is `C_modelled_documented` plus a layer; E is D plus a check. Each
column adds to the one below rather than trading one thing for another.

`E_enforced` sits at a different guardrail cell and is a **paired comparison against D alone** — it
is not part of the load ladder, because reading it against A or B would compare guardrails rather
than data modelling.

## Why D and E run on MetricFlow

`FINDINGS.md` §15 traced `D_declared`'s failure — 31% correct when it used our own layer against 70%
when it ignored it — to three properties of `semantic/semantic_layer.yml`, two of them
architectural:

| defect | consequence |
|---|---|
| one base table per metric, no join model | every segment rung unreachable |
| no metric exposes a user grain | "how many people" unanswerable |
| filters hidden in metric names (`active_habits`) | the arm that used the layer got a narrowed answer |

MetricFlow fixes the first two by construction — models declare **entities**, and a shared entity is
a join. The third is fixed by discipline in `layers/D_declared/layer.yaml`: every filter sits on a
metric and is rendered, and where a question could mean the filtered or unfiltered thing, both are
declared.

Two things MetricFlow could not do either, and both fixes are Kimball's: **a derived attribute on
the conformed dimension** for the fact-to-fact join, and **a role-playing dimension** for the two
people in a referral.

### Coverage is computed, not declared

MetricFlow's spec has no field for "what period does this hold data for", so the adapter declared
`coverage=False` — which withdrew the `check_coverage` tool and blocked the `coverage_check`
guardrail. `E_enforced` answered both out-of-coverage questions wrong, three times each, because
nothing could tell it the data ends on 12 July.

The window was never missing from the data. Every semantic model names an `agg_time_dimension`, and
min/max of that column is the answer, so `semantic/metricflow_engine.py` now computes it **per
model** — habits run to 2026-07-24 while subscriptions stop at 2026-07-12, and one layer-wide window
would be wrong for one of them. Ratio metrics resolve through their inputs and take the narrowest.

`segments`, `members` and `additivity` stay `False`: no computation recovers them. They are decisions
somebody has to write down, and MetricFlow gives nowhere to write them.

## Running it

```
./bench study 00_primitive_load --reps 3 --concurrency 6
./bench study 00_primitive_load --reps 1 --arms D_declared,E_enforced
./bench study 00_primitive_load --mock --reps 1          # checks every invariant, spends nothing
```

**The mock run is not optional.** It computes every gold, prints the vocabulary audit and the
fingerprints, and validates the `columns:` block and the declared primitive profiles. Three of this
study's defects were caught there rather than after a paid run.

**The mock cannot see a guardrail.** `MockModel` answers without ever calling `query_metric`, so no
BEFORE or AFTER guardrail executes in a mock run. Two paid runs died at rows 31 and 61 on methods the
MetricFlow adapter did not implement, both cleared to run by `check_compatible` — **which checks
capabilities, not methods.** `tests/test_adapters.py` now covers both: one test drives the real
guardrail against the real adapter with no model in the loop, one asserts the adapter implements
every layer method the agent path calls. Run the tests before spending on a sweep.

## What the study cannot do

**It is not powered.** 31 items — 23 answerable, five per load level, plus 8 with no answer — and
about one cell in five disagreeing with itself across three identical repetitions. The claims in
`FINDINGS.md` §30.5 rest on replication across runs, never on a single cell. `D_declared` is a useful
noise gauge: between the last two runs nothing about that arm changed except three metrics appearing
in its catalogue, and its individual items moved by up to 2 of 3 in both directions while every total
stayed flat.

**It no longer separates the top of the ladder.** Three arms tie at 57 of 60 on the answerable pile.
Anything that distinguishes a star from a layer must now be measured on the second pile, or on a
harder ladder.

**It measures one filter.** Every over-application found here is `is_internal`. Whether a documented
grain or join rule behaves the same way is untested and is the obvious next question.

**Grounded-answer rate is not measured.** It needs the `claims` protocol, and the answer tool only
carries a `claims` field where there is a governed surface (`action_space.py` returns the base schema
when `semantic is None`). Switching it on would therefore change the tool surface for `D` and `E`
alone — a second treatment applied to exactly the two arms that already differ — so the study runs
`protocol: {}` and the column reports `—` rather than a misleading zero.

**The blocking guardrail's value is unmeasured.** `coverage_check` fired zero times in six
opportunities; the coverage gain came from the agent looking the window up itself. Separating the two
needs an arm with the capability on and the guardrail off.
