# Experiment 06 — the third state

**One question, and it is the most ordinary question anyone asks an analytics system.**

> How many active users did we have last week?

Two governed metrics answer it. Both are right. They are 3.72% apart.

```text
active_users      886   excludes internal and test accounts   owner: Product
                        used by the weekly product review and the North Star metric tree
active_accounts   919   includes them                         owner: Platform
                        used by capacity planning and the support-volume forecast
```

Serving either figure alone is a number the reader cannot tell was a choice. It is a governed
result of a real metric, computed by real SQL, in the right unit and the right order of magnitude,
so the provenance check passes, the output validation passes, and the judge sees a genuine
trajectory. Nothing in the system has a signature to test against.

This experiment scores that.

## The stack, and a constraint on it

**Open source only. No hosted service is used or required.**

- **MetricFlow 0.211.0**, the open-source engine behind the dbt Semantic Layer, run in process.
  The layer is a standard MetricFlow manifest and the engine's own API produces both the compiled
  SQL and the results.
- **DuckDB**, local, over a generated warehouse.
- **The dbt models are real dbt SQL** — `{{ source() }}`, `{{ ref() }}`, one SELECT per file — but
  they are materialised by `fixture/build.py`, a documented subset, because dbt-core plus an adapter
  is fifty packages and a profile file for models this simple. `dbt build` against a duckdb profile
  produces the same objects from the same files.
- **Not the dbt Cloud Semantic Layer API**, and nothing here calls a metrics service over a network.

The reason is not cost. A result that depends on a hosted product cannot be reproduced by a reader,
cannot be inspected when it disagrees with expectation, and cannot be pinned to a version. Every
number in this experiment is reproducible from this repository and a model API key.

The choice has a price and it is visible in the findings: this engine exposes no dimension-member
resolver and no additivity metadata, so `resolve` and `output_validation` cannot run here, and the
experiment is pinned below R5. That is a fact about the stack teams actually deploy, which is the
point of using it.


## Why it is not experiment 05 again

Experiment 05 asked whether fixing what a static scan finds removes runtime harm. It does: eleven
findings before the repair, zero after, and wrong-metric selection fell to zero where the layer
governs the concept.

This fork cannot be repaired. Product needs customers; Platform needs load. Both definitions are
owned, both have a downstream consumer, and deleting either breaks a real report. The scan finds it
and the fix does not exist — which is why the case schema **requires an owner and a consumer for
every candidate**. A definition nobody owns and nothing consumes is a leftover, a leftover is
reducible, and deleting it offline is the previous experiment's finding rather than this one's.

## What is here

| | |
|---|---|
| [`00_reading.md`](00_reading.md) | Steps 1–2 of the brief: how `clarify` is handled end to end today, and whether the existing fixture can support a third pile. It cannot. |
| [`01_clarification_taxonomy.md`](01_clarification_taxonomy.md) | What the published taxonomies say about kinds of clarification, and the vocabulary that follows for this harness. |
| [`02_domain_map.md`](02_domain_map.md) | The fifteen layers, the six instruments and their reach, fifty named problems, and where all six experiments sit. |
| [`fixture/`](fixture/) | A dbt project, one contested pair, one question. |

## The fixture

A dbt project over the warehouse every other experiment already runs on. Raw sources, a staging
layer that resolves the mess, four marts, and a MetricFlow semantic layer over the marts.

```
fixture/
  dbt_project.yml
  models/
    sources.yml                     the raw layer, declared as it arrives
    staging/stg_users.sql           seven spellings of the platform, and the internal-account rule
    staging/stg_events.sql          `etype` 1/2/3 decoded into app_open / value_moment / reminder_click
    staging/stg_subscriptions.sql
    staging/stg_marketing_spend.sql
    marts/dim_users.sql
    marts/fct_user_days.sql         one row per account per day it did anything
    marts/fct_subscriptions.sql
    marts/fct_marketing_spend.sql
  layer/
    semantic_models.yml             the governed layer — and the contested pair
    project.yaml                    MetricFlow's project config (the time spine)
  build.py                          materialise the models into DuckDB, no dbt-core
  cases.yml                         ONE question, typed `contested`
  run.py         zero_point.md      ask the question, show what the agent did
  divergence.py  divergence.md      what each candidate returns, per slice
  scan.py        scan.md            the static dose, and its agreement with the hand labels
```

The governed layer sits in `layer/` rather than under `models/` because this repo does not run
dbt-core: MetricFlow parses the YAML directly and its parser reads every `.yml` in the directory it
is given, including dbt-only files like `sources.yml` that it cannot interpret. Nothing is
duplicated — that is the only copy.

`build.py` resolves `{{ source() }}` and `{{ ref() }}`, sorts the models by their refs and creates
one view each. The files are ordinary dbt models and `dbt build` against a duckdb profile produces
the same objects; the runner exists so the experiment keeps running on a laptop with no profile and
no adapter, which is the same call `semantic/metricflow_engine.py` already made for MetricFlow.

```bash
uv sync --group metricflow
uv run python fixture/build.py --drop        # 8 models -> schema wh_06
uv run python fixture/divergence.py --write  # what the two definitions return, per slice
uv run python fixture/scan.py --write        # preflight, and agreement with the hand labels
cd fixture && PYTHONPATH=. python run.py --model gpt-5-mini --reps 5   # ask it
```

## The dose, measured rather than asserted

**Divergence.** The two definitions disagree on 11 of 12 slices, by between 0.00% and 5.17%, and by
3.72% on the week as a whole. The sign is consistent, so neither is a data error. Danger runs
inverse to magnitude: the narrow slices are the dangerous ones, because a swap there is invisible
to any reader and any range check.

**Agreement.** The candidates in `cases.yml` were written by reading the layer. preflight 0.4.0
reads the same layer independently and reports exactly one finding, HIGH, naming the same pair as a
`SCOPE_TRAP`. One of one. The two passes are kept separate because a detector that both writes the
ground truth and enforces it at query time is marking its own homework.

## The case is a first-class citizen

`expect.type: contested` is wired into the shared machinery, not into a script beside it.

| where | what changed |
|---|---|
| `evals/cases/schema.json` | a `contested` variant: a concept, and two or more candidates each declaring a metric, its own oracle, an owner and a consumer |
| `evals/gold.py` | validates the shape, and resolves each candidate's oracle onto the candidate. A contested case has **no single gold**, and forcing one would state the thing the case denies |
| `evals/grade.py` | clarifying is correct; refusing is an over-refusal; answering is a silent error, and **which** candidate was served is recorded along with how far it sits from the one it was chosen over |
| `evals/selective.py` | a third pile. Balanced accuracy averages the piles that *have* questions, so a suite without pile C scores exactly what it scored before |

Graded five ways on the real case:

| the run ended | correct | bucket | silent error | served | divergence |
|---|---|---|---|---|---|
| clarified | **yes** | idk | no | — | — |
| answered 886 | no | wrong | **yes** | `active_users` | 3.72% |
| answered 919 | no | wrong | **yes** | `active_accounts` | 3.59% |
| answered 1,204 | no | wrong | yes | — | — |
| refused | no | idk | no | — | — |

Every change is additive. 413 published values recomputed from the archived rows, and none moved:
pile C is empty there, `expected_action` is absent, and `_pile` falls back to `expected_refuse`.
(One value differs from `cells.csv` for a pre-existing reason unrelated to this work — see
`experiment.yml`.)

## The zero point — the name picks the metric

Full trace in [`fixture/zero_point.md`](fixture/zero_point.md).

**Three action spaces, no difference.** No clarify tool, a prose one, and a coded one with the rule
written into the prompt: 35 attempts across two models, 0 clarifications.

**Rename the pair and the served number changes.** Four presentations of the same two definitions —
identical measures, filters, values, owners and consumers, only the labels move.

| variant | the 886 reading is called | the 919 reading is called | attempts | served |
|---|---|---|---:|---|
| `baseline` | `active_users` | `active_accounts` | 8 | **886** |
| `no_exact_match` | `active_customers` | `active_accounts` | 8 | **886** |
| `reversed` | `active_users` *(second)* | `active_accounts` *(first)* | 8 | **886** |
| **`crossed`** | **`real_customers`** | **`active_customers`** | **16** | **919** |

The word "active" moved from one definition to the other and the answer moved with it. On the
crossed layer it served a count that **includes staff and test logins** for a question about users,
from a metric whose own description says it is about load rather than customers — because that
metric was called `active_customers`.

**The description is available; the answering path does not consult it.** Asked to *compare* rather
than to answer, the same model on the same layer clarifies, names both candidates, and states the
discriminator exactly. Asked to answer, it matches on the label and reads past the description.

**The practitioner finding, and it cuts against standard advice.** Better naming does not stop an
agent choosing silently. It changes which definition it silently chooses.

## What `clarify` now is, on the agent side

| | before | now |
|---|---|---|
| payload | one free-text `question` | `reason` (4-code enum) · `candidates` (governed names) · `question`, asked in the user's words |
| stored reason | the literal string `"clarify"` | the model's own code, or None where the tool did not ask |
| in the registry | absent | `clarify` and `typed_clarify`, both `ACTION_SPACE` |
| can be switched off | no | `R3-clarify` |
| prompt | "if the question is too ambiguous to attempt" | refuse when nothing answers, clarify when more than one thing does |

Two flags rather than one, because the arms are three: no channel, a prose channel, a typed one.
Both sit **outside** the published ladder (`in_ladder=False`), so `LADDER` is still R0–R9 and every
preset keeps its declared defaults. `test_surface.py` pins what the model sees across 24 cells and
passes unchanged, which is the proof that no published run moved.

The vocabulary is four codes, not the eight the taxonomy supports, and it splits two ways:
`competing_definitions` and `undefined_term` describe the **layer** and recur for every user until
someone decides, so they route to governance; `underspecified_request` describes the **question**
and is resolved once. Finer splits when there is traffic to justify them.

## Not built yet

- **The checks the payload was built for.** The candidates now arrive; nothing yet asks whether
  they exist in the catalogue, whether they actually diverge on the slice asked about, or whether
  the question names the facet that differs. Those three are lookups needing no gold answer, and
  they are the reason the payload exists. With 0 clarifications so far there is nothing to run
  them on.
- **A lookup that runs whether or not the model asks for it.** The advisory route is a measured
  null. The next lever is the enforced one, and it needs a cluster index — which is the open
  question, since the layer format has no field naming the concept a metric claims.
- **The second turn.** No user simulator, so a clarification is priced at half an episode and
  abandonment is unmeasurable.
- **The rest of pile C.** One concept is one data point. The sizing work in `00_reading.md` says a
  usable pile needs four to five distinct contested concepts, not one sliced several ways.
- **Piles A and B on this fixture.** The contested pile has no counterweight yet, so
  over-clarification cannot be measured.
