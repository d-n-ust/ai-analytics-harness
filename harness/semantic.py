"""The semantic layer (rung 3): a small YAML of governed metrics compiled to SQL.

A metric names one correct definition (the right grain, the right filters, the
right math) so the agent *selects* a metric instead of writing — and possibly
mis-writing — the SQL itself. This is the layer that turns "MRR computed the
model's way" into "MRR computed our way", every time.

The compiler is deliberately small: one base table per metric (the star's marts
are pre-joined, so no join resolution is needed), an aggregate expression, an
optional time column for ranges/grains, and a whitelist of filterable dimensions.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .config import NAMED_PERIODS, resolve_period
from .warehouse import run_query

SPEC_PATH = Path(__file__).resolve().parent.parent / "grounding" / "rung3_semantic" / "semantic_layer.yml"


class SemanticError(Exception):
    """Raised for an unknown metric, dimension, or filter — surfaced to the agent."""


def _literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


class SemanticLayer:
    def __init__(self, con, spec_path: Path = SPEC_PATH):
        self.con = con
        self.spec = yaml.safe_load(spec_path.read_text())
        self.metrics: dict[str, dict] = self.spec["metrics"]

    # -- introspection the agent sees -------------------------------------- #
    def list_metrics_text(self) -> str:
        lines = ["Governed metrics (call query_metric with these names):"]
        for name, m in self.metrics.items():
            dims = m.get("dimensions", [])
            bits = [f"- {name}: {m['description']}"]
            if dims:
                bits.append(f"    group_by / filter dimensions: {', '.join(dims)}")
            if m.get("supports_internal_filter"):
                bits.append("    supports filter is_internal=false")
            if m.get("time_column"):
                bits.append("    time-filterable (period=…) and grainable (time_grain=week|month|day)")
            else:
                bits.append("    point-in-time (as of now); no period filter")
            lines.append("\n".join(bits))
        lines.append(f"\nNamed periods: {', '.join(NAMED_PERIODS)} (or pass explicit start/end 'YYYY-MM-DD').")
        return "\n".join(lines)

    # -- compilation ------------------------------------------------------- #
    def _allowed_filters(self, m: dict) -> set[str]:
        allowed = set(m.get("dimensions", [])) | set(m.get("filterable", []))
        if m.get("supports_internal_filter"):
            allowed.add("is_internal")
        return allowed

    def compile(self, name, group_by=None, filters=None, time_grain=None,
                start=None, end=None, period=None) -> str:
        if name not in self.metrics:
            raise SemanticError(
                f"unknown metric {name!r}. Available: {', '.join(self.metrics)}")
        m = self.metrics[name]
        time_col = m.get("time_column")

        select, group = [], []
        if time_grain:
            if not time_col:
                raise SemanticError(f"metric {name!r} has no time dimension to grain by.")
            select.append(f"date_trunc('{time_grain}', {time_col})::date AS period")
            group.append("period")
        for d in group_by or []:
            if d not in m.get("dimensions", []):
                raise SemanticError(
                    f"cannot group {name!r} by {d!r}. Dimensions: {m.get('dimensions', [])}")
            select.append(d)
            group.append(d)
        select.append(f"{m['agg']} AS value")

        where = list(m.get("default_filters", []))
        if period is not None:
            start, end = resolve_period(period)
        if (start or end) and not time_col:
            raise SemanticError(f"metric {name!r} is point-in-time; it takes no period.")
        if start and time_col:
            where.append(f"{time_col} >= DATE '{start}'")
        if end and time_col:
            where.append(f"{time_col} <= DATE '{end}'")

        allowed = self._allowed_filters(m)
        for col, val in (filters or {}).items():
            if col not in allowed:
                raise SemanticError(
                    f"cannot filter {name!r} by {col!r}. Allowed: {sorted(allowed)}")
            if isinstance(val, (list, tuple)):
                where.append(f"{col} IN ({', '.join(_literal(v) for v in val)})")
            else:
                where.append(f"{col} = {_literal(val)}")

        sql = f"SELECT {', '.join(select)} FROM {m['base']}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if group:
            sql += " GROUP BY " + ", ".join(group) + " ORDER BY " + ", ".join(group)
        return sql

    def query(self, name, **kw) -> tuple[list[str], list[tuple]]:
        return run_query(self.con, self.compile(name, **kw))

    def scalar(self, name, *, filters=None, start=None, end=None, period=None):
        """One number for one metric over one period (used by the metric tree)."""
        _, rows = self.query(name, filters=filters, start=start, end=end, period=period)
        if not rows or rows[0][0] is None:
            return None
        return float(rows[0][0])
