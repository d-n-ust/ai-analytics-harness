# Results — July 2026 series

A fresh results record, written as the runs land. It supersedes nothing: earlier numbers were
measured on a different question set and a different model-visible surface, and the two are not
comparable. Where an earlier figure is quoted here it is labelled as superseded and kept only to
show what moved.

**Status**

| # | Experiment | State |
|---|---|---|
| 1 | Grounding ladder — what structure buys | **done** (2026-07-26) |
| 2 | Reliability ladder — what guardrails buy | pending |
| 3 | Reasoning-effort sweep | pending |
| 4 | Shapley attribution | pending |

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

### What the metrics mean

- **coverage** — of the answerable questions, the share the agent actually answered.
- **precision** — of those it answered, the share that were right.
- **groundedness** — of the unanswerable questions, the share where it did *not* invent a number.
  This is the safety number.
- **yield** — correct rows over all rows, refusals included. A refusal of an unanswerable
  question counts as correct only if it also names the right reason.

---

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

## Experiment 2 — the reliability ladder

*Pending.* Holds grounding fixed and climbs the guardrail ladder, so the comparison to Experiment 1
is like-for-like on the same 57 questions.

Planned cells: rungs 3 and 7 at R9. R9 cannot run below rung 3 — every guardrail above abstention
acts on a semantic layer, and `incoherent()` refuses the pairing rather than producing rows whose
label overstates what ran.

The one number to hold in view, from a rung 7 · R9 run on the current question set (measured before
the vocabulary fix, so its yield will move):

```
rung 7 · R1   groundedness 69.0%   ← 27 fabrications
rung 7 · R9   groundedness 97.8%   ← 1 fabrication
```

Same grounding, same questions, same model. Grounding took fabrication from 36 to 27; guardrails
took it from 27 to 1.

---

## Experiment 3 — reasoning effort

*Pending.* Every run in this document uses `minimal`. Whether the findings survive a more capable
reasoning setting is untested, and it is the most obvious objection to all of it.

---

## Experiment 4 — Shapley attribution

*Pending.* Per-guardrail contribution over coherent coalitions. The previously published figures
(32 configurations, 120 orderings) are superseded — the coherence rules changed, and so did the
guardrail set: `single_metric` is now `governed_numbers`, a different rule with a different name.

---

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
