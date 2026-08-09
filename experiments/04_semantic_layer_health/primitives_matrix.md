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

## What each column means for each row

The column *question* is fixed for every row. The **artifact** that answers it is specific to the
primitive. Without this table each study has to reinvent the definition, and two studies then use
the same letter for different things.

Column A is the same everywhere — the fact is true in the data and stated nowhere — so it is left
out here.

| row | B documented | C modelled | D declared | E enforced |
|---|---|---|---|---|
| 1 entity | a comment on `evt` stating what one row is and what the `kind` codes mean | `fct_value_moments` — the kinds are already split, so the table name is the entity | `entity:` on the metric | R9 thing-match: does the metric measure the thing the question asks about |
| 2 segment | the metric description states who is counted | `dim_users.is_internal` — **constant**: present and identical in every arm | `governance.segments` — a named, reusable segment | R9 scope-match: the population used against the population asked for |
| 3 measure + agg | the description states what is summed, and of what | a pre-aggregated table whose column is the measure — `agg_active_days.moments` | `agg:` | a check that the aggregation matches the question |
| 4 grain | a comment: "one row is one user-day" | the primary key — a declared key is a machine-readable grain statement | `time_column:` and the grain field | refuse a group-by finer than the grain |
| 5 additivity | `NOT additive over time` in the description | expose only the correctly rolled-up table, so there is no daily column to sum | `additive_over_time:` | `governed_numbers` — a number must trace to one governed result |
| 6 join path | a comment naming the join key and its cardinality | a pre-joined mart — the join is already done | declared entities and join keys | refuse when a join multiplies rows |
| 7 composition | the description states the metric is a share, not a count | a view materialising the ratio at its correct grain | a derived metric with numerator and denominator declared | refuse an average of a ratio |
| 8 causality | the description states the number is correlational | **absent** — see below | a field marking the metric diagnostic rather than causal | refuse causal wording with no experiment behind it |
| 9 coverage | a comment stating the coverage window and what is not tracked | an explicit coverage or freshness table | declared coverage bounds on the metric | refuse a period outside the declared bounds |
| *(domain facts)* | the description carries the fact | a reference table — plan to features, channel to type | verified examples in the knowledge tier | refuse when the answer depends on an unmodelled domain fact |

**Documentation is a modifier, not only a column.** Any shape can be documented or not. Column B is
column A with documentation added, and `C_modelled_documented` is column C with the same addition.
There is no `D_declared_documented`, because in a semantic layer the description is a field — column
D already contains its documentation.

**Column C is the hardest to fill.** It requires the shape of the warehouse to carry the fact, and
additivity, causality and coverage are statements *about* data rather than statements *of* it.
Causality has no artifact at all: no warehouse shape prevents a correlational number from being read
as a cause. The other two have indirect artifacts, listed above.

---

## The matrix

Each cell carries an evidence class.

| class | meaning |
|---|---|
| **measured** | a controlled comparison in this repo |
| **bundled** | a real result, but the step changed more than one primitive, so it cannot be attributed to this row alone |
| **argued** | a reasoned position with no run behind it |
| **open** | untested, and testable |
| **constant** | the artifact exists and is identical in every arm, so this study cannot vary it |
| **absent** | no artifact of this kind exists for this primitive |

The last two are not weaker forms of **open**. **Open** means someone should run it; **constant**
and **absent** mean there is nothing to run.

| primitive | B documented | C modelled | D declared | E enforced |
|---|---|---|---|---|
| 1 entity | open | **works** · bundled | open | open |
| 2 segment | **works** · measured | *constant* | **no better than B** · measured | open |
| 3 measure + agg | open | open | **works** · measured | open |
| 4 grain | open | open | open | open |
| 5 additivity | **fails** · measured | open | **fails** · measured | **works** · measured |
| 6 join path | open | **works** · bundled | open | open |
| 7 composition | open | open | open | open |
| 8 causality | open | *absent* | **works** · measured | open |
| 9 coverage | open | open | **works** · measured | open |
| *(domain facts)* | **works** · measured | open | open | open |

Twelve of the forty cells carry evidence, and three of those are bundled or argued. Two more are
closed rather than untested: segment/C is *constant* and causality/C is *absent*. The rest mean
untested, not unimportant.

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

### Segment: the middle column is held constant, not empty

Column C asks whether the shape of the warehouse carries the fact. For a population that shape is a
filterable attribute on a conformed dimension, and `warehouse/star.sql:39` already provides one:

```sql
((coalesce(internal, 0) = 1) OR (lower(email) LIKE '%@internal-test.com')) AS is_internal
```

One resolved boolean, never null, carried into `fct_value_moments` at lines 136 and 160. Every arm
of study 02 runs at rung 3 over this star, so all of them hold column C at its best value. The row
varies B and D against a fixed C.

Making C vary would mean removing an attribute from a conformed dimension. That measures a damaged
star, not a segment, and the result would be uninteresting because it is already known.

**An earlier version of this section marked the cell harmful**, on the grounds that materialising a
segment as its own object produces `real_value_moments` beside `value_moments`. That object is a
metric in the semantic layer, not a warehouse table, so it belongs to column D. The harm claim is
withdrawn.

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
