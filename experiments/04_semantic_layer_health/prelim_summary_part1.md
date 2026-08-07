# Preliminary summary, part 1 — what the runs say about the hypothesis

**The hypothesis under test.** A semantically sound data model and semantic layer make an analyst
agent working on top of them measurably more reliable.

This document reports only what the stored runs support, and states the limit of each claim. Every
table is computed from `results/experiments/`. The companion document `FINDINGS.md` covers the
harness and measurement findings; this one covers the hypothesis.

**Summary in one paragraph.** The hypothesis holds in a sharper form than it was posed. The payoff
comes from whether a fact is present in the model at all, not from how formally it is expressed.
Removing the fact produces confidently wrong numbers, reproducibly. Writing it in a description
fixes that. Declaring it as a structural object — a named, reusable segment — bought nothing
further, and in two independent studies it cost something.

---

## 1. The defect, and that it is real

Two governed metrics measure the same thing, over the same rows, at the same grain. They differ in
one respect: which population they count. Neither name says so.

`A_absent` removes the fact entirely — nothing the agent can read states which population each
metric covers. `B_prose` states it in the metric description.

Study 01, rebuilt on **dbt MetricFlow**, three independent runs of the identical configuration:

| question | needs the fact? | A_absent | B_prose |
|---|---|---|---|
| "how many habits did our customers complete last week?" | yes | **0, 0, 0** | **1, 1, 1** |
| "excluding staff and test accounts, June 2026?" | yes | **0, 0, 0** | **1, 1, 1** |
| "…across every account, including internal?" | no — control | 1, 1, 1 | 1, 1, 1 |
| "…in total, counting every account?" | no — control | 1, 1, 1 | 1, 1, 1 |

Perfect separation on the questions that need the fact, and no variation in either direction across
six observations per cell. The two controls pass everywhere, which is what makes the failure
attributable to the missing fact rather than to the questions being harder.

**The failure mode is the dangerous one.** `A_absent` did not refuse or ask for clarification. It
served numbers:

```
customers, last week    3,785   (three times, verbatim)
excluding staff, June   64,257 · 15,329 · 15,329
```

A wrong number delivered with no signal of doubt is worse than a refusal, because nothing downstream
can detect it.

**This is not a property of our file format.** It reproduces on a semantic layer that thousands of
teams run in production. That is the answer to the strongest objection available: *you measured your
own YAML.*

**The limit: two discriminating items.** The repetitions show the effect is not sampling noise; they
do not increase the number of independent questions. Two items cannot carry a headline.

---

## 2. Where the hypothesis needs correcting

The intended ladder has three rungs: the fact is **absent**, the fact is stated in **prose**, the
fact is **declared** as a structural object the layer can offer as a choice.

The first step pays. The second did not.

| | absent | prose | declared |
|---|---|---|---|
| study 01 — MetricFlow, 3 runs | 2/4 each run | **4/4 each run** | 3/4 · 3/4 · 4/4 |
| study 02 — our own engine, 3 reps | 13/15 | **15/15** | 13/15 |

In study 02 the declared arm answered `21` on a question both other arms answered correctly, twice
out of three attempts — on our own engine, where a genuine named segment exists and is offered to
the agent as an enumerated choice.

**What this is and is not.** It is two items across two studies, two engines and two question sets,
pointing the same way. It is not a measured rate, and the individual cells sit inside the
13% run-to-run noise floor documented in `FINDINGS.md`. The reason to report it is that it points
**opposite** to what the ladder predicted. A result that contradicts the design is worth more
attention than one that confirms it, not less.

**A plausible mechanism, untested.** Adding a named segment adds an argument the agent must decide
whether to use. On questions that do not need it, that is one more way to be wrong. The prose arm
offers no such choice. If that is the mechanism, the cost of formalism is paid on every question
while the benefit is collected only on the questions that need the distinction.

---

## 3. The hypothesis, restated to match the evidence

> A semantically sound model improves agent reliability. The payoff comes from **completeness** —
> whether the model states the facts an answer depends on — rather than from **formalism**, whether
> those facts are expressed as structure or as prose.

Three independent results support this reading.

**Presentation does not matter.** Study 03 rendered a byte-identical catalogue as prose, as JSON and
as a markdown table. No difference large enough to detect. Token cost differs substantially — JSON
costs 2.15× what the table costs for the same facts — but accuracy did not follow it.

**Completeness does.** A refactor silently removed the time-grain vocabulary from the catalogue while
the query tool still accepted it. Restoring it changed study 03 measurably:

| | prose | JSON | table | cells disagreeing with themselves |
|---|---|---|---|---|
| grain missing | 14/15 | 13/15 | 12/15 | 5 of 15 |
| grain restored | 14/15 | 14/15 | 15/15 | 2 of 15 |

The refusal wording steadied as well. One arm had produced three different reasons for the same
refusal across three runs, and afterwards gave one. A soft observation — five questions, one
unrepeated comparison — but it is the shape the restated hypothesis predicts.

**The formal version is not universally available anyway.** MetricFlow has no named-segment
construct. A population is expressed as a where-constraint over a dimension, and there is nowhere to
give it a name.

| | how a population is expressed | can a machine read its name? |
|---|---|---|
| Cube | `segments:` — named, described, reusable | yes |
| ours | governed segment — the same idea | yes |
| MetricFlow | a where-constraint over a dimension | no — only the predicate survives |
| DAX | inside a measure expression | no |

If formalism were the mechanism, MetricFlow users would be unable to repair this defect. The data
says they can: the prose arm fixed it completely on MetricFlow.

---

## 4. Why the restated version is the more useful claim

The original form requires a specific class of tool and a modelling project. The restated form is
actionable in any stack, this week:

> Every metric must state who or what it counts, somewhere the agent can read. A description is
> enough.

That is checkable without an agent, which is the basis of the diagnostic work in `semantic/health.py`.

---

## 5. What is missing

**Items, on one contrast.** The evidence rests on two discriminating questions in study 01 and one
in study 02. Twenty to thirty questions of the same shape — a fact the answer depends on that the
metric name does not carry — would make this a result rather than a demonstration. The question
design is already proven to discriminate, which is the hard part.

**Not needed:** more repetitions, more arms, or further work on catalogue format. Repetitions
measure the noise floor, which is already measured. The gap is item count on **absent versus
present**.

**Open question worth its own study.** Does declaring a fact structurally cost accuracy on the
questions that do not need it? Both regressions above are consistent with that, and neither was
designed to test it. If it holds, it is a more interesting finding than the one this experiment set
out to produce.

---

## Provenance

| claim | source |
|---|---|
| study 01 per-cell results | `20260807-142016`, `-144843`, `-145627`, all `01_segment_in_metric_name__mf` |
| confidently wrong values | the `answer` field of those runs' graded rows |
| study 02 per-cell results | `20260806-114523-scope_in_agg`, 3 reps |
| grain-restoration comparison | `20260807-180538` against `20260807-183018` |
| token counts | `o200k_base` over the current renderings |
| noise floor 13% | pooled across all three studies — see `FINDINGS.md` |
