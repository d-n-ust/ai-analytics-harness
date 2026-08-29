#!/usr/bin/env python3
"""Materialise the dbt models into DuckDB, without dbt-core.

The models under `models/` are ordinary dbt: `{{ source(...) }}` and `{{ ref(...) }}`, one SELECT
per file, no macros. dbt-core plus an adapter is 50-odd packages and a profile file, and the repo
already decided against that dependency for MetricFlow (semantic/metricflow_engine.py). So this
resolves the two functions it needs, sorts the models by their refs, and creates one view per file.

`dbt build` against a duckdb profile produces the same objects from the same files. Nothing here is
a dialect of dbt; it is a subset of it, and the subset is stated:

    {{ source('raw', 'x') }}   ->  "_source".x        the generated warehouse, untouched
    {{ ref('y') }}             ->  wh_06.y            a model in this project

    python build.py            # create or replace every model
    python build.py --drop     # drop the schema first, so a renamed model cannot outlive its file
"""
from __future__ import annotations

import argparse
import pathlib
import re

from warehouse.warehouse import open_warehouse

HERE = pathlib.Path(__file__).resolve().parent
MODELS = HERE / "models"
SCHEMA = "wh_06"

_SOURCE = re.compile(r"\{\{\s*source\(\s*['\"](\w+)['\"]\s*,\s*['\"](\w+)['\"]\s*\)\s*\}\}")
_REF = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")

# The raw schemas a source name maps to. One entry, and it is the generated warehouse — the point of
# the experiment is that the mess is the one every other experiment already runs on.
SOURCE_SCHEMA = {"raw": "_source"}


# WHICH SCHEMA EACH LAYER LANDS IN. dbt's own convention, and here it is load-bearing rather than
# tidy: the agent is given ONE schema to read, so staging and intermediate must not be in it.
# `stg_users` is the messy source with the casing fixed and nothing else decided; `int_*` are spine
# tables that exist only to build a mart. An agent that can reach them can answer from a layer that
# has had no business logic applied and looks exactly like one that has.
LAYER_SUFFIX = {"staging": "_stg", "intermediate": "_int", "marts": ""}


def _layer_of(path, root) -> str:
    """The layer a model file belongs to, from its directory. Unfiled models land in marts, which
    is the safe default: a model nobody classified is visible rather than silently hidden."""
    rel = path.relative_to(root).parts
    return rel[0] if len(rel) > 1 and rel[0] in LAYER_SUFFIX else "marts"


def _models(root=None) -> dict[str, str]:
    """{model name -> SQL}, from every .sql file under a models directory. The file name is the
    model name, which is dbt's own rule and the reason no manifest is needed to find one."""
    root = root or MODELS
    return {p.stem: p.read_text() for p in sorted(root.rglob("*.sql"))}


def _schemas(root, schema: str) -> dict[str, str]:
    """{model name -> the schema it is built into}."""
    root = root or MODELS
    return {p.stem: schema + LAYER_SUFFIX[_layer_of(p, root)] for p in sorted(root.rglob("*.sql"))}


def _refs(sql: str) -> set[str]:
    return set(_REF.findall(sql))


def _ordered(models: dict[str, str]) -> list[str]:
    """Model names in dependency order.

    A plain repeated sweep rather than a graph library: the project has seven models, and a cycle
    shows up as a sweep that places nothing, which is reported rather than looped on."""
    placed: list[str] = []
    remaining = dict(models)
    while remaining:
        ready = [n for n, sql in remaining.items() if _refs(sql) <= set(placed)]
        if not ready:
            raise SystemExit(f"circular or missing ref among: {', '.join(sorted(remaining))}")
        for name in sorted(ready):
            placed.append(name)
            del remaining[name]
    return placed


def _compile(sql: str, schema: str = SCHEMA, schemas: dict | None = None) -> str:
    sql = _SOURCE.sub(lambda m: f'"{SOURCE_SCHEMA[m.group(1)]}".{m.group(2)}', sql)
    return _REF.sub(lambda m: f"{(schemas or {}).get(m.group(1), schema)}.{m.group(1)}", sql)


def build(con, drop: bool = False, root=None, schema: str = SCHEMA) -> list[str]:
    """Materialise one models directory into one schema.

    Parameterised so a SECOND warehouse can live beside the first rather than replacing it. The
    original stays exactly as it is, because every number measured in this experiment was measured
    against it and a rebuilt fixture is not a comparison.
    """
    schemas = _schemas(root, schema)
    for target in sorted(set(schemas.values())):
        if drop:
            con.execute(f"DROP SCHEMA IF EXISTS {target} CASCADE")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {target}")
    models = _models(root)
    built = []
    for name in _ordered(models):
        into = schemas[name]
        con.execute(f"CREATE OR REPLACE VIEW {into}.{name} AS\n"
                    f"{_compile(models[name], schema, schemas)}")
        built.append((into, name))
    return built


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default=None, help="models directory (default: ./models)")
    ap.add_argument("--schema", default=SCHEMA, help=f"target schema (default: {SCHEMA})")
    ap.add_argument("--drop", action="store_true",
                    help="drop the schema first, so a model renamed in git cannot survive as an object")
    args = ap.parse_args()
    con = open_warehouse(create_star_views=True)
    root = pathlib.Path(args.models) if args.models else None
    built = build(con, drop=args.drop, root=root, schema=args.schema)
    print(f"built {len(built)} models:")
    for into, name in built:
        n = con.execute(f"SELECT count(*) FROM {into}.{name}").fetchone()[0]
        print(f"  {into + '.' + name:44} {n:>8,} rows")


if __name__ == "__main__":
    main()
