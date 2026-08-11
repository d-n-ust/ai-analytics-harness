# Experiment 4 — findings so far

What the runs in this folder have actually established, and what they have not. Every number here
is computed from a stored run under `results/experiments/`; nothing is quoted from memory.

Read this before quoting any figure from a study README. Several results that looked decisive when
first produced did not survive repetition, and the reasons are more useful than the results were.

---

## 1. The measured noise floor is 13%

The single most important number in this folder. Repeated runs on **byte-identical input** disagree
with themselves.

| study | engine | design | cells that disagreed with themselves |
|---|---|---|---|
| 01 segment in metric name | dbt MetricFlow | 3 independent runs, same config | 2 of 16 — **12%** |
| 02 segment in aggregate | harness | 3 reps in one run | 2 of 15 — **13%** |
| 03 catalogue format | harness | 3 reps in one run | 2 of 15 — **13%** |
| **pooled** | | | **6 of 46 — 13%** |

A "cell" is one arm answering one question. If the agent were stable, every cell would score 3/3 or
0/3.

Three different question sets, two different semantic-layer engines, three different treatments,
and the rate is the same. This is a property of the agent, not of any one study.

**It cannot be turned down.** The agent runs on `gpt-5-mini` with `reasoning_effort=minimal`.
Reasoning models fix `temperature` and `top_p` at 1.0 and reject overrides, so the sampling that
produces this variation is not a setting anyone chose. `seed` is best-effort and carries a
deprecation marker; no provider offers a reproducibility guarantee.

### The noise is not spread evenly

In study 01 both unstable cells are the **same question** — `p_pop_customers_week`. In study 03
both are Germany questions. In study 02 both are threshold questions.

Instability concentrates on borderline items rather than dusting itself uniformly across the set.
Two consequences: a per-item pass **rate** carries much more information than a per-item verdict,
and the unstable items are identifiable, so they can be reported rather than averaged away.

---

## 2. Therefore: no between-arm result in this folder is publishable

With 5 questions and 3 repetitions, the smallest difference this design can detect at 80% power is
roughly **59 to 63 percentage points** (two independent calculations from the paired sample-size
literature agree). The differences we observe are 7 to 13 points.

| design | smallest detectable gap |
|---|---|
| 5 questions, 3 reps — what every study here uses | 59–63 pp |
| 30 questions | ~26 pp |
| 80 questions | ~15 pp |
| 150 questions | ~11 pp |

**Repetitions do not fix this.** The variance is `ω²/n + (σ²_A+σ²_B)/(nK)`. At a fixed total number
of runs the second term is constant, so only the number of questions moves the result. Repetitions
measure the noise; questions measure the effect.

A prior estimate in this project put the requirement at 30–40 questions. That was too optimistic by
roughly a factor of three.

---

## 3. What does survive: five stable observations

These do not depend on the noisy scorer, either because the cell was perfectly stable across every
repetition or because the finding is deterministic.

### 3.1 The defect reproduces on a production semantic layer

`A_implicit` scored **2/4 in all three MetricFlow runs** — no variation at all — and both failures
were confidently wrong numbers rather than refusals. The agent picked the shorter metric name both
times the question meant the other twin.

This answers the strongest objection to the whole programme: *you measured your own file format.*
The same defect and the same failure appear in dbt MetricFlow, which thousands of teams run.

`B_documented` was also stable at 4/4 across all three runs.

### 3.2 MetricFlow cannot express the repair as a named segment

Our layer repairs this defect by declaring a named, described, reusable segment. Cube has the same
construct. MetricFlow does not: a metric filter is an expression over a dimension, and there is
nowhere to give the resulting population a name.

| | how a population is expressed | can a machine read its name? |
|---|---|---|
| Cube | `segments:` — named, described, reusable | yes |
| ours | governed segment — the same idea | yes |
| MetricFlow | a where-constraint over a dimension | no — only the predicate survives |
| DAX | inside a measure expression | no |

This is a structural fact about the tools, established by building the layer rather than by
measuring an agent. It does not depend on the noise floor at all.

### 3.3 Paraphrase is what separates the questions, and the prediction made here was wrong

**Superseded 2026-08-09.** An earlier version of this section reported that `D_declared` on
MetricFlow failed `p_pop_customers_week` in two runs of three, and predicted that a named segment
survives paraphrase where a dimension filter does not. Both halves need correcting.

**The failure is gone.** On the current layer, `20260809-124835`, `D_declared` scores 12/12 with
zero unstable cells. The earlier runs predate the addition of `reminders_shown` and `active_habits`
and the MetricFlow fixes.

**The paraphrase effect is real and larger than reported.** Across both engines, only two of the
questions discriminate, and they differ in one word:

| question | wording | needs |
|---|---|---|
| week | "our **customers**" | knowing that customer means real user |
| June | "**excluding staff and test accounts**" | knowing which dimension carries the flag |

The June question is answerable by dimension inspection alone. In `02_segment__mf`, `A_implicit`
applied `user__is_internal = False` itself and returned the correct 15,329, then graded as a miss
only because it declared `value_moments` rather than `real_value_moments`. So the item measures
metric choice, not the answer — and three of that arm's six `confidently wrong` flags are this case
rather than a wrong number.

**The prediction went the other way.** The two engines do split on the paraphrased question, but not
as predicted:

| engine | `B_documented` on "our customers" | picked | answered |
|---|---|---|---|
| MetricFlow | **3/3 correct** | `real_value_moments` | 3,642 |
| harness | **0/3** | `value_moments` | 3,785 |

The descriptions of the twin pair are **byte-identical between the two engines**. What differs is
the catalogue around them:

| | metrics in the catalogue | carrying "excludes internal/test" |
|---|---|---|
| MetricFlow | 3 | 2 |
| harness | 13 | 7 |

Two candidate explanations, and this run separates neither: the harness catalogue is four times
larger, and it repeats the exclusion phrase on seven metrics, which may stop the phrase functioning
as a distinguishing property of the twin. **The two studies are therefore not comparable on the B
arm**, and any claim that one engine's documentation "works better" is unsupported.

The cheap test is to run `02_segment` against a three-metric catalogue and see whether
`B_documented` recovers the week question. That is a rendering change, not a modelling one.

### 3.4 The benefit of documentation is a function of model capability, and at the frontier it is zero

**CORRECTED 2026-08-09 BY `00_primitive_load` §9.** This section concluded that documentation is
worth nothing to a frontier model. That is a ceiling effect, not an absence. On a fifteen-item set
built to require up to four primitives at once, `gpt-5.6-terra` scores **38/45 undocumented against
45/45 documented** — a gap of about 20 points that this five-item study could not see.

What survives, and it is the sharper claim:

| | gpt-5-mini | gpt-5.6-terra |
|---|---|---|
| is there a gap? | yes | **yes** |
| does it grow with question depth? | **yes — 0, 0, 0, +22, +56 pp by load** | no — flat near +20 pp |

So documentation still pays at the frontier; what changes with model tier is not *whether* it pays
but *what it pays for*. On the cheap model the benefit is concentrated in compositional depth, and
at load 4 it reaches 56 points. On the frontier model the failures are scattered across loads with
no pattern, which is item difficulty rather than compounding.

The claim below — "the value of documentation is a function of model capability, and at the frontier
it is zero" — should be read as *"...and at the frontier this five-item set cannot detect it"*.


Added 2026-08-09, and it conditions every other number in this folder.

`01_entity` is the only study built well enough to re-run unchanged, so it was swept across three
models with `--override-model`. Everything else is identical: same arms, same questions, same
guardrails, same judge, each agent at the cheapest reasoning effort it accepts.

| arm | gpt-5.4-mini | gpt-5-mini | gpt-5.6-terra |
|---|---|---|---|
| A_implicit — nothing documented | 12/15 | 10/15 | **15/15** |
| B_documented — one sentence per table | 15/15 | 15/15 | 15/15 |
| C_modelled | 13/15 | 14/15 | 15/15 |
| C_modelled_documented | 15/15 | 14/15 | 15/15 |
| D_declared | 14/15 | 15/15 | 15/15 |
| E_enforced | 14/15 | 14/15 | 15/15 |
| **A → B gap** | **3** | **5** | **0** |
| **silent wrong, all arms** | 7 | 7 | **0** |

`A_implicit` is the messy warehouse with nothing documented: `evt` holding app opens, completed
habits and reminders behind an unlabelled integer, `u.internal` as 0/1/NULL, `subs.st` as a status
code. **`gpt-5.6-terra` answered every question from it, three times out of three, with zero
self-disagreement across all thirty cells.** It resolved the entity from column names, value
distributions and its own domain knowledge; nothing in the warehouse states that `etype = 2` is a
completed habit.

This belongs in §3 rather than §2 because it does not depend on the noisy scorer: the frontier
column is perfectly stable, and the two mini columns agree with each other on direction.

**What it licenses, and what it does not.**

| | |
|---|---|
| supported | *the cheaper the model you run, the more your documentation is doing* |
| not supported | documentation is worthless — this defect is too easy for this model, and `04_grain/FINDINGS.md` §6 records the same model failing a different defect badly |
| not supported | the mini tiers are broken — they serve **wrong numbers silently**, seven each, which is the failure mode that matters |

**Why every other cell in this folder is now conditional.** Each was measured on `gpt-5-mini` alone.
`primitives_matrix.md` records interventions against primitives and says nothing about the model;
after this sweep that omission is a claim, not a gap. A cell that reads **works · measured** means
*works on gpt-5-mini at minimal reasoning*, and on this evidence the same cell may read differently
one tier up.

**The honest caveat on the comparison.** Each model ran at its own floor — `minimal` for
`gpt-5-mini`, `none` for the other two — because the ladders differ and neither is a prefix of the
other. Reasoning depth is held at "cheapest available" rather than exactly constant, which is what
`agent/models.py` documents as the harness standard.

### 3.8 Documentation's effect scales with question depth, and its sign depends on the question

Added 2026-08-09 from `00_primitive_load/FINDINGS.md` §19 — six arms, 23 items, three repetitions,
every item passing the primitive check.

Eleven of the questions ask to exclude staff and test accounts; twelve do not. Splitting on that,
and then by how many primitives the question forces:

| A→B at load 4 | run 1 | run 2 | run 3 |
|---|---|---|---|
| question **asks** for the documented fact | +22 pp | +44 pp | **+22 pp** |
| question does **not** | −50 pp | −50 pp | **−50 pp** |

Three independent runs, the same −50 each time. The middle rungs do not replicate; the deepest one
does.

**Both grow with depth, in opposite directions.** Read as one curve the gap is `+0, +13, +13, −7`,
which is their average and looks like noise.

> What documentation does to an agent scales with the depth of the question, and its **sign** depends
> on whether the question needs the documented fact. If the answer requires it, documenting it pays
> more the deeper the question. If not, documenting it costs more — the agent applies the documented
> filter unasked, and that error compounds with everything else the question makes it resolve.

**The mechanism is over-application, and rewording did not stop it.** `00_primitive_load` §11 found a
rule-shaped comment being applied as a default and reworded it descriptively. The effect survived:
all nine wrong answers in the documented arms of the family whose questions never mention staff are
the gold with staff excluded. **Naming a filterable population in documentation is enough**, however
it is phrased.

**This supersedes the earlier readings of the load hypothesis** in §3.4 and in that study's §9 and
§11. Those measured a mixture of the two directions and got a different shape each time depending on
the item mix; three families ask and two do not.

Cell sizes are two or three items and the mechanism is one filter (`is_internal`). Whether a
documented grain or join rule over-applies the same way is untested and is the obvious next
question.

### 3.9 A model that carries its own meaning beats documenting a worse one

Added 2026-08-10 from `00_primitive_load/FINDINGS.md` §24 — six arms, 23 items, three repetitions,
after the star's codes were decoded into descriptive attributes.

| arm | score |
|---|---|
| `C_modelled` — conformed star, **no comments** | **66/69** |
| `C_modelled_documented` | 65/69 |
| `E_enforced` — layer plus provenance check | 64/69 |
| `D_declared` — layer | 62/69 |
| `B_documented` — raw tables, documented | 60/69 |
| `A_implicit` — raw tables | 52/69 |

**The undocumented conformed star beats the documented star, the semantic layer, and the layer with
a guardrail.** `C_modelled` scored exactly 66/69 in both runs since `dim_users` gained `country_name`
and `user_type`, and the ordering held in both.

The change that produced it is Kimball's oldest rule: a dimension attribute should be verbose and
descriptive, so a code sits beside its label. Storing `DE` alone had pushed the decode onto every
consumer, and three items failed on it in every earlier run. **Documenting the mapping in a comment
was the weaker fix and could not reach the arm that reads no comments.**

**Three findings now replicate across runs**, which nothing in that study did before: `C_modelled` at
66, the load-4 documentation split (below), and `E_enforced` never once skipping the catalogue —
0 of 69, three runs running, against `D_declared`'s 38 to 47.

Not powered: 23 items, 16% of cells unstable, six arms separated by one to three points at the top.

### 3.7 Requiring provenance is what makes an agent use the layer

Added 2026-08-09 from `00_primitive_load/FINDINGS.md` §17. §3.5 measured how often a governed layer
is skipped and named "what makes an agent use one" as a study nobody had run. It has now been run,
as a paired comparison inside one study: the same MetricFlow layer, the same warehouse, one
guardrail apart.

| | correct | silent wrong | used `query_metric` | wrote SQL | **never read the catalogue** |
|---|---|---|---|---|---|
| D_declared — R1 | 20/23 | 3 | 13 | 10 | **10** |
| E_enforced — R7, `governed_numbers` | 20/23 | **2** | **23** | **0** | **0** |

**A number must trace to one governed result, so raw SQL cannot produce an acceptable answer, so the
catalogue has to be read.** Accuracy is identical; every other column moves.

Two consequences.

**The bypass finding needs restating.** §3.5 and §3.6 read as "the layer is unhelpful, so the agent
abandons it". On this evidence the layer was abandoned because **nothing required it** — and once
something did, it was used on every row without costing accuracy.

**It changes what a semantic layer is for.** The layer alone did not beat SQL. The layer plus a
provenance requirement got the same answers through a governed, citable path, and turned one silent
wrong number into a refusal. Those are different products, and only the second is what the practice
sells.

One arm, 23 rows, one model, one repetition. A mechanism and a direction, not a rate.

### 3.6 When the agent does use the layer, it is less accurate than when it writes SQL

Added 2026-08-09 from the trace analysis in `00_primitive_load/FINDINGS.md` §15. §3.5 measured how
often the layer is skipped; this is what happens when it is not.

| how `D_declared` reached its answer | rows | correct |
|---|---|---|
| governed only — `query_metric`, no SQL | 16 | **31%** |
| SQL only — never used the layer | 44 | **70%** |
| layer, rejected, then SQL | 9 | **89%** |

Three causes, all in our layer:

**It has no join model.** `semantic/semantic.py` compiles every metric to `SELECT … FROM <one base
table>`, so a dimension is usable only if it is a column on that table. Seven metrics sit on
`agg_active_days`, which `star.sql` pre-joins `dim_users` into, and are richly sliceable. Ten sit on
tables carrying no user attributes and have one dimension or none. **The catalogue renders both
kinds identically**, so the agent cannot tell which metric will accept a filter until it is refused.

**No metric exposes a user grain**, so "how many people" is unanswerable through the layer for
habits, reminders or referrals.

**Two metrics hide a filter in their name.** `active_habits` carries `default_filters: ["NOT
is_archived"]` and `paying_users` carries `["is_active"]`. Asked for fitness habits, the arm that
correctly reached for the governed metric got 1,032 where the answer is 1,235.

That last one is `real_value_moments` under a different noun — **the defect `02_segment` exists to
measure, shipped in our own layer.** It must be fixed before any of this is published, and it means
every column-D reading in `primitives_matrix.md` that rests on `00_primitive_load` is partly a
measurement of our layer's coverage and defaults rather than of declaring facts.

**The 31%-against-70% is a subgroup comparison inside one arm**, not a controlled contrast: those
rows differ in which questions they are as well as in which route was taken. It sets up a study
rather than concluding one.

### 3.5 The stronger the model, the less it uses the semantic layer

From the same sweep, and larger in consequence than 3.4.

`D_declared` and `E_enforced` reach data through `query_metric` and are supposed to read the
governed catalogue first. The context audit records when they did not:

| | gpt-5-mini | gpt-5.4-mini | gpt-5.6-terra |
|---|---|---|---|
| governed rows that never called `list_metrics` | 7/30 | 8/30 | **13/30** |

At the frontier, **43% of the governed rows answered without consulting the catalogue at all.**

This is not a harness artefact — the audit records a tool that was available and not called. Two
consequences:

**Column D's score is increasingly not a measurement of the semantic layer.** On a growing share of
rows the layer was not consulted, so what is being scored is the model answering from the schema
with a governed tool sitting unused beside it. Any D-versus-B comparison on a frontier model must
report that share or it is reporting something else.

**It names a study the matrix does not have.** What makes an agent *use* a governed layer it has
been given is a question about tool affordance rather than about data modelling, and on this
evidence it may matter more than any cell in the matrix.

---

## 4. The largest yield so far has been defects in our own instrument

More has been learned from what the harness got wrong than from what the agent got wrong.

### 4.1 Study 03's first result was entirely our own bugs

The first run read prose 5/5, table 4/5, JSON 1/5 — a four-point spread that looked like a finding.
Four differences had crept in because each renderer decided its own wording:

| defect | consequence |
|---|---|
| only the JSON arm's header advertised the `segment` argument | it applied `segment=real_acquisition` unasked and answered **227** where the truth was **283** |
| prose wrote `is_internal=false`, supplying a value the others only named | the value was pasted straight into a call |
| a metric with no dimensions rendered as `—` in the table and as silence in prose and JSON | the load-bearing fact of that study, stated two different ways |
| `filterable` dimensions were never rendered in any format | the compiler accepted a filter the catalogue never advertised |

The guard designed to prevent exactly this passed all four times. It checked that each rendering
*contained* every name, description and synonym, and containment cannot see an extra instruction, a
value the others omit, or a fact stated as silence.

### 4.2 The replacement guard had the same blind spot one level up

The containment check was replaced by word parity: all three formats must use the same set of
content words. It catches three of the four defects above.

It then missed a fifth. A refactor collapsed the time-grain vocabulary (`day`, `week`, `month`)
into the single word "supported", removing it from **all three formats at once** while the tool
schema kept accepting `time_grain`. Three formats in perfect agreement about a catalogue that no
longer said what grains existed.

**The lesson generalises: a guard that compares the arms only to each other cannot see anything
removed from all of them.** Every check of this kind needs a second source outside the comparison —
here, the tool schema.

### 4.3 A guard that searches prose for words can be satisfied by coincidence

The first schema-parity check looked for the grain words in the rendered catalogue. It passed while
the grain field was missing, because "week" is a substring of "last_week" and a period name
satisfied a check about grains. Rewritten to read the catalogue's structure instead.

### 4.4 A more complete catalogue made the agent more consistent

Restoring the dropped grain vocabulary changed study 03 measurably:

| | prose | JSON | table | unstable cells |
|---|---|---|---|---|
| grain missing | 14/15 | 13/15 | 12/15 | 5 of 15 |
| grain restored | 14/15 | 14/15 | 15/15 | 2 of 15 |

The refusal wording steadied as well: the table arm had produced three different reasons for one
refusal across three runs, and afterwards gave the same one every time.

**A soft observation, worth testing properly.** Five questions, one comparison, and the comparison
itself was not repeated. But it points the same way as the external evidence that semantic content
matters far more than presentation, and it is the most interesting lead this folder has produced.

---

## 5. The agent refuses reliably and categorises unreliably

On the two unanswerable questions in study 03, the agent almost always refused rather than
inventing a number — but named a different reason for the same refusal across identical runs:

```
prose  signups from Germany   segment_undefined → dimension_not_supported → dimension_not_supported
table  spend in EMEA          no_governed_definition → ungoverned_dimension_value → dimension_not_supported
```

Scoring the **action** (refused rather than fabricated) instead of the exact code cut instability
from five cells to three, and changed which arm ranked best.

This is a known split in the literature — refusal is a detection skill and a categorisation skill,
and models are much weaker at the second. What appears **not** to be published anywhere is
categorisation instability *across identical repeated runs*, which is what we measured. That makes
it publishable material rather than only a nuisance.

Part of it is our own taxonomy. For "marketing spend by region" on a metric with no region
dimension, all three codes the agent produced are defensible. A taxonomy where a reasonable
reviewer could defend more than one label is measuring its own ambiguity.

Every run now prints two columns — right action, and right reason — because they can rank the arms
differently and they answer different questions. Refusing instead of fabricating is reliability;
naming the reason correctly is usability.

---

## 6. What study 03 did establish

The format comparison itself is unresolved and probably always will be at this scale, but the work
produced three solid results.

**The three formats are provably saying the same thing.** Parsing each delivered catalogue back
into `(metric, field) → values` recovers every fact in all three: zero missing, zero mismatched,
identical metric order.

**Their measurable differences are these, and they are not defects:**

| property | prose | JSON | table |
|---|---|---|---|
| tokens | 1,204 | 2,209 | **1,028** |
| lines | 91 | 372 | 38 |
| characters between a metric's name and its description | 5–22 | 28–45 | 6–23 |
| metric / dimension / segment visually typed | no | yes | yes |

JSON costs **2.15×** what the table costs to convey identical facts. Prose costs 1.17×.

**Prose reuses one syntax for three different kinds of object** — `- name: comma, separated, text`
serves metrics, dimension values and segments alike, distinguished only by a section heading. The
table types every row. No arm ever passed a dimension name where a metric belonged, so the
ambiguity is real but produced no observed error.

### The default, stated honestly

We render the catalogue as prose because people have to read it. The comparison showed no
difference large enough to change that — but it could only have detected very large effects, so
this is a default we chose, not an equivalence we established. **Token cost is not the reason:** the
table is cheaper.

---

## 6b. Every study is decided by two questions or fewer

Added 2026-08-09, from a per-item pass over all four studies. It is the most important structural
fact in this folder and it was not visible while only arm totals were being read.

| study | questions | that discriminate between arms |
|---|---|---|
| `00_catalogue_format` | 5 | **0** |
| `01_entity` | 5 | **2** |
| `02_segment` | 8 | **2** |
| `02_segment__mf` | 4 | **2** |
| `05_additivity` | 5 | **1** |

Everything else is a constant added to every arm's total. Three consequences:

**Arm totals conceal this.** `02_segment` reads 18 / 21 / 23 out of 24, which looks like a ladder. It
is six flat questions plus two that move, and the two move in different arms.

**Merging studies did not help.** `02_segment` was formed by merging the name instance with the
aggregate instance, on the argument that item count is the binding constraint. The three aggregate
questions are answered correctly by every arm, and `D_declared` loses a cell on one of them. The
merge doubled the denominator and left the numerator alone, which moves every rate toward the middle
and makes the study look more stable than the evidence is.

**More repetitions cannot fix it.** Repetitions estimate noise *within* an item; the effect lives
*across* items. Six discordant items is the floor for p < 0.05 on a paired test, and no study here
has more than two.

Each study's `FINDINGS.md` now carries its own per-item table. Read those before any arm total.

---

## 6c. One word meaning two things, found twice and filed under two different rows

Added 2026-08-09. Two studies have now produced the same failure, and neither was built to look for
it.

| study | the word | the two readings | what the agent did |
|---|---|---|---|
| `02_segment` | **customers** | real users (3,642) · every account (3,785) | served 3,785, 0/3 |
| `04_grain` | **subscriber** | people holding a subscription (413) · users (2,500) | divided by 2,500, 5 of 9 misses |

This is **polysemy**, and it is not the segment primitive. A segment question asks *which ones of a
known thing*; here the disagreement is about *which thing the word denotes*, and both readings
return a plausible number. Nothing downstream can tell them apart.

Two things follow.

**The repair that worked in both cases was vocabulary, not structure.** `02_segment`'s declared arm
answered the "customers" question because its segment lists `customers` as a synonym. `04_grain`'s
governed arms answered 3/3 because the metric pins the denominator. In both cases what a metric
definition supplied was *a word pinned to one meaning*, which is a different mechanism from the one
the matrix's column D describes.

**It is not being given a matrix row yet.** The evidence is two accidental observations from studies
built for other primitives, and `primitives_matrix.md` is already 15 cells filled of 40. A row with
no study behind it is a to-do item wearing a framework's clothes. When a study exists, the row
follows.

---

## 7. What to do next

0. **Decide the target model before authoring any item bank.** §3.4 changes what "hard enough"
   means: `gpt-5.6-terra` scored 15/15 in every arm of `01_entity`, so a question set written at the
   current difficulty would max out on a frontier model and separate nothing. Running `02_segment`
   with `--override-model gpt-5.6-terra` costs one small run and tells us whether the segment defect
   survives a tier up. Doing it after writing thirty questions is the expensive order.
1. **Re-estimate the variance components from our own runs** rather than the literature's generic
   calibration, and recompute what our designs can actually detect.
2. **Score cells as rates rather than verdicts**, and replace the McNemar guidance the runner still
   prints with paired item-level differences and honest intervals. McNemar needs binary cells and
   discards the repetition information entirely.
3. **Collapse the refusal taxonomy** so that no two codes describe one defect, and require the
   rationale to be written before the label.
4. **Then author questions — 60 to 150, not 30 to 40** — and spend them on the defect studies,
   where the effect being chased is a property of the data model rather than of its presentation.

Do not mode-aggregate repetitions into a single verdict per cell. It is the obvious-looking fix and
it destroys interval coverage.

---

## Provenance

| claim | where it comes from |
|---|---|
| noise floor 13% | `results/experiments/04_repair_matrix/` — three MetricFlow runs, one study 02 run, one study 03 run |
| defect reproduces on MetricFlow | `20260807-142016`, `-144843`, `-145627`; confirmed on `20260809-124835` |
| discriminating-item counts (§6b) | per-item pass over `20260807-183018`, `20260808-232437`, `20260808-132436`, `20260809-121926`, `20260809-124835` |
| the two engines' B arms split | `20260809-124835` and `20260809-121926`, `p_pop_customers_week`, all reps |
| catalogue sizes 3 versus 13 | the `list_metrics` result stored in each run's first step |
| four confounds in study 03 | `20260807-170942` and the trace comparison that followed |
| grain regression | `20260807-180538` against `20260807-183018` |
| the three-model sweep (§3.4, §3.5) | `20260808-232437` (gpt-5-mini, pre-rename arm names), `20260809-175723` (gpt-5.4-mini), `20260809-180003` (gpt-5.6-terra) — same study, same questions, same judge |
| catalogue-skip counts | the `context_audit` field of the `D_declared` and `E_enforced` rows of those three runs |
| token counts | `o200k_base` over the current renderings |
| detectable-effect figures | paired sample-size formulas from the LLM-eval statistics literature, using generic binary calibration — **not yet re-estimated from our own data** |
