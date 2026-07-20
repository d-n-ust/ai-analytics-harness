# Agentic Analytics: How Much Does Grounding Actually Buy You?

A controlled lab experiment: build one small AI "analyst" that answers business
questions over data, then answer the **same questions at each of six levels of
structure**, changing only that structure. Hold the model and the questions fixed. Watch
what each layer of structure buys you.

The claim being tested: **a modern model is already good enough. What it lacks is
not intelligence, it's context — and context is exactly the thing a data team
builds.**

> Companion to two essays: [Data Modelling in 2026](https://decisionspine.com/blog/data-modelling-in-2026)
> (the argument) and [Agentic Analytics: How Much Does Grounding Actually Buy You?](https://decisionspine.com/blog/agentic-analytics-grounding)
> (the experiment this repo is the evidence for).

## The six rungs

Each rung adds exactly one thing to the *same* agent. Nothing else changes.

| # | Rung | What the agent gets | Failure it removes | Question type it unlocks |
|---|------|---------------------|--------------------|--------------------------|
| 1 | **Messy data** | raw tables: cryptic names, dirty values, no docs | — (baseline) | ~none reliably |
| 2 | **Star schema** | clean `dim_` / `fct_` models, sane names, typed values | wrong tables, hallucinated columns | simple lookups |
| 3 | **Semantic layer** | governed metrics + join paths (a YAML compiled to SQL) | wrong grain, ungoverned metric math | filtered / segmented metrics |
| 4 | **+ Verified examples** | approved question→query pairs, each a scoped call into the governed metrics | vague phrasings and world-facts a metric can't hold (the APAC launch cutoff, the partnerships test channel) | business-knowledge questions |
| 5 | **+ Knowledge base** | the *same* business rules again, as free-text prose (stacked on the examples) | — (the control: does prose deliver what an example does?) | none it didn't already |
| 6 | **+ Metric tree** | the driver graph (identity + influence edges) | can't structure *why did X move* at all | diagnostic / root-cause |

Rungs 1–3 buy **accuracy**. Rung 4 buys **the definitions and world-facts accuracy can't
see**, delivered as concrete, scoped examples. Rung 5 re-delivers the *same* knowledge as
free-text prose to test one thing — does prose hold up as reliably as an example? (In the runs
it never does.) Rung 6 buys **usefulness**: the jump from "what was the number" to "why did it
move."

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

## Run it

```bash
make install      # uv sync
make data         # generate data/warehouse.duckdb (deterministic)
make smoke        # end-to-end on a mock model — no API key needed
# add your key:
cp .env.example .env && $EDITOR .env   # set OPENAI_API_KEY (and ANTHROPIC_API_KEY for the claude-* models)
make eval         # the real experiment: 25 questions x 6 rungs x 2 models x 5 reps
```

Ask a single question at a single rung:

```bash
make ask Q="how many active users do we have?" RUNG=3 MODEL=gpt-5.6-terra
```

The write-up runs two OpenAI models five times each (`--repeats 5`, for the error bars):
**gpt-5.6-terra** (the flagship) and **gpt-5.4-mini** (the cheap one). Anthropic **claude-haiku-4-5**
and **claude-sonnet-5** are wired up too — swap any into `--models`.

## How answers are graded

The 25 questions are tagged by tier (lookup / filtered / metric / knowledge
/ diagnostic). Each has a hand-written gold SQL, a gold number, and a tolerance
note. Grading is deliberately layered, because "did the SQL run" is not "is this
the right business answer":

1. **Executed?** — did it return a result at all.
2. **Correct within tolerance?** — numeric match against the gold answer.
3. **Right for the right reason?** — an LLM-judge pass for the diagnostic tier,
   scored against a gold decomposition (which driver moved, direction, rough size).

The gold set is treated as fallible and sanity-checked — benchmark "gold" answers
are wrong more often than anyone admits.

## What this is and isn't

- It **is** a minimal, honest, reproducible measurement of how much structure
  helps a capable model, built with a few hundred lines of Python and SQL.
- It is **not** a vendor benchmark or a claim about any product. Numbers computed
  here are computed in code; the model writes queries, it never invents a figure.
- Results are reported as they came out, including the surprises.

## Layout

```
data/         synthetic warehouse generator (messy raw + clean star)
grounding/    per-rung grounding: star schema, semantic layer, verified examples, knowledge base, metric tree
harness/      the agent: tool-loop, self-correction, semantic compiler, tree walk
evaluation/   the 25 questions, gold answers, and the grader
results/      summary.md the write-up draws on (raw rows regenerate with make eval)
run.py        CLI: data | ask | eval
```

## Results

The full run — 2 models × 6 rungs × 25 questions × 5 reps — is in
[`results/summary.md`](results/summary.md). Accuracy climbs as structure is added, and each jump
lands on a rung:

| rung | gpt-5.6-terra | gpt-5.4-mini |
|---|---|---|
| 1 · messy data | 40% ± 6 | 22% ± 2 |
| 2 · star schema | 46% ± 4 | 34% ± 4 |
| 3 · semantic layer | 66% ± 4 | 54% ± 7 |
| 4 · + verified examples | 81% ± 2 | 77% ± 4 |
| 5 · + knowledge base | 78% ± 2 | 75% ± 3 |
| 6 · + metric tree | 92% ± 3 | 78% ± 5 |

- **The semantic layer is the turning point** — the biggest jump (rung 2→3) is where the model
  stops guessing definitions.
- **Verified examples deliver business knowledge; a free-text knowledge base doesn't** — rung 5
  never beat rung 4 across five runs (it cost ~2 points), the only rung that never earned its place.
- **"Why did it move" needs the metric tree** — gpt-5.6-terra's diagnostic answers go from 3/25 at the
  semantic layer to 18/25 with the tree; gpt-5.4-mini can read a governed number but still can't reason
  about the why (8/25).

Numbers are one 5-rep run; re-running moves them a point or two (the ± is that spread). The
write-up this backs: **[Agentic Analytics: How Much Does Grounding Actually Buy You?](https://decisionspine.com/blog/agentic-analytics-grounding)**.

## License

MIT — see [LICENSE](./LICENSE).
