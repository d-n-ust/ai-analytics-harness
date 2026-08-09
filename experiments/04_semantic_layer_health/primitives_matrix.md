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
| 1 entity | **works** · measured | **works** · measured | **works** · measured | **no better than B** · measured |
| 2 segment | **works** · measured | *constant* | **works, confounded** · measured | open |
| 3 measure + agg | open | open | **works** · measured | open |
| 4 grain | open | open | open | open |
| 5 additivity | **fails** · measured | open | **fails** · measured | **works** · measured |
| 6 join path | open | **works** · bundled | open | open |
| 7 composition | open | open | open | open |
| 8 causality | open | *absent* | **works** · measured | open |
| 9 coverage | open | open | **works** · measured | open |
| *(domain facts)* | **works** · measured | open | open | open |

Fifteen of the forty cells carry evidence, and two of those are bundled. Two more are closed rather
than untested: segment/C is *constant* and causality/C is *absent*. The rest mean untested, not
unimportant.

**EVERY CELL IS CONDITIONAL ON ONE MODEL, and after 2026-08-09 that is a claim rather than a
gap.** Every number in this matrix was measured on `gpt-5-mini` at minimal reasoning. `01_entity` has
since been swept across three tiers, and the row it fills reads differently at each:

| | gpt-5.4-mini | gpt-5-mini | gpt-5.6-terra |
|---|---|---|---|
| entity, A_implicit — nothing documented | 12/15 | 10/15 | **15/15** |
| entity, B_documented — one sentence per table | 15/15 | 15/15 | 15/15 |
| **the gap this row reports** | **3** | **5** | **0** |

So `1 entity · B documented` should be read as *works on gpt-5-mini*, and on the frontier model the
same intervention buys nothing on the same questions. A cell is a statement about a primitive, an
intervention **and a model tier**, and only the third is currently unstated. See `FINDINGS.md` §3.4.

A second result from that sweep bears directly on column D: the share of governed rows that never
called `list_metrics` rises with model strength — 7/30, 8/30, **13/30**. Column D's score is
partly a measurement of whether the layer was consulted at all. See `FINDINGS.md` §3.5.

**Row 1 and row 2/D were refreshed on 2026-08-09** from the stored runs. Row 1 had read `open` in
three columns although `01_entity` had run all six arms; row 2/D had read *no better than B* from a
superseded run. Both are now read from `01_entity/FINDINGS.md` and `02_segment/FINDINGS.md`.

---

## What the filled cells say

### The answer differs by row, and not in order of cost

| primitive | what wins | the cheapest thing that works |
|---|---|---|
| join path | **modelled** — a pre-joined mart | days of modelling |
| entity | **documented** — one sentence per table | an afternoon of `COMMENT ON` |
| segment | **declared**, but confounded — see below | a description in the business's own words |
| measure + aggregation | **declared** — a metric definition | a modelling project |
| additivity | **enforced** — documenting and declaring both failed | a runtime check |

Five primitives, four different answers, spanning every column. This is the finding the matrix
exists to make legible, and it is the reason "just build a semantic layer" is not an answer.

### Entity: the cheapest column closes the whole gap

| arm | correct | confidently wrong |
|---|---|---|
| A_implicit | 10/15 | **5** |
| B_documented | **15/15** | 0 |
| C_modelled | 14/15 | 1 |
| C_modelled_documented | 14/15 | 1 |
| D_declared | **15/15** | 0 |
| E_enforced | 14/15 | 0 |

One sentence per table takes 10/15 to 15/15 and removes every silent error. Nothing above it
improves on that, so B through E are marked **works** and the honest claim is about A against
everything else — the set has a ceiling.

The 2×2 that motivated six arms is inconclusive at this size: documenting the messy tables helped
(10 → 15); documenting the star did not (14 → 14). That is the predicted direction — conformed
naming substitutes for documentation — and it is not yet a result.

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
At R6, with that check removed, the declared arm answered 2012 against a true 886 — on all three
repetitions, while rendering `additivity: NOT additive over time` in its own catalogue.

**What "works" means in this cell, precisely.** No arm at either guardrail cell ever answered 886.
The check converts a silent error into a visible abstention; it does not produce the right answer.
That is a large benefit and it is not the same as being right, so a write-up must say which one it
is claiming. See `05_additivity/FINDINGS.md` §3.

### Segment: the declared cell wins on one item, and that item is the confound

| arm | correct | the two discriminating questions |
|---|---|---|
| A_implicit | 18/24 | 0/3 · 0/3 |
| B_documented | 21/24 | **0/3** · 3/3 |
| D_declared | 23/24 | **3/3** · 3/3 |

Six of eight questions are flat across all arms. A beats nothing; B beats A on one question; D beats
B on one different question. **A five-point spread produced by two items is not a five-point
effect.**

The two questions differ in one word. *"Excluding staff and test accounts"* names the exclusion in
terms that map onto a dimension the agent can see, and `B_documented`'s descriptions use those same
words. *"Our customers"* maps onto nothing — and `D_declared` is the only arm whose segment lists
`customers` as a synonym.

So the mechanism visible in the data is **lexical, not structural**: what repaired the second
question was that somebody wrote down what "customers" means. The vocabulary confound is not an
objection to the result; it is the result. The cell is marked **works, confounded** until
`D_declared_neutral` separates the two. See `02_segment/FINDINGS.md`.

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

1. **Segment: `D_declared_neutral` and `B_documented_minus`.** Twenty lines each. Row 2 is the row
   with the most evidence and the least attributable evidence; these two arms separate structure
   from wording and equalise the candidate count. Nothing else in the matrix is this cheap.
2. **Grain, column B.** Empty row, upstream of two measured failures, and the intervention is one
   table comment. If a grain sentence fixes the roll-up that a rendered `additivity` field could
   not, that is the most practical and most surprising result available to us.
3. **Additivity, column C.** Materialise a weekly table so the addition never has to happen. It
   completes the only row with three cells already filled.
4. **Join path, columns B and D.** The one bundled win worth separating: does declaring join keys
   do what a pre-joined mart does, or is the mart the whole effect?

**Item count, not arm count, is the binding constraint.** Every study here has two discriminating
questions or fewer. More arms and more repetitions buy nothing — repetitions measure noise *within*
an item, while the effect lives *across* items.

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
| entity B, C, D, E | `01_entity`, run `20260808-232437` | 2 discriminating items of 5; ceiling above B |
| segment B, D | `02_segment` `20260809-121926`; `02_segment__mf` `20260809-124835` | **2 discriminating items**, and D's single win is on the item its synonyms contain |
| additivity B, D, E | `05_additivity`, runs `20260808-131841` (R7) and `-132436` (R6) | 1 trap question; E refuses rather than answers |
| segment C | present and identical in every arm | **constant, not measurable in this row** |

**The tier-level numbers throughout come from 5 questions per tier**, 5 reps, 2 models. Large
effects such as metric-tier 2/25 → 19/25 survive that; fine distinctions between adjacent tiers do
not, and are stated here as direction only.
