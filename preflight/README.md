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

```bash
pip install preflight                 # core: structural detection on a lexical gate
pip install "preflight[embeddings]"   # + sentence-transformers for the sharper, validated gate
```

## Use — terminal

```bash
preflight scan path/to/environment                 # human-readable, grouped by danger
preflight scan path/to/environment --format json   # machine-readable
preflight scan path/to/environment --min-danger high --fail-on high
```

`scan` reads whichever of `semantic/semantic_layer.yml`, `warehouse/schema.sql`, and
`docs/data_dictionary.md` are present. It exits non-zero when a finding at or above `--fail-on`
(default `high`) exists, so it gates CI. `--gate auto` uses embeddings when installed, else lexical.

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

## The gate

Similarity decides only **which name-pairs are worth examining**, never whether a collision is
dangerous — that is decided structurally (same measure under a subset population, same concept over
different columns, same term with divergent scope, and so on). `gate="auto"` uses embeddings when
installed and falls back to a dependency-free lexical gate, so the tool always runs; the published
accuracy numbers use the embedding gate.

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
