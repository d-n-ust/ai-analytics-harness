# results/published/ — the evidence behind the write-up

Curated results a Decision Spine write-up cites, committed so a reader can check the numbers.
Disposable dev runs live in `results/runs/` (gitignored) and regenerate with a run.

- **`grounding/`** — the six-rung grounding experiment (2 models × 6 rungs × 25 questions × 5 reps).
  `summary.md` is the committed record; the per-run raw rows were treated as regenerable.
- **`shapley-proof/`** — the n=1 restricted-Shapley proof (32 coherent guardrail configs × 12
  wrong-metric traps, `gpt-5-mini`). `raw.jsonl` **is** committed here, because model outputs are
  not deterministically regenerable and the attribution numbers are cited in the write-up.

To promote a new run to evidence: copy its dir here (keep `summary.md` + `summary.json`, add
`raw.jsonl` only if the raw rows back a published number) and commit.
