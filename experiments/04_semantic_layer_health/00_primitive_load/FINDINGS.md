# Study 00 — the load ladder, run once, and why it is not yet readable

Run `20260809-192455-00_primitive_load`: five questions, four arms, three repetitions, `gpt-5-mini`
at minimal reasoning, R1. **The frontier-model half of the plan was not run**, because the trace
audit found two defects in the instrument first.

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
| per-item results | `20260809-192455-00_primitive_load/run.json` |
| the three control queries | the same run, `A_implicit`, `pl_control_spend`, all three reps, `steps` |
| the invented event mapping | the same run, `A_implicit`, `pl_l3_grain`, rep 1 |
| `01_entity`'s per-item A scores | `20260808-232437-01_entity` |
