# Sketch — handing the judge's veto back instead of serving it as a refusal

Not built. A design to argue with before anything is written.

## The failure it targets

Study 01, arm `A_absent`. Two governed metrics measure the same thing over the same rows at the
same grain and differ only in which population they count. The arm removes the fact that says which
is which, and leaves both metrics in the catalogue.

Every wrong answer, across three independent runs:

| question | picked | answered |
|---|---|---|
| customers, last week | `value_moments` | 3,785 |
| excluding staff, June | `value_moments` | 64,257 / 15,329 |

Six observations, one metric, zero variation. **The right metric was reachable every time.** This
is a wrong choice among available options — which is the shape a repair loop can fix, and the shape
`F_enforced` in study 05 does *not* have, where the correct answer needed a table the catalogue
never modelled.

## What exists today, and what does not

**`Protocol.repair`** hands back a *citation that names nothing* — "you cited r7, there is no r7."
Its own docstring is explicit: it "cannot stop a wrong number, only an unaccountable one." Whether a
claim is mislabelled or unsupported is deliberately left to the audit, *where they are measured
rather than corrected away*.

**`trajectory_verify`** (R9) asks whether the metric actually answers the question, and on a
mismatch returns a terminal verdict. The answer becomes a refusal immediately. No hand-back.

So the path being proposed is a third one, and it deliberately crosses the line the existing repair
respects: it corrects an ANALYSIS fault, not a bookkeeping fault. That is the main thing to argue
about before building it.

## The design

One bounded hand-back, gated by its own flag so a cell can say which of the two moved a number:

```yaml
agent:
  guardrails: 9
  protocol:
    claims: true
    repair: true          # existing — a citation naming nothing
  verify_repair: once     # NEW — the judge's veto is handed back, at most once
```

On a veto, instead of returning the refusal:

```
Your answer was not accepted: the metric you used measures a different THING from the one
the question asks about. Reconsider and answer again. This is your only retry.
```

Then the run continues, the agent answers again, and the second answer is judged normally. A second
veto is terminal.

## Four constraints, and three of them are about not cheating

**The hint must not name the right metric.** If the harness says "use `real_value_moments`", it has
done the work and the study measures the harness. The hand-back carries the judge's CATEGORY —
`thing`, `kind`, `scope`, `definition`, `segment` — and never its prose, because the prose is
free-form and will eventually contain the answer.

**Bounded at one.** Same as citation repair. An unbounded loop turns a refusal into a wandering
search and makes latency a treatment.

**A repeated answer is not a repair.** If the second answer carries the same value, accept the first
veto rather than judging again. Otherwise an agent that re-asserts gets two chances at a noisy judge.

**It must be counted, not absorbed.** Every hand-back is recorded, the way `Answer.repairs` already
records citation repairs. An arm that answers correctly only after being told it was wrong has not
performed as well as one that was right first time, and a single "correct" column that hides the
difference would say it had.

## What it would measure, and the honest risk

The interesting comparison is **model it, or catch it**:

| | `A_absent` | `A_absent` + verify_repair |
|---|---|---|
| wrong numbers served | 6 of 6 | ? |
| correct after one hand-back | — | ? |

We already have one result where enforcement beat modelling — study 04's provenance check caught a
semi-additive roll-up that neither a description nor a declared field prevented. This would be a
second, on a different primitive, and the two together would be the strongest thing this programme
has: *some faults are cheaper to catch than to model, and here is which.*

**The risk is that it measures the judge.** `trajectory_verify` is an LLM, and study 05 showed it
refusing 8 of 15 — including questions the agent had answered correctly. A repair loop built on a
noisy judge inherits that noise on both sides: false vetoes waste a retry, and missed vetoes never
trigger one. Before this is worth building, the judge's own false-positive rate on study 01's
questions needs measuring, which is a smaller and duller job that should come first.

## Where it does not belong

Study 05's `F_enforced`. Its refusals are on questions with no governed metric — `reminder_open_rate`
is a share, nothing counts habits — so the hint would send the agent looking for a better metric
that does not exist. The failure there is not a bad pick; it is the judge assuming a metric must be
the answer.

## Order

1. Measure `trajectory_verify`'s false-positive rate on study 01's four questions. If it vetoes
   correct answers often, stop here.
2. Add the hand-back behind `verify_repair`, with the category-only hint and the repeated-answer
   guard.
3. Run `A_absent` with and without it. The prediction is that it converts confidently wrong numbers
   into correct answers, because the right metric was always one step away.
4. Report repairs as their own column. Right-first-time and right-after-a-hint are different
   products, and a customer buying a guardrail should see which one they are getting.
