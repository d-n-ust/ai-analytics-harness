# results/published/ — the evidence behind the write-ups

Curated results a Decision Spine write-up cites, committed so a reader can check the numbers.
Disposable dev runs live in `runs/` (gitignored) and regenerate with a run.

**One folder per published result, named `YYYY-MM-<what-it-is>`** — the month the result was
produced, then a plain name. The folder name tells you what it is; the experiment it came from and
the headline it backs are in the table below. To go the other way — from an experiment to its
evidence — each `harness/experiments/NN_*/experiment.yml` lists these paths under `evidence:`.

| folder | experiment | what it holds | headline |
|---|---|---|---|
| [`2026-07-grounding-ladder/`](2026-07-grounding-ladder/) | 1 · grounding ladder | accuracy by grounding rung (2 models × 6 rungs × 25 questions × 5 reps) | right answers 36% → 85%; confidently wrong only 52% → 31% |
| [`2026-07-reliability-ladder/`](2026-07-reliability-ladder/) | 2 · reliability ladder | the R0–R9 guardrail grid: coverage / silent-error / balanced-accuracy per cell, plus the four raw runs | silent error 48.5% → 2.4% |
| [`2026-07-guardrail-shapley/`](2026-07-guardrail-shapley/) | 2 · reliability (attribution) | restricted-Shapley attribution over 24 guardrail coalitions (32 configs × 12 wrong-metric traps, `gpt-5-mini`) | one guardrail contributes −0.0 while firing 656 times |
| [`2026-08-preflight-ambiguity/`](2026-08-preflight-ambiguity/) | 5 · preflight ambiguity | one warehouse before/after repairing scan-flagged definitions (36 questions × 3 reps, 2 models) | scan 11 → 0 findings; silent error on flagged concepts 43.7% → 9.2% (`gpt-5-mini`), 25.3% → 3.4% (`gpt-5.6-terra`) |
| [`2026-09-held-out-reliability/`](2026-09-held-out-reliability/) | 6 · third state | silent-error rate on fresh held-out suites (`current_best`, `gpt-5-mini`, rung 3) | silent error 0.036 → 0.014 on unseen questions |

**Shape of a result folder.** A `summary.md` (or the CSVs, for a grid) is the human-readable board.
Raw per-attempt rows are committed **only** when the model outputs back a claim and are not
deterministically regenerable; where a run's rows were treated as regenerable, only the summary is
kept. So a folder with no raw rows is a deliberate choice, not a missing file.

**Names are stable once shipped.** A published article links files here by URL
(`.../blob/master/results/published/<folder>/...`), so renaming a folder breaks that link. Rename
only in step with the articles that cite it.

---

## 2026-07-reliability-ladder — the reliability series

Backs *Agentic Analytics: Teaching an AI Analyst to Say I Don't Know* (experiment 2).

**`2026-07-reliability-ladder/*.csv`** — every published rate, one row per cell. Regenerate with:

```
PYTHONPATH=. uv run python evals/components/publish_metrics.py \
    results/published/2026-07-reliability-ladder runs/<run> [...]
```

| file | grain | what it answers |
|---|---|---|
| `cells.csv` | (run, rung, config) | every coverage / silent-error / balanced-accuracy figure, the five buckets behind them, judge behaviour, cost, tokens, latency |
| `tiers.csv` | (cell, tier, family) | which question types a cell wins and loses |
| `tools.csv` | (cell, tool) | what the agent reached for |

Each cell row carries model, reasoning effort, verifier and SURFACE FINGERPRINT, so a reader can
tell whether two cells were answering the same prompt. Without that a comparison is a coincidence.

**`2026-07-reliability-ladder/runs/`** — the four runs whose RAW rows back a claim the tables cannot
express, gzipped with traces intact. `cells.csv` gives you a rate; these let you replay the judge
call or re-derive a coalition value that produced it.

| run | backs |
|---|---|
| `20260727-140714-gpt-5-mini` | the R0–R9 ladder; the R9 worked example; the judge audit (58 calls, 12 stops, 0 good answers blocked) |
| `20260726-223032-gpt-5-mini` | the Shapley lattice, first half |
| `20260726-224953-gpt-5-mini` | the Shapley lattice, second half — 24 coalitions × 171 across the pair |
| `20260728-041240-gpt-5.6-sol` | the frontier-model cell |

Everything here is post-regrade. Runs graded before `ebf103f` scored honest refusals that name a
date as fabrications, and their numbers do not appear in this directory or in the article.

## 2026-07-guardrail-shapley — the guardrail attribution (experiment 2)

The n=1 restricted-Shapley proof: 32 coherent guardrail configs × 12 wrong-metric traps,
`gpt-5-mini`. `raw.jsonl` **is** committed here, because model outputs are not deterministically
regenerable and the attribution numbers are cited in the write-up. `summary.md` / `summary.json`
carry the board.

## 2026-07-grounding-ladder — the six-rung grounding ladder (experiment 1)

2 models × 6 rungs × 25 questions × 5 reps. `summary.md` is the committed record; the per-run raw
rows were treated as regenerable, so only the summary is kept.

## 2026-09-held-out-reliability — the silent-error rate on fresh questions (experiment 6)

The confident-wrong rate of the standard cell (`current_best`, `gpt-5-mini`, rung 3) measured on
suites authored blind and run once, so the number reports capability rather than fit. **0.0145
silent (2/138) on `heldout4`, down from 0.0362 on `heldout3`.** `summary.md` carries both boards,
the causal firing evidence for the two guards, and the honest caveats; `heldout3.raw.jsonl.gz` and
`heldout4.raw.jsonl.gz` are the scored rows (138 each, one attempt per line). The raw rows **are**
committed because model outputs are not deterministically regenerable, and the board recomputes from
them with `evals.selective` (command in `summary.md`). Full method and derivation: §77–79 in
`harness/experiments/06_third_state/findings.md`.

---

To promote a new run: add a folder here named `YYYY-MM-<what-it-is>`, give it a `summary.md`, commit
its raw rows only if a published claim needs the per-row detail, add a row to the index table above,
and point the source experiment's `experiment.yml` `evidence:` list at the new folder.
