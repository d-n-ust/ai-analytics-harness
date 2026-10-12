# Experiment 07: semantic layer grounding

A governed metric does not make the answer governed. A query is a metric plus parameters: filters,
a period, a time grain and a group-by. The semantic layer governs few of them. This experiment asks
what an AI analyst needs so that every parameter of a governed `query_metric` call is **grounded**,
meaning it comes from a source the analyst can point to, and what the semantic layer must declare
for that to happen.

The ledger of every run is `findings.md` (sections 1 to 39; the open list is section 39). The
manifest is `experiment.yml`. The first model of the problem, as designed on 2026-09-22, is
`milestoneA.md`.

## What the experiment found

A parameter is grounded by **a rule** (declared in the layer, the governance file or the calendar)
or by **a dimension search**: code finds the values a phrase could mean, an exact match is applied by
code, and otherwise a decision model judges among the candidates above fixed bars, and the answer
states the judgement. If nothing grounds a parameter, the analyst asks.

| finding | evidence | section |
|---|---|---|
| A fact written as a sentence in the layer is not applied; the same fact as a modelled attribute is | controlled test, "mobile": missing 6/24 correct with 9 silent wrong; prose 6/24 with 18 asks; applied by code 24/24 | 27 |
| A decision model choosing each parameter from options built by code lowers silent errors, at a cost in coverage | held-out v1: silent error 0.298 to 0.053, coverage 0.952 to 0.762 (19 questions, a direction, not significant) | 19 |
| Telling the agent to state its assumptions does not lower silent errors; showing it the reading first raises them | held-out v1: 0.298 and 0.298; 0.053 to 0.193 | 19 |
| The typed reader (the model marks phrases, code resolves them) lowers silent errors on the same blind set, at first at a cost in coverage | blind set 1: 12.5% to 0.9%; coverage 80% to 60% | 31, 35 |
| Allowing a stated analyst judgement recovers coverage | blind set 3: coverage 81.0%, silent wrong 1.4% | 34, 35 |
| One narrow yes/no per judgement replaces one check of the whole reading, which vetoed 83 right readings for 13 wrong ones | development set 2: balanced accuracy 85.4% to 96.5%, coverage 81.2% to 97.9% | 36 |
| The latest typed reader | blind set 4, one run, corrected labels: silent wrong 1.4% (1 of 72), balanced accuracy 95.4%, coverage 96.3% | 38 |

The blind sets were written outside the work (intents by one model, wordings by another), with
predictions registered before each run and labels audited after it. Each set measured a newer
version, so comparisons across sets are not controlled; the only same-set comparison is set 1. All
results come from one synthetic warehouse and one metric.

## Layout

| path | what it is |
|---|---|
| `experiment.yml` | the manifest: question, status, evidence |
| `findings.md` | every run and what it showed, in order; section 39 is the open list |
| `milestoneA.md` | the first model of query trust and the three-arm design (2026-09-22) |
| `fixture/` | the dbt project and MetricFlow layer (copied from experiment 06), modelled attributes (`device_type`, `country_name`, seasons, hemisphere), value meanings, complete lists, and `governance.yml` |
| `01_parameter_grounding/` | study 01: the whole agent in four or five arms (`run.py`); development, red-team and two held-out suites; the grader `reading_errors` |
| `02_readiness_audit/` | study 02: the question reader alone; the readiness audit, the controlled test, four blind replication sets with label audits, the metamorphic suite, regrading and metrics at no cost, `grid.py` |
| `03_typed_reader/` | the typed reader's design (`design.md`) and the spike of its language step |
| `04_value_search/` | candidate search for large dimensions: a prototype tested on 12,409 cities without the decision model |
| `probes/` | single-run outputs from before the shared runner, cited by `findings.md` |

Code this experiment depends on lives in the shared packages:

| module | role |
|---|---|
| `ontology/src/ontology/parameters.py` | the parameter surface of a metric: dimensions, values read from the data, declared meanings and complete lists, and value maps derived from the data (country to region) |
| `engine/src/agent/guardrails/decisions.py` | `decision_grounding`: the reading of the question, held against every call |
| `engine/src/agent/guardrails/typed_reader/` | `typed_reader`: proposal, accounting, resolution, judgement, narrow checks; `english.py` holds the English closed classes |
| `engine/src/agent/guardrails/parameters.py` | `parameter_grounding`, the earlier LLM grounding step |
| `harness/evals/` | recording, grading and the three headline metrics (`selective.py`) |

## Status

| step | state |
|---|---|
| the agent arms on development and held-out suites (study 01) | done (sections 11 to 23) |
| the readiness audit, its rubric and the controlled test (study 02) | done (sections 24 to 28) |
| the typed reader, and four blind replication sets | done (sections 29 to 38) |
| candidate search for large dimensions | designed; step A prototyped (section 39, `04_value_search`) |
| the final run: a frozen version, a fifth blind set, three repetitions, the plain agent as a third arm | open (section 39) |

## Run

Measured runs call models through OpenRouter (`OPEN_ROUTER_API_KEY` in `.env`). Regrading, metrics
and the grid use stored rows and make no model call.

```bash
# from the repo root, once:
uv sync && uv run python -m cli data                     # runs/warehouse.duckdb

cd harness/experiments/07_semantic_layer_grounding/02_readiness_audit

python element_tests.py tests_dev_policy5.yml --reader typed --only 1,2      # a probe
python head_to_head.py replication4/tests.yml --readers typed --reps 1       # a blind set
python regrade.py results/<run>-head_to_head.json replication4/tests_corrected.yml
python metrics.py                                                          # headline numbers, sets 1 to 3
python grid.py                                                             # the readiness grid

# the agent arms (study 01):
python ../01_parameter_grounding/run.py --help
```

Known issue (section 39, 2026-10-12): `regrade.py` grades without the layer's rollups, which the run
used, so it counts a broader value stated as broader as a silent error; it also fails at its last
step. `grid.py` passes the rollups.

## Article

"What an AI Analyst Needs From Your Semantic Layer", decisionspine.com (draft, slug
`what-an-ai-analyst-needs-from-your-semantic-layer`).
