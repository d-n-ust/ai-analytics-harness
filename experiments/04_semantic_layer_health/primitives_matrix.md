# The primitives matrix — what an agent needs, and the cheapest way to give it

A research spine, not a result. It names the things an analytical question forces an agent to
resolve, the interventions available for each, and which combinations we have actually measured.

**The claim it is built to test.** There is no single answer to "how do I make my data model
agent-ready". The right intervention differs by primitive, and it is not monotone in cost — for at
least one primitive the cheap fix works and the expensive one does not, and for at least one the
middle option makes things worse.

---

## The rows: nine primitives

What a question forces the agent to resolve. Named with the terms the field already uses, so a
practitioner recognises them rather than learning our vocabulary.

| # | primitive | the question it answers | industry name |
|---|---|---|---|
| 1 | entity | which thing | entity (MetricFlow), fact/dimension (Kimball) |
| 2 | segment | which ones of it | segment (Cube), metric `filter` (MetricFlow) |
| 3 | measure + aggregation | how it is counted | measure + `agg` |
| 4 | grain | at what level — "one row is one ___" | grain |
| 5 | additivity | whether periods may be added | additive / semi-additive / non-additive |
| 6 | join path | how two entities connect | join keys, conformed dimensions |
| 7 | composition | how measures combine — ratio, share, delta | derived metrics, metric tree |
| 8 | causality | why a number moved | — |
| 9 | coverage | whether it can be known at all | coverage window, freshness |

A tenth row is implied by the data and not yet named: **domain facts** — things true of the business
that are in no table at all (what a plan includes, which channel is a test integration). The
grounding ladder's `knowledge` tier measures it, and verified examples moved it from 4/25 to 25/25.
It is listed in the matrix below but left out of the numbered set until it has a definition sharper
than "everything else".

**Measure and aggregation stay one row** until something separates them. They fail together — the
agent picks a wrong metric, not a wrong aggregate on a right metric — and a row that cannot be
tested costs more than it explains.

**Why these and not the old tiers.** `lookup`, `filtered`, `metric` were never arbitrary
categories: they are how many primitives a question forces the agent to resolve. That is why they
unlock at different rungs. Stated as primitives, a question carries a requirement profile rather
than a position on a ladder — which matters because the ladder's implied total order breaks as soon
as joins are involved.

---

## The columns: five interventions

Each is a real thing a team can do, in increasing cost.

| | intervention | what it means | typical cost |
|---|---|---|---|
| **A** | implicit | the fact is true in the data and stated nowhere | zero |
| **B** | documented | a table or column comment, a metric description | hours |
| **C** | modelled | a warehouse object makes it structurally true — a view, a pre-joined mart, a table named for its grain | days |
| **D** | declared | a typed construct in the semantic layer | a modelling project |
| **E** | enforced | a runtime check that refuses when the fact is violated | engineering, not modelling |

**Column E is not in the usual advice, and it earns its place.** Study 04 found a primitive where B
and D both failed and E worked. Any framework that stops at "declare it in your semantic layer"
would have got that case wrong.

---

## The matrix

Each cell carries an evidence class. **measured** — a controlled comparison in this repo.
**bundled** — a real result, but the step changed more than one primitive, so it cannot be
attributed to this row alone. **argued** — a reasoned position with no run behind it.
**open** — untested.

| primitive | B documented | C modelled | D declared | E enforced |
|---|---|---|---|---|
| 1 entity | open | **works** · bundled | open | open |
| 2 segment | **works** · measured | **harmful** · argued | **no better than B** · measured | open |
| 3 measure + agg | open | open | **works** · measured | open |
| 4 grain | open | open | open | open |
| 5 additivity | **fails** · measured | open | **fails** · measured | **works** · measured |
| 6 join path | open | **works** · bundled | open | open |
| 7 composition | open | open | open | open |
| 8 causality | open | open | **works** · measured | open |
| 9 coverage | open | open | **works** · measured | open |
| *(domain facts)* | **works** · measured | open | open | open |

Twelve cells of forty-five carry anything at all, and three of those are bundled or argued. The
empty cells mean untested, not unimportant.

---

## What the filled cells say

### The answer differs by row, and not in order of cost

| primitive | what wins |
|---|---|
| join path | **modelled** — a pre-joined mart |
| segment | **documented** — a sentence was as good as a declaration, twice |
| measure + aggregation | **declared** — a metric definition |
| additivity | **enforced** — documenting and declaring both failed |

Four primitives, four different answers, spanning every column. This is the finding the matrix
exists to make legible, and it is the reason "just build a semantic layer" is not an answer.

### Segment: the middle column is the defect

Materialising a segment as its own warehouse object is precisely `real_value_moments` sitting
beside `value_moments` — one measure, two populations, two metric names. That is the defect studies
01 and 02 were built to study, not a repair for it.

So for this row the intervention one step up the cost ladder plausibly makes things worse. Marked
**argued** rather than measured: no run compares "materialised segment" against "segment as an
argument" directly, because study 01's repair arm *removes* the twin rather than adding one.

### Additivity: the only row where enforcement beat modelling

At R7 the trap failed 0/3 in all three arms — including the arm rendering
`additivity: NOT additive over time — summing periods double-counts`, which was verified present in
the delivered context. The refusal came from `governed_numbers`, which requires a number to trace to
a governed result; a figure obtained by adding seven daily rows traces to none.

**Requiring provenance prevents semi-additive roll-ups without knowing anything about additivity.**
At R6, with that check removed, the declared arm answered 2012 against a true 886.

### Grain is empty, and it sits upstream of two rows that are not

`agg_active_days` has grain *one row is one user-day*, and nothing in the warehouse says so. The
additivity failure is summing user-days into user-weeks. The segment failure is which users a row
stands for. Both are grain questions wearing other clothes.

---

## Method for filling a cell

1. Pick a primitive and a column.
2. Write questions whose answer depends on that primitive and pair them with controls where the
   same operation is legal, so a degenerate strategy cannot score.
3. Arms differ only in the intervention. The numbers must not move — check before spending.
4. Report against the measured **13% noise floor** (see `FINDINGS.md`). At five questions the
   smallest detectable difference is roughly 59 points, so a five-question run is a pilot that
   establishes direction and question quality, never a result.

**Column C will fight the current harness.** Materialising a fact usually adds a warehouse object,
which trips the candidate-count guard and can move the numbers. C-column studies need a different
invariant than the patch-based ones — closer to the MetricFlow port's `layer_dir` than to an arm
patch.

---

## Priority

1. **Grain, column B.** Empty row, upstream of two measured failures, and the intervention is one
   table comment — the cheapest cell in the matrix. If a grain sentence fixes the roll-up that a
   rendered `additivity` field could not, that is the most practical and most surprising result
   available to us.
2. **Additivity, column C.** Materialise a weekly table so the addition never has to happen. It
   completes the only row with three cells already filled.
3. **Join path, columns B and D.** The one bundled win worth separating: does declaring join keys
   do what a pre-joined mart does, or is the mart the whole effect?
4. **Segment, column C.** Turn the argued cell into a measured one, since it is the matrix's most
   counter-intuitive claim.

Everything else waits. Ten rows times five columns is a multi-year programme; the value is in the
frame plus the handful of cells that contradict the obvious advice.

---

## Provenance and caveats

| cell | source | caveat |
|---|---|---|
| entity C, join path C | grounding ladder r1→r2 | **bundled** — rung 2 changes naming, shape and pre-joining at once |
| measure D | grounding ladder r2→r3, metric tier: mini 2/25 → 19/25 | single-variable step, but **5 questions per tier** |
| domain facts B | r3→r4, knowledge tier: gpt 4/25 → 25/25 | single-variable (examples only); 5 questions |
| causality D | r5→r6, diagnostic tier: gpt 0/25 → 18/25 | single-variable (tree only); 5 questions |
| coverage D | R3 coverage guardrail | mechanism, not a between-arm comparison |
| segment B, D | studies 01, 01__mf, 02 | 2 discriminating items in 01, 1 in 02 |
| additivity B, D, E | study 04, runs `20260808-131841` (R7) and `-132436` (R6) | 1 trap question |
| segment C | reasoning from study 01's design | **argued, not measured** |

**The tier-level numbers throughout come from 5 questions per tier**, 5 reps, 2 models. Large
effects such as metric-tier 2/25 → 19/25 survive that; fine distinctions between adjacent tiers do
not, and are stated here as direction only.
