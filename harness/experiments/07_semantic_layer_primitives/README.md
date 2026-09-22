# Experiment 07 — Semantic Layer Primitives

**A catalogue match tells you a metric is governed. It does not tell you the question is answerable
with confidence.** Every question forces a series of decisions — population, entity, grain, segment
member, time role, calendar, coverage, additivity, route — and each is either grounded in the layer,
silently defaulted, undefined, or reachable off the governed path.

This experiment runs the real agent on **one question at a time**, decomposes what it did into that
decision series, and shows, per decision, what the agent decided, from what source, on what
grounding, and in which state. The output is a **question anatomy**: the full breakdown of what an
answer stands on, with the silent defaults made visible.

It is the instrument the domain map (`../06_third_state/02_domain_map.md`) calls trace-backed: it
reaches the semantic layer and the act stratum, needs no gold answers, and could run in production.

## Status

| Part | State |
|---|---|
| `fixture/` — warehouse + dbt + MetricFlow layer, copied from exp06 so it can be modified freely | ✓ copied |
| `spine/generate.py` + `spine/overlay.yaml` → `spine/spine.yaml` | ✓ built |
| `inspector/` — run the agent on one question, render the anatomy | · next |
| `questions/`, `results/` | · pending |

## The spine, in two halves

The spine is the reference the agent's trace is scored against. Only one half is written by hand.

- **Generated base** (`generate.py`): entities, the join graph, measures and their source fact, the
  time role each is anchored on, the raw scope filter each carries, the categorical attributes, and
  — read straight from DuckDB — **coverage** (min/max of each fact's time dimension) and the
  **member set** of every attribute (with the raw spellings staging collapsed). Recomputed from the
  layer + warehouse; it cannot drift from them.
- **Governance overlay** (`overlay.yaml`): the facts no source declares — the vocabulary (a word
  maps to a candidate set), relations between definitions (contested / alias / supersedes, with
  owner, evidence tier, status, policy), per-dimension additivity, named populations, owner and
  status. **The overlay's size is a primary output: it is the shape of what the layer cannot say.**

## Run it

```bash
# from the repo root, once:
uv sync && uv run python -m cli data                       # generate runs/warehouse.duckdb
python harness/experiments/07_semantic_layer_primitives/fixture/build.py   # materialise the marts

# regenerate the spine from the layer + warehouse:
python harness/experiments/07_semantic_layer_primitives/spine/generate.py
```

## First question

`"How many times did Android users open the app in June 2026?"` → `app_opens`. Non-contested, a
single governed metric, as clean as a catalogue match gets — and its primitive combination is still
only partly grounded. That gap is the subject.
