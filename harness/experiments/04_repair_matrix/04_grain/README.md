# Study 04 — grain: what one row stands for

Findings are in `FINDINGS.md`; the practitioner summary is in `PRACTITIONER-NOTES.md`.

**Row 4 of `../primitives_matrix.md`, and it is still empty.** Two runs produced two nulls. What the
study established is about item design rather than about grain, and that is recorded rather than
dressed up.

## The defect

```
fct_subscriptions      457 rows        one row is one subscription TERM
                       413 people      43 users hold more than one
```

Counting rows overstates subscribers by 10.7% — outside the 2% tolerance, and small enough to look
like a real number. Nothing in the warehouse says so.

## Why the row matters

Grain sits upstream of two rows that are already measured and already failing. `../05_additivity`'s
trap is summing user-days into user-weeks, which is a grain fault wearing an additivity coat.
`../02_segment`'s is which users a row stands for.

## The arms

| arm | the fact lives |
|---|---|
| `A_implicit` | every table says what it holds; none says what one row is |
| `B_documented` | one sentence per fact table: *one row is one subscription term* |
| `C_modelled` | the table is named for its grain — `fct_subscription_terms`, byte-identical data |
| `D_declared` | a governed metric whose `agg` resolves the grain, so the caller never sees a row |
| `E_enforced` | R9 thing-match on top of D |

`C_modelled_documented` is declared `OPEN` in `study.yml` with its reason.

## What the two runs found

**Run 1 — one question, and it did not discriminate.** Nine of nine SQL attempts wrote
`COUNT(DISTINCT user_id)` as their first query. The question said *"how many **users**"*, so the
aggregation followed from the noun and no knowledge of the grain was needed.

**Run 2 — three questions, and the discriminating one measured something else.** Five of nine misses
divided by 2,500 signups instead of 413 subscribers: a disagreement about what "subscriber" denotes,
not about what a row stands for.

**The rule this establishes:** an item is a grain item only if the correct aggregation **cannot be
inferred from the question's noun.**

## Where the trap actually lives

The same model handles the subscription-term grain unprompted, 9 of 9, and fails the user-day grain
0 of 9 in `../05_additivity`. A user holding two subscription terms is a familiar shape; a user
appearing on seven daily rows and counting once for the week is not. The next item belongs on the
user-day table, which means exposing it at rung 2.

## Running it

```
./bench study 04_grain --reps 3
./bench study 04_grain --mock --reps 1
```
