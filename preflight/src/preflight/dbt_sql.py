"""Adapter for raw dbt models (no semantic layer): recover metric-shaped marts from their SQL.

Most warehouses have no governed semantic layer — the "metrics" are dbt models whose SQL is
`SUM(...) ... WHERE ...`. This adapter de-templates dbt Jinja, parses each model with sqlglot, and
recovers one grounding fact per aggregated output column (its alias, the aggregate, the measured
column, the source table, and the filter), so the detector can compare metric-shaped marts across a
project.

It is CTE-aware: an aggregate defined in a CTE is recovered from that CTE's scope (its FROM and
WHERE), not the final passthrough SELECT — which is where the recoverable signal usually lives. It is
also best-effort: a model that does not parse is skipped, and load_dbt_project reports coverage.
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import traverse_scope

from .adapters import additivity, entity_from_base
from .model import GroundingFact
from .scope import build_scope

_REF = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_SOURCE = re.compile(r"\{\{\s*source\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_JINJA_STMT = re.compile(r"\{%.*?%\}", re.DOTALL)
_JINJA_EXPR = re.compile(r"\{\{.*?\}\}", re.DOTALL)


def _dejinja(sql: str) -> str:
    """Turn dbt Jinja into plain SQL sqlglot can parse: ref/source resolve to their table name,
    control tags and remaining `{{ ... }}` (config, var, macros) are removed."""
    sql = _REF.sub(lambda m: m.group(1), sql)
    sql = _SOURCE.sub(lambda m: m.group(1), sql)
    sql = re.sub(r"\{\{\s*this\s*\}\}", "this_model", sql)
    sql = _JINJA_STMT.sub(" ", sql)
    sql = _JINJA_EXPR.sub(" ", sql)
    return sql


def _norm(t: str | None) -> str | None:
    return t.split(".")[-1].strip().lower() if t else None


def _base_of(scope) -> str | None:
    """The first physical source table feeding this scope (CTE references are not physical)."""
    for src in scope.sources.values():
        if isinstance(src, exp.Table):
            return _norm(src.name)
    return None


def _scope_filter(select: exp.Select) -> tuple:
    where = select.args.get("where")
    return build_scope(where.this.sql()) if where else ()


# Only these aggregations denote a metric (a number leadership tracks). MIN/MAX/etc. over a column
# are almost always dimensional grabs ("one value per group"), not measures — including them floods
# the output with false collisions between date/dimension columns that merely share a name-stem.
_MEASURE_AGGS = ("sum", "count", "count_distinct")


def _aggregations(select: exp.Select):
    """(alias, agg, measure) per aggregated projection that is a measure (sum/count) and not a
    window function."""
    out = []
    for proj in select.selects:
        alias = proj.alias_or_name
        if not alias:
            continue
        agg = next((af for af in proj.find_all(exp.AggFunc)
                    if af.find_ancestor(exp.Window) is None), None)
        if agg is None:
            continue
        key = agg.key.lower()
        if isinstance(agg, exp.Count) and agg.this is not None and agg.this.find(exp.Distinct):
            key = "count_distinct"
        if key not in _MEASURE_AGGS:
            continue
        measure = agg.this.sql().lower() if agg.this is not None else None
        out.append((alias.lower(), key, measure))
    return out


def facts_from_dbt_model(sql: str, model: str) -> list[GroundingFact]:
    """Recover grounding facts (one per aggregated output column) from one dbt model's SQL."""
    try:
        tree = sqlglot.parse_one(_dejinja(sql), read="snowflake")
        scopes = traverse_scope(tree) if tree is not None else []
    except SqlglotError:                          # unparseable model SQL -> no facts from it
        return []
    facts: list[GroundingFact] = []
    seen: set[str] = set()
    for scope in scopes:
        select = scope.expression
        if not isinstance(select, exp.Select):
            continue
        base = _base_of(scope)
        preds = _scope_filter(select)
        for alias, agg, measure in _aggregations(select):
            if alias in seen:                 # one fact per output name per model
                continue
            seen.add(alias)
            facts.append(GroundingFact(
                id=f"dbt:{model}.{alias}", label=alias, layer="queries", kind="query",
                agg=agg, measure=measure, base=base, entity=entity_from_base(base),
                additive=additivity(agg), scope=preds,
                text=f"{alias.replace('_', ' ')} in dbt model {model}"))
    return facts


def load_dbt_project(path: str | Path) -> list[GroundingFact]:
    """Load metric-shaped facts from a dbt project's model SQL (a file or a directory of *.sql)."""
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.rglob("*.sql"))
    facts: list[GroundingFact] = []
    for f in files:
        facts += facts_from_dbt_model(f.read_text(), f.stem)
    return facts
