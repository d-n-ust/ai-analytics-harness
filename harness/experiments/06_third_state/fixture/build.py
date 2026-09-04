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


# The layer a model belongs to decides which schema it lands in — dbt's convention, and here it is
# load-bearing: the agent is scoped to the MARTS schema, so staging must sit elsewhere or an
# unmodelled staging table would show up beside the documented facts.
LAYER_SUFFIX = {"staging": "_stg", "intermediate": "_int", "marts": ""}


def _models(root=None) -> dict[str, str]:
    """{model name -> SQL}, from every .sql file under a models directory. The file name is the
    model name, which is dbt's own rule and the reason no manifest is needed to find one."""
    return {p.stem: p.read_text() for p in sorted((root or MODELS).rglob("*.sql"))}


def _schema_of(name: str, root=None) -> str:
    """The schema a model lands in, from the sub-directory it sits in (marts is the default)."""
    for path in (root or MODELS).rglob(f"{name}.sql"):
        parts = path.relative_to(root or MODELS).parts
        if len(parts) > 1 and parts[0] in LAYER_SUFFIX:
            return LAYER_SUFFIX[parts[0]]
    return ""


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


def _compile(sql: str, schema: str = SCHEMA, ref_schema=None) -> str:
    sql = _SOURCE.sub(lambda m: f'"{SOURCE_SCHEMA[m.group(1)]}".{m.group(2)}', sql)
    return _REF.sub(lambda m: f"{(ref_schema or (lambda n: schema))(m.group(1))}.{m.group(1)}", sql)


def build(con, drop: bool = False, root=None, schema: str = SCHEMA) -> list[str]:
    """Materialise one models directory into one schema.

    Parameterised so a SECOND warehouse can live beside the first rather than replacing it. The
    original stays exactly as it is, because every number measured in this experiment was measured
    against it and a rebuilt fixture is not a comparison.
    """
    models = _models(root)
    target = lambda n: (schema + _schema_of(n, root))          # marts -> schema, staging -> _stg
    for s in sorted({target(n) for n in models}):
        if drop:
            con.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
    built = []
    for name in _ordered(models):
        con.execute(f"CREATE OR REPLACE VIEW {target(name)}.{name} AS\n"
                    f"{_compile(models[name], schema, target)}")
        built.append(name)
    _apply_docs(con, root or MODELS, schema)
    return built


def _apply_docs(con, root: pathlib.Path, schema: str) -> None:
    """Persist table and column descriptions from marts/schema.yml as COMMENT ON — dbt's
    `persist_docs`. `warehouse.schema_text` reads these back, so a documented mart reaches the agent
    as documentation rather than as bare names and types. Silently does nothing when no docs file
    exists, so an undocumented project still builds."""
    docs = root / "marts" / "schema.yml"
    if not docs.is_file():
        return
    import yaml
    spec = yaml.safe_load(docs.read_text()) or {}
    esc = lambda s: str(s).replace("'", "''")
    for model in spec.get("models", []):
        name = model["name"]
        if model.get("description"):
            con.execute(f"COMMENT ON VIEW {schema}.{name} IS '{esc(model['description'])}'")
        cols = {c[0] for c in con.execute(f"DESCRIBE {schema}.{name}").fetchall()}
        for col in model.get("columns", []):
            if col.get("description") and col["name"] in cols:
                con.execute(f"COMMENT ON COLUMN {schema}.{name}.{col['name']} IS "
                            f"'{esc(col['description'])}'")
            elif col.get("description"):
                print(f"  doc skipped: {name}.{col['name']} is not a column")


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
    root = pathlib.Path(args.models) if getattr(args, "models", None) else None
    print(f"built {len(built)} models:")
    for name in built:
        into = args.schema + _schema_of(name, root)
        n = con.execute(f"SELECT count(*) FROM {into}.{name}").fetchone()[0]
        print(f"  {into + '.' + name:34} {n:>8,} rows")


if __name__ == "__main__":
    main()
