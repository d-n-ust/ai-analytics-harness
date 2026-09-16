# Golden path — one experiment, end to end

How to take a question you care about and turn it into a result you can defend, using this harness
and a local Langfuse. Nine steps, in order, with the cheapest checks first.

The ordering is the point. Every step before step 6 costs nothing or costs cents, and each one can
kill an experiment that would otherwise have been paid for in full. The most expensive mistake
available here is running a suite before the instrument has been shown to move.

| step | costs | what it can kill |
|---|---|---|
| 1 · Ask a falsifiable question | nothing | an experiment with no possible negative result |
| 2 · Design items that can discriminate | nothing | a study that cannot reach significance at any n |
| 3 · Declare the arms | nothing | arms that differ in capability rather than treatment |
| 4 · Guards | nothing | a confound, before a token is spent |
| 5 · Gate | about $0.01 | broken plumbing |
| 6 · Run small | cents | an instrument that does not move |
| 7 · Read the report | nothing | a result that is noise |
| 8 · Investigate traces | nothing | the wrong hypothesis about why |
| 9 · Scale, regrade, republish | dollars | — |

---

## 1 · Ask a question that can come out negative

Write the question so that a specific outcome would refute it. "Does declaring the segment help?"
is not yet falsifiable; "does an agent pick the right metric more often when the segment is
declared in the layer than when it is only described in prose?" is.

Put it in the experiment manifest, which is also where the answer goes when you have one:

```yaml
# harness/experiments/07_my_experiment/experiment.yml
title: "What the experiment is called"
question: "The falsifiable question, in one sentence."
status: draft          # draft → running → shipped
runs: declarative
```

## 2 · Design items that can discriminate

**This is the step that decides whether the experiment can produce a result at all**, and it is
free. An item only carries information if the arms can *disagree* on it. Items that are right
everywhere, or wrong everywhere, are a constant added to both sides.

The floor is six. Fewer than six disagreeing items cannot reach p < 0.05 on a paired sign test, at
any number of repetitions — repetition estimates noise *within* an item, while the effect lives
*across* items.

So aim for **at least ten items you expect to separate the arms**, not ten items in total. Two
failure shapes to design out:

| shape | why it wastes the run |
|---|---|
| Answerable without the fact under test | Comes back flat for a boring reason. |
| A 15× error rather than a near miss | Separates, but tests whether the failure happens at all, not whether it is *catchable*. Both are valid questions — decide which one you are asking. |

Write the cases with a checkable expectation wherever possible:

```yaml
# harness/experiments/07_my_experiment/01_my_study/cases.yml
cases:
  - id: q_segment_customers_week
    tier: population
    question: "How many habits did our customers complete last week?"
    expect:
      type: metric_answer               # graded against a gold figure — auditable
      metric: real_value_moments
      gold_sql: "SELECT count(*) FROM fct_value_moments f JOIN dim_users u USING(user_id)
                 WHERE NOT u.is_internal AND f.week = DATE '2026-07-06'"
      tolerance: 0.02
    note: "'Customers' excludes staff, but no metric name says so."
```

Prefer `metric_answer` (gold figure), `refuse` (required terminal action) or a typed slot. A
`keywords` or `diagnostic` expectation is graded by matching words in free text, which cannot
separate an answer that names the right driver from one that names it amid invented figures — and
that path can never register a silent error. The report prints how many of your verdicts rest on
it. Keep the number small and deliberate.

## 3 · Declare the arms as patches

An arm is a patch against the shipped layer, never a forked copy of it. Forked layers drift.

```yaml
# harness/experiments/07_my_experiment/01_my_study/study.yml
base: semantic/semantic_layer.yml
rung: 3
arms: [A_implicit, B_documented, D_declared]
```

See `experiments/README.md` for the two-level shape.

## 4 · Let the guards run

Four checks run before a token is spent. They exist because each one has already caught a
confound that would otherwise have been paid for:

| guard | catches |
|---|---|
| same-numbers invariant | arms that differ in capability rather than treatment |
| candidate-count guard | an arm quietly offering fewer metrics — worth ~50 points before any treatment exists |
| vocabulary audit | the question leaking verbatim into one arm's catalogue |
| context expectation | an arm whose rendered catalogue never reached the model |

```bash
./bench study 07_my_experiment/01_my_study --describe     # guards only, no model calls
```

## 5 · Gate the pipeline

Three questions, one per pile, one repetition, through the same code path the full run uses.
Prove the plumbing before paying for a sweep.

```bash
./bench gate                      # mock model, free — 16 checks
./bench gate --model gpt-5-mini   # live, about $0.01 — adds the checks that need a real meter
```

## 6 · Run small first

Two questions, two arms, one repetition. The purpose is not a result. The purpose is to see
whether the instrument moves at all, and what a trace looks like.

```bash
./bench study 07_my_experiment/01_my_study --mock                       # free
./bench study 07_my_experiment/01_my_study --model gpt-5-mini \
    --arms A_implicit,D_declared --only q_segment_customers_week --reps 1
```

Results land in `runs/experiments/<experiment>/<timestamp>-<study>/` as `run.json` (every row),
`layers/` (the exact generated YAML each number came from), `summary.json` and `summary.md`.

## 7 · Read the report, in this order

`summary.md` is written automatically. Read its sections top to bottom — they are ordered so that
each one qualifies the ones below it.

**a. How these verdicts were reached.** How many rest on matching words in prose. If that share is
high, whatever follows is partly unaudited.

**b. Discrimination.** How many items separated the cells. Below six, stop: no between-arm
difference in this run is a result, and adding repetitions cannot change it. The report says so in
those words. Go back to step 2 and add discriminating *items*.

**c. Selective prediction.** Coverage, precision, risk and groundedness, per cell. Never pooled
across answerable and unanswerable questions, because on one pile answering is correct and on the
other refusing is.

**d. Uncertainty.** 95% intervals from resampling **questions**, not rows — four repetitions of
one question are four correlated measurements of one thing, so `n_q` is the real sample size.
Overlapping intervals are not evidence of no difference; each interval carries question
difficulty, and the paired comparison cancels it.

**e. Price of being wrong.** Each arm's cost line, and the price of a wrong answer at which the
choice between two arms flips. There is no single right price — a silently wrong figure costs one
thing in a regulated bank and another in a seed-stage app — so the output is the crossing, and the
reader locates their own business on it. Money and latency sit beside the curve, measured, never
folded into it.

Re-render at any time without re-running:

```bash
./bench report --run runs/experiments/07_my_experiment/<timestamp>-01_my_study
```

## 8 · Investigate in Langfuse

The report says *whether*. Traces say *why*.

```bash
docker compose -f observability/docker-compose.yml up -d
export LANGFUSE_HOST=http://localhost:3100
export LANGFUSE_PUBLIC_KEY=pk-lf-local-harness LANGFUSE_SECRET_KEY=sk-lf-local-harness

./bench publish --run runs/experiments/07_my_experiment/<timestamp>-01_my_study
```

Sign in at `localhost:3100` as `local@harness.test` / `localdevpassword`. The stack provisions its
own project and keys, so nothing leaves the machine. Publishing makes no model calls, so run it as
often as you like. Add `--dry-run` to see the payload with no server at all.

Two surfaces, and asking one the other's question is the common mistake:

| | Experiments | Tracing |
|---|---|---|
| answers | which arm is better | why *this* answer was wrong |
| unit | a cell | a row |
| shows | one trace per question per run | every row, filterable |

Start with the dangerous set: **Scores → `silent_error` = true**. Those are answers a reader
cannot tell are false. Open three to five and read them properly — the tool call shows what was
actually asked of the data, the guardrail span shows what was checked, and the answer shows what
the reader got. The failure is usually visible in the gap between the first and the last.

Filter by `qid`, `config`, `model`, `rung`, `rep`, `tier`, `expected_action`, `bucket` or
`graded_by`. Filtering out `graded_by = prose` leaves only the verdicts that can be audited.

One limit to know: a dataset run links one trace per question, so a cell of 148 rows shows 37 in
the Experiments table. Every row is in Tracing.

## 9 · Scale, regrade, republish

Only now is a full run worth paying for, and only if step 6 showed movement and step 7 showed
enough discriminating items.

```bash
./bench study 07_my_experiment/01_my_study --model gpt-5-mini --reps 3 --concurrency 2
```

Keep concurrency low. A measurement taken through a rate limiter measures the limiter: at
concurrency 8 this harness once produced 21 silent errors that were entirely infrastructure, and
the same cell at concurrency 2 had zero tool errors.

When a grading rule changes, recompute verdicts from the stored model outputs — no new model
calls — and republish. Trace and score ids are derived from the run, so the corrected scores land
on the traces you already have open rather than beside them.

```bash
./bench regrade --run runs/experiments/07_my_experiment/<timestamp>-01_my_study
./bench publish --run runs/experiments/07_my_experiment/<timestamp>-01_my_study
```

Write the finding into the study's `FINDINGS.md`, set the manifest `status` to `shipped`, and say
the n out loud in every sentence that carries a number.

---

## The whole path, condensed

```bash
./bench study 07_my_experiment/01_my_study --describe          # 4 guards, free
./bench gate --model gpt-5-mini                                # ~$0.01
./bench study 07_my_experiment/01_my_study --model gpt-5-mini \
    --arms A,D --only q_one,q_two --reps 1                     # cents
less runs/experiments/.../summary.md                           # discrimination first
./bench publish --run runs/experiments/...                     # free, no model calls
./bench study 07_my_experiment/01_my_study --model gpt-5-mini --reps 3 --concurrency 2
```

## Four questions to answer before calling anything a result

| | |
|---|---|
| How many items separated the cells? | Below six, it is a direction to investigate, not a finding. |
| What is `n_q`? | Questions are the sample. Rows are not. |
| Did you compare the intervals, or the pair? | Overlap is not sameness. The paired number cancels question difficulty. |
| How many verdicts were decided by prose? | That share of the result is unaudited. |

## Related documents

| | |
|---|---|
| `SYSTEM.md` | the three planes, and where Langfuse and OpenTelemetry sit |
| `ANATOMY.md` | the agent's components and request lifecycle |
| `EVALUATION.md` | the measurement rules, E-01 … E-27 |
| `experiments/README.md` | how a study is declared |
