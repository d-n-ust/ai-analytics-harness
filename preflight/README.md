# preflight

Static, cross-layer **ambiguity detection** for governed analytics grounding.

Before an AI analyst (or a person) runs a query, `preflight` compares the governed definitions it
could ground on — semantic-layer metrics, warehouse columns and views, documented terms — and
reports the pairs a competent reader would confuse and that resolve to **different numbers**. It
reads the declarations, not the query traffic, so it says which confusions are *possible* rather
than which have happened, and the structural detection needs no model, no questions, and no run.

This is the **selection** half of grounding safety: two valid definitions exist and the wrong one
gets picked. It does not check whether a single definition is internally correct (columns that
exist, values in range, additivity, grain, join fan-out) — those are complementary per-primitive
validators, not ambiguity.

## Install

Not yet on PyPI (that name belongs to an unrelated project), so install from source:

```bash
uv tool install .                 # from this repo root; core: structural detection on a lexical gate
uv tool install ".[embeddings]"   # + sentence-transformers for the sharper, validated gate
```

New here? **[QUICKSTART.md](QUICKSTART.md)** walks a dbt project (jaffle shop) end to end in a few commands.

## Use — terminal

```bash
preflight scan path/to/environment                 # summary, grouped by danger, each finding cited
preflight scan path/to/environment --detail        # + every colliding site and its source line
preflight scan path/to/environment --format json   # machine-readable (each item carries its source)
preflight scan path/to/environment --min-danger high --fail-on high
```

Every finding is anchored to `path:line` (the linter convention), so it points straight at the file
and row to open. `--detail` lists every colliding site and prints the offending source line:

```text
HIGH (2)
  docs/data_dictionary.md:1: [DEFINITION_DIVERGENCE] active user[doc]  ~  active user[doc]
      'active user' documented two different ways
      docs/data_dictionary.md:1        ## active user
      docs/data_dictionary.md:4        ## active user
```

`scan` reads whichever of `semantic/semantic_layer.yml`, `warehouse/schema.sql`, and
`docs/data_dictionary.md` are present. It exits non-zero when a finding at or above `--fail-on`
(default `high`) exists, so it gates CI. `--gate auto` uses embeddings when installed, else lexical.

### Native dbt

Point `--dialect dbt-manifest` at a dbt project (or its compiled `target/manifest.json`) to scan all
three layers of a real project at once. One `dbt parse` (no warehouse connection) compiles the
semantic models, metrics, model columns, and descriptions into the manifest; preflight reads them and
cites each finding back to the source `.yml`/`.sql` file and line.

```
dbt parse                                          # writes target/manifest.json
preflight scan . --dialect dbt-manifest --detail
```

Or, when `dbt` is on your PATH, do both in one step — `preflight dbt` runs your own `dbt parse` (your
real profile) and scans the fresh manifest, so you never scan a stale one:

```
preflight dbt .            --detail                 # parse + scan
preflight dbt path/to/proj --fail-on high           # as a CI gate
```

Other dialects: `--dialect metricflow` (raw MetricFlow YAML), `--dialect dbt` (raw dbt model SQL),
`--dialect cube` (Cube), `--dialect env` (the default `semantic/warehouse/docs` layout above).

## Use — library

```python
from preflight import scan

# conventional layout: semantic/semantic_layer.yml, warehouse/schema.sql, docs/data_dictionary.md
findings = scan("path/to/environment")           # list[Finding], most dangerous first
for f in findings:
    print(f.danger, f.type, [it.label for it in f.items], "—", f.note)
```

Grounding on other artifacts? Assemble facts with the adapters and detect directly:

```python
from preflight import adapt_semantic, adapt_warehouse, detect_collisions, as_dicts

facts = adapt_semantic(sem_path) + adapt_warehouse(schema_path)
findings = detect_collisions(facts, gate="lexical")   # or "auto" / "embeddings"
payload = as_dicts(findings)                          # JSON-ready plain dicts
```

Tune sensitivity without editing the package by passing a `DetectConfig`:

```python
from preflight import DetectConfig, detect_collisions
detect_collisions(facts, config=DetectConfig(gate=0.6, min_shared_facets=2))
```

## Use as a guardrail (CI / pre-commit)

`preflight scan --fail-on high` exits non-zero when a dangerous collision exists, so a change that
introduces one fails the build.

### GitHub Actions

A composite action ships with the package. Point it at your analytics repo:

```yaml
# .github/workflows/preflight.yml
name: preflight
on: [pull_request]
jobs:
  ambiguity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: d-n-ust/ai-analytics-harness/preflight@master   # becomes d-n-ust/preflight@v1 once extracted
        with:
          path: .
          gate: embeddings          # best results; use 'lexical' to skip torch
          fail-on: high
```

Until `preflight` is on PyPI, override `spec` with the VCS form:
`preflight[embeddings] @ git+https://github.com/d-n-ust/ai-analytics-harness@master#subdirectory=preflight`.

### pre-commit

Once `preflight` is its own repo, use the packaged hook:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/d-n-ust/preflight
    rev: v0.1.0
    hooks: [{ id: preflight }]
```

Today, from any environment where `preflight` is installed, use a local hook:

```yaml
repos:
  - repo: local
    hooks:
      - id: preflight
        name: preflight ambiguity scan
        entry: preflight scan . --gate lexical --fail-on high
        language: system
        pass_filenames: false
```

## The gate

Similarity decides only **which name-pairs are worth examining**, never whether a collision is
dangerous — that is decided structurally (same measure under a subset population, same concept over
different columns, same term with divergent scope, and so on).

### Why embeddings are optional

Because the embedding model powers only that gate — it sharpens *what to look at*, it is not
load-bearing for the danger decision — and there is a dependency-free lexical fallback. That is what
lets the core install stay light (no PyTorch) and run anywhere: on a CI runner, serverless, ARM, or
an air-gapped box. A required deep-learning dependency would be inflicted on everything that in turn
depends on `preflight`, and can fail to install outright on some platforms; optional-with-fallback
guarantees the tool always installs and runs, and upgrades to the sharper gate when it is available.

| gate | scores similarity by | role |
|---|---|---|
| **embeddings** (`preflight[embeddings]`) | spelling *and* meaning (`revenue` ~ `sales`, `churn` ~ `attrition`) | the **validated** path — the published recall numbers use this |
| **lexical** (core, stdlib only) | spelling only (`revenue` ~ `revenues`) | graceful fallback when torch is unavailable |

### Getting the best results

**Install `[embeddings]` wherever you run it, including CI.** `gate="auto"` (the default) then uses
the embedding gate automatically and only falls back to lexical if the extra is absent. "Optional" is
a packaging choice, not a recommendation to skip it — for best results, do not skip it.

One caveat worth knowing: `auto` falls back **silently**. If you must be sure you are on the
validated gate — for example, so CI cannot quietly score on the weaker one after someone forgets the
extra — ask for it explicitly with `gate="embeddings"` (library) or `--gate embeddings` (CLI). That
**errors** when the extra is not installed rather than degrading.

## Findings

Each finding is a frozen `Finding`: a `type`, a `danger` (`high` / `medium` / `low`), a `note`, and
the `items` (`Item` with `id` / `label` / `layer`) that collide. `Finding.to_dict()` and the
top-level `as_dicts()` render them for JSON. Types: `SCOPE_TRAP`, `CONCEPT_FORK`,
`DEFINITION_DIVERGENCE`, `GRAIN_MISMATCH`, `NAME_COLLISION`, `SIBLING`, `DUPLICATE`.

## Layout

Pure transforms, I/O at the edges — so every stage tests in isolation and the pairwise work is
parallel-safe (nothing mutates).

| module | responsibility |
|---|---|
| `model.py` | immutable value types: `GroundingFact`, `Finding`, `Item`, `Classification`, `DetectConfig` |
| `scope.py` | population algebra: parse predicates, compare/subsume populations (pure) |
| `adapters.py` | `facts_from_*` (pure, content in) + `adapt_*` (thin file readers) + `load_env` |
| `gate.py` | the confusability gate: lexical (stdlib) or embeddings (optional) |
| `detect.py` | `classify` one pair, build edges, cluster, rank — composed by `detect_collisions` |
