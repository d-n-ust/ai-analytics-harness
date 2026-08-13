"""The adapter layer: the small set of things that genuinely differ between SQL engines.

This module is deliberately tiny, and that is a measured claim rather than optimism. The SQL the
semantic compiler emits is:

    SELECT <aggs> FROM <base> WHERE <predicates> GROUP BY <dims> ORDER BY <dims>

which is ANSI. Auditing the compiler it was ported from turned up exactly one dialect-specific
construct in everything it generated — a `date_trunc(...)::date` cast — because the aggregate
expressions themselves come from the semantic spec and are therefore the spec author's
responsibility, not the compiler's.

So a `Dialect` is not a SQL translation layer and must not grow into one. If a method here starts
needing to rewrite an expression tree, that is the signal to bring in `sqlglot` and transpile,
rather than to accumulate per-engine string surgery.

Identifier quoting is included even though nothing needs it yet. Unquoted identifiers case-fold
in opposite directions across engines — Postgres and DuckDB to lower, Snowflake to upper — so a
dimension called `Region` resolves differently depending on where it runs. That bug is silent,
returns plausible numbers, and is exactly the class this product exists to refuse.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable

TimeGrain = str  # "day" | "week" | "month" | "quarter" | "year"

GRAINS: tuple[TimeGrain, ...] = ("day", "week", "month", "quarter", "year")


class DialectError(Exception):
    """A construct this engine cannot express. Surfaced to the agent as a refusal reason rather
    than raised past it: 'this warehouse cannot group by week' is an answerable-but-not-here
    situation, and the typed refusal channel exists precisely for that."""


@runtime_checkable
class Dialect(Protocol):
    """What the semantic compiler needs to know about the target engine."""

    @property
    def name(self) -> str:
        """Stable identifier, e.g. 'duckdb'. Reported in traces and in the disclosure line, so a
        user reading compiled SQL knows which flavour they are reading."""
        ...

    def quote_ident(self, name: str) -> str:
        """Quote an identifier so case and reserved words survive."""
        ...

    def date_literal(self, value: dt.date) -> str:
        """Render a date as a literal.

        Takes a `date`, never a string. Every value that reaches SQL by interpolation is a place
        an injection can hide, and a typed parameter cannot carry one. The caller is forced to
        have parsed the value before it gets here.
        """
        ...

    def truncate_date(self, expr: str, grain: TimeGrain) -> str:
        """Truncate a timestamp/date expression to `grain`, yielding a DATE.

        The one construct that reliably differs. Implementations must return a DATE rather than a
        timestamp, so grouped periods compare and sort identically across engines.
        """
        ...

    def limit(self, sql: str, n: int) -> str:
        """Apply a row cap. Separate from `execute`'s fetch cap on purpose: fetching fewer rows
        still makes the database compute all of them, and on a metered warehouse that is the
        difference between a cheap query and an expensive one."""
        ...

    def string_literal(self, value: str) -> str:
        """Quote a string literal with the engine's escaping rules."""
        ...
