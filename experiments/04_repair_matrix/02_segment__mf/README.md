# Study 01, rebuilt on MetricFlow

The same three arms as `02_segment`, expressed in **dbt MetricFlow** instead of this
repository's own YAML.

## Layout

```
study.yml     what varies, at which cell, on which engine
cases.yml     the questions (study 01's, minus the mrr control this layer cannot answer)
arms/         one .yml per arm — its claim, level, and how its numbers are REACHED
layers/       one directory per arm — the MetricFlow YAML itself
```

Arms are declarations and layers are content. They carry the same names and are deliberately kept
apart: an arm is a file in every other study, and making it a directory here would be a second
convention to hold in mind. `layer_dir:` in an arm file points at its layer.

```bash
./bench study 02_segment__mf --reps 1
./bench study 02_segment__mf --arms D_declared --only p_pop_customers_week --reps 1
```

## Why it exists

Study 02 produced a finding about *rendering*: segments appeared in a global list that never said
which metric offered them, and the agent could not connect the two. That is a property of our
renderer, not of semantic layers. So a reasonable objection to the whole programme is:

> You measured your own file format. Nobody uses that.

This folder answers it. If the same defect and the same repair can be expressed in a semantic layer
that thousands of teams run in production, the finding is about semantic modelling. If they cannot,
that is a more interesting result and it needs saying out loud.

## No dbt

MetricFlow is normally reached through dbt: a project, `dbt parse`, a compiled `manifest.json`.
None of it is required. The engine ships its own YAML parser and a DuckDB SQL renderer.

| | packages | pulls `dbt-core` |
|---|---|---|
| `metricflow` alone | **14** | no |
| `dbt-metricflow` + `dbt-duckdb` | 51 | yes, plus a telemetry client |

`client.py` is the whole adapter — MetricFlow's `SqlClient` protocol is four methods and two
properties. It lives in a `metricflow` dependency group, so the harness itself never installs it.

```bash
PYTHONPATH=. uv run --group metricflow python \
    experiments/04_repair_matrix/02_segment__mf/check.py
```

## What it proves

**The numbers match ours exactly.** MetricFlow returns **3642** for `real_value_moments` over the
week of 2026-07-06 — the same figure `cases.yml` carries as gold for `p_pop_customers_week`,
computed independently by raw SQL. Two engines, two definitions of the layer, one number.

**All three arms hold the same-numbers invariant.**

```
A_implicit     everyone=  67132 real=  64257  [OK]  via two metrics
B_documented      everyone=  67132 real=  64257  [OK]  via two metrics
D_declared    everyone=  67132 real=  64257  [OK]  via one metric + a where-constraint
```

**Time filtering and distinct counts both work**, which were the two open questions. Every question
in this study names a period, so a layer that could not answer a time-constrained query would have
been useless here regardless of anything else.

## The finding: MetricFlow cannot express the repair as a segment

This is the reason the folder is worth more than a port.

Our layer repairs this defect by declaring a **named, described, reusable segment** and offering it
on the metric. Cube does the same thing under the same name. MetricFlow has no such construct — a
metric filter is an expression over a dimension, and there is nowhere to give the resulting
population a name.

So arm D here is a *different repair*: delete the twin, keep one metric, and let the caller state
the population as a where-constraint.

```
ours    query_metric(metric="value_moments", segment="real_users")
        └─ `real_users` is declared once, with a description, and is offered by the metric

MetricFlow
        mf query --metrics value_moments --where "{{ Dimension('user__is_internal') }} = false"
        └─ there is no `real_users` anywhere. Only `is_internal = false`, and the agent has to
           know that this is what "customers" means.
```

It reaches the right number. It does not name the thing it selected.

**And it forces prose to do structural work.** Look at arm D's `is_internal` dimension: the
instruction *"filter on this to choose the population"* had to be written into its description,
because nothing structural marks a dimension as a population selector. Writing a fact into prose
because the structure cannot hold it is precisely what this study exists to criticise, and
MetricFlow leaves no alternative.

That gives a spectrum worth publishing, rather than a rule:

| | how a population is expressed | can a machine read its name? |
|---|---|---|
| Cube | `segments:` — named, described, reusable | yes |
| ours | governed segment — the same idea | yes |
| MetricFlow | a where-constraint over a dimension | no — only the predicate survives |
| DAX | inside a measure expression | no |

## First run, one rep

```
arm               correct   silent wrong
A_implicit            2/4          2
B_documented             4/4          0
D_declared           3/4          1
B_prose_swapped     4/4          0   (retired — see below)
```

**The defect reproduces on a real semantic layer.** `A_implicit` served two confidently wrong numbers,
picking the shorter name both times the question meant the other twin. That is the answer to "you
measured your own file format".

**The position control did NOT hold, and this write-up previously said it did.** `B_documented` scored
4/4 in all three runs; `B_prose_swapped` scored 4/4, 3/4, 3/4. The arm has since been retired,
because reordering changes the catalogue text and so a gap between the two is position or noise with
nothing to separate them. See `B_prose_swapped.retired.md`.

**`D_declared` failed exactly one question, and how it failed is the finding.** On
`p_pop_customers_week` it called `{metric: value_moments, period: last_week}` — no filter at all —
and got a well-formed call returning the everyone figure. On `p_pop_customers_june` it filtered
correctly. The difference is the wording: June's question says *"excluding staff and test accounts"*,
which only has to be transcribed; the week's says *"our customers"*, which requires knowing that
customers means non-internal. Our own C arm carries that word in the segment's synonyms and offers
`real_users` as an enumerated choice, so it does not have to be inferred.

**A named segment survives paraphrase; a dimension filter does not.** That is the sharpest claim
this port produced, and it makes a prediction: the two engines should split on paraphrased questions
and agree on literal ones. Two of these four questions differ on that axis and both engines split
the same way — one observation per cell, so a direction rather than a rate.

## What is not here yet

Arms point at **full YAML directories, not patches**. That is a step backwards from the patch engine
used everywhere else, and it is deliberate: MetricFlow parses a directory of multi-document YAML,
which the patch language cannot express. If this port proves out, that is the first thing to fix —
forked layers drift, which is the lesson study 01 paid for once already.

The two engines cannot run at the same ladder level, so this study names a subtractive cell
(`R7-coverage_check-resolve`) instead. Comparing against study 01 means re-running that one at the
same cell; comparing against its R7 numbers would measure the guardrails rather than the layer.

## One side effect

MetricFlow answers time-filtered queries by joining a **time spine** — a table with one row per day.
`client.py` creates `main.mf_time_spine` as a VIEW over the warehouse's own date range. No rows are
copied and `bench data` regenerates the file anyway, but it is a write to the warehouse and it is
better stated than discovered.
