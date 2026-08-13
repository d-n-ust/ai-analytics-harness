# Study 05 — additivity: whether periods may be added

Row 5 of `../primitives_matrix.md`. The findings are in `FINDINGS.md`; the practitioner summary is
in `PRACTITIONER-NOTES.md`.

## The defect

```
active_users:  agg "count(distinct user_id)"   base agg_active_days  (one row = one user-day)
```

A distinct count does not compose across periods. A user active on Monday and Tuesday is **one**
weekly active user and **two** daily ones. Asking for last week at `time_grain=day` and adding the
seven rows gives **2,012** where the governed weekly figure is **886** — a 2.27× overstatement,
reached through two entirely governed calls, with no invented SQL anywhere.

## What makes it the sharpest test here

**The layer already knows.** `SemanticLayer.additivity()` derives the answer from the aggregate for
every metric and gets every one right: a distinct count is semi-additive whether or not anyone
annotated it. The fact is computed, correct, and never rendered.

So the defect is not a missing fact. It is a known fact that never reaches the point of use.

It is also the row where structure ought to beat a description. Additivity is a property of the
measure, derived once and true everywhere; a segment is a sentence the model must read, remember and
apply.

## The arms

| arm | the fact lives |
|---|---|
| `A_implicit` | nowhere |
| `B_documented` | in the descriptions of the metrics the traps use |
| `D_declared` | in `additive_over_time:`, a fixed slot on every metric |

`C_modelled` and `E_enforced` have no arm. `study.yml` says why: the modelled repair would be to
expose only the correctly rolled-up table, which is untested; the enforced result was measured by
moving the whole study between two guardrail cells rather than by adding an arm.

## The questions

| id | shape |
|---|---|
| `a_add_actives_week` | **the trap** — daily breakdown plus a weekly total, on a distinct count |
| `a_add_frequency_week` | **the trap** — the same shape on a ratio, non-additive in every direction |
| `a_add_moments_week` | control — the same shape on a measure that genuinely composes |
| `a_add_spend_quarter` | control — a second legal roll-up, different grain, different metric family |
| `a_add_actives_plain` | anchor — the trap's metric with the grain removed from the question |

The controls are the important half. An arm that starts refusing legal roll-ups has learned "never
add" rather than "add what composes", and its win on the traps would be worthless.

## The guardrail cell, and why it is R6

Two guardrails mask the treatment:

- **R8** `output_validation` reads additivity and refuses the roll-up outright. Running there would
  measure the guardrail.
- **R7** `governed_numbers` makes the model declare which governed result its number came from. A
  figure obtained by adding seven daily rows traces to none, so it is refused — without the
  guardrail knowing anything about additivity.

R6 keeps coverage, tool restriction, member resolution and transparency, and drops the provenance
requirement. The arms can then be separated by the numbers themselves.

## Running it

```
./bench study 05_additivity --reps 3
./bench study 05_additivity --arms D_declared --only a_add_actives_week --reps 1
```
