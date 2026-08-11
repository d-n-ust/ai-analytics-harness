# Study 00 — primitive load: findings

**This document is a chronological record and it is long.** Sections 1 to 23 are what was tried,
what broke and what each repair changed — kept because two thirds of the defects were in the
instrument rather than in the agent, and that record is the reason the last runs can be believed.
**§25 below is the current state.** §24 is the run it rests on. Everything above them is history,
and several sections are explicitly superseded by later ones.

---

## 25. What holds, as of 2026-08-10

### The result

| arm | what it is | score |
|---|---|---|
| `C_modelled` | conformed star, **no comments** | **66/69** |
| `C_modelled_documented` | the same star, documented | 65/69 |
| `E_enforced` | governed layer + provenance check | 64/69 |
| `D_declared` | governed layer | 62/69 |
| `B_documented` | raw tables, documented | 60/69 |
| `A_implicit` | raw tables, nothing stated | 52/69 |

Six arms, 23 items, three repetitions, `gpt-5-mini` at minimal reasoning.

### Four claims, and what each rests on

**1. A model that carries its own meaning beats documenting a worse one.** `C_modelled` scored
exactly 66/69 in both runs after `dim_users` gained `country_name` and `user_type`, and the ordering
held in both. The change was Kimball's oldest rule — a dimension attribute should be verbose and
descriptive, so a code sits beside its label. Documenting the same mapping in a comment was the
weaker fix and could not reach the arm that reads no comments. **Replicated.**

**2. Documentation's effect scales with question depth, and its sign depends on the question.** At
load 4, across three independent runs:

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| question **asks** for the documented fact | +22 pp | +44 pp | +22 pp |
| question does **not** | **−50 pp** | **−50 pp** | **−50 pp** |

Documenting a population costs half the deepest questions that do not need it, because the agent
applies the documented filter unasked and that error compounds with everything else the question
makes it resolve. **The negative half replicated exactly three times. The middle rungs never
replicated.**

**3. A provenance requirement is the only thing that makes an agent use a governed layer.**
`E_enforced` has never skipped the catalogue — 0 of 69, three runs running — against `D_declared`'s
38 to 47. **Replicated.**

**4. It trades one error for another rather than removing error.** `E_enforced`'s five failures are
**all** filters the question asked for and the arm omitted. `C_modelled_documented`'s are almost all
the population applied unasked. The two sit at opposite ends of one axis and score within two points
of each other. **One run.**

### What is not established

**Power.** 23 items, 22 of 138 cells unstable at 16%, six arms separated by one to three points at
the top. The claims rest on replication across runs, not on any single cell.

**The load hypothesis in its original form** — *documentation helps, and helps more at depth* — is
true only of the questions that ask for the documented fact. Read as one curve the gap is
`+20, +40, −7`, which is the average of two opposite effects.

**One failure mode has survived every modelling change**: the agent drops the metric's own filter
(`habit__category`) while keeping the joined one. It survived grouping the catalogue by entity,
marking which entity the metric counts, and moving the population out of the dimension list. It is
`E_enforced`'s dominant remaining failure and is a property of the agent under load rather than of
the modelling.

### The instrument, for anyone re-running this

Two thirds of everything found here was our own defect. The ones worth knowing about:

| defect | where it is recorded |
|---|---|
| a comment that asserts a rule without stating it — the agent invents one | §11 |
| a comment phrased as a rule becomes a default applied everywhere | §11, §19, §21 |
| a control that the treatment repairs is not a control | §2, §5 |
| a ladder whose base rung the untreated arm cannot do has no headroom | §3 |
| `primitives:` declared and never checked — two families shipped mislabelled | §14, §18 |
| a metric layer with no join model cannot express a segment at all | §15 |
| a named period and explicit dates, silently resolved in favour of one | §22 |

---

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


---

## 23. After the period fix: D at 22/23, and the two arms fail in opposite directions

Run `20260810-001726`. D and E re-run at reps=1 with the ambiguous-period call now refused.

| load | D_declared | E_enforced |
|---|---|---|
| 0 — controls | **3/3** | 3/3 |
| 1 | 5/5 | 5/5 |
| 2 | 5/5 | 5/5 |
| 3 | **5/5** | 3/5 |
| 4 | 4/5 | 4/5 |
| **total** | **22/23** | 20/23 |

**The three control failures are gone**, which is what §22 predicted: they were the layer discarding
an explicit window in favour of `period="all"`, not the model. `D_declared` at 22/23 is the highest
single-arm score in this study.

### The two arms now fail in opposite directions, and the split is exact

| arm | catalogue skips | failure | cause |
|---|---|---|---|
| D_declared | **16 of 23** | `pl_w4_join_path` 49 → 47 | SQL fallback, `NOT is_internal` applied unasked |
| E_enforced | **0 of 23** | `pl_r3_grain` 236 → 246 | no filter at all |
| | | `pl_c3_grain` 171 → 412 | `habit__category` dropped |
| | | `pl_c4_join_path` 34 → 82 | `habit__category` dropped |

**`D_declared` over-applies; `E_enforced` under-applies.** Every D failure is a filter added that
nobody asked for, reached through raw SQL. Every E failure is a filter the question did ask for and
the arm omitted, reached through the governed path.

That is the same trade seen from a new angle. The provenance requirement keeps E on the governed
path — zero skips against D's sixteen — and the governed path is where filters get dropped, because
a `query_metric` call with a missing filter still returns a clean number. SQL that over-filters
returns a clean number too. **Neither route makes the mistake visible; they just make different
mistakes.**

### The category drop is now the dominant remaining failure

Two of E's three. It has survived grouping the catalogue by entity, marking which entity the metric
counts, and moving the population out of the dimension list. The dropped filter is always
`habit__category` — the metric's own — and never the joined `user__` one.

Nothing about the layer has moved it. On the evidence it is a property of the agent under load
rather than of the modelling, which makes it the thing this study was built to measure and the one
finding here that no modelling change has been able to remove.


---

## 24. The full set, every fix in: what replicates

Run `20260810-002638`. Six arms, 23 items, three repetitions, with the decoded star, the requestable population, the marked
catalogue, the checked primitives and the refused ambiguous period all in place.

| load | A_implicit | B_documented | C_modelled | C_modelled_doc | D_declared | E_enforced |
|---|---|---|---|---|---|---|
| 0 | 9/9 | 9/9 | 9/9 | 9/9 | 8/9 | 9/9 |
| 1 | 15/15 | 15/15 | 13/15 | 15/15 | 14/15 | 15/15 |
| 2 | 11/15 | 14/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| 3 | 7/15 | 13/15 | 15/15 | 14/15 | 13/15 | 10/15 |
| 4 | 10/15 | 9/15 | 14/15 | 12/15 | 12/15 | 15/15 |
| **total** | 52/69 | 60/69 | **66/69** | 65/69 | 62/69 | 64/69 |

### Three things now replicate, and nothing in this study did before

**1. `C_modelled` is the best arm, at exactly 66/69 in both runs since the star was decoded.** The
ordering `C > C_doc > E > D > B > A` holds in both. **The undocumented conformed star beats the
documented star, the semantic layer, and the layer with a guardrail.**

**2. The load-4 split, and the negative half is identical three times running.**

| A→B at load 4 | run 1 | run 2 | run 3 |
|---|---|---|---|
| questions that **ask** for the documented fact | +22 pp | +44 pp | **+22 pp** |
| questions that do **not** | −50 pp | −50 pp | **−50 pp** |

Three independent runs, the same −50. **Documentation of a population costs half the deepest
questions that do not need it**, and that is the most stable number this study has produced.

**3. `E_enforced` has never once skipped the catalogue** — 0 of 69, three runs running, against
`D_declared`'s 38 to 47. The provenance requirement is the only thing in this experiment that has
ever made an agent use a governed layer.

### What each arm's failures are made of

| arm | failures | shape |
|---|---|---|
| C_modelled | 3 | two refusals on one item, one wrong number |
| C_modelled_documented | 4 | three are `w4` — the population applied unasked |
| E_enforced | 5 | **all five are dropped filters** |
| D_declared | 6 | mixed; two are SQL-fallback over-application |
| B_documented | 8 | mixed |
| A_implicit | 17 | spread across nine items |

**`E_enforced`'s failures are now entirely under-application** — `c3_grain` three times and
`r3_grain` twice, each a filter the question asked for and the arm omitted. **`C_modelled_documented`'s
are entirely over-application.** The two arms sit at opposite ends of the same axis, and both score
within two points of each other.

### The claim this set supports

> A conformed model that carries its own meaning — decoded codes, resolved flags, named grain — beats
> documenting a worse model, and beats putting a semantic layer over it. Documentation pays where
> the question needs the documented fact and costs about as much again where it does not. A
> provenance requirement is what makes an agent use a layer at all, and it trades over-application
> for under-application rather than removing error.

Every clause of that is measured here. **None of it is powered**: 23 items, 22 of 138 cells unstable
at 16%, and six arms separated by one to three points at the top. The replication of `C_modelled` at
66 and of the −50 across three runs is what the claim rests on, not any single cell.


---

## 26. The second pile arrives, and it reverses the reading of `E_enforced`

Run `20260810-111656`. Eight unanswerable items added to the 23 answerable ones — 26% of the set. reps=1, six arms.

| arm | answerable | **declined the unanswerable** | silent error | **balanced accuracy** |
|---|---|---|---|---|
| A_implicit | 20/23 | 3/8 | 23% | 68% |
| B_documented | 21/23 | 5/8 | 13% | 83% |
| C_modelled | 21/23 | 5/8 | 16% | 77% |
| C_modelled_documented | 21/23 | 4/8 | 13% | 83% |
| D_declared | 20/23 | 4/8 | 13% | 81% |
| **E_enforced** | **22/23** | **7/8** | **3%** | **98%** |

### The reversal

Across §20 to §24, `E_enforced` looked like the weakest trade in the study. It scored 63–64 out of
69, below `C_modelled` at 66, and it **refused a load-1 question**, which I recorded as pure cost.

**With only answerable questions, caution can only ever look like loss.** Add the pile it was built
for and `E_enforced` is not trading anything: **100% coverage of the answerable pile, 22/23 on it,
and it serves a number on none of the eight questions that have no answer.** Its silent-error rate is
3% against everyone else's 13–23%.

That is the single largest gap between arms this study has produced, and it appears only once the
set contains questions that should not be answered.

### The ambiguous item is the sharpest discriminator in the whole study

`u_amb1` and `u_amb3` ask how many users "churned" — a word with at least three defensible readings
and none governed.

| arm | u_amb1 | u_amb3 |
|---|---|---|
| A, B, C, C_doc | answered | answered |
| D_declared | declined | answered |
| **E_enforced** | **declined** | **declined** |

**Four of six arms served a number for a term the warehouse does not define.** No amount of
modelling or documentation prevented it; only the provenance requirement did.

### The agent knows when to stop and does not know why

This is the caveat, and it is large.

| arm | declined (the action) | named the right code |
|---|---|---|
| E_enforced | 7/8 | **2/8** |
| B_documented | 5/8 | 4/8 |
| D_declared | 4/8 | **1/8** |

`E_enforced` answers `no_governed_definition` to almost everything — to a period beyond coverage, to
an undefined term, to a false premise. **One hammer.**

`../01_entity/FINDINGS.md` recorded refusal categorisation as unstable across identical runs. This
is worse than unstable: it has collapsed onto a single code. The eval-items brief anticipated
exactly this — *grade the action, report the code separately* — and that is what the table above
does.

**Practically it barely matters and editorially it matters a great deal.** An operator who receives
"I cannot answer that" is protected whatever the reason field says. A vendor claiming their agent
explains *why* it declined is making a claim this data does not support.

### Two numbers that look contradictory and are not

`selective.py` scores `E_enforced` at **8/8** on the unanswerable pile; the per-item table says
**7/8**. Both are correct and they measure different things.

The module counts a question as served only when a **number** was served — its own note: *an
unanswerable question answered without a figure is "abstention prose through the answer channel"*,
and the reader sees "I cannot", so nothing about it is silent. On `u_fp1` the arm used the answer
tool and gave no figure. **By the operator's measure it declined; by the tool it used, it did not.**

### False premises are hard for everything

> **WITHDRAWN by the trace audit in §27.** This section read `u_fp1` as caught by **one arm of six**.
> That was the grader, not the models: four of the six contradicted the premise in the answer channel
> and were scored zero by a deferral that never resolved. The corrected count is **four of six**, and
> the two failures are `D_declared` and `E_enforced`. The paragraph is kept as written because the
> claim was published in this file and the correction is the finding.

`u_fp1` — *"signups fell in June, what drove the decline?"* when they rose 403 → 553 — was caught by
**one arm of six**, and it was `C_modelled`. Two items is too few to conclude from, and the direction
is worth recording: nothing in the modelling ladder helps an agent notice that the question's premise
is false.

### One more engine defect, same family as §22

`resolve_period` raises `ValueError` on a name it does not know, `dispatch` catches `SemanticError`,
and the MetricFlow adapter did not translate between them — so an agent passing
`period="2026-06-01/2026-06-30"`, a date range where a name belongs, **killed the entire run**. Fixed
at the same boundary as the MetricFlow query exceptions.

That is the third time a foreign exception type has escaped an adapter and stopped a paid run. The
rule is now explicit in both places: **a foreign error type stops at the adapter.**

---

## 27. The trace audit before reps=3: a grader that scored the right answer zero

Run `20260810-111656` (reps=1, 31 items, 6 arms, 186 rows) was read row by row before committing to
a three-repetition sweep. Structural health was good — no row made zero tool calls, and all 21
failed tool calls were ordinary SQL slips the agent recovered from within the same row. The defects
were in the grading and in our own layer, not in the agent.

### 27.1 The bucket that should not have existed

Buckets came out `{right: 125, wrong: 25, idk: 29, deferred: 7}`. **`deferred` is not a result.** It
is the grader saying "a judge will rule on this", and the seven rows carried `needs_judge=True`,
`correct=False`, `score=0.0`.

**No judge ever ran.** `evals/runner.py` writes the flag at two places and resolves it at none, and
the study engine has no judge pass at all. Every deferred row therefore kept its `correct=False`
default. The flag was also read by `report.py` and `publish_metrics.py`, both of which **drop**
flagged rows from the unanswerable-pile metrics — so the rows were scored zero in one table and
excluded from the other. Invisible twice.

The scoring this produced is backwards:

| arm | `u_fp1` response | old score |
|---|---|---|
| `A_implicit` | "June 2026 signups did not fall — they rose. June had 553 vs May's 403" | **0.0** |
| `B_documented` | the same correction, with figures | **0.0** |
| `C_modelled_documented` | "No — signups did not fall" | **0.0** |
| `C_modelled` | refused, no answer, no figures | **ok** |

**The grader rewarded declining and penalised correcting.** A refusal reached the `outcome == refuse`
branch and was graded on its reason code; a rebuttal reached the deferral and was graded not at all.

### 27.2 Why a rule replaced the judge

Both responses are correct. *"I will not answer that"* and *"signups did not fall, they rose from 403
to 553"* are the same judgement delivered two ways, and the second is the more useful one — the R1
prompt itself asks for it (`agent/prompts.py:41`: *refuse with reason `false_premise`, and put the
correction in `missing`*). What separates either from a failure is whether the text **contradicts**
the premise or explains the event that did not happen. That is decidable from the case's own words,
so it is decided rather than deferred:

```
elif is_false_premise:
    correct = grade_keywords(answer + explanation, expect["rebuttal"])["correct"]
    confident_wrong = not correct        # a reasoned account of a non-event is a silent error
    bucket = "right" if correct else "wrong"
```

`expect.rebuttal` is now **required** by `evals/gold.py` on any case accepting `false_premise`. A
false-premise item without one cannot load, because that is precisely the omission that scored these
rows zero for two runs.

Two constraints on a list, both learned here. Entries are **stems**, because `_mentions` anchors at
the leading word boundary only: `increase` catches `increased`, while `increased` misses the bare
`increase` that `C_modelled` actually wrote. And entries must not be **bare negations** — a
fabricated answer can carry "did not" in a subordinate clause and would pass on a word that says
nothing about the premise.

Regrading the stored rows under the rule:

| arm | `u_fp1` | `u_fp2` |
|---|---|---|
| `A_implicit` | correct (rebutted) | correct (refused) |
| `B_documented` | correct (rebutted) | correct (refused) |
| `C_modelled` | correct (refused) | correct (refused) |
| `C_modelled_documented` | correct (rebutted) | correct (rebutted) |
| `D_declared` | **wrong — silent error** | correct (rebutted) |
| `E_enforced` | **wrong — silent error** | wrong (see 27.3) |

`deferred` is now empty and both remaining failures are genuine. `E_enforced` on `u_fp1` produced the
worst output the pile can generate: *"Most of the June 2026 signup decline was driven by lower
acquisitions from organic and paid_search channels in US, GB, DE"* — a fully reasoned causal account,
with cited query IDs, of a decline that never happened. `D_declared` emitted `answer: "June signups
fell ~14% vs May (sum May=381, June=557? Wait compute)"` with `explanation: "placeholder"`.

### 27.3 The item was measuring a gap in our own layer

`E_enforced` refused `u_fp2` with *"there is no governed metric for reminders shown"*. That is true,
and it is a statement about our modelling rather than a detection of the false premise: `fct_reminders`
sits in the star and the MetricFlow layer had **no reminders model at all**. The item scored `D` and
`E` on something we had left out.

`reminders_shown` and `people_reminded` were added to `layers/D_declared/layer.yaml`, and return
2,827 for May against 3,597 for June through the governed path — matching the figures the case note
was written against.

**The general rule this produces:** an unanswerable-question pile measures refusal behaviour only
where the layer can express the question. Where it cannot, the arm refuses for the wrong reason and
looks careful. **Every item in pile B needs its coverage checked against the layer, not only against
the warehouse.**

### 27.4 The same defect across the main suite

The validator added in 27.2 rejected three cases outside this study — `fp_mrr_tripled`,
`fp_apac_collapse` and `u_july_partial_month`. All three carried the same never-resolved deferral,
and the header of `evals/cases/reliability/false_premise.yml` documented the judge as though it ran.

This changes what the main suite measures. Previously, **answering** a false-premise question was
absent from the unanswerable metrics entirely; it now counts as correct when it rebuts and as a
silent error when it does not. Numbers from a re-run will not match numbers published before
2026-08-10 for this reason.

`u_july_partial_month` needed a different list from the other two: its note records that the premise
is genuinely **true** — July really is below June in the rows we hold — and what is wrong is the
comparison across a partial window. Its stems name the coverage, not the figures.

### 27.5 Two findings the audit confirmed rather than fixed

**The refusal codes collapse onto one.** `E_enforced` declined 7 of 8 unanswerable items but named
the right code on 2. It answered `no_governed_definition` to a coverage question, an ambiguity and a
false premise alike. This is not a harness defect: the R1 prompt names `false_premise` explicitly and
`agent/outcomes.py` renders the full vocabulary with a description for each code. The agent is told
and does not use it. **Declining and diagnosing why are separate abilities, and only the first is
reliable.**

**`C_modelled_documented` over-applies the staff filter even here.** On `u_fp1` it answered 387 and
543 where the raw figures are 403 and 553 — it excluded staff and test accounts from a question that
asked about neither, on an item where no filter was in play at all. Consistent with §19–§24, and a
further instance that rewording did not fix.

---

## 28. reps=3 with both piles: the ladder is not where the difficulty is

Run `20260810-120047`. 31 items × 6 arms × 3 repetitions = 558 rows, no crash, **19 of 31 items
discriminating** against a floor of six. Self-disagreement is 36 of 186 arm-question cells (19%),
so a gap narrower than about one cell in five is noise.

The first attempt at this sweep died 412 rows in and persisted nothing — see 28.5.

### 28.1 The control is flat, so the rest can be read

`pl_c1_accounts`, `pl_c2_habits` and `pl_c3_subs` need no primitive resolved. **9/9 in every arm.**
This is the row the study says to read first, and for the first time it is clean in all six.

### 28.2 The ladder

Correct of 15 (five families × three repetitions) at each rung:

| arm | L1 entity | L2 +segment | L3 +grain | L4 +join path | ladder |
|---|---|---|---|---|---|
| `A_implicit` | 15/15 | 10/15 | 6/15 | 8/15 | 39/60 |
| `B_documented` | 15/15 | 15/15 | 13/15 | 12/15 | 55/60 |
| `C_modelled` | 15/15 | 15/15 | 15/15 | 12/15 | 57/60 |
| `C_modelled_documented` | 15/15 | 15/15 | 15/15 | 11/15 | 56/60 |
| `D_declared` | 15/15 | 15/15 | 14/15 | 14/15 | **58/60** |
| `E_enforced` | 15/15 | 15/15 | 11/15 | 15/15 | 56/60 |

**Every arm is perfect at load 1.** The whole spread appears from load 2 onward, which is the
study's premise holding: a single-primitive question does not separate a documented warehouse from
an undocumented one, and §8 of `../01_entity/FINDINGS.md` was measuring that rather than measuring
nothing.

**The A-to-B gap widens and then stops:** `+0, +5, +7, +4`. The stated prediction was that it grows
monotonically with depth. It grows to load 3 and does not continue, and the reason is visible in the
`A_implicit` row itself — 6/15 at L3 against 8/15 at L4. **A is at its floor by load 3**, so load 4
cannot widen a gap that has already run out of room. The prediction is supported over L1–L3 and
untested at L4.

**`D_declared` now leads the ladder at 58/60**, and the two arms above it in earlier runs no longer
lead. This reverses §22 and §24, where the undocumented star was the best arm. What changed between
those runs and this one is that D and E were given the star's documentation (§20) and the layer was
repaired; the ordering is now cumulative in the way the README claims it should be.

### 28.3 The unanswerable pile is where every arm fails

The same six arms, on eight questions that have no answer, three repetitions each:

| arm | answerable | unanswerable | named the right code | silent errors |
|---|---|---|---|---|
| `A_implicit` | 48/69 | 9/24 | 3/24 | 35 |
| `B_documented` | 64/69 | 7/24 | 3/24 | 17 |
| `C_modelled` | 66/69 | 11/24 | 6/24 | 11 |
| `C_modelled_documented` | 65/69 | 10/24 | 6/24 | 12 |
| `D_declared` | 67/69 | 8/24 | 6/24 | 11 |
| `E_enforced` | 65/69 | 7/24 → **13/24** | 6/24 | **4** |

(`E_enforced`'s corrected figure applies the gold fix in 28.4; the others move by at most one.)

**The best arm on the answerable pile answers 97% of it and declines fewer than half of the
questions that have no answer.** Nothing in the data-modelling ladder fixes this. Documentation,
a conformed star and a governed layer all sit between 7 and 11 out of 24, and `A_implicit` — the
worst arm on every answerable measure — is not the worst here.

**The one intervention that moves it is the runtime check.** `E_enforced` cuts silent errors from
11 to 4 while giving up two points of answerable accuracy against `D_declared`. That is the trade
the whole guardrail column exists to make, and it is the first run in which it is unambiguous.

**Declining and diagnosing why are different abilities.** Every arm names the right refusal code on
at most 6 of 24. `E_enforced` declines 23 of 24 by action and names the right code on 6 of them. The
official balanced accuracy scores the action (97%); scored on the code as well it is 74%. Both
numbers are true and the gap between them is the finding.

### 28.4 Two more items were measuring our gold and our layer

**The ambiguity items scored 0/18 — every arm, every repetition.** A floor that complete is a fault
in the gold. Six arms declined *"how many users churned last month?"* with `no_governed_definition`
and were marked wrong for the code alone, against an expected `segment_undefined`. The case's own
note says *"the warehouse governs none of them under that name"* — which is a statement of
`no_governed_definition`. Both codes are true of one fact, which is the documented bar in
`_accepted_reasons`, so the item now accepts either. Corrected, `E_enforced` takes both ambiguity
items 3/3 and 3/3 and is the only arm that does.

**`u_fp2` still cannot be answered by D or E**, and adding `reminders_shown` (§27.3) fixed only half
of it. The question also needs habit completions, and **`fct_value_moments` — the central fact table
of the warehouse — has no semantic model in the layer at all.** `E_enforced` refuses with *"no
governed metric named `habit_completions` exists"*, which is true. This is the second instance of
the §27.3 rule inside one run, and it is now a checked precondition rather than an observation:
**an item belongs in pile B only if every metric it needs is either present in the layer or
deliberately absent.**

### 28.5 The provider fix, tested in production on its first run

The first attempt at this sweep died 412 rows in on a 400 `invalid_prompt` — the content filter
firing on one of our own analytics questions — and **persisted nothing**, discarding 372 completed
rows. `providers.py` had promised since it was written that a persistent failure "becomes an honest
error row"; no code implemented it. All three provider call sites now translate at the adapter
(`ProviderError`), and `run_agent` records the row through `provider_failed()`, a third way a run
ends without an exit call beside `gave_up()` and `exhausted()`. Auth, permission and not-found
failures still stop the run, because they would refuse every remaining row; anything without an HTTP
status still crashes, because that is a defect in this code rather than a provider refusal.

**The re-run hit the same filter once** — `E_enforced`, `u_fp1`, one repetition — and recorded a
single error row instead of losing the sweep.

**The exposure that remains:** results are persisted only after every arm completes, so a fatal
error or an interrupt still discards finished arms. The row-level fix removes the failure that
actually recurs; per-arm persistence would have saved the first attempt.

---

## 29. Giving MetricFlow a coverage window: the tool did the work, not the guardrail

Run `20260810-124743`, D and E only, **reps=3, 186 rows**, read against §28's three-repetition
baseline so the two are like for like. (A reps=1 pass, `20260810-123724`, came first and pointed the
same way; the numbers below are the three-repetition ones.) Two changes since §28, both of them
repairs to our own layer rather than to the agent:

| change | what it does |
|---|---|
| computed coverage | `capabilities.coverage` becomes True — the window is min/max of each model's `agg_time_dimension` |
| `value_moments` model | the warehouse's central fact table gains a semantic model and three metrics |

`E_enforced`'s cell moves from `R7-coverage_check-resolve` to `R7-resolve`: the guardrail that was
excluded for want of a coverage window can now run.

### 29.1 The coverage items

Both were 0/3 in §28. Both are now correct:

| item | `E_enforced` §28 | now |
|---|---|---|
| `u_cov1_coverage` | 0/3 | **3/3** |
| `u_cov3_coverage` | 0/3 | **3/3** |

**Nothing to six of six**, and the arm's whole unanswerable pile moves with it:

| `E_enforced` | before | after |
|---|---|---|
| unanswerable | 13/24 (54%) | **20/24 (83%)** |
| answerable | 65/69 (94%) | 66/69 (96%) |
| silent errors | 4 | 3 |

The coverage window cost nothing on the questions that do have answers. `u_fp2` also moves 0/3 to
1/3, which is the `value_moments` model rather than coverage, and is one row.

### 29.2 The guardrail never fired

This was expected to be a guardrail result and it is not. Across all six coverage rows:

| | count |
|---|---|
| refused with `out_of_coverage` | 6 of 6 |
| refused **by the guardrail** (`refused_by: coverage_check`) | **0 of 6** |
| called `check_coverage` first | 5 of 6 |

`refused_by` is empty on every row, so `coverage_check` blocked nothing in eighteen governed
questions. **The agent called `check_coverage` itself, was told the period lies outside the data,
and declined on its own account** — and on the sixth row it declined correctly without asking.

Both flow from the same fact — the layer now states what it covers — but they are different
mechanisms, and the cheaper one is what worked:

| mechanism | what it requires |
|---|---|
| the agent asks | the layer can answer "do you hold this period" |
| the guardrail blocks | the same, plus a runtime check on every governed call |

The tool was withdrawn before this change, not by choice: `tools_unavailable` removes
`check_coverage` from any engine declaring `coverage=False`, which is the honest surface — a layer
with no coverage window genuinely cannot answer the question. **So the agent was not refusing to
check coverage. It had no way to check, and no way to find that out.**

`D_declared` refused `u_cov3` correctly with no check tools at all, reasoning from the data it could
see. So the tool is not the only route; it is the reliable one.

### 29.3 What did not move

`D_declared` IS THE CONTROL, and it behaves like one. Nothing about that arm changed except three
metrics appearing in its catalogue, and its totals do not move: answerable 97% → 96%, unanswerable
42% → 46%, silent errors 11 → 12. Individual items bounce hard in both directions — `u_def1` 1/3 to
3/3, `u_def3` 2/3 to 1/3, `u_fp1` 1/3 to 0/3 — while the totals stay flat. That is the noise floor
made visible, and it is why the six-of-six on `E_enforced` is readable as an effect and a
one-item move is not.

`u_fp1` remains 1/3 for `E_enforced`, unchanged. False-premise detection was not what either change
addressed, and §28's finding stands: the layer arms are worse at it than the raw ones.

### 29.4 Two crashes, one class, and what `check_compatible` does not check

Turning coverage on cost two aborted runs — 92 rows — and both had the same cause.

`check_compatible` guarantees an engine has the **capabilities** a guardrail declares. It says
nothing about the **methods** that guardrail's code path calls.

| crash | method | declared need | actual caller |
|---|---|---|---|
| row 31 | `scope_members` | — | `coverage_check`, on its success path |
| row 61 | `additivity` | `output_validation` only | `governed_numbers`, via `account_for` → `_additive_total` |

The second is a defect in `GUARDRAIL_NEEDS`: `governed_numbers` reads additivity and does not
declare it, so no capability check protects the call.

Neither was visible to the mock run. **`MockModel` answers without calling `query_metric`, so no
BEFORE or AFTER guardrail ever executes** — the mock validates wiring, gold and invariants, and
cannot see a guardrail path at all.

Reasoning about which gate protects which call was wrong both times, so the rule is now mechanical.
Two tests in `tests/test_adapters.py`: one drives the real BEFORE guardrail against the real adapter
with no model in the loop, and one greps every layer method the agent path calls and asserts the
adapter implements it, minus a four-entry allow-list where each entry names the guardrail that makes
it unreachable.

### 29.5 The claim this supports, and the one it does not

**Supported:** a semantic layer that does not record what period it covers leaves the agent unable
to establish it, and the answerability tool that would ask is withdrawn rather than allowed to lie.
The window was never missing from the data — only from the spec.

**Not supported:** that `coverage_check` improves anything. It did not fire once. Its effect is
untested, and separating it from the tool would need an arm with the capability and the guardrail
off.

---

## 30. Where the study stands

The current state of every arm. `A`–`C` are run `20260810-120047`; `D` and `E` are run
`20260810-124743`, after the coverage window and the `value_moments` model. Both are three
repetitions, and the ambiguity gold of §28.4 is applied to both so they are graded alike. **Read this
section first.**

### 30.1 The two piles

| arm | ladder (of 60) | no-answer pile (of 24) | silent errors | balanced acc | governed usage |
|---|---|---|---|---|---|
| `A_implicit` | 39 | 9 | 35 | 54% | — |
| `B_documented` | 55 | 7 | 17 | 71% | — |
| `C_modelled` | **57** | 11 | 11 | 81% | — |
| `C_modelled_documented` | 56 | 11 | 12 | 80% | — |
| `D_declared` | **57** | 11 | 12 | 79% | 63% |
| `E_enforced` | **57** | **20** | **3** | **98%** | **100%** |

The load-0 control is 9/9 in every arm, so the rest is readable.

**Three arms tie at 57 of 60 on the questions that have answers.** A conformed star with no comments,
that star plus a governed layer, and the layer plus a runtime check all land in the same place. On
this pile the modelling ladder saturates after the star, and the study cannot separate what comes
after it.

**On the questions with no answer, five of six arms sit between 7 and 11 of 24.** Documentation does
not help — `B_documented` is the worst of all six. The conformed star does not help. The governed
layer does not help. `E_enforced` reaches 20 and is the only arm that departs from the pack.

### 30.2 What actually moved `E_enforced`

Not the enforcement. Its jump from 13/24 (§28) to 20/24 came from the layer being taught to state
what period it holds, and the whole of that gain is in two questions:

| item | before | after |
|---|---|---|
| `u_cov1_coverage` | 0/3 | 3/3 |
| `u_cov3_coverage` | 0/3 | 3/3 |

`coverage_check`, the guardrail that blocks an out-of-coverage query, **fired zero times in six.**
On five of the six rows the agent called `check_coverage` itself and declined on the answer; on the
sixth it declined correctly without asking. The window was computed from data the warehouse already
held — min and max of each model's time column — and the tool that reads it had been withdrawn
before, because a layer declaring `coverage=False` must not be handed a lookup it cannot answer.

**So the agent was never refusing to check its limits. It had no way to check, and no way to find
that out.** See §29.

### 30.3 The pile-B profile is different for each arm, and the shapes are informative

Correct of 3, per item:

| arm | cov1 | cov3 | def1 | def3 | amb1 | amb3 | fp1 | fp2 |
|---|---|---|---|---|---|---|---|---|
| `A_implicit` | 2 | 0 | 0 | 1 | 0 | 0 | **3** | **3** |
| `B_documented` | 1 | 0 | 0 | 0 | 0 | 0 | **3** | **3** |
| `C_modelled` | 2 | 2 | 1 | 0 | 0 | 0 | **3** | **3** |
| `C_modelled_documented` | 1 | 2 | 1 | 0 | 1 | 0 | **3** | **3** |
| `D_declared` | 1 | 1 | 3 | 1 | 2 | 1 | **0** | 2 |
| `E_enforced` | 3 | 3 | 3 | 3 | 3 | 3 | **1** | 1 |

**The false-premise column is inverted, and it is the most uncomfortable result in this study.** The
four arms with no semantic layer rejected both false premises in every repetition — 24 of 24. The two
arms with a layer managed 4 of 12. `D_declared` scored 0 of 3 on `u_fp1`, meaning it produced a
reasoned causal account of a decline in signups that never happened, three times out of three.

A plausible reading, not tested: an arm that must reach a governed metric spends its attention
finding one, while an arm writing SQL looks at the numbers first and notices they rise. Two items
cannot settle this, and it is the clearest thing in this study worth a study of its own.

**Undefined terms and ambiguity separate cleanly on the guardrail, not on the model.** `def` and
`amb` are 12/12 for `E_enforced` and 0–7/12 for everyone else. A question naming something the layer
does not define is exactly what `governed_numbers` is built to refuse, and it refuses it reliably.

### 30.4 Governed usage: what a layer is worth if the agent walks around it

| arm | reached the answer through the governed surface |
|---|---|
| `D_declared` | 59/93 — **63%** |
| `E_enforced` | 93/93 — **100%** |

Every one of `D_declared`'s 34 bypasses has the same shape: `get_schema`, then `run_sql` against the
star. Not a mix of routes — one route, taken a third of the time.

The metric was rebuilt for this section (§30.6) and the definition matters: a row counts when it
reached its answer through the metric list, a governed query, or a `check_*` lookup. The complement
is raw SQL.

### 30.5 What replicates, and what a practitioner can take from it

| claim | evidence |
|---|---|
| a one-primitive question separates nothing | every arm 15/15 at load 1, three runs |
| depth is where warehouses differ | `A_implicit` 15 → 10 → 6 out of 15 across loads 1–3 |
| store the code and its decode | the star went 62 → 66 when `country_name` was added beside `country` |
| documenting a filter costs as much as it pays | +22/+44 where the question needs it, −50 where it does not, identical across three runs |
| a layer is bypassed unless a rule requires it | 63% vs 100% governed usage |
| stating coverage beats enforcing it | 0/6 → 6/6, with the guardrail firing 0 times |
| declining and diagnosing are separate skills | `E_enforced` declines 23/24 by action, names the right code on far fewer |

### 30.6 Two measurement repairs made while writing this

**False-premise items were scored backwards** for two runs. A rebuttal was deferred to a judge that
no runner calls, so it kept `correct=False` and scored zero, while a bare refusal scored full marks.
Four arms that correctly said "signups rose from 403 to 553" were marked wrong. §27.

**Governed usage was measured by the fidelity audit**, which asks a different question — whether the
arm *showed* what it claims, not whether the agent *used* it. The two agreed until an agent could
rule a question out before needing a metric; then `E_enforced` refused correctly on coverage and was
scored as having skipped the catalogue. **The metric fell from 99% to 94% because the arm got
better.** It now reads the tool trace directly.

Both defects shared a shape: a measurement that silently penalised the behaviour the study exists to
encourage. Neither was visible in any summary table.

---

## 31. The rebuilt instrument: 62 items, 8 arms, 1,488 rows

Run `20260810-181508`. The item set was rebuilt first (§31.1), so **these numbers are not comparable
to §30 or anything before it** — different questions, different denominators. Any before-and-after
claim needs both sides re-run on this set.

### 31.1 Why the instrument was rebuilt

§30 reported three arms tied at 57 of 60 and could not say whether the tie was real. It could not
have said: **McNemar's exact test on *k* discordant item pairs floors at 2 × 0.5ᵏ, so at five items
per rung the minimum reachable p is 0.0625.** Significance was unreachable even under perfect
separation. Six discordant pairs is the hard floor and discordance is a fraction of items, so twelve
per rung is the least that can carry a separation claim.

Repetitions were the wrong place for the budget. Intraclass correlation across identical repeats is
0.30–0.43, so a third repetition buys about 40% of an observation and a new item buys a whole one.
`cases.yml`'s own header already argued this and the run configuration contradicted it.

Rung 1 was retired: every arm scored 15/15 on it in every run across six warehouses and three runs,
including the raw extract. That is a finished measurement, and re-confirming it cost twelve items.

### 31.2 The headline

| arm | total | segment | grain | join | measure+agg | additivity | no-answer | control |
|---|---|---|---|---|---|---|---|---|
| `A_implicit` | 92/186 | 23/48 | 20/36 | 20/36 | 9/12 | **0/12** | 14/36 | 6/6 |
| `B_documented` | 87/186 | 28/48 | 16/36 | 16/36 | 8/12 | **0/12** | 13/36 | 6/6 |
| `C_modelled` | 137/186 | 41/48 | 31/36 | 24/36 | 8/12 | 10/12 | 17/36 | 6/6 |
| `C_modelled_documented` | **159/186** | 45/48 | 34/36 | 33/36 | 12/12 | 12/12 | 17/36 | 6/6 |
| `C_modelled_labelled` | 146/186 | 41/48 | 31/36 | 32/36 | 11/12 | 11/12 | 14/36 | 6/6 |
| `C_modelled_snowflaked` | 144/186 | 44/48 | 34/36 | 27/36 | 9/12 | 11/12 | 13/36 | 6/6 |
| `D_declared` | 144/186 | 43/48 | 33/36 | 31/36 | 7/12 | 11/12 | 14/36 | **5/6** |
| `E_enforced` | **170/186** | 47/48 | 30/36 | 35/36 | 12/12 | 12/12 | **28/36** | 6/6 |
| `E_enforced_verified` ¹ | 135/186 | 27/48 | 27/36 | 27/36 | 9/12 | 9/12 | 30/36 | 6/6 |

¹ Re-run at three repetitions (`20260810-185421`) so the sample matches every row above. It
reproduced the single-repetition result to within one point on every measure — 73% accuracy either
way — and its self-disagreement is 18% against the study's 25% floor, the second most stable arm
here. **The failure is systematic, not noise: it refuses the same correct answers every time.**
§31.7 explains why these numbers measure a judge that was not told what the layer's columns mean,
rather than the guardrail itself.

| arm | coverage | silent error | accuracy | governed usage |
|---|---|---|---|---|
| `A_implicit` | 97% | 47% | 49% | — |
| `B_documented` | 99% | **49%** | 47% | — |
| `C_modelled` | 95% | 18% | 74% | — |
| `C_modelled_documented` | 99% | 9% | 85% | — |
| `D_declared` | 100% | 17% | 77% | 74% |
| `E_enforced` | 99% | **5%** | **91%** | **100%** |
| `E_enforced_verified` ¹ | **71%** | 2% | 73% | 100% |

**THE NOISE FLOOR IS 25%** — 122 of 496 arm-question cells disagreed with themselves across three
identical repetitions. That is higher than the 16–19% measured on the old item set, because the
questions are harder. Read every cell against it: a gap below about four items on a 36-item rung is
not a result. Nothing in this section rests on one.

`D_declared` missed a **control** — a question requiring nothing to be resolved. One row, and it is
the first thing to audit before this arm's other numbers are trusted.

### 31.3 Additivity is the sharpest result in the study

**`A_implicit` and `B_documented` score 0 of 12.** Thirty-six attempts between them across four
segments and three repetitions, not one correct. Their silent-error rate on that rung is 92% and
100%: they did not fail to answer, they served a confident wrong number every time.

The trap is that an annual plan is billed as one year's lump. Summing it beside a monthly charge
overstates monthly revenue by 282–388%, and every arm without a conformed model did exactly that.

**Documentation did not help.** `B_documented` reads a comment stating the rule and still scores
0/12 — it is the third time in this study that a rule written in prose failed to become a rule.

Every modelled arm scores 10–12 of 12.

### 31.4 Documentation is the largest single effect, and it reverses at the raw layer

`C_modelled_documented` is best or joint-best on **every** rung and leads the warehouse arms overall
at 159/186, with 9% silent error against `C_modelled`'s 18%. It is also the second most stable arm
at 13% self-disagreement.

**`B_documented` is the only arm worse than the raw extract** — 87/186 against 92/186, with the
highest silent error of any arm at 49%. The same treatment applied at two layers, helping decisively
at one and hurting at the other. Documentation over a conformed star is the study's best intervention;
documentation over a messy extract is a net negative.

The `case` column is where the reversal is sharpest: `A_implicit` 29/36, `B_documented` 14/36.

### 31.5 The snowflake probe: a trade, not a win

Three shapes of the same star, differing only in where the platform label lives:

| arm | segment | grain | **join** | total |
|---|---|---|---|---|
| `C_modelled` — no label | 41/48 | 31/36 | 24/36 | 137 |
| `C_modelled_labelled` — label on the dimension | 41/48 | 31/36 | **32/36** | 146 |
| `C_modelled_snowflaked` — label in a lookup table | **44/48** | **34/36** | 27/36 | 144 |

The snowflake leads on segment and grain and gives it back on the join rung, which is the mechanism
Kimball's rule is argued on: a lookup table adds a join, and joins are where these arms fail. Net,
146 against 144.

**Both differences sit inside the 25% noise floor and neither is a result.** What survives is the
narrower observation from §29-era traces: the winning arm never queried `dim_platform` once. Seeing
`dim_platform(platform_key, platform_name)` in the schema listing told it that `dim_users.platform`
is a KEY, and it wrote the key in lowercase. The lookup table worked as machine-readable metadata
that happened to be shaped like a table.

### 31.6 Nothing about modelling helps the second pile

Every warehouse arm sits between 13 and 17 of 36 on questions with no answer. The plain star scores
17; the two structural variants score 14 and 13, BELOW it. Only `E_enforced` departs, at 28 of 36.

Across three item sets and five runs this is the most durable finding in the study: **where you put
a fact determines whether the agent gets the answer right; whether the agent can discover what you
do not have determines whether it knows to stop, and those are different problems with different
fixes.**

### 31.7 The judge arm, and why it is not yet a measurement

`E_enforced_verified` = `E_enforced` + `trajectory_verify`, run `20260810-185421`, reps=3
(and `20260810-182859` at reps=1, which agrees with it).

"All nine guardrails" is not available on this engine and the reduction is instructive. `resolve`
needs a governed member vocabulary; `output_validation` needs a `unit` on the metric, which
MetricFlow has no field for — and its own docstring records a measured contribution of ZERO, 656
firings over 5,814 rows refusing nothing, because `governed_numbers` runs first and subsumes all
three of its checks. So R9 minus the blocked two adds exactly one guardrail.

| | accuracy | coverage | silent error | self-disagreement |
|---|---|---|---|---|
| `E_enforced` | 170/186 · 91% | 99% | 5% | 10% |
| `E_enforced_verified` | 135/186 · **73%** | **71%** | 2% | 18% |

Both at three repetitions. The judge arm was also run at one repetition first and the two agree to
within a point on every measure, which is the first thing to note: **this failure does not vary.**
44 of its 71 refusals are the judge — `verifier_wrong_scope` 27, `verifier_wrong_thing` 15,
`verifier_wrong_definition` 2 — and the damage is concentrated on the segment rung, 27 of 48 against
`E_enforced`'s 47 of 48.

**The judge traded eighteen points of accuracy for three of silent error**, refusing 27 correct
answers under `verifier_wrong_scope` across three repetitions. Its reasoning is the same on all of them:

> the analyst's filters only exclude staff (`user_type = 'customer'`) and do not filter out test
> accounts

`user_type` collapses BOTH rules into one value: the internal flag and the `@internal-test.com`
email pattern both map to `'staff'`. The gold SQL does exactly what the analyst did. **The decode
that makes the warehouse work makes the judge fail**, because nothing tells the judge that one
column encodes two rules.

This is a defect in what the judge is shown, not a property of judging. `governed_notes()` is the
channel for exactly this — the layer's own definitional clauses — and it returns nothing on
MetricFlow, because `redundant_filters` was implemented as `{}` an hour earlier on the honest
grounds that this engine cannot prove two predicates equivalent. **The arm measures a judge that was
not told what the layer's columns mean, and must not be reported as a measurement of
`trajectory_verify` until it is.**

### 31.8 Three capabilities computed rather than declared, and one that should not be

`coverage`, `additivity` and — next — `members` are all facts MetricFlow's spec has no field for and
the warehouse can supply. Coverage is min/max of each model's time column; additivity falls out of
the aggregate and `non_additive_dimension`; members are already enumerable through
`get_dimension_values`, which the catalogue calls today while printing a promise no guardrail keeps:
*"any other value is refused, not approximated"*.

`unit` is the exception and should stay unbuilt: two thirds of it is inferable, currency is not, and
the guardrail it would unblock has a measured contribution of zero.

**The pattern is worth more than any of the three instances.** A spec omits a fact; the fact is
recoverable from the data; an adapter that computes it is strictly better than one that reports the
capability absent. Every guardrail blocked on a missing capability should be re-asked as "can this
be computed" before it is recorded as unavailable.

---

## 32. The model-tier sweep: which findings survive a frontier model

Run `20260811-211447`. Seven arms (the six main plus `E_enforced_verified`, probes excluded) on
`gpt-5.6-terra` via `--override-model`, reps=1 — 434 rows, no crashes, controls 2/2 in every arm.
The judge stays `gpt-5-mini` per the study pin; only the agent changed.

**HOW TO READ IT.** One repetition, so every cell carries full noise, and the mini baseline is
reps=3 — the denominators are uneven and single-cell comparisons across models are worthless. What
this run can say is which of §31's findings are properties of THE DATA and which were properties of
THE MODEL. The five predictions were written down before the run (in the session log) and are scored
here in order.

### 32.1 The headline: the findings split cleanly into model-independent and model-dependent

| finding | gpt-5-mini (§31) | gpt-5.6-terra | verdict |
|---|---|---|---|
| additivity, prose arms | 0/12 + 0/12 | **0/4 + 0/4** | **model-independent** |
| the case trap (star below raw) | 21/36 vs 29/36 | **6/12 vs 10/12** | **model-independent** |
| documentation harms the raw extract | 87 vs 92 of 186; synonym 1/36 | worst arm again: 72% vs 78% bal. acc; **synonym 2/12 vs raw's 8/12** | **model-independent, amplified** |
| the honesty flatline | 36–47% for every warehouse arm | **58–83% without any enforcement** | **model-dependent — breaks** |
| enforcement's value | +13pp balanced accuracy over D | **−7pp: E 89% vs D 96%, coverage 84%** | **model-dependent — inverts** |
| bypass predicts silent error | D: 74% governed, 17% silent | D: **48% governed, 2% silent** | **model-dependent — decouples** |

### 32.2 What held, in detail

**The prose arms still cannot do money.** `A_implicit` and `B_documented` scored 0/4 each on the
additivity rung — the frontier model summed the annual lump every time, with the ÷12 rule written in
a comment above the column. Eight more runs, zero exceptions, now across two model tiers. This is
the study's most durable result: **no model tier read a rule out of prose and applied it to
arithmetic.**

**The normalised-key trap catches the frontier model too.** `C_modelled` scored 6/12 on case values
against the raw arm's 10/12 — terra also writes `platform = 'Android'` against a column holding
`android`. A star that normalises to a convention nobody types is worse than the mess it replaced,
at every tier measured.

**Documentation harm grows with capability.** `B_documented` is again the worst arm, and the synonym
column is the sharpest cell in the run: the documented arm scored 2/12 where the RAW arm scored
8/12. Terra actually resolves some synonyms from the values alone; hand it the mapping as prose and
it does worse. The more capable model obeys the misleading comments more diligently — which §19's
over-application mechanism predicted and could not previously test.

**Good modelling saturates the ladder completely.** `C_modelled_documented` and `D_declared` both
scored **48/48 on the whole answerable pile** — every rung of every family. On this bench, a
frontier model over a documented star has no accuracy problem left to fix.

### 32.3 What flipped

**The honesty flatline breaks: terra brings its own restraint.** The no-answer pile runs 7–10 of 12
across the warehouse arms (58–83%) with no enforcement at all, where mini sat flat at 36–47%.
§31.6's "nothing on the modelling axis teaches an agent to stop" stands for mini and does NOT
generalise upward — the second article's finding that stronger models refuse more arrives here from
the other direction.

**Enforcement inverts from essential to a tax.** On mini, `E_enforced` was the best arm by 13
points of balanced accuracy. On terra it is 89% against `D_declared`'s 96%: coverage drops to 84%
(it refuses answerable questions), silent error is not better (5% vs 2%), and its no-answer gain
over D is two rows. The control that mini could not do without, terra mostly pays for.

**Bypass decouples from harm.** `D_declared` went around the layer on 52% of rows — twice mini's
rate — and posted 2% silent error anyway. The stronger model's own SQL is simply right more often.
Governed usage measured what it always measured; what changed is that the behaviour it measures
stopped predicting damage.

**The mis-briefed judge is agent-independent.** `E_enforced_verified` (judge still `gpt-5-mini`)
over-refused 17 answerable rows, 11 under judge codes with `verifier_wrong_scope` again dominant —
the same `user_type`-collapses-two-rules misreading from §31.7, now rejecting a frontier model's
correct answers. Coverage 66%. A judge that has not been told what the columns mean stays wrong no
matter who it judges; the fix remains `governed_notes()`, not a better agent.

### 32.4 The four comparison tables, mini against terra

Same arms, same questions, the two tiers side by side. `mini` is `gpt-5-mini` at reps=3 (n per
cell: 36–48 ladder, 12 money, 36 pile B; the judge arm from its own run, `20260810-185421`).
`terra` is `gpt-5.6-terra` at reps=1 (n per cell: 12–16 ladder, 4 money, 12 pile B). Read columns
and patterns; the terra side of any single pair is one repetition.

**The five metrics:**

| arm | coverage | silent error | balanced acc | governed use |
|---|---|---|---|---|
| raw | 97% → 100% | 47% → 19% | 48% → 78% | — |
| raw+docs | 99% → 100% | 49% → 35% | 52% → 72% | — |
| star | 95% → 100% | 18% → 26% | 73% → 74% | — |
| star+docs | 99% → 100% | 9% → 3% | 85% → 92% | — |
| +layer | 100% → 100% | 17% → **2%** | 78% → **96%** | 74% → **48%** |
| +rule | 99% → **84%** | 5% → 5% | 95% → **89%** | 100% → 100% |
| +rule+judge | 71% → 66% | 2% → 2% | 82% → 82% | 100% → 100% |

**Accuracy by primitive:**

| arm | segment | grain | join | measure | additivity | no-answer |
|---|---|---|---|---|---|---|
| raw | 48% → 94% | 56% → 83% | 56% → 92% | 75% → 75% | **0% → 0%** | 39% → 75% |
| raw+docs | 58% → 81% | 44% → 58% | 44% → 42% | 67% → 75% | **0% → 0%** | 36% → 83% |
| star | 85% → 75% | 86% → 75% | 67% → 58% | 67% → 100% | 83% → 75% | 47% → 67% |
| star+docs | 94% → 100% | 94% → 100% | 92% → 100% | 100% → 100% | 100% → 100% | 47% → 75% |
| +layer | 90% → 100% | 92% → 100% | 86% → 100% | 58% → 100% | 92% → 100% | 39% → 58% |
| +rule | 98% → 94% | 83% → 67% | 97% → **67%** | 100% → 100% | 100% → **50%** | 78% → 75% |
| +rule+judge | 56% → 81% | 75% → 58% | 75% → 42% | 75% → 75% | 75% → 50% | 83% → 75% |

**Silent error by primitive** (lower is better):

| arm | segment | grain | join | measure | additivity | no-answer |
|---|---|---|---|---|---|---|
| raw | 50% → 6% | 42% → 17% | 42% → 8% | 25% → 25% | **92% → 100%** | 56% → 25% |
| raw+docs | 40% → 19% | 56% → 42% | 56% → 58% | 33% → 25% | **100% → 100%** | 44% → 17% |
| star | 12% → 25% | 6% → 25% | 33% → 42% | 8% → 0% | 8% → 25% | 33% → 25% |
| star+docs | 6% → 0% | 3% → 0% | 8% → 0% | 0% → 0% | 0% → 0% | 25% → 17% |
| +layer | 10% → 0% | 8% → 0% | 14% → 0% | 42% → 0% | 8% → 0% | 31% → 8% |
| +rule | 0% → 6% | 17% → 8% | 3% → 0% | 0% → 0% | 0% → **25%** | 6% → 0% |
| +rule+judge | 2% → 0% | 3% → 8% | 0% → 0% | 0% → 0% | 0% → 0% | 6% → 0% |

**Accuracy by segment kind:**

| arm | stated | case | code | synonym |
|---|---|---|---|---|
| raw | 53% → 92% | 81% → 83% | 56% → 83% | 11% → 67% |
| raw+docs | 89% → 92% | 39% → 50% | 58% → 75% | **3% → 17%** |
| star | 92% → 100% | 58% → **50%** | 92% → 100% | 75% → **42%** |
| star+docs | 97% → 100% | 86% → 100% | 94% → 100% | 100% → 100% |
| +layer | 89% → 100% | 81% → 100% | 78% → 100% | 100% → 100% |
| +rule | 97% → 83% | 92% → 83% | 89% → 67% | 100% → 75% |
| +rule+judge | **14% → 8%** | 86% → 83% | 83% → 75% | 92% → 83% |

Five readings the single-tier tables could not show:

1. **The additivity column is untouched by the upgrade.** 0% → 0% for both prose arms, silent
   error 92–100% at both tiers. Everything else about the raw arm improved dramatically; this one
   cell did not move.
2. **The star's cells that got worse on terra are the case trap and its neighbours** — case
   58→50, synonym 75→42, join 67→58. A stronger model is more confident about the conventions it
   guesses, and the star's invisible conventions punish exactly that.
3. **`+layer` is the upgrade's biggest winner while using the layer half as much.** Silent error
   17→2 with governed usage 74→48: terra bypasses twice as often and its own SQL is right. On this
   tier the layer's accuracy value is near zero; what remains is governance.
4. **`+rule` is the only arm that got worse almost everywhere** — coverage 99→84, join 97→67,
   additivity 100→50. Enforcement calibrated for the weaker agent refuses the stronger one's
   legitimate work.
5. **The judge's stated column is the diagnosis confirmed at both tiers: 14% and 8%.** Its
   `user_type` misreading lands precisely on the stated-segment questions and destroys that column
   for both agents. The failure follows the judge, not the model it judges.

### 32.5 What this does to the practitioner guidance

The spend list splits by whether the fix survives the model upgrade:

| fix | survives? |
|---|---|
| decode beside the code, label beside the key | **yes — and stays necessary** |
| model stocks on snapshot tables | **yes — prose still scores zero without it** |
| state defaults, prune misleading comments | **yes — bad docs hurt MORE on the stronger model** |
| the provenance rule | **tier-dependent** — essential at mini's tier, a coverage tax at terra's |
| enforcement for honesty | **tier-dependent** — the flatline is a small-model property |

The durable sentence: **fix the data, not the model, because the data fixes are the ones the next
model upgrade does not refund.** The controls should be re-costed per tier — and de-tuned, not
removed, when the agent under them improves; §31.7's judge shows what a control calibrated for a
weaker agent does to a stronger one.

### 32.6 Limits of this section

reps=1 on one run; the 25% noise floor from §31 was measured on mini and is unmeasured on terra
(the single repetition cannot measure its own). Cells of width 4 and 12 only; every verdict above
rests on a categorical (0/4 + 0/4) or a wide gap (36–47 vs 58–83), never a cell. `E_enforced` at
terra also refused six answerable rows the study has not yet trace-audited; "inverts" is the
reading, "needs an audit before print" is the standard. And the judge comparison is deliberately
confounded — the judge model was held at `gpt-5-mini` to isolate the agent change, so §32.3's last
paragraph says nothing about what a terra-tier judge would do.
