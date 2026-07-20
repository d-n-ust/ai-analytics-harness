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
| Harness | commit ef487c6, `eval --models gpt --repeats 1` |
| Date | 2026-07-20 |

## Accuracy by rung

| rung | Qwen3-30B-A3B (local) | mini (GPT-5.4-mini, upstream) | gpt (GPT-5.6, upstream) |
|---|---|---|---|
| 1 · messy data | 16% (4/25) | 22% | 40% |
| 2 · star schema | 32% (8/25) | 34% | 46% |
| 3 · semantic layer | 52% (13/25) | 54% | 66% |
| 4 · + verified examples | 72% (18/25) | 77% | 81% |
| 5 · + knowledge base | 68% (17/25) | 75% | 78% |
| 6 · + metric tree | 76% (19/25) | 78% | 92% |

## Correct-rate by tier x rung

| tier | r1 | r2 | r3 | r4 | r5 | r6 |
|---|---|---|---|---|---|---|
| lookup | 3/5 | 4/5 | 4/5 | 5/5 | 4/5 | 5/5 |
| filtered | 0/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| metric | 0/5 | 0/5 | 4/5 | 5/5 | 4/5 | 4/5 |
| knowledge | 1/5 | 0/5 | 0/5 | 3/5 | 4/5 | 4/5 |
| diagnostic | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |

## Observations

- **The ladder replicates.** Every structural jump lands on the same rung as the
  upstream runs: the semantic layer and the verified examples are the two big
  steps, and the overall curve tracks GPT-5.4-mini within a few points at every rung.
- **Rung 5 replicates too.** Prose knowledge lost points against verified examples
  here as well (72% -> 68%). Three models, same verdict: examples beat prose.
- **What did not survive the downsizing: diagnostics.** 1/25 on the diagnostic tier
  even with the metric tree (upstream flagship: 18/25). A grounded local 30B reads
  governed numbers reliably but does not yet reason about why they moved.
- Single repetition; expect a point or two of drift between runs, as upstream notes.

Happy to adjust the format if a different layout works better for community results.
