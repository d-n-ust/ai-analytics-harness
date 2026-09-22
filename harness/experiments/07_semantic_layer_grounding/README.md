# Experiment 07: semantic layer grounding

A governed metric does not make the answer governed. A query is a metric plus a set of parameter
decisions: filters, group-by dimensions, time grain and period. The semantic layer governs few of
them. This experiment classifies each decision by its basis (the question, a governed declaration, a
governed principle, or nothing) and by whether the answer disclosed it. It then measures whether an
agent that grounds and discloses every parameter has a lower silent error rate.

The model and the measurement design are in `milestoneA.md`. The ledger of exploratory runs is
`findings.md`. The manifest is `experiment.yml`.

## Layout

| path | what it is |
|---|---|
| `experiment.yml` | the manifest: question, status, evidence |
| `milestoneA.md` | the model of query trust, the measures, and the three-arm design |
| `findings.md` | what each exploratory run showed, in order |
| `01_parameter_grounding/cases.yml` | 14 questions with `gold_sql` oracles and per-decision labels |
| `fixture/` | the dbt project, the MetricFlow layer, and `layer/governance.yml` |
| `ground.py` | the grounding step, as a prototype that runs one question |
| `probes/` | three single-run outputs cited by `findings.md`, recorded before the shared runner |

Code this experiment depends on lives in the shared packages, not here:

| module | role |
|---|---|
| `ontology/src/ontology/parameters.py` | the parameter surface of a metric: legal dimensions and members |
| `engine/src/agent/core/measure.py` | additivity of each aggregation |
| `engine/src/agent/core/members.py` | which member a phrase may map to |
| `harness/evals/row.py`, `grade.py`, `report.py` | recording, grading and reporting every measured run |

`fixture/` is a copy of experiment 06's fixture, kept here so this experiment does not depend on
another experiment's folder. `layer/governance.yml` is the only file 06 does not have.

## Status

| step | state |
|---|---|
| model of query trust (`milestoneA.md`) | done |
| question suite with proven oracles (`01_parameter_grounding/cases.yml`) | done; loads once the two case-format extensions exist |
| grounding step in `engine/src/agent` as `R3+grounding`, plus `R3+disclose` | next |
| case-format extensions: `breakdown` expectation, `decisions` block | next |
| `./bench gate`, small run, full run | after that |

## Run the prototype

```bash
# from the repo root, once:
uv sync && uv run python -m cli data                                          # runs/warehouse.duckdb
uv run python harness/experiments/07_semantic_layer_grounding/fixture/build.py   # materialise the marts

# one question through the grounding prototype (live model, writes ground.html):
uv run python harness/experiments/07_semantic_layer_grounding/ground.py \
    "How did Android app opens break down by segment in June 2026?"
```

The prototype records no row, so its output is not a measurement. Measured runs go through the
shared runner once the grounding step is in the engine.
