# Community result: Qwen3-30B-A3B (local, llama.cpp)

A third data point for the grounding ladder, on a fully local model. Same harness,
same 25 questions, same six rungs, nothing changed but the model behind the
OpenAI-compatible endpoint.

## Setup

| | |
|---|---|
| Model | Qwen3-30B-A3B-Instruct-2507 (MoE, ~3B active params), unsloth GGUF UD-Q3_K_XL |
| Serving | llama.cpp b10050 `llama-server` (`--jinja`, 8192 ctx), `OPENAI_BASE_URL` pointed at it, model alias `gpt` |
| Reasoning | off (`OPENAI_REASONING=none`, non-thinking instruct model) |
| Hardware | Apple M4 Pro, 24 GB unified memory |
| Harness | commit ef487c6. Full ladder: `eval --repeats 1`. Variance follow-up: `eval --repeats 5 --rungs 4,5,6` |
| Date | 2026-07-20 (full ladder), 2026-07-21 (5-rep follow-up) |

## Accuracy by rung (single run)

| rung | Qwen3-30B-A3B (local) | mini (GPT-5.4-mini, upstream) | gpt (GPT-5.6, upstream) |
|---|---|---|---|
| 1 · messy data | 16% (4/25) | 22% | 40% |
| 2 · star schema | 32% (8/25) | 34% | 46% |
| 3 · semantic layer | 52% (13/25) | 54% | 66% |
| 4 · + verified examples | 72% (18/25) | 77% | 81% |
| 5 · + knowledge base | 68% (17/25) | 75% | 78% |
| 6 · + metric tree | 76% (19/25) | 78% | 92% |

## Variance: five reps on rungs 4-6

Fair question on the thread: one run or several? The first pass above was one rep.
Here are five, on the three rungs where the interesting action is. The harness reports
each rung as mean +/- sd once `--repeats > 1`.

| rung | 1 run | 5 reps (mean +/- sd) | range |
|---|---|---|---|
| 4 · + verified examples | 72% | 70% +/- 2 | 68-72 |
| 5 · + knowledge base | 68% | 69% +/- 2 | 68-72 |
| 6 · + metric tree | 76% | 75% +/- 3 | 72-80 |

Diagnostic tier pooled over the five reps: 0/25 at rung 4, 0/25 at rung 5, 7/25 at rung 6.
375 runs (1 model x 3 rungs x 25 questions x 5 reps) in 29 minutes on the M4.

## Correct-rate by tier x rung (single run)

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 3/5 | 4/5 | 4/5 | 5/5 | 4/5 | 5/5 |
| filtered | 0/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| metric | 0/5 | 0/5 | 4/5 | 5/5 | 4/5 | 4/5 |
| knowledge | 1/5 | 0/5 | 0/5 | 3/5 | 4/5 | 4/5 |
| diagnostic | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |

## Observations

- **The ladder replicates.** Every structural jump lands on the same rung as the
  upstream runs: the semantic layer and the verified examples are the two big steps,
  and the overall curve tracks GPT-5.4-mini within a few points at every rung.
- **Rung 5, corrected by the reps.** The single run showed a clean 4-point prose
  penalty (72% -> 68%). Five reps shrink that to 1 point (70% +/- 2 vs 69% +/- 2),
  with the two ranges fully overlapping (68-72 both). On this model the
  prose-vs-examples difference sits inside the noise. Examples still never win by much
  and never lose, but I would not call rung 5 a clean replication of the drop here.
- **What clears the spread: the metric tree.** Diagnostic questions go 0/25 -> 7/25
  from rung 5 to rung 6 across the five reps, a jump far larger than the +/- 3 sd. That
  is the one effect at this model size I would stake a claim on.
- **Deep diagnostics still do not survive the downsizing.** Even with the metric tree,
  diagnostic tops out around 7/25 pooled over five reps (upstream flagship: 18/25 single
  run). A grounded local 30B reads governed numbers reliably but barely reasons about
  why they moved.
- Rungs 1-3 above are still single-run; the variance section only re-ran 4-6.

Happy to adjust the format if a different layout works better for community results.
