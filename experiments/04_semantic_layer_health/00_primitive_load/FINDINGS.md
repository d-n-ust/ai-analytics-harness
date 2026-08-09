# Study 00 — the load ladder: two rebuilds, and a frontier model that does not break

Three runs. The first two were instrument, the third is the result.

| run | model | score | what it was |
|---|---|---|---|
| `20260809-192243` | gpt-5-mini | 40/60 | first build — control broken, ladder on the floor |
| `20260809-201725` | gpt-5-mini | 48/60 | ladder rebased — exposed an under-specified comment |
| `20260809-202056` | gpt-5-mini | 55/60 | **the readable run** |
| `20260809-202236` | gpt-5.6-terra | **60/60** | **the readable run, one tier up** |

**The answer: on `gpt-5-mini` the gap does widen with load. On `gpt-5.6-terra` there is no gap at
any depth up to four primitives.** Sections 1–5 are the instrument history and are kept because two
of the three defects were in our own documentation rather than in the questions. Section 6 is the
result.

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
