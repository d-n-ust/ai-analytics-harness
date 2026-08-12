# Study 02 on dbt MetricFlow — what the runs established

The same primitive as `../02_segment`, on a semantic layer this project did not write. The
practitioner summary is in `PRACTITIONER-NOTES.md`; the harness version of the row is in
`../02_segment/FINDINGS.md`.

Numbers below are from `results/experiments/04_repair_matrix/20260809-124835-02_segment__mf`
— four questions, three repetitions, `gpt-5-mini` at `reasoning=minimal`, rung 3, the reduced cell
`R7-coverage_check-resolve`. That cell is what both engines can run; comparing it against the
harness study's full R7 would compare guardrails rather than layers.

The run directory keeps the pre-rename arm names; `study.yml` holds the mapping.

---

## 1. Why this study exists

The strongest objection available to the harness result is *you measured your own YAML*. This study
answers it: the defect is reproduced on dbt MetricFlow, which thousands of teams run in production,
using its own idioms and its own query engine.

It also measures something the harness cannot. **MetricFlow has no named-segment construct.** A
population is a where-constraint over a dimension, and there is nowhere to give the resulting
population a name. So column D is weaker here than in the harness study, and the two must not be
pooled.

---

## 2. Results

| arm | correct | confidently wrong |
|---|---|---|
| A_implicit | 6/12 | 6 |
| B_documented | **12/12** | 0 |
| D_declared | **12/12** | 0 |

Zero unstable cells across twelve. Every repetition of every arm on every question agreed with
itself.

| question | A_implicit | B_documented | D_declared |
|---|---|---|---|
| "our **customers**, last week" | 0/3 | 3/3 | 3/3 |
| "**excluding staff and test accounts**, June" | 0/3 | 3/3 | 3/3 |
| "every account, including internal" — control | 3/3 | 3/3 | 3/3 |
| "in total, counting every account" — control | 3/3 | 3/3 | 3/3 |

Perfect separation on the two questions that need the fact, and both controls flat everywhere. The
controls passing is what makes the failure attributable to the missing fact rather than to the
questions being harder.

**This supersedes the figures in `README.md`**, which record an earlier run where `D_declared`
failed one question in two of three repetitions. That run predates the two metric additions and the
MetricFlow fixes; on the current layer the arm answers everything.

---

## 3. The two failures are not the same kind of failure

`A_implicit` scores 6/12, and the six misses split evenly into two categories.

**A genuinely wrong number, on the week question.** The agent called `value_moments` with no filter
of any kind and returned **3,785** where the correct figure is **3,642**. Three repetitions,
identical, no signal of doubt.

**A right number with the wrong metric declared, on the June question.** The trace:

```
query_metric  metric=value_moments  filters={user__is_internal: False}   -> 15329
explanation:  "Queried governed metric value_moments for June 2026 with filter
               user__is_internal = False; returned sum = 15329"
```

15,329 is correct. The expectation names `real_value_moments`, so declaring `value_moments` grades
as a miss and as `confidently wrong`.

**Both engines show the same split**, which makes it a property of the question set rather than of
either layer. `A_implicit`'s six flags here are three wrong numbers and three provenance
mismatches; in `../02_segment` the same arm splits five into three and two.

`evals/grade.py` now separates them. `wrong_metric` is its own outcome, scored where the number is
right and the declared metric is not the one the case names. It still costs what a wrong answer
costs, because at R7 a number must trace to the governed result the question is about — but it is a
routing failure rather than a correctness one.

---

## 4. What separates the two questions

| question | wording | what the agent needs |
|---|---|---|
| week | "our **customers**" | that "customer" means a real user |
| June | "**excluding staff and test accounts**" | which dimension carries the staff flag |

MetricFlow exposes `user__is_internal` as a dimension the agent can list. When the question states
the exclusion literally, the agent maps the words onto that dimension and filters, with no metric
documentation involved. When the question uses business vocabulary, there is nothing to map.

So the June question is answerable by dimension inspection alone, and the week question is not.
**One of this study's four questions actually tests the primitive.**

---

## 5. What the engine cannot do, and why that matters

The repair available here is not the repair the harness offers:

```
harness       query_metric(metric="value_moments", segment="real_users")
              real_users is declared once, with a description, and offered by the metric

MetricFlow    mf query --metrics value_moments --where "{{ Dimension('user__is_internal') }} = false"
              there is no real_users anywhere — only is_internal = false
```

It reaches the right number. It does not name the population it selected.

**And it forces prose to do structural work.** The instruction *"filter on this to choose the
population"* had to be written into the `is_internal` dimension's description, because nothing
structural marks a dimension as a population selector. Writing a fact into prose because the
structure cannot hold it is the thing this experiment exists to criticise, and the engine leaves no
alternative.

This is the evidence for the framework's most useful claim: **the repair that works is available in
every stack, and the formal one is not.** If formalism were the mechanism, MetricFlow users could
not fix this. They can — `B_documented` scores 12/12.

---

## 6. Limits

**Four questions, two of which are controls.** One question genuinely tests the primitive. The
three repetitions show the effect is not sampling noise; they do not increase the item count.

**B and D are indistinguishable here**, at 12/12 each. That is a ceiling, not a null: the set has no
question either arm fails.

**The `where`-clause route is available to every arm.** An agent that inspects dimensions can reach
the right population without reading a single metric description, which is what the June question
shows. A question set that closes that route would measure the primitive more sharply.

---

## Provenance

| claim | source |
|---|---|
| per-arm and per-item figures | `20260809-124835-02_segment__mf/run.json` |
| the June trace | the same run, `A_implicit`, `p_pop_customers_june`, rep 0, `steps` |
| the superseded README figures | an earlier run, before `reminders_shown` and `active_habits` were added |
