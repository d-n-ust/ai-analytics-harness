# The AI-Analyst Harness

A controlled lab for measuring what makes an LLM "analyst" **reliable** over data. Build one small
agent that answers business questions over a warehouse, then change **one thing at a time** —
holding the model and the questions fixed — and watch what it buys you.

Everything is generated deterministically and runs on a laptop. No warehouse to provision, one
DuckDB file, and a mock model so the whole loop works before you spend a cent.

```bash
make install && make data && make smoke     # end to end, no API key
```

> Companion essays: [How Much Does Grounding Actually Buy You?](https://decisionspine.com/blog/agentic-analytics-grounding)
> · [Teaching an AI Analyst to Say I Don't Know](https://decisionspine.com/blog/teaching-an-ai-analyst-to-say-i-dont-know)
> · [The Evidence Graph](https://decisionspine.com/blog/the-evidence-graph-teaching-an-ai-analyst-to-show-its-work)
> · [Data Modelling in 2026](https://decisionspine.com/blog/data-modelling-in-2026), the argument underneath all three.

## The five experiments

The first three vary one axis of the agent — what it *knows*, what it may *do*, what it must
*declare* — over the same **65 questions**. The last two freeze the agent and vary the warehouse
underneath it. Every delta is attributable to one change, not to prompt luck or question drift.

The first three are independent, not one ladder. A declaration is not "stricter" than a verifier, so
protocol crosses the guardrail cells rather than extending them, and "R5 with claims" is a cell you
can run.

**1 · Grounding** — how much does structure buy? Six rungs, each adding one layer: messy tables →
star schema → semantic layer → verified examples → knowledge base → metric tree.
*Six levels of structure take right answers from **36% to 85%**, and confidently-wrong answers from
only **52% to 31%**. Structure makes an agent capable much faster than it makes it honest.*
→ [`docs/GROUNDING.md`](docs/GROUNDING.md)

**2 · Reliability** — how much do guardrails cut confident-wrong answers, and let the agent refuse
safely? Ten rungs, R0 to R9, each switching on one guardrail.
*Silent error falls from **48.5% to 2.4%**. The single biggest win is the cheapest: adding a typed
`refuse` tool — no enforcement, just a move the model didn't have — is worth 17 points on its own.
An exact Shapley pass over all 24 coalitions then found one guardrail contributing **−0.0** while
firing 656 times, which no ladder could have shown.*
→ [`docs/RELIABILITY.md`](docs/RELIABILITY.md)

**3 · Protocol** — when every assertion must name the governed value it rests on, how much of an
answer can be *checked*, and does being asked for an account change the answer itself?
*It does not — a measured null, with its power stated. But citation repair moves grounded-answer
rate 87.2% → 94.7% and nothing else, which is the shape a mechanism predicts when it checks
citations and knows nothing about the business. And **73.7% of answers draw no conclusion at all**:
the graph captures the evidence and loses the argument.*
→ [`docs/EVIDENCE-GRAPH.md`](docs/EVIDENCE-GRAPH.md)

**4 · Repair** — when a question stacking several primitives fails, which primitive broke, and what
is the cheapest place to fix its grounding: implicit, documented, modelled, declared, or enforced?
62 questions against eight versions of one warehouse.
→ [`docs/REPAIR-MATRIX.md`](docs/REPAIR-MATRIX.md)

**5 · Ambiguity** — a static scan reads the definitions before any agent runs and predicts which
ones an agent could confuse. Does fixing what it flags remove the harm? One dbt-shaped warehouse
with models *and* a metrics layer over them, 36 questions, an agent holding both `query_metric`
and raw SQL, before and after the repair.
*The scan reports **11 findings before, 0 after**. Where the metrics layer governs the concept,
wrong-metric selection goes **24% → 0.00** for `gpt-5-mini` and **11% → 0.00** for `gpt-5.6-terra`,
in 93 answers each. Scale does not substitute for governed definitions: the larger model made no
construction errors and still picked a decoy metric one time in nine. Two problems the scan cannot
see — two undocumented staff flags and a stale `status` column — did the damage the repair could
not remove, and a third residue is new: asked for a count the layer governs no metric for, the
agent substitutes the nearest governed metric rather than writing SQL.*
→ [`harness/experiments/05_preflight_ambiguity/`](harness/experiments/05_preflight_ambiguity/)

[`docs/FINDINGS.md`](docs/FINDINGS.md) is the standing ledger — what is established, what is a
measured null, and what was tried and rejected. Every number is labelled with its n.

## Anatomy — what's inside

A canonical agent, named the way the field names it:

- **Orchestrator** (`engine/src/agent/loop.py`) — the control loop: call the model, run the tool it
  asks for, feed the result back, stop on a terminal tool. The part that is *not* the model.
- **Model** (`engine/src/agent/providers.py`) — the LLM, behind one interface (OpenAI / Anthropic /
  DeepSeek). The interchangeable part.
- **Tools** (`engine/src/agent/tools.py`) — the action space: governed metric queries, raw SQL
  (until `tool_restriction` removes it), answerability checks, and the three **terminal** tools
  `answer` / `refuse` / `clarify`, so every run ends in a *typed outcome*, never a sentence to grep.
- **Context** (`engine/src/agent/prompts.py`, over `warehouse/` · `semantic/` · `agent/context/`) —
  what the agent is given. This is the grounding axis.
- **Guardrails** (`engine/src/agent/guardrails/`) — what the system *enforces*, not behaviours the
  model chooses, grouped by where each sits in a request. This is the reliability axis.
- **Protocol** (`engine/src/agent/protocol.py`) — what the answer must *declare* about its own work.
  A peer of the guardrail set, not a part of it. This is the evidence-graph axis.
- **Evidence layer** (`engine/src/evidence/`) — resolves every declaration against the trace it was
  built from. It **decides nothing**: no verdict, no refusal, no downgrade. That is what keeps it an
  instrument rather than a second judge, and why its numbers need no gold answers.
- **Memory** — none, by design: each question is a fresh conversation.

[`docs/ANATOMY.md`](docs/ANATOMY.md) is the full file→component map.

## The dataset

A synthetic but realistically messy consumer habit app: users, habits, completions, sessions,
subscriptions, referrals, marketing spend, notifications. The raw layer is deliberately hostile —
cryptic column names, inconsistent enums (`ios`/`iOS`/`1`), internal and test users mixed into
production, status codes instead of labels, and grain traps that silently double numbers.

A known anomaly is injected into the most recent week, so the diagnostic questions have a
*computable* correct root cause rather than a vibe. Everything comes from a fixed seed.

→ [`docs/DATA.md`](docs/DATA.md)

## Run it

```bash
make install      # uv sync
make data         # generate runs/warehouse.duckdb (deterministic)
make smoke        # the full grid on a mock model — no API key needed
make test         # the no-LLM suite

cp .env.example .env && $EDITOR .env    # OPENAI_API_KEY / ANTHROPIC_API_KEY / DEEPSEEK_API_KEY
make eval         # the real thing: 65 questions x 6 rungs x 2 models x 5 reps
```

Everything runs through one CLI — `./bench <verb>`, a thin wrapper over `python -m cli`:
`data · verify · query · ask · run · regrade · report · trace · chain · study · context · health ·
ambiguity · test`.

```bash
./bench ask "how many active users?" --rung 3 --mock       # one question, no key, no cost
./bench run --rungs 3 --rrungs R0,R1,R3,R4,R7,R9           # climb the guardrail ladder
./bench run --rungs 3 --cells R9,R9-resolve                # R9 vs R9-minus-one-guardrail
./bench run --rungs 7 --cells R9 --protocols none,claims   # what declaring buys
./bench chain <qid> --run runs/latest                      # question -> evidence -> answer, no verdict
./bench ambiguity                                          # confusable governed names, from the YAML alone
./bench study                                              # the repair-matrix studies
```

**Models.** The reliability write-up runs on `gpt-5-mini` and compares against `gpt-5.6-terra` and
`gpt-5.6-sol`. `gpt-5.4-mini`, `gpt-5.6-luna`, `gpt-4.1-mini`, `claude-haiku-4-5`,
`claude-sonnet-5`, `deepseek-v4-flash` and `deepseek-v4-pro` are wired up too — swap any into
`--models`.

Reasoning effort is a **ladder per model, not a floor**: `gpt-5-mini` accepts `minimal/low/medium/
high` and 400s on `none`; the `gpt-5.6` models accept `none/low/medium/high/xhigh` and 400s on
`minimal`. Neither is a prefix of the other, so a model runs at its nearest accepted effort and the
row records what was actually sent (`engine/src/agent/models.py`).

## How answers are graded

Every run ends in one typed outcome, so grading never phrase-matches prose. Each case declares in
YAML what a correct response *is*; the grader reads that rather than inferring it from the tier.
Scoring is **selective prediction** — coverage, silent error rate and balanced accuracy, three
numbers never pooled into one, because an agent that may decline cannot be judged on accuracy alone.

The gold set is treated as fallible, and the LLM verifier is scored rather than trusted.

→ [`docs/GRADING.md`](docs/GRADING.md)

## Layout

Three roles at the top level, and a directory belongs to exactly one: the code that ships, the
apparatus that measures it, and the product built on it.

```
engine/       WHAT SHIPS. Installable on its own; troodos depends on this and nothing else.
  src/agent/       the agent: loop, prompts, tools, model adapters, guardrails, protocol.
                   `context/` sits inside it — the verified examples and knowledge base are
                   package data, and a wheel that leaves them behind assembles a short prompt
  src/semantic/    the governed model: the semantic layer (metrics/segments) + the metric tree
  src/warehouse/   the data platform: generator, DuckDB I/O, star schema (dim_/fct_ views)
  src/evidence/    what an answer DECLARED, resolved against its trace. Decides nothing.
  tests/           tests that import nothing but engine packages

harness/      WHAT MEASURES IT. Never ships, never installed by anyone but the maintainer.
  evals/           the 65 questions (cases/), gold answers, the grader, report.py
  experiments/     pre-registrations + findings logs
  cli/             the `bench` entry point (one dispatcher over every verb)
  scratchpad/      one-off analyses
  harness_paths/   the one definition of where the repo root, runs/ and results/ are
  tests/           tests that may import anything, including repo-shape assertions

troodos/      THE PRODUCT. Its own package, environment and lockfile.
results/      Tracked evidence behind the write-ups, cited by essays at these exact paths.
runs/         Everything a run regenerates. Gitignored; `make clean` is `rm -rf runs/`.
docs/         the experiments, the architecture, and the findings ledger
```

The one rule that keeps it honest: **nothing under `engine/` may import the apparatus.** When the
engine needs something the harness has, the harness passes it in — `ask_one` takes a renderer rather
than importing the CLI's. `harness/tests/test_structural.py` walks the import graph, including
function-local imports, and fails on any edge in the wrong direction.

## What this is and isn't

- It **is** a minimal, honest, reproducible measurement of how much structure and how many
  guardrails help a capable model.
- It is **not** a vendor benchmark or a claim about any product. Numbers computed here are computed
  in code; the model writes queries, it never invents a figure.
- Results are reported as they came out, including the surprises and the nulls, and labelled with
  their n. Re-running a cell moves it a point or two, and the write-ups print two runs of the same
  configuration so a reader can see how much.

Every published figure lives in [`results/published/2026-07-reliability-ladder/`](results/published/2026-07-reliability-ladder/) — 70
cells across the 12 runs the write-ups cite, regenerable with
`harness/evals/components/publish_metrics.py`. The four runs whose raw rows back a claim the tables
cannot express are in `2026-07/runs/`, gzipped with traces intact.

## License

MIT — see [LICENSE](./LICENSE).
