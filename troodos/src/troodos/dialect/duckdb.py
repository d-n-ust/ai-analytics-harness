"""DuckDB dialect. Also the reference implementation — it is the shortest possible Dialect,
which is the point: if a second one is much longer, the extra length is a bug in the compiler,
not a fact about the engine."""

from __future__ import annotations

import datetime as dt

from .base import GRAINS, DialectError, TimeGrain


class DuckDBDialect:
    name = "duckdb"

    def quote_ident(self, name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    def string_literal(self, value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def date_literal(self, value: dt.date) -> str:
        if not isinstance(value, dt.date):
            raise DialectError(f"date_literal needs a date, got {type(value).__name__}")
        return f"DATE '{value.isoformat()}'"

    def truncate_date(self, expr: str, grain: TimeGrain) -> str:
        if grain not in GRAINS:
            raise DialectError(f"unknown time grain {grain!r}; use one of {', '.join(GRAINS)}")
        # The cast is not cosmetic. date_trunc returns TIMESTAMP, so without it a period column
        # is a timestamp at midnight — which compares unequal to the DATE literals the same query
        # filters on, and silently returns nothing.
        return f"date_trunc('{grain}', {expr})::date"

    def limit(self, sql: str, n: int) -> str:
        return f"{sql} LIMIT {int(n)}"
