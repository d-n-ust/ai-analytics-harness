# The AI analyst needs a spine

A controlled lab experiment: build one small AI "analyst" that answers business
questions over data, then answer the **same questions five times** while changing
only the *structure* underneath it. Hold the model and the questions fixed. Watch
what each layer of structure buys you.

The claim being tested: **a modern model is already good enough. What it lacks is
not intelligence, it's context — and context is exactly the thing a data team
builds.**

> Companion to two essays: [Data Modelling in 2026](https://decisionspine.com/blog/data-modelling-in-2026)
> (the argument) and the write-up this repo is the evidence for (the experiment).

## The five rungs

Each rung adds exactly one thing to the *same* agent. Nothing else changes.

| # | Rung | What the agent gets | Failure it removes | Question type it unlocks |
|---|------|---------------------|--------------------|--------------------------|
| 1 | **Messy data** | raw tables: cryptic names, dirty values, no docs | — (baseline) | ~none reliably |
| 2 | **Star schema** | clean `dim_` / `fct_` models, sane names, typed values | wrong tables, hallucinated columns | simple lookups |
| 3 | **Semantic layer** | governed metrics + join paths (a YAML compiled to SQL) | wrong grain, ungoverned metric math | filtered / segmented metrics |
| 4 | **+ Knowledge base** | business glossary, rules, example question→query pairs | "the rules that live in Slack" — definitions, exclusions | definitional ("active user *here* means…") |
| 5 | **+ Metric tree** | the driver graph (identity + influence edges) | can't structure *why did X move* at all | diagnostic / root-cause |

Rungs 1–3 buy **accuracy**. Rung 4 buys **the definitions accuracy can't see**.
Rung 5 buys **usefulness** — the jump from "what was the number" to "why did it move."

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
cp .env.example .env && $EDITOR .env   # set ANTHROPIC_API_KEY
make eval         # the real experiment: 25 questions x 5 rungs x {small, large}
```

Ask a single question at a single rung:

```bash
make ask Q="how many active users do we have?" RUNG=3 MODEL=small
```

## How answers are graded

The 25 questions are tagged by tier (lookup / filtered / multi-join / definitional
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
grounding/    the five rungs: star models, semantic layer, knowledge base, metric tree
harness/      the agent: tool-loop, self-correction, semantic compiler, tree walk
eval/         the 25 questions, gold answers, and the grader
results/      generated results + the summary the write-up draws on
run.py        CLI: data | ask | eval
```

## Results

_Filled in after the run — see `results/summary.md`._

## License

MIT — see [LICENSE](./LICENSE).
