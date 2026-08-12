# The AI-Analyst Harness

A controlled lab for measuring what makes an LLM "analyst" **reliable** over data. Build one
small agent that answers business questions over a warehouse, then change **one thing at a time**
— holding the model and the questions fixed — and watch what it buys you.

The harness runs **four experiments on the same rig**. The first three each vary one axis of the
agent — what it *knows*, what it may *do*, and what it must *declare*. The fourth freezes the agent
and varies the **warehouse it reads**:

1. **Grounding** — how much does *structure* (a schema, a semantic layer, a knowledge base, a
   metric tree) improve a capable model's answers? *The six-rung grounding ladder.*
2. **Reliability** — how much do *guardrails* (a typed refusal channel, a coverage check, a
   governed-only data path, an answer verifier) cut **confident-wrong** answers and let the agent **refuse
   safely** when it should? *The R0–R9 guardrail ladder.* Includes an **attribution** pass that runs
   every coherent combination of the six independent guardrails and computes an exact Shapley value
   per guardrail — because a ladder cannot say which rung did the work.
3. **Protocol** — when every assertion has to name the governed value it rests on, how much of a
   served answer can be *checked* — and does being asked for an account change the answer itself?
   *The evidence graph.*
4. **Repair** — when a question that stacks several primitives fails, which primitive broke, and
   what is the cheapest location — implicit, documented, modelled, declared, enforced — where its
   grounding reliably holds? *The repair matrix: 62 questions against eight versions of one
   warehouse (`experiments/04_repair_matrix/`).*

The first three are independent, not one ladder. A declaration is not "stricter" than a verifier, so
protocol crosses the guardrail cells rather than extending them, and "R5 with claims" is a cell you
can run.

Each of the first three adds exactly one thing to the *same* agent and re-answers the **same 65
questions**. The fourth inverts the design: the agent is frozen and the warehouse changes under it,
one grounding location at a time, over its own 62-question set. Either way nothing else changes, so
every delta is attributable to that one change — not to prompt luck or question drift.

> Companion essays: [Agentic Analytics: How Much Does Grounding Actually Buy You?](https://decisionspine.com/blog/agentic-analytics-grounding)
> (the grounding experiment), [Agentic Analytics: Teaching an AI Analyst to Say I Don't Know](https://decisionspine.com/blog/teaching-an-ai-analyst-to-say-i-dont-know)
> (the reliability experiment) and [The Evidence Graph: Teaching an AI Analyst to Show Its Work](https://decisionspine.com/blog/the-evidence-graph-teaching-an-ai-analyst-to-show-its-work)
> (the protocol experiment), with [Data Modelling in 2026](https://decisionspine.com/blog/data-modelling-in-2026)
> as the argument underneath all three.

## Anatomy — what's inside

A canonical agent, named the way the field names it:

- **Orchestrator** (`agent/loop.py`) — the control loop: call the model, run the tool it asks
  for, feed the result back, stop on a terminal tool. The part that is *not* the model.
- **Model** (`agent/providers.py`) — the LLM, reached by an external API call (OpenAI / Anthropic /
  DeepSeek behind one interface). The interchangeable part.
- **Tools** (`agent/tools.py`) — the action space: governed metric queries, raw SQL (until
  `tool_restriction` removes it), answerability checks, and the three **terminal** tools `answer` / `refuse` /
  `clarify`, so every run ends in a *typed outcome*, never a sentence to grep.
- **Context** (`agent/prompts.py` + `agent/rungs.py`, over `warehouse/` · `semantic/` · `agent/context/`) — what the agent is
  given: the star schema, the semantic layer, verified example queries, the knowledge base, the
  metric tree. This is the grounding-ladder axis.
- **Guardrails** (`agent/guardrails/`) — the reliability stack, grouped by where each sits in a
  request: the coverage check, the tool restriction, member resolution, governed_numbers, output validation, the trajectory
  verifier. What the system *enforces*, not behaviours the model chooses. This is the
  reliability-ladder axis.
- **Protocol** (`agent/protocol.py`) — what the answer must *declare* about its own work: a purpose
  per governed call, one claim per assertion, each naming the governed value it rests on. A peer of
  the guardrail set, not a part of it. This is the evidence-graph axis.
- **Evidence layer** (`evidence/`) — resolves every declaration against the trace it was built from.
  It **decides nothing**: no verdict, no refusal, no downgrade. That is what keeps it an instrument
  rather than a second judge, and it is why its numbers need no gold answers.
- **Memory** — none, by design: each question is a fresh conversation.
- **Observability** — typed outcomes + an expect-driven grader (below).

## The dataset

A synthetic but realistically messy consumer habit app: users,
habits, habit completions, sessions, subscriptions, referrals, marketing spend,
notifications. The raw layer is deliberately hostile — cryptic column names,
inconsistent enums (`ios`/`iOS`/`1`), internal/test users mixed into production,
status codes instead of labels, and grain traps that silently double numbers. A
known anomaly is injected into the most recent week so the diagnostic questions
have a *computable* correct root cause, not a vibe.

Everything is generated deterministically from a fixed seed, so the whole thing
reproduces on a laptop with no warehouse to provision (DuckDB, one file).

## Experiment 1 — the grounding ladder

Each rung adds exactly one layer of structure to the *same* agent.

| # | Rung | What the agent gets | Failure it removes | Unlocks |
|---|------|---------------------|--------------------|---------|
| 1 | **Messy data** | raw tables: cryptic names, dirty values, no docs | — (baseline) | ~none reliably |
| 2 | **Star schema** | clean `dim_`/`fct_` models, typed values | wrong tables, hallucinated columns | simple lookups |
| 3 | **Semantic layer** | governed metrics + join paths (YAML → SQL) | wrong grain, ungoverned metric math | filtered / segmented metrics |
| 4 | **+ Verified examples** | approved question→query pairs | vague phrasings, world-facts a metric can't hold | business-knowledge questions |
| 5 | **+ Knowledge base** | the *same* rules again, as free-text prose | — (the control: does prose match an example?) | none it didn't already |
| 6 | **+ Metric tree** | the driver graph (identity + influence edges) | can't structure *why did X move* | diagnostic / root-cause |

Rungs 1–3 buy **accuracy**; rung 4 buys **the definitions and world-facts accuracy can't see**;
rung 5 re-delivers the same knowledge as prose to test whether prose holds up (in the runs it never
beats the example); rung 6 buys **usefulness** — the jump from "what was the number" to "why it moved."

## Experiment 2 — the reliability ladder

The grounding ladder makes the agent *capable*. The reliability ladder makes it *trustworthy* —
answer when the data supports it, and **refuse with a typed reason** when it does not, instead of
serving a confident wrong number. Each rung switches on one guardrail (`agent/guardrails/__init__.py`):

| Rung | Guardrail | What it stops |
|---|---|---|
| R0 | — | no refusal channel (baseline: it must answer) |
| R1 | **abstain** | adds the typed `refuse` tool (coded reason + what's missing) |
| R2 | **check_tools** | answerability checks the model may call first |
| R3 | **coverage_check** | blocks out-of-coverage / ungoverned governed calls |
| R4 | **tool_restriction** | removes raw SQL; every data path is a governed call |
| R5 | **resolve** | filter values must resolve to governed members |
| R6 | **transparency** | shows the compiled SQL and a plain scope line |
| R7 | **governed_numbers** | compare, don't compose: the served number is a governed result, or a comparison of two of the *same* metric |
| R8 | **output_validation** | the returned value must be well-formed |
| R9 | **trajectory_verify** | an LLM verifier checks the metric actually answers the question |

Because the guardrails are *independent flags*, the harness can run the cumulative ladder **or** any
individual ablation cell, so a guardrail's contribution can be measured where it functions. The **35
reliability-tier questions** (`valid_but_wrong`, `adversarial`, `unanswerable`, `rt_phantom`,
`false_premise`) are where the guardrails discriminate; the **30 answerable-tier questions** are
shared with the grounding experiment.

Scoring is **selective prediction** — an agent that may decline cannot be judged on accuracy alone,
since refusing everything scores perfectly on what it answers. Three numbers, never pooled into one
(`evals/selective.py` is the single definition):

| | |
|---|---|
| **coverage** | of the questions that *have* an answer, the share it attempted |
| **silent error rate** | of everything asked, the share where it served a confident number that was false — a wrong answer, or an answer to a question that had none |
| **balanced accuracy** | the mean of the two families' accuracies, so the score describes the agent rather than how many of each kind of question the suite happens to contain |

### Attribution — which guardrail actually did the work?

The ladder cannot say, because every rung is only ever seen stacked on the ones below it. R9 minus
one guardrail answers "what does removing it cost *here*", which is a different question. So the
harness runs **every coherent combination** of the six independent guardrails and computes an exact
Shapley value per guardrail — the average marginal contribution over all orderings, with the
efficiency axiom (the parts must sum to the whole) checked to floating point. *24 coalitions, 4,104
answers.*

This is an analysis of the ladder above, not an axis of its own, which is why it sits here rather
than as an experiment. The finding it produced that no ladder could — one guardrail contributing
exactly nothing while firing 656 times — is in [Results](#results).

## Experiment 3 — the evidence graph

The two ladders judge an answer as one thing. An answer is not one thing: a diagnostic reply averages
~5 assertions, and only the single declared number was ever checked. One live run served nine
assertions, had one verified, and declared it under a metric it had not used. It graded correct.

So the third experiment asks the answer to **declare its own structure**. Every successful tool
result carries a handle (`r1`, `r2`), and a result holding many numbers is addressed one value at a
time — `r1:days_per_user.pct_change`, never a bare `r1`. Each assertion then names either:

- **`sources`** — the governed values it was read off, or
- **`premises`** — the earlier claims it was concluded from.

Carrying both is itself a defect: a claim is read from evidence or derived from claims, and mixing
the two hides the distinction the graph exists to draw.

| Switch | What the answer must declare |
|---|---|
| **`purpose`** | one line per governed call on what it is for |
| **`claims`** | one claim per assertion, each naming the value it rests on |
| **`repair`** | a citation naming nothing is handed back, bounded, before the answer is served |
| **`rendered`** | the harness writes each measurement's sentence from the cited values, so a measurement *cannot* carry an argument |

Each is switched separately (`--protocols claims+repair`), and a `rule` / `role` framing varies
whether being checkable is presented as a field to fill in or as part of the analyst's job.

**Why this is a different kind of metric.** Coverage, silent error and balanced accuracy all need
someone to have written the right answer down first. The evidence graph needs no gold: every check is
a lookup against the trace, so **grounded-answer rate** — the share of served answers whose every
citation resolves — computes on a client's question where no answer key will ever exist. It is
reported *beside* the three above and never averaged into them; "was it right" and "can it be
inspected" are different questions, and their mean answers neither.

Three things it sees that nothing above it can:

- **Claim support.** Whether each declared citation resolves, and whether a stated figure is one the
  cited values support. Deterministic — a broken citation is broken, no judge required. Every
  attribution metric in the literature is judge-dependent because citations point at *text*; these
  point at *query results*, so resolution is a dictionary lookup.
- **Semantic-model defects.** Confusable metric names, unsupported dimensions, missing grains and
  weak causal edges stop being private model mistakes and become counts a data team can act on.
  `./bench ambiguity` finds the dangerous pairs from the YAML alone, before a run: `value_moments`
  and `real_value_moments` agree on all six facets of *what* they measure and differ only in scope,
  so their figures land a quarter-point apart and no numeric check separates them.
- **Whether the answer contains an argument at all.** The uncomfortable one: across 1,405 served
  answers carrying a graph, **73.7% drew no conclusion** — a flat list of cited measurements with the
  diagnosis left in the prose beside the graph. Seventeen reached two levels of inference.

`./bench chain --run <dir>` renders any stored row the way a reader would read it: the question, what
was asked of the data, what the answer claims, and what each claim rests on. It prints **no verdict**
— no score, no band, no colour meaning "trust this". The first working version stamped `NOT SUPPORTED`
across a substantively correct answer because the model had typed `value_moments` where it meant
`weekly_value_moments`. The defect was real; the verdict was a smoke alarm going off at toast, and a
reader who sees one wrong red badge stops believing the green ones.

## Run it

```bash
make install      # uv sync
make data         # generate warehouse/warehouse.duckdb (deterministic)
make smoke        # end-to-end on a mock model — no API key needed
# add your key:
cp .env.example .env && $EDITOR .env   # OPENAI_API_KEY (and ANTHROPIC_API_KEY / DEEPSEEK_API_KEY as needed)
make eval         # the grounding experiment: 65 questions x 6 rungs x {gpt-5.6-terra,gpt-5.4-mini} x 5 reps
```

Everything runs through one CLI — `./bench <verb>` (a thin wrapper over `python -m cli`):
`data · verify · query · ask · run · regrade · report · trace · chain · ambiguity · test`. Vary the
**reliability** ladder with `--rrungs`, or run explicit ablation cells with `--cells`:

```bash
./bench run --rungs 3 --rrungs 0,1,3,4,7,9    # hold grounding fixed, climb the guardrail ladder
./bench run --rungs 3 --cells R9,R9-resolve   # R9 vs R9-minus-one-guardrail
./bench ask "how many active users?" --rung 3 --guardrails R9   # one question at any cell
```

Cross either ladder with the **protocol** axis, and read one answer's graph back:

```bash
./bench run --rungs 7 --cells R9 --protocols none,claims,claims+repair   # what declaring buys
./bench ask "why did value moments fall?" --rung 6 --protocol claims --trace
./bench chain --run results/latest        # the question -> evidence -> answer chain, no verdict
./bench ambiguity                         # confusable governed names, from the YAML alone
```

Ask a single question at one rung:

```bash
make ask Q="how many active users do we have?" RUNG=3 MODEL=gpt-5.6-terra
```

Models. The reliability write-up runs on **gpt-5-mini** (the cheap one it was built to stress) and
compares against **gpt-5.6-terra** and **gpt-5.6-sol**, the two larger models in that family.
**gpt-5.4-mini**, **gpt-5.6-luna**, **gpt-4.1-mini**, Anthropic **claude-haiku-4-5** /
**claude-sonnet-5** and **deepseek-v4-flash** / **deepseek-v4-pro** are wired up too — swap any into
`--models`.

Reasoning effort is a **ladder per model, not a floor**: `gpt-5-mini` accepts
`minimal/low/medium/high` and 400s on `none`; the `gpt-5.6` models accept `none/low/medium/high/xhigh`
and 400s on `minimal`. Neither is a prefix of the other, so a model runs at its nearest accepted
effort and the row records what was actually sent (`agent/models.py`).

## How answers are graded

Every run ends in one **typed outcome** — `answer`, `refuse`, or `clarify` — so grading never
phrase-matches prose. Each of the 65 cases declares in YAML what a correct response *is* (an
`expect` block); the grader reads that, it never infers the expected outcome from the tier:

- **`metric_answer`** — a number within tolerance of an independent gold SQL, from the right
  governed metric (when the model declares its `source_metric`).
- **`refuse`** — a refusal carrying the expected **coded reason**; for such a case *any* served
  number is a miss (a confident-wrong, or a right number reached off-governance = a fabrication).
- **`diagnostic`** / **`keywords`** — named the right driver / the right metric (an LLM judge for the
  diagnostic tier, scored against a gold decomposition).

Every response reduces to one bucket — **right / wrong / I-don't-know / deferred / other / error** —
reported per rung. `confident_wrong` and `fabricated` are tracked separately and reported on their
own denominators, never pooled. The gold set is treated as fallible and sanity-checked — benchmark
"gold" is wrong more often than anyone admits.

**The verifier is scored, not trusted.** On the ladder run's R9 cell it made 58 decisions, stopped
12 answers, and none of the 12 was a correct answer. It let one bad answer through: *"how many users
do we have in total?"*, answered off a signups metric — a real number to a question nobody asked,
which is the failure the whole experiment is about. Those four counts are columns in
`results/published/2026-07/cells.csv` (`judge_ran`, `judge_rejected`, `judge_blocked_good`,
`judge_passed_bad`), so the claim is checkable rather than asserted. An earlier blind 3-judge panel
(n=37) is **invalidated** and must not be quoted: 7 of its 37 cases were labelled against a corrupted
evidence field, and the run metadata carries `"stale": true` saying so.

Because the claim audit is a pure lookup over the trace, `./bench regrade --run <dir>` re-derives
every verdict on a finished run **with no model calls**. The model's outputs are immutable; only what
is read from them changes. That is how a fix to the grader or the audit reaches numbers already
measured, instead of costing a re-run.

## What this is and isn't

- It **is** a minimal, honest, reproducible measurement of how much structure and how many guardrails
  help a capable model, built with a few hundred lines of Python and SQL.
- It is **not** a vendor benchmark or a claim about any product. Numbers computed here are computed
  in code; the model writes queries, it never invents a figure.
- Results are reported as they came out, including the surprises, and labelled with their n.

## Layout

```
warehouse/    the data platform: generator, DuckDB I/O, star schema (dim_/fct_ views)
semantic/     the governed model: the semantic layer (metrics/segments) + the metric tree
agent/context/  what the agent is GIVEN: verified example queries + the knowledge base (text, no
              code). Inside the package because they are package data: a wheel that leaves them
              behind assembles a prompt that is silently short.
agent/        the agent: orchestrator loop, prompt/context assembly, tools, model adapters,
              guardrails, the answer verifier, and the declaration protocol
evidence/     what an answer DECLARED, resolved against the trace it was built from, and the
              question -> evidence -> answer chain a reader is shown. Pure lookups, no model — and
              it decides nothing, which is what keeps it an instrument rather than a second judge
evals/        the 65 questions (cases/), gold answers, the grader, and report.py (summary.md/json)
cli/          the `bench` entry point (one dispatcher over every verb)
experiments/  pre-registrations + findings logs
docs/         ANATOMY · DATA · GROUNDING · RELIABILITY · REPAIR-MATRIX · RESULTS-2026-07 ·
              ARCHITECTURE · EVIDENCE-GRAPH · TRUST-MODEL · ONTOLOGY · FINDINGS
results/      published/ = the evidence behind the write-ups (cells/tiers/tools CSVs + the
              runs whose raw rows back a claim); runs/ is gitignored and regenerates
```

See [`docs/ANATOMY.md`](docs/ANATOMY.md) for the file→component map, and
[`docs/GROUNDING.md`](docs/GROUNDING.md) / [`docs/RELIABILITY.md`](docs/RELIABILITY.md) /
[`docs/EVIDENCE-GRAPH.md`](docs/EVIDENCE-GRAPH.md) / [`docs/REPAIR-MATRIX.md`](docs/REPAIR-MATRIX.md)
for the experiments.
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) says why declaring is a third axis rather than a
guardrail rung; [`docs/TRUST-MODEL.md`](docs/TRUST-MODEL.md) says what the evidence layer is
eventually meant to compute and why those numbers must never be averaged with the ones above;
[`docs/FINDINGS.md`](docs/FINDINGS.md) is the standing ledger of what is established, what is a
measured null, and what was tried and rejected.

## Results

Every published figure lives in [`results/published/2026-07/`](results/published/2026-07/) — 70 cells
across the 12 runs the write-ups cite, one row per (run, rung, config), regenerable with
`evals/components/publish_metrics.py`. The four runs whose *raw* rows back a claim the tables can't
express (replaying a judge call, re-deriving a coalition value) are in `2026-07/runs/`, gzipped with
traces intact.

**Grounding.** The qualitative findings are robust across runs:

- **The semantic layer is the turning point** — the biggest jump (rung 2→3) is where the model
  stops guessing definitions.
- **Verified examples deliver business knowledge; a free-text knowledge base doesn't** — rung 5
  never beat rung 4, the only rung that never earned its place.
- **"Why did it move" needs the metric tree** — diagnostic answers jump sharply once the tree is added.

Measured on the 57-question set (`gpt-5-mini`, 3 reps, refuse tool available throughout), six levels
of structure take right answers from **36% to 85%** — and confidently-wrong answers from only **52%
to 31%**. Structure makes the agent capable much faster than it makes it honest. (The suite has since
grown to 65; the eight additions are deliberately harder, so these percentages are not comparable to
a fresh run of the current set.)

**Reliability.** Same top-rung grounding, one guardrail at a time:

| | silent error | coverage | balanced accuracy |
|---|---|---|---|
| **R0** no refusal channel | **48.5%** | 99% | 53% |
| **R1** the typed `refuse` tool, nothing else | **31.0%** | 100% | 70% |
| **R9** all nine guardrails | **2.4%** | 85% | 90% |

- **The single biggest win is the cheapest.** R0→R1 is 17 points of silent error for a tool
  description — no enforcement, no checking, just a move the model didn't have before.
- **The first six rungs are close to free.** Coverage never falls below 94.9% through R6, against
  98.7% at R0, while invented answers fall from 69 to 20.
- **Honesty is built, not prompted.** Half of what R0 says is a confident invisible error; the same
  model with the stack around it is at 2.4%.

**Attribution** (exact Shapley, 24 coalitions, 3,000 bootstrap resamples). Only two guardrails have
an interval that clears zero on silent error: `trajectory_verify` (+8.8 points) and `coverage_check`
(+5.2). `governed_numbers` (+4.2) and `tool_restriction` (+4.1) do real work but overlap.
`output_validation` contributes **−0.0** — across 5,814 answers it fired 656 times and refused
nothing, ever, because all three of its checks are already guaranteed by layers beneath it. A stack
accumulates redundant checks, and no passing test suite will tell you.

**A bigger model does not fix it.** At R9, `gpt-5-mini` scores 90% balanced accuracy for $0.33 a run;
`gpt-5.6-terra` scores 90% for $0.80; `gpt-5.6-sol` scores **88%** for $1.73. The larger models make
no mistakes at all — zero wrong numbers, zero inventions — and lose by declining more answerable
questions. Past the point where guardrails have bought honesty, model size buys caution.

**The evidence graph.** What has held up across runs, nulls included
([`docs/FINDINGS.md`](docs/FINDINGS.md) is the full ledger):

- **Asking for an account does not measurably change the answer.** Every difference against the same
  cell without claims is within noise. Recorded as a null *with its power stated*: at 78 answerable
  questions per arm it could only ever have caught a large effect. It costs ~50% more output tokens.
- **Citation repair moves the fourth number and only the fourth** — grounded-answer rate 87.2% →
  94.7%, while balanced accuracy moved 0.6. That is the shape a mechanism predicts when it checks
  citations and knows nothing about the business question. Replicated across two independent sweeps.
- **It repairs rather than deletes.** A broken citation has two cheap fixes and only one is intended;
  recording what went *in* as well as what came out separates them. No handed-back answer came back
  smaller.
- **The graph captures the evidence and loses the argument.** Seven in ten answers contain no
  conclusion at all — the single largest open problem on this axis. The lever that moves it
  (`rendered`) is currently confounded with its framing, which makes it the most valuable unrun
  experiment here.
- **Two mechanisms were tested and rejected**, and are kept as rejected: orphan repair (the signal is
  Simpson's paradox, and its cheapest compliance is *deleting* the evidence) and broken citations as
  a correctness predictor (same trap, found the same way).

Every number is labelled with its n; re-running a cell moves it a point or two, and the write-up
prints two runs of the same configuration so a reader can see how much.

## License

MIT — see [LICENSE](./LICENSE).
