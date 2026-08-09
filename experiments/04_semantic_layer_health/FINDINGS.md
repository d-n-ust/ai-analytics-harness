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

## 3. What does survive: three stable observations

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

### 3.3 A named segment appears to survive paraphrase where a dimension filter does not

`D_declared` on MetricFlow failed `p_pop_customers_week` in two runs of three. The question says
*"our customers"*, which requires knowing that customers means non-internal. The June question says
*"excluding staff and test accounts"*, which only has to be transcribed, and was answered correctly
every time. Our own layer carries "customers" as a segment synonym and offers `real_users` as an
enumerated choice, so it does not have to be inferred.

**Treat this as a direction, not a rate.** The cell is one of the two unstable cells in that study,
so the observation and the noise are the same event. It makes a testable prediction — the two
engines should split on paraphrased questions and agree on literal ones — and that prediction is
what a properly powered study should be built to check.

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

## 7. What to do next

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
| noise floor 13% | `results/experiments/04_semantic_layer_health/` — three MetricFlow runs, one study 02 run, one study 03 run |
| defect reproduces on MetricFlow | `20260807-142016`, `-144843`, `-145627` |
| four confounds in study 03 | `20260807-170942` and the trace comparison that followed |
| grain regression | `20260807-180538` against `20260807-183018` |
| token counts | `o200k_base` over the current renderings |
| detectable-effect figures | paired sample-size formulas from the LLM-eval statistics literature, using generic binary calibration — **not yet re-estimated from our own data** |
