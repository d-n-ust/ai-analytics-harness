# results/published/ — the evidence behind the write-up

Curated results a Decision Spine write-up cites, committed so a reader can check the numbers.
Disposable dev runs live in `runs/` (gitignored) and regenerate with a run.

## 2026-07 — the reliability series

Backs *Agentic Analytics: Teaching an AI Analyst to Say I Don't Know*.

**`2026-07/*.csv`** — every published rate, one row per cell. Regenerate with:

```
PYTHONPATH=. uv run python evals/components/publish_metrics.py \
    results/published/2026-07 runs/<run> [...]
```

| file | grain | what it answers |
|---|---|---|
| `cells.csv` | (run, rung, config) | every coverage / silent-error / balanced-accuracy figure, the five buckets behind them, judge behaviour, cost, tokens, latency |
| `tiers.csv` | (cell, tier, family) | which question types a cell wins and loses |
| `tools.csv` | (cell, tool) | what the agent reached for |

Each cell row carries model, reasoning effort, verifier and SURFACE FINGERPRINT, so a reader can
tell whether two cells were answering the same prompt. Without that a comparison is a coincidence.

**`2026-07/runs/`** — the four runs whose RAW rows back a claim the tables cannot express, gzipped
with traces intact. `cells.csv` gives you a rate; these let you replay the judge call or re-derive a
coalition value that produced it.

| run | backs |
|---|---|
| `20260727-140714-gpt-5-mini` | the R0–R9 ladder; the R9 worked example; the judge audit (58 calls, 12 stops, 0 good answers blocked) |
| `20260726-223032-gpt-5-mini` | the Shapley lattice, first half |
| `20260726-224953-gpt-5-mini` | the Shapley lattice, second half — 24 coalitions × 171 across the pair |
| `20260728-041240-gpt-5.6-sol` | the frontier-model cell |

Everything here is post-regrade. Runs graded before `ebf103f` scored honest refusals that name a
date as fabrications, and their numbers do not appear in this directory or in the article.

## Earlier

- **`grounding/`** — the six-rung grounding experiment (2 models × 6 rungs × 25 questions × 5 reps).
  `summary.md` is the committed record; the per-run raw rows were treated as regenerable.
- **`shapley-proof/`** — the n=1 restricted-Shapley proof (32 coherent guardrail configs × 12
  wrong-metric traps, `gpt-5-mini`). `raw.jsonl` **is** committed here, because model outputs are
  not deterministically regenerable and the attribution numbers are cited in the write-up.

To promote a new run: add it to the `publish_metrics.py` invocation above, and copy its raw rows
into `runs/` only if a published claim needs the per-row detail.
