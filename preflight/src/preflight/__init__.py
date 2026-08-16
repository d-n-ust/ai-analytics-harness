"""preflight — static, cross-layer ambiguity detection for governed analytics grounding.

Before an agent ever runs a query, compare the governed definitions it could ground on — semantic
metrics, warehouse columns and views, documented terms — and report the pairs a competent reader
would confuse and that resolve to different numbers. The structural detection needs no model;
embeddings are an optional extra that sharpens which name-pairs are worth comparing.

    from preflight import scan
    findings = scan("path/to/environment")     # collision findings, most dangerous first

`scan` reads the conventional layout (semantic/semantic_layer.yml, warehouse/schema.sql,
docs/data_dictionary.md). To ground on other artifacts, assemble GroundingFacts with the adapters
and call detect_collisions directly.
"""

from __future__ import annotations

from pathlib import Path

from .detect import classify, detect_collisions
from .grounding import (
    GroundingFact,
    adapt_docs,
    adapt_queries,
    adapt_semantic,
    adapt_warehouse,
    load_env,
)

__all__ = [
    "scan",
    "detect_collisions",
    "classify",
    "GroundingFact",
    "load_env",
    "adapt_semantic",
    "adapt_warehouse",
    "adapt_docs",
    "adapt_queries",
]

__version__ = "0.1.0"


def scan(env_dir, *, gate="auto", model=None):
    """Load the conventional artifact layout under `env_dir` and detect collisions across all
    layers. `gate`/`model` are passed through to detect_collisions."""
    return detect_collisions(load_env(Path(env_dir)), gate=gate, model=model)
