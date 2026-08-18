"""preflight — static, cross-layer ambiguity detection for governed analytics grounding.

Before an agent ever runs a query, compare the governed definitions it could ground on — semantic
metrics, warehouse columns and views, documented terms — and report the pairs a competent reader
would confuse and that resolve to different numbers. The structural detection needs no model;
embeddings are an optional extra that sharpens which name-pairs are worth comparing.

    from preflight import scan
    for f in scan("path/to/environment"):          # Finding objects, most dangerous first
        print(f.danger, f.type, [it.label for it in f.items], "—", f.note)

`scan` reads the conventional layout (semantic/semantic_layer.yml, warehouse/schema.sql,
docs/data_dictionary.md). To ground on other artifacts, assemble GroundingFacts with the adapters
and call detect_collisions directly. `as_dicts` renders findings as plain JSON-ready dicts.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .adapters import (
    adapt_docs,
    adapt_queries,
    adapt_semantic,
    adapt_warehouse,
    facts_from_docs,
    facts_from_queries,
    facts_from_semantic,
    facts_from_warehouse,
    line_of_definition,
    load_env,
    with_yaml_sources,
)
from .cube import facts_from_cube_js, facts_from_cube_yaml, load_cube
from .dbt_manifest import load_dbt_manifest
from .dbt_sql import facts_from_dbt_model, load_dbt_project
from .detect import classify, detect_collisions, is_plumbing, partition, rank
from .gate import make_gate
from .metricflow import facts_from_metricflow, load_metricflow
from .model import (
    Classification,
    DetectConfig,
    Finding,
    GroundingFact,
    Item,
    Recovered,
    Source,
)

__all__ = [
    # high-level
    "scan", "as_dicts", "detect_collisions",
    # value types
    "GroundingFact", "Finding", "Item", "Classification", "Recovered", "DetectConfig", "Source",
    # adapters (I/O)
    "load_env", "adapt_semantic", "adapt_warehouse", "adapt_docs", "adapt_queries",
    # adapters (pure)
    "facts_from_semantic", "facts_from_warehouse", "facts_from_docs", "facts_from_queries",
    # source provenance (for citing findings back to path:line)
    "line_of_definition", "with_yaml_sources",
    # dbt MetricFlow dialect
    "load_metricflow", "facts_from_metricflow",
    # native dbt project (compiled manifest.json — all three layers)
    "load_dbt_manifest",
    # raw dbt-SQL dialect
    "load_dbt_project", "facts_from_dbt_model",
    # Cube dialect
    "load_cube", "facts_from_cube_yaml", "facts_from_cube_js",
    # detector internals, exposed for composition/testing
    "classify", "partition", "rank", "is_plumbing", "make_gate",
]

__version__ = "0.1.0"


def scan(env_dir: str | Path, *, gate: str = "auto", model=None,
         config: DetectConfig | None = None) -> list[Finding]:
    """Load the conventional artifact layout under `env_dir` and detect collisions across all layers.
    `gate` / `model` / `config` are passed through to detect_collisions."""
    return detect_collisions(load_env(env_dir), gate=gate, model=model, config=config)


def as_dicts(findings: Iterable[Finding]) -> list[dict]:
    """Render findings as plain JSON-ready dicts (the wire format used by the experiment scripts)."""
    return [f.to_dict() for f in findings]
