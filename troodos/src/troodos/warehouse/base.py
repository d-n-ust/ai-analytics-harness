"""The connection layer: what the engine is allowed to know about a database.

Everything above this module talks to `Warehouse`, never to a driver. That is what lets the
same agent, the same semantic compiler and the same guardrails run against a local DuckDB file,
MotherDuck, Postgres or Snowflake without any of them learning a second SQL flavour.

Two design decisions worth stating, because both were bought with evidence:

`assert_read_only` is on the Protocol, not a mixin or a helper. A warehouse that cannot say
"this statement only reads" is not a warehouse this product will talk to, so the requirement is
structural rather than advisory. The DuckDB adapter implements it against the real parser — a
`sql.startswith("select")` check is defeated by a leading comment, a CTE, or a chained second
statement, and the adapter it replaced was written that way. Adapters that have no parser must
say so by refusing to implement it, not by degrading to prefix matching.

Introspection returns comments. Every warehouse worth connecting to carries table and column
descriptions (DuckDB `COMMENT ON`, Postgres `obj_description`, Snowflake and BigQuery natively),
and dbt's `persist_docs` writes model documentation into them. That text is the cheapest
grounding available: it is already written, already reviewed, and already lives next to the data.
It is not a substitute for a governed metric definition — it carries no grain, no filters and no
math — but it is what turns a blank-page onboarding into a mostly-filled-in one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class WarehouseError(Exception):
    """A connection, query or permission failure, carrying the database's own message.

    The message is surfaced to the model verbatim: an agent's self-correction loop is only as
    good as the error it is shown, and a wrapped "query failed" teaches it nothing about which
    column it hallucinated.
    """


class ReadOnlyViolation(WarehouseError):
    """A statement that is not a single read. Raised before anything reaches the database."""


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str | None = None
    nullable: bool = True


@dataclass(frozen=True)
class Relation:
    """A table or view the agent may see.

    `kind` is kept because it is a governance signal, not decoration: in a modelled warehouse the
    views are usually the curated layer and the tables the raw one, so a caller narrowing what the
    agent may touch will often narrow by exactly this.
    """

    name: str
    kind: str  # "table" | "view"
    schema: str | None = None
    comment: str | None = None
    columns: tuple[Column, ...] = field(default_factory=tuple)

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    @property
    def documented(self) -> bool:
        """Whether this relation carries any human-written description, on itself or a column.

        The bootstrapper sorts by this: a warehouse where `persist_docs` has run is a far better
        starting point for a semantic spec than one where it has not, and the user should be told
        which they have rather than left to guess from a half-empty draft.
        """
        return bool(self.comment) or any(c.comment for c in self.columns)


@dataclass(frozen=True)
class Result:
    """The outcome of one read. Deliberately not a DataFrame.

    The engine formats these into text for a model and hands them to the guardrails for numeric
    checks; neither needs indexing, joins or dtypes. Keeping the boundary at plain tuples is what
    keeps pandas out of the dependency set, and pandas is the single largest obstacle to shipping
    a signed macOS bundle later.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def scalar(self):
        """The single value of a 1x1 result, or None. Used by the numeric guardrails."""
        if len(self.rows) == 1 and len(self.rows[0]) == 1:
            return self.rows[0][0]
        return None


@runtime_checkable
class Warehouse(Protocol):
    """The contract every database adapter implements."""

    @property
    def dialect(self) -> object:
        """The `Dialect` this warehouse speaks. The semantic compiler asks the warehouse rather
        than being configured separately, so a connection and its SQL flavour cannot disagree."""
        ...

    @property
    def label(self) -> str:
        """Human-readable identity for traces and error messages, e.g. 'duckdb:analytics.db'.
        Must never contain a credential."""
        ...

    def relations(self) -> tuple[Relation, ...]:
        """Every table and view visible to this connection, with comments and columns."""
        ...

    def assert_read_only(self, sql: str) -> None:
        """Raise `ReadOnlyViolation` unless `sql` is exactly one read statement.

        Required, not optional. Implement against the engine's own parser; do not pattern-match
        on the string.
        """
        ...

    def execute(self, sql: str, max_rows: int = 100) -> Result:
        """Run one read-only statement. Must call `assert_read_only` first.

        Raises `WarehouseError` carrying the database's own message on failure.
        """
        ...

    def close(self) -> None: ...
