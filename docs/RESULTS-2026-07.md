# Results — July 2026 series

A fresh results record, written as the runs land. It supersedes nothing: earlier numbers were
measured on a different question set and a different model-visible surface, and the two are not
comparable. Where an earlier figure is quoted here it is labelled as superseded and kept only to
show what moved.

**Status**

| # | Experiment | State |
|---|---|---|
| 1 | Grounding ladder — what structure buys | **done** (2026-07-26) |
| 2 | What guardrails buy — the two axes | **done** (2026-07-26) |
| 3 | Reasoning effort and model class | **done** (2026-07-26) |
| 4 | Shapley attribution | **done** (2026-07-27) |
| 5 | The reliability ladder, R0–R9 | **done** (2026-07-27) |

---

## Method, common to every run

| | |
|---|---|
| Model | `gpt-5-mini`, reasoning effort `minimal` |
| Verifier model | `gpt-5-mini`, reasoning effort `low`, stance `skeptical` |
| Questions | 57, fixed across every cell |
| Repeats | 3 per cell |
| Warehouse | deterministic, one seed, DuckDB (`make data` reproduces it) |
| Row schema | v14 |
| Concurrency | 12 in-flight questions; I/O-bound, no effect on results |

Every cell answers the **same 57 questions**, so a difference between cells is attributable to the
one thing that changed. The question set moved once this month: `rt_total_subs_ever` and
`t1_value_moments_june` were dropped (a self-declared duplicate, and a question that scored 15/15
in every cell it ever ran in) and replaced by two that contest the metric tree's causal edges.
Runs before that swap are not comparable to runs after it.

### The two families of question

The 57 split into two groups that behave completely differently, and keeping them apart is the
single most important reporting decision here.

- **Answerable (75 rows/cell)** — `lookup`, `filtered`, `metric`, `knowledge`, `diagnostic`. A
  correct answer exists and the agent should produce it.
- **Reliability (96 rows/cell)** — `adversarial`, `rt_phantom`, `unanswerable`,
  `valid_but_wrong`, `false_premise`. **No correct answer exists.** The only right move is to
  decline, with the right reason.

Pooling these into one accuracy number hides the entire finding, so nothing here pools them.

### How each question is graded, and where that is weak

| grading | questions | rows/cell | how |
|---|---|---|---|
| `refuse` | 31 | 93 | did it decline, and name the expected coded reason |
| `metric_answer` | 17 | 51 | is the number within tolerance of an **independent** `gold_sql` |
| `diagnostic` / `keywords` | 9 | 27 | **keyword match over prose** |

`metric_answer` is the strong one: `gold_sql` computes the answer straight from the fact tables
and never touches the semantic layer the agent used, so a wrong metric definition cannot make a
wrong answer look right.

**27 of 171 rows per cell are scored by keyword match over free text**, and that is the weakest
instrument here — a keyword grader rewards saying the word, not being right. It does not drive
the headline results: coverage, precision and groundedness are computed on numeric and refusal
rows, and the answerable/reliability split moves by tens of rows where this could move a handful.
But `diagnostic` figures quoted on their own carry that caveat, and the honest fix is a validated
judge for prose answers rather than a longer keyword list.

### Is the verifier itself trustworthy?

R9's numbers depend on an LLM judge, so its error rate is a first-class number rather than an
assumption. Two measurements, and they answer different questions:

| | n | agreement | false-flag | catch | status |
|---|---|---|---|---|---|
| human panel (`verifier_audit.py`) | 37 | 92% | 10% | — | **invalidated** — 7 cases were judged on the wrong number, and the blind sheet carried the same wrong value, so both sides used corrupted evidence |
| independent gold (`verifier_vs_gold.py`) | **177** | **95.5%** | **5.0%** | **97.4%** | current, recomputed against the live prompt |

The gold-based score exists because the panel goes stale every time the judge's prompt changes —
five times in this series alone — while `gold_sql` is already there on every numeric question and
costs nothing to re-score. It refused **7 of 139 correct answers** and caught **37 of 38 wrong
ones**.

Two limits, stated because they decide what this does and does not settle:

- It covers only rows with a numeric gold — **177 of 202 judged decisions**. Diagnostic and
  keyword rows have no numeric gold, so the judge's behaviour on exactly the prose questions
  above is still unscored. That is the labelling job worth doing.
- `gold_sql` is an independent **computation**, not an independent **judgement**. It kills "the
  semantic layer graded its own homework" — the gold never passes through it — and it does not
  kill "the author graded their own homework."

### What the metrics mean

- **coverage** — of the answerable questions, the share the agent actually answered.
- **precision** — of those it answered, the share that were right.
- **groundedness** — of the unanswerable questions, the share where it did *not* invent a number.
  This is the safety number.
- **yield** — correct rows over all rows, refusals included. A refusal of an unanswerable
  question counts as correct only if it also names the right reason.

---

### The evidence behind every number here

`runs/` is gitignored — 27 runs in one day, and per-run output is a dev iteration. What is
tracked is the **measurements**, in `results/published/2026-07/`:

| file | grain | what it holds |
|---|---|---|
| `cells.csv` | one row per (run, rung, config) | the selective-prediction point, both question families, buckets, refusal quality, judge behaviour, cost, tokens, latency p50/p90, tool and model calls, provenance adoption |
| `tiers.csv` | one row per (cell, tier) | correct / n — which question types each cell wins and loses |
| `tools.csv` | one row per (cell, tool) | calls per question — what the agent actually reached for |

**~90KB for the whole series**, and every figure in this document was re-derived from those
tables before publication. Each row carries the model, reasoning effort, verifier, schema version
and **surface fingerprint**, so a reader can tell whether two cells were answering the same prompt
— without which a comparison is a coincidence.

What is deliberately not kept is the per-row traces. They are 84% of the bytes, and they are what
you would need to audit an *individual answer* or replay a judge call. The trade is stated rather
than hidden: these tables let you check a published figure and compare cells; they do not let you
re-derive one from scratch. For that, re-run the cell — the fingerprint and treatment columns are
what make that reproducible.

## Experiment 1 — the grounding ladder

**Question.** How much does *structure* buy? Not guardrails — structure: a clean schema, a
governed semantic layer, a metric tree.

**Design.** Four grounding rungs, one guardrail level. The guardrail level is **R1: the typed
`refuse` tool and nothing else.** No coverage check, no restriction on raw SQL, no checks on the
answer. The agent *may* decline; nothing makes it.

That is the point. With no guardrail interfering, whatever changes across the rungs is what the
grounding itself bought.

| rung | what the agent gets |
|---|---|
| 1 | raw tables — cryptic names, dirty values, no docs |
| 2 | a clean star schema |
| 3 | + the governed semantic layer (`list_metrics`, `query_metric`) |
| 7 | + the metric tree (`get_metric_tree`, `explain_change`) |

Rungs 4 and 5 (verified examples, knowledge base) are skipped deliberately. Both are *advisory
prose* — helpful, unverifiable, and not the thing under test. Rung 7 exists precisely so the tree
can be added without them: it is the **governed-only** cell, everything checkable and nothing
narrative.

`run` — `./bench run --models gpt-5-mini --rungs 1,2,3,7 --rrungs 1 --repeats 3 --reasoning minimal`
· 684 rows · 2026-07-26 · zero infrastructure errors

### Headline

| rung | coverage | precision | groundedness | fabrications | yield |
|---|---|---|---|---|---|
| 1 — messy data | 80.8% | **44.4%** | **58.6%** | 36/87 | 35/171 |
| 2 — star schema | 88.5% | **44.9%** | **53.4%** | 41/88 | 39/171 |
| 3 — semantic layer | 97.4% | **77.6%** | **65.2%** | 31/89 | 70/171 |
| 7 — + metric tree | 98.7% | **85.7%** | **69.0%** | 27/87 | 75/171 |

**Precision nearly doubles: 44.4% → 85.7%, +41 points.**
**Groundedness moves 10 points, and not even monotonically.**

### The finding

Split the same runs by question family:

| rung | answerable | reliability |
|---|---|---|
| 1 | 25/75 — **33%** | 10/96 — **10%** |
| 2 | 29/75 — 39% | 10/96 — 10% |
| 3 | 56/75 — 75% | 14/96 — 15% |
| 7 | **63/75 — 84%** | **12/96 — 13%** |

> Grounding moves the answerable questions **+51 points**. It moves the questions that have no
> answer **+3 points**, and non-monotonically.

**Better data buys accuracy. It does not buy honesty.**

Two details make the point sharper than the averages do.

**Rung 2 goes backwards on safety.** Groundedness *falls* to 53.4% — the worst of the four — while
coverage rises to 88.5%. A cleaner star schema made the model more willing to answer, and more of
those answers were invented. Better data made it more confident, not more careful.

**Rung 7 still fabricates on 27 of 87.** With the best grounding available — a governed semantic
layer *and* a metric tree, every definition it could need — the agent still invents a number for
nearly a third of the questions that have none. Nothing is checking, so nothing stops it.

### Per tier

| tier | rung 1 | rung 2 | rung 3 | rung 7 |
|---|---|---|---|---|
| lookup | 7/9 | 7/9 | 8/9 | 8/9 |
| filtered | 5/15 | 12/15 | 12/15 | 9/15 |
| metric | 7/15 | 2/15 | **15/15** | **15/15** |
| knowledge | 0/15 | 3/15 | **12/15** | 11/15 |
| diagnostic | 6/21 | 5/21 | 9/21 | **20/21** |
| adversarial | 3/39 | 2/39 | 6/39 | 6/39 |
| rt_phantom | 1/12 | 0/12 | 0/12 | 0/12 |
| unanswerable | 3/18 | 5/18 | 4/18 | 3/18 |
| valid_but_wrong | 3/21 | 2/21 | 3/21 | 3/21 |
| false_premise | 0/6 | 1/6 | 1/6 | 0/6 |

Each layer of structure pays off on a specific tier, and only there:

- **The semantic layer owns `metric`** — 2/15 → 15/15 at rung 3. Governed definitions are exactly
  what "what is our ARPU" needs, and raw SQL over a star schema is *worse* than raw SQL over raw
  tables (7/15 → 2/15), because a clean schema invites a confident wrong join.
- **The metric tree owns `diagnostic`** — 9/21 → 20/21 at rung 7. "Why did it move" needs a
  decomposition, and no amount of schema hygiene substitutes.
- **Nothing owns the reliability tiers.** `rt_phantom` is 1/12 → 0/12. `valid_but_wrong` sits at
  3/21 throughout. `false_premise` never exceeds 1/6.

### Cost, latency, tool usage

| rung | in tokens | out tokens | cached in | tokens/question | wall/question | tool calls/question | model calls/question | cost |
|---|---|---|---|---|---|---|---|---|
| 1 | 1,376,595 | 100,984 | 75,904 | 8,641 | 9.4s | 4.9 | ~5.5 | $0.53 |
| 2 | 1,099,697 | 84,807 | 32,512 | 6,927 | 7.7s | 3.8 | ~5.5 | $0.44 |
| 3 | 2,390,722 | 62,207 | 432,896 | 14,345 | 7.7s | 4.5 | ~5.5 | $0.63 |
| 7 | 2,339,541 | 47,527 | 626,432 | 13,959 | 6.6s | 4.2 | ~5.5 | $0.54 |

**$2.13 for the whole experiment**, 684 answered questions.

Two things worth noting. Grounding **halves output tokens** (100,984 → 47,527) — a grounded agent
writes less, because it explores less. And it gets **faster in wall time** (9.4s → 6.6s) despite
consuming more input, because a governed call replaces several rounds of table exploration.

Which tools each rung reaches for, per question:

| rung | tools used |
|---|---|
| 1 | `run_sql` 2.5 · `describe_table` 1.4 · `get_schema` 1.1 |
| 2 | `run_sql` 1.8 · `get_schema` 1.0 · `describe_table` 0.9 |
| 3 | `query_metric` 2.5 · `list_metrics` 1.2 · `run_sql` 0.4 |
| 7 | `query_metric` 1.6 · `list_metrics` 1.1 · `explain_change` 0.4 · `get_metric_tree` 0.3 · `run_sql` 0.4 |

Raw SQL does not vanish when a semantic layer appears — it drops to 0.4 calls per question and
stays there. At R1 nothing forbids it; the agent simply stops needing it.

### Caveats on this run

- **`yield` is depressed at every rung** by a reason-code problem: the agent declines correctly but
  names a different *true* code than the question expects. Measured at 49% of correct refusals. It
  affects all four rungs about equally, so the comparison holds, but the absolute yield figures
  should not be quoted. Coverage, precision and groundedness do not depend on reason codes and are
  unaffected.
- The refusal vocabulary was **undocumented** when this run executed — twelve bare enum strings with
  no descriptions. That is now fixed, which will change reason accuracy but not the three headline
  metrics.
- 3 rows of 684 died on provider `invalid_prompt` errors, all on the agent's opening call. Excluded
  from rate denominators.
- `iterations` is not written to the row (always `null`); model calls per question is derived from
  the recorded turns instead. Worth fixing in the writer.

---

## Experiment 2 — what guardrails buy

*(This measures two points, R1 and R9, at two grounding rungs — it is not the ladder. The full
ten-level ladder is Experiment 5.)*

**Question.** Experiment 1 showed structure cannot make the agent honest. What can?

**Design.** The same two grounding rungs that mattered in Experiment 1 — 3 (semantic layer) and 7
(+ metric tree) — at **R9**, the full guardrail ladder, against R1 as the baseline. Same 57
questions, same model, same reps. The only thing that changes is the guardrails.

R9 cannot run below rung 3: every guardrail above abstention acts on a semantic layer, and
`incoherent()` refuses the pairing rather than emitting rows whose label overstates what ran.

`run` — `./bench run --models gpt-5-mini --rungs 3,7 --rrungs 9 --repeats 3 --reasoning minimal`
· 342 rows · 2026-07-26 · zero infrastructure errors

### Headline — the full 2×2

| cell | coverage | precision | groundedness | fabrications | yield |
|---|---|---|---|---|---|
| rung 3 · R1 | 97.4% | 77.6% | 65.2% | 31/89 | 70/171 |
| rung 3 · R9 | 75.6% | 89.8% | **95.5%** | **4/89** | 119/171 |
| rung 7 · R1 | 98.7% | 85.7% | 69.0% | 27/87 | 75/171 |
| rung 7 · R9 | 87.2% | **97.1%** | **96.7%** | **3/87** | **135/171** |

### The finding — the two axes are orthogonal

| | answerable (75) | reliability (96) |
|---|---|---|
| rung 3 · R1 | 56/75 | 14/96 |
| **grounding** → rung 7 · R1 | **63/75** (+7) | 12/96 (−2) |
| **guardrails** → rung 7 · R9 | **63/75** (+0) | **72/96** (+60) |

> Grounding moves the answerable questions and not the others. Guardrails move the others and
> **cost nothing at all** on the answerable ones — 63/75 either way.

Each axis fixes what the other cannot touch. That is the whole argument in six numbers, and it is
why the two have to be built and measured separately: neither is a substitute for the other, and a
team that invests only in data modelling will get an agent that is accurate and still dishonest.

**Fabrication, end to end.** Of 87 unanswerable questions at the best grounding:

```
rung 7 · R1    27 fabrications      grounding alone
rung 7 · R9     3 fabrications      + guardrails
```

Grounding took fabrication from 36 (rung 1) to 27. Guardrails took it from 27 to 3.

### Per tier, at rung 7

| tier | R1 | R9 | |
|---|---|---|---|
| valid_but_wrong | 3/21 | **21/21** | the hardest failure — a real metric answering a slightly different question |
| unanswerable | 3/18 | **17/18** | |
| adversarial | 6/39 | **26/39** | |
| rt_phantom | 0/12 | **7/12** | |
| false_premise | 0/6 | 1/6 | still the worst tier — see below |
| metric | 15/15 | 15/15 | no cost |
| lookup | 8/9 | 9/9 | no cost |
| knowledge | 11/15 | 11/15 | no cost |
| filtered | 9/15 | 11/15 | no cost |
| diagnostic | 20/21 | 17/21 | **the only tier the guardrails cost anything** |

`valid_but_wrong` going 3/21 → 21/21 is the result to lead with. Those questions are the ones where
a plausible, correctly-computed governed number answers a *slightly different* question than the
one asked — the failure that survives every amount of data modelling and that a human reviewer
will not catch either.

The 3-row cost on `diagnostic` is what remains of the coverage price, down from **13 of 15** before
this month's judge work.

### Cost and latency

| cell | tokens/question | wall/question | tool calls/question | cost |
|---|---|---|---|---|
| rung 3 · R9 | 17,286 | 10.6s | 3.7 | $0.43 |
| rung 7 · R9 | 15,699 | 10.2s | 3.2 | $0.38 |

Guardrails add roughly **50% to wall time** (6.6s → 10.2s at rung 7) and about 12% to tokens. The
latency is two extra model calls per answered question: the role classifier and the judge. That is
the real price — not tokens, and not accuracy.

### What is still broken

**`false_premise` — 1/6, the worst tier at every cell measured.** The agent invents a cause for a
collapse that never happened. Nothing in the guardrail ladder addresses it, because every position
in the architecture (`action_space`, `before`, `disclosure`, `after`) acts on what the agent
*does*, and this failure is in what it was *asked*. A question carrying a false presupposition is
never inspected by anything. This is scoped to the planning experiment, not to this ladder.

**Judge over-refusals — 6 at rung 7, 7 at rung 3.** Every remaining refusal of an answerable
question comes from the one probabilistic guardrail; the eight deterministic ones over-refuse
nothing.

---

## Experiment 3 — reasoning effort and model class

**Question.** Everything above ran the cheapest model at its lowest reasoning setting. The obvious
objection is that the whole finding is an artefact of a weak agent. Does it survive more reasoning,
or a flagship model?

**Design.** Rung 7 throughout, four configurations at R1 and R9, same 57 questions and reps.

`run` — 5 cells × 171 rows · 2026-07-26 · **$2.83** · zero errors

| cell | loop | verifier | | coverage | precision | groundedness | answerable | reliability | s/q | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| a | mini @ minimal | — | R1 | 98.7% | 85.7% | 69.0% | 63/75 | 12/96 | 6.6 | $0.54 |
| b | mini @ **low** | — | R1 | 93.6% | 87.7% | **90.2%** | 61/75 | 36/96 | 6.8 | $0.36 |
| d | **terra** | — | R1 | 96.2% | 90.7% | 82.8% | **65/75** | 48/96 | **4.1** | $1.08 |
| a | mini @ minimal | mini | R9 | 87.2% | 97.1% | 96.7% | 63/75 | 72/96 | 10.2 | $0.38 |
| b | mini @ **low** | mini | R9 | 83.3% | 96.9% | **100%** | 60/75 | 62/96 | 9.3 | $0.26 |
| c | mini @ minimal | **terra** | R9 | 87.2% | 98.5% | 96.7% | **64/75** | 73/96 | 8.2 | $0.32 |
| d | **terra** | **terra** | R9 | 79.5% | **100%** | **100%** | 59/75 | **79/96** | **4.0** | $0.80 |

### This qualifies Experiment 1, and the qualification matters

Experiment 1 concluded *"better data buys accuracy, not honesty."* That stands for **structure** and
it does **not** generalise to **capability**. At R1, with no guardrails at all:

```
groundedness   mini@minimal 69.0%  →  mini@low 90.2%  →  terra 82.8%
reliability    12/96              →  36/96           →  48/96
```

A more capable agent *is* meaningfully more honest. Any claim that "the model can't be trusted to
refuse" has to be narrowed to "the cheapest model at its lowest setting can't." That is a real
correction to the framing, not a footnote.

### But the conclusion survives, and the comparison is sharper than before

> **A flagship model with no guardrails is worse than a cheap model with guardrails — and costs
> three times as much.**

```
terra   · R1   groundedness 82.8%   reliability 48/96   $1.08
mini    · R9   groundedness 96.7%   reliability 72/96   $0.38
```

Capability narrows the gap. It does not close it. Whatever a bigger model buys you, a mechanism
that checks the answer buys more, for less.

### Three secondary findings

**A flagship verifier buys almost nothing.** Cell (c) swaps the judge for terra and moves
reliability 72 → 73 and answerable 63 → 64. Within noise. The judge's job — does this metric answer
this question — turns out not to need a frontier model, which is the cheap half of the stack to
run.

**A flagship loop trades coverage for safety.** Cell (d) at R9 reaches perfect precision and
groundedness and the best reliability (79/96), but coverage falls to 79.5% and answerable to 59/75.
It refuses more, including things it could have answered.

**Terra is 2.5× faster per question** (4.0s vs 10.2s) despite being the larger model — it reaches an
answer in fewer loop iterations. Latency here is a function of how many times round the loop, not
model size.

### One anomaly, and it is a grading artefact

Cell (b) at R9 reaches **100% groundedness** yet its reliability score *drops* (72 → 62). It
declines more, not less: 92 of 93 unanswerable questions versus 88. The difference is the channel —
it used `clarify` 16 times against 6, and a clarify scores zero on a question whose expected
outcome is `refuse`.

More reasoning made it ask more clarifying questions, which is defensible behaviour scored as
failure. This is the same artefact as `u_pricing_cause`, and it is now visible in a headline
number rather than a single row.

---

## Experiment 4 — Shapley attribution

**Question.** The ladder says the stack works. Which guardrail is doing the work?

**Design.** Six guardrails vary; `abstain`, `check_tools` and `transparency` are held on
throughout. Six switches would be 2⁶ = 64 configurations, but **40 are incoherent** — they
describe a system that cannot do what its label says:

- `governed_numbers` without `tool_restriction` — the check reads governed results, which only
  governed queries record, so every raw-SQL answer auto-refuses
- `output_validation` without `governed_numbers` — `value` never reaches the answer schema, so
  the check cannot fire at all
- `trajectory_verify` without `governed_numbers` — the judge inspects a metric+SQL trajectory,
  which a hand-composed number does not have

Running those measures a contribution of zero *by construction* rather than by evidence.
`incoherent()` rules them out, leaving **24 cells and 60 legal orderings** (an ordering is legal
only if every prefix is coherent). Every ordering is enumerated — no Monte-Carlo — so the
efficiency axiom is an arithmetic check, not an approximation.

The previously published **32 configurations and 120 orderings are superseded.** That figure came
from the legality rule being restated inside the Shapley script instead of read from
`incoherent()`, and it drifted. The guardrail set changed too: `single_metric` is now
`governed_numbers`, a different rule.

`run` — 24 cells × 57 questions × 3 reps · **4,104 rows** · rung 7 · loop `gpt-5-mini@minimal`,
verifier `gpt-5-mini@low` · **$9.02** · 7 rows lost to errors (5 provider `invalid_prompt`, 2 a
harness crash since fixed)

### Safety — the wrong-number rate avoided

v(none) = 0.187 → v(full) = 0.029. **Point estimates with 95% bootstrap intervals (500 resamples,
resampling rows within each coalition and recomputing the whole exact Shapley each time):**

| guardrail | contribution | 95% interval | |
|---|---|---|---|
| `trajectory_verify` | **+0.0842** | [+0.0606, +0.1068] | clear of zero |
| `coverage_check` | **+0.0455** | [+0.0248, +0.0663] | clear of zero |
| `governed_numbers` | +0.0162 | [−0.0257, +0.0538] | |
| `tool_restriction` | +0.0117 | [−0.0444, +0.0671] | |
| `resolve` | +0.0069 | [−0.0146, +0.0271] | |
| `output_validation` | −0.0058 | [−0.0265, +0.0158] | indistinguishable from zero |

**Efficiency: Σ = −0.1579 = v(full) − v(none) — exact to floating point.**

### What this does and does not establish

Read the intervals, not the ordering. What the data supports:

- **`trajectory_verify` is the largest single safety contributor**, and its interval clears zero.
  The one probabilistic guardrail in the stack is also the one doing the most work.
- **`coverage_check` is second and also clear of zero.**
- **`output_validation` contributes nothing to safety**, which is what it should do: it catches a
  *malformed* value, not a *wrong* one. Its work shows up as a well-formedness guarantee, not as
  a lower error rate.
- **The bottom four are not ranked by this data.** Their intervals overlap each other and mostly
  straddle zero.

### Why the intervals are the headline

A one-rep pilot ran first, at $3, and produced this ordering: `trajectory_verify` +0.0719,
`tool_restriction` +0.0397, `coverage_check` +0.0281. It looks like a clean result. Bootstrapping
it showed **zero of five adjacent pairs separated at 95%** and `tool_restriction`'s interval ran
from −0.055 to +0.145 — wider than the whole spread from first to fifth.

At three reps `tool_restriction` fell to +0.0117 and `coverage_check` rose to +0.0455. **Second
and third place swapped.** Publishing the pilot's point estimates would have put a wrong ranking
in print, and nothing in those numbers would have shown it.

That is the reason every figure here carries an interval, and the reason the claims above name
only what survives one.

### Task-success — the correct typed-refusal rate

v(none) = 0.585 → v(full) = 0.749. Efficiency Σ = +0.1637, exact.

| guardrail | contribution | 95% interval |
|---|---|---|
| `coverage_check` | +0.0549 | [+0.0195, +0.0901] |
| `trajectory_verify` | +0.0430 | [+0.0064, +0.0817] |
| `governed_numbers` | +0.0427 | [−0.0082, +0.0959] |
| `tool_restriction` | +0.0244 | [−0.0495, +0.0955] |
| `resolve` | +0.0176 | [−0.0121, +0.0491] |
| `output_validation` | **−0.0197** | [−0.0583, +0.0164] |

The order changes between the two value functions, which is the point of computing both:
`coverage_check` leads on getting the refusal *right*, `trajectory_verify` on avoiding a wrong
number. `output_validation` is negative here — it costs correct refusals without buying safety —
though its interval crosses zero, so that is a direction to investigate rather than a finding.

---

## Experiment 5 — the reliability ladder, R0 to R9

**Question.** Experiment 2 compared two endpoints. Where *on the ladder* does each failure get
fixed, and what does each rung cost?

**Design.** Grounding held at rung 7. Every guardrail level from R0 (no refusal channel at all —
the agent must answer) to R9 (the full stack), one rung per row, in a single run so every cell is
directly comparable.

`run` — `./bench run --models gpt-5-mini --rungs 7 --rrungs 0,1,2,3,4,5,6,7,8,9 --repeats 3`
· 1,710 rows · 2026-07-27 · **$3.84** · 5 rows lost to provider errors

### The five outcomes, per rung

Every attempt lands in exactly one of five places. Group A (78 attempts) are questions that have
an answer; Group B (93) are questions that do not.

| | guardrail added | A: right ✓ | A: wrong ✗ | A: refused ✗ | B: refused ✓ | B: answered ✗ | cov | silent | bal |
|---|---|---|---|---|---|---|---|---|---|
| **R0** | `—` | 63 | 14 | 1 | 8 | 85 | 99% | **57.9%** | 45% |
| **R1** | `abstain` | 67 | 11 | 0 | 39 | 54 | 100% | **38.0%** | 64% |
| **R2** | `check_tools` | 63 | 12 | 3 | 56 | 37 | 96% | **28.7%** | 70% |
| **R3** | `coverage_check` | 66 | 8 | 4 | 62 | 31 | 95% | **22.8%** | 76% |
| **R4** | `tool_restriction` | 69 | 7 | 2 | 64 | 27 | 97% | **20.1%** | 79% |
| **R5** | `resolve` | 71 | 3 | 4 | 67 | 26 | 95% | **17.0%** | 82% |
| **R6** | `transparency` | 66 | 8 | 4 | 64 | 29 | 95% | **21.6%** | 77% |
| **R7** | `governed_numbers` | 63 | 5 | 10 | 77 | 15 | 87% | **11.8%** | 82% |
| **R8** | `output_validation` | 65 | 8 | 5 | 74 | 18 | 94% | **15.3%** | 82% |
| **R9** | `trajectory_verify` | 65 | 1 | 12 | 85 | 7 | 85% | **4.7%** | 88% |

The two columns marked ✗ in bold type are the ones a user cannot see: a wrong number, and a number
where none exists. `silent` is those two over all attempts — *ask it 100 questions, how often are
you confidently misled?*

### R0 is the honest zero point

With no refusal channel, the agent must answer. It answers **85 of the 93 questions that have no
answer**, and its silent error rate is **57.9%**. That is the number to hold next to every
"just add an LLM to your warehouse" pitch: not wrong occasionally — **misleading on more than half
of what it says**, with nothing on screen to distinguish those from the rest.

### The single biggest win is a tool description

**R0 → R1 drops silent error from 57.9% to 38.0%** — twenty points, and the only change is that
the agent is *given a way to say no*. No structural enforcement, no check on the answer; just a
`refuse` tool in the list and a prompt line describing it.

It is also the cheapest thing in the entire ladder, and it is what most deployed systems lack.

### The first six guardrails are nearly free

Coverage sits at **95–100% through R6** and only falls at R7 (87%) and R9 (85%). Meanwhile
fabrication falls from 85 to 29 over that same stretch.

> Two thirds of the fabrication is removed before you pay anything in answers.

That matters for adoption: the guardrails that cost coverage are the last two, so a team can take
most of the safety benefit without the argument about over-refusal.

### Two rungs go backwards, and one of them is corroborated

`transparency` (R6) worsens silent error 17.0% → 21.6%, and `output_validation` (R8) worsens it
11.8% → 15.3%. Both are within the ±3-row run-to-run variance measured elsewhere in this series,
so on this evidence alone they are flat rather than harmful.

But R8 agrees with Experiment 4, which scored `output_validation` at **−0.0058 on safety** by a
completely different method. Two independent measurements saying the same thing is worth more than
either alone: **output validation does not make answers safer.** It guarantees well-formedness — a
share cannot exceed 100, a count cannot be negative — which is a real property, and not this one.

### The endpoints

```
R0    coverage 99%    silent error 57.9%
R9    coverage 85%    silent error  4.7%
```

**Fourteen points of coverage for fifty-three points of silent error.**

## Changes to the harness during this series

Recorded because each one moves the model-visible surface, and runs either side of it are not
comparable.

| change | effect |
|---|---|
| The North Star became its own governed metric | the tree and the layer disagreed by 4% on the same word |
| The tree records its computed figures | 18 governed values per decomposition, previously invisible to every check |
| `governed_numbers` replaced `single_metric` | compare, don't compose — the diagnostic tier went 2/15 → 14/15 at R9 |
| The judge is shown the answer text | it was judging a bare number against a question |
| The judge settles what the number is *doing* first | answer vs evidence; 19 of 37 rejections were role confusion |
| The judge is shown the tree's causal edges | identity is exact, influence is correlational, a region is neither |
| The refusal vocabulary carries its meanings | twelve bare enum strings, guessed at 49% |
| `check_causal_evidence` returns UNKNOWN without a tree | it had been answering "NO — no causal evidence is encoded" |
