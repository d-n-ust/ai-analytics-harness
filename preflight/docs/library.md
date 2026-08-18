# preflight — library use

`preflight` is a library as well as a CLI. Import `scan` for the conventional layout, or assemble facts
with the adapters and call `detect_collisions` directly.

## Scan a conventional environment

```python
from preflight import scan

# conventional layout: semantic/semantic_layer.yml, warehouse/schema.sql, docs/data_dictionary.md
findings = scan("path/to/environment")           # list[Finding], most dangerous first
for f in findings:
    print(f.danger, f.type, [it.label for it in f.items], "—", f.note)
```

## Ground on other artifacts

Assemble facts with the adapters and detect directly:

```python
from preflight import adapt_semantic, adapt_warehouse, detect_collisions, as_dicts

facts = adapt_semantic(sem_path) + adapt_warehouse(schema_path)
findings = detect_collisions(facts, gate="lexical")   # or "auto" / "embeddings"
payload = as_dicts(findings)                          # JSON-ready plain dicts
```

For a whole dbt project, `load_dbt_manifest("path/to/project")` returns the facts across all three
layers from `target/manifest.json`.

## Tune sensitivity

Pass a `DetectConfig` instead of editing the package:

```python
from preflight import DetectConfig, detect_collisions
detect_collisions(facts, config=DetectConfig(gate=0.6, min_shared_facets=2))
```

## The Finding object

Each finding is a frozen `Finding`: a `type`, a `danger` (`high` / `medium` / `low`), a `note`, and the
`items` (`Item` with `id` / `label` / `layer`) that collide. `Finding.to_dict()` and the top-level
`as_dicts()` render them for JSON. The seven types, with a worked example and fix for each, are in
[catalog.md](catalog.md).

## Package layout

Pure transforms, I/O at the edges — every stage tests in isolation and the pairwise work is
parallel-safe (nothing mutates).

| module | responsibility |
|---|---|
| `model.py` | immutable value types: `GroundingFact`, `Finding`, `Item`, `Classification`, `DetectConfig` |
| `scope.py` | population algebra: parse predicates, compare/subsume populations (pure) |
| `adapters.py` | `facts_from_*` (pure, content in) + `adapt_*` (thin file readers) + `load_env` |
| `gate.py` | the confusability gate: lexical (stdlib) or embeddings (optional) |
| `detect.py` | `classify` one pair, build edges, cluster, rank — composed by `detect_collisions` |
