# Study 00 — the load ladder, and two ways to write documentation badly

Three runs. The first two were instrument, the third is the result.

| run | model | score | what it was |
|---|---|---|---|
| `20260809-192243` | gpt-5-mini | 40/60 | first build — control broken, ladder on the floor |
| `20260809-201725` | gpt-5-mini | 48/60 | ladder rebased — exposed an under-specified comment |
| `20260809-202056` | gpt-5-mini | 55/60 | **the readable run** |
| `20260809-202236` | gpt-5.6-terra | **60/60** | **the readable run, one tier up** |

**READ §14 FIRST.** It is the trace analysis of the latest run, and it finds five defects — two of
which void the two families added in §11, and one of which reverses §13. Every section below it was
written before those defects were known.

**Then §11, which supersedes §9.** The load curve appeared on three families and did not
reproduce when two more were added. What did survive the expansion is two findings about how
documentation is written, both in §11, and neither of which the study set out to look for.

**§9, kept because it is what three families showed.** On `gpt-5-mini` the gap between a
documented and an undocumented warehouse is flat to load 2 and then accelerates — 0, 0, 0, +22, +56
percentage points. On `gpt-5.6-terra` a gap of about 20 points exists at every load and does not
grow.

Sections 1–5 are the instrument history: three defects, two of them in our own documentation rather
than in the questions. §6 is a five-item run whose conclusion about the frontier model §9 corrects —
it is kept rather than deleted, because "the null was a ceiling effect from too few items" is the
most repeatable mistake in this folder.

---

## 1. What came back

| question | load | A_implicit | B_documented | C_modelled | D_declared |
|---|---|---|---|---|---|
| L1 entity | 1 | **0/3** | 3/3 | 3/3 | 3/3 |
| L2 + segment | 2 | 0/3 | 2/3 | 3/3 | 3/3 |
| L3 + grain | 3 | 0/3 | 1/3 | 3/3 | 2/3 |
| L4 + join path | 4 | 1/3 | 3/3 | 3/3 | 2/3 |
| control | 0 | **0/3** | 2/3 | 3/3 | 3/3 |
| **total** | | **1/15** | 11/15 | **15/15** | 13/15 |

**Six of twenty cells disagree with themselves** across identical repetitions — 30%, more than twice
the 13% floor measured elsewhere. That alone makes the per-item numbers unreadable.

---

## 2. Defect one: the control is not a control

`pl_control_spend` — *"How much did we spend on paid search in June 2026?"* — was written as the
row to read first, needing no primitive resolved. It scored **0/3 in `A_implicit`**, and the traces
show why:

```
rep 0   WHERE LOWER(chan) = 'paid-search'                    ->  1,987.43
rep 1   WHERE chan ILIKE 'paid search'                       ->  2,432.59
rep 2   summed paid-search + Paid Search + paid_search       -> 10,169.72
```

The gold is **12,786.81**. `spend.chan` carries the same channel under several spellings —
`paid_search`, `Paid Search`, `paid-search`, `ppc` — and the documented arm is told the list while
the undocumented arm has to discover it.

**So the control is an enum-resolution question**, which is a primitive, and it is exactly the
primitive `messy_tables` documents. A control that the treatment repairs is not a control. It has to
be replaced with something that has no enum, no join and no grain choice — a count of rows in a
table whose grain is one row per thing.

---

## 3. Defect two: the ladder starts on the floor

`A_implicit` scored **0/3 at L1**, the shallowest rung. A gap cannot widen with load if it is
already maximal at load 1.

The traces show the agent guessing the event-code mapping, differently each time, and once
inventing one outright:

```sql
-- rep 1, L3
CASE WHEN etype=1 THEN 'reminder_shown' WHEN etype=2 THEN 'reminder_dismissed'
     WHEN etype=3 THEN 'other' END
```

The true mapping is 1 = app open, 2 = completed habit, 3 = reminder shown. Across nine `evt`
attempts the arm used `etype = 1`, `= 2`, `= 3`, `IN (1,2,3)` and `= 2 AND src = 'app'`.

**This is not new, and `../01_entity` shows it was already true there.** Its `A_implicit` scored
10/15, and the ten come almost entirely from the questions that do not touch `evt`:

| item | A_implicit |
|---|---|
| completed habits (`evt.etype`) | 1/3 |
| reminders shown (`evt.etype`) | 0/3 |
| habits not archived (`hab.arch` NULL) | 3/3 |
| active subscriptions (`subs.st`) | 3/3 |
| control | 3/3 |

**So the undocumented arm resolves NULL semantics and status codes reliably, and the mixed-event
table not at all.** Building the ladder on `evt.etype` put a primitive at the base that the arm
scores near zero on, and every rung above inherits it.

**The design constraint this establishes:** the base rung must be a primitive the undocumented arm
resolves *most* of the time. Otherwise there is no headroom for the compounding effect the study
exists to measure. On this warehouse that means building the ladder on `hab` or `subs`, not on
`evt`.

---

## 4. What the run does suggest, held loosely

`C_modelled` scored **15/15** — the conformed star answered every rung including L4, where the
subscription cardinality trap survives the star untouched. That was predicted to fail and did not.

`B_documented` fell in the middle of the ladder and recovered at the top — 3/3, 2/3, 1/3, 3/3 —
which is not a shape any hypothesis predicts and sits inside the 30% instability. Not readable.

`D_declared` never used a governed metric for L2 or L3; the `picked` column shows it reaching for
`real_acquisition` and falling back to SQL. The prediction in `study.yml` that the layer's coverage
falls off with load is consistent with this, and one run at 30% instability cannot confirm it.

---

## 5. What to change before running it again

| defect | fix |
|---|---|
| control is an enum question | replace with a count over a table with one row per thing and no coded column |
| ladder base is on the floor | rebuild the ladder on `hab`/`subs` primitives, which `01_entity` shows the undocumented arm handles |
| 30% self-disagreement | follows from the two above — the arm was guessing, and guesses vary |

The frontier-model run is deferred until then. Running `gpt-5.6-terra` against a broken control
would produce a second unreadable table at a higher price.

---

## Provenance

| claim | source |
|---|---|
| per-item results | `20260809-192243-00_primitive_load/run.json` |
| the three control queries | the same run, `A_implicit`, `pl_control_spend`, all three reps, `steps` |
| the invented event mapping | the same run, `A_implicit`, `pl_l3_grain`, rep 1 |
| `01_entity`'s per-item A scores | `20260808-232437-01_entity` |


---

## 6. The rebuilt ladder, on two models

Control replaced with a signup count — one table, one date column, one row per account, and safe
under both readings (553 counting every account, 543 excluding staff, 0.98x, inside tolerance).
Ladder rebased from `evt` onto `hab` and `subs`, the primitives `../01_entity` shows the
undocumented arm actually resolves.

### gpt-5-mini

| question | load | A_implicit | B_documented | C_modelled | D_declared |
|---|---|---|---|---|---|
| control | 0 | 3/3 | 3/3 | 3/3 | 3/3 |
| L1 entity / NULL | 1 | 3/3 | 3/3 | 3/3 | 3/3 |
| L2 + segment | 2 | 3/3 | 3/3 | 3/3 | 3/3 |
| L3 + grain | 3 | **2/3** | 3/3 | 3/3 | 3/3 |
| L4 + join path | 4 | **2/3** | 3/3 | **2/3** | **1/3** |
| total | | 13/15 | **15/15** | 14/15 | 13/15 |

**The predicted shape appears, weakly.** `A_implicit` holds at the first two rungs and loses a
repetition at each of the last two; `B_documented` stays at ceiling throughout. The A-to-B gap by
load is 0, 0, 1, 1 out of 3 — monotone non-decreasing, which is the direction the hypothesis
predicts and far too small to be a measurement.

`D_declared` is the worst arm at L4 (1/3), consistent with the pre-registered reading that a
semantic layer stocks the questions someone thought of and a four-primitive question falls outside
it. Four of its fifteen rows never called `list_metrics` at all.

### gpt-5.6-terra

| question | load | A_implicit | B_documented | C_modelled | D_declared |
|---|---|---|---|---|---|
| every question | 0–4 | **3/3** | 3/3 | 3/3 | 3/3 |
| total | | **15/15** | 15/15 | 15/15 | 15/15 |

**Zero self-disagreement across all twenty cells.** The frontier model answered a four-primitive
question — event kind, population definition with a NULL-bearing flag, people-not-rows, and a
one-to-many join it must not fan — from the raw application extract with no comments anywhere,
three times out of three.

---

## 7. What this settles, and what it moves

**The load hypothesis is supported on the small model and not on the frontier model.** Depth alone,
to four primitives, does not bring `gpt-5.6-terra` off the ceiling. `../01_entity/FINDINGS.md` §3.4
found the same at load 1; this extends it to load 4 on a different set of primitives and a different
table.

So the claim from that sweep survives in a stronger form than it was made:

> The cheaper the model you run, the more your documentation is doing — and on this warehouse that
> holds at every question depth we can currently construct.

**The remaining lever is the warehouse, not the question.** Our environment has six objects at rung
1 and seven at rung 2, with no redundancy: the frontier model reads the whole schema in one call and
reasons about it. A real warehouse of this domain carries forty to eighty overlapping objects —
`vw_weekly_actives_ios`, `daily_actives_v2`, `user_activity_summary` — several of which can answer
any given question and disagree. That is what accumulated modelling debt is, and we have never
built it.

Depth was the cheaper lever and it has now been tested. Sprawl is next, and it comes with a measure
that removes our own gold from the loop: **ask each question in several wordings and check whether
the answers agree with each other.** Agreement needs no gold SQL, which is the one thing that
answers the circularity objection to this whole programme.

---

## 8. Two defects found in our own documentation, not in the questions

Worth separating from the item-design failures above, because they are the more useful kind.

**`u.internal` asserted a rule and withheld it.** `messy_tables.sql` said a few NULL-flagged
accounts "are internal accounts identifiable only by their email domain" and never named the domain.
Both arms guessed — the agent excluded every email containing `test` or `@example.com` and returned
**4,057** where the gold is 6,147, in the documented arm as well as the undocumented one. Naming the
domain took `B_documented` from 11/15 to 15/15 and halved self-disagreement, 7 of 20 cells to 4.

**A comment that says a rule exists without stating it is worse than no comment**, because it
directs the reader to invent one. That is a finding about documentation quality rather than about
documentation quantity, and it is the kind of thing this experiment is for.

The fix went into `warehouse/docs/messy_load.sql` and deliberately not into the shared
`messy_tables.sql`, which `../01_entity`'s stored runs depend on.


---

## Provenance for the rebuilt runs

| claim | source |
|---|---|
| gpt-5-mini per-item table | `20260809-202056-00_primitive_load/run.json` |
| gpt-5.6-terra per-item table | `20260809-202236-00_primitive_load/run.json` |
| the 4,057 wrong value and its predicate | `20260809-201725`, `A_implicit` and `B_documented` on `pl_l2_segment`; reproduced against the warehouse as `internal=0 AND email NOT LIKE '%test%' AND email NOT LIKE '%@example.com'` |
| catalogue-skip counts | the `context_audit` field of the `D_declared` rows in both readable runs |


---

## 9. Fifteen items: the curve appears, and §6 was wrong about the frontier model

Three items per rung instead of one — three nested families of four rungs, plus three controls.
Runs `20260809-203751` (gpt-5-mini) and `20260809-204041` (gpt-5.6-terra), 45 rows per arm.

### The A-to-B gap by primitive load

| load | gpt-5-mini | gpt-5.6-terra |
|---|---|---|
| 0 — control | +0 pp | +0 pp |
| 1 | +0 pp | +22 pp |
| 2 | +0 pp | +11 pp |
| 3 | **+22 pp** | +22 pp |
| 4 | **+56 pp** | +22 pp |

**On `gpt-5-mini` the predicted curve appears, and it is sharp.** `A_implicit` scores 9/9, 9/9, 8/9,
6/9, **3/9** as the ladder climbs; `B_documented` holds at 9, 9, 8, 8, 8. The gap is flat to load 2
and then accelerates.

The prediction written in `study.yml` before the run was that an independent-primitive model gives
*p*ⁿ, putting the load-4 gap near 59pp — the point at which this design can detect anything at all.
**Measured: 56pp.** That is closer than the pilot deserves and should be treated as a coincidence
until more items exist, but the *shape* is the one the hypothesis names.

### The correction

**§6 of this document reported that `gpt-5.6-terra` shows no gap at any depth. With fifteen items it
shows a gap of about 20 points.** The earlier null was five items against a ceiling, not an absence.

But the frontier gap is **flat, not growing**: +22, +11, +22, +22. Its failures are scattered across
loads rather than concentrated at depth — including `pl_a1_entity`, a **load-1** item it gets 1/3
on. That is item difficulty, not compounding.

| | small model | frontier model |
|---|---|---|
| is there a gap? | yes, 7/45 | yes, 7/45 |
| does it grow with load? | **yes — 0, 0, 0, 22, 56** | **no — 22, 11, 22, 22** |
| where do failures sit? | the join-path rung, two families of three | scattered, no pattern |

**So depth is what documentation buys back on a cheap model, and it is not what the frontier model
is failing on.** Both statements are new; the second replaces "the frontier model needs nothing".

### What is not clean

**Sixteen of sixty cells disagree with themselves on the small model** — 27%, twice the measured
floor. The frontier model is far steadier at 5 of 60. A curve read off a 27%-unstable arm is a
direction, not a rate.

**One family of three does not show the effect.** On `gpt-5-mini` the referral ladder is flat at the
top — `pl_r3` and `pl_r4` are 2/3 in both arms — so the load-4 gap rests on the two habit families.
Three items per rung was the right change and three is still not many.

**`D_declared` is the weakest arm at load 1 on both models** (7/9 and 9/9) and twelve of its
forty-five rows on the small model never called `list_metrics`. Its numbers remain partly a
measurement of whether the layer was consulted.

---

## 10. Provenance for the fifteen-item runs

| claim | source |
|---|---|
| per-load tables | `20260809-203751-00_primitive_load` (gpt-5-mini), `20260809-204041-00_primitive_load` (gpt-5.6-terra) |
| per-item A-versus-B | the same two runs |
| every gold | executed against the warehouse before `cases.yml` was written, and re-checked against the harness's own `compute_gold` |


---

## 11. Five families: the curve does not survive, and a new failure mode appears

Two families added — `w` (fitness habits on the web platform) and `c` (learning habits in Germany) —
because the three-family set left one family carrying no signal at the top and because their segment
rungs are far stronger. Families h, a and r segment on staff-and-test accounts, which is 3.4% of
users, so their segment rung barely moves the number. Families w and c segment on an enum recorded
in several spellings: `u.plat` holds three platforms in nine spellings, `u.ctry` holds `DE` beside
`de`. An arm matching one spelling returns 114 where the gold is 390.

### The result: no trend

| load | A_implicit | B_documented | C_modelled | D_declared | A→B |
|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 7/9 | +0 pp |
| 1 | 15/15 | 14/15 | 15/15 | 10/15 | −7 pp |
| 2 | 9/15 | 12/15 | 13/15 | 11/15 | +20 pp |
| 3 | 11/15 | 10/15 | 12/15 | 9/15 | −7 pp |
| 4 | 10/15 | 12/15 | 14/15 | 7/15 | +13 pp |
| **total** | 54/69 | 57/69 | **63/69** | 44/69 | |

**The 0, 0, 0, +22, +56 curve from §9 does not reproduce.** Thirty-two of ninety-two cells disagree
with themselves — 35%, nearly three times the measured floor.

### It splits by family, and the two new ones are why

| family | A_implicit | B_documented | B − A |
|---|---|---|---|
| h  habits still tracked | 9/12 | 10/12 | +1 |
| a  habits archived | 7/12 | **12/12** | **+5** |
| r  activated referrals | 11/12 | 12/12 | +1 |
| **w  fitness × web platform** | **12/12** | **8/12** | **−4** |
| c  learning × Germany | 6/12 | 6/12 | 0 |

The three original families all favour the documented arm. **Family w reverses it: the undocumented
arm is perfect and the documented arm loses four.** Family c is poor in both arms.

So §9's curve rested on three families that agree, and adding two that do not removes it. **On the
present evidence the load hypothesis is not established.** It has appeared once, on three families,
and failed to reproduce on five.

### The new failure mode, and it is the useful part

Before the reword below, `B_documented` scored **1/5 at load 3** against `A_implicit`'s 5/5. Its
answers were all slightly under gold, and each one is identifiable:

| item | gold | B answered | what that is |
|---|---|---|---|
| `pl_c3_grain` | 179 | **174** | the gold **with staff excluded** — never asked for |
| `pl_h3_grain` | 2,321 | **2,065** | `internal = 0`, dropping the 271 NULLs the comment says to keep |

The cause was our own wording. The comment read:

> *An account is staff or test when internal = 1 OR its email ends @internal-test.com. Every other
> account is a real user.*

**A comment phrased as a rule becomes a default the agent applies everywhere** — including to the
two new families, whose questions say nothing about staff at all. Rewriting it to describe what the
values mean rather than what to do with them took `B_documented` from 17/23 to 18/23 at reps=1 and
removed the 1/5 collapse at load 3.

This is the second documentation-quality finding from this study, and it pairs with the first:

| defect | effect |
|---|---|
| a comment that asserts a rule and does not state it | the agent invents one — 4,057 against a gold of 6,147 |
| a comment that states a rule prescriptively | the agent applies it everywhere — 174 against a gold of 179 |

Neither is about how much documentation exists. Both are about how it is written, and both were
found by reading values rather than scores.

### What this leaves

**`C_modelled` is the best arm at 63/69**, and it is the only arm above both A and B at every load
above 1. That was not the study's question and it is the clearest signal in the run.

**`D_declared` is the worst at 44/69**, with twenty-eight of sixty-nine rows never calling
`list_metrics`. Its score remains partly a measurement of whether the layer was consulted.

**Before this set is run again:** family w needs its traces read. An undocumented arm at 12/12 and a
documented arm at 8/12 on the same twelve questions is not noise, and until it is understood the
whole set carries it.

---

## 12. Provenance for the five-family runs

| claim | source |
|---|---|
| per-load and per-family tables | `20260809-210443-00_primitive_load` (gpt-5-mini, reps=3) |
| §13 five-arm run | `20260809-212756-00_primitive_load` |
| the prescriptive-comment collapse | `20260809-205533` (before the reword) against `20260809-205839` (after) |
| the 174 and 2,065 values | reproduced against the warehouse as gold-plus-staff-excluded and `internal = 0` |
| reps=1 preserves the shape on a fixed item set | `20260809-204*` at reps=1 against `20260809-203751` at reps=3, same 15 items |


---

## 13. The documented star: the fifth arm, and the null it was built to produce

`C_modelled_documented` added — the same conformed star as `C_modelled`, carrying
`warehouse/docs/star_schema.sql`. It was missing and nothing in `study.yml` said why; the arm exists
in `../01_entity` and its absence here was an oversight rather than a decision.

| load | A_implicit | B_documented | C_modelled | C_modelled_documented | D_declared |
|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 9/9 | 8/9 |
| 1 | 15/15 | 13/15 | 15/15 | 15/15 | 9/15 |
| 2 | 8/15 | 14/15 | 12/15 | 11/15 | 10/15 |
| 3 | 9/15 | 10/15 | 12/15 | 9/15 | 10/15 |
| 4 | 9/15 | 9/15 | 12/15 | 12/15 | 7/15 |
| **total** | 50/69 | 55/69 | **60/69** | 56/69 | 44/69 |

**Describing the star bought nothing: 60/69 against 56/69.** The four-point difference is inside the
run-to-run drift — `C_modelled` scored 63/69 on the previous run of the identical arm — so the two
are indistinguishable, and 26 of 115 cells disagree with themselves.

**That null is the arm's purpose.** The star already resolves every primitive this ladder uses,
structurally rather than in prose:

| the fact | where the star puts it |
|---|---|
| a NULL archive date means still tracked | `dim_habits.is_archived` — computed once |
| the staff flag plus the email rule | `dim_users.is_internal` — resolved, never NULL |
| nine platform spellings are three platforms | `dim_users.platform` — `lower()` and a CASE |
| `DE` and `de` are one country | `dim_users.country` — `upper()` |

So the sentences a comment would add are already true of the shape, and adding them changed nothing.
**Conformed modelling substitutes for documentation; the reverse does not hold** — `B_documented` at
55/69 does not reach `C_modelled` at 60/69.

That is the 2×2 `../01_entity` runs, reproduced on a different question set:

| | undocumented | documented | what it says |
|---|---|---|---|
| messy tables | 50/69 | 55/69 | describing messy tables helps |
| conformed star | **60/69** | 56/69 | describing a star does not |

`../01_entity` found the same and called it inconclusive at five questions. At twenty-three it points
the same way, and it is the strongest argument this experiment has for spending the days rather than
the afternoon.

**The caveat that matters:** the star normalises exactly the four primitives this ladder tests. A
ladder built on facts the star does *not* encode — a business rule, a coverage window, a causal
caveat — would not reproduce this, and the comparison would go the other way.


---

## 14. Trace analysis: five defects, two of which invalidate two families

Every one of the 345 rows of `20260809-212756` was read — outcomes, tool errors, and each wrong
value matched against readings computed from the warehouse rather than guessed at. The run has
**25 failed tool calls, 6 non-answers, and 74 wrong answers**, and most of the wrong answers are
explained by five defects. Two of them are in the questions and invalidate the two families added in
§11.

### Defect 1 — family c asks for a country by name and the data holds ISO codes

`pl_c2_segment` returned **0** in `A_implicit`, `C_modelled` and `D_declared`, three repetitions
each. The reason is not subtle:

```
rows where ctry = 'Germany'   0
rows where ctry = 'DE'      364
rows where upper(ctry)='DE' 412
```

The question says *"people in Germany"*; the column holds `DE`. `C_modelled` refused and said so
outright: *"You asked for users 'in Germany' but the country dimension uses ISO codes."*

**So this rung tests country-code mapping, not the enum-casing defect it was built for** — a third
primitive smuggled in, documented nowhere, and not the one the item declares. The family is void.

### Defect 2 — family w's category name has a semantic neighbour in its own column

`A_implicit` answered **774** where the gold is 390. The trace:

```sql
WHERE lower(cat) IN ('fitness','health','exercise') OR lower(nm) LIKE '%fitness%'
```

`hab.cat` contains both `fitness` and `health`. Asked for *"habits in the fitness category"*, the
agent read "fitness" as a topic rather than as a category value and swept in the neighbour. That is
a defensible reading of an English sentence, and it means the item measures whether the agent
guesses our category taxonomy. The family is void.

### Defect 3 — both new families leave the archive status open

*"How many habits are in the fitness category?"* does not say whether archived habits count. The
gold includes them. Six wrong answers across the run are exactly the not-archived reading, and one
arm asked about it rather than guessing:

> *Do you want (1) count of all habits in category "learning" including archived, or (2) count of
> active (not archived) habits…*

Families h and a do not have this problem because their questions are *about* the archive status.
The two new families inherited it by using a different entity rung and not closing it.

### Defect 4 — the star's own documentation causes over-application, and it hit the new arm hardest

§11 recorded this for the raw-table comments and reworded them. **It is also true of
`warehouse/docs/star_schema.sql`, which was not reworded**, and `C_modelled_documented` is where it
shows:

| arm | wrong answers that are "gold + staff excluded" |
|---|---|
| C_modelled_documented | **7** |
| C_modelled | 1 |
| B_documented | 2 |

`dim_users.is_internal` is described as *"True for staff and test accounts, false for real users"* —
and the arm applies it to questions that never mention staff. **The documented star is the arm most
harmed by its own documentation**, which is why it scored 56/69 against `C_modelled`'s 60/69 in §13.

### Defect 5 — the semantic layer cannot express these questions

All 25 failed `query_metric` calls are `D_declared`, and they are not model errors:

```
cannot filter 'active_habits' by 'is_internal'.  Allowed: ['category']       6x
cannot group  'active_habits' by 'user_id'.      Dimensions: ['category']    3x
cannot filter 'paying_users'  by 'country'.      Allowed: ['plan']           3x
metric 'active_habits' is point-in-time; it takes no period.                 3x
```

`active_habits` carries **one** dimension. Every segment rung in this study is therefore
unreachable through the layer, and `D_declared` must abandon it and write SQL. **Its 44/69 measures
our layer's dimension coverage, not the declared column.** This is the same finding as the
catalogue-skip counts, seen from the other side.

### The sound subset, and it is post-hoc

Removing the two void families leaves families h, a and r plus the three controls — 45 rows per arm:

| load | A_implicit | B_documented | C_modelled | C_modelled_documented | D_declared | A→B |
|---|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 9/9 | 8/9 | +0 pp |
| 1 | 9/9 | 9/9 | 9/9 | 9/9 | 4/9 | +0 pp |
| 2 | 6/9 | 9/9 | 9/9 | 9/9 | 8/9 | **+33 pp** |
| 3 | 6/9 | 9/9 | 9/9 | 9/9 | 9/9 | **+33 pp** |
| 4 | 4/9 | 6/9 | 7/9 | 9/9 | 5/9 | **+22 pp** |
| **total** | 34/45 | 42/45 | 43/45 | **45/45** | 34/45 | |

`A_implicit` degrades monotonically — 9, 9, 6, 6, 4 — and `B_documented` holds at 9 until load 4.
**The gap is zero at loads 0 and 1 and about 30 points from load 2 up.** That is a step rather than
§9's accelerating curve, and it is the third different shape this study has produced.

**THIS IS A POST-HOC SUBSET AND MUST BE LABELLED ONE.** Families were removed after the run. The
exclusions rest on named, reproducible defects in the items — a country name against ISO codes, a
category name colliding with its neighbour — and not on their scores, but a subset chosen after
seeing results cannot carry a headline. It sets up the next run; it does not conclude this one.

**It also reverses §13.** On the sound subset `C_modelled_documented` is **45/45**, above
`C_modelled`'s 43/45. The "describing the star bought nothing" reading came from the two void
families, where that arm was the one most damaged by the star's prescriptive comments.

### What has to happen before this study runs again

| defect | fix |
|---|---|
| family c asks for a country by name | use the ISO code, or drop the family |
| family w's category has a neighbour | pick a category with no semantic twin, or name the column value |
| archive status open in both | state it, as families h and a do by construction |
| `star_schema.sql` comments are prescriptive | reword descriptively, as `messy_load.sql` already was |
| `active_habits` has one dimension | either give the layer the dimensions the questions need, or stop reading D as a measurement of the declared column |


---

## 15. Root cause of `D_declared`: using the semantic layer made the agent worse

`D_declared` has been the worst or second-worst arm in every run of this study. The traces give four
causes, and the first three are in our layer rather than in the model.

### The number that frames it

| how `D_declared` reached its answer | rows | correct | rate |
|---|---|---|---|
| **governed only** — `query_metric`, no SQL | 16 | 5 | **31%** |
| **SQL only** — never used the layer | 44 | 31 | **70%** |
| **layer, rejected, then SQL** | 9 | 8 | **89%** |

**Using the layer was worse than ignoring it, and the best outcome was trying it, being refused, and
falling back.** The layer's failures are loud and recoverable; its successes are quietly wrong.

Only **16 of 69 rows** were answered through the governed path at all. At load 4, **all fifteen**
fell back to SQL. For most of this study `D_declared` is not a declared arm — it is a rung-3 arm
doing rung-2 work with a catalogue in its context.

### Cause 1 — the layer has no join model

`semantic/semantic.py` says so in its own docstring, and the compiler is one line:

```python
# The compiler is deliberately small: one base table per metric              (line 8)
sql = f"SELECT {', '.join(select)} FROM {m['base']}"                          # line 515
```

A dimension is usable only if it is a **column on that one table**. So a metric's dimensionality is
inherited from whichever mart happens to sit underneath it:

| base table | user attributes on it | dimensions its metrics get |
|---|---|---|
| `agg_active_days` | `is_internal`, `region`, `country`, `platform`, `channel` | region, platform, channel, country |
| `dim_habits` | **none** | `category` |
| `fct_reminders` | **none** | — |
| `fct_referrals` | **none** | — |
| `fct_subscriptions` | **none** | `plan` |

`agg_active_days` is a mart that `warehouse/star.sql` pre-joins `dim_users` into. The other four are
queried directly. **Seven metrics are richly sliceable and ten are nearly unsliceable, and nothing in
the catalogue says which is which** — they are rendered identically.

Every one of the 25 rejected calls follows from this:

```
cannot filter 'active_habits' by 'is_internal'.  Allowed: ['category']    6x
cannot filter 'paying_users'  by 'country'.      Allowed: ['plan']        3x
```

### Cause 2 — no metric exposes a user grain

`cannot group 'active_habits' by 'user_id'. Dimensions: ['category']` — three times. There is no
metric anywhere in the layer that answers *"how many people"* about habits, reminders or referrals.
The grain rung is unreachable by construction, which is a second consequence of cause 1: `user_id`
is on `dim_habits`, but a count-distinct over it was never declared as a metric.

### Cause 3 — our own layer contains the defect this programme exists to study

`active_habits` carries a filter its caller cannot see:

```yaml
active_habits:
  description: "Habits that have not been archived — the ones users are still tracking."
  agg: count(*)
  default_filters: ["NOT is_archived"]
```

Asked *"how many habits are in the fitness category"*, `D_declared` reached for the governed metric
and got **1,032**. The answer is **1,235**. The metric silently excludes archived habits and the only
clue is the word *active* in its name.

**That is `real_value_moments` wearing a different noun** — a population baked into a metric where
the name is the sole carrier, which is exactly the defect `../02_segment` was built to measure.
`paying_users` has the same shape with `default_filters: ["is_active"]`.

So an agent that does the right thing — reach for the governed metric rather than write SQL — is
punished for it. That is the mechanism behind the 31%.

### Cause 4 — what the arm therefore measures

Not the declared column. `D_declared`'s score is a blend of:

- how often the layer can express the question at all (rarely, above load 1),
- whether the agent notices and falls back (usually),
- and whether the metric it did reach had a hidden filter (twice, wrongly).

**Its 44/69 is a measurement of our layer's coverage and defaults.** Every reading of column D in
`../primitives_matrix.md` that rests on this study has to say so.

### What follows

| finding | what to do |
|---|---|
| dimensionality is inherited from marts, invisibly | either declare joins, or render each metric's real sliceability in the catalogue so the agent is not misled |
| no user-grain metric exists | declare one, or stop asking grain questions of column D |
| `active_habits` and `paying_users` hide filters in their names | fix them — we cannot publish a study of this defect while shipping it |
| the layer is worse than SQL when used | this is the most quotable result in the study and it needs its own run to confirm, not a subgroup of this one |

The last line is the important one. **31% against 70% is a subgroup comparison inside one arm**, not
a controlled contrast — the rows differ in which questions they are as well as in route. It sets up
a study; it does not conclude one.


---

## 16. `D_declared` migrated to dbt MetricFlow: 20/23, and what the last three say

§15 traced this arm's failure to three properties of `semantic/semantic_layer.yml`, two of them
architectural. The arm now runs on MetricFlow with its own layer under `layers/D_declared/`.

| layer | score at reps=1 |
|---|---|
| `semantic/semantic_layer.yml` | ~14.7/23 equivalent (44/69 at reps=3) |
| MetricFlow, first build | 17/23 |
| MetricFlow, role-playing entity fixed | **20/23** |

Families h, a and r are **4/4 each**. Under the old layer every question above load 1 was
unreachable through the layer at all.

### What the migration fixed, and how it was verified

**Before any model call**, all 22 ladder and control questions were resolved against the layer and
compared to the gold SQL: **22 exact matches, 0 unreachable.**

| §15 cause | fix |
|---|---|
| no join model — `SELECT … FROM <one base>` | MetricFlow models declare **entities**, and a shared entity *is* a join. `habits` and `users` join on `user`; every segment rung became reachable |
| no user grain | `count_distinct(user_id)` declared as a measure — `people_with_habits`, `people_tracking_habits`, `people_who_archived_habits` |
| hidden default filters | **every filter sits on a metric and is rendered in the catalogue.** Where a question can mean the filtered or the unfiltered thing, both are declared: `habits_total` / `habits_tracked` / `habits_archived` replace the single `active_habits`, and `subscribers_all_time` / `subscribers_live` replace `paying_users` |

### Two things MetricFlow could not do either, and the fixes are Kimball's

**Fact-to-fact.** `habits` and `subscriptions` both hold `user` as a *foreign* entity, so each joins
to `users` and neither joins to the other. The L4 rungs need exactly that join. The answer is a
derived attribute carried on the conformed dimension — `users.has_ever_subscribed` — which is the
textbook remedy rather than a workaround.

**A role-playing entity, and it produced a wrong number with a clean provenance trail.** A referral
has two people in it. The first build declared only `user` = the person referred, so
`referrers_activated` accepted `user__has_ever_subscribed` and **silently filtered the referred side
while counting referrers**: 48 where the truth is 36, through a governed call that raised nothing.

The fix is a second declaration of `dim_users` keyed on `referrer` — one physical table, two logical
roles — because MetricFlow joins a foreign entity to the model where that entity is *primary*, and
`referrer` had no such model. `pl_r4` went from wrong to exact.

### The three remaining failures, and two of them are one behaviour

| question | gold | answered | what happened |
|---|---|---|---|
| `pl_c1_accounts` (a **control**) | 553 | 713 | got **553** from `query_metric`, twice, then grouped by day and summed the groups |
| `pl_c3_grain` | 179 | 412 | dropped the `habit__category` filter, then tried `SELECT … FROM metric_results` |
| `pl_w4_join_path` | 51 | 45 | skipped the catalogue, wrote SQL, added `billed_amount > 0` unprompted |

**The agent invents a table to post-process a governed result.** Twice it reached for
`metric_results` and `query_results_from_metric`, neither of which exists. There is no supported way
to take a number out of `query_metric` and do anything further with it, so it fabricates one.

**The control failure is the additivity defect in miniature.** It had the right answer from the
governed path and then summed daily groups on top of it. A control that a *correct* governed call
can be talked out of is worth keeping and worth naming: it says the failure is not retrieval.

### What is not fixed

**Eleven of twenty-three rows still never called `list_metrics`.** The layer being able to express
the question does not make the agent read the catalogue, and that remains the open question §3.5
named.

**`pl_c2_segment` and the `w`/`c` families keep their item defects** — country name against ISO
codes, `fitness` colliding with `health`. §14 voids those families and the migration does not
change that.


---

## 17. The four repairs, and the guardrail that made the agent use the layer

The board's five recommendations on §16's three failures, all applied.

### D_declared, run by run

| build | score | silent wrong | never read the catalogue |
|---|---|---|---|
| `semantic/semantic_layer.yml` | ~14.7/23 | — | 12/23 equivalent |
| MetricFlow, first build | 17/23 | 6 | 8 |
| + role-playing referrer entity | 20/23 | 3 | 11 |
| + the four repairs below | **21/23** | 2 | 10 |

The two remaining failures are both in family **c**, which §14 already voids for asking about a
country by name against ISO codes.

### What the four repairs were

**Group the catalogue's dimensions by entity.** `people_with_habits` advertised ten dimensions on
one sorted line, nine of them arriving across a join, and the arm dropped the one that was not a
`user__` prefix — four times. Cube groups by cube, LookML by view, MetricFlow's own CLI by entity;
ours printed a flat list. Now:

```
- people_with_habits: Distinct people holding AT LEAST ONE habit, archived or not. …
    by habit: habit__category, habit__habit_created_date, habit__is_archived
    by user:  user__channel, user__country, user__has_ever_subscribed, user__is_internal, …
    time:     metric_time
```

Filter-drops fell from four to one.

**Say what a cross-entity filter means.** A count of people filtered by an attribute of a habit is
ambiguous by construction — *people with at least one fitness habit*, or *people all of whose habits
are fitness*? The metric silently meant the first. Every `people_*` description now says so, and
`referrers_activated` says which side `user__` and `referrer__` describe.

**Define what "paid subscription" counts.** `fct_subscriptions` carries active, canceled and
refunded terms and nothing said whether a refunded term makes someone a paying customer. One arm
invented `billed_amount > 0` and answered 45 where the truth is 51. The rule — membership of the
table, whatever the status or amount — is now in the dimension comment and in every metric
description that depends on it. That is a **domain fact**, the matrix's tenth row, not a modelling
one.

**Declare the composition.** Thirteen `simple` metrics and nothing else meant a governed result was
a terminal value: any further step had to happen outside the layer, and the agent's three ways of
doing that were arithmetic in its head, an invented table, and raw SQL. Three `ratio` metrics are
now declared and verified against SQL.

### The paired comparison: D against E, same layer, one guardrail apart

`E_enforced` is `D_declared` plus `governed_numbers` — a number must trace to one governed result.

| | correct | silent wrong | refused | used `query_metric` | wrote SQL | **never read the catalogue** |
|---|---|---|---|---|---|---|
| D_declared (R1) | 20/23 | 3 | 0 | 13 | 10 | **10** |
| E_enforced (R7 reduced) | 20/23 | **2** | 1 | **23** | **0** | **0** |

**Accuracy is identical and everything else moved.** The predicted shape held: the check trades a
wrong number for an abstention rather than producing a right answer, exactly as `../05_additivity`
found on a different defect.

**The unpredicted result is the last column, and it answers a question open since `../FINDINGS.md`
§3.5.** That section measured how often a governed layer is skipped — 7, 8, then 13 of 30 rows as
the model got stronger — and named "what makes an agent use a layer it has been given" as a study
nobody had run.

**Requiring provenance makes it use the layer.** A number must trace to a governed result, so raw
SQL cannot produce an acceptable answer, so the catalogue must be read. D skipped it on 10 of 23
rows and wrote SQL on 10; E skipped it on none and wrote SQL on none.

That is one arm, 23 rows, one model, one reps — a direction, not a rate. But it is a mechanism, it
is cheap to test again, and it reframes the bypass finding: **the layer was not being ignored
because it was unhelpful. It was being ignored because nothing required it.**


---

## 18. Families repaired, primitives checked, and the first internally comparable run

### The repairs

**Family w: `fitness` → `finance`.** `hab.cat` holds both `fitness` and `health`, and the arm read
the word as a topic — `cat IN ('fitness','health','exercise') OR nm LIKE '%fitness%'` — answering
774 against a gold of 390. `finance` has no near-synonym in the column.

**Family c: `learning` → `mindfulness`, and the country vocabulary is now documented.** Three arms
had filtered `ctry = 'Germany'` and returned 0, because the column holds ISO codes. Both docs files
now carry the mapping:

```
Two-letter ISO country code … DE is Germany, FR France, GB the United Kingdom, …
```

That makes it a **documented fact the treated arms are told and `A_implicit` must find by inspecting
values** — which is what a segment rung is when a population is named in business terms and stored
as a code. The case declares it.

**Both: the archive status is closed in the wording.** *"Counting archived ones as well"* / *"archived
or not"*. Six wrong answers in the previous run were exactly that open reading.

**`star_schema.sql`: a correction to §14.** §14 listed its comments as prescriptive and they are not
— they describe what values mean rather than what to do with them. The only editorial phrase,
*"never needs interpreting"*, is removed. **The `C_modelled_documented` over-application is therefore
not explained**, and the likelier cause is salience: `is_internal` is the one column comment naming a
filterable business concept. That is a hypothesis, not a finding.

### `primitives:` is now checked

It was declared on every item and read by nothing — no validation, no reporting. That is how both
families shipped a rung labelled load 2 that needed a third, undeclared primitive.

`_validate_primitives` refuses a study whose case declares a primitive its own gold SQL shows no
sign of. It is deliberately crude: a primitive is present if the gold shows the *shape* that
primitive takes in this warehouse — `count(distinct` for grain, a subquery or join for join_path, a
user attribute for segment.

**It cannot prove a question needs a primitive** — that is a judgement about English, and it is what
the trace audit is for. It proves the gold exercises what the label claims, which catches the
mislabelled rung and the copy-paste, and it is the check that would have caught w and c before the
run rather than after it.

### The run

Run `20260809-232023`, six arms, 23 items, three repetitions.: six arms, 23 items, reps=1

The first run in which every arm is in its current state. The previous five-arm table stitched two
runs together, with A/B/C/C_doc predating the MetricFlow migration.

| load | A_implicit | B_documented | C_modelled | C_modelled_doc | D_declared | E_enforced | A→B |
|---|---|---|---|---|---|---|---|
| 0 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | +0 |
| 1 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | +0 |
| 2 | 4/5 | 5/5 | 3/5 | 5/5 | 4/5 | 5/5 | **+20** |
| 3 | 3/5 | 4/5 | 4/5 | 3/5 | 2/5 | 4/5 | **+20** |
| 4 | 4/5 | 4/5 | 5/5 | 4/5 | 4/5 | 5/5 | +0 |
| **total** | 19/23 | 21/23 | 20/23 | 20/23 | 18/23 | **22/23** | |

**`E_enforced` is the best arm at 22/23, with zero catalogue skips against `D_declared`'s ten.** That
is the §17 result reproduced on a repaired item set: requiring provenance makes the agent use the
layer, and here it also scored highest.

**The load curve is still not established.** 0, 0, +20, +20, 0 is a fourth shape. At reps=1 each cell
is five observations and a single item moves a rung by 20 points, so this run is a check that the
instrument is sound, not a measurement of the effect. **The next thing this study needs is reps=3 on
this exact set** — the first run that could carry a number.


---

## 19. reps=3 on the repaired set: the effect grows with depth in BOTH directions

Run `20260809-225835`, six arms, 23 items, three repetitions — 414 rows, and the first run in which
every arm is current and every item has passed the primitive check.

| load | A_implicit | B_documented | C_modelled | C_modelled_doc | D_declared | E_enforced |
|---|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 9/9 | 7/9 | 9/9 |
| 1 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| 2 | 12/15 | 14/15 | 13/15 | 15/15 | 12/15 | 15/15 |
| 3 | 11/15 | 13/15 | 12/15 | 11/15 | 12/15 | 11/15 |
| 4 | 9/15 | 8/15 | 12/15 | 10/15 | **15/15** | 12/15 |
| **total** | 56/69 | 59/69 | 61/69 | 60/69 | 61/69 | **62/69** |

Read as one curve the A-to-B gap is `+0, +0, +13, +13, −7` — a fifth shape, and at load 4
documentation makes things *worse*. That reading is wrong, and the reason is the finding.

### Family w reversed again, and every wrong answer had the same cause

Family w was rebuilt this session — `fitness` became `finance` because the first category collided
with `health`. It reversed anyway: `A_implicit` 12/12, `B_documented` 8/12.

**All nine wrong answers in the two documented arms are the gold with staff excluded.** Family w's
questions never mention staff.

This survived the fix in §11, where the `u.internal` comment was reworded from a rule
(*"An account is staff or test when…"*) to a description. **Phrasing was not the cause.** Naming a
filterable population in documentation at all is enough.

### Split the items by whether the question asks for the documented fact

Eleven of the 23 questions say "excluding staff and test accounts". Twelve do not.

| | A_implicit | B_documented | A→B |
|---|---|---|---|
| question **asks** to exclude staff | 25/33 | 30/33 | **+15 pp** |
| question does **not** | 31/36 | 29/36 | **−6 pp** |

And by load, which is where it becomes a result rather than an observation:

| load | asks to exclude — A→B | does not — A→B |
|---|---|---|
| 1 | — | +0 pp |
| 2 | +0 pp | +33 pp |
| 3 | **+33 pp** | **−17 pp** |
| 4 | **+22 pp** | **−50 pp** |

**Both grow with depth, in opposite directions.** The reported curve is their average, which is why
it looked flat and then negative.

### The claim this supports

> **What documentation does to an agent scales with the depth of the question, and its sign depends
> on whether the question needs the documented fact.**
>
> If the answer requires it, documenting it pays more the deeper the question. If the answer does
> not, documenting it costs more the deeper the question — because the agent applies the documented
> filter unasked, and that error compounds with everything else the question makes it resolve.

That is the load hypothesis, refined by the data rather than confirmed by it. The original form —
*documentation helps, and helps more at depth* — is true only of the half of the items that ask for
the documented fact.

**It also explains every earlier shape this study produced.** Runs whose item mix leaned toward
questions that ask showed a rising curve; runs that leaned the other way showed a flat or falling
one. Three families ask and two do not, and the mix per rung is what moved.

### What is not established

**Cell sizes are two or three items.** The split table rests on 6 to 9 rows per cell. The pattern is
monotone in both directions and the −50 pp is large, but this is a direction with a mechanism, not a
rate.

**The mechanism is one filter.** Every over-application in this run is `is_internal`. Whether a
documented *grain* or *join* rule is over-applied the same way is untested, and it is the obvious
next question.

**23 of 138 cells disagree with themselves** — 17%, against the 13% floor. Better than the 27–35% of
the previous builds, and still above it.

### Two arm-level notes

**`E_enforced` is the best arm at 62/69, with zero catalogue skips against `D_declared`'s 31.** The
§17 result holds on a repaired item set at three repetitions.

**`D_declared` scores 15/15 at load 4** — the only arm to do so, and its worst rung is the control.
A governed layer that can express the question does best where the question is hardest, which is
the shape the matrix's column D predicts and this experiment had not previously shown.


---

## 20. The ladder made cumulative: D and E now see the star's documentation

`D_declared` and `E_enforced` declared `tables: star_schema` and no `docs:`, so they received the
governed layer and **no table comments at all**. On 31 of 69 rows they fell back to SQL, and there
they were operating like `A_implicit` on a star — three failures in §19 were filtering
`country = 'Germany'` while the ISO mapping sat documented in a file they could not see.

**A team that has built a semantic layer has not left the warehouse underneath it undocumented.**
With `docs: star_schema` the ladder is cumulative: D is `C_modelled_documented` plus the layer, and
E is D plus the check, so each column adds to the one below rather than trading one thing for
another.

### The run · `20260810-000736`

| load | A_implicit | B_documented | C_modelled | C_modelled_doc | D_declared | E_enforced |
|---|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 |
| 1 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| 2 | 11/15 | 15/15 | 12/15 | 15/15 | **15/15** | 15/15 |
| 3 | 11/15 | 14/15 | 13/15 | 13/15 | 12/15 | 12/15 |
| 4 | 10/15 | 11/15 | 13/15 | 12/15 | 12/15 | 12/15 |
| **total** | 56/69 | **64/69** | 62/69 | **64/69** | 63/69 | 63/69 |

**D's load-2 went from 12/15 to 15/15** — precisely the rung whose failures §19 traced to the missing
comments. The fix landed where it was aimed.

Against the previous run: A unchanged at 56 (nothing about it changed), B **59 → 64**, C_modelled_doc
**60 → 64**, D **61 → 63**, E **62 → 63**. B and C_doc moved because the country-code vocabulary was
documented this session; D and E moved because they can now read it.

### Every arm above A is now within two points

`B_documented` and `C_modelled_documented` tie at 64, D and E at 63, `C_modelled` at 62 — and
`A_implicit` is **eight points below all of them.** On this set, documentation is worth eight points
and everything after it is worth nothing measurable.

That is the same ceiling `../01_entity` hit at load 1, now reproduced on a set that goes to four
primitives.

### The split, replicated

| | this run | previous run |
|---|---|---|
| A→B at load 4, questions that **ask** for the documented fact | **+44 pp** | +22 pp |
| A→B at load 4, questions that do **not** | **−50 pp** | −50 pp |

**The deepest rung reproduces across two independent runs**: documentation is strongly positive
where the question needs the documented fact and −50 points where it does not. The middle rungs do
not replicate — `+11, +11` here against `+0, +33` before, and `+50, +33` against `+33, −17`.

So §19's claim survives at load 4 and not below it. **The honest statement is about the deepest
rung**: the sign of documentation's effect depends on whether the question needs the documented
fact, and the effect is largest where the question is hardest.

### One thing got worse

`D_declared` skipped the catalogue on **40 of 69 rows**, up from 31. Giving it readable table
comments made the SQL path more attractive, not less. `E_enforced` still skips on zero — the
provenance requirement is the only thing in this study that has ever made the layer get used.


---

## 21. The two board fixes: what they reached and what they did not

**Gap 1 — the population becomes something you request by name.** `is_internal` was a filterable
dimension described as *"true for staff and test accounts"*, and every documented arm applied it on
questions that never asked. It is removed as a dimension and replaced by `user_type`, a descriptive
attribute with values `staff` / `customer`. MetricFlow has no `segments:` construct, so the flag is
simply unreachable and the default is everyone.

**Gap 2 — the catalogue marks the metric's own entity.** Grouping by entity cut the dropped-filter
failures and did not remove them, and the dropped filter was always the metric's own. The catalogue
now says which is which:

```
- people_with_habits: Distinct people holding AT LEAST ONE habit…
    by habit (what this metric counts): habit__category, habit__habit_created_date, habit__is_archived
    by user (joined):  user__channel, user__country, user__platform, …
```

All 23 questions re-validated against the changed layer before the run: **23 of 23 exact.**

### The run — D and E, three repetitions · `20260809-235214`

| load | D_declared | E_enforced |
|---|---|---|
| 0 | 9/9 | 9/9 |
| 1 | 15/15 | 14/15 |
| 2 | **15/15** | **15/15** |
| 3 | 14/15 | 10/15 |
| 4 | 12/15 | **15/15** |
| **total** | **65/69** | 63/69 |

**`D_declared` at 65/69 is the highest any arm has scored in this study** — above `B_documented` and
`C_modelled_documented` at 64/69 in the previous run of the same items. **Self-disagreement fell to
5 of 46 cells — 11%, below the 13% floor, for the first time in this study.**

### What the fixes reached

**Over-application through the layer is gone.** No failure in either arm is a habits metric filtered
to customers unasked.

### What they did not reach, and it is the more interesting half

**`D_declared`'s two remaining over-applications happen in raw SQL.** Both traces are `run_sql`
against `dim_users` filtering `NOT is_internal` directly:

| item | gold | answered | route |
|---|---|---|---|
| `pl_w3_grain` | 306 | 297 | SQL, `NOT is_internal` |
| `pl_w4_join_path` | 49 | 47 | SQL, `NOT is_internal` |

**D skipped the catalogue on 47 of 69 rows.** A fix inside the semantic layer cannot reach an arm
that is not using the semantic layer, and the star still carries `is_internal` with its original
comment. That is not a flaw in the fix; it is the bypass problem measured from a third angle.

**One over-application survives inside the layer**, on the two-sided referral metric: `E_enforced`
answered 229 where the gold is 236, filtering both `referrer__` and `user__`. The description added
this session says *"Filter neither unless the question names that side"* and it was not enough.

**The category drop is reduced, not removed.** `D_declared` has one left; `E_enforced` has two.

### Where the board disagreed, and who was right

Semantic-modelling held that gap 1 was fixable by making the population requestable. Data-modelling
held that the agent over-applies because the concept is **salient**, and that renaming would move the
problem rather than solve it.

**Both are partly right, and the split is clean.** Inside the layer, making it requestable worked —
the over-application is gone. Outside the layer, where the same concept is still a documented column
on the star, it continues exactly as before. **The mechanism is salience; the remedy is removing the
affordance; and a remedy that only covers the governed path only helps an arm that stays on it.**

`E_enforced`, which never leaves the governed path, has zero staff over-applications.

### The cost, stated

`E_enforced` fell to 10/15 at load 3 and **refused a load-1 question** — asking whether "not archived"
meant all time or a period. The provenance requirement makes it cautious as well as governed, and at
63/69 it is now below D. The two arms have swapped places since §20.


---

## 22. The Kimball fix on the star: the undocumented model becomes the best arm

The board's answer to the ISO failures was that they are a **modelling** gap, not a documentation
one. Kimball's rule for a dimension attribute is that it be verbose, descriptive and in business
terminology: a code is for joining, a label is for filtering. `warehouse/star.sql` stored `DE` alone
and pushed the decode onto every consumer.

Two attributes added to `dim_users`, beside the columns they decode:

```sql
CASE upper(ctry) WHEN 'DE' THEN 'Germany' … END          AS country_name
CASE WHEN <internal or test email> THEN 'staff'
     ELSE 'customer' END                                 AS user_type
```

`country` and `is_internal` are kept — twelve governed metrics and `agg_active_days` filter on the
flag, and retiring it is a migration rather than an edit.

### The run

| load | A_implicit | B_documented | C_modelled | C_modelled_doc | D_declared | E_enforced |
|---|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 9/9 | **5/9** | 9/9 |
| 1 | 15/15 | 15/15 | 14/15 | 15/15 | 14/15 | 15/15 |
| 2 | 8/15 | 15/15 | 15/15 | 15/15 | 14/15 | 15/15 |
| 3 | 13/15 | 14/15 | 15/15 | 13/15 | 15/15 | 11/15 |
| 4 | 11/15 | 10/15 | 13/15 | 13/15 | 13/15 | 14/15 |
| **total** | 56/69 | 63/69 | **66/69** | 65/69 | 61/69 | 64/69 |

**`C_modelled` went from 62 to 66/69 — the best score any arm has reached in this study**, and its
three ISO failures are gone: `pl_c2_segment`, `pl_c3_grain` and `pl_c4_join_path` all pass. The fix
landed exactly where the board predicted.

**The ordering is now `C_modelled` > `C_modelled_documented` > `E_enforced` > `B_documented` >
`D_declared` > `A_implicit`.** The **undocumented** star beats the documented one, the semantic
layer and everything else.

> When the model carries the meaning, documentation adds nothing and a layer above it costs
> something.

That is the sharpest statement this experiment has produced, and it is one run.

### A control regressed, and it exposed a defect in both engines

`D_declared` fell to **5/9 at load 0** — the controls. All three failures are the all-time figure
where June was asked: 2,500 instead of 553, 7,467 instead of 1,533, 457 instead of 106.

The trace names it:

| rep | arguments | result |
|---|---|---|
| 0 | `period: null`, `start`, `end` | **553** |
| 1, 2 | `period: "all"`, `start`, `end` | **2,500** |

**A named period and explicit dates were both supplied, and `period` silently won.** Both engines
did this — `semantic.py` and `metricflow_engine.py` each read `if period: start, end =
resolve_period(period)` and discarded the caller's window without a word.

That is this project's own subject matter, produced by the layer rather than by the model: a
plausible number for the wrong window, under a scope line naming the window it did not use.

Both engines now **refuse the ambiguous call** rather than resolving it:

```
period='all' was given together with start/end. Use one: a named period, or an explicit
start and end.
```

The mistake is unrepresentable rather than detectable, and the agent recovers by reissuing with one
of the two. **The run above predates the fix**, so `D_declared`'s 61/69 carries three control
failures that would not happen now.

### What is not settled

**Self-disagreement rose to 24 of 138 — 17%.** The previous D/E-only run was 11%. Larger runs are
noisier here and the arm ordering above is separated by one to three points across six arms.

**`A_implicit` fell to 8/15 at load 2** while every other arm scored 15/15. Its failures are the
same over-application and ISO problems as before, which the star fixes and the raw tables do not —
so the A-to-everything gap is now partly a measurement of the star rather than of documentation.
