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

## Use

```python
from preflight import scan

# conventional layout: semantic/semantic_layer.yml, warehouse/schema.sql, docs/data_dictionary.md
findings = scan("path/to/environment")           # most dangerous first
for f in findings:
    print(f["danger"], f["type"], [it["label"] for it in f["items"]], "—", f["note"])
```

Grounding on other artifacts? Assemble facts with the adapters and detect directly:

```python
from preflight import adapt_semantic, adapt_warehouse, detect_collisions

facts = adapt_semantic(sem_path) + adapt_warehouse(schema_path)
findings = detect_collisions(facts, gate="lexical")   # or "auto" / "embeddings"
```

## The gate

Similarity decides only **which name-pairs are worth examining**, never whether a collision is
dangerous — that is decided structurally (same measure under a subset population, same concept over
different columns, same term with divergent scope, and so on). `gate="auto"` uses embeddings when
installed and falls back to a dependency-free lexical gate, so the tool always runs; the published
accuracy numbers use the embedding gate.

## Findings

Each finding is a clustered group with a `type`, a `danger` (`high` / `medium` / `low`), a `note`,
and the `items` that collide. Types: `SCOPE_TRAP`, `CONCEPT_FORK`, `DEFINITION_DIVERGENCE`,
`GRAIN_MISMATCH`, `NAME_COLLISION`, `SIBLING`, `DUPLICATE`.
