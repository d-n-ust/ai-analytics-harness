# Study 00 — primitive load: how many things one question makes the agent resolve

Findings are in `FINDINGS.md` — read §25 first, it is the current state. The practitioner summary is
in `PRACTITIONER-NOTES.md`.

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

**Families h, a and r segment on staff and test accounts; w and c segment on an enum recorded in
several spellings.** That split is not decoration — it is what §25's second claim rests on, because
only the first three ask for a fact the documentation states.

## The arms

| arm | what it is | rung |
|---|---|---|
| `A_implicit` | the raw application extract, no comments | 1 |
| `B_documented` | the same tables, every primitive stated in a comment | 1 |
| `C_modelled` | the conformed star, no comments | 2 |
| `C_modelled_documented` | the same star, documented | 2 |
| `D_declared` | the documented star plus a governed layer on dbt MetricFlow | 3 |
| `E_enforced` | D plus `governed_numbers` — a number must trace to one governed result | 3 |

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

## Running it

```
./bench study 00_primitive_load --reps 3 --concurrency 6
./bench study 00_primitive_load --reps 1 --arms D_declared,E_enforced
./bench study 00_primitive_load --mock --reps 1          # checks every invariant, spends nothing
```

**The mock run is not optional.** It computes every gold, prints the vocabulary audit and the
fingerprints, and validates the `columns:` block and the declared primitive profiles. Three of this
study's defects were caught there rather than after a paid run.

## What the study cannot do

**It is not powered.** 23 items, five per load level, 16% of cells disagreeing with themselves. The
claims in `FINDINGS.md` §25 rest on replication across runs, not on any single cell.

**It measures one filter.** Every over-application found here is `is_internal`. Whether a documented
grain or join rule behaves the same way is untested and is the obvious next question.
